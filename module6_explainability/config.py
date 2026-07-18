"""
Module 6 - Explainability & Visualization Layer (Track 3)

v3: dashboard reorganized around the 5 Cs of Credit (full replacement of
the old 6-dimension structure, no dual mode). Per user feedback on the
first 5C pass: parameters show a SCORE (out of 10), not their weight
(weights stay a background calculation input, available via tooltip);
each C is expandable to its submetric breakdown; 5 selectable chart types;
RAG (red/amber/green) coloring on the composite and each C; a client-side
score-override capability with mandatory justification, captured to
localStorage + an export button (this is a standalone offline HTML file
with no backend, so that's the actual mechanism - not a fabricated "feeds
the model" claim); an auto-generated bottom-of-page commentary; and an
IDBI-style green/white visual theme.

SCOPE NOTE on the trend view (UNCHANGED from v1/v2): a true replay of
Module 5's full composite methodology at each historical checkpoint would
need to re-derive Modules 2-4's completeness/weights as of each past
point - a lot of re-plumbing for a secondary view. This module computes a
REAL trend from 3 robust point-in-time metrics only (average balance,
cheque bounce rate, GST on-time filing ratio), not a literal historical
replay of the 5C composite - say so plainly, still true after the
restructure, deliberately left as-is (see module6 README/plan).
"""

import os

DEFAULT_DATA_LAKE_DIR = os.path.join(os.path.dirname(__file__), "..", "module1_data_ingestion", "data_lake")
DEFAULT_FEATURES_DIR = os.path.join(os.path.dirname(__file__), "..", "module3_feature_engineering", "features_output")
DEFAULT_SCORING_DIR = os.path.join(os.path.dirname(__file__), "..", "module5_scoring", "scoring_output")
DEFAULT_SEGMENTATION_DIR = os.path.join(os.path.dirname(__file__), "..", "module4_segmentation", "segmentation_output")
DEFAULT_ML_DIR = os.path.join(os.path.dirname(__file__), "..", "module9_ml_layer", "ml_output")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "explainability_output")

DIMENSIONS = ["capacity", "character", "capital", "compliance", "collateral"]

DIMENSION_LABELS = {
    "capacity": "Capacity",
    "character": "Character",
    "capital": "Capital",
    "compliance": "Compliance",
    "collateral": "Collateral",
}

# Dimensions with exactly one scoring submetric - no "top driver" comparison
# is possible for these, same "nothing to compare" case drivers.py already
# had for the old repayment_credit_behavior dimension.
SINGLE_SUBMETRIC_DIMENSIONS = {"capital", "collateral"}

FEATURE_LABELS = {
    "current_ratio": "Current ratio",
    "leverage_ratio": "Leverage (debt / net worth)",
    "dscr": "Debt service coverage ratio",
    "interest_coverage_ratio": "Interest coverage ratio",
    "cash_flow_match_ratio": "Cash flow vs. declared turnover match",
    "revenue_cagr_3yr": "Revenue CAGR (3yr)",
    "projected_revenue_growth_rate": "Projected revenue growth",
    "customer_concentration_pct": "Customer concentration",
    "supplier_concentration_pct": "Supplier concentration",
    "bureau_score": "Bureau score",
    "civil_suit_years_since_active": "Civil suit status",
    "other_legal_dispute_years_since_active": "Other legal dispute status",
    "cheque_bounce_rate": "Cheque bounce rate",
    "owner_time_in_business_years": "Owner's time in business",
    "net_worth_to_assets_ratio": "Net worth / total assets",
    "covenant_compliance_flag": "Bank covenant compliance",
    "gst_ontime_filing_ratio": "GST on-time filing ratio",
    "utility_payment_timeliness": "Utility payment timeliness",
    "epfo_ontime_remittance_ratio": "EPFO on-time remittance ratio",
    "rent_payment_timeliness": "Rent payment timeliness",
    "salary_payment_timeliness": "Salary payment timeliness",
    "collateral_quality_score": "Collateral quality",
}

# Trend checkpoints: months into the shared recent 12-month window
# (cumulative from window start, not disjoint quarters)
TREND_CHECKPOINT_MONTHS = [3, 6, 9, 12]
TREND_WINDOW_MONTHS = 12  # bank's 365-day window is the binding constraint

