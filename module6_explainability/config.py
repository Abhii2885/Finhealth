"""
Module 6 - Explainability & Visualization Layer (Track 3)

Three deliverables, per the architecture doc:
1. Radar/spider chart across dimensions - "core visual deliverable"
2. Top drivers per dimension (what's pulling the score up/down)
3. Trend view (score improving/declining over recent quarters)

SCOPE NOTE on (3): a true quarterly trend would replay Modules 2-5's full
methodology at each historical checkpoint (recomputing completeness
tiers, weights, growth features, etc. as of each past quarter). That's a
lot of re-plumbing for a "nice to have" view, and growth/volatility
features are fragile on short truncated windows (a 3-month slice can't
compute a meaningful "first-3-months vs last-3-months" growth rate).
Instead, this module computes a REAL trend from robust point-in-time
metrics only (average balance, cheque bounce rate, GST on-time filing
ratio) at 4 cumulative checkpoints within the shared recent 12-month
window (bank data's 365-day window is the binding constraint - GST/EPFO
have 24 months but are truncated to align). This is directional and
genuinely computed from the data, but it is NOT the same composite score
methodology as Module 5 - say so plainly, don't imply it's a literal
historical replay of the final score.
"""

import os

DEFAULT_DATA_LAKE_DIR = os.path.join(os.path.dirname(__file__), "..", "msme_data_gen", "data_lake")
DEFAULT_FEATURES_DIR = os.path.join(os.path.dirname(__file__), "..", "module3_feature_engineering", "features_output")
DEFAULT_SCORING_DIR = os.path.join(os.path.dirname(__file__), "..", "module5_scoring", "scoring_output")
DEFAULT_SEGMENTATION_DIR = os.path.join(os.path.dirname(__file__), "..", "module4_segmentation", "segmentation_output")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "explainability_output")

DIMENSIONS = [
    "liquidity_cash_flow",
    "repayment_credit_behavior",
    "revenue_growth_signal",
    "operational_stability",
    "compliance_discipline",
]

DIMENSION_LABELS = {
    "liquidity_cash_flow": "Liquidity & Cash Flow",
    "repayment_credit_behavior": "Repayment & Credit Behavior",
    "revenue_growth_signal": "Revenue & Growth Signal",
    "operational_stability": "Operational Stability",
    "compliance_discipline": "Compliance Discipline",
    "concentration_risk": "Concentration Risk (not computable - no data source)",
}

FEATURE_LABELS = {
    "balance_trend_pct": "Bank balance trend",
    "monthly_inflow_volatility": "Inflow volatility",
    "monthly_outflow_volatility": "Outflow volatility",
    "txn_frequency_stability": "Transaction regularity",
    "cheque_bounce_rate": "Cheque bounce rate",
    "turnover_growth_rate": "Turnover growth",
    "turnover_volatility": "Turnover volatility",
    "headcount_growth_rate": "Headcount growth",
    "headcount_volatility": "Headcount volatility",
    "wage_bill_growth_rate": "Wage bill growth",
    "gst_ontime_filing_ratio": "GST on-time filing ratio",
    "gst_missed_filing_rate": "GST missed-filing rate",
    "gst_avg_filing_delay_days": "GST average filing delay",
}

# Trend checkpoints: months into the shared recent 12-month window
# (cumulative from window start, not disjoint quarters)
TREND_CHECKPOINT_MONTHS = [3, 6, 9, 12]
TREND_WINDOW_MONTHS = 12  # bank's 365-day window is the binding constraint
