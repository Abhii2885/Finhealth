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
#
# Deliberately excluded (not archetype-driven by construction, so no
# ordering is expected - same precedent as Module 5 already excluding
# avg_monthly_turnover_inr as a "size measure, not a health signal"):
# cash_flow_match_ratio (band, not monotonic), customer/supplier_
# concentration_pct (structural, independent of archetype in Module 1),
# owner_time_in_business_years (correlated with business_age, not
# archetype), collateral_type/construction_status/estimated_value_inr
# (categorical / turnover-anchored, not archetype-driven).
FEATURE_DIRECTION = {
    "current_ratio": True,
    "leverage_ratio": False,
    "dscr": True,
    "interest_coverage_ratio": True,
    "revenue_cagr_3yr": True,
    "projected_revenue_growth_rate": True,
    "bureau_score": True,
    # True (not False): this is years-SINCE-active, not a severity flag -
    # higher means "longer since any trouble" (or never had one at all, via
    # the NEVER_HAD_DISPUTE_SENTINEL_YEARS sentinel), which is HEALTHIER.
    "civil_suit_years_since_active": True,
    "other_legal_dispute_years_since_active": True,
    "cheque_bounce_rate": False,
    "cheque_bounce_count_annualized": False,
    "net_worth_to_assets_ratio": True,
    "gst_ontime_filing_ratio": True,
    "gst_missed_filing_rate": False,
    "gst_avg_filing_delay_days": False,
    "epfo_ontime_remittance_ratio": True,
    "utility_payment_timeliness": True,
    "rent_payment_timeliness": True,
    "salary_payment_timeliness": True,
    "covenant_compliance_flag": True,
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
