"""Tiny static+API server for the screenable web UI."""
from __future__ import annotations

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .config import METRICS_JSON, PREDICTIONS_CSV, ROOT, WEB_DIR


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/predictions":
            return self._json_file(PREDICTIONS_CSV, as_csv=True)
        if path == "/api/metrics":
            return self._json_file(METRICS_JSON)
        if path == "/api/health":
            return self._json({"ok": True})
        return super().do_GET()

    def _json_file(self, path: Path, as_csv: bool = False) -> None:
        if not path.exists():
            return self._json({"error": f"missing {path.name}"}, status=404)
        if as_csv:
            import csv

            with path.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            return self._json({"rows": rows})
        return self._json(json.loads(path.read_text(encoding="utf-8")))

    def _json(self, obj, status: int = 200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        pass


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    if not PREDICTIONS_CSV.exists():
        print(f"WARN: {PREDICTIONS_CSV} missing — run: python -m src.run_eval")
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Demo UI → http://127.0.0.1:{args.port}/  (cwd web={WEB_DIR})")
    print(f"Repo root {ROOT}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
