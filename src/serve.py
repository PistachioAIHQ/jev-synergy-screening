"""Tiny static+API server for the screenable web UI (v2: grid + live hybrid classify)."""
from __future__ import annotations

import argparse
import csv
import json
import math
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .config import DEMO_CSV, METRICS_JSON, PREDICTIONS_CSV, ROOT, WEB_DIR
from .hybrid import NOUL_KEYS
from .jev_client import classify, load_api_key


def _finite(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/demo":
            return self._demo()
        if path == "/api/predictions":
            return self._json_file(PREDICTIONS_CSV, as_csv=True)
        if path == "/api/metrics":
            return self._json_file(METRICS_JSON)
        if path == "/api/health":
            return self._json({"ok": True, "ui": "v2", "rule": "hybrid_cd_choice_plus_r2_nouls"})
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/classify":
            return self._classify()
        return self._json({"error": "not found"}, status=404)

    def _demo(self) -> None:
        if not DEMO_CSV.exists():
            return self._json({"error": f"missing {DEMO_CSV.name}"}, status=404)
        rows = []
        with DEMO_CSV.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append(
                    {
                        "demo_idx": int(r.get("demo_idx") or 0),
                        "pmid": r.get("pmid") or "",
                        "title": r.get("title") or "",
                        "abstract": r.get("abstract") or "",
                        "gold": r.get("gold") or "",
                    }
                )
        return self._json({"rows": rows, "n": len(rows)})

    def _classify(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return self._json({"error": "invalid JSON"}, status=400)

        title = (body.get("title") or "").strip()
        abstract = (body.get("abstract") or "").strip()
        pmid = str(body.get("pmid") or "").strip()
        text = (body.get("text") or "").strip()
        if not text:
            text = f"{title} {abstract}".strip()
        if not text:
            return self._json({"error": "title/abstract or text required"}, status=400)

        try:
            load_api_key()
        except RuntimeError as e:
            return self._json({"error": str(e)}, status=503)

        try:
            out = classify(text)
        except Exception as e:  # noqa: BLE001
            return self._json({"error": str(e), "pmid": pmid}, status=502)

        nouls = {k: _finite(out.get(k)) for k in NOUL_KEYS}
        return self._json(
            {
                "pmid": pmid,
                "pred": out.get("pred"),
                "choice": out.get("choice"),
                "confidence": out.get("confidence"),
                "probabilities": out.get("probabilities")
                or {
                    "RCT": out.get("p_RCT"),
                    "non_RCT": out.get("p_non_RCT"),
                },
                "p_RCT": out.get("p_RCT"),
                "p_non_RCT": out.get("p_non_RCT"),
                **nouls,
                "answers": out.get("answers"),
                "latency_ms": out.get("latency_ms"),
                "model": out.get("model"),
                "rule": out.get("rule") or "hybrid_cd_choice_plus_r2_nouls",
                "aggressive": False,
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
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        pass


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    if not DEMO_CSV.exists():
        print(f"WARN: {DEMO_CSV} missing — run: python -m src.prepare_demo")
    if not PREDICTIONS_CSV.exists():
        print(f"WARN: {PREDICTIONS_CSV} missing — Replay cached needs: python -m src.run_eval")
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Demo UI v2 (hybrid) → http://127.0.0.1:{args.port}/  (cwd web={WEB_DIR})")
    print(f"Repo root {ROOT}")
    print("GET /api/demo · POST /api/classify · GET /api/predictions (replay)")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
