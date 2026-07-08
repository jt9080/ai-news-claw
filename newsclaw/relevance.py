"""Keyword-allowlist relevance filter.

A deliberately mechanical stopgap until the Slice 3 LLM judge does real relevance.
Terms are matched case-insensitively at a word boundary (so "rag" does not match
"storage") against the story title and url. A story is kept if any term matches;
the matched terms become its ``topics``.

The exact list is meant to be tuned after a real fetch.
"""

from __future__ import annotations

import re

from newsclaw.models import Candidate

# Agent-development terms first (ranked-first per CLAUDE.md), then the rest of AI.
# Whole words only (optional trailing plural) — stems that collide with common
# English ("skill"→"skilled") are spelled out to avoid false positives.
ALLOWLIST = [
    "agentic", "multiagent", "subagent", "agent", "mcp", "skills",
    "llm", "gpt", "claude", "gemini", "llama", "mistral", "deepseek", "qwen",
    "openai", "anthropic", "huggingface", "hugging face", "mixtral",
    "rag", "transformer", "diffusion", "neural", "fine-tuning", "fine-tune",
    "inference", "embedding", "chatbot", "prompt", "multimodal", "reasoning model",
]

# Whole-word match at both boundaries, allowing only an optional trailing plural
# "s". This keeps "rag" out of "storage" and "skill" out of "skilled" while still
# matching "agents"/"models". A knowingly imperfect stopgap, superseded by the S3 judge.
_PATTERNS = [
    (term, re.compile(r"\b" + re.escape(term) + r"s?\b", re.IGNORECASE))
    for term in ALLOWLIST
]


def find_topics(title: str, url: str) -> list[str]:
    """Return the sorted, unique allowlist terms matching the title or url."""
    haystack = f"{title} {url}"
    matched = {term for term, pattern in _PATTERNS if pattern.search(haystack)}
    return sorted(matched)


def filter_relevant(candidates: list[Candidate]) -> list[Candidate]:
    """Keep only candidates matching the allowlist, tagging each with its topics."""
    kept = []
    for candidate in candidates:
        topics = find_topics(candidate.title, candidate.url)
        if topics:
            candidate.topics = topics
            kept.append(candidate)
    return kept
