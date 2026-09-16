"""Round-3 ship default: CD medium Choice + R2/R3 nouls (NOT aggressive; NOT exp@0.5)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import LABEL_NON, LABEL_RCT, RESULTS_DIR

NOUL_THRESHOLD = 0.5
EXP_THRESHOLD = 0.95  # FP-safe gate (0.5 adds FP=2 — do not ship)

# Shipped nouls in combine + UI
NOUL_KEYS = (
    "has_random_allocation",
    "parallel_intervention_arms",
    "is_cluster_random",
    "is_secondary_or_nested_only",
    "is_protocol_or_single_arm",
    "reports_or_reanalyzes_an_rct",
    "is_review_or_meta",
    "experimental_allocation_implied",
)

# Present in questions_v3; queried live; not required by ship rule
OPTIONAL_NOUL_KEYS = (
    "parent_study_was_rct",
)

ALL_NOUL_KEYS = NOUL_KEYS + OPTIONAL_NOUL_KEYS

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


def _questions_v3_path() -> Path:
    return RESULTS_DIR / "round3" / "questions_v3.json"


def load_noul_questions() -> dict[str, Any]:
    """Atomic nouls from questions_v3.json (label stripped — we use CD medium)."""
    path = _questions_v3_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if k != "label" and isinstance(v, dict)}


def build_hybrid_questions() -> dict[str, Any]:
    """Full questions map: CD medium Choice + round-3 nouls (questions_v3)."""
    qs: dict[str, Any] = {"label": dict(CD_MEDIUM_LABEL)}
    qs.update(load_noul_questions())
    return qs


build_round3_questions = build_hybrid_questions


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
    exp_threshold: float = EXP_THRESHOLD,
    aggressive: bool = False,
) -> str:
    """
    DEFAULT r3_ship (aggressive=False):
      RCT iff choice==RCT
        OR ((rand|cluster|parallel)>=t AND secondary<t AND protocol<t)
        OR (reports_or_reanalyzes_an_rct>=t AND is_review_or_meta<t)
        OR (experimental_allocation_implied>=exp_t
            AND secondary<t AND protocol<t AND review<t)

    Aggressive drops the secondary exclude — DO NOT use for the demo default.
    exp@0.5 (psych OR without 0.95 gate) is NOT shipped (FP=2).
    """
    if aggressive:
        raise ValueError("aggressive hybrid is not the demo default; refuse to apply")

    t = threshold
    exp_t = exp_threshold
    choice_rct = choice == LABEL_RCT
    positive = (
        _as_float(nouls.get("has_random_allocation")) >= t
        or _as_float(nouls.get("is_cluster_random")) >= t
        or _as_float(nouls.get("parallel_intervention_arms")) >= t
    )
    secondary = _as_float(nouls.get("is_secondary_or_nested_only"))
    protocol = _as_float(nouls.get("is_protocol_or_single_arm"))
    review = _as_float(nouls.get("is_review_or_meta"))
    exclude = secondary >= t or protocol >= t

    reports_path = (
        _as_float(nouls.get("reports_or_reanalyzes_an_rct")) >= t
        and review < t
    )
    # FP-safe experimental path (gate 0.95 — NOT 0.5)
    exp_path = (
        _as_float(nouls.get("experimental_allocation_implied")) >= exp_t
        and secondary < t
        and protocol < t
        and review < t
    )

    if choice_rct:
        return LABEL_RCT
    if positive and not exclude:
        return LABEL_RCT
    if reports_path:
        return LABEL_RCT
    if exp_path:
        return LABEL_RCT
    return LABEL_NON


def extract_nouls(answers: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key in ALL_NOUL_KEYS:
        ans = answers.get(key) or {}
        out[key] = _as_float(ans.get("noul"), float("nan"))
    return out
