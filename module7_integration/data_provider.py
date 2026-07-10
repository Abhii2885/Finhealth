"""
Loads Module 4/5/6's real computed outputs into memory and maps them to
the score-card presentment schema. The numbers served by the API are the
actual pipeline outputs - nothing fabricated for the demo.
"""

import os
import datetime
import pandas as pd

from config import DEFAULT_SCORING_DIR, DEFAULT_EXPLAINABILITY_DIR, DEFAULT_SEGMENTATION_DIR, SCHEMA_LABEL
from schema import SCORE_CARD_RESPONSE_SCHEMA


class ScoreCardStore:
    def __init__(self, scoring_dir=None, explainability_dir=None, segmentation_dir=None):
        scoring_dir = scoring_dir or DEFAULT_SCORING_DIR
        explainability_dir = explainability_dir or DEFAULT_EXPLAINABILITY_DIR
        segmentation_dir = segmentation_dir or DEFAULT_SEGMENTATION_DIR

        self.scores = pd.read_csv(os.path.join(scoring_dir, "borrower_scores.csv")).set_index("borrower_id")
        self.drivers = pd.read_csv(os.path.join(explainability_dir, "top_drivers.csv")).set_index("borrower_id")
        self.segmentation = pd.read_csv(os.path.join(segmentation_dir, "segmentation_policy.csv")).set_index("borrower_id")

        # consent_id isn't in the scoring output - pull from Module 1's
        # borrower_master if available, else synthesize a placeholder so
        # the contract stays satisfiable even if that file isn't reachable.
        self._consent_lookup = {}
        master_path = os.path.join(os.path.dirname(__file__), "..", "msme_data_gen", "data_lake", "borrower_master.csv")
        if os.path.exists(master_path):
            master = pd.read_csv(master_path)
            self._consent_lookup = dict(zip(master["borrower_id"], master["consent_id"]))

        self.dimension_keys = [
            "liquidity_cash_flow", "repayment_credit_behavior", "revenue_growth_signal",
            "operational_stability", "compliance_discipline",
        ]
        self.dimension_labels = {
            "liquidity_cash_flow": "Liquidity & Cash Flow",
            "repayment_credit_behavior": "Repayment & Credit Behavior",
            "revenue_growth_signal": "Revenue & Growth Signal",
            "operational_stability": "Operational Stability",
            "compliance_discipline": "Compliance Discipline",
        }

    def has_borrower(self, borrower_id):
        return borrower_id in self.scores.index

    def get_score_card(self, borrower_id):
        if not self.has_borrower(borrower_id):
            return None

        score_row = self.scores.loc[borrower_id]
        seg_row = self.segmentation.loc[borrower_id] if borrower_id in self.segmentation.index else {}
        driver_row = self.drivers.loc[borrower_id] if borrower_id in self.drivers.index else {}

        def _clean(v):
            try:
                if pd.isna(v):
                    return None
            except Exception:
                pass
            return v

        dimensions = []
        for key in self.dimension_keys:
            dimensions.append({
                "key": key,
                "label": self.dimension_labels[key],
                "score": _clean(score_row.get(f"{key}_score")),
                "weight": _clean(seg_row.get(f"{key}_effective_weight") if hasattr(seg_row, "get") else None),
                "status": _clean(seg_row.get(f"{key}_status") if hasattr(seg_row, "get") else None),
                "top_positive_driver": _clean(driver_row.get(f"{key}_top_positive") if hasattr(driver_row, "get") else None),
                "top_negative_driver": _clean(driver_row.get(f"{key}_top_negative") if hasattr(driver_row, "get") else None),
            })

        return {
            "borrower_id": borrower_id,
            "consent_id": self._consent_lookup.get(borrower_id, "unknown-consent-id"),
            "as_of_date": datetime.date.today().isoformat(),
            "composite_score": _clean(score_row.get("composite_score")),
            "grade": _clean(score_row.get("grade")),
            "segment_label": _clean(score_row.get("segment_label")),
            "scorable": bool(score_row.get("scorable")) if not pd.isna(score_row.get("scorable")) else False,
            "dimensions": dimensions,
            "data_provenance": {
                "source": "synthetic MSME Financial Health Score pipeline (Modules 1-6)",
                "schema_label": SCHEMA_LABEL,
                "disclaimer": "Score is computed from SYNTHETIC data for a prototype. "
                               "This API contract is illustrative, inspired by ULI/OCEN "
                               "presentment patterns, and has not been validated against "
                               "the certified official specification.",
            },
        }

    def list_borrower_ids(self, limit=None):
        ids = list(self.scores.index)
        return ids[:limit] if limit else ids
