"""Run Jev over the 200-row demo set; write predictions + metrics."""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from .bat4rct import load_demo
from .config import METRICS_JSON, PREDICTIONS_CSV, RESULTS_DIR
from .jev_client import classify, load_api_key
from .metrics import compute_metrics


def _one(row: dict, api_key: str, dry_run: bool) -> dict:
    base = {
        "demo_idx": row["demo_idx"],
        "pmid": row["pmid"],
        "gold": row["gold"],
        "title": row["title"],
        "abstract": row["abstract"],
    }
    if dry_run:
        # heuristic stub for UI wiring without API
        text = (row.get("text") or "").lower()
        is_rct = any(k in text for k in ("randomized", "randomised", "randomly assigned", "rct"))
        pred = "RCT" if is_rct else "non_RCT"
        return {
            **base,
            "pred": pred,
            "confidence": 0.5,
            "p_RCT": 0.7 if is_rct else 0.3,
            "p_non_RCT": 0.3 if is_rct else 0.7,
            "noul_is_rct": 0.7 if is_rct else 0.3,
            "latency_ms": 1.0,
            "correct": pred == row["gold"],
            "error": "",
        }
    try:
        out = classify(row["text"], api_key=api_key)
        pred = out["pred"]
        return {
            **base,
            "pred": pred,
            "confidence": out["confidence"],
            "p_RCT": out["p_RCT"],
            "p_non_RCT": out["p_non_RCT"],
            "noul_is_rct": out["noul_is_rct"],
            "latency_ms": out["latency_ms"],
            "correct": pred == row["gold"],
            "error": "",
        }
    except Exception as e:  # noqa: BLE001 — keep going on single failures
        return {
            **base,
            "pred": "",
            "confidence": 0.0,
            "p_RCT": 0.0,
            "p_non_RCT": 0.0,
            "noul_is_rct": float("nan"),
            "latency_ms": 0.0,
            "correct": False,
            "error": str(e)[:300],
        }


def run(limit: int | None = None, workers: int = 4, dry_run: bool = False) -> dict:
    demo = load_demo()
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
    df.to_csv(PREDICTIONS_CSV, index=False)

    ok = df[df["pred"].astype(str).str.len() > 0]
    metrics = compute_metrics(ok["gold"], ok["pred"], ok["latency_ms"])
    metrics["wall_seconds"] = time.perf_counter() - t0
    metrics["n_errors"] = int((df["error"].astype(str).str.len() > 0).sum())
    metrics["dry_run"] = dry_run
    METRICS_JSON.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return metrics


def main() -> None:
    p = argparse.ArgumentParser(description="Run Jev on Bat4RCT demo_200")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    run(limit=args.limit, workers=args.workers, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
