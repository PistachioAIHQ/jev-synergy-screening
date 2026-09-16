from __future__ import annotations

from typing import Iterable

from .config import BIOBERT_ACC, BIOBERT_F1, LABEL_RCT


def compute_metrics(golds: Iterable[str], preds: Iterable[str], latencies_ms: Iterable[float]) -> dict:
    golds = list(golds)
    preds = list(preds)
    lats = list(latencies_ms)
    n = len(golds)
    if n == 0:
        raise ValueError("empty")
    correct = sum(g == p for g, p in zip(golds, preds))
    acc = correct / n

    tp = sum(g == LABEL_RCT and p == LABEL_RCT for g, p in zip(golds, preds))
    fp = sum(g != LABEL_RCT and p == LABEL_RCT for g, p in zip(golds, preds))
    fn = sum(g == LABEL_RCT and p != LABEL_RCT for g, p in zip(golds, preds))
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    mean_lat = sum(lats) / len(lats) if lats else 0.0

    return {
        "n": n,
        "accuracy": acc,
        "precision_RCT": prec,
        "recall_RCT": rec,
        "f1_RCT": f1,
        "mean_latency_ms": mean_lat,
        "biobert_accuracy": BIOBERT_ACC,
        "biobert_f1": BIOBERT_F1,
        "delta_acc_vs_biobert": acc - BIOBERT_ACC,
        "delta_f1_vs_biobert": f1 - BIOBERT_F1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": sum(g != LABEL_RCT and p != LABEL_RCT for g, p in zip(golds, preds)),
    }
