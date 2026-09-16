"""Fair head-to-head: Jev vs Anthropic on stratified Cohen ADHD Abstract Triage ~100."""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from .anthropic_client import classify_anthropic, load_anthropic_key
from .cohen_adhd import NOUL_KEYS, RULE_ID, load_h2h, load_metadata
from .config import H2H_DIR, H2H_SEED, LABEL_INCLUDE
from .jev_client import classify_cohen, load_api_key
from .metrics import compute_metrics


def _jev_one(row: dict, api_key: str) -> dict:
    base = {
        "demo_idx": int(row["demo_idx"]),
        "pmid": row.get("pmid") or "",
        "gold": row["gold"],
        "title": row["title"],
        "abstract": row["abstract"],
        "system": "jev",
    }
    try:
        out = classify_cohen(row["text"], api_key=api_key)
        return {
            **base,
            "pred": out["pred"],
            "choice": out.get("choice"),
            "confidence": out.get("confidence"),
            "p_include": out.get("p_include"),
            "p_exclude": out.get("p_exclude"),
            **{k: out.get(k) for k in NOUL_KEYS},
            "latency_ms": out["latency_ms"],
            "input_tokens": out.get("input_tokens") or 0,
            "output_tokens": 0,
            "cost_usd": out.get("cost_usd") if out.get("cost_usd") is not None else 0.0,
            "model": out.get("model"),
            "rule": out.get("rule") or RULE_ID,
            "error": "",
        }
    except Exception as e:  # noqa: BLE001
        return {
            **base,
            "pred": "",
            "choice": "",
            "confidence": 0.0,
            "latency_ms": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "model": "",
            "rule": RULE_ID,
            "error": str(e)[:300],
        }


def _ant_one(row: dict, api_key: str) -> dict:
    base = {
        "demo_idx": int(row["demo_idx"]),
        "pmid": row.get("pmid") or "",
        "gold": row["gold"],
        "title": row["title"],
        "abstract": row["abstract"],
        "system": "anthropic",
    }
    try:
        out = classify_anthropic(row["title"], row["abstract"], api_key=api_key)
        return {
            **base,
            "pred": out["pred"],
            "choice": out.get("choice"),
            "confidence": out.get("confidence"),
            "latency_ms": out["latency_ms"],
            "input_tokens": out.get("input_tokens") or 0,
            "output_tokens": out.get("output_tokens") or 0,
            "cost_usd": out.get("cost_usd") or 0.0,
            "model": out.get("model"),
            "rule": out.get("rule"),
            "error": "",
        }
    except Exception as e:  # noqa: BLE001
        return {
            **base,
            "pred": "",
            "choice": "",
            "confidence": 0.0,
            "latency_ms": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "model": "",
            "rule": "anthropic_structured_tool_include_exclude",
            "error": str(e)[:300],
        }


def _summarize(df: pd.DataFrame, system: str) -> dict:
    ok = df[df["pred"].astype(str).str.len() > 0]
    m = compute_metrics(
        ok["gold"], ok["pred"], ok["latency_ms"], positive_label=LABEL_INCLUDE, include_biobert=False
    )
    m["system"] = system
    m["n_errors"] = int((df["error"].astype(str).str.len() > 0).sum())
    m["cost_usd_sum"] = float(pd.to_numeric(ok["cost_usd"], errors="coerce").fillna(0).sum())
    m["input_tokens_total"] = float(pd.to_numeric(ok["input_tokens"], errors="coerce").fillna(0).sum())
    m["output_tokens_total"] = float(pd.to_numeric(ok.get("output_tokens"), errors="coerce").fillna(0).sum())
    models = ok["model"].dropna().astype(str)
    models = models[models.str.len() > 0]
    m["model"] = models.mode().iloc[0] if len(models) else ""
    return m


