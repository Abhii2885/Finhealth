"""Sanity checks on the segmentation output - not a ground-truth backtest
(there's no "correct" weight vector to check against), just internal
consistency checks that would catch a broken policy."""

import pandas as pd
from segmentation import DIMENSIONS


def run_checks(seg_df):
    checks = []

    # Tolerance is 1e-3, not 1e-6: effective weights are rounded to 4dp for
    # the output CSV, so up to ~6 dimensions each contributing +/-0.00005
    # rounding error can push the sum a few 1e-4 away from exactly 1.0.
    # That's an artifact of rounding for display, not a policy bug.
    weight_cols = [f"{d}_effective_weight" for d in DIMENSIONS]
    weight_sums = seg_df[weight_cols].sum(axis=1)
    scorable_sums = weight_sums[seg_df["scorable"]]
    checks.append({
        "check": "scorable borrowers' effective weights sum to ~1.0 (tolerance 1e-3 for rounding)",
        "pass": bool(((scorable_sums - 1.0).abs() < 1e-3).all()) if len(scorable_sums) else None,
        "detail": f"{len(scorable_sums)} scorable borrowers checked, max deviation "
                  f"{(scorable_sums - 1.0).abs().max() if len(scorable_sums) else 'n/a'}",
    })

    non_scorable_sums = weight_sums[~seg_df["scorable"]]
    checks.append({
        "check": "non-scorable borrowers have zero effective weight everywhere",
        "pass": bool((non_scorable_sums.abs() < 1e-6).all()) if len(non_scorable_sums) else True,
        "detail": f"{len(non_scorable_sums)} non-scorable borrowers checked",
    })

    concentration_weight = seg_df["concentration_risk_effective_weight"]
    checks.append({
        "check": "concentration_risk weight always 0 (not_computable_in_prototype for everyone)",
        "pass": bool((concentration_weight == 0).all()),
        "detail": f"max observed weight: {concentration_weight.max()}",
    })

    return pd.DataFrame(checks)
