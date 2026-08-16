#!/usr/bin/env node
// Knowledge-stack-first nudge (Cursor beforeShellExecution hook).
// Cross-platform port of the Claude Code knowledge_gate PreToolUse hook.
// When the agent tries a RAW code search (grep/rg/findstr/Select-String/find -name),
// it sends a reminder to the agent to prefer `ccc search` / GRAPH_REPORT.md first.
// Non-blocking: always returns "allow". The agent gets the nudge in agent_message
// and may choose to use the knowledge stack instead. The user is not prompted.

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
      permission: "allow",
      agent_message:
        'Reminder — knowledge-stack-first: prefer `ccc search "..."` or read graphify-out/GRAPH_REPORT.md before raw grep/rg/findstr. Proceed with the raw search only if the stack already returned nothing, or you need ALL call sites of a known symbol.',
    });
  }
  return out({ permission: "allow" });
});

function out(o) {
  process.stdout.write(JSON.stringify(o));
  process.exit(0);
}
