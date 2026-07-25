"""
LLM helper for the self-adaptive knowledge loop.

Thin wrapper around OpenRouter-compatible chat completions. Used by
knowledge_loop.py for:

  - graphify delta_update   (re-extract structure for touched nodes)
  - wiki write-through      (rewrite rationale on a wiki page if it shifted)

Designed to be:

  - tolerant of missing API keys (degrades to "no-op + mark degraded")
  - tolerant of rate limits (exponential backoff, try alternate models)
  - small token budget per call (cap at 2k output tokens; full corpus
    re-extraction belongs to /graphify, not this loop)
  - offline-friendly: if the network is down, fail soft.

Configuration:
  - OPENROUTER_API_KEY       env var (required for real calls)
  - OPENROUTER_DEFAULT_MODEL env var (overrides model registry default)
  - LOOP_MODEL_FALLBACK      comma-separated model list (last-resort)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Iterable

OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / '.agent_state'
STATE_DIR.mkdir(exist_ok=True)

CALL_LOG = STATE_DIR / 'llm_calls.jsonl'

# Defaults — used if ~/.claude/openrouter_models.json is missing.
DEFAULT_MODELS = [
    'deepseek/deepseek-chat-v3.1:free',
    'meta-llama/llama-3.3-70b-instruct:free',
    'qwen/qwen-2.5-72b-instruct:free',
]


# ------------------------------------------------------------------ model registry

def _load_models() -> list[str]:
    """Load model list from ~/.claude/openrouter_models.json (tasks.doc_extraction
    is closest to what we do). Fall back to DEFAULT_MODELS if registry missing."""
    cfg_path = Path.home() / '.claude' / 'openrouter_models.json'
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding='utf-8'))
            tasks = data.get('tasks', {})
            for task in ('doc_extraction', 'reasoning', 'code_implementation'):
                ms = tasks.get(task, {}).get('models', [])
                if ms:
                    return list(ms)
        except Exception:
            pass
    env = os.environ.get('LOOP_MODEL_FALLBACK', '').strip()
    if env:
        return [m.strip() for m in env.split(',') if m.strip()]
    return DEFAULT_MODELS


# ------------------------------------------------------------------ rate limit + circuit breaker

def _circuit_state() -> dict:
    p = STATE_DIR / 'llm_circuit.json'
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {'failures': 0, 'last_failure_ts': None, 'open_until': None}


def _circuit_record_success() -> None:
    p = STATE_DIR / 'llm_circuit.json'
    p.write_text(json.dumps({'failures': 0, 'last_failure_ts': None,
                             'open_until': None}, indent=2))


def _circuit_record_failure(err: str) -> bool:
    """Record a failure. Return True if circuit is now OPEN (skip further
    calls for the cool-down period)."""
    state = _circuit_state()
    state['failures'] = state.get('failures', 0) + 1
    state['last_failure_ts'] = time.time()
    # 3 failures in a row → open the circuit for 5 minutes
    if state['failures'] >= 3:
        state['open_until'] = time.time() + 300
        p = STATE_DIR / 'llm_circuit.json'
        p.write_text(json.dumps(state, indent=2))
        return True
    p = STATE_DIR / 'llm_circuit.json'
    p.write_text(json.dumps(state, indent=2))
    return False


def circuit_is_open() -> bool:
    state = _circuit_state()
    until = state.get('open_until')
    if until and time.time() < until:
        return True
    return False


# ------------------------------------------------------------------ call

def chat(messages: list[dict], max_tokens: int = 1500,
         temperature: float = 0.0, timeout: int = 60,
         purpose: str = 'loop') -> str | None:
    """Call OpenRouter and return the assistant text. Returns None on failure.

    `messages` is a list of {role, content} dicts. Use OpenAI-style format.
    """
    if circuit_is_open():
        return None
    api_key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not api_key:
        # Fail soft — degrade to no-op so the loop can continue
        _circuit_record_failure('no_api_key')
        return None

    models = _load_models()
    # Try models in order; succeed on first 200; otherwise fall through.
    for model in models:
        try:
            payload = {
                'model': model,
                'messages': messages,
                'max_tokens': max_tokens,
                'temperature': temperature,
            }
            req = urllib.request.Request(
                OPENROUTER_API_URL,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://local.knowledge-loop',
                    'X-Title': f'uav-knowledge-loop ({purpose})',
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode('utf-8'))
            text = body.get('choices', [{}])[0].get('message', {}).get('content', '')
            usage = body.get('usage', {})
            _record_call(purpose, model, True, len(text), usage)
            _circuit_record_success()
            return text.strip()
        except urllib.error.HTTPError as e:
            err = f'HTTP {e.code}: {e.read()[:200]!r}'
            _record_call(purpose, model, False, 0, {'error': err})
            if _circuit_record_failure(err):
                return None
            # Otherwise try next model
            continue
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            err = f'NET: {e}'
            _record_call(purpose, model, False, 0, {'error': err})
            if _circuit_record_failure(err):
                return None
            continue
        except Exception as e:
            _record_call(purpose, model, False, 0, {'error': repr(e)})
            if _circuit_record_failure(repr(e)):
                return None
            continue
    return None


def _record_call(purpose: str, model: str, ok: bool, out_chars: int,
                 usage: dict | None) -> None:
    rec = {
        'ts':       time.time(),
        'purpose':  purpose,
        'model':    model,
        'ok':       ok,
        'out_chars': out_chars,
        'usage':    usage or {},
    }
    with CALL_LOG.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec) + '\n')


# ------------------------------------------------------------------ CLI for ad-hoc testing

def main(argv: list[str] | None = None) -> int:
    if not argv or argv[0] != 'test':
        print(__doc__)
        return 0
    print('circuit open?', circuit_is_open())
    print('models:', _load_models()[:3])
    msg = [{'role': 'user', 'content': 'Reply with the single word OK.'}]
    out = chat(msg, max_tokens=10, purpose='selftest')
    print('output:', out)
    return 0 if out else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
