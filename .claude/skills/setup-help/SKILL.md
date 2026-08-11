---
name: setup-help
description: >
  Walk the user through setting up anything step by step. Use when the user asks for
  help setting up, configuring, installing, or getting something working — "help me
  set up X", "walk me through this". Differentiator: gives one current step at a time,
  then always lists every remaining setup step after each response.
disable-model-invocation: true
---

# setup-help

Guide the user through any setup, one step at a time, in plain English.

## Response format (every single response)

1. **Current step** — ONE atomic action. A single click, field, or command — not a checklist.
   1–2 lines max. If it needs sub-steps, it's too big: split it and push the rest
   into "Still remaining". Plain English.
2. A `----` divider.
3. **Still remaining** — a numbered list of the setup steps left after this one.
   Max 8 items. Each item is a HEADLINE only: a few words, easy to glance at.
   No commands, URLs, event names, values, or explanations — that detail appears only
   when the item becomes the Current step.

Repeat this format for every response until setup is done.

## Rules

- Before the first step, build a complete canonical checklist from the user's outline,
  repo/docs, current screen, and any discovered prerequisites.
- The **Still remaining** list must never exceed 8 items.
- If a new required step is discovered mid-setup, add it to **Still remaining** immediately.
- Before every response, audit the current step plus **Still remaining** against the
  canonical checklist. If any unfinished step is missing, fix the list before replying.
- Only give instructions for the current step. Do not jump ahead.
- Keep it concise. Short sentences. No filler.
- When nothing remains, say setup is complete instead of showing the list.