# RAG (red/amber/green) thresholds, reusing GRADE_BANDS' existing B-Good
# (65) and D-Weak (35) cut points rather than inventing new ones - applied
# identically to the composite score and to every individual C's 0-100
# score.
RAG_GREEN_MIN = 65
RAG_AMBER_MIN = 35

# Parameter (submetric) scores are displayed out of this scale (not their
# weight - weights stay a background calculation input). Half-point
# granularity preserves real signal from the underlying continuous 0-100
# score without implying false precision.
PARAMETER_SCORE_SCALE = 10

# Per-submetric methodology text for the dashboard's "(i)" explainability
# button (per user instruction: "keep the current scoring logic but add an
# 'i' button for explainability" for the submetrics not covered by the
# lender's Score Band sheet - generalized here to ALL submetrics, not just
# those three, so every row is equally explainable). Duplicated/hand-
# summarized from module5_scoring/config.py's TIERED_ANCHORS and
# SCORING_SUBMETRICS (not imported cross-module, same convention as
# GRADE_BANDS above) - keep in sync if Module 5's bands change.
METHODOLOGY_TEXT = {
    # Capacity
    "dscr": "Tiered per lender rubric: <1.0x scores 0-3, 1.0-1.2x scores 3-6, 1.2-1.5x scores 6-9, >1.5x scores 10 (linear interpolation between cutoffs).",
    "cash_flow_match_ratio": "Target-band scoring: bank credit inflows matching 70-80% of declared turnover score 10; the score decays symmetrically the further the actual ratio strays above or below that band, reaching 0 roughly 30 points outside it. Neither a very low nor a very high match is 'better'.",
    "current_ratio": "Tiered per lender rubric: <1.00 scores 0-3, 1.00-1.33 scores 3-6, 1.33-2.00 scores 6-9, >2.00 scores 10.",
    "interest_coverage_ratio": "Tiered per lender rubric: <1.5x scores 0-3, 1.5-5.0x scores 3-6, 5.0-7.0x scores 6-9, >7.0x scores 10.",
    "leverage_ratio": "Tiered per lender rubric, lower is better (Debt / Net-worth basis): <1.0x scores 10, 1.0-2.0x scores 9-10, 2.0-5.0x scores 6-9, 5.0-7.0x scores 3-6, >7.0x scores 0-3.",
    "revenue_cagr_3yr": "Tiered per lender rubric: 0% or negative scores 0, 0-5% scores 0-3, 5-10% scores 3-6, 10-15% scores 6-9, >15% scores 10.",
    "projected_revenue_growth_rate": "Tiered, same bands as Revenue CAGR (3yr) — self-reported management projection, treated as a lower-trust signal than the audited CAGR.",
    "customer_concentration_pct": "Tiered, lower concentration is healthier: <10% scores 10, 10-14% scores 9-10, 14-15% scores 6-9, 15-20% scores 4-6, >20% scores 0-4.",
    "supplier_concentration_pct": "Tiered, same bands as Customer concentration (lower is healthier).",
    # Character
    "bureau_score": "Tiered on the CIBIL-style 300-900 scale: <600 scores 0-3, 600-700 scores 3-6, 700-800 scores 6-9, >800 scores 10.",
    "civil_suit_years_since_active": "Tiered by recency: an active dispute or one resolved <3yr ago scores 0-3, 3-5yr ago scores 3-6, 5-10yr ago scores 6-9, >10yr ago or never having had one scores 10. Open disputes are penalised more heavily than closed ones.",
    "other_legal_dispute_years_since_active": "Tiered, same recency bands as Civil suit status.",
    "cheque_bounce_rate": "Tiered, lower is better: 0% scores 10, 0-2% scores 7-10, 2-5% scores 4-7, 5-10% scores 0-4, >10% scores 0.",
    "owner_time_in_business_years": "Tiered: <3yr scores 0-3, 3-10yr scores 3-6, 10-15yr scores 6-9, >15yr scores 10.",
    # Capital
    "net_worth_to_assets_ratio": "Tiered: <25% scores 0-3, 25-50% scores 3-6, 50-60% scores 6-9, >60% scores 10.",
    # Compliance — direct ratio*10 read (v5, per explicit user instruction),
    # NOT a percentile rank against the batch — 50% on-time scores 5/10,
    # 80% scores 8/10, regardless of how the rest of the population is
    # doing. Not part of the lender's Score Band sheet.
    "covenant_compliance_flag": "Direct read: the loan's most recent covenant test outcome, compliant = 10/10, breached = 0/10. Not a percentile rank.",
    "gst_ontime_filing_ratio": "Direct read: on-time filing ratio × 10 (e.g. 50% on-time = 5/10, 80% = 8/10), over the trailing 6 months. Not a percentile rank — the same ratio scores the same regardless of the rest of the batch.",
    "utility_payment_timeliness": "Direct read: on-time payment ratio × 10 over the trailing 6 months. Not a percentile rank.",
    "epfo_ontime_remittance_ratio": "Direct read: on-time remittance ratio × 10 over the trailing 6 months. Not a percentile rank.",
    "rent_payment_timeliness": "Direct read: on-time payment ratio × 10 over the trailing 6 months. Not a percentile rank.",
    "salary_payment_timeliness": "Direct read: on-time payment ratio × 10 over the trailing 6 months. Not a percentile rank.",
    # Collateral
    "collateral_quality_score": "Lookup table by collateral type × construction status — not part of the lender's Score Band sheet. Residential (constructed=10, bare plot=7.5) > Commercial (constructed=7, bare plot=5) > Industrial (constructed=4, bare plot=2).",
}

