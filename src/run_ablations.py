"""Systematic Jev prompt/criteria ablations on fixed demo_200 IDs.

Caches raw API answers per (pmid, variant_family) so dual_gate / conf_gate
threshold sweeps do not re-hit the API.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import requests

from .bat4rct import load_demo
from .config import JEV_MODEL, JEV_URL, LABEL_NON, LABEL_RCT, RESULTS_DIR
from .jev_client import load_api_key
from .metrics import compute_metrics

CACHE_DIR = RESULTS_DIR / "ablation_cache"
TABLE_MD = RESULTS_DIR / "ablations_table.md"
TABLE_CSV = RESULTS_DIR / "ablations_table.csv"

# ---- question builders -----------------------------------------------------

BASELINE_CHOICE = {
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

STRONGER_CHOICE = {
    "type": "choice",
    "instructions": (
        "Classify this MEDLINE citation as RCT or non_RCT using a strict MEDLINE-style "
        "definition of a completed human randomized controlled trial."
    ),
    "criteria": {
        LABEL_RCT: (
            "Completed human RCT: humans were randomly assigned to intervention vs "
            "control/comparison arms, and the abstract reports trial results (not a protocol)."
        ),
        LABEL_NON: (
            "Not a completed human RCT: protocols/study designs without results; "
            "observational (cohort, case-control, cross-sectional); reviews/meta-analyses/"
            "systematic reviews; animal-only or in-vitro; quasi-experimental or "
            "non-random allocation; case reports/series; commentaries/letters/guidelines; "
            "or insufficient evidence of random assignment of human participants."
        ),
    },
}

NOUL_BASELINE = {
    "type": "noul",
    "instructions": "This abstract reports a randomized controlled trial",
    "criteria": {
        "true": "Clear evidence of random allocation to trial arms",
        "false": "Not clearly an RCT",
    },
}

NOUL_COMPLETED_HUMAN = {
    "type": "noul",
    "instructions": "This abstract reports a completed human randomized controlled trial",
    "criteria": {
        "true": (
            "Humans randomly assigned to interventions; results of a completed trial "
            "(not protocol-only, observational, review, animal-only, or quasi-experimental)."
        ),
        "false": "Does not clearly report a completed human RCT",
    },
}

SCORE_RUBRIC = {
    "type": "score",
    "instructions": (
        "How clearly does this MEDLINE title and abstract report a completed human "
        "randomized controlled trial (humans randomly assigned to interventions)?"
    ),
    "criteria": [
        "Clearly not an RCT: observational, review, protocol-only, animal-only, "
        "quasi-experimental, case report, or no random assignment of humans.",
        "Ambiguous: mentions randomization or trial language but unclear whether a "
        "completed human RCT with random allocation was performed.",
        "Clearly a completed human RCT: humans randomly assigned to intervention arms "
        "and results are reported.",
    ],
}

SCORE_THRESHOLD = 1.5  # score >= 1.5 → RCT (levels 0/1/2)


def questions_baseline_family() -> dict[str, Any]:
    """One call feeds baseline / dual_gate / conf_gate / title_abstract."""
    return {
        "label": BASELINE_CHOICE,
        "is_rct_statement": NOUL_BASELINE,
        "is_completed_human_rct": NOUL_COMPLETED_HUMAN,
    }


def questions_stronger_family() -> dict[str, Any]:
    return {
        "label": STRONGER_CHOICE,
        "is_rct_statement": NOUL_COMPLETED_HUMAN,
        "is_completed_human_rct": NOUL_COMPLETED_HUMAN,
    }


def questions_score_family() -> dict[str, Any]:
    return {"rct_clarity": SCORE_RUBRIC}


# ---- API + cache -----------------------------------------------------------

def cache_path(family: str, pmid: str) -> Path:
    return CACHE_DIR / family / f"{pmid}.json"


def call_systemone(
    state: str,
    questions: dict[str, Any],
    api_key: str,
    timeout: float = 60.0,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    resp = requests.post(
        JEV_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"state": state, "model": JEV_MODEL, "questions": questions},
        timeout=timeout,
    )
    latency_ms = (time.perf_counter() - t0) * 1000.0
    if resp.status_code >= 400:
        raise RuntimeError(f"Jev HTTP {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    data["_latency_ms"] = latency_ms
    return data


def fetch_cached(
    family: str,
    pmid: str,
    state: str,
    questions: dict[str, Any],
    api_key: str,
    force: bool = False,
) -> dict[str, Any]:
    path = cache_path(family, pmid)
    if path.exists() and not force:
        return json.loads(path.read_text(encoding="utf-8"))
    data = call_systemone(state, questions, api_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def _finite(x: Any, default: float = float("nan")) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def parse_choice_bundle(data: dict[str, Any]) -> dict[str, Any]:
    answers = data.get("answers") or {}
    label = answers.get("label") or {}
    probs = label.get("probabilities") or {}
    noul_base = answers.get("is_rct_statement") or {}
    noul_comp = answers.get("is_completed_human_rct") or {}
    return {
        "choice": label.get("choice"),
        "confidence": _finite(label.get("confidence"), 0.0),
        "p_RCT": _finite(probs.get(LABEL_RCT), 0.0),
        "p_non_RCT": _finite(probs.get(LABEL_NON), 0.0),
        "noul_baseline": _finite(noul_base.get("noul")),
        "noul_completed": _finite(noul_comp.get("noul")),
        "latency_ms": _finite(data.get("_latency_ms"), 0.0),
        "error": "",
    }


def parse_score(data: dict[str, Any]) -> dict[str, Any]:
    answers = data.get("answers") or {}
    sc = answers.get("rct_clarity") or {}
    score = _finite(sc.get("score"))
    return {
        "score": score,
        "confidence": _finite(sc.get("confidence"), 0.0),
        "latency_ms": _finite(data.get("_latency_ms"), 0.0),
        "error": "",
        "pred": LABEL_RCT if (math.isfinite(score) and score >= SCORE_THRESHOLD) else LABEL_NON,
    }


# ---- family runners --------------------------------------------------------

def run_family(
    name: str,
    demo: pd.DataFrame,
    state_fn: Callable[[dict], str],
    questions: dict[str, Any],
    api_key: str,
    workers: int,
    force: bool,
) -> dict[str, dict[str, Any]]:
    """Return pmid -> raw cached response dict (with _latency_ms)."""
    rows = demo.to_dict(orient="records")
    out: dict[str, dict[str, Any]] = {}
    errors = 0

    def _one(row: dict) -> tuple[str, dict[str, Any]]:
        pmid = str(row["pmid"])
        try:
            data = fetch_cached(
                name, pmid, state_fn(row), questions, api_key, force=force
            )
            return pmid, data
        except Exception as e:  # noqa: BLE001
            return pmid, {"_error": str(e)[:400], "_latency_ms": 0.0, "answers": {}}

    print(f"[{name}] fetching {len(rows)} (workers={workers}) …", flush=True)
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_one, r) for r in rows]
        done = 0
        for fut in as_completed(futs):
            pmid, data = fut.result()
            out[pmid] = data
            if data.get("_error"):
                errors += 1
            done += 1
            if done % 25 == 0 or done == len(rows):
                print(f"  [{name}] {done}/{len(rows)} errors={errors}", flush=True)
    print(f"[{name}] done in {time.perf_counter()-t0:.1f}s errors={errors}", flush=True)
    return out


def metrics_row(
    variant: str,
    golds: list[str],
    preds: list[str],
    lats: list[float],
    extra: dict | None = None,
) -> dict:
    m = compute_metrics(golds, preds, lats)
    row = {
        "variant": variant,
        "n": m["n"],
        "accuracy": m["accuracy"],
        "precision_RCT": m["precision_RCT"],
        "recall_RCT": m["recall_RCT"],
        "f1_RCT": m["f1_RCT"],
        "mean_latency_ms": m["mean_latency_ms"],
        "tp": m["tp"],
        "fp": m["fp"],
        "fn": m["fn"],
        "tn": m["tn"],
        "coverage": 1.0,
    }
    if extra:
        row.update(extra)
    return row


def evaluate_choice_preds(
    variant: str,
    demo: pd.DataFrame,
    parsed_by_pmid: dict[str, dict],
    pred_fn: Callable[[dict], str],
) -> tuple[dict, pd.DataFrame]:
    golds, preds, lats, records = [], [], [], []
    for row in demo.to_dict(orient="records"):
        pmid = str(row["pmid"])
        p = parsed_by_pmid.get(pmid) or {}
        if p.get("error") or not p.get("choice"):
            # count as miss / empty skip from metrics? include as wrong empty
            pred = ""
            lat = _finite(p.get("latency_ms"), 0.0)
        else:
            pred = pred_fn(p)
            lat = _finite(p.get("latency_ms"), 0.0)
        if not pred:
            continue
        golds.append(row["gold"])
        preds.append(pred)
        lats.append(lat)
        records.append(
            {
                "demo_idx": row["demo_idx"],
                "pmid": pmid,
                "gold": row["gold"],
                "pred": pred,
                "confidence": p.get("confidence"),
                "p_RCT": p.get("p_RCT"),
                "p_non_RCT": p.get("p_non_RCT"),
                "noul_baseline": p.get("noul_baseline"),
                "noul_completed": p.get("noul_completed"),
                "latency_ms": lat,
                "correct": pred == row["gold"],
                "variant": variant,
            }
        )
    return metrics_row(variant, golds, preds, lats), pd.DataFrame(records)


def evaluate_conf_gate(
    variant: str,
    demo: pd.DataFrame,
    parsed_by_pmid: dict[str, dict],
    tau: float,
) -> tuple[dict, pd.DataFrame]:
    golds, preds, lats, records = [], [], [], []
    total = 0
    for row in demo.to_dict(orient="records"):
        pmid = str(row["pmid"])
        p = parsed_by_pmid.get(pmid) or {}
        choice = p.get("choice")
        if not choice:
            continue
        total += 1
        conf = _finite(p.get("confidence"), 0.0)
        if conf < tau:
            continue
        golds.append(row["gold"])
        preds.append(choice)
        lats.append(_finite(p.get("latency_ms"), 0.0))
        records.append(
            {
                "demo_idx": row["demo_idx"],
                "pmid": pmid,
                "gold": row["gold"],
                "pred": choice,
                "confidence": conf,
                "latency_ms": lats[-1],
                "correct": choice == row["gold"],
                "variant": variant,
            }
        )
    coverage = (len(preds) / total) if total else 0.0
    if not preds:
        rowm = {
            "variant": variant,
            "n": 0,
            "accuracy": float("nan"),
            "precision_RCT": float("nan"),
            "recall_RCT": float("nan"),
            "f1_RCT": float("nan"),
            "mean_latency_ms": float("nan"),
            "tp": 0,
            "fp": 0,
            "fn": 0,
            "tn": 0,
            "coverage": 0.0,
            "tau": tau,
        }
        return rowm, pd.DataFrame(records)
    m = metrics_row(variant, golds, preds, lats, extra={"coverage": coverage, "tau": tau})
    return m, pd.DataFrame(records)


def fmt_pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{100.0 * x:.1f}%"


def fmt_ms(x: float | None) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:.0f}"


def write_table(rows: list[dict]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(TABLE_CSV, index=False)
    lines = [
        "# Jev prompt/criteria ablations (Bat4RCT demo_200)",
        "",
        "Fixed set: `data/demo_200.csv` (n=200). Baseline to beat: Acc **87.0%** / F1 **85.2%**.",
        "",
        "Score rubric mapping: levels `clearly not RCT` (0) / `ambiguous` (1) / `clearly RCT` (2); "
        f"**pred = RCT iff score ≥ {SCORE_THRESHOLD}**.",
        "",
        "| variant | Acc | F1_RCT | Prec | Rec | mean_lat_ms | coverage | notes |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        notes = []
        if "tau" in r and r["tau"] is not None and not (isinstance(r.get("tau"), float) and math.isnan(r["tau"])):
            notes.append(f"τ={r['tau']}")
        if r["variant"].startswith("score"):
            notes.append(f"score≥{SCORE_THRESHOLD}→RCT")
        if r["variant"].startswith("dual_gate"):
            notes.append("choice=RCT ∧ noul_completed≥τ")
        if r["variant"].startswith("conf_gate"):
            notes.append("among conf≥τ")
        lines.append(
            "| {v} | {a} | {f} | {p} | {r_} | {l} | {c} | {n} |".format(
                v=r["variant"],
                a=fmt_pct(r.get("accuracy")),
                f=fmt_pct(r.get("f1_RCT")),
                p=fmt_pct(r.get("precision_RCT")),
                r_=fmt_pct(r.get("recall_RCT")),
                l=fmt_ms(r.get("mean_latency_ms")),
                c=fmt_pct(r.get("coverage")),
                n="; ".join(notes) if notes else "",
            )
        )
    lines.append("")
    TABLE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {TABLE_MD} and {TABLE_CSV}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true", help="ignore cache")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    demo = load_demo()
    if args.limit is not None:
        demo = demo.head(args.limit).copy()
    api_key = load_api_key()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def state_ta(row: dict) -> str:
        return (row.get("text") or f"{row.get('title','')} {row.get('abstract','')}").strip()

    def state_title(row: dict) -> str:
        return str(row.get("title") or "").strip()

    # --- API families (parallelizable; sequential here for clearer logs) ---
    raw_baseline = run_family(
        "baseline_ta",
        demo,
        state_ta,
        questions_baseline_family(),
        api_key,
        args.workers,
        args.force,
    )
    raw_stronger = run_family(
        "stronger_ta",
        demo,
        state_ta,
        questions_stronger_family(),
        api_key,
        args.workers,
        args.force,
    )
    raw_score = run_family(
        "score_ta",
        demo,
        state_ta,
        questions_score_family(),
        api_key,
        args.workers,
        args.force,
    )

    parsed_base = {
        pmid: (
            {**parse_choice_bundle(d), "error": d.get("_error", "")}
            if not d.get("_error")
            else {"error": d["_error"], "choice": None, "latency_ms": 0.0}
        )
        for pmid, d in raw_baseline.items()
    }
    parsed_strong = {
        pmid: (
            {**parse_choice_bundle(d), "error": d.get("_error", "")}
            if not d.get("_error")
            else {"error": d["_error"], "choice": None, "latency_ms": 0.0}
        )
        for pmid, d in raw_stronger.items()
    }
    parsed_score = {
        pmid: (
            {**parse_score(d), "error": d.get("_error", "")}
            if not d.get("_error")
            else {"error": d["_error"], "pred": None, "latency_ms": 0.0}
        )
        for pmid, d in raw_score.items()
    }

    table_rows: list[dict] = []
    pred_frames: dict[str, pd.DataFrame] = {}

    # 1 baseline
    m, dfp = evaluate_choice_preds(
        "baseline", demo, parsed_base, lambda p: p["choice"]
    )
    table_rows.append(m)
    pred_frames["baseline"] = dfp

    # 2 stronger_criteria
    m, dfp = evaluate_choice_preds(
        "stronger_criteria", demo, parsed_strong, lambda p: p["choice"]
    )
    table_rows.append(m)
    pred_frames["stronger_criteria"] = dfp

    # pick best Choice for title_only questions
    best_choice = "baseline"
    if (
        math.isfinite(table_rows[1]["accuracy"])
        and math.isfinite(table_rows[0]["accuracy"])
        and (
            table_rows[1]["accuracy"] > table_rows[0]["accuracy"]
            or (
                table_rows[1]["accuracy"] == table_rows[0]["accuracy"]
                and table_rows[1]["f1_RCT"] > table_rows[0]["f1_RCT"]
            )
        )
    ):
        best_choice = "stronger_criteria"
    print(f"Best Choice so far for title_only: {best_choice}", flush=True)

    # 3 dual_gate sweeps (baseline Choice + completed-human noul)
    for tau in (0.5, 0.6, 0.7, 0.8):

        def pred_fn(p: dict, t=tau) -> str:
            noul = _finite(p.get("noul_completed"))
            if p.get("choice") == LABEL_RCT and math.isfinite(noul) and noul >= t:
                return LABEL_RCT
            return LABEL_NON

        m, dfp = evaluate_choice_preds(f"dual_gate_τ={tau}", demo, parsed_base, pred_fn)
        m["tau"] = tau
        table_rows.append(m)
        pred_frames[f"dual_gate_{tau}"] = dfp

    # 4 score_rubric
    golds, preds, lats, records = [], [], [], []
    for row in demo.to_dict(orient="records"):
        pmid = str(row["pmid"])
        p = parsed_score.get(pmid) or {}
        pred = p.get("pred")
        if not pred:
            continue
        golds.append(row["gold"])
        preds.append(pred)
        lats.append(_finite(p.get("latency_ms"), 0.0))
        records.append(
            {
                "demo_idx": row["demo_idx"],
                "pmid": pmid,
                "gold": row["gold"],
                "pred": pred,
                "score": p.get("score"),
                "confidence": p.get("confidence"),
                "latency_ms": lats[-1],
                "correct": pred == row["gold"],
                "variant": "score_rubric",
            }
        )
    m = metrics_row("score_rubric", golds, preds, lats, extra={"score_threshold": SCORE_THRESHOLD})
    table_rows.append(m)
    pred_frames["score_rubric"] = pd.DataFrame(records)

    # 5 title_only (best Choice questions)
    title_family = "title_only_stronger" if best_choice == "stronger_criteria" else "title_only_baseline"
    title_qs = (
        questions_stronger_family()
        if best_choice == "stronger_criteria"
        else questions_baseline_family()
    )
    raw_title = run_family(
        title_family,
        demo,
        state_title,
        title_qs,
        api_key,
        args.workers,
        args.force,
    )
    parsed_title = {
        pmid: (
            {**parse_choice_bundle(d), "error": d.get("_error", "")}
            if not d.get("_error")
            else {"error": d["_error"], "choice": None, "latency_ms": 0.0}
        )
        for pmid, d in raw_title.items()
    }
    m, dfp = evaluate_choice_preds(
        "title_only", demo, parsed_title, lambda p: p["choice"]
    )
    m["notes_choice"] = best_choice
    table_rows.append(m)
    pred_frames["title_only"] = dfp

    # 6 title_abstract (= baseline Choice on title+abstract; confirm)
    m, dfp = evaluate_choice_preds(
        "title_abstract", demo, parsed_base, lambda p: p["choice"]
    )
    table_rows.append(m)
    pred_frames["title_abstract"] = dfp

    # 7 conf_gate sweeps
    for tau in (0.5, 0.6, 0.7, 0.8):
        m, dfp = evaluate_conf_gate(f"conf_gate_τ={tau}", demo, parsed_base, tau)
        table_rows.append(m)
        pred_frames[f"conf_gate_{tau}"] = dfp

    write_table(table_rows)

    # persist all predictions
    all_path = RESULTS_DIR / "ablations_predictions.json"
    summary = {k: df.to_dict(orient="records") for k, df in pred_frames.items()}
    all_path.write_text(json.dumps({"table": table_rows, "preds": summary}, indent=2), encoding="utf-8")

    # decide best prompt to commit (full-coverage variants only)
    candidates = [
        r
        for r in table_rows
        if r["variant"] in ("baseline", "stronger_criteria", "score_rubric", "title_abstract")
        or r["variant"].startswith("dual_gate")
    ]
    # title_only is an ablation not a default prompt replacement
    base = next(r for r in table_rows if r["variant"] == "baseline")
    best = base
    for r in candidates:
        if r["variant"] == "baseline":
            continue
        # beat Acc or F1 without catastrophic precision collapse (prec >= 0.85 or >= base-0.1)
        beats = (
            r["accuracy"] > base["accuracy"] + 1e-9
            or r["f1_RCT"] > base["f1_RCT"] + 1e-9
        )
        prec_ok = r["precision_RCT"] >= max(0.85, base["precision_RCT"] - 0.10)
        if beats and prec_ok:
            # prefer higher Acc, then F1
            if (r["accuracy"], r["f1_RCT"]) > (best["accuracy"], best["f1_RCT"]):
                best = r

    if best["variant"] == "stronger_criteria":
        commit_prompt = "stronger_criteria"
        note = "commit stronger Choice criteria into jev_client"
    elif best["variant"] == "score_rubric":
        commit_prompt = "score_rubric"
        note = "commit Score rubric into jev_client"
    elif best["variant"].startswith("dual_gate"):
        commit_prompt = None
        note = "dual_gate wins via post-process only; keep Choice prompt"
    else:
        commit_prompt = None
        note = "nothing beats baseline on Acc/F1 without precision collapse"
    decision = {
        "baseline": {k: base[k] for k in ("accuracy", "f1_RCT", "precision_RCT", "recall_RCT")},
        "best_variant": best["variant"],
        "best": {k: best[k] for k in ("accuracy", "f1_RCT", "precision_RCT", "recall_RCT", "mean_latency_ms")},
        "commit_prompt": commit_prompt,
        "note": note,
        "score_threshold": SCORE_THRESHOLD,
        "best_choice_for_title_only": best_choice,
    }

    (RESULTS_DIR / "ablations_decision.json").write_text(
        json.dumps(decision, indent=2), encoding="utf-8"
    )
    print(json.dumps(decision, indent=2), flush=True)
    print(TABLE_MD.read_text(encoding="utf-8"), flush=True)


if __name__ == "__main__":
    main()
