from __future__ import annotations

import math
import os
import time
from pathlib import Path
from typing import Any

import requests

from .config import JEV_MODEL, JEV_URL, LABEL_NON, LABEL_RCT
from .hybrid import (
    NOUL_KEYS,
    build_hybrid_questions,
    extract_nouls,
    hybrid_combine,
)


def load_api_key() -> str:
    env = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if env:
        return env
    candidates = [
        Path.home() / ".config" / "typesafe" / "api_key",
        Path("/home/box/.config/typesafe/api_key"),
    ]
    for p in candidates:
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    raise RuntimeError(
        "No TypeSafe API key. Set TYPESAFE_API_KEY or write ~/.config/typesafe/api_key"
    )


def build_questions() -> dict[str, Any]:
    """DEFAULT: CD medium Choice + round-2 atomic nouls (hybrid)."""
    return build_hybrid_questions()


def classify(text: str, api_key: str | None = None, timeout: float = 60.0) -> dict[str, Any]:
    """POST systemone with hybrid questions; return hybrid pred + full per-question answers."""
    key = api_key or load_api_key()
    questions = build_hybrid_questions()
    payload = {
        "state": text,
        "model": JEV_MODEL,
        "questions": questions,
    }
    t0 = time.perf_counter()
    resp = requests.post(
        JEV_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    latency_ms = (time.perf_counter() - t0) * 1000.0
    if resp.status_code >= 400:
        raise RuntimeError(f"Jev HTTP {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    answers = data.get("answers") or {}
    label_ans = answers.get("label") or {}
    choice = label_ans.get("choice")
    probs = label_ans.get("probabilities") or {}
    confidence = float(label_ans.get("confidence") or 0.0)
    nouls = extract_nouls(answers)
    # hybrid_combine refuses aggressive=True
    pred = hybrid_combine(choice, nouls, aggressive=False)

    finite_nouls = {
        k: (None if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else v)
        for k, v in nouls.items()
    }

    return {
        "pred": pred,
        "choice": choice,
        "confidence": confidence,
        "p_RCT": float(probs.get(LABEL_RCT) or 0.0),
        "p_non_RCT": float(probs.get(LABEL_NON) or 0.0),
        "probabilities": {
            LABEL_RCT: float(probs.get(LABEL_RCT) or 0.0),
            LABEL_NON: float(probs.get(LABEL_NON) or 0.0),
        },
        **{k: finite_nouls[k] for k in NOUL_KEYS},
        "answers": {
            "label": {
                "choice": choice,
                "confidence": confidence,
                "probabilities": {
                    LABEL_RCT: float(probs.get(LABEL_RCT) or 0.0),
                    LABEL_NON: float(probs.get(LABEL_NON) or 0.0),
                },
            },
            **{
                k: {"noul": finite_nouls[k]}
                for k in NOUL_KEYS
            },
        },
        "latency_ms": latency_ms,
        "model": data.get("model"),
        "usage": data.get("usage"),
        "rule": "hybrid_cd_choice_plus_r2_nouls",
        # legacy alias (first positive noul-ish signal for older UI)
        "noul_is_rct": finite_nouls.get("has_random_allocation"),
    }
