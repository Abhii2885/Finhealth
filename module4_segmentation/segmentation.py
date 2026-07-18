"""
Core segmentation logic: turns Module 2's per-(dimension, submetric)
availability into a two-level weight vector (submetric weights within each
C, and each C's own weight in the composite), an eligibility flag, and a
human-readable segment label.

Two-stage renormalization, not one flat pass across all 22 submetrics:
1. WITHIN each C: exclude unavailable submetrics, renormalize the
   remainder to sum to 1.0 relative to that C. This is where Character's
   bureau-unavailable redistribution and Compliance's covenant-absent
   re-ranking actually happen - see config.py's comments for the hand-
   verified proof this reproduces the user's exact stated orderings.
2. ACROSS the 5 Cs: a C is either "in play" (>=1 usable submetric, gets
   its FULL base weight) or fully excluded (zero usable submetrics, weight
   redistributed to the other C's) - same top-level mechanism the old
   6-dimension version already had, just fed by submetric totals instead
   of a single flat per-dimension status.

A single flat renormalization across all 22 submetrics at once would be
WRONG here - it would let a partially-thin C (e.g. Character with just
bureau missing) bleed weight to OTHER dimensions instead of keeping it
inside Character, which is exactly the "some but not all excluded" case
the user's proportional-redistribution requirement is about.
"""

import pandas as pd
from config import BASE_DIMENSION_WEIGHTS, SUBWEIGHTS_BY_DIM, INSUFFICIENT_DATA_WEIGHT_MULTIPLIER, MIN_DIMENSIONS_FOR_SCORING

DIMENSIONS = list(BASE_DIMENSION_WEIGHTS.keys())


def _raw_weight(status, base_weight):
    if status == "available":
        return base_weight
    if status == "insufficient_data":
        return base_weight * INSUFFICIENT_DATA_WEIGHT_MULTIPLIER
    return 0.0  # not_applicable


def _subweight_discount_effect(statuses):
    """Per-C diagnostic mirroring the old whole-pipeline data_confidence
    field, moved one level deeper: is INSUFFICIENT_DATA_WEIGHT_MULTIPLIER
    actually changing this borrower's within-C weights, or a no-op?
    Renormalizing after scaling ALL included items by the same constant is
    mathematically identical to not discounting at all - only matters when
    it applies to SOME but not ALL of a C's included submetrics."""
    included = [s for s in statuses if s in ("available", "insufficient_data")]
    discounted = [s for s in statuses if s == "insufficient_data"]
    if not included:
        return "not_applicable"
    if not discounted:
        return "full"
    if len(discounted) < len(included):
        return "discount_applied"
    return "discount_is_noop_all_submetrics_uniformly_thin"


def _segment_label(row):
    included = [d for d in DIMENSIONS if row[f"{d}_effective_weight"] > 0]
    if not row["scorable"]:
        return "Insufficient data for scoring"
    n = len(included)
    if n >= 5:
        return f"Full — {n} of 5 Cs available"
    return f"Reduced — {n} of 5 Cs available ({', '.join(included)})"


def build_segmentation(submetric_avail_df):
    rows = []
    for _, r in submetric_avail_df.iterrows():
        row = {"borrower_id": r["borrower_id"]}
        dim_raw_weight = {}

        for dim in DIMENSIONS:
            subweights = SUBWEIGHTS_BY_DIM[dim]
            raw_subweights = {}
            statuses = []
            for submetric, base_subweight in subweights.items():
                status_col = f"{dim}__{submetric}_status"
                status = r[status_col]
                statuses.append(status)
                row[status_col] = status
                raw_subweights[submetric] = _raw_weight(status, base_subweight)

            total_raw_sub = sum(raw_subweights.values())
            for submetric in subweights:
                col = f"{dim}__{submetric}_effective_subweight"
                row[col] = round(raw_subweights[submetric] / total_raw_sub, 4) if total_raw_sub > 0 else 0.0

            row[f"{dim}_subweight_discount_effect"] = _subweight_discount_effect(statuses)
            dim_raw_weight[dim] = BASE_DIMENSION_WEIGHTS[dim] if total_raw_sub > 0 else 0.0

        total_dim_raw = sum(dim_raw_weight.values())
        n_included = sum(1 for w in dim_raw_weight.values() if w > 0)
        scorable = n_included >= MIN_DIMENSIONS_FOR_SCORING and total_dim_raw > 0

        for dim in DIMENSIONS:
            if scorable and total_dim_raw > 0:
                row[f"{dim}_effective_weight"] = round(dim_raw_weight[dim] / total_dim_raw, 4)
            else:
                row[f"{dim}_effective_weight"] = 0.0

        row["n_dimensions_included"] = n_included
        row["scorable"] = scorable
        rows.append(row)

    out = pd.DataFrame(rows)
    out["segment_label"] = out.apply(_segment_label, axis=1)
    return out
