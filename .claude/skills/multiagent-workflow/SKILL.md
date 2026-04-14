---
name: multiagent-workflow
description: >
  Token-efficient orchestration workflow. Use when the user says
  "implement X", "add feature Y", "fix bug Z", or any coding task
  that touches multiple functions or files. Keeps Copilot in planner/reviewer
  role only; coding is delegated to a free OpenRouter model.
  Skip for trivial single-function fixes - implement those directly.
---

# Multi-Agent Workflow

## Role of This Agent (Copilot / Planner-Reviewer)
- Decompose the task into a single atomic contract.
- Slice exactly the right context using ccc search and Graphify.
- Delegate code generation to the free implementer.
- Review the deterministic checker report and decide.
- Never write implementation code directly unless complexity bypass applies.

## Step 0 - Complexity Check

If the task touches <=1 function in <=1 file with clear intent:
-> implement directly, skip the contract workflow.

Otherwise, proceed to Step 1.

## Step 1 - Context Gathering (before writing the contract)

Run these in order. Stop as soon as you have enough:

1a. Check lessons from past tasks:
```powershell
if (Test-Path .agent_memory/lessons.jsonl) {
    Get-Content .agent_memory/lessons.jsonl | Select-Object -Last 10
}
```

1b. Semantic search (micro - exact implementation location):
```powershell
ccc search "QUERY_HERE" --top 5
```

1c. Architecture map (macro - dependencies and ownership):
```
Read: graphify-out/GRAPH_REPORT.md
Look for: relevant communities, coupling hotspots, dependency paths
```

1d. Targeted file read (only if ccc + Graphify are insufficient):
```
Read only the specific function or struct, not the whole file.
```

## Step 2 - Write the Task Contract

Save to: `.agent_contracts/TASK_YYYYMMDD_HHMMSS.md`

Template:
```markdown
# Task Contract

## Goal
One sentence. What should be true after this task is done.

## Subsystem
firmware | ground_station | simulation | docs
(This determines which checker gates run.)

## Scope
Files allowed to change: [list only specific files]
Files NOT to touch: [list explicitly]

## Context Snippet
[Paste only the relevant function/struct/header - max 100 lines]
[Include function signatures of direct dependencies - max 20 lines]
[Never paste whole files]

## Constraints
- Language/style rules specific to this codebase
- Known fragile areas from Graphify hotspot analysis
- Lessons from .agent_memory/lessons.jsonl relevant to this area
- Any API contracts that must not break

## Acceptance Criteria
- [ ] Criterion 1 (measurable)
- [ ] Criterion 2 (measurable)
- [ ] Appropriate checker gates pass

## Rollback Criteria
If any acceptance criteria fail after 2 repair loops: revert and escalate.

## Implementer Instructions
[Exact instructions for the free model - be explicit, no ambiguity]
[State expected output: replacement code blocks for each changed file]
[Example of correct output format:]

FILE: path/to/file.c
FUNCTION: function_name
```c
// replacement code here
```

[End of example]
```

## Step 3 - Create Pre-Patch Checkpoint

Before invoking the implementer, always create a rollback point:
```powershell
git stash push -m "pre-patch-TASK_YYYYMMDD_HHMMSS"
```

## Step 4 - Invoke the Free Implementer

```powershell
$env:PYTHONIOENCODING='utf-8'
python .agent_scripts/implementer.py --contract .agent_contracts/TASK_YYYYMMDD_HHMMSS.md
```

For repair loops (max 2):
```powershell
python .agent_scripts/implementer.py --contract .agent_contracts/TASK_YYYYMMDD_HHMMSS.md --loop 2 --failure-context .agent_reports/TASK_YYYYMMDD_HHMMSS_loop1_checker.md --prev-patch .agent_patches/TASK_YYYYMMDD_HHMMSS_loop1.patch
```

## Step 5 - Run the Deterministic Checker

```powershell
python .agent_scripts/checker.py --contract .agent_contracts/TASK_YYYYMMDD_HHMMSS.md --patch .agent_patches/TASK_YYYYMMDD_HHMMSS_loop1.patch
```

Output saved to: `.agent_reports/TASK_YYYYMMDD_HHMMSS_loop1_checker.md`

## Step 6 - Review (Copilot reads contract + diff + checker report only)

Decision matrix:
| Checker result | Action |
|---|---|
| All gates pass | ACCEPT - apply patch, pop git stash |
| 1-2 targeted failures | FIX - send failure + original contract + previous patch to implementer (loop 2) |
| Repeated failure after 2 loops | ESCALATE - revert via `git stash pop`, flag for Claude Code or human |
| Scope violation detected | REJECT - revert, rewrite contract with tighter scope |

## Step 7 - Post-Task Learning

After every completed task (success or failure), append one lesson:
```powershell
python .agent_scripts/log_lesson.py --task TASK_YYYYMMDD_HHMMSS --outcome success|failure --lesson "one line: what worked or what broke"
```

## Hard Rules
- Max 2 repair loops per task. After that: escalate to Claude Code or human.
- Never send whole files to the free model. Snippets only (100 lines max).
- Never let the implementer touch files outside the contract scope.
- Checker always runs before Copilot review. No exceptions.
- One coding agent active at a time. No parallel edits on same branch.
- Always create git stash checkpoint before applying any patch.
- Always check .agent_memory/lessons.jsonl before writing a new contract.
