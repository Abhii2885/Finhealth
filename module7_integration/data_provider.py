"""
Loads Module 1/4/5/6's real computed outputs into memory and maps them to
the score-card presentment schema. The numbers served by the API are the
actual pipeline outputs - nothing fabricated for the demo.

v3: 5C dimensions (capacity/character/capital/compliance/collateral),
per-submetric breakdown (from Module 5's feature_scores.csv + Module 4's
segmentation_policy.csv), and a "context" block of applicant flags
(is_gst_registered, balance_sheet_available, etc. + projected revenue)
sourced from Module 1's master/loan_application - the real future-user-
input surface (see schema.APPLICANT_INPUT_REQUEST_SCHEMA).
"""

import os
import datetime
import pandas as pd

from config import DEFAULT_SCORING_DIR, DEFAULT_EXPLAINABILITY_DIR, DEFAULT_SEGMENTATION_DIR, DEFAULT_DATA_LAKE_DIR, SCHEMA_LABEL

DIMENSION_KEYS = ["capacity", "character", "capital", "compliance", "collateral"]
DIMENSION_LABELS = {
    "capacity": "Capacity",
    "character": "Character",
    "capital": "Capital",
    "compliance": "Compliance",
    "collateral": "Collateral",
}


def _clean(v):
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    return v


class ScoreCardStore:
    def __init__(self, scoring_dir=None, explainability_dir=None, segmentation_dir=None, data_lake_dir=None):
        scoring_dir = scoring_dir or DEFAULT_SCORING_DIR
        explainability_dir = explainability_dir or DEFAULT_EXPLAINABILITY_DIR
        segmentation_dir = segmentation_dir or DEFAULT_SEGMENTATION_DIR
        data_lake_dir = data_lake_dir or DEFAULT_DATA_LAKE_DIR

        self.scores = pd.read_csv(os.path.join(scoring_dir, "borrower_scores.csv")).set_index("borrower_id")
        self.feature_scores = pd.read_csv(os.path.join(scoring_dir, "feature_scores.csv")).set_index("borrower_id")
        self.drivers = pd.read_csv(os.path.join(explainability_dir, "top_drivers.csv")).set_index("borrower_id")
        self.segmentation = pd.read_csv(os.path.join(segmentation_dir, "segmentation_policy.csv")).set_index("borrower_id")

        self._consent_lookup = {}
        self._context_lookup = {}
        master_path = os.path.join(data_lake_dir, "borrower_master.csv")
        if os.path.exists(master_path):
            master = pd.read_csv(master_path)
            self._consent_lookup = dict(zip(master["borrower_id"], master["consent_id"]))
            self._context_lookup = master.set_index("borrower_id").to_dict("index")

        self._projected_revenue_lookup = {}
        application_path = os.path.join(data_lake_dir, "loan_application", "loan_application.csv")
        if os.path.exists(application_path):
            application = pd.read_csv(application_path)
            self._projected_revenue_lookup = dict(zip(application["borrower_id"], application["projected_revenue_next_year_inr"]))

        # Submetric keys per dimension, discovered from segmentation's
        # "{dim}__{submetric}_status" columns - single source of truth,
        # not re-declared here (mirrors Module 6's dashboard.py approach).
        self.submetrics_by_dim = {}
        for col in self.segmentation.columns:
            for dim in DIMENSION_KEYS:
                prefix, suffix = f"{dim}__", "_status"
                if col.startswith(prefix) and col.endswith(suffix):
                    self.submetrics_by_dim.setdefault(dim, []).append(col[len(prefix):-len(suffix)])

    def has_borrower(self, borrower_id):
        return borrower_id in self.scores.index

    def get_score_card(self, borrower_id):
        if not self.has_borrower(borrower_id):
            return None

        score_row = self.scores.loc[borrower_id]
        seg_row = self.segmentation.loc[borrower_id] if borrower_id in self.segmentation.index else {}
        driver_row = self.drivers.loc[borrower_id] if borrower_id in self.drivers.index else {}
        fscore_row = self.feature_scores.loc[borrower_id] if borrower_id in self.feature_scores.index else {}

        dimensions = []
        for key in DIMENSION_KEYS:
            submetrics = []
            for sm in self.submetrics_by_dim.get(key, []):
                submetrics.append({
                    "key": sm,
                    "score": _clean(fscore_row.get(f"featscore__{key}__{sm}") if hasattr(fscore_row, "get") else None),
                    "weight": _clean(seg_row.get(f"{key}__{sm}_effective_subweight") if hasattr(seg_row, "get") else None),
                    "status": _clean(seg_row.get(f"{key}__{sm}_status") if hasattr(seg_row, "get") else None),
                })
            dimensions.append({
                "key": key,
                "label": DIMENSION_LABELS[key],
                "score": _clean(score_row.get(f"{key}_score")),
                "weight": _clean(seg_row.get(f"{key}_effective_weight") if hasattr(seg_row, "get") else None),
                "status": "available" if (seg_row.get(f"{key}_effective_weight", 0) or 0) > 0 else "not_applicable",
                "top_positive_driver": _clean(driver_row.get(f"{key}_top_positive") if hasattr(driver_row, "get") else None),
                "top_negative_driver": _clean(driver_row.get(f"{key}_top_negative") if hasattr(driver_row, "get") else None),
                "submetrics": submetrics,
            })

        applicant = self._context_lookup.get(borrower_id, {})

        return {
            "borrower_id": borrower_id,
            "consent_id": self._consent_lookup.get(borrower_id, "unknown-consent-id"),
            "as_of_date": datetime.date.today().isoformat(),
            "composite_score": _clean(score_row.get("composite_score")),
            "grade": _clean(score_row.get("grade")),
            "segment_label": _clean(score_row.get("segment_label")),
            "scorable": bool(score_row.get("scorable")) if not pd.isna(score_row.get("scorable")) else False,
            "dimensions": dimensions,
            "context": {
                "is_gst_registered": bool(applicant.get("is_gst_registered", True)),
                "balance_sheet_available": bool(applicant.get("balance_sheet_available", False)),
                "has_bureau_record": bool(applicant.get("has_bureau_record", False)),
                "has_existing_loan": bool(applicant.get("has_existing_loan", False)),
                "has_collateral": bool(applicant.get("has_collateral", False)),
                "projected_revenue_next_year_inr": _clean(self._projected_revenue_lookup.get(borrower_id)),
            },
            "data_provenance": {
                "source": "synthetic MSME Financial Health Score pipeline (Modules 1-6), 5C framework",
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
