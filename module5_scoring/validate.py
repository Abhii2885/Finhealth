"""
Validates the composite score and grade against the hidden true_archetype
label, and separately audits the honest cost of the consistency-flag
penalty (how many healthy-archetype borrowers get docked despite the
underlying check having only ~40% precision - see Module 2 README).
"""

import pandas as pd


def validate_composite(result_df, ground_truth_df):
    m = result_df.merge(ground_truth_df[["borrower_id", "true_archetype", "is_gst_underreporter"]],
                         on="borrower_id", how="left")

    means = m.groupby("true_archetype")["composite_score"].mean().reindex(["healthy", "stagnant", "distressed"])
    ordering_correct = bool(means["healthy"] > means["stagnant"] > means["distressed"])

    grade_by_archetype = pd.crosstab(m["true_archetype"], m["grade"])

    return {
        "composite_means_by_archetype": means.round(2).to_dict(),
        "ordering_correct": ordering_correct,
    }, grade_by_archetype, m


def audit_consistency_penalty(m):
    """
    How many borrowers took the consistency penalty, and of those, how
    many were healthy-archetype (i.e. penalized despite the underlying
    signal being wrong for them) vs actually under-reporters. Reported
    plainly - this check was disclosed at ~40% precision in Module 2 and
    that cost shows up here as healthy borrowers losing points.
    """
    penalized = m[m["capacity_consistency_penalty"] < 0]
    if len(penalized) == 0:
        return {"n_penalized": 0}

    healthy_penalized = (penalized["true_archetype"] == "healthy").sum()
    actual_underreporters_penalized = penalized["is_gst_underreporter"].sum()

    return {
        "n_penalized": int(len(penalized)),
        "healthy_borrowers_penalized": int(healthy_penalized),
        "actual_underreporters_penalized": int(actual_underreporters_penalized),
        "avg_points_lost": round(penalized["capacity_consistency_penalty"].mean(), 2),
    }
