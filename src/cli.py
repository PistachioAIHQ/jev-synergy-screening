"""Screenable CLI: criteria → abstracts → label+confidence → green/red → scoreboard."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

from .bat4rct import load_demo
from .config import BIOBERT_ACC, BIOBERT_F1, METRICS_JSON, PREDICTIONS_CSV
from .jev_client import classify, load_api_key
from .metrics import compute_metrics

GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _bar(pct: float, width: int = 28) -> str:
    n = int(round(pct * width))
    return "█" * n + "░" * (width - n)


def show_criteria() -> None:
    print(f"\n{BOLD}{CYAN}══ Jev × Bat4RCT ══{RESET}")
    print("Task: title + abstract → RCT vs non_RCT")
    print("Baseline (BioBERT, paper): F1 90.85%  Acc 96.37%")
    print(f"\n{BOLD}Screening criteria{RESET}")
    print("  RCT      — randomized allocation to intervention arms")
    print("  non_RCT  — observational / review / case / other")
    print(f"{DIM}Model: jev-latest · Choice + Noul · no free-text rationale{RESET}\n")
    time.sleep(1.2)


def film(limit: int | None, delay: float, live: bool) -> None:
    show_criteria()
    if PREDICTIONS_CSV.exists() and not live:
        df = pd.read_csv(PREDICTIONS_CSV)
        print(f"{DIM}Replaying {PREDICTIONS_CSV}{RESET}\n")
    else:
        demo = load_demo()
        if limit:
            demo = demo.head(limit)
        key = load_api_key()
        rows = []
        for _, r in demo.iterrows():
            out = classify(r["text"], api_key=key)
            rows.append(
                {
                    **r.to_dict(),
                    "pred": out["pred"],
                    "confidence": out["confidence"],
                    "noul_is_rct": out["noul_is_rct"],
                    "latency_ms": out["latency_ms"],
                    "correct": out["pred"] == r["gold"],
                }
            )
        df = pd.DataFrame(rows)

    if limit:
        df = df.head(limit)

    for _, row in df.iterrows():
        title = str(row.get("title") or "")[:110]
        pred = row["pred"]
        gold = row["gold"]
        conf = float(row.get("confidence") or 0)
        ok = bool(row.get("correct")) if "correct" in row else pred == gold
        color = GREEN if ok else RED
        mark = "✓" if ok else "✗"
        print(f"{DIM}PMID {row.get('pmid')}{RESET}")
        print(f"  {title}…")
        print(
            f"  → {BOLD}{pred}{RESET}  conf={conf:.2f}  gold={gold}  "
            f"{color}{mark}{RESET}  ({float(row.get('latency_ms') or 0):.0f} ms)"
        )
        time.sleep(delay)

    metrics = compute_metrics(df["gold"], df["pred"], df.get("latency_ms", [0] * len(df)))
    print(f"\n{BOLD}Scoreboard (n={metrics['n']}){RESET}")
    print(f"  Jev      Acc {_bar(metrics['accuracy'])} {metrics['accuracy']*100:5.2f}%")
    print(f"  BioBERT  Acc {_bar(BIOBERT_ACC)} {BIOBERT_ACC*100:5.2f}%")
    print(f"  Jev      F1  {_bar(metrics['f1_RCT'])} {metrics['f1_RCT']*100:5.2f}%")
    print(f"  BioBERT  F1  {_bar(BIOBERT_F1)} {BIOBERT_F1*100:5.2f}%")
    print(f"  mean latency {metrics['mean_latency_ms']:.0f} ms")
    if METRICS_JSON.exists():
        print(f"{DIM}Saved metrics: {METRICS_JSON}{RESET}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=12, help="Abstracts to show (film default 12)")
    p.add_argument("--delay", type=float, default=0.35)
    p.add_argument("--all", action="store_true", help="Show all 200")
    p.add_argument("--live", action="store_true", help="Call API instead of replaying CSV")
    args = p.parse_args()
    limit = None if args.all else args.limit
    film(limit=limit, delay=args.delay, live=args.live)


if __name__ == "__main__":
    main()
