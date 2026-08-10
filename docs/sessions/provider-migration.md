# Provider migration session (2026-08-09) - ACTIVE

Status: Alibaba Token Plan Personal LIVE. Full history in chat; this file holds the durable facts.

## Decisions
- Claude Pro ending -> keep Claude Code; provider = Token Plan Personal (first month promo
  done; renewal terms unverified at purchase - confirm before month 2).
- Coding Plan rejected (Pro tier perpetually out of stock). Qoder CN Credits are
  Qoder-products-only, they do not power Claude Code - Qoder stays a separate tool.
- Taobao relay stations rejected (device-ID ban contamination, prompt interception).

## Config
- ~/.claude/settings.json env block: ANTHROPIC_AUTH_TOKEN (sk-sp-..., shown ONCE at creation,
  console masks it after), ANTHROPIC_BASE_URL = token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic
  (from the console page; NOT coding.dashscope... which is Coding Plan - never mix).
- Mapping: ANTHROPIC_MODEL=qwen3.6-flash (routine + classifier), sonnet=qwen3.6-plus,
  opus=qwen3.8-max, haiku=qwen3.6-flash, CLAUDE_CODE_SUBAGENT_MODEL=qwen3.7-max,
  CLAUDE_CODE_MAX_CONTEXT_TOKENS=983616. Top-level model="haiku" -> fresh sessions start
  cheap; /model opus escalates. Backup: ~/.claude/settings.json.bak-20260809.
- Alibaba's `bl config agent` quick-setup was deliberately NOT run (it would overwrite
  settings.json and nuke hooks/MCP config).

## Gotchas learned the hard way
- VPN must be smart/direct for *.aliyuncs.com. Global mode exits outside China ->
  500 "Invoke backend failed" (auth passes, backend call dies). HTTPS_PROXY=127.0.0.1:7897
  is machine-wide and honored by curl + Claude Code.
- settings env takes effect for newly spawned processes immediately (the safety classifier
  switched mid-session on 2026-08-09).
- Consumption: first heavyweight session burned ~22% of the 2,500 Credits/7d. Long contexts
  on qwen3.8-max are the expensive shape; Lite buys ~4 such sessions/week. Standard (139,
  10,000/7d) matches the real style if this stays the driver.
- Lite concurrency cap (1-2 agents): parallel Claude Code windows throttle everything,
  including the permission classifier ("model temporarily unavailable" on every gated tool).
- AUTOMATION BAN: plan key is for interactive coding tools only. Never point /free,
  .agent_scripts/implementer.py, copilot-agent or the deepseek batch skill at it
  (suspension risk). Those stay on DeepSeek/OpenRouter.
- Data clause: inputs/outputs used for service improvement, no retroactive withdrawal.
  Weigh thesis-sensitive content per session.

## Model switching cheat-sheet (gateway)
/model haiku -> qwen3.6-flash | /model sonnet -> qwen3.6-plus | /model opus -> qwen3.8-max |
full IDs pass through (/model qwen3.7-max). Angle brackets in usage text are placeholders.

## Open
- Confirm glm-5 / kimi-k2.5 / MiniMax-M2.5 availability on the Personal tier.
- 5h cap returns when the limited-time waiver ends.
- Auto-renew OFF. Decide Standard before renewal.
