"""
Per-submetric scoring (percentile / tiered / band_distance / lookup_table /
direct_ratio - see config.SCORING_SUBMETRICS), then a WEIGHTED average within each C
using Module 4's per-borrower effective subweights - this replaced the
old unweighted skipna mean, since submetrics within a C no longer carry
equal importance by default (e.g. Capacity's dscr matters more than
customer_concentration_pct).

NaN handling: a borrower with no value for a submetric (not_applicable,
insufficient source, etc.) gets NaN for that submetric's score. Module 4
already zeroed that submetric's effective_subweight for them, so it's
excluded from the weighted average the same way aggregate.py already
excludes zero-weight dimensions from the composite - dropped, not treated
as a zero score, and the weighted average rescales over whatever weight
actually had a usable score.
"""

import pandas as pd
import numpy as np
from config import SCORING_SUBMETRICS, CONSISTENCY_FLAG_PENALTY, CASH_FLOW_MATCH_TARGET_LOW, \
    CASH_FLOW_MATCH_TARGET_HIGH, CASH_FLOW_MATCH_DECAY_WIDTH, COLLATERAL_QUALITY_LOOKUP, \
    TIERED_ANCHORS, TIERED_FLOOR_AT_ZERO


def _percentile_score(series, higher_is_healthier):
    """Returns 0-100 percentile rank, direction-adjusted. NaN stays NaN."""
    pct = series.rank(pct=True, na_option="keep") * 100
    if not higher_is_healthier:
        pct = 100 - pct
    return pct


def _tiered_score(series, anchors, floor_at_zero=False):
    """Piecewise-linear interpolation across the lender-supplied Score Band
    anchor points (config.TIERED_ANCHORS - ascending-x (raw_value, score)
    pairs on the rubric's native 0-10 scale, multiplied by 10 here to match
    this pipeline's 0-100 internal scale everywhere else).

    Direction (ascending vs descending y) is read off the anchors
    themselves rather than assumed, since some submetrics are "higher is
    better" (current_ratio: low x -> low score) and others are "lower is
    better" (leverage_ratio: low x -> high score). Whichever end of the
    anchor list is the LAST NAMED CUTOFF before the rubric's unbounded "10"
    tier (e.g. current_ratio's ">2.0", leverage's "<1x") flatlines at a
    perfect 100 beyond that point - the other end is a natural data floor
    (0, or CIBIL's 300) where interpolation simply starts/ends, since real
    values can't go further in that direction anyway.

    floor_at_zero submetrics (revenue CAGR, projected growth) score exactly
    0 for v<=0 rather than extrapolating below the first anchor - per the
    user's explicit "0% or negative CAGR scores zero" rule.
    """
    xs = [a[0] for a in anchors]
    ys = [a[1] * 10.0 for a in anchors]
    ascending = ys[-1] > ys[0]

    def score_one(v):
        if pd.isna(v):
            return np.nan
        if floor_at_zero and v <= 0:
            return 0.0
        if ascending:
            if v >= xs[-1]:
                return 100.0
            if v <= xs[0]:
                return ys[0]
        else:
            if v <= xs[0]:
                return 100.0
            if v >= xs[-1]:
                return ys[-1]
        return float(np.interp(v, xs, ys))
    return series.apply(score_one)


def _direct_ratio_score(series):
    """Compliance submetrics (v5): a straight ratio*100 read, not a
    percentile rank against the batch. Per explicit user instruction - 50%
    on-time filing scores 5/10, 80% scores 8/10, regardless of how the
    rest of the 400-borrower population happens to be doing. This makes
    Compliance scores portable/absolute (comparable across runs, batches,
    or a single new applicant scored alone) the same way the tiered Score
    Band submetrics already are - percentile ranking previously used here
    couldn't do that, since a single applicant has no population to rank
    against."""
    def score_one(v):
        if pd.isna(v):
            return np.nan
        return float(min(max(v * 100.0, 0.0), 100.0))
    return series.apply(score_one)


