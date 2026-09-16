"""Run Jev r3_ship over the 200-row demo set; write predictions + metrics."""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from .bat4rct import load_demo
from .config import METRICS_JSON, PREDICTIONS_CSV, RESULTS_DIR
from .hybrid import ALL_NOUL_KEYS as NOUL_KEYS
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
    empty_nouls = {k: float("nan") for k in NOUL_KEYS}
    if dry_run:
        text = (row.get("text") or "").lower()
        is_rct = any(k in text for k in ("randomized", "randomised", "randomly assigned", "rct"))
        pred = "RCT" if is_rct else "non_RCT"
        return {
            **base,
            "choice": pred,
            "pred": pred,
            "confidence": 0.5,
            "p_RCT": 0.7 if is_rct else 0.3,
            "p_non_RCT": 0.3 if is_rct else 0.7,
            **{k: (0.7 if is_rct else 0.3) for k in NOUL_KEYS},
            "latency_ms": 1.0,
            "input_tokens": "",
            "input_tokens_est": "",
            "correct": pred == row["gold"],
            "error": "",
            "rule": "r3_ship_cd_choice_plus_reports_exp095",
        }
    try:
        out = classify(row["text"], api_key=api_key)
        pred = out["pred"]
        return {
            **base,
            "choice": out.get("choice"),
            "pred": pred,
            "confidence": out["confidence"],
            "p_RCT": out["p_RCT"],
            "p_non_RCT": out["p_non_RCT"],
            **{k: out.get(k) for k in NOUL_KEYS},
            "latency_ms": out["latency_ms"],
            "input_tokens": (out.get("input_tokens")
                if out.get("input_tokens") is not None
                else (out.get("usage") or {}).get("input_tokens")),
            "input_tokens_est": "",
            "correct": pred == row["gold"],
            "error": "",
            "rule": out.get("rule") or "r3_ship_cd_choice_plus_reports_exp095",
        }
    except Exception as e:  # noqa: BLE001
        return {
            **base,
            "choice": "",
            "pred": "",
            "confidence": 0.0,
            "p_RCT": 0.0,
            "p_non_RCT": 0.0,
            **empty_nouls,
            "latency_ms": 0.0,
            "input_tokens": "",
            "input_tokens_est": "",
            "correct": False,
            "error": str(e)[:300],
            "rule": "r3_ship_cd_choice_plus_reports_exp095",
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
    metrics["rule"] = "r3_ship_cd_choice_plus_reports_exp095"
    metrics["aggressive"] = False
    metrics["exp_threshold"] = 0.95
    METRICS_JSON.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return metrics


def main() -> None:
    p = argparse.ArgumentParser(description="Run r3_ship Jev on Bat4RCT demo_200")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    run(limit=args.limit, workers=args.workers, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
