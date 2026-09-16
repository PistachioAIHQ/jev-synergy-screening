"""Static+API server — default SYNERGY Donners; optional Bat4RCT r3_ship mode."""
from __future__ import annotations

import argparse
import csv
import json
import math
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import (
    BAT4RCT_METRICS_JSON,
    BAT4RCT_PREDICTIONS_CSV,
    DEMO_CSV,
    DONNERS_CSV,
    METRICS_JSON,
    PREDICTIONS_CSV,
    ROOT,
    WEB_DIR,
)
from .hybrid import ALL_NOUL_KEYS as BAT_NOUL_KEYS
from .hybrid import build_round3_questions, hybrid_combine
from .jev_client import classify, load_api_key
from .synergy_screening import (
    COMBINE_TEXT as SYNERGY_COMBINE,
    NOUL_KEYS as SYNERGY_NOUL_KEYS,
    RULE_ID as SYNERGY_RULE,
    build_questions as build_synergy_questions,
    load_metadata,
)

INPUT_USD_PER_MTOK = 0.042
OUTPUT_USD_PER_MTOK = 0.0
BAT_RULE = "r3_ship_cd_choice_plus_reports_exp095"
BAT_COMBINE = (
    "RCT iff choice==RCT "
    "OR ((rand|cluster|parallel)>=0.5 AND secondary<0.5 AND protocol<0.5) "
    "OR (reports>=0.5 AND review<0.5) "
    "OR (experimental_allocation_implied>=0.95 AND secondary<0.5 AND protocol<0.5 AND review<0.5)"
)


