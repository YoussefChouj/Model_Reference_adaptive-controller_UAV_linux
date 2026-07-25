<#
.SYNOPSIS
  ⚠️ DEPRECATED — use the Cursor GUI subagents instead.

.DESCRIPTION
  Frozen on 2026-07-25 when the pipeline migrated from the cursor-agent CLI to Cursor GUI
  subagents. Replaced by:

    /uav-implementer  →  .cursor/agents/uav-implementer.md   (pinned to composer-2.5)
    /uav-reviewer     →  .cursor/agents/uav-reviewer.md      (gpt-5.6-sol-xhigh, readonly)

  Why frozen, not deleted:
    - The CLI requires a paid Cursor plan (free plans fail --model with
      ActionRequiredError). The GUI path works with the third-party token-manager
      extension that surfaces shared Pro credits.
    - cursor-agent's HTTP/2 stream is unreliable on this machine (see
      .claude/skills/cursor-pipeline/SKILL.md — Known blockers). The GUI's
      Agents Window is more stable for long agentic runs.
    - The skill files (.cursor/skills/implement-spec/SKILL.md and
      .cursor/skills/review-spec/SKILL.md) are still the source of truth for the
      leg behaviour — both the GUI agents and this wrapper delegate to them.

  To revive this wrapper: flip $Deprecated back to $false and resolve the model ids
  against `cursor-agent models` (they drift). The exit-75/76 guards below are
  implementation-legit and worth keeping if anyone re-enables the CLI path.

.PARAMETER Mode
  Was: implement | review
.PARAMETER Task
  Was: <TASK_ID>
.PARAMETER Tier
  Was: fast | default | hard
.PARAMETER Model
  Was: explicit model id, overrides -Tier
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [ValidateSet('implement', 'review')]
    [string]$Mode,

    [Parameter(Mandatory = $false)]
    [string]$Task,

    [ValidateSet('fast', 'default', 'hard')]
    [string]$Tier = 'default',

    [string]$Model,

    [string]$OutDir = '.agent_reports',

    [switch]$Json
)

$ErrorActionPreference = 'Stop'

$Deprecated = $true
if ($Deprecated) {
    Write-Host @"
cursor_run.ps1 is deprecated as of 2026-07-25.

Use the Cursor GUI subagents instead — they route through the third-party token-manager
extension and avoid the paid-plan requirement that blocked the CLI path:

    /uav-implementer <TASK_ID>   - implements the spec; pinned to composer-2.5
    /uav-reviewer    <TASK_ID>   - read-only review;   pinned to gpt-5.6-sol-xhigh

See:
    .cursor/agents/uav-implementer.md
    .cursor/agents/uav-reviewer.md
    .claude/skills/cursor-pipeline/SKILL.md
"@ -ForegroundColor Yellow
    exit 78  # EX_CONFIG: configuration has changed; use the new entry point
}

# --- everything below this line is the old CLI implementation, kept verbatim ---------

# Verified against `cursor-agent models` on 2026-07-25.
# implement: Composer is Cursor's own speed-tuned agentic coder - cheap and fast, which is the
#            whole point of this leg. Escalate to Codex 5.3 High for numerics/concurrency.
# review:    GPT-5.6 Sol, a different family from both the planner (Claude) and the implementer
#            (Composer) - independence is what makes the review leg worth running at all.
$Models = @{
    implement = @{ fast = 'composer-2.5-fast'; default = 'composer-2.5'; hard = 'gpt-5.3-codex-high' }
    review    = @{ fast = 'gpt-5.6-sol-high-fast'; default = 'gpt-5.6-sol-xhigh'; hard = 'gpt-5.6-sol-max' }
}

$Exe = Join-Path $env:LOCALAPPDATA 'cursor-agent\cursor-agent.cmd'
if (-not (Test-Path $Exe)) {
    throw "cursor-agent not found at $Exe. Install with: irm 'https://cursor.com/install?win32=true' | iex"
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$TaskDir = Join-Path $Root ".agent_contracts\$Task"
$SpecPath = Join-Path $TaskDir 'spec.md'
$JournalPath = Join-Path $TaskDir 'journal.md'

if (-not (Test-Path $SpecPath)) {
    throw "Spec not found: $SpecPath`nThe planning leg (Claude Code) writes this before implement runs."
}
if (-not (Test-Path $JournalPath)) {
    "# Journal - $Task", "" | Out-File -FilePath $JournalPath -Encoding utf8
}

if (-not $Model) { $Model = $Models[$Mode][$Tier] }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$LogPath = Join-Path $OutDir "$Task`_$Mode`_$Stamp.md"

# --- Build the prompt -------------------------------------------------------
# Kept deliberately thin. The real instructions are in the skill files so that the Agents tab
# and this CLI share one source of truth.

$SkillFile = if ($Mode -eq 'implement') {
    '.cursor/skills/implement-spec/SKILL.md'
} else {
    '.cursor/skills/review-spec/SKILL.md'
}

$Prompt = @"
Read $SkillFile and follow it exactly for TASK_ID = $Task.

That skill is your full instruction set. In particular it requires you to read the task journal
before acting and to append your entry to it when done - do not skip either step.

Task directory: .agent_contracts/$Task/
  spec.md     - what to build
  journal.md  - shared memory across planner/implementer/reviewer, append-only

Record your model id as '$Model' in the journal entry heading.
"@

# --- Invoke -----------------------------------------------------------------

# --trust only marks the directory trusted; it does not grant edit permission.
# The review leg still gets --plan below, which keeps it strictly read-only.
$CliArgs = @('-p', '--workspace', $Root, '--model', $Model, '--trust')

if ($Mode -eq 'review') {
    # Read-only: the reviewer must not be able to "fix" what it finds.
    $CliArgs += '--plan'
}
else {
    # Deny rules in .cursor/cli.json still take precedence over --force.
    $CliArgs += '--force'
}

if ($Json) { $CliArgs += @('--output-format', 'json') }

Write-Host "cursor-agent $Mode | model=$Model (tier=$Tier) | task=$Task" -ForegroundColor Cyan

$Header = @(
    "# cursor-agent $Mode",
    "",
    "- task: ``$Task``",
    "- model: ``$Model`` (tier ``$Tier``)",
    "- when: $Stamp",
    "",
    "---",
    ""
)
$Header | Out-File -FilePath $LogPath -Encoding utf8

$JournalBefore = (Get-Item $JournalPath).Length

& $Exe @CliArgs $Prompt | Tee-Object -FilePath $LogPath -Append
$Code = $LASTEXITCODE

# The Cursor API drops long-lived HTTP/2 streams fairly often. When that happens the CLI can
# exit 0 having produced nothing at all - a silent no-op that looks like success. Catch it here
# rather than letting the orchestrator act on an empty result.
$Produced = ((Get-Content $LogPath -Raw) -split '---', 2)[1]
$JournalGrew = (Get-Item $JournalPath).Length -gt $JournalBefore

if ($Code -eq 0 -and [string]::IsNullOrWhiteSpace($Produced)) {
    Write-Host "cursor-agent exited 0 but produced no output - almost certainly a dropped connection. Re-run." -ForegroundColor Yellow
    $Code = 75  # EX_TEMPFAIL: retriable
}
elseif ($Code -eq 0 -and -not $JournalGrew) {
    Write-Host "cursor-agent produced output but did not append to journal.md - the handoff is incomplete." -ForegroundColor Yellow
    $Code = 76
}

"MANIFEST mode=$Mode model=$Model tier=$Tier task=$Task exit=$Code journal_appended=$JournalGrew log=$LogPath journal=$JournalPath"
exit $Code