# --- ML layer (Module 9) surfacing: chips + collapsed detail card ---
# Every string names the algorithm that produced the value, so provenance
# is explicit on the dashboard: nothing ML-generated is ever shown as if
# it came from the rule-based scorecard, and vice versa. The champion
# (Module 5 composite) remains the only score of record - all of this is
# advisory display.
ML_ADVISORY_NOTE = (
    "Generated by ML models running in parallel (champion–challenger). "
    "Advisory only — does not change the score of record."
)
ML_CHIP_DIVERGENCE_LABEL = "⚠ Model divergence — review advised"
ML_CHIP_DIVERGENCE_TOOLTIP = (
    "The Gradient Boosting challenger model's score differs materially from the "
    "rule-based scorecard for this borrower. Advisory: review the file more closely. "
    "Does not change the score."
)
ML_CHIP_ANOMALY_LABEL = "◆ Unusual profile (ML)"
ML_CHIP_ANOMALY_TOOLTIP = (
    "Isolation Forest anomaly detection flags this borrower's overall data pattern "
    "as statistically unusual for this population — not necessarily unhealthy. "
    "Advisory: verify the underlying inputs. Does not change the score."
)
# Tag shown on a submetric row the ML explanation names as worth revisiting.
ML_ADVISED_TAG_LABEL = "ML"
ML_ADVISED_TAG_TOOLTIP = "The ML challenger's explanation names this submetric as a top contributor to its disagreement with the scorecard."

# Duplicated from module9_ml_layer/config.py's DIVERGENCE_FLAG_THRESHOLD -
# needed client-side so the dashboard can recompute flagged_for_review
# live after a submetric override changes the champion score. Keep in
# sync if Module 9's threshold changes.
ML_DIVERGENCE_FLAG_THRESHOLD = 25.0

# Generic explainer for each C's "Overall <C> score" row - same weighted-
# average mechanism for all 5 Cs, so one shared string rather than 5
# near-duplicates.
DIMENSION_METHODOLOGY_NOTE = (
    "Weighted average of this C's submetric scores below, using each "
    "submetric's effective weight. Weights renormalize automatically when "
    "a submetric is not applicable or has insufficient data for this "
    "borrower, so the remaining submetrics absorb its share rather than "
    "the score being penalized for a missing input."
)

# Duplicated from module5_scoring/config.py's GRADE_BANDS (not imported
# cross-module - this project runs each module as a standalone script with
# its own sys.path, so a small stable display constant is duplicated
# rather than reaching across directories). Needed client-side so an
# override that changes the composite score can also recompute the grade
# without a server round-trip. Keep in sync if Module 5's bands change.
GRADE_BANDS = [
    (80, 100, "A - Strong"),
    (65, 80, "B - Good"),
    (50, 65, "C - Fair"),
    (35, 50, "D - Weak"),
    (0, 35, "E - Poor"),
]