def _finite(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def _cost_usd(input_tokens: float | int | None) -> float | None:
    if input_tokens is None:
        return None
    try:
        return float(input_tokens) * INPUT_USD_PER_MTOK / 1_000_000.0
    except (TypeError, ValueError):
        return None


def _mode_from_path(path: str, query: dict) -> str:
    q = (query.get("mode") or ["synergy"])[0].strip().lower()
    if q in ("bat4rct", "bat", "medline", "rct"):
        return "bat4rct"
    return "synergy"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        mode = _mode_from_path(path, query)
        if path == "/api/demo":
            return self._demo(mode)
        if path == "/api/predictions":
            return self._predictions(mode)
        if path == "/api/metrics":
            return self._metrics(mode)
        if path == "/api/questions":
            return self._questions(mode)
        if path == "/api/health":
            meta = load_metadata()
            return self._json(
                {
                    "ok": True,
                    "ui": "v3-synergy",
                    "default_mode": "synergy",
                    "modes": ["synergy", "bat4rct"],
                    "synergy_review": meta.get("review"),
                    "synergy_rule": SYNERGY_RULE,
                    "bat4rct_rule": BAT_RULE,
                    "input_usd_per_mtok": INPUT_USD_PER_MTOK,
                    "output_usd_per_mtok": OUTPUT_USD_PER_MTOK,
                }
            )
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/classify":
            return self._classify()
        return self._json({"error": "not found"}, status=404)

    def _demo(self, mode: str) -> None:
        if mode == "bat4rct":
            csv_path = DEMO_CSV
            if not csv_path.exists():
                return self._json({"error": f"missing {csv_path.name}"}, status=404)
            rows = []
            with csv_path.open(encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    rows.append(
                        {
                            "demo_idx": int(r.get("demo_idx") or 0),
                            "pmid": r.get("pmid") or "",
                            "record_id": r.get("pmid") or "",
                            "title": r.get("title") or "",
                            "abstract": r.get("abstract") or "",
                            "gold": r.get("gold") or "",
                        }
                    )
            return self._json(
                {
                    "mode": "bat4rct",
                    "task": "MEDLINE publication-type RCT tagging",
                    "rows": rows,
                    "n": len(rows),
                    "positive_label": "RCT",
                }
            )

        csv_path = DONNERS_CSV
        if not csv_path.exists():
            return self._json({"error": f"missing {csv_path.name}"}, status=404)
        meta = load_metadata()
        rows = []
        with csv_path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rid = r.get("record_id") or r.get("openalex_id") or ""
                rows.append(
                    {
                        "demo_idx": int(r.get("demo_idx") or 0),
                        "pmid": rid,
                        "record_id": rid,
                        "doi": r.get("doi") or "",
                        "title": r.get("title") or "",
                        "abstract": r.get("abstract") or "",
                        "gold": r.get("gold") or "",
                        "label_included": r.get("label_included"),
                    }
                )
        return self._json(
            {
                "mode": "synergy",
                "task": "ASReview SYNERGY human systematic-review screening",
                "review": meta.get("review"),
                "review_title": meta.get("publication_title"),
                "eligibility_criteria": meta.get("eligibility_criteria"),
                "why": meta.get("why"),
                "rows": rows,
                "n": len(rows),
                "positive_label": "include",
                "n_included": meta.get("n_included"),
            }
        )

    def _questions(self, mode: str) -> None:
        if mode == "bat4rct":
            qs = build_round3_questions()
            rule, combine = BAT_RULE, BAT_COMBINE
        else:
            qs = build_synergy_questions()
            rule, combine = SYNERGY_RULE, SYNERGY_COMBINE
        items = []
        for qid, q in qs.items():
            items.append(
                {
                    "id": qid,
                    "type": q.get("type"),
                    "instructions": q.get("instructions") or "",
                    "criteria": q.get("criteria") or {},
                }
            )
        payload = {
            "mode": mode,
            "rule": rule,
            "combine": combine,
            "questions": items,
            "input_usd_per_mtok": INPUT_USD_PER_MTOK,
            "output_usd_per_mtok": OUTPUT_USD_PER_MTOK,
        }
        if mode == "synergy":
            payload["review"] = load_metadata()
        return self._json(payload)

    def _predictions(self, mode: str) -> None:
        path = BAT4RCT_PREDICTIONS_CSV if mode == "bat4rct" else PREDICTIONS_CSV
        return self._json_file(path, as_csv=True)

    def _metrics(self, mode: str) -> None:
        path = BAT4RCT_METRICS_JSON if mode == "bat4rct" else METRICS_JSON
        return self._json_file(path)

    def _classify(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return self._json({"error": "invalid JSON"}, status=400)

        mode = (body.get("mode") or "synergy").strip().lower()
        if mode in ("bat", "medline", "rct"):
            mode = "bat4rct"
        if mode not in ("synergy", "bat4rct"):
            mode = "synergy"

        title = (body.get("title") or "").strip()
        abstract = (body.get("abstract") or "").strip()
        pmid = str(body.get("pmid") or body.get("record_id") or "").strip()
        text = (body.get("text") or "").strip()
        if not text:
            text = f"{title}\n\n{abstract}".strip()
        if not text:
            return self._json({"error": "title/abstract or text required"}, status=400)

        try:
            load_api_key()
        except RuntimeError as e:
            return self._json({"error": str(e)}, status=503)

        try:
            out = classify(text, mode=mode)
        except Exception as e:  # noqa: BLE001
            return self._json({"error": str(e), "pmid": pmid, "mode": mode}, status=502)

        usage = out.get("usage") if isinstance(out.get("usage"), dict) else {}
        input_tokens = out.get("input_tokens")
        if input_tokens is None and usage:
            input_tokens = usage.get("input_tokens")

        if mode == "bat4rct":
            nouls = {k: _finite(out.get(k)) for k in BAT_NOUL_KEYS}
            return self._json(
                {
                    "mode": mode,
                    "pmid": pmid,
                    "pred": out.get("pred"),
                    "choice": out.get("choice"),
                    "confidence": out.get("confidence"),
                    "probabilities": out.get("probabilities"),
                    "p_RCT": out.get("p_RCT"),
                    "p_non_RCT": out.get("p_non_RCT"),
                    **nouls,
                    "answers": out.get("answers"),
                    "latency_ms": out.get("latency_ms"),
                    "model": out.get("model"),
                    "usage": usage or None,
                    "input_tokens": input_tokens,
                    "cost_usd": _cost_usd(input_tokens),
                    "rule": out.get("rule") or BAT_RULE,
                }
            )

        nouls = {k: _finite(out.get(k)) for k in SYNERGY_NOUL_KEYS}
        return self._json(
            {
                "mode": mode,
                "pmid": pmid,
                "pred": out.get("pred"),
                "choice": out.get("choice"),
                "confidence": out.get("confidence"),
                "probabilities": out.get("probabilities"),
                "p_include": out.get("p_include"),
                "p_exclude": out.get("p_exclude"),
                **nouls,
                "answers": out.get("answers"),
                "latency_ms": out.get("latency_ms"),
                "model": out.get("model"),
                "usage": usage or None,
                "input_tokens": input_tokens,
                "cost_usd": _cost_usd(input_tokens),
                "rule": out.get("rule") or SYNERGY_RULE,
            }
        )

    def _json_file(self, path: Path, as_csv: bool = False) -> None:
        if not path.exists():
            return self._json({"error": f"missing {path.name}"}, status=404)
        if as_csv:
            with path.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            return self._json({"rows": rows})
        return self._json(json.loads(path.read_text(encoding="utf-8")))

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, obj, status: int = 200) -> None:
        body = json.dumps(obj, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(body.__len__()))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        pass


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    if not DONNERS_CSV.exists():
        print(f"WARN: {DONNERS_CSV} missing — SYNERGY mode needs data/donners_258.csv")
    if not PREDICTIONS_CSV.exists():
        print(f"WARN: {PREDICTIONS_CSV} missing — Replay cached needs film cache (run run_synergy_eval)")
    if not DEMO_CSV.exists():
        print(f"WARN: {DEMO_CSV} missing — Bat4RCT optional mode unavailable until prepare_demo")
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Demo UI (SYNERGY default · Bat4RCT optional) → http://127.0.0.1:{args.port}/")
    print(f"Repo root {ROOT}")
    print("GET /api/demo?mode=synergy|bat4rct · /api/questions · POST /api/classify · /api/predictions")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
