from __future__ import annotations

from typing import Iterable

from .config import BIOBERT_ACC, BIOBERT_F1, LABEL_INCLUDE, LABEL_RCT


def _percentile(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def compute_metrics(
    golds: Iterable[str],
    preds: Iterable[str],
    latencies_ms: Iterable[float],
    *,
    positive_label: str = LABEL_RCT,
    include_biobert: bool = True,
) -> dict:
    golds = list(golds)
    preds = list(preds)
    lats = [float(x) for x in latencies_ms]
    n = len(golds)
    if n == 0:
        raise ValueError("empty")
    correct = sum(g == p for g, p in zip(golds, preds))
    acc = correct / n

    pos = positive_label
    tp = sum(g == pos and p == pos for g, p in zip(golds, preds))
    fp = sum(g != pos and p == pos for g, p in zip(golds, preds))
    fn = sum(g == pos and p != pos for g, p in zip(golds, preds))
    tn = sum(g != pos and p != pos for g, p in zip(golds, preds))
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    mean_lat = sum(lats) / len(lats) if lats else 0.0

    out = {
        "n": n,
        "accuracy": acc,
        "positive_label": pos,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "mean_latency_ms": mean_lat,
        "p50_latency_ms": _percentile(lats, 50),
        "p95_latency_ms": _percentile(lats, 95),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }
    out["precision_RCT"] = prec if pos == LABEL_RCT else None
    out["recall_RCT"] = rec if pos == LABEL_RCT else None
    out["f1_RCT"] = f1 if pos == LABEL_RCT else None
    if pos == LABEL_INCLUDE:
        out["precision_include"] = prec
        out["recall_include"] = rec
        out["f1_include"] = f1
    if include_biobert and pos == LABEL_RCT:
        out["biobert_accuracy"] = BIOBERT_ACC
        out["biobert_f1"] = BIOBERT_F1
        out["delta_acc_vs_biobert"] = acc - BIOBERT_ACC
        out["delta_f1_vs_biobert"] = f1 - BIOBERT_F1
    return out
