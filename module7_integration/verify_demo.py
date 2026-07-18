"""
Automated, non-interactive proof that the mock API actually works:
starts the server in a background thread, makes real HTTP calls against
it (urllib only, no extra deps), validates response shapes against the
declared schema, and saves a demo run log. Stops the server on exit.

Run:
    python verify_demo.py [scoring_dir] [explainability_dir] [segmentation_dir]

Produces integration_output/demo_run_log.json
"""

import sys
import os
import json
import time
import threading
import urllib.request
import urllib.error

from config import SERVER_HOST, SERVER_PORT, OUTPUT_DIR, DEFAULT_SCORING_DIR, DEFAULT_EXPLAINABILITY_DIR, DEFAULT_SEGMENTATION_DIR, DEFAULT_DATA_LAKE_DIR
from data_provider import ScoreCardStore
from server import run_server
from schema import SCORE_CARD_RESPONSE_SCHEMA


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _validate_score_card_shape(card):
    """Lightweight structural check against SCORE_CARD_RESPONSE_SCHEMA's
    required fields - not a full JSON-Schema validator (avoids adding a
    jsonschema dependency), but catches the obvious break-the-contract cases."""
    missing = [f for f in SCORE_CARD_RESPONSE_SCHEMA["required"] if f not in card]
    dim_issues = []
    for d in card.get("dimensions", []):
        dim_required = SCORE_CARD_RESPONSE_SCHEMA["properties"]["dimensions"]["items"]["required"]
        missing_dim_fields = [f for f in dim_required if f not in d]
        if missing_dim_fields:
            dim_issues.append({"dimension": d.get("key"), "missing": missing_dim_fields})
    return {"missing_top_level_fields": missing, "dimension_field_issues": dim_issues,
            "valid": len(missing) == 0 and len(dim_issues) == 0}


