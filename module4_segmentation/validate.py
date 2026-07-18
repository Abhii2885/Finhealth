"""Sanity checks on the segmentation output - not a ground-truth backtest
(there's no "correct" weight vector to check against), just internal
consistency checks that would catch a broken policy."""

import pandas as pd
from segmentation import DIMENSIONS
from config import SUBWEIGHTS_BY_DIM


def run_checks(seg_df):
    checks = []

    # Tolerance is 1e-3, not 1e-6: effective weights are rounded to 4dp for
    # the output CSV, so up to 5 dimensions each contributing +/-0.00005
    # rounding error can push the sum a few 1e-4 away from exactly 1.0.
    # That's an artifact of rounding for display, not a policy bug.
    weight_cols = [f"{d}_effective_weight" for d in DIMENSIONS]
    weight_sums = seg_df[weight_cols].sum(axis=1)
    scorable_sums = weight_sums[seg_df["scorable"]]
    checks.append({
        "check": "scorable borrowers' effective (5C) weights sum to ~1.0 (tolerance 1e-3 for rounding)",
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

    # New invariant for the two-level 5C structure: within each C, the
    # included submetrics' effective_subweight must sum to ~1.0 whenever
    # that C is "in play" for a borrower (dimension_effective_weight > 0),
    # and to exactly 0 when the C is fully excluded. This is the submetric-
    # level analogue of the check above, one level deeper.
    for dim in DIMENSIONS:
        subweight_cols = [f"{dim}__{s}_effective_subweight" for s in SUBWEIGHTS_BY_DIM[dim]]
        sub_sums = seg_df[subweight_cols].sum(axis=1)
        dim_in_play = seg_df[f"{dim}_effective_weight"] > 0
        in_play_sums = sub_sums[dim_in_play]
        excluded_sums = sub_sums[~dim_in_play]
        ok = True
        if len(in_play_sums):
            ok = ok and bool(((in_play_sums - 1.0).abs() < 1e-3).all())
        if len(excluded_sums):
            ok = ok and bool((excluded_sums.abs() < 1e-6).all())
        checks.append({
            "check": f"{dim}: submetric weights sum to ~1.0 when in play, 0 when excluded",
            "pass": ok,
            "detail": f"{len(in_play_sums)} in-play, {len(excluded_sums)} excluded borrowers checked",
        })

    return pd.DataFrame(checks)
