"""
Mock ULI/OCEN-style presentment API. Stdlib only (http.server) - no
Flask/FastAPI dependency, so this runs on any Python 3 install without
pip installing anything, which matters for a hackathon judge's machine.

Endpoints:
  GET  /health
  GET  /uli/v1/score-card/{borrower_id}
  POST /uli/v1/consent-refresh                          (body: schema.CONSENT_REFRESH_REQUEST_SCHEMA)
  GET  /uli/v1/consent-refresh/log                       (demo/audit helper, not part of the "real" contract)
  POST /uli/v1/score-card/{borrower_id}/applicant-inputs (body: schema.APPLICANT_INPUT_REQUEST_SCHEMA)
  GET  /uli/v1/applicant-inputs/log                      (demo/audit helper)
  POST /uli/v1/score-card/{borrower_id}/override         (body: schema.OVERRIDE_REQUEST_SCHEMA)
  GET  /uli/v1/override/log                              (demo/audit helper - server-side counterpart to
                                                            Module 6 dashboard's client-side override log)

The new applicant-inputs and override endpoints follow the EXACT same
pattern as consent-refresh: logged only, in-memory, does NOT trigger a
live recompute - same honesty caveat, not a new one invented for them.
"""

import json
import re
import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from data_provider import ScoreCardStore
from schema import CONSENT_REFRESH_RESPONSE_SCHEMA  # noqa: F401 (documents the response shape)

SCORE_CARD_RE = re.compile(r"^/uli/v1/score-card/([A-Za-z0-9\-]+)$")
APPLICANT_INPUTS_RE = re.compile(r"^/uli/v1/score-card/([A-Za-z0-9\-]+)/applicant-inputs$")
OVERRIDE_RE = re.compile(r"^/uli/v1/score-card/([A-Za-z0-9\-]+)/override$")

# In-memory logs - visible via GET, reset on server restart. Intentionally
# NOT persisted - a demo aid, not a claim about production durability.
_consent_refresh_log = []
_applicant_inputs_log = []
_override_log = []


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

            if self.path == "/uli/v1/applicant-inputs/log":
                self._send_json(200, {"events": _applicant_inputs_log})
                return

            if self.path == "/uli/v1/override/log":
                self._send_json(200, {"events": _override_log})
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

            m = APPLICANT_INPUTS_RE.match(self.path)
            if m:
                borrower_id = m.group(1)
                if not store.has_borrower(borrower_id):
                    self._send_json(404, {"error": f"unknown borrower_id: {borrower_id}"})
                    return
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    self._send_json(400, {"error": "invalid JSON body"})
                    return

                received_at = datetime.datetime.utcnow().isoformat() + "Z"
                event = {"borrower_id": borrower_id, **payload, "received_at": received_at}
                _applicant_inputs_log.append(event)

                self._send_json(202, {
                    "borrower_id": borrower_id,
                    "status": "queued",
                    "received_at": received_at,
                    "note": "Logged only - this prototype does not actually trigger a "
                            "recompute. This is the real future-user-input surface "
                            "(balance_sheet_available / projected_revenue_next_year_inr) "
                            "that Module 1 simulates across the synthetic 400-borrower "
                            "population for testing; a production version would feed this "
                            "into Modules 3-5 and invalidate the cached score card.",
                })
                return

            m = OVERRIDE_RE.match(self.path)
            if m:
                borrower_id = m.group(1)
                if not store.has_borrower(borrower_id):
                    self._send_json(404, {"error": f"unknown borrower_id: {borrower_id}"})
                    return
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    self._send_json(400, {"error": "invalid JSON body"})
                    return

                missing = [f for f in ("parameter", "overridden_score") if f not in payload]
                if not payload.get("comment", "").strip():
                    missing.append("comment (must be non-empty)")
                if missing:
                    self._send_json(400, {"error": f"missing/invalid required fields: {missing}"})
                    return

                received_at = datetime.datetime.utcnow().isoformat() + "Z"
                event = {"borrower_id": borrower_id, **payload, "received_at": received_at}
                _override_log.append(event)

                self._send_json(202, {
                    "borrower_id": borrower_id,
                    "status": "queued",
                    "received_at": received_at,
                    "note": "Logged only - this prototype does not actually trigger a "
                            "recompute. Server-side counterpart to the Module 6 dashboard's "
                            "client-side override capability (localStorage + JSON export) - "
                            "best-effort only, used if this server happens to be reachable.",
                })
                return

            self._send_json(404, {"error": "not found"})

    return Handler


def run_server(host, port, store: ScoreCardStore):
    handler = make_handler(store)
    httpd = HTTPServer((host, port), handler)
    return httpd
