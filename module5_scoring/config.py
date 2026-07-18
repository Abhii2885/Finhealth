"""
Module 5 - Scoring & Aggregation Engine (Track 3)

v3: restructured around the 5 Cs of Credit. v5: Compliance moved off
percentile ranking entirely (see below) - the remaining Capacity/Character/
Capital submetrics not covered by the lender's Score Band sheet still use
percentile rank (deliberately not a trained model for those - this track
doesn't require labeled default outcomes, and percentile rank is robust to
the skewed absolute values already flagged in Module 1, e.g. bank
balances). Four submetric groups need a genuinely different scoring mode:

- dscr / current_ratio / leverage_ratio / interest_coverage_ratio /
  revenue_cagr_3yr / etc: "tiered" - piecewise-linear interpolation across
  the lender's Score Band rubric anchor points (see TIERED_ANCHORS),
  independent of where the rest of the portfolio happens to sit.
- cash_flow_match_ratio: "band_distance" - a symmetric target BAND
  (70-80%), not a "higher is better" direction. A borrower matching 95%
  isn't healthier than one matching 75%; distance from the band in either
  direction reduces the score.
- collateral_quality_score: "lookup_table" - categorical (type x
  construction-status), not a numeric feature at all.
- All 6 Compliance submetrics (covenant_compliance_flag,
  gst_ontime_filing_ratio, utility/epfo/rent/salary timeliness):
  "direct_ratio" - a straight ratio*100 read (50% on-time = 5/10, 80% =
  8/10), NOT a percentile rank against the batch - per explicit user
  instruction. This makes Compliance scores absolute/portable (comparable
  across batches or a lone new applicant), unlike percentile rank which
  needs a population to rank against.

Pipeline: Module 3 feature -> submetric score (0-100, by whichever method
applies) -> weighted average within each C using Module 4's per-borrower
effective SUBweights -> weighted composite using Module 4's per-borrower
effective DIMENSION weights -> composite 0-100 -> grade band.
"""

import os

DEFAULT_FEATURES_DIR = os.path.join(os.path.dirname(__file__), "..", "module3_feature_engineering", "features_output")
DEFAULT_SEGMENTATION_DIR = os.path.join(os.path.dirname(__file__), "..", "module4_segmentation", "segmentation_output")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "scoring_output")

CASH_FLOW_MATCH_TARGET_LOW = 70.0
CASH_FLOW_MATCH_TARGET_HIGH = 80.0
CASH_FLOW_MATCH_DECAY_WIDTH = 30.0  # points outside the band before score hits 0

COLLATERAL_QUALITY_LOOKUP = {
    ("residential", "constructed"): 100.0,
    ("residential", "bare_plot"): 75.0,
    ("commercial", "constructed"): 70.0,
    ("commercial", "bare_plot"): 50.0,
    ("industrial", "constructed"): 40.0,
    ("industrial", "bare_plot"): 20.0,
}

# --- Lender-supplied "Score Band" tiered scoring (v4) ---
# The lender's rubric gives 4 tiers per submetric (0-3 / 4-6 / 7-9 / 10),
# described as inequalities ("<=1.00", ">=7", "0-5%", ...). Rather than
# hard-reset each tier to its own labeled sub-range (which would create
# arbitrary score jumps exactly AT each boundary and gaps where two rows
# don't share an edge, e.g. Leverage's "<=5" / ">=7" - nothing names 5-7),
# each submetric is expressed as an ascending (raw_value, score) anchor
# list and scored by continuous piecewise-linear interpolation - see
# _tiered_score in dimension_scores.py. This satisfies the tier bands
# exactly AT their named cutoffs, resolves gaps between rows smoothly, and
# matches the explicit instruction that a value near the WORSE end of its
# tier should score toward that tier's floor and a value near the BETTER
# end should score toward its ceiling. Values outside the outermost
# anchors clamp flat (0 or 10) - there is no data beyond the "10" tier's
# named edge, so nothing to interpolate against.
#
# Units: each anchor list is in the SAME units Module 3 already stores
# for that raw feature (ratios as ratios, concentration/net-worth as the
# percentage-point or fraction Module 3 already emits - see each list's
# comment). "floor_at_zero" submetrics (CAGR, projected growth) score a
# flat 0 for v<=0 per the explicit "0% or negative scores zero" rule,
# rather than extrapolating the interpolation below their first anchor.
TIERED_ANCHORS = {
    # Capacity
    "current_ratio": [(0.0, 0.0), (1.00, 3.0), (1.33, 6.0), (2.0, 9.0)],  # ratio; >2.0 -> 10
    "leverage_ratio": [(1.0, 10.0), (2.0, 9.0), (5.0, 6.0), (7.0, 3.0), (10.0, 0.0)],  # ratio; <1.0 -> 10
    "dscr": [(0.0, 0.0), (1.0, 3.0), (1.2, 6.0), (1.5, 9.0)],  # ratio; >1.5 -> 10
    "interest_coverage_ratio": [(0.0, 0.0), (1.5, 3.0), (5.0, 6.0), (7.0, 9.0)],  # ratio; >7.0 -> 10
    "revenue_cagr_3yr": [(0.0, 0.0), (0.05, 3.0), (0.10, 6.0), (0.15, 9.0)],  # fraction; >0.15 -> 10; floor_at_zero
    "projected_revenue_growth_rate": [(0.0, 0.0), (0.05, 3.0), (0.10, 6.0), (0.15, 9.0)],  # fraction; >0.15 -> 10; floor_at_zero
    "customer_concentration_pct": [(10.0, 10.0), (14.0, 9.0), (15.0, 6.0), (20.0, 4.0), (90.0, 0.0)],  # pct-points; <10 -> 10
    "supplier_concentration_pct": [(10.0, 10.0), (14.0, 9.0), (15.0, 6.0), (20.0, 4.0), (90.0, 0.0)],  # pct-points; <10 -> 10

    # Character
    "bureau_score": [(300.0, 0.0), (600.0, 3.0), (700.0, 6.0), (800.0, 9.0)],  # CIBIL scale; >800 -> 10
    # years-since-last-active (0 = active now, sentinel 100 = never had one):
    "civil_suit_years_since_active": [(0.0, 0.0), (3.0, 3.0), (5.0, 6.0), (10.0, 9.0)],  # >10yr (incl. sentinel) -> 10
    "other_legal_dispute_years_since_active": [(0.0, 0.0), (3.0, 3.0), (5.0, 6.0), (10.0, 9.0)],
    "cheque_bounce_rate": [(0.0, 10.0), (0.02, 7.0), (0.05, 4.0), (0.10, 0.0)],  # fraction (0-0.10 clip); descending
    "owner_time_in_business_years": [(0.0, 0.0), (3.0, 3.0), (10.0, 6.0), (15.0, 9.0)],  # years; >15 -> 10

    # Capital
    "net_worth_to_assets_ratio": [(0.0, 0.0), (0.25, 3.0), (0.50, 6.0), (0.60, 9.0)],  # fraction; >0.60 -> 10
}

