"""
Percentile-rank scoring per feature, averaged within each dimension.

Percentile rank (not min-max) deliberately: min-max scaling would let a
single outlier (we already found bank balances running into the crores
for some borrowers - see Module 1 README) compress everyone else into a
tiny range. Percentile rank is robust to that and is directly explainable
to a loan officer ("this borrower's turnover growth is in the 73rd
percentile of the portfolio").

NaN handling: a borrower with no value for a feature (not_applicable,
excluded dimension, etc.) gets NaN for that feature's percentile score,
and NaNs are skipped (not zero-filled) when averaging within a dimension.
If ALL features in a dimension are NaN for a borrower, the dimension score
is NaN - Module 4 already zeroed that dimension's weight for them, so it
won't affect the composite anyway.
"""

import pandas as pd
from config import DIMENSION_SCORING_FEATURES, CONSISTENCY_FLAG_PENALTY


def _percentile_score(series, higher_is_healthier):
    """Returns 0-100 percentile rank, direction-adjusted. NaN stays NaN."""
    pct = series.rank(pct=True, na_option="keep") * 100
    if not higher_is_healthier:
        pct = 100 - pct
    return pct


def build_dimension_scores(features_df):
    out = features_df[["borrower_id"]].copy()
    feature_score_cols_by_dim = {}

    for dimension, feature_directions in DIMENSION_SCORING_FEATURES.items():
        per_feature_scores = []
        for feature, higher_is_healthier in feature_directions.items():
            if feature not in features_df.columns:
                continue
            # kept (not dropped) so Module 6 can identify top drivers per
            # dimension without recomputing/duplicating this scoring logic
            score_col = f"featscore__{dimension}__{feature}"
            out[score_col] = _percentile_score(features_df[feature], higher_is_healthier)
            per_feature_scores.append(score_col)

        feature_score_cols_by_dim[dimension] = per_feature_scores
        if per_feature_scores:
            out[f"{dimension}_score_raw"] = out[per_feature_scores].mean(axis=1, skipna=True)
        else:
            out[f"{dimension}_score_raw"] = float("nan")

    out.attrs["feature_score_cols_by_dim"] = feature_score_cols_by_dim

    # Transparent, capped adjustment to revenue_growth_signal from Module 2's
    # consistency flag - see config.CONSISTENCY_FLAG_PENALTY for why this is
    # a visible penalty rather than a blended feature.
    if "gst_bank_consistency_flag" in features_df.columns:
        penalty = features_df["gst_bank_consistency_flag"].map(CONSISTENCY_FLAG_PENALTY).fillna(0)
        out["revenue_growth_signal_consistency_penalty"] = penalty
        out["revenue_growth_signal_score"] = (
            out["revenue_growth_signal_score_raw"] + penalty
        ).clip(lower=0, upper=100)
    else:
        out["revenue_growth_signal_consistency_penalty"] = 0
        out["revenue_growth_signal_score"] = out["revenue_growth_signal_score_raw"]

    # Other dimensions: score = raw (no adjustment defined yet)
    for dimension in DIMENSION_SCORING_FEATURES:
        if dimension == "revenue_growth_signal":
            continue
        out[f"{dimension}_score"] = out[f"{dimension}_score_raw"]

    return out
