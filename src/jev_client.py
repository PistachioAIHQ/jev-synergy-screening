from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import requests

from .config import JEV_MODEL, JEV_URL, LABEL_NON, LABEL_RCT


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
    """Choice RCT|non_RCT + optional Noul. questions must be a map."""
    return {
        "label": {
            "type": "choice",
            "instructions": (
                "Classify this MEDLINE title and abstract as RCT or non_RCT. "
                "An RCT randomly assigns participants to intervention vs control/comparison."
            ),
            "criteria": {
                LABEL_RCT: (
                    "Reports a randomized controlled trial (or randomised controlled trial): "
                    "participants were randomly allocated to intervention arms."
                ),
                LABEL_NON: (
                    "Not an RCT: observational study, case report/series, review, "
                    "meta-analysis, guideline, commentary, letter, animal-only, or unclear."
                ),
            },
        },
        "is_rct_statement": {
            "type": "noul",
            "instructions": "This abstract reports a randomized controlled trial",
            "criteria": {
                "true": "Clear evidence of random allocation to trial arms",
                "false": "Not clearly an RCT",
            },
        },
    }


def classify(text: str, api_key: str | None = None, timeout: float = 60.0) -> dict[str, Any]:
    """POST systemone; return prediction fields + latency_ms. No rationale text."""
    key = api_key or load_api_key()
    payload = {
        "state": text,
        "model": JEV_MODEL,
        "questions": build_questions(),
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
    noul_ans = answers.get("is_rct_statement") or {}
    choice = label_ans.get("choice")
    probs = label_ans.get("probabilities") or {}
    return {
        "pred": choice,
        "confidence": float(label_ans.get("confidence") or 0.0),
        "p_RCT": float(probs.get(LABEL_RCT) or 0.0),
        "p_non_RCT": float(probs.get(LABEL_NON) or 0.0),
        "noul_is_rct": float(noul_ans.get("noul") if noul_ans.get("noul") is not None else float("nan")),
        "latency_ms": latency_ms,
        "model": data.get("model"),
        "usage": data.get("usage"),
    }
