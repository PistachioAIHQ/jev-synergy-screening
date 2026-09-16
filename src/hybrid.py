"""Round-2 hybrid default: CD medium Choice + atomic nouls (NOT aggressive)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import LABEL_NON, LABEL_RCT, RESULTS_DIR

NOUL_THRESHOLD = 0.5
NOUL_KEYS = (
    "has_random_allocation",
    "parallel_intervention_arms",
    "is_cluster_random",
    "is_secondary_or_nested_only",
    "is_protocol_or_single_arm",
)

# CD medium Choice — Acc 87% / F1 85.23% choice-only (NOT the longer R2 rewrite).
CD_MEDIUM_LABEL: dict[str, Any] = {
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
}


def _questions_v2_path() -> Path:
    return RESULTS_DIR / "round2" / "questions_v2.json"


def load_noul_questions() -> dict[str, Any]:
    """Atomic nouls from questions_v2.json (label stripped — we use CD medium)."""
    path = _questions_v2_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if k != "label" and isinstance(v, dict)}


def build_hybrid_questions() -> dict[str, Any]:
    """Full questions map: CD medium Choice + R2 atomic nouls."""
    qs: dict[str, Any] = {"label": dict(CD_MEDIUM_LABEL)}
    qs.update(load_noul_questions())
    return qs


def _as_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def hybrid_combine(
    choice: str | None,
    nouls: dict[str, float],
    *,
    threshold: float = NOUL_THRESHOLD,
    aggressive: bool = False,
) -> str:
    """
    DEFAULT hybrid (aggressive=False):
      RCT iff choice==RCT OR (
        (has_random_allocation>=t OR is_cluster_random>=t OR parallel_intervention_arms>=t)
        AND is_secondary_or_nested_only<t
        AND is_protocol_or_single_arm<t
      )

    Aggressive drops the secondary exclude — DO NOT use for the demo default.
    """
    if aggressive:
        raise ValueError("aggressive hybrid is not the demo default; refuse to apply")

    t = threshold
    choice_rct = choice == LABEL_RCT
    positive = (
        _as_float(nouls.get("has_random_allocation")) >= t
        or _as_float(nouls.get("is_cluster_random")) >= t
        or _as_float(nouls.get("parallel_intervention_arms")) >= t
    )
    exclude = (
        _as_float(nouls.get("is_secondary_or_nested_only")) >= t
        or _as_float(nouls.get("is_protocol_or_single_arm")) >= t
    )
    if choice_rct:
        return LABEL_RCT
    if positive and not exclude:
        return LABEL_RCT
    return LABEL_NON


def extract_nouls(answers: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key in NOUL_KEYS:
        ans = answers.get(key) or {}
        out[key] = _as_float(ans.get("noul"), float("nan"))
    return out
