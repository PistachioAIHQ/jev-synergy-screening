from __future__ import annotations

import math
import os
import time
from pathlib import Path
from typing import Any

import requests

from .cohen_adhd import (
    NOUL_KEYS as COHEN_NOUL_KEYS,
    RULE_ID as COHEN_RULE_ID,
    build_questions as build_cohen_questions,
    cohen_combine,
    extract_nouls as extract_cohen_nouls,
)
from .config import (
    INPUT_USD_PER_MTOK,
    JEV_MODEL,
    JEV_URL,
    LABEL_EXCLUDE,
    LABEL_INCLUDE,
    LABEL_NON,
    LABEL_RCT,
)
from .hybrid import (
    ALL_NOUL_KEYS,
    build_round3_questions,
    extract_nouls as extract_bat_nouls,
    hybrid_combine,
)
from .synergy_screening import (
    NOUL_KEYS as SYNERGY_NOUL_KEYS,
    RULE_ID as SYNERGY_RULE_ID,
    build_questions as build_synergy_questions,
    extract_nouls as extract_synergy_nouls,
    synergy_combine,
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
    """DEFAULT film path: Cohen ADHD Abstract Triage."""
    return build_cohen_questions()


def _post(text: str, questions: dict[str, Any], api_key: str, timeout: float) -> tuple[dict, float]:
    payload = {"state": text, "model": JEV_MODEL, "questions": questions}
    t0 = time.perf_counter()
    resp = requests.post(
        JEV_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    latency_ms = (time.perf_counter() - t0) * 1000.0
    if resp.status_code >= 400:
        raise RuntimeError(f"Jev HTTP {resp.status_code}: {resp.text[:500]}")
    return resp.json(), latency_ms


def _finite_nouls(nouls: dict[str, float]) -> dict[str, float | None]:
    return {
        k: (None if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else v)
        for k, v in nouls.items()
    }


def classify_cohen(text: str, api_key: str | None = None, timeout: float = 60.0) -> dict[str, Any]:
    key = api_key or load_api_key()
    questions = build_cohen_questions()
    data, latency_ms = _post(text, questions, key, timeout)
    answers = data.get("answers") or {}
    label_ans = answers.get("label") or {}
    choice = label_ans.get("choice")
    probs = label_ans.get("probabilities") or {}
    confidence = float(label_ans.get("confidence") or 0.0)
    nouls = extract_cohen_nouls(answers)
    pred = cohen_combine(choice, nouls)
    finite = _finite_nouls(nouls)
    in_tok = None
    usage = data.get("usage")
    if isinstance(usage, dict):
        in_tok = usage.get("input_tokens")
    cost = None
    if in_tok is not None:
        try:
            cost = float(in_tok) * INPUT_USD_PER_MTOK / 1_000_000.0
        except (TypeError, ValueError):
            cost = None
    return {
        "pred": pred,
        "choice": choice,
        "confidence": confidence,
        "p_include": float(probs.get(LABEL_INCLUDE) or 0.0),
        "p_exclude": float(probs.get(LABEL_EXCLUDE) or 0.0),
        "probabilities": {
            LABEL_INCLUDE: float(probs.get(LABEL_INCLUDE) or 0.0),
            LABEL_EXCLUDE: float(probs.get(LABEL_EXCLUDE) or 0.0),
        },
        **{k: finite[k] for k in COHEN_NOUL_KEYS},
        "answers": {
            "label": {
                "choice": choice,
                "confidence": confidence,
                "probabilities": {
                    LABEL_INCLUDE: float(probs.get(LABEL_INCLUDE) or 0.0),
                    LABEL_EXCLUDE: float(probs.get(LABEL_EXCLUDE) or 0.0),
                },
            },
            **{k: {"noul": finite[k]} for k in COHEN_NOUL_KEYS},
        },
        "latency_ms": latency_ms,
        "model": data.get("model"),
        "usage": usage,
        "input_tokens": in_tok,
        "cost_usd": cost,
        "rule": COHEN_RULE_ID,
        "mode": "cohen",
    }


def classify_synergy(text: str, api_key: str | None = None, timeout: float = 60.0) -> dict[str, Any]:
    key = api_key or load_api_key()
    questions = build_synergy_questions()
    data, latency_ms = _post(text, questions, key, timeout)
    answers = data.get("answers") or {}
    label_ans = answers.get("label") or {}
    choice = label_ans.get("choice")
    probs = label_ans.get("probabilities") or {}
    confidence = float(label_ans.get("confidence") or 0.0)
    nouls = extract_synergy_nouls(answers)
    pred = synergy_combine(choice, nouls)
    finite = _finite_nouls(nouls)
    return {
        "pred": pred,
        "choice": choice,
        "confidence": confidence,
        "p_include": float(probs.get(LABEL_INCLUDE) or 0.0),
        "p_exclude": float(probs.get(LABEL_EXCLUDE) or 0.0),
        "probabilities": {
            LABEL_INCLUDE: float(probs.get(LABEL_INCLUDE) or 0.0),
            LABEL_EXCLUDE: float(probs.get(LABEL_EXCLUDE) or 0.0),
        },
        **{k: finite[k] for k in SYNERGY_NOUL_KEYS},
        "answers": {
            "label": {
                "choice": choice,
                "confidence": confidence,
                "probabilities": {
                    LABEL_INCLUDE: float(probs.get(LABEL_INCLUDE) or 0.0),
                    LABEL_EXCLUDE: float(probs.get(LABEL_EXCLUDE) or 0.0),
                },
            },
            **{k: {"noul": finite[k]} for k in SYNERGY_NOUL_KEYS},
        },
        "latency_ms": latency_ms,
        "model": data.get("model"),
        "usage": data.get("usage"),
        "input_tokens": (data.get("usage") or {}).get("input_tokens")
        if isinstance(data.get("usage"), dict)
        else None,
        "rule": SYNERGY_RULE_ID,
        "mode": "synergy",
    }


def classify_bat4rct(text: str, api_key: str | None = None, timeout: float = 60.0) -> dict[str, Any]:
    key = api_key or load_api_key()
    questions = build_round3_questions()
    data, latency_ms = _post(text, questions, key, timeout)
    answers = data.get("answers") or {}
    label_ans = answers.get("label") or {}
    choice = label_ans.get("choice")
    probs = label_ans.get("probabilities") or {}
    confidence = float(label_ans.get("confidence") or 0.0)
    nouls = extract_bat_nouls(answers)
    pred = hybrid_combine(choice, nouls)
    finite = _finite_nouls(nouls)
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
        **{k: finite[k] for k in ALL_NOUL_KEYS},
        "answers": {
            "label": {
                "choice": choice,
                "confidence": confidence,
                "probabilities": {
                    LABEL_RCT: float(probs.get(LABEL_RCT) or 0.0),
                    LABEL_NON: float(probs.get(LABEL_NON) or 0.0),
                },
            },
            **{k: {"noul": finite[k]} for k in ALL_NOUL_KEYS},
        },
        "latency_ms": latency_ms,
        "model": data.get("model"),
        "usage": data.get("usage"),
        "input_tokens": (data.get("usage") or {}).get("input_tokens")
        if isinstance(data.get("usage"), dict)
        else None,
        "rule": "r3_ship_cd_choice_plus_reports_exp095",
        "mode": "bat4rct",
        "noul_is_rct": finite.get("has_random_allocation"),
    }


def classify(
    text: str,
    api_key: str | None = None,
    timeout: float = 60.0,
    mode: str = "cohen",
) -> dict[str, Any]:
    mode = (mode or "cohen").strip().lower()
    if mode == "bat4rct":
        return classify_bat4rct(text, api_key=api_key, timeout=timeout)
    if mode == "synergy":
        return classify_synergy(text, api_key=api_key, timeout=timeout)
    return classify_cohen(text, api_key=api_key, timeout=timeout)