def main():
    scoring_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SCORING_DIR
    explainability_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_EXPLAINABILITY_DIR
    segmentation_dir = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_SEGMENTATION_DIR
    data_lake_dir = sys.argv[4] if len(sys.argv) > 4 else DEFAULT_DATA_LAKE_DIR
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading score data + starting mock server in a background thread...")
    store = ScoreCardStore(scoring_dir, explainability_dir, segmentation_dir, data_lake_dir)
    httpd = run_server(SERVER_HOST, SERVER_PORT, store)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)  # let the socket bind

    base = f"http://{SERVER_HOST}:{SERVER_PORT}"
    log = {"calls": []}

    try:
        # 1. health check
        status, body = _get(f"{base}/health")
        log["calls"].append({"call": "GET /health", "status": status, "response": body})
        print(f"GET /health -> {status} {body}")

        # 2. pick 3 real borrowers spanning different grades for a meaningful demo
        all_ids = store.list_borrower_ids()
        sample_ids = []
        seen_grades = set()
        for bid in all_ids:
            card = store.get_score_card(bid)
            if card["grade"] not in seen_grades:
                sample_ids.append(bid)
                seen_grades.add(card["grade"])
            if len(sample_ids) >= 3:
                break

        for bid in sample_ids:
            status, body = _get(f"{base}/uli/v1/score-card/{bid}")
            validation = _validate_score_card_shape(body)
            log["calls"].append({
                "call": f"GET /uli/v1/score-card/{bid}",
                "status": status,
                "response": body,
                "schema_validation": validation,
            })
            print(f"GET /uli/v1/score-card/{bid} -> {status}, composite={body.get('composite_score')}, "
                  f"grade={body.get('grade')}, schema_valid={validation['valid']}")

        # 3. unknown borrower -> should 404 cleanly
        status, body = _get(f"{base}/uli/v1/score-card/MSME-NOT-REAL")
        log["calls"].append({"call": "GET /uli/v1/score-card/MSME-NOT-REAL (expect 404)", "status": status, "response": body})
        print(f"GET unknown borrower -> {status} {body}")

        # 4. consent-refresh webhook
        refresh_payload = {
            "borrower_id": sample_ids[0],
            "consent_id": "demo-consent-id-001",
            "event_type": "new_data_available",
            "source": "bank_upi_transactions",
        }
        status, body = _post(f"{base}/uli/v1/consent-refresh", refresh_payload)
        log["calls"].append({"call": "POST /uli/v1/consent-refresh", "status": status,
                              "request": refresh_payload, "response": body})
        print(f"POST /uli/v1/consent-refresh -> {status} {body}")

        # 5. malformed consent-refresh -> should 400 cleanly
        status, body = _post(f"{base}/uli/v1/consent-refresh", {"borrower_id": "MSME-00001"})
        log["calls"].append({"call": "POST /uli/v1/consent-refresh (missing fields, expect 400)",
                              "status": status, "response": body})
        print(f"POST malformed consent-refresh -> {status} {body}")

        # 6. confirm the event actually shows up in the log endpoint
        status, body = _get(f"{base}/uli/v1/consent-refresh/log")
        log["calls"].append({"call": "GET /uli/v1/consent-refresh/log", "status": status, "response": body})
        logged_ok = any(e.get("borrower_id") == sample_ids[0] for e in body.get("events", []))
        print(f"GET /uli/v1/consent-refresh/log -> {status}, refresh event present: {logged_ok}")

        # 7. applicant-inputs webhook - the real future-user-input surface
        applicant_payload = {"balance_sheet_available": True, "projected_revenue_next_year_inr": 5_000_000}
        status, body = _post(f"{base}/uli/v1/score-card/{sample_ids[0]}/applicant-inputs", applicant_payload)
        log["calls"].append({"call": "POST /uli/v1/score-card/.../applicant-inputs", "status": status,
                              "request": applicant_payload, "response": body})
        print(f"POST /uli/v1/score-card/{sample_ids[0]}/applicant-inputs -> {status} {body}")

        status, body = _get(f"{base}/uli/v1/applicant-inputs/log")
        applicant_logged_ok = any(e.get("borrower_id") == sample_ids[0] for e in body.get("events", []))
        log["calls"].append({"call": "GET /uli/v1/applicant-inputs/log", "status": status, "response": body})
        print(f"GET /uli/v1/applicant-inputs/log -> {status}, event present: {applicant_logged_ok}")

        # 8. score override with mandatory comment (happy path)
        override_payload = {"parameter": "capacity.dscr", "original_score": 70.0, "overridden_score": 85.0,
                             "comment": "Verified stronger cash position from bank statement not yet reflected."}
        status, body = _post(f"{base}/uli/v1/score-card/{sample_ids[0]}/override", override_payload)
        log["calls"].append({"call": "POST /uli/v1/score-card/.../override", "status": status,
                              "request": override_payload, "response": body})
        print(f"POST /uli/v1/score-card/{sample_ids[0]}/override -> {status} {body}")

        # 9. override missing the required comment -> should 400 cleanly
        status, body = _post(f"{base}/uli/v1/score-card/{sample_ids[0]}/override",
                              {"parameter": "capacity.dscr", "overridden_score": 85.0, "comment": ""})
        log["calls"].append({"call": "POST /uli/v1/score-card/.../override (empty comment, expect 400)",
                              "status": status, "response": body})
        print(f"POST override missing comment -> {status} {body}")

        status, body = _get(f"{base}/uli/v1/override/log")
        override_logged_ok = any(e.get("borrower_id") == sample_ids[0] for e in body.get("events", []))
        log["calls"].append({"call": "GET /uli/v1/override/log", "status": status, "response": body})
        print(f"GET /uli/v1/override/log -> {status}, event present: {override_logged_ok}")

        log["summary"] = {
            "sample_borrowers_tested": sample_ids,
            "all_score_cards_schema_valid": all(
                c["schema_validation"]["valid"] for c in log["calls"] if "schema_validation" in c
            ),
            "consent_refresh_event_logged": logged_ok,
            "applicant_inputs_event_logged": applicant_logged_ok,
            "override_event_logged": override_logged_ok,
        }

    finally:
        httpd.shutdown()

    log_path = os.path.join(OUTPUT_DIR, "demo_run_log.json")
    with open(log_path, "w") as f:
        json.dump(log, f, indent=2)
    print(f"\nDemo run log saved to {log_path}")
    print(json.dumps(log["summary"], indent=2))


if __name__ == "__main__":
    main()
