# Module 7 — Ecosystem Integration Layer (Track 3)

## Read this first

The architecture doc says it plainly, and it's worth repeating before
anything else: **"you're not actually integrating with live ULI/OCEN
sandboxes — you're building the API contract and demonstrating one mocked
call. Say that plainly rather than implying live integration."**

This module is exactly that. Two things are real, one thing is not:

- **Real:** a running mock HTTP API, serving the *actual* score-card data
  computed by Modules 4–6 (not fabricated demo numbers), with a
  documented request/response contract.
- **Real:** an automated demo that starts the server, makes genuine HTTP
  calls against it, and validates the responses against the declared
  schema — proof it works, not an assertion.
- **Not real:** the schema itself is an **illustrative contract inspired
  by the general shape of ULI (Unified Lending Interface) / OCEN (Open
  Credit Enablement Network) presentment patterns** — it has not been
  checked against the certified official specification. Field names here
  are reasonable placeholders your team would map to the real spec during
  actual integration, not verified ground truth. Also not real: the
  consent-refresh webhook logs events but does **not** trigger an actual
  recompute (see below).

## Run it

**Interactive (manual):**
```bash
cd module7_integration
pip install pandas
python run_module7.py   # starts server on http://127.0.0.1:8077, Ctrl+C to stop
```
Then in another terminal:
```bash
curl http://127.0.0.1:8077/health
curl http://127.0.0.1:8077/uli/v1/score-card/MSME-00001
curl -X POST http://127.0.0.1:8077/uli/v1/consent-refresh \
     -H "Content-Type: application/json" \
     -d '{"borrower_id": "MSME-00001", "consent_id": "abc-123", "event_type": "new_data_available", "source": "bank_upi_transactions"}'
curl http://127.0.0.1:8077/uli/v1/consent-refresh/log
```

**Automated (non-interactive proof it works):**
```bash
python verify_demo.py
```
Starts the server in a background thread, makes real calls against every
endpoint (including the expected-failure cases: unknown borrower → 404,
malformed webhook → 400), validates response shapes, and writes
`integration_output/demo_run_log.json`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/uli/v1/score-card/{borrower_id}` | Returns the score-card presentment payload (see `schema.py`) |
| POST | `/uli/v1/consent-refresh` | AA consent-refresh webhook — logs the event, does NOT trigger recompute |
| GET | `/uli/v1/consent-refresh/log` | Demo/audit helper — lists received refresh events (in-memory, resets on restart) |

Zero extra dependencies for the server itself — built on Python's stdlib
`http.server`, so it runs anywhere Python 3 runs without a pip install for
the server (pandas is only needed to load the CSV outputs into memory).

## Verified this run

```json
{
  "sample_borrowers_tested": ["MSME-00001", "MSME-00002", "MSME-00003"],
  "all_score_cards_schema_valid": true,
  "consent_refresh_event_logged": true
}
```

Sample borrowers were chosen to span 3 different grades (D-Weak,
B-Good, E-Poor) rather than picking arbitrary IDs, so the demo actually
exercises different score profiles. Composite scores returned by the API
matched Module 5's computed values exactly (e.g. MSME-00001: 35.79,
D-Weak) — confirming the API serves the real pipeline output, not a
placeholder.

Both expected-failure paths were also verified, not just the happy path:
requesting an unknown borrower returns a clean 404, and posting a
consent-refresh webhook missing required fields returns a clean 400 with
the specific missing fields named.

## The consent-refresh webhook: what it actually does

Accepts a POST, validates required fields (`borrower_id`, `consent_id`,
`event_type`), logs it with a timestamp, and returns `202 Queued` with an
explicit note: **"this prototype does not actually trigger a recompute."**

Why not: real incremental recompute would need Module 1's batch generator
refactored into a per-borrower pipeline (right now it regenerates the
entire 400-borrower synthetic population at once, not one borrower's slice
on demand), plus Modules 2–6 would need to run against just that one
borrower's refreshed data. That's a real architectural change, not a
config flag — flagged as future work rather than faked here.

## Known limitations

1. **The schema is illustrative, not certified** — see above. Don't
   present this as "we integrated with ULI/OCEN," present it as "we built
   the contract our system would expose to one."
2. **In-memory only** — the consent-refresh log and the score-card data
   are both loaded/reset on server (re)start. No persistence, no
   database. Fine for a demo, not for anything real.
3. **No authentication** — a real presentment API would need the
   consuming LSP to authenticate (mTLS, OAuth, API keys tied to their
   ULI/OCEN registration) and the consent_id would need to be verified
   against an actual AA consent artifact, not just echoed back. None of
   that exists here.
4. **Single-threaded stdlib server** — fine for a demo hitting it a few
   times, not load-tested, not meant for concurrent production traffic.
5. **The `as_of_date` field is always "today"** — it should reflect when
   the underlying data was actually last ingested/computed, not the
   server's current date. A real version needs to track and return
   Module 1's actual ingestion timestamp per borrower.

## Files

```
module7_integration/
  config.py             - server host/port, output paths, schema-label disclaimer
  schema.py              - the two API contracts (score-card response, consent-refresh request/response)
  data_provider.py        - loads Module 4/5/6 outputs, maps to the score-card schema
  server.py               - stdlib HTTP server implementing the endpoints
  run_module7.py           - interactive entry point (blocks, serves until Ctrl+C)
  verify_demo.py            - automated, non-interactive proof: starts server, calls every endpoint, validates responses
  integration_output/       - demo_run_log.json (generated by verify_demo.py, not checked in by hand)
```
