"""
Validates that each engineered feature actually separates by the hidden
true_archetype label (healthy / stagnant / distressed) - i.e. proves the
feature engineering captured real signal, rather than just asserting it.

This is a backtest, not a feature used anywhere downstream. Do not let
Module 5 see true_archetype.

For each feature, we know in advance whether "higher" should mean
healthier or riskier (defined in FEATURE_DIRECTION below) based on how
Module 1's generator was built. We check group means follow that expected
order and report it plainly - including if a feature doesn't separate,
rather than cherry-picking the ones that do.
"""

import pandas as pd

# True -> higher value = healthier (expect healthy > stagnant > distressed)
# False -> higher value = riskier (expect healthy < stagnant < distressed)
FEATURE_DIRECTION = {
    "balance_trend_pct": True,
    "monthly_inflow_volatility": False,
    "monthly_outflow_volatility": False,
    "txn_frequency_stability": False,
    "cheque_bounce_rate": False,
    "cheque_bounce_count_annualized": False,
    "turnover_growth_rate": True,
    "turnover_volatility": False,
    "headcount_growth_rate": True,
    "headcount_volatility": False,
    "wage_bill_growth_rate": True,
    "gst_ontime_filing_ratio": True,
    "gst_missed_filing_rate": False,
    "gst_avg_filing_delay_days": False,
}

ARCHETYPE_ORDER = ["healthy", "stagnant", "distressed"]


def validate_features(features_df, ground_truth_df):
    m = features_df.merge(ground_truth_df[["borrower_id", "true_archetype"]], on="borrower_id", how="left")

    results = []
    for feature, higher_is_healthier in FEATURE_DIRECTION.items():
        if feature not in m.columns:
            continue
        means = m.groupby("true_archetype")[feature].mean()
        means = means.reindex(ARCHETYPE_ORDER)
        if means.isna().any():
            results.append({"feature": feature, "healthy_mean": means.get("healthy"),
                             "stagnant_mean": means.get("stagnant"), "distressed_mean": means.get("distressed"),
                             "direction_correct": None, "note": "insufficient data to compare all 3 groups"})
            continue

        if higher_is_healthier:
            correct = means["healthy"] > means["stagnant"] > means["distressed"]
        else:
            correct = means["healthy"] < means["stagnant"] < means["distressed"]

        results.append({
            "feature": feature,
            "healthy_mean": round(means["healthy"], 4),
            "stagnant_mean": round(means["stagnant"], 4),
            "distressed_mean": round(means["distressed"], 4),
            "direction_correct": bool(correct),
            "note": "",
        })

    return pd.DataFrame(results)
