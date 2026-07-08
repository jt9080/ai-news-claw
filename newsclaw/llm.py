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

# OpenCode Go endpoint — a flat-rate subscription (not per-token credits), so its
# models carry no marginal cost. Model ids are bare (no "opencode-go/" prefix).
# Override LLM_MODEL for another Go model (glm-5.2, qwen3.7-max, kimi-k2.7-code…).
DEFAULT_BASE_URL = "https://opencode.ai/zen/go/v1"
DEFAULT_MODEL = "deepseek-v4-pro"
USER_AGENT = "ai-news-monitor/0.1 (+https://github.com/jt9080/ai-news-claw)"
# These reasoning models take ~80-95s on a full digest payload and vary; give
# generous headroom. This is a daily batch call — no interactive user waiting.
TIMEOUT_SECONDS = 240


class LLMError(Exception):
    """The LLM call could not produce a usable response."""


def complete(system: str, user: str, timeout: int = TIMEOUT_SECONDS) -> str:
    """Send a system+user prompt and return the assistant's text.

    Raises LLMError on any failure so callers can fall back cleanly."""
    # Strip env values: repo vars/secrets often pick up stray leading/trailing
    # whitespace when pasted, and " deepseek-v4-pro" / " https://..." break the
    # call. Strip first, then fall back to the default if empty (an unset CI var
    # arrives as "").
    key = (os.environ.get("OPENCODE_API_KEY") or "").strip()
    if not key:
        raise LLMError("OPENCODE_API_KEY is not set")

    base = ((os.environ.get("LLM_BASE_URL") or "").strip() or DEFAULT_BASE_URL).rstrip("/")
    model = (os.environ.get("LLM_MODEL") or "").strip() or DEFAULT_MODEL
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
