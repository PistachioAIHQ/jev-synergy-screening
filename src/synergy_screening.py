"""Donners_2021 SYNERGY human screening: Choice include|exclude + atomic nouls."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .config import DATA_DIR, LABEL_EXCLUDE, LABEL_INCLUDE

DONNERS_CSV = DATA_DIR / "donners_258.csv"
DONNERS_META = DATA_DIR / "donners_metadata.json"

# Shipped combine: Choice-only (document clearly). Iterate once if Acc terrible.
RULE_ID = "synergy_donners_choice_and_eligibility_nouls"
COMBINE_TEXT = (
    "include iff choice==include\n"
    "  AND mentions_emicizumab>=0.5\n"
    "  AND is_human_data>=0.5\n"
    "  AND reports_pk_or_pkpd>=0.5\n"
    "  AND is_secondary_without_pk<0.5\n"
    "(One iteration after Choice-only: Acc 86.8%/F1 39.3% → Acc 91.9%/F1 48.8%; "
    "nouls gate false includes that lack PK / are secondary.)"
)

NOUL_KEYS = (
    "mentions_emicizumab",
    "is_human_data",
    "reports_pk_or_pkpd",
    "is_secondary_without_pk",
)

ELIGIBILITY = (
    "The following inclusion criteria were applied: emicizumab studies providing "
    "(1) data on humans, (2) original PK data or modeled PK data or PK/PD relationships, "
    "and (3) access to the abstract and the full text in English."
)


def load_metadata() -> dict[str, Any]:
    if DONNERS_META.exists():
        return json.loads(DONNERS_META.read_text(encoding="utf-8"))
    return {
        "review": "Donners_2021",
        "eligibility_criteria": ELIGIBILITY,
        "n_records": 258,
        "n_included": 15,
    }


def load_demo(csv_path: Path | None = None) -> pd.DataFrame:
    path = csv_path or DONNERS_CSV
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Export Donners_2021 via synergy-dataset "
            "(see README) or restore committed data/donners_258.csv."
        )
    df = pd.read_csv(path)
    if "gold" not in df.columns:
        df["gold"] = df["label_included"].map({1: LABEL_INCLUDE, 0: LABEL_EXCLUDE, True: LABEL_INCLUDE, False: LABEL_EXCLUDE})
    df["gold"] = df["gold"].astype(str)
    df["title"] = df["title"].fillna("").astype(str)
    df["abstract"] = df["abstract"].fillna("").astype(str)
    if "demo_idx" not in df.columns:
        df["demo_idx"] = range(len(df))
    if "record_id" not in df.columns:
        df["record_id"] = df.get("openalex_id", pd.Series(range(len(df)))).astype(str)
    df["text"] = (df["title"] + "\n\n" + df["abstract"]).str.strip()
    return df.sort_values("demo_idx").reset_index(drop=True)


def build_questions() -> dict[str, Any]:
    """Map of Choice + atomic Nouls encoding Donners eligibility."""
    return {
        "label": {
            "type": "choice",
            "instructions": (
                "Screen this title and abstract for the systematic review "
                "'Pharmacokinetics and Associated Efficacy of Emicizumab in Humans' "
                "(Donners et al., 2021). Choose include or exclude. "
                "When eligibility is uncertain from the abstract, prefer include "
                "(matching the original reviewers' practice)."
            ),
            "criteria": {
                LABEL_INCLUDE: (
                    "Emicizumab (ACE910 / Hemlibra) study providing data on humans AND "
                    "original pharmacokinetic (PK) data, modeled PK data, or a PK/PD "
                    "relationship. English-language research with accessible abstract/full text."
                ),
                LABEL_EXCLUDE: (
                    "Does not meet inclusion: not about emicizumab; animal-only or in-vitro-only; "
                    "no original/modeled PK or PK/PD content; pure opinion/editorial/guideline "
                    "without PK data; or otherwise out of scope."
                ),
            },
        },
        "mentions_emicizumab": {
            "type": "noul",
            "instructions": (
                "The title or abstract concerns emicizumab "
                "(also known as ACE910 or Hemlibra / Hemlibra®)."
            ),
        },
        "is_human_data": {
            "type": "noul",
            "instructions": (
                "The record reports data on humans (patients with hemophilia or healthy "
                "volunteers), not animal-only or in-vitro-only experiments."
            ),
        },
        "reports_pk_or_pkpd": {
            "type": "noul",
            "instructions": (
                "The record provides original pharmacokinetic data, modeled PK results, "
                "and/or a pharmacokinetic/pharmacodynamic (PK/PD) relationship for emicizumab."
            ),
        },
        "is_secondary_without_pk": {
            "type": "noul",
            "instructions": (
                "This is a review, editorial, guideline, commentary, or news item that does "
                "not present original or modeled PK / PK-PD results."
            ),
        },
    }


def _f(nouls: dict[str, float] | None, key: str, default: float = 0.0) -> float:
    if not nouls:
        return default
    try:
        v = float(nouls.get(key))  # type: ignore[arg-type]
        if v != v:  # NaN
            return default
        return v
    except (TypeError, ValueError):
        return default


def synergy_combine(choice: str | None, nouls: dict[str, float] | None = None) -> str:
    """Shipped rule (post Choice-only iteration): Choice AND eligibility nouls."""
    if (choice or "").strip() != LABEL_INCLUDE:
        return LABEL_EXCLUDE
    if (
        _f(nouls, "mentions_emicizumab") >= 0.5
        and _f(nouls, "is_human_data") >= 0.5
        and _f(nouls, "reports_pk_or_pkpd") >= 0.5
        and _f(nouls, "is_secondary_without_pk") < 0.5
    ):
        return LABEL_INCLUDE
    return LABEL_EXCLUDE


def extract_nouls(answers: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for k in NOUL_KEYS:
        ans = answers.get(k) or {}
        v = ans.get("noul")
        try:
            out[k] = float(v) if v is not None else float("nan")
        except (TypeError, ValueError):
            out[k] = float("nan")
    return out