# Submetrics whose tiered score floors at exactly 0 for v<=0, rather than
# extrapolating the interpolation below the first anchor - per the user's
# explicit "0% or negative CAGR scores zero" rule, extended to projected
# revenue growth for consistency (same tier structure, same sign risk).
TIERED_FLOOR_AT_ZERO = {"revenue_cagr_3yr", "projected_revenue_growth_rate"}

# (dimension, submetric) -> scoring method + params. Keys mirror Module 4's
# SUBWEIGHTS_BY_DIM exactly (same 22 submetrics) - deliberately, since
# Module 4's effective_subweight columns are looked up by this same key.
SCORING_SUBMETRICS = {
    ("capacity", "dscr"): {"method": "tiered"},
    ("capacity", "cash_flow_match_ratio"): {"method": "band_distance"},
    ("capacity", "current_ratio"): {"method": "tiered"},
    ("capacity", "interest_coverage_ratio"): {"method": "tiered"},
    ("capacity", "leverage_ratio"): {"method": "tiered"},
    ("capacity", "revenue_cagr_3yr"): {"method": "tiered"},
    ("capacity", "projected_revenue_growth_rate"): {"method": "tiered"},
    ("capacity", "customer_concentration_pct"): {"method": "tiered"},
    ("capacity", "supplier_concentration_pct"): {"method": "tiered"},

    ("character", "bureau_score"): {"method": "tiered"},
    ("character", "civil_suit_years_since_active"): {"method": "tiered"},
    ("character", "other_legal_dispute_years_since_active"): {"method": "tiered"},
    ("character", "cheque_bounce_rate"): {"method": "tiered"},
    ("character", "owner_time_in_business_years"): {"method": "tiered"},

    ("capital", "net_worth_to_assets_ratio"): {"method": "tiered"},

    ("compliance", "covenant_compliance_flag"): {"method": "direct_ratio"},
    ("compliance", "gst_ontime_filing_ratio"): {"method": "direct_ratio"},
    ("compliance", "utility_payment_timeliness"): {"method": "direct_ratio"},
    ("compliance", "epfo_ontime_remittance_ratio"): {"method": "direct_ratio"},
    ("compliance", "rent_payment_timeliness"): {"method": "direct_ratio"},
    ("compliance", "salary_payment_timeliness"): {"method": "direct_ratio"},

    ("collateral", "collateral_quality_score"): {"method": "lookup_table", "columns": ["collateral_type", "construction_status"]},
}

# Module 2's GST-vs-bank consistency check has precision ~0.40 / recall
# ~0.29 (see module2_data_quality/README.md) - real signal, but weak
# standalone. Applied as a small, visible, capped penalty to Capacity's
# revenue_cagr_3yr submetric score (its natural home under the 5C
# restructure - a revenue-integrity signal), not blended silently into a
# continuous feature, specifically so it stays auditable given its known
# false-positive rate.
CONSISTENCY_FLAG_PENALTY = {
    "bank_inflow_much_higher_than_declared": -10,  # possible GST under-reporting
    "bank_inflow_much_lower_than_declared": -5,     # possible under-banked/cash-heavy, weaker signal
    "consistent": 0,
    "unscoreable": 0,
}

# Composite score -> letter grade. Assumptions, not calibrated against any
# real portfolio - tune here. Module 5's original README already flagged
# the A-band as too aggressive for the old 6-dimension distribution; worth
# re-checking once the 5C composite distribution is populated, not
# blindly carried forward.
GRADE_BANDS = [
    (80, 100, "A - Strong"),
    (65, 80, "B - Good"),
    (50, 65, "C - Fair"),
    (35, 50, "D - Weak"),
    (0, 35, "E - Poor"),
]
