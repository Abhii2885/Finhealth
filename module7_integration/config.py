"""
Module 7 - Ecosystem Integration Layer (Track 3)

Per the architecture doc: "you're not actually integrating with live
ULI/OCEN sandboxes in 3 days - you're building the API contract and
demonstrating one mocked call. Say that plainly rather than implying live
integration." This module does exactly that:

1. An illustrative score-card presentment API contract, INSPIRED BY the
   general shape of ULI (Unified Lending Interface) / OCEN (Open Credit
   Enablement Network) presentment patterns as publicly described - NOT a
   verified reproduction of the certified official schema. We have not
   cross-checked this against live ULI/OCEN API documentation. Treat every
   field name here as a reasonable placeholder your team would map to the
   real spec during actual integration, not as ground truth.
2. A real, running mock HTTP server (stdlib only, no Flask/FastAPI - so it
   runs anywhere Python 3 runs) serving that contract from Module 5/6's
   actual computed data - the SCORE DATA returned is real, computed from
   the synthetic pipeline, not fabricated for the demo.
3. A consent-refresh webhook endpoint that accepts and logs AA
   consent-refresh events. It does NOT actually trigger a recompute -
   full incremental single-borrower recompute would require refactoring
   Module 1's batch generator into a per-borrower pipeline, which is out
   of scope here. The response says so explicitly rather than pretending.
"""

import os

DEFAULT_SCORING_DIR = os.path.join(os.path.dirname(__file__), "..", "module5_scoring", "scoring_output")
DEFAULT_EXPLAINABILITY_DIR = os.path.join(os.path.dirname(__file__), "..", "module6_explainability", "explainability_output")
DEFAULT_SEGMENTATION_DIR = os.path.join(os.path.dirname(__file__), "..", "module4_segmentation", "segmentation_output")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "integration_output")

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8077

API_VERSION = "v1"
SCHEMA_LABEL = "illustrative-uli-ocen-inspired, not certified"
