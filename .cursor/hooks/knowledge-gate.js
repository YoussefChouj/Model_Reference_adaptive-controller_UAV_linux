#!/usr/bin/env node
// Knowledge-stack-first nudge (Cursor beforeShellExecution hook).
// Cross-platform port of the Claude Code knowledge_gate PreToolUse hook.
// When the agent tries a RAW code search (grep/rg/findstr/Select-String/find -name),
// it asks the user to confirm — reminding it to use `ccc search` / GRAPH_REPORT.md first.
// Non-destructive: returns "ask", never "deny". failClosed:false → if this errors, the shell proceeds.

let raw = "";
process.stdin.on("data", (d) => (raw += d));
process.stdin.on("end", () => {
  let cmd = "";
  try {
    cmd = String(JSON.parse(raw).command || "");
  } catch (_) {
    return out({ permission: "allow" });
  }

  const rawSearch =
    /\b(grep|rg|ripgrep|ack|findstr)\b|Select-String|\bfind\b\s+\S+\s+-name/i;

  if (rawSearch.test(cmd)) {
    return out({
      permission: "ask",
      user_message: "Raw code search — knowledge-stack-first?",
      agent_message:
        'Knowledge-stack-first: prefer `ccc search "..."` or read graphify-out/GRAPH_REPORT.md before raw grep/rg/findstr. Proceed only if the stack already returned nothing, or you need ALL call sites of a known symbol.',
    });
  }
  return out({ permission: "allow" });
});

function out(o) {
  process.stdout.write(JSON.stringify(o));
  process.exit(0);
}
