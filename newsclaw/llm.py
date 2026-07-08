"""Minimal client for an OpenAI-compatible /chat/completions endpoint.

Default target is OpenCode Zen; base URL, model, and key are env vars so the
same client works against OpenAI or an Anthropic-compatible gateway without code
changes. Standard library only (``urllib``) — no SDK, so the toolchain rules are
unchanged.

Any failure (missing key, network, HTTP, timeout, empty body) raises ``LLMError``
so the judge can degrade to the stand-in selector rather than crash the run.
"""

from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://opencode.ai/zen/v1"
# Free Zen model — no account credits required. Override with LLM_MODEL to use a
# paid model (e.g. gpt-5.4-mini, claude-haiku-4-5) once the workspace is funded.
DEFAULT_MODEL = "deepseek-v4-flash-free"
USER_AGENT = "ai-news-monitor/0.1 (+https://github.com/jt9080/ai-news-claw)"
# Free/trial models can be slow on a full digest payload; give them room. This
# is a daily batch call with no interactive user waiting.
TIMEOUT_SECONDS = 120


class LLMError(Exception):
    """The LLM call could not produce a usable response."""


def complete(system: str, user: str, timeout: int = TIMEOUT_SECONDS) -> str:
    """Send a system+user prompt and return the assistant's text.

    Raises LLMError on any failure so callers can fall back cleanly."""
    key = os.environ.get("OPENCODE_API_KEY")
    if not key:
        raise LLMError("OPENCODE_API_KEY is not set")

    base = os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
    url = f"{base}/chat/completions"

    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
    }).encode("utf-8")

    request = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = payload["choices"][0]["message"]["content"]
    except Exception as exc:  # network, HTTP, decode, missing keys — all degrade
        raise LLMError(str(exc)) from exc

    if not text or not text.strip():
        raise LLMError("empty response from model")
    return text
