"""Cohen et al. 2006 — ADHD Abstract Triage (fair TIAB gold).

Gold: Abstract Triage Status only (I = include; anything else = exclude).
NEVER Article Triage. NEVER SYNERGY label_included.

Eligibility: Oregon DERP ADHD pharmacologic review. Encoded as Choice
include|exclude + atomic Nouls aligned to Cohen reason codes 2–7.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .config import (
    ADHD_CSV,
    ADHD_FILM_CSV,
    ADHD_H2H_CSV,
    ADHD_META,
    LABEL_EXCLUDE,
    LABEL_INCLUDE,
)

RULE_ID = "cohen_adhd_abstract_triage_choice_and_codes_2_7"
COMBINE_TEXT = (
    "include iff choice==include\n"
    "  AND eligible_population>=0.5\n"
    "  AND listed_adhd_drug>=0.5\n"
    "  AND eligible_outcome>=0.5\n"
    "  AND eligible_study_design>=0.5\n"
    "  AND wrong_publication_type<0.5\n"
    "  AND inadequate_study_duration<0.5"
)

NOUL_KEYS = (
    "eligible_population",
    "listed_adhd_drug",
    "eligible_outcome",
    "eligible_study_design",
    "wrong_publication_type",
    "inadequate_study_duration",
)

ELIGIBILITY = (
    "Oregon DERP — Pharmacologic treatments for ADHD (Final Report, Sep 2005). "
    "Population: pediatric or adult outpatients with ADD/ADHD. "
    "Interventions (IR/ER where applicable): amphetamine mixture (Adderall/XR), "
    "dextroamphetamine, dexmethylphenidate, methylphenidate (Ritalin/Concerta/Metadate/etc.), "
    "modafinil, pemoline, atomoxetine, bupropion, clonidine, guanfacine, and atypical "
    "antipsychotics (aripiprazole, clozapine, olanzapine, quetiapine, risperidone, ziprasidone). "
    "Outcomes: ADHD symptom response, functional capacity, caregiver satisfaction, quality of life, "
    "adverse effects / withdrawals / serious AEs, onset or duration of effect. "
    "Designs: controlled clinical trials, good-quality systematic reviews; observational studies "
    "only when they report functional or adverse-event outcomes. "
    "Exclude: wrong outcome, wrong drug (not on list), wrong population (not ADD/ADHD outpatients), "
    "wrong publication type (letter/editorial/news/no abstract usable for triage), "
    "wrong study design, wrong/inadequate study duration."
)

DRUG_LIST = (
    "amphetamine mixture / Adderall / Adderall XR; dextroamphetamine / Dexedrine / Dextrostat; "
    "dexmethylphenidate / Focalin; methylphenidate / Ritalin / Concerta / Metadate / Methylin; "
    "modafinil / Provigil; pemoline / Cylert; atomoxetine / Strattera; bupropion / Wellbutrin; "
    "clonidine / Catapres; guanfacine / Tenex; atypical antipsychotics "
    "(aripiprazole, clozapine, olanzapine, quetiapine, risperidone, ziprasidone)."
)


def load_metadata() -> dict[str, Any]:
    if ADHD_META.exists():
        return json.loads(ADHD_META.read_text(encoding="utf-8"))
    return {
        "dataset": "Cohen et al. 2006 — Abstract Triage",
        "topic": "ADHD",
        "n_full": 851,
        "n_include": 84,
        "eligibility": ELIGIBILITY,
        "paper_doi": "10.1197/jamia.M1929",
    }


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "gold" not in df.columns:
        col = "abs_triage" if "abs_triage" in df.columns else "abstract_triage_status"
        df["gold"] = df[col].map(
            lambda x: LABEL_INCLUDE if str(x).strip() == "I" else LABEL_EXCLUDE
        )
    df["gold"] = df["gold"].astype(str)
    df["title"] = df["title"].fillna("").astype(str)
    df["abstract"] = df["abstract"].fillna("").astype(str)
    if "pmid" not in df.columns:
        df["pmid"] = df.get("record_id", pd.Series(range(len(df)))).astype(str)
    else:
        df["pmid"] = df["pmid"].astype(str)
    if "record_id" not in df.columns:
        df["record_id"] = df["pmid"]
    else:
        df["record_id"] = df["record_id"].astype(str)
    if "demo_idx" not in df.columns:
        df["demo_idx"] = range(len(df))
    df["demo_idx"] = df["demo_idx"].astype(int)
    df["text"] = (df["title"] + "\n\n" + df["abstract"]).str.strip()
    return df.sort_values("demo_idx").reset_index(drop=True)


def load_demo(csv_path: Path | None = None) -> pd.DataFrame:
    path = csv_path or ADHD_CSV
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. See data/COHEN_LICENSE_NOTE.md")
    return _normalize(pd.read_csv(path))


def load_film() -> pd.DataFrame:
    if ADHD_FILM_CSV.exists():
        return _normalize(pd.read_csv(ADHD_FILM_CSV))
    return load_demo()


def load_h2h() -> pd.DataFrame:
    if not ADHD_H2H_CSV.exists():
        raise FileNotFoundError(f"Missing {ADHD_H2H_CSV}")
    return _normalize(pd.read_csv(ADHD_H2H_CSV))


def build_questions() -> dict[str, Any]:
    return {
        "label": {
            "type": "choice",
            "instructions": (
                "Screen this MEDLINE title and abstract for the Oregon DERP systematic review "
                "'Pharmacologic treatments for ADHD' (ADHD Final Report, Sep 2005), matching "
                "Cohen et al. 2006 Abstract Triage. Choose include or exclude. "
                "When eligibility is uncertain from title+abstract alone, prefer include "
                "(abstract-triage practice: pass uncertain citations to full-text review)."
            ),
            "criteria": {
                LABEL_INCLUDE: (
                    "Title/abstract is consistent with: ADD/ADHD outpatient population; "
                    f"at least one listed DERP ADHD drug ({DRUG_LIST}); "
                    "an eligible outcome (symptoms, function, QoL, caregiver satisfaction, or AEs); "
                    "and an eligible design (controlled trial, good systematic review, or observational "
                    "study with functional/AE outcomes). Not clearly a wrong publication type or "
                    "clearly inadequate duration for the question."
                ),
                LABEL_EXCLUDE: (
                    "Clearly out of scope on abstract triage: wrong outcome; drug not on the DERP ADHD "
                    "list; population not ADD/ADHD outpatients; wrong publication type "
                    "(letter, editorial, news, non-research); wrong study design; or inadequate/"
                    "wrong study duration — Cohen reason codes 2–7."
                ),
            },
        },
        "eligible_population": {
            "type": "noul",
            "instructions": (
                "Cohen code 4 inverse: the record concerns pediatric or adult outpatients with "
                "Attention Deficit Disorder (ADD) or Attention Deficit Hyperactivity Disorder (ADHD), "
                "not a clearly different population (e.g., only schizophrenia, only epilepsy without ADHD)."
            ),
        },
        "listed_adhd_drug": {
            "type": "noul",
            "instructions": (
                "Cohen code 3 inverse: the title or abstract involves at least one DERP-listed ADHD "
                f"pharmacologic treatment: {DRUG_LIST}"
            ),
        },
        "eligible_outcome": {
            "type": "noul",
            "instructions": (
                "Cohen code 2 inverse: the record addresses an eligible outcome — ADHD symptom response, "
                "functional capacity (social/academic/occupational), caregiver satisfaction, quality of life, "
                "adverse effects / withdrawals / serious AEs, or onset/duration of effectiveness — "
                "not solely an unrelated endpoint."
            ),
        },
        "eligible_study_design": {
            "type": "noul",
            "instructions": (
                "Cohen code 6 inverse: study design appears to be a controlled clinical trial, "
                "a good-quality systematic review/meta-analysis of such trials, or an observational "
                "study that reports functional or adverse-event outcomes. Animal-only, in-vitro-only, "
                "or pure methods papers without clinical outcomes score low."
            ),
        },
        "wrong_publication_type": {
            "type": "noul",
            "instructions": (
                "Cohen code 5: this is a wrong publication type for abstract triage inclusion — "
                "letter, editorial, commentary, news, conference abstract without usable methods/"
                "outcomes detail, or similar non-research item. Score high if clearly that type."
            ),
        },
        "inadequate_study_duration": {
            "type": "noul",
            "instructions": (
                "Cohen code 7: study duration is clearly inadequate or wrong for evaluating ADHD "
                "pharmacologic effectiveness or harms as framed by the DERP review (e.g., single-dose "
                "PK-only with no clinical ADHD outcome, or duration so short it cannot speak to "
                "treatment response). Score high only when duration is clearly inadequate from TIAB."
            ),
        },
    }


def _f(nouls: dict[str, float] | None, key: str, default: float = 0.0) -> float:
    if not nouls:
        return default
    try:
        v = float(nouls.get(key))  # type: ignore[arg-type]
        if v != v:
            return default
        return v
    except (TypeError, ValueError):
        return default


def cohen_combine(choice: str | None, nouls: dict[str, float] | None = None) -> str:
    if (choice or "").strip() != LABEL_INCLUDE:
        return LABEL_EXCLUDE
    if (
        _f(nouls, "eligible_population") >= 0.5
        and _f(nouls, "listed_adhd_drug") >= 0.5
        and _f(nouls, "eligible_outcome") >= 0.5
        and _f(nouls, "eligible_study_design") >= 0.5
        and _f(nouls, "wrong_publication_type") < 0.5
        and _f(nouls, "inadequate_study_duration") < 0.5
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


def criteria_text_for_anthropic() -> str:
    qs = build_questions()
    return (
        f"{ELIGIBILITY}\n\n"
        "Decide include or exclude from TITLE + ABSTRACT only "
        "(Abstract Triage / TIAB; do not assume full text).\n"
        f"INCLUDE when: {qs['label']['criteria'][LABEL_INCLUDE]}\n"
        f"EXCLUDE when: {qs['label']['criteria'][LABEL_EXCLUDE]}\n"
        "If uncertain from TIAB alone, prefer include."
    )


# runner aliases
RULE_ID = RULE_ID
load_metadata = load_metadata
load_h2h = load_h2h
