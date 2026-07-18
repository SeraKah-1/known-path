#!/usr/bin/env python3
"""Lightweight DataHub-like GMS stand-in for local tool testing.

NOT production DataHub — implements just enough for known-path:
  GET  /health
  GET  /config
  POST /api/graphql  (search + minimal dataset fields)
  Bearer PAT auth (optional; default token printed on start)

Use when Docker quickstart is unavailable (e.g. Android/PRoot).
"""

from __future__ import annotations

import json
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Allow importing known_path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from known_path.fixtures import demo_catalog  # noqa: E402

HOST = "127.0.0.1"
PORT = 8080
# Fixed demo token so settings can be filled deterministically
DEFAULT_TOKEN = "dh_pat_" + "knownpath_demo_token_local_only_do_not_use_prod"


def _assets_as_search_results():
    results = []
    for a in demo_catalog():
        results.append(
            {
                "entity": {
                    "urn": a.urn,
                    "type": "DATASET",
                    "name": a.name,
                    "platform": {"name": a.platform},
                    "properties": {"description": a.description},
                    "tags": {
                        "tags": [{"tag": {"name": t}} for t in a.tags]
                    },
                }
            }
        )
    return results


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print("[mini-gms]", fmt % args)

    def _auth_ok(self) -> bool:
        auth = self.headers.get("Authorization") or ""
        if not auth:
            # allow unauthenticated health/config; graphql requires token if present
            return True
        if auth.lower().startswith("bearer "):
            tok = auth.split(" ", 1)[1].strip()
            return tok == DEFAULT_TOKEN or tok.startswith("dh_pat_")
        return False

    def _send(self, code: int, obj: dict | list | str, ctype: str = "application/json") -> None:
        if isinstance(obj, (dict, list)):
            body = json.dumps(obj).encode("utf-8")
        else:
            body = str(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/health/"):
            self._send(200, {"status": "UP", "components": {"mini_gms": "UP"}})
            return
        if path in ("/config", "/config/"):
            self._send(
                200,
                {
                    "datahub": {
                        "serverType": "mini-gms-demo",
                        "version": "0.0.1-local",
                        "managedIngestion": {"defaultCliVersion": "n/a"},
                    },
                    "note": "Stand-in for local testing without Docker quickstart",
                },
            )
            return
        if path.startswith("/entities/"):
            if not self._auth_ok():
                self._send(401, {"error": "unauthorized"})
                return
            urn = path[len("/entities/") :]
            for a in demo_catalog():
                if a.urn == urn or a.urn.replace(":", "%3A") == urn:
                    self._send(200, {"urn": a.urn, "name": a.name, "description": a.description})
                    return
            self._send(404, {"error": "not found"})
            return
        self._send(404, {"error": "not found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8") if n else "{}"
        try:
            body = json.loads(raw or "{}")
        except json.JSONDecodeError:
            body = {}

        if path in ("/api/graphql", "/graphql"):
            auth = self.headers.get("Authorization") or ""
            if not auth.lower().startswith("bearer "):
                self._send(401, {"errors": [{"message": "Authorization Bearer token required"}]})
                return
            tok = auth.split(" ", 1)[1].strip()
            if tok != DEFAULT_TOKEN and not tok.startswith("dh_pat_"):
                self._send(401, {"errors": [{"message": "Invalid token"}]})
                return
            # Return search results regardless of query text — enough for known-path client
            payload = {
                "data": {
                    "search": {
                        "searchResults": _assets_as_search_results(),
                    }
                }
            }
            self._send(200, payload)
            return

        self._send(404, {"error": "not found", "path": path})


def main() -> None:
    port = PORT
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    httpd = ThreadingHTTPServer((HOST, port), Handler)
    print("=" * 60)
    print("mini-gms (DataHub stand-in for known-path testing)")
    print(f"  GMS URL : http://{HOST}:{port}")
    print(f"  PAT     : {DEFAULT_TOKEN}")
    print("  UI      : (none — use known-path workbench)")
    print("  NOT full DataHub — no Kafka/MySQL/OpenSearch")
    print("=" * 60)
    print("Workbench settings:")
    print(f"  GMS URL = http://{HOST}:{port}")
    print(f"  PAT     = {DEFAULT_TOKEN}")
    print("  Use live DataHub = ON")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
