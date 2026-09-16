"""Run Jev on Cohen ADHD Abstract Triage; write results/predictions.csv + metrics.json."""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from .cohen_adhd import NOUL_KEYS, RULE_ID, load_demo, load_film, load_metadata
from .config import LABEL_INCLUDE, METRICS_JSON, PREDICTIONS_CSV, RESULTS_DIR
from .jev_client import classify_cohen, load_api_key
from .metrics import compute_metrics


def _one(row: dict, api_key: str, dry_run: bool) -> dict:
    base = {
        "demo_idx": int(row["demo_idx"]),
        "record_id": row.get("record_id") or row.get("pmid") or "",
        "pmid": row.get("pmid") or "",
        "gold": row["gold"],
        "title": row["title"],
        "abstract": row["abstract"],
        "abs_triage": row.get("abs_triage") or "",
        "abs_reason": row.get("abs_reason") or "",
    }
    empty = {k: float("nan") for k in NOUL_KEYS}
    if dry_run:
        text = (row.get("text") or "").lower()
        hit = ("adhd" in text or "attention deficit" in text) and (
            "methylphenidate" in text or "amphetamine" in text or "atomoxetine" in text
        )
        pred = LABEL_INCLUDE if hit else "exclude"
        return {
            **base,
            "choice": pred,
            "pred": pred,
            "confidence": 0.55,
            "p_include": 0.7 if hit else 0.3,
            "p_exclude": 0.3 if hit else 0.7,
            **{k: (0.7 if hit else 0.3) for k in NOUL_KEYS},
            "latency_ms": 1.0,
            "input_tokens": "",
            "cost_usd": "",
            "correct": pred == row["gold"],
            "error": "",
            "rule": RULE_ID,
        }
    try:
        out = classify_cohen(row["text"], api_key=api_key)
        pred = out["pred"]
        return {
            **base,
            "choice": out.get("choice"),
            "pred": pred,
            "confidence": out["confidence"],
            "p_include": out["p_include"],
            "p_exclude": out["p_exclude"],
            **{k: out.get(k) for k in NOUL_KEYS},
            "latency_ms": out["latency_ms"],
            "input_tokens": out.get("input_tokens") or "",
            "cost_usd": out.get("cost_usd") if out.get("cost_usd") is not None else "",
            "correct": pred == row["gold"],
            "error": "",
            "rule": out.get("rule") or RULE_ID,
        }
    except Exception as e:  # noqa: BLE001
        return {
            **base,
            "choice": "",
            "pred": "",
            "confidence": 0.0,
            "p_include": 0.0,
            "p_exclude": 0.0,
            **empty,
            "latency_ms": 0.0,
            "input_tokens": "",
            "cost_usd": "",
            "correct": False,
            "error": str(e)[:300],
            "rule": RULE_ID,
        }


def run(
    *,
    subset: str = "full",
    limit: int | None = None,
    workers: int = 8,
    dry_run: bool = False,
    out_csv: Path | None = None,
    out_metrics: Path | None = None,
) -> dict:
    demo = load_film() if subset == "film" else load_demo()
    if limit is not None:
        demo = demo.head(limit).copy()
    api_key = None if dry_run else load_api_key()
    rows = demo.to_dict(orient="records")
    results: list[dict] = []
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_one, r, api_key or "", dry_run): r["demo_idx"] for r in rows}
        done = 0
        for fut in as_completed(futs):
            results.append(fut.result())
            done += 1
            if done % 10 == 0 or done == len(rows):
                print(f"  {done}/{len(rows)} …", flush=True)
    results.sort(key=lambda r: r["demo_idx"])
    df = pd.DataFrame(results)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    pred_path = out_csv or PREDICTIONS_CSV
    met_path = out_metrics or METRICS_JSON
    df.to_csv(pred_path, index=False)

    ok = df[df["pred"].astype(str).str.len() > 0]
    metrics = compute_metrics(
        ok["gold"], ok["pred"], ok["latency_ms"], positive_label=LABEL_INCLUDE, include_biobert=False
    )
    metrics["wall_seconds"] = time.perf_counter() - t0
    metrics["n_errors"] = int((df["error"].astype(str).str.len() > 0).sum())
    metrics["dry_run"] = dry_run
    metrics["rule"] = RULE_ID
    metrics["mode"] = "cohen"
    metrics["subset"] = subset
    metrics["dataset"] = "Cohen_2006_ADHD_Abstract_Triage"
    metrics["review_meta"] = load_metadata()
    metrics["fairness"] = (
        "Gold = Abstract Triage (I=include). Evidence = MEDLINE title+abstract via PMID. "
        "Never Article Triage / full-text labels."
    )
    toks = pd.to_numeric(ok.get("input_tokens"), errors="coerce")
    if toks.notna().any():
        total_tok = float(toks.sum())
        metrics["input_tokens_total"] = total_tok
        metrics["cost_usd_est"] = total_tok * 0.042 / 1_000_000.0
    metrics["wss95_footnote"] = (
        "Cohen 2006 reported WSS@95 as a historical screening-workload metric; "
        "this demo headlines Prec/Rec/F1 on include + confusion + $ + latency."
    )
    met_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return metrics


def main() -> None:
    p = argparse.ArgumentParser(description="Jev × Cohen ADHD Abstract Triage")
    p.add_argument("--subset", choices=["full", "film"], default="full")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out-csv", type=Path, default=None)
    p.add_argument("--out-metrics", type=Path, default=None)
    args = p.parse_args()
    run(
        subset=args.subset,
        limit=args.limit,
        workers=args.workers,
        dry_run=args.dry_run,
        out_csv=args.out_csv,
        out_metrics=args.out_metrics,
    )


if __name__ == "__main__":
    main()