def _band_distance_score(series, target_low, target_high, decay_width):
    def score_one(v):
        if pd.isna(v):
            return np.nan
        if target_low <= v <= target_high:
            return 100.0
        dist = (target_low - v) if v < target_low else (v - target_high)
        return float(max(100.0 - (dist / decay_width) * 100.0, 0.0))
    return series.apply(score_one)


def _lookup_table_score(df, columns, table):
    col_a, col_b = columns

    def score_one(row):
        a, b = row[col_a], row[col_b]
        if pd.isna(a) or pd.isna(b):
            return np.nan
        return table.get((a, b), np.nan)

    return df.apply(score_one, axis=1)


def _weighted_dim_score(row, dim, submetrics):
    weighted_sum = 0.0
    weight_total = 0.0
    for submetric in submetrics:
        w = row.get(f"{dim}__{submetric}_effective_subweight", 0.0)
        s = row.get(f"featscore__{dim}__{submetric}", float("nan"))
        if w and w > 0 and pd.notna(s):
            weighted_sum += w * s
            weight_total += w
    return weighted_sum / weight_total if weight_total > 0 else float("nan")


def build_dimension_scores(features_df, segmentation_df):
    out = features_df[["borrower_id"]].copy()

    submetrics_by_dim = {}
    for (dim, submetric), spec in SCORING_SUBMETRICS.items():
        submetrics_by_dim.setdefault(dim, []).append(submetric)
        col = f"featscore__{dim}__{submetric}"
        method = spec["method"]

        if method == "lookup_table":
            cols = spec["columns"]
            if all(c in features_df.columns for c in cols):
                out[col] = _lookup_table_score(features_df, cols, COLLATERAL_QUALITY_LOOKUP)
            else:
                out[col] = np.nan
            continue

        if submetric not in features_df.columns:
            out[col] = np.nan
            continue

        if method == "percentile":
            out[col] = _percentile_score(features_df[submetric], spec["higher_is_healthier"])
        elif method == "direct_ratio":
            out[col] = _direct_ratio_score(features_df[submetric])
        elif method == "tiered":
            out[col] = _tiered_score(
                features_df[submetric], TIERED_ANCHORS[submetric], floor_at_zero=submetric in TIERED_FLOOR_AT_ZERO
            )
        elif method == "band_distance":
            out[col] = _band_distance_score(
                features_df[submetric], CASH_FLOW_MATCH_TARGET_LOW, CASH_FLOW_MATCH_TARGET_HIGH, CASH_FLOW_MATCH_DECAY_WIDTH
            )
        else:
            raise ValueError(f"unknown scoring method: {method}")

    # Transparent, capped adjustment to Capacity's revenue_cagr_3yr submetric
    # score from Module 2's consistency flag - see config.CONSISTENCY_FLAG_
    # PENALTY for why this is a visible penalty rather than a blended feature.
    cagr_col = "featscore__capacity__revenue_cagr_3yr"
    if "gst_bank_consistency_flag" in features_df.columns and cagr_col in out.columns:
        penalty = features_df["gst_bank_consistency_flag"].map(CONSISTENCY_FLAG_PENALTY).fillna(0)
        out["capacity_consistency_penalty"] = penalty
        out[cagr_col] = (out[cagr_col] + penalty).clip(lower=0, upper=100)
    else:
        out["capacity_consistency_penalty"] = 0

    # Weighted average within each C, using Module 4's per-borrower
    # effective subweights (NOT an unweighted skipna mean anymore).
    subweight_cols = [f"{dim}__{s}_effective_subweight" for dim, ss in submetrics_by_dim.items() for s in ss]
    merged = out.merge(segmentation_df[["borrower_id"] + subweight_cols], on="borrower_id", how="left")

    for dim, submetrics in submetrics_by_dim.items():
        merged[f"{dim}_score"] = merged.apply(lambda r: _weighted_dim_score(r, dim, submetrics), axis=1)

    merged = merged.drop(columns=subweight_cols)
    merged.attrs["submetrics_by_dim"] = submetrics_by_dim
    return merged
