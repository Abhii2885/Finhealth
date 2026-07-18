"""
Champion-challenger comparison + validation.

Comparison: per-borrower divergence between the champion (Module 5's
rule-based composite_score) and the challenger (Gradient Boosting
challenger_score), both already on the same 0-100 scale. Divergence past
config.DIVERGENCE_FLAG_THRESHOLD is flagged for manual review - this
module never resolves a disagreement or overrides the champion, it only
surfaces it, which is the entire point of running a challenger in
parallel rather than replacing the champion outright.

Validation: same discipline module3/module5's validate.py already
applies to the rule-based scorecard - check the challenger_score and the
anomaly flag against the hidden true_archetype and report plainly,
including if something doesn't separate cleanly, rather than only
reporting the checks that pass.
"""

import pandas as pd
from config import DIVERGENCE_FLAG_THRESHOLD

ARCHETYPE_ORDER = ["healthy", "stagnant", "distressed"]


def build_comparison(champion_df, challenger_df, anomaly_df):
    out = champion_df[["borrower_id", "composite_score", "grade"]].rename(columns={"composite_score": "champion_score"})
    out = out.merge(challenger_df, on="borrower_id", how="left")
    out = out.merge(anomaly_df, on="borrower_id", how="left")

    out["divergence"] = (out["challenger_score"] - out["champion_score"]).round(2)
    out["abs_divergence"] = out["divergence"].abs()
    out["flagged_for_review"] = out["abs_divergence"] >= DIVERGENCE_FLAG_THRESHOLD

    return out.sort_values("abs_divergence", ascending=False).reset_index(drop=True)


def validate_challenger(comparison_df, ground_truth_df):
    m = comparison_df.merge(ground_truth_df[["borrower_id", "true_archetype"]], on="borrower_id", how="left")

    challenger_means = m.groupby("true_archetype")["challenger_score"].mean().reindex(ARCHETYPE_ORDER)
    champion_means = m.groupby("true_archetype")["champion_score"].mean().reindex(ARCHETYPE_ORDER)
    anomaly_rate_by_archetype = m.groupby("true_archetype")["is_anomaly"].mean().reindex(ARCHETYPE_ORDER)

    challenger_ordering_correct = bool(
        challenger_means["healthy"] > challenger_means["stagnant"] > challenger_means["distressed"]
    )

    return {
        "challenger_means_by_archetype": {k: round(v, 2) for k, v in challenger_means.items()},
        "champion_means_by_archetype": {k: round(v, 2) for k, v in champion_means.items()},
        "challenger_ordering_correct": challenger_ordering_correct,
        "note": "challenger_ordering_correct uses the same healthy>stagnant>distressed backtest as the champion's own validate.py - both should agree on population-level ordering even though they use different mechanisms (rule-based tiers vs. learned nonlinear splits).",
        "anomaly_rate_by_archetype": {k: round(v, 3) for k, v in anomaly_rate_by_archetype.items()},
        "anomaly_rate_note": "Not a pass/fail check - anomaly detection flags UNUSUAL feature profiles, not unhealthy ones. A higher rate among distressed borrowers would be a plausible finding (distress often looks structurally different) but is not required for this module to be considered correct.",
        "n_flagged_for_review": int(comparison_df["flagged_for_review"].sum()),
        "pct_flagged_for_review": round(float(comparison_df["flagged_for_review"].mean() * 100), 1),
    }
