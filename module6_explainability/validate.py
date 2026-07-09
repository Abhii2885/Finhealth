"""Validates the trend indicator against the hidden true_archetype label
(never used as an input - only to check the trend view carries real
signal, same pattern as every prior module)."""

import pandas as pd


def validate_trend(trend_df, ground_truth_df):
    m = trend_df.merge(ground_truth_df[["borrower_id", "true_archetype"]], on="borrower_id", how="left")
    pivot = m.pivot_table(index="true_archetype", columns="checkpoint_frac", values="trend_indicator", aggfunc="mean")
    pivot = pivot.reindex(["healthy", "stagnant", "distressed"])

    # Direction check: does the FINAL checkpoint (1.0) still show the same
    # healthy > stagnant > distressed ordering the rest of the pipeline has?
    final = pivot[1.0]
    ordering_correct = bool(final["healthy"] > final["stagnant"] > final["distressed"])

    # Trajectory check: does distressed's trend_indicator actually DECLINE
    # from checkpoint 0.25 to 1.0 (as you'd expect for a business trending
    # into distress), and healthy stay flat/improve?
    distressed_declining = bool(pivot.loc["distressed", 1.0] < pivot.loc["distressed", 0.25])
    healthy_stable_or_improving = bool(pivot.loc["healthy", 1.0] >= pivot.loc["healthy", 0.25] - 2)  # small tolerance

    return {
        "trend_indicator_means_by_archetype_and_checkpoint": pivot.round(2).to_dict(),
        "final_checkpoint_ordering_correct": ordering_correct,
        "distressed_trend_declines_over_window": distressed_declining,
        "healthy_trend_stable_or_improving": healthy_stable_or_improving,
    }
