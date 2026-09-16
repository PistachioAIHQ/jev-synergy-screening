"""Anthropic structured include|exclude (tool/JSON schema; no CoT essay)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests

from .cohen_adhd import criteria_text_for_anthropic
from .config import (
    ANTHROPIC_INPUT_USD_PER_MTOK,
    ANTHROPIC_MODEL,
    ANTHROPIC_OUTPUT_USD_PER_MTOK,
    LABEL_EXCLUDE,
    LABEL_INCLUDE,
    OPUS_INPUT_USD_PER_MTOK,
    OPUS_MODEL,
    OPUS_OUTPUT_USD_PER_MTOK,
)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def load_anthropic_key() -> str:
    env = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if env:
        return env
    candidates = [
        Path.home() / ".config" / "anthropic" / "api_key",
        Path("/home/box/.config/anthropic/api_key"),
    ]
    for p in candidates:
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    raise RuntimeError(
        "No Anthropic API key. Set ANTHROPIC_API_KEY or write ~/.config/anthropic/api_key "
        "(ask Zuck / parent if missing from Pistachio secrets)."
    )


SCREEN_TOOL = {
    "name": "screen_abstract",
    "description": "Return abstract-triage decision for the DERP ADHD review (TIAB only).",
    "input_schema": {
        "type": "object",
        "properties": {
            "decision": {
                "type": "string",
                "enum": [LABEL_INCLUDE, LABEL_EXCLUDE],
                "description": "include or exclude",
            }
        },
        "required": ["decision"],
        "additionalProperties": False,
    },
}


def pricing_for_model(model: str) -> tuple[float, float]:
    """Return (input_usd_per_mtok, output_usd_per_mtok) for known Anthropic models."""
    m = (model or "").lower()
    if "opus" in m or model == OPUS_MODEL:
        return OPUS_INPUT_USD_PER_MTOK, OPUS_OUTPUT_USD_PER_MTOK
    return ANTHROPIC_INPUT_USD_PER_MTOK, ANTHROPIC_OUTPUT_USD_PER_MTOK


def classify_anthropic(
    title: str,
    abstract: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    timeout: float = 90.0,
    input_usd_per_mtok: float | None = None,
    output_usd_per_mtok: float | None = None,
) -> dict[str, Any]:
    key = api_key or load_anthropic_key()
    model = model or ANTHROPIC_MODEL
    in_rate, out_rate = pricing_for_model(model)
    if input_usd_per_mtok is not None:
        in_rate = input_usd_per_mtok
    if output_usd_per_mtok is not None:
        out_rate = output_usd_per_mtok
    criteria = criteria_text_for_anthropic()
    user = (
        f"{criteria}\n\n---\nTITLE:\n{title.strip()}\n\nABSTRACT:\n{abstract.strip()}\n---\n"
        "Call screen_abstract with your decision. Do not write an essay; tool call only."
    )
    payload = {
        "model": model,
        "max_tokens": 64,
        "tools": [SCREEN_TOOL],
        "tool_choice": {"type": "tool", "name": "screen_abstract"},
        "messages": [{"role": "user", "content": user}],
    }
    t0 = time.perf_counter()
    resp = requests.post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    latency_ms = (time.perf_counter() - t0) * 1000.0
    if resp.status_code >= 400:
        raise RuntimeError(f"Anthropic HTTP {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    decision = None
    for block in data.get("content") or []:
        if block.get("type") == "tool_use" and block.get("name") == "screen_abstract":
            inp = block.get("input") or {}
            decision = inp.get("decision")
            break
    if decision not in (LABEL_INCLUDE, LABEL_EXCLUDE):
        # fallback parse
        text = " ".join(
            b.get("text", "") for b in (data.get("content") or []) if b.get("type") == "text"
        ).lower()
        if "include" in text and "exclude" not in text:
            decision = LABEL_INCLUDE
        else:
            decision = LABEL_EXCLUDE
    usage = data.get("usage") or {}
    in_tok = int(usage.get("input_tokens") or 0)
    out_tok = int(usage.get("output_tokens") or 0)
    cost = in_tok * in_rate / 1_000_000.0 + out_tok * out_rate / 1_000_000.0
    return {
        "pred": decision,
        "choice": decision,
        "confidence": 1.0,
        "latency_ms": latency_ms,
        "model": data.get("model") or model,
        "usage": usage,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": cost,
        "mode": "anthropic",
        "rule": "anthropic_structured_tool_include_exclude",
        "raw": data,
    }


# runner aliases
load_anthropic_key = load_anthropic_key
classify_anthropic = classify_anthropic
