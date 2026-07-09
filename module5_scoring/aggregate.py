"""
Weighted aggregation of dimension scores (this module) with Module 4's
per-borrower effective weights into one composite 0-100 score + grade.

Zero-weight dimensions (not_applicable, not_computable_in_prototype, or
concentration_risk which is ALWAYS zero-weight in this prototype - see
Module 4) are excluded from the weighted sum entirely, not treated as a
zero score. A NaN dimension score with 0 weight contributes 0 * NaN which
is NaN in pandas/numpy - explicitly guarded against below so one
inapplicable dimension can't silently NaN-out an otherwise valid composite.
"""

import pandas as pd
from config import DIMENSION_SCORING_FEATURES, GRADE_BANDS

SCORABLE_DIMENSIONS = list(DIMENSION_SCORING_FEATURES.keys())  # excludes concentration_risk (no source)


def _grade(score):
    if pd.isna(score):
        return "Not scored"
    for lo, hi, label in GRADE_BANDS:
        if lo <= score <= hi:
            return label
    return "Not scored"


def build_composite(dim_scores_df, segmentation_df):
    m = dim_scores_df.merge(segmentation_df, on="borrower_id", how="left", suffixes=("", "_seg"))

    composite = []
    for _, row in m.iterrows():
        if not row["scorable"]:
            composite.append(float("nan"))
            continue
        weighted_sum = 0.0
        weight_total = 0.0
        for dim in SCORABLE_DIMENSIONS:
            w = row.get(f"{dim}_effective_weight", 0.0)
            s = row.get(f"{dim}_score", float("nan"))
            if w and w > 0 and pd.notna(s):
                weighted_sum += w * s
                weight_total += w
        # weight_total should equal the borrower's total weight across
        # scorable dimensions (Module 4 already renormalized to 1.0 minus
        # whatever concentration_risk would've held, which is always 0
        # here) - if a dimension has weight but somehow NaN score, that
        # weight is silently dropped here rather than corrupting the sum,
        # and we rescale over whatever weight actually had a usable score.
        composite.append(round(weighted_sum / weight_total, 2) if weight_total > 0 else float("nan"))

    m["composite_score"] = composite
    m["grade"] = m["composite_score"].apply(_grade)
    return m
