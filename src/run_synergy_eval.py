"""Run Jev on Donners_2021 SYNERGY set; write results/predictions.csv + metrics.json."""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from .config import LABEL_INCLUDE, METRICS_JSON, PREDICTIONS_CSV, RESULTS_DIR
from .jev_client import classify_synergy, load_api_key
from .metrics import compute_metrics
from .synergy_screening import NOUL_KEYS, RULE_ID, load_demo, load_metadata


def _one(row: dict, api_key: str, dry_run: bool) -> dict:
    base = {
        "demo_idx": int(row["demo_idx"]),
        "record_id": row.get("record_id") or "",
        "pmid": row.get("record_id") or "",  # UI reuses pmid field as id
        "doi": row.get("doi") or "",
        "gold": row["gold"],
        "title": row["title"],
        "abstract": row["abstract"],
        "label_included": int(row.get("label_included") or (1 if row["gold"] == LABEL_INCLUDE else 0)),
    }
    empty_nouls = {k: float("nan") for k in NOUL_KEYS}
    if dry_run:
        text = (row.get("text") or "").lower()
        hit = ("emicizumab" in text or "ace910" in text or "hemlibra" in text) and (
            "pharmacokinet" in text or "pk/" in text or "pk-pd" in text or "pkpd" in text
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
            "input_tokens_est": "",
            "correct": pred == row["gold"],
            "error": "",
            "rule": RULE_ID,
        }
    try:
        out = classify_synergy(row["text"], api_key=api_key)
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
            "input_tokens": (
                out.get("input_tokens")
                if out.get("input_tokens") is not None
                else (out.get("usage") or {}).get("input_tokens")
            ),
            "input_tokens_est": "",
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
            **empty_nouls,
            "latency_ms": 0.0,
            "input_tokens": "",
            "input_tokens_est": "",
            "correct": False,
            "error": str(e)[:300],
            "rule": RULE_ID,
        }


def run(limit: int | None = None, workers: int = 8, dry_run: bool = False) -> dict:
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
    metrics = compute_metrics(
        ok["gold"], ok["pred"], ok["latency_ms"], positive_label=LABEL_INCLUDE, include_biobert=False
    )
    metrics["wall_seconds"] = time.perf_counter() - t0
    metrics["n_errors"] = int((df["error"].astype(str).str.len() > 0).sum())
    metrics["dry_run"] = dry_run
    metrics["rule"] = RULE_ID
    metrics["mode"] = "synergy"
    metrics["review"] = "Donners_2021"
    metrics["review_meta"] = load_metadata()
    # cost estimate
    toks = pd.to_numeric(ok.get("input_tokens"), errors="coerce")
    if toks.notna().any():
        total_tok = float(toks.sum())
        metrics["input_tokens_total"] = total_tok
        metrics["cost_usd_est"] = total_tok * 0.042 / 1_000_000.0
    METRICS_JSON.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return metrics


def main() -> None:
    p = argparse.ArgumentParser(description="Run Jev on SYNERGY Donners_2021 (default film path)")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    run(limit=args.limit, workers=args.workers, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
