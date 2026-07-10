"""
Mock ULI/OCEN-style presentment API. Stdlib only (http.server) - no
Flask/FastAPI dependency, so this runs on any Python 3 install without
pip installing anything, which matters for a hackathon judge's machine.

Endpoints:
  GET  /health
  GET  /uli/v1/score-card/{borrower_id}
  POST /uli/v1/consent-refresh              (body: schema.CONSENT_REFRESH_REQUEST_SCHEMA)
  GET  /uli/v1/consent-refresh/log          (demo/audit helper, not part of the "real" contract)
"""

import json
import re
import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from data_provider import ScoreCardStore
from schema import CONSENT_REFRESH_RESPONSE_SCHEMA  # noqa: F401 (documents the response shape)

SCORE_CARD_RE = re.compile(r"^/uli/v1/score-card/([A-Za-z0-9\-]+)$")

# In-memory log of consent-refresh events received - visible via GET, reset
# on server restart. This is intentionally NOT persisted - it's a demo aid,
# not a claim about production durability.
_consent_refresh_log = []


def make_handler(store: ScoreCardStore):
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, status, payload):
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass  # quiet - avoid noisy stderr during automated demo runs

        def do_GET(self):
            if self.path == "/health":
                self._send_json(200, {"status": "ok"})
                return

            m = SCORE_CARD_RE.match(self.path)
            if m:
                borrower_id = m.group(1)
                card = store.get_score_card(borrower_id)
                if card is None:
                    self._send_json(404, {"error": f"unknown borrower_id: {borrower_id}"})
                else:
                    self._send_json(200, card)
                return

            if self.path == "/uli/v1/consent-refresh/log":
                self._send_json(200, {"events": _consent_refresh_log})
                return

            self._send_json(404, {"error": "not found"})

        def do_POST(self):
            if self.path == "/uli/v1/consent-refresh":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    self._send_json(400, {"error": "invalid JSON body"})
                    return

                missing = [f for f in ("borrower_id", "consent_id", "event_type") if f not in payload]
                if missing:
                    self._send_json(400, {"error": f"missing required fields: {missing}"})
                    return

                received_at = datetime.datetime.utcnow().isoformat() + "Z"
                event = {**payload, "received_at": received_at}
                _consent_refresh_log.append(event)

                self._send_json(202, {
                    "borrower_id": payload["borrower_id"],
                    "status": "queued",
                    "received_at": received_at,
                    "note": "Logged only - this prototype does not actually trigger a "
                            "recompute. A production version would re-run Modules 1-6 "
                            "(or an incremental equivalent) for this borrower and "
                            "invalidate their cached score card.",
                })
                return

            self._send_json(404, {"error": "not found"})

    return Handler


def run_server(host, port, store: ScoreCardStore):
    handler = make_handler(store)
    httpd = HTTPServer((host, port), handler)
    return httpd
