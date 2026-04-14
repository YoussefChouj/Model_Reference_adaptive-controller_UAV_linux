"""
Free OpenRouter implementer agent.
Reads a Task Contract, calls free models, saves the output.
Accepts replacement code blocks (not raw diffs) for reliability with free models.

Usage:
  python .agent_scripts/implementer.py --contract PATH
  python .agent_scripts/implementer.py --contract PATH --loop 2 --failure-context REPORT --prev-patch PATCH
"""

import argparse
import json
import os
import sys
import time
import requests
from pathlib import Path
from datetime import datetime

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
CONFIG_PATH = os.path.expanduser("~/.claude/openrouter_models.json")
COST_LOG = Path(".agent_memory/costs.jsonl")

SYSTEM_PROMPT = """You are a precise code implementer.
You receive a Task Contract specifying exactly what to change.

OUTPUT FORMAT - follow exactly:
For each file you change, output:

FILE: path/to/file.ext
FUNCTION: function_or_section_name
```
// your replacement code for this function/section
```

Rules:
- Only change files listed in the Scope section.
- Only change functions/sections mentioned in the instructions.
- Do not add commentary, explanations, or markdown headers.
- Do not change code outside the specified functions.
- If a constraint says do not touch X, you do not touch X.

Self-check before responding:
- Does every changed file appear in the Scope list?
- Does the output satisfy all Acceptance Criteria?
- Did you follow the exact output format above?
"""


def load_models():
    if not Path(CONFIG_PATH).exists():
        print(f"[implementer] ERROR: {CONFIG_PATH} not found", file=sys.stderr)
        sys.exit(1)
    config = json.loads(Path(CONFIG_PATH).read_text(encoding="utf-8"))
    tasks = config.get("tasks", {})
    primary = tasks.get("code_implementation", {}).get("models", [])
    fallback = tasks.get("doc_extraction", {}).get("models", [])

    # Keep order while removing duplicates: try primary first, then fallback models.
    models = []
    for m in list(primary) + list(fallback):
        if m and m not in models:
            models.append(m)

    if not models:
        print("[implementer] ERROR: no models configured", file=sys.stderr)
        sys.exit(1)
    return models


def validate_output(content: str, contract_text: str) -> bool:
    """Basic structural validation - does the output look like code blocks?"""
    has_file_marker = "FILE:" in content
    has_code = "```" in content or content.strip().startswith("//") or content.strip().startswith("#")
    refusal_signals = ["I cannot", "I'm sorry", "I apologize", "As an AI"]
    is_refusal = any(s.lower() in content.lower()[:200] for s in refusal_signals)
    return (has_file_marker or has_code) and not is_refusal


def call_free_model(prompt: str, models: list, proxy: str = "") -> str:
    proxies = {"https": proxy} if proxy else {}
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("[implementer] ERROR: OPENROUTER_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    for model in models:
        t0 = time.time()
        try:
            print(f"[implementer] Trying: {model}")
            r = requests.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 4000,
                },
                proxies=proxies,
                timeout=90,
            )
            elapsed = time.time() - t0

            if r.status_code == 200:
                data = r.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})

                COST_LOG.parent.mkdir(parents=True, exist_ok=True)
                with open(COST_LOG, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "ts": datetime.now().isoformat(),
                        "model": model,
                        "tokens_in": usage.get("prompt_tokens", 0),
                        "tokens_out": usage.get("completion_tokens", 0),
                        "latency_s": round(elapsed, 1),
                        "status": "ok",
                    }) + "\n")

                if validate_output(content, prompt):
                    print(f"[implementer] Success: {model} ({elapsed:.1f}s)")
                    return content
                print(f"[implementer] {model} returned invalid output, trying next...", file=sys.stderr)
            elif r.status_code == 429:
                print(f"[implementer] Rate limited on {model}", file=sys.stderr)
            else:
                print(f"[implementer] {model} returned {r.status_code}", file=sys.stderr)

        except requests.exceptions.Timeout:
            print(f"[implementer] {model} timed out after 90s", file=sys.stderr)
        except Exception as e:
            print(f"[implementer] {model} error: {e}", file=sys.stderr)

    print("[implementer] All models failed.", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    parser.add_argument("--loop", type=int, default=1)
    parser.add_argument("--failure-context", default="")
    parser.add_argument("--prev-patch", default="")
    args = parser.parse_args()

    if args.loop > 2:
        print("[implementer] ESCALATION: max loops reached.", file=sys.stderr)
        sys.exit(2)

    contract_path = Path(args.contract)
    if not contract_path.exists():
        print(f"[implementer] Contract not found: {args.contract}", file=sys.stderr)
        sys.exit(1)

    contract_text = contract_path.read_text(encoding="utf-8")

    if args.loop > 1:
        repair_context = f"\n\n## Repair Loop {args.loop}\n"
        if args.prev_patch and Path(args.prev_patch).exists():
            prev = Path(args.prev_patch).read_text(encoding="utf-8")
            repair_context += f"\n### Your Previous Attempt (DO NOT repeat the same approach)\n{prev[:3000]}\n"
        if args.failure_context and Path(args.failure_context).exists():
            failure = Path(args.failure_context).read_text(encoding="utf-8")
            repair_context += f"\n### Why It Failed\n{failure[:2000]}\n"
        repair_context += "\nFix the specific failures above. Do not repeat the same mistake.\n"
        contract_text += repair_context

    models = load_models()
    proxy = os.environ.get("HTTPS_PROXY", "") or os.environ.get("https_proxy", "")

    output = call_free_model(f"Task Contract:\n\n{contract_text}", models, proxy)

    patch_dir = Path(".agent_patches")
    patch_dir.mkdir(parents=True, exist_ok=True)
    stem = contract_path.stem
    patch_path = patch_dir / f"{stem}_loop{args.loop}.patch"
    patch_path.write_text(output, encoding="utf-8")
    print(f"[implementer] Output saved: {patch_path}")


if __name__ == "__main__":
    main()
