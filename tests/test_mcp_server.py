"""Tests for ground_station.mcp_server."""
from __future__ import annotations

import asyncio
import json
import re
from unittest.mock import patch

import pytest


@pytest.fixture
def server():
    """Import and return the server module."""
    from ground_station import mcp_server
    return mcp_server


@pytest.mark.anyio
async def test_list_tools_returns_expected_set(server):
    """list_tools() must return all 11 tool names."""
    tools = await server.mcp.list_tools()
    names = {t.name for t in tools}
    expected = {
        "livewatch_read",
        "livewatch_verify",
        "livewatch_writable",
        "livewatch_patch",
        "ulog_query",
        "param_set",
        "param_get",
        "sweep_run",
        "offboard_command",
        "sim_run",
        "sindy_fit",
    }
    assert names == expected, f"got {names}"


@pytest.mark.anyio
async def test_livewatch_verify_calls_verify_subcommand(server):
    """livewatch_verify must shell out to the livewatch verify subcommand."""
    captured_args: dict = {}

    def capture(*args, capture_output=True, text=True, **kwargs):
        captured_args["args"] = args
        class R:
            returncode = 0
            stdout = "ELF matches target"
            stderr = ""
        return R()

    with patch("subprocess.run", side_effect=capture):
        result = await server.livewatch_verify(elf=None, chunks=5)

    args_str = str(captured_args["args"])
    assert "verify" in args_str, f"expected 'verify' in args: {args_str}"


def test_not_implemented_returns_depends_on(server):
    """NOT_IMPLEMENTED tools return structured not_implemented with correct dep."""
    for name, dep in [("param_set", "agent-05"),
                      ("param_get", "agent-05"),
                      ("sweep_run", "agent-07"),
                      ("offboard_command", "agent-06")]:
        result = server._not_implemented(name)
        text = result.content[0].text
        data = json.loads(text)
        assert data["status"] == "not_implemented"
        assert data["depends_on"] == dep


@pytest.mark.anyio
async def test_ulog_query_routes_to_reader(server):
    """ulog_query with action=topics must invoke the ulog_query module."""
    captured_args: dict = {}

    def capture(*args, capture_output=True, text=True, cwd=None):
        captured_args["args"] = args
        class R:
            returncode = 0
            stdout = "topics listed"
            stderr = ""
        return R()

    with patch("subprocess.run", side_effect=capture):
        result = await server.ulog_query(
            file="/some/file.ulg",
            action="topics",
            topic=None,
            field=None,
            what=None,
        )

    args = captured_args.get("args", [])
    assert any("ulog_query" in str(a) for a in args), \
        f"expected ulog_query in args: {args}"


@pytest.mark.anyio
async def test_livewatch_patch_requires_safety_gate(server):
    """livewatch_patch must block without i_understand=True."""
    result = await server.livewatch_patch(
        name="foo", value=1.0, i_understand=False,
    )
    data = json.loads(result.content[0].text)
    assert data["status"] == "safety_gate"


@pytest.mark.anyio
async def test_sim_run_rejects_unknown_scenario(server):
    """sim_run must return error for unknown scenario name."""
    result = await server.sim_run(scenario="nonexistent_scenario")
    data = json.loads(result.content[0].text)
    assert data["status"] == "error"
    assert "unknown scenario" in data["message"]


@pytest.mark.anyio
async def test_sindy_fit_returns_error_for_missing_file(server):
    """sindy_fit must return error when file does not exist."""
    result = await server.sindy_fit(file="/nonexistent/path.csv", axis="roll")
    data = json.loads(result.content[0].text)
    assert data["status"] == "error"
