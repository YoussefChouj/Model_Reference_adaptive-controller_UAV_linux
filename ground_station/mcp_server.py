"""MCP server for the drone bench toolchain.

Exposes livewatch, ulog query, sim run, and SINDy as MCP tools so any
LLM front-end (Cursor, Claude Code, Aider) can drive the drone as a native
resource. Stdio transport only for v0.

Tools NOT_IMPLEMENTED until their respective specs land:
    param_set / param_get  → agent-05
    sweep_run              → agent-07
    offboard_command       → agent-06

Safety constraints enforced here:
    livewatch_patch requires i_understand=True (--i-understand in the CLI).

The server does NOT hold a persistent pyocd session. Each tool that needs
hardware opens its own transport context and tears it down on completion.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = MCPServer("drone-bench")

# ---------------------------------------------------------------------------
# NOT_IMPLEMENTED payload helper
# ---------------------------------------------------------------------------

_NOT_IMPL_DEPENDS: dict[str, str] = {
    "param_set": "agent-05",
    "param_get": "agent-05",
    "sweep_run": "agent-07",
    "offboard_command": "agent-06",
}


def _text_result(text: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=text)])


def _not_implemented(tool_name: str) -> CallToolResult:
    dep = _NOT_IMPL_DEPENDS.get(tool_name, "its parent spec")
    return _text_result(json.dumps({"status": "not_implemented", "depends_on": dep}))


# ---------------------------------------------------------------------------
# Tool: livewatch_read
# ---------------------------------------------------------------------------

@mcp.tool(
    name="livewatch_read",
    title="livewatch read",
    description=(
        "Read one or more live variables from the running STM32F407 firmware "
        "over SWD (CMSIS-DAP) or UART5. Requires hardware. "
        "Names are DWARF-dotted paths (e.g. s_ekf.x[3]) or group:name tokens."
    ),
)
async def livewatch_read(
    names: list[str],
    elf: str | None = None,
    transport: str | None = None,
) -> CallToolResult:
    args = ["python", "-m", "ground_station.livewatch", "read"]
    if transport:
        args += ["--transport", transport]
    if elf:
        args += ["--elf", elf]
    args += names
    result = subprocess.run(
        args, capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    if result.returncode != 0:
        return _text_result(json.dumps({"status": "error", "stderr": result.stderr}))
    return _text_result(json.dumps({"status": "ok", "stdout": result.stdout}))


# ---------------------------------------------------------------------------
# Tool: livewatch_verify
# ---------------------------------------------------------------------------

@mcp.tool(
    name="livewatch_verify",
    title="livewatch verify",
    description=(
        "Prove OBJ/JX_FLY.axf matches the firmware running on the target "
        "before trusting any livewatch_read. Reads flash over SWD. "
        "Exits 0 on match, 2 on stale ELF. Requires hardware."
    ),
)
async def livewatch_verify(
    elf: str | None = None,
    chunks: int = 5,
) -> CallToolResult:
    args = ["python", "-m", "ground_station.livewatch", "verify"]
    if elf:
        args += ["--elf", elf]
    args += ["--chunks", str(chunks)]
    result = subprocess.run(
        args, capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    return _text_result(json.dumps({
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }))


# ---------------------------------------------------------------------------
# Tool: livewatch_writable
# ---------------------------------------------------------------------------

@mcp.tool(
    name="livewatch_writable",
    title="livewatch writable",
    description=(
        "List the livewatch writable registry — DWARF-dotted variable names "
        "that can be patched in RAM via livewatch_patch. "
        "Offline; no hardware required."
    ),
)
async def livewatch_writable(
    group: str | None = None,
) -> CallToolResult:
    """List RAM-writable variables via the livewatch writable subcommand."""
    args = ["python", "-m", "ground_station.livewatch", "writable"]
    if group:
        args += ["--group", group]
    result = subprocess.run(
        args, capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    return _text_result(json.dumps({
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }))


# ---------------------------------------------------------------------------
# Tool: livewatch_patch
# ---------------------------------------------------------------------------

@mcp.tool(
    name="livewatch_patch",
    title="livewatch patch",
    description=(
        "Write a new float value to a live firmware variable in RAM over SWD. "
        "SAFETY GATE: i_understand must be True. "
        "Requires hardware.  Changes are lost on power cycle."
    ),
)
async def livewatch_patch(
    name: str,
    value: float,
    i_understand: bool = False,
) -> CallToolResult:
    if not i_understand:
        return _text_result(json.dumps({
            "status": "safety_gate",
            "message": (
                "livewatch_patch writes RAM on the live target. "
                "Pass i_understand=True to confirm you accept this risk."
            ),
        }))
    args = [
        "python", "-m", "ground_station.livewatch", "patch",
        "--i-understand",
        name, str(value),
    ]
    result = subprocess.run(
        args, capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    return _text_result(json.dumps({
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }))


# ---------------------------------------------------------------------------
# Tool: ulog_query
# ---------------------------------------------------------------------------

@mcp.tool(
    name="ulog_query",
    title="ulog query",
    description=(
        "Query a PX4 ULog (.ulg) file: list topics, list fields in a topic, "
        "or extract a field's time series as JSON. "
        "Uses ground_station.ulog_query module. Offline; no hardware required."
    ),
)
async def ulog_query(
    file: str,
    action: str,  # "topics" | "fields" | "read"
    topic: str | None = None,
    field: str | None = None,
    what: str | None = None,
) -> CallToolResult:
    import sys as _sys
    args = ["python", "-m", "ground_station.ulog_query", action, file]
    if topic:
        args += ["--topic", topic]
    if field:
        args += ["--field", field]
    if what:
        args += ["--what", what]
    result = subprocess.run(
        args, capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    return _text_result(json.dumps({
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }))


# ---------------------------------------------------------------------------
# Tool: param_set / param_get — stubs until agent-05
# ---------------------------------------------------------------------------

@mcp.tool(
    name="param_set",
    title="param set",
    description="Set a MAVLink parameter on the running firmware. Stub until agent-05 lands.",
)
async def param_set(name: str, value: float) -> CallToolResult:
    return _not_implemented("param_set")


@mcp.tool(
    name="param_get",
    title="param get",
    description="Get a MAVLink parameter from the running firmware. Stub until agent-05 lands.",
)
async def param_get(name: str) -> CallToolResult:
    return _not_implemented("param_get")


# ---------------------------------------------------------------------------
# Tool: sweep_run — stub until agent-07
# ---------------------------------------------------------------------------

@mcp.tool(
    name="sweep_run",
    title="sweep run",
    description=(
        "Run a Sobol/Bayesian parameter sweep on the bench. "
        "Stub until agent-07 lands."
    ),
)
async def sweep_run(preset: str) -> CallToolResult:
    return _not_implemented("sweep_run")


# ---------------------------------------------------------------------------
# Tool: offboard_command — stub until agent-06
# ---------------------------------------------------------------------------

@mcp.tool(
    name="offboard_command",
    title="offboard command",
    description="Send a MAVLink offboard command. Stub until agent-06 lands.",
)
async def offboard_command(command: str, params: dict[str, Any] | None = None) -> CallToolResult:
    return _not_implemented("offboard_command")


# ---------------------------------------------------------------------------
# Tool: sim_run
# ---------------------------------------------------------------------------

@mcp.tool(
    name="sim_run",
    title="sim run",
    description=(
        "Run one closed-loop simulation scenario and return the metrics dict. "
        "Uses sim.run (MujocoPlant-free; pure Python). Offline; no hardware required."
    ),
)
async def sim_run(
    scenario: str = "step_roll",
    injection: bool = True,
    write_artifacts: bool = False,
) -> CallToolResult:
    try:
        from sim.run import run
        from sim import scenarios
        sc = scenarios.ALL.get(scenario)
        if sc is None:
            return _text_result(json.dumps({
                "status": "error",
                "message": f"unknown scenario {scenario!r}; available: {list(scenarios.ALL.keys())}",
            }))
        result = run(sc(), injection=injection, write_artifacts=write_artifacts)
        for k in ("log", "theta", "_cal_log"):
            result.pop(k, None)
        return _text_result(json.dumps({"status": "ok", "result": result}))
    except Exception as exc:
        return _text_result(json.dumps({"status": "error", "message": str(exc)}))


# ---------------------------------------------------------------------------
# Tool: sindy_fit
# ---------------------------------------------------------------------------

@mcp.tool(
    name="sindy_fit",
    title="SINDy fit",
    description=(
        "Fit a SINDy sparse-regression model to a flight log CSV or PX4 ulog. "
        "Returns active terms and quality metrics. "
        "Uses sim.sindy.fitter. Offline; no hardware required."
    ),
)
async def sindy_fit(
    file: str,
    axis: str = "roll",
    library: str = "match_6basis",
    n_train: float = 0.8,
) -> CallToolResult:
    try:
        from sim.sindy import load_stream_log_csv, preprocess, load_ulog
        from sim.sindy.fitter import fit_sindy
        from pathlib import Path as _P

        p = _P(file)
        if p.suffix == ".ulg":
            ds = load_ulog(p, axis=axis)
        else:
            ds = load_stream_log_csv(p, axis=axis)
        pp = preprocess(ds)
        res = fit_sindy(pp.X, dt=pp.t[1] - pp.t[0], library=library, n_train=n_train)
        return _text_result(json.dumps({
            "status": "ok",
            "active_terms": res.active_term_names(),
            "quality_metrics": res.quality_metrics,
            "library_id": res.library_id,
            "n_features": res.n_features,
            "n_terms": res.n_terms,
        }))
    except Exception as exc:
        return _text_result(json.dumps({"status": "error", "message": str(exc)}))


# ---------------------------------------------------------------------------
# call_tool override — dispatch by name
# ---------------------------------------------------------------------------

async def _handle_all_tools(
    name: str, arguments: dict[str, Any]
) -> CallToolResult:
    """Synchronous dispatch table for all tool names.

    MCPServer.call_tool is the handler registration point; we delegate to the
    registered async functions and return CallToolResult.
    """
    import asyncio

    dispatch: dict[str, Any] = {
        "livewatch_read": livewatch_read,
        "livewatch_verify": livewatch_verify,
        "livewatch_writable": livewatch_writable,
        "livewatch_patch": livewatch_patch,
        "ulog_query": ulog_query,
        "param_set": param_set,
        "param_get": param_get,
        "sweep_run": sweep_run,
        "offboard_command": offboard_command,
        "sim_run": sim_run,
        "sindy_fit": sindy_fit,
    }

    fn = dispatch.get(name)
    if fn is None:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(
                {"status": "error", "message": f"unknown tool {name!r}"}
            ))],
            is_error=True,
        )

    try:
        result = fn(**arguments)
        if asyncio.iscoroutine(result):
            result = await result
    except Exception as exc:
        text = json.dumps({"status": "error", "message": str(exc)})
        return CallToolResult(
            content=[TextContent(type="text", text=text)],
            is_error=True,
        )

    if isinstance(result, CallToolResult):
        return result

    text = str(result)
    return CallToolResult(content=[TextContent(type="text", text=text)])


# Monkey-patch MCPServer.call_tool with our dispatcher.
# This is the cleanest override point in v2 SDK.
mcp.call_tool = _handle_all_tools  # type: ignore[method-assign]

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the drone-bench MCP server over stdio."""
    import asyncio
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
