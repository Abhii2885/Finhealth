# Module 7 — Ecosystem Integration Layer (Track 3)

## Read this first

**This module does not integrate with live ULI/OCEN sandboxes — it
builds the API contract and demonstrates it against the real pipeline
output.** Two things are real, one is not:

- **Real:** a running mock HTTP API serving the *actual* score-card
  data computed by Modules 4–6 (not fabricated demo numbers), with a
  documented request/response contract.
- **Real:** an automated demo that starts the server, makes genuine
  HTTP calls against every endpoint, and validates responses against
  the declared schema.
- **Not real:** the schema is an **illustrative contract inspired by
  the general shape of ULI (Unified Lending Interface) / OCEN
  presentment patterns** — not checked against any certified official
  specification. Webhook endpoints log events but do **not** trigger
  recomputes (each response says so explicitly).

## Run it

**Interactive:**
```bash
cd module7_integration
pip install pandas
python run_module7.py   # serves on http://127.0.0.1:8077, Ctrl+C to stop
```

**Automated proof:**
```bash
python verify_demo.py
```
Starts the server in a background thread, exercises every endpoint
including expected-failure cases (unknown borrower → 404, malformed
payloads → 400 with the missing fields named), validates response
shapes, and writes `integration_output/demo_run_log.json`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/uli/v1/score-card/{borrower_id}` | Score-card presentment: composite, grade, 5C dimension scores with submetric detail, context flags |
| POST | `/uli/v1/consent-refresh` | AA consent-refresh webhook — logged, not recomputed |
| GET | `/uli/v1/consent-refresh/log` | Audit helper (in-memory) |
| POST | `/uli/v1/score-card/{borrower_id}/applicant-inputs` | Applicant-supplied inputs (balance-sheet availability, projected revenue) — the real future user-input surface Module 1 currently simulates |
| GET | `/uli/v1/applicant-inputs/log` | Audit helper (in-memory) |
| POST | `/uli/v1/score-card/{borrower_id}/override` | Server-side counterpart to the dashboard's score override; `comment` is mandatory (400 without it) |
| GET | `/uli/v1/override/log` | Audit helper (in-memory) |

Built on Python's stdlib `http.server` — no server-side dependencies
beyond pandas for loading the CSVs.

## Verified this run

```json
{
  "sample_borrowers_tested": ["MSME-00001", "MSME-00002", "MSME-00003"],
  "all_score_cards_schema_valid": true,
  "consent_refresh_event_logged": true,
  "applicant_inputs_event_logged": true,
  "override_event_logged": true
}
```

Composite scores returned by the API matched Module 5's computed values
exactly (e.g. MSME-00001: 60.88, C-Fair) — the API serves real pipeline
output, not placeholders. All expected-failure paths verified alongside
the happy paths.

## Known limitations

1. **The schema is illustrative, not certified** — present it as "the
   contract our system would expose," not "we integrated with ULI/OCEN."
2. **In-memory only** — logs and score data reset on restart.
3. **No authentication** — a real presentment API needs mTLS/OAuth tied
   to the consumer's registration, and consent verification against a
   real AA artefact.
4. **Webhooks log but do not recompute** — incremental per-borrower
   recompute would require refactoring Module 1's batch generator, a
   real architectural change flagged as future work rather than faked.
5. **Single-threaded stdlib server** — demo-grade, not load-tested.

## Files

```
module7_integration/
  config.py          - server host/port, output paths, schema-label disclaimer
  schema.py          - API contracts (score-card, consent-refresh, applicant-inputs, override)
  data_provider.py   - loads Module 4/5 outputs, maps to the score-card schema
  server.py          - stdlib HTTP server implementing all endpoints
  run_module7.py     - interactive entry point
  verify_demo.py     - automated end-to-end proof with schema validation
  integration_output/ - demo_run_log.json (generated)
```
