"""Cohen et al. 2006 — ADHD Abstract Triage (fair TIAB gold).

Gold: Abstract Triage Status only (I = include; anything else = exclude).
NEVER Article Triage. NEVER SYNERGY label_included.

Eligibility: Oregon DERP ADHD pharmacologic review. Encoded as Choice
include|exclude + atomic Nouls (r2_ship).
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

RULE_ID = "cohen_adhd_r2_ship"
COMBINE_TEXT = (
    "include iff choice==include\n"
    "  AND is_drug_monograph_or_product_profile<0.5\n"
    "  AND is_imaging_or_biomarker_only<0.5\n"
    "  AND is_formulation_dev_without_efficacy<0.5\n"
    "  AND eligible_population>=0.4\n"
    "  AND listed_adhd_drug>=0.5\n"
    "  AND eligible_outcome>=0.35\n"
    "  AND eligible_study_design>=0.45\n"
    "  AND wrong_publication_type<0.4\n"
    "  AND inadequate_study_duration<0.85"
)

NOUL_KEYS = (
    "eligible_population",
    "listed_adhd_drug",
    "eligible_outcome",
    "eligible_study_design",
    "wrong_publication_type",
    "inadequate_study_duration",
    "is_drug_monograph_or_product_profile",
    "is_imaging_or_biomarker_only",
    "is_formulation_dev_without_efficacy",
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

# Exact port of /workspace/jev-ablation/cohen-adhd-r2/questions_r2.json
_QUESTIONS_R2: dict[str, Any] = {
    "label": {
        "type": "choice",
        "instructions": (
            "Screen this MEDLINE title and abstract for the Oregon DERP systematic review "
            "'Pharmacologic treatments for ADHD' (ADHD Final Report, Sep 2005), matching "
            "Cohen et al. 2006 Abstract Triage. Choose include or exclude. When eligibility is "
            "uncertain from title+abstract alone, prefer include (abstract-triage practice: pass "
            "uncertain citations to full-text review). INCLUDE secondary/acquired attentional "
            "disorders (e.g., after brain injury) when a listed ADHD drug is studied for "
            "attention/ADHD-like symptoms. EXCLUDE clear drug monographs/product profiles (title "
            "is just a drug name; Adis-style narrative prescribing summaries), pure "
            "imaging/biomarker mechanism papers without clinical ADHD symptom/function/AE "
            "endpoints, and formulation/PK development papers without efficacy/effectiveness outcomes."
        ),
        "criteria": {
            "include": (
                "Title/abstract is consistent with: ADD/ADHD or closely related attentional-disorder "
                "outpatients (including acquired/secondary attention deficits treated pharmacologically); "
                f"at least one listed DERP ADHD drug ({DRUG_LIST}); "
                "an eligible clinical outcome (ADHD/attention symptoms, classroom/academic/social "
                "function, caregiver satisfaction, QoL, AEs/withdrawals, onset/duration of effect); "
                "and an eligible design (controlled trial, good SR, or observational with functional/AE "
                "outcomes). Not clearly a monograph, letter/editorial, or PK-only formulation paper."
            ),
            "exclude": (
                "Clearly out of scope on abstract triage — Cohen reason codes 2–7: wrong outcome "
                "(imaging/EEG/neurochemistry-only without clinical ADHD endpoints); wrong drug; wrong "
                "population (not ADD/ADHD/attentional outpatients); wrong publication type (letter, "
                "editorial, news, drug monograph/product profile); wrong study design (formulation "
                "development without efficacy; methods-only); or clearly inadequate duration "
                "(single-dose PK-only with no clinical ADHD outcome)."
            ),
        },
    },
    "eligible_population": {
        "type": "noul",
        "instructions": (
            "Cohen code 4 inverse: concerns pediatric or adult outpatients with ADD/ADHD OR a "
            "closely related attentional disorder being treated with ADHD pharmacotherapy "
            "(including acquired/secondary attention deficits after brain injury). Score low only "
            "for clearly different populations (e.g., only schizophrenia, only epilepsy without "
            "ADHD/attention treatment aim, diabetes AE studies without ADHD focus)."
        ),
    },
    "listed_adhd_drug": {
        "type": "noul",
        "instructions": (
            "Cohen code 3 inverse: title or abstract involves at least one DERP-listed ADHD "
            f"pharmacologic treatment: {DRUG_LIST} Generic class terms (stimulant, psychostimulant, "
            "MPH, DEX) count if clearly one of these agents. Score low for drugs not on the list "
            "(e.g., carbamazepine, selegiline, ibuprofen) as primary intervention."
        ),
    },
    "eligible_outcome": {
        "type": "noul",
        "instructions": (
            "Cohen code 2 inverse: addresses an eligible clinical outcome — ADHD/attention symptom "
            "response, functional capacity (social/academic/occupational/classroom behavior), "
            "reinforcer/motivation effects relevant to classroom function, caregiver satisfaction, "
            "quality of life, adverse effects / withdrawals / serious AEs, or onset/duration of "
            "effectiveness. Score LOW when the ONLY endpoints are imaging (fMRI/MRI), EEG/ERP, CSF "
            "metabolites, or other biomarkers/mechanisms without clinical ADHD symptom, function, "
            "or AE outcomes."
        ),
    },
    "eligible_study_design": {
        "type": "noul",
        "instructions": (
            "Cohen code 6 inverse: appears to be a controlled clinical trial, good-quality "
            "systematic review/meta-analysis, or observational study reporting functional or AE "
            "outcomes. Score LOW for formulation/PK development without efficacy endpoints, "
            "animal-only, in-vitro-only, pure methods papers, or N-of-1 methods without clinical "
            "ADHD outcomes."
        ),
    },
    "wrong_publication_type": {
        "type": "noul",
        "instructions": (
            "Cohen code 5: wrong publication type for abstract-triage inclusion — letter, editorial, "
            "commentary, news, conference abstract without usable methods/outcomes, OR a drug "
            "monograph / product profile / narrative prescribing summary (often titled only with "
            "the drug name, e.g. 'Atomoxetine.' or 'Dexmethylphenidate.', summarizing "
            "pharmacology/dosing rather than reporting a primary study). Score HIGH if clearly that type."
        ),
    },
    "inadequate_study_duration": {
        "type": "noul",
        "instructions": (
            "Cohen code 7: score HIGH only when duration is clearly inadequate from TIAB for "
            "evaluating ADHD pharmacologic effectiveness or harms — e.g., single-dose PK-only with "
            "no clinical ADHD symptom/function/AE outcome. Do NOT score high merely because duration "
            "is short but a clinical ADHD/behavioral endpoint is measured (acute classroom/lab "
            "challenge studies can be eligible)."
        ),
    },
    "is_drug_monograph_or_product_profile": {
        "type": "noul",
        "instructions": (
            "Cohen code 5 specialist: this record is primarily a drug monograph, Adis Drug Profile, "
            "product information summary, or narrative review of a single agent's "
            "pharmacology/dosing/indications rather than an original comparative/efficacy trial or "
            "systematic review with extractable study results. High score = monograph/profile."
        ),
    },
    "is_imaging_or_biomarker_only": {
        "type": "noul",
        "instructions": (
            "Cohen code 2 specialist: the primary reported outcomes are neuroimaging "
            "(fMRI/MRI/PET), EEG/ERP, CSF neurochemistry, or other biomarkers/mechanisms, WITHOUT "
            "clinical ADHD symptom scales, functional/classroom outcomes, or adverse-event endpoints "
            "as study aims. High score = imaging/biomarker-only wrong outcome."
        ),
    },
    "is_formulation_dev_without_efficacy": {
        "type": "noul",
        "instructions": (
            "Cohen code 6 specialist: paper focuses on developing or describing a new "
            "formulation/delivery system (e.g., once-a-day MPH development, OROS engineering) with "
            "PK/formulation endpoints and without reporting a controlled efficacy/effectiveness "
            "evaluation of ADHD outcomes. High score = formulation-dev without efficacy."
        ),
    },
}


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
    """Exact questions_r2.json (r2_ship)."""
    return json.loads(json.dumps(_QUESTIONS_R2))


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
    """r2_ship combine (from jev-ablation/cohen-adhd-r2)."""
    if (choice or "").strip() != LABEL_INCLUDE:
        return LABEL_EXCLUDE
    if _f(nouls, "is_drug_monograph_or_product_profile") >= 0.5:
        return LABEL_EXCLUDE
    if _f(nouls, "is_imaging_or_biomarker_only") >= 0.5:
        return LABEL_EXCLUDE
    if _f(nouls, "is_formulation_dev_without_efficacy") >= 0.5:
        return LABEL_EXCLUDE
    if (
        _f(nouls, "eligible_population") >= 0.4
        and _f(nouls, "listed_adhd_drug") >= 0.5
        and _f(nouls, "eligible_outcome") >= 0.35
        and _f(nouls, "eligible_study_design") >= 0.45
        and _f(nouls, "wrong_publication_type") < 0.4
        and _f(nouls, "inadequate_study_duration") < 0.85
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