def run(*, workers: int = 6, systems: tuple[str, ...] = ("jev", "anthropic")) -> dict:
    demo = load_h2h()
    H2H_DIR.mkdir(parents=True, exist_ok=True)
    rows = demo.to_dict(orient="records")
    summary: dict = {
        "n": len(rows),
        "seed": H2H_SEED,
        "dataset": "Cohen_2006_ADHD_Abstract_Triage",
        "gold": "Abstract Triage only (I=include)",
        "fairness": (
            "Same stratified N≈100 PMIDs (seed documented), same title+abstract, "
            "same DERP eligibility criteria text. Jev=Choice+Noul protocol; "
            "Anthropic=structured tool include|exclude (no CoT essay)."
        ),
        "prevalence": {
            "include": int((demo["gold"] == LABEL_INCLUDE).sum()),
            "exclude": int((demo["gold"] != LABEL_INCLUDE).sum()),
        },
        "review_meta": load_metadata(),
        "systems": {},
    }

    if "jev" in systems:
        print("=== Jev on H2H-100 ===", flush=True)
        key = load_api_key()
        t0 = time.perf_counter()
        out: list[dict] = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(_jev_one, r, key) for r in rows]
            done = 0
            for fut in as_completed(futs):
                out.append(fut.result())
                done += 1
                if done % 10 == 0 or done == len(rows):
                    print(f"  jev {done}/{len(rows)}", flush=True)
        out.sort(key=lambda r: r["demo_idx"])
        jdf = pd.DataFrame(out)
        jdf.to_csv(H2H_DIR / "jev_predictions.csv", index=False)
        jm = _summarize(jdf, "jev")
        jm["wall_seconds"] = time.perf_counter() - t0
        jm["rule"] = RULE_ID
        summary["systems"]["jev"] = jm
        print(json.dumps(jm, indent=2), flush=True)

    if "anthropic" in systems:
        print("=== Anthropic on H2H-100 ===", flush=True)
        key = load_anthropic_key()
        t0 = time.perf_counter()
        out = []
        aw = min(workers, 4)
        with ThreadPoolExecutor(max_workers=aw) as ex:
            futs = [ex.submit(_ant_one, r, key) for r in rows]
            done = 0
            for fut in as_completed(futs):
                out.append(fut.result())
                done += 1
                if done % 10 == 0 or done == len(rows):
                    print(f"  anthropic {done}/{len(rows)}", flush=True)
        out.sort(key=lambda r: r["demo_idx"])
        adf = pd.DataFrame(out)
        adf.to_csv(H2H_DIR / "anthropic_predictions.csv", index=False)
        am = _summarize(adf, "anthropic")
        am["wall_seconds"] = time.perf_counter() - t0
        summary["systems"]["anthropic"] = am
        print(json.dumps(am, indent=2), flush=True)

    table = []
    for name, m in summary["systems"].items():
        table.append(
            {
                "system": name,
                "n": m["n"],
                "precision": m["precision"],
                "recall": m["recall"],
                "f1": m["f1"],
                "accuracy": m["accuracy"],
                "tp": m["tp"],
                "fp": m["fp"],
                "fn": m["fn"],
                "tn": m["tn"],
                "mean_latency_ms": m["mean_latency_ms"],
                "p50_latency_ms": m["p50_latency_ms"],
                "p95_latency_ms": m["p95_latency_ms"],
                "cost_usd_sum": m["cost_usd_sum"],
                "model": m.get("model"),
            }
        )
    summary["table"] = table
    (H2H_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    pd.DataFrame(table).to_csv(H2H_DIR / "h2h_table.csv", index=False)
    print("=== H2H TABLE ===", flush=True)
    print(pd.DataFrame(table).to_string(index=False), flush=True)
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--systems", default="jev,anthropic")
    args = p.parse_args()
    systems = tuple(s.strip() for s in args.systems.split(",") if s.strip())
    run(workers=args.workers, systems=systems)


if __name__ == "__main__":
    main()
