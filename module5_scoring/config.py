"""
Module 5 - Scoring & Aggregation Engine (Track 3)

Rule-based, percentile-rank scoring - deliberately NOT a trained ML model.
Per the architecture doc, this track doesn't require labeled default
outcomes, and percentile ranking is distribution-free (robust to the
skewed/outlier-heavy absolute values we already flagged in Module 1, e.g.
bank balances) and directly explainable ("you're in the Nth percentile of
borrowers on this metric").

Pipeline: Module 3 feature -> percentile rank (0-100, direction-aware) ->
average within dimension -> weight by Module 4's per-borrower effective
weights -> composite 0-100 -> grade band.
"""

import os

DEFAULT_FEATURES_DIR = os.path.join(os.path.dirname(__file__), "..", "module3_feature_engineering", "features_output")
DEFAULT_SEGMENTATION_DIR = os.path.join(os.path.dirname(__file__), "..", "module4_segmentation", "segmentation_output")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "scoring_output")

# Which Module 3 features feed each dimension's score, and their direction.
# True = higher raw value is healthier. False = higher raw value is riskier.
# Deliberately a SUBSET of Module 3's output columns - things like
# avg_monthly_turnover_inr or *_periods_observed are size/data-quantity
# measures, not health signals, and are excluded from scoring on purpose.
DIMENSION_SCORING_FEATURES = {
    "liquidity_cash_flow": {
        "balance_trend_pct": True,
        "monthly_inflow_volatility": False,
        "monthly_outflow_volatility": False,
        "txn_frequency_stability": False,
    },
    "repayment_credit_behavior": {
        "cheque_bounce_rate": False,
    },
    "revenue_growth_signal": {
        "turnover_growth_rate": True,
        "turnover_volatility": False,
    },
    "operational_stability": {
        "headcount_growth_rate": True,
        "headcount_volatility": False,
        "wage_bill_growth_rate": True,
    },
    "compliance_discipline": {
        "gst_ontime_filing_ratio": True,
        "gst_missed_filing_rate": False,
        "gst_avg_filing_delay_days": False,
    },
}

# Module 2's GST-vs-bank consistency check has precision ~0.40 / recall
# ~0.29 (see module2_data_quality/README.md) - real signal, but weak
# standalone. Applied as a small, visible, capped penalty to the revenue
# dimension score rather than blended silently into a continuous feature,
# specifically so it stays auditable given its known false-positive rate.
CONSISTENCY_FLAG_PENALTY = {
    "bank_inflow_much_higher_than_declared": -10,  # possible GST under-reporting
    "bank_inflow_much_lower_than_declared": -5,     # possible under-banked/cash-heavy, weaker signal
    "consistent": 0,
    "unscoreable": 0,
}

# Composite score -> letter grade. Assumptions, not calibrated against any
# real portfolio - tune here.
GRADE_BANDS = [
    (80, 100, "A - Strong"),
    (65, 80, "B - Good"),
    (50, 65, "C - Fair"),
    (35, 50, "D - Weak"),
    (0, 35, "E - Poor"),
]
