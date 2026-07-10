"""
Entry point for Module 7: starts the mock ULI/OCEN-style presentment API
and blocks (Ctrl+C to stop). For an automated, non-interactive proof that
it works end to end, run verify_demo.py instead.

Run:
    python run_module7.py [scoring_dir] [explainability_dir] [segmentation_dir]

Then, in another terminal:
    curl http://127.0.0.1:8077/health
    curl http://127.0.0.1:8077/uli/v1/score-card/MSME-00001
    curl -X POST http://127.0.0.1:8077/uli/v1/consent-refresh \\
         -H "Content-Type: application/json" \\
         -d '{"borrower_id": "MSME-00001", "consent_id": "abc-123", "event_type": "new_data_available", "source": "bank_upi_transactions"}'
    curl http://127.0.0.1:8077/uli/v1/consent-refresh/log
"""

import sys
from config import SERVER_HOST, SERVER_PORT, DEFAULT_SCORING_DIR, DEFAULT_EXPLAINABILITY_DIR, DEFAULT_SEGMENTATION_DIR
from data_provider import ScoreCardStore
from server import run_server


def main():
    scoring_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SCORING_DIR
    explainability_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_EXPLAINABILITY_DIR
    segmentation_dir = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_SEGMENTATION_DIR

    print(f"Loading score data from {scoring_dir} ...")
    store = ScoreCardStore(scoring_dir, explainability_dir, segmentation_dir)
    print(f"  {len(store.list_borrower_ids())} borrowers loaded")

    httpd = run_server(SERVER_HOST, SERVER_PORT, store)
    print(f"\nServing on http://{SERVER_HOST}:{SERVER_PORT}  (Ctrl+C to stop)")
    print("This is a MOCK API for demo purposes - illustrative schema, not a certified ULI/OCEN integration.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
