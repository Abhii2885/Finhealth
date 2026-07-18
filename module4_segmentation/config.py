"""
Module 4 - Segmentation & Scoring-Eligibility Policy (Track 3)

v3: restructured around the 5 Cs of Credit (Capacity/Character/Capital/
Compliance/Collateral), replacing the old 6-dimension architecture-doc
structure entirely (full replacement, not a dual-mode system).

Key design simplification found during the 5C restructure: the user's
three "conditional sub-weighting" requirements (Character redistributes
when bureau is unavailable; Compliance re-ranks when covenants are absent;
Capacity excludes balance-sheet-dependent ratios when unavailable) do NOT
need separate conditional tables. A single flat sub-weight table per C,
run through the SAME exclude-and-renormalize mechanism this module already
had for whole dimensions - just applied one level deeper, to submetrics
within a C - produces every conditional behavior asked for automatically,
because renormalizing after excluding an item preserves the relative
proportion of what remains. See segmentation.py.

Base weights sum to 1.0 across the 5 Cs. Sub-weights within each C also
sum to 1.0 (relative weight WITHIN that C, before being scaled by the C's
own base weight). All numbers below are assumptions, not derived from any
lender's actual risk model - tune here, same as the old BASE_DIMENSION_
WEIGHTS always was.
"""

import os

DEFAULT_QUALITY_DIR = os.path.join(os.path.dirname(__file__), "..", "module2_data_quality", "quality_output")
DEFAULT_FEATURES_DIR = os.path.join(os.path.dirname(__file__), "..", "module3_feature_engineering", "features_output")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "segmentation_output")

BASE_DIMENSION_WEIGHTS = {
    "capacity": 0.30,
    "character": 0.25,
    "capital": 0.20,
    "compliance": 0.15,
    "collateral": 0.10,
}
assert abs(sum(BASE_DIMENSION_WEIGHTS.values()) - 1.0) < 1e-9

# Capacity: DSCR leads (per explicit user instruction - loan-type-
# conditional sub-weighting was considered and dropped in favor of this
# single fixed scheme), then cash-flow match, then liquidity, then
# interest coverage, then the remaining metrics. Supplier/customer
# concentration retained under Capacity (not a separate dimension) per
# explicit user instruction.
CAPACITY_SUBWEIGHTS = {
    "dscr": 0.22,
    "cash_flow_match_ratio": 0.18,
    "current_ratio": 0.14,
    "interest_coverage_ratio": 0.10,
    "leverage_ratio": 0.10,
    "revenue_cagr_3yr": 0.10,
    "projected_revenue_growth_rate": 0.06,
    "customer_concentration_pct": 0.05,
    "supplier_concentration_pct": 0.05,
}
assert abs(sum(CAPACITY_SUBWEIGHTS.values()) - 1.0) < 1e-9

# Character: bureau highest when available (redistributes proportionally
# among civil suits / other disputes / time-in-business / bounce rate when
# it isn't - see segmentation.py, this is the exclude+renormalize
# mechanism, not a separate table). cheque_bounce_rate lives here (moved
# from the old repayment_credit_behavior dimension per explicit user
# instruction - a behavioral reliability signal).
CHARACTER_SUBWEIGHTS = {
    "bureau_score": 0.50,
    "civil_suit_years_since_active": 0.18,
    "other_legal_dispute_years_since_active": 0.13,
    "cheque_bounce_rate": 0.11,
    "owner_time_in_business_years": 0.08,
}
assert abs(sum(CHARACTER_SUBWEIGHTS.values()) - 1.0) < 1e-9

# Capital: single submetric - net worth as a share of total assets.
CAPITAL_SUBWEIGHTS = {"net_worth_to_assets_ratio": 1.0}

# Compliance: covenant compliance highest IF a covenant exists; when it
# doesn't (not_applicable, excluded), the remaining weights renormalize
# and GST becomes highest automatically - hand-verified in the README/plan
# that this exclude+renormalize mechanism reproduces the user's exact
# stated no-covenant ordering (gst > utility > epfo > rent > salary)
# without a second table.
COMPLIANCE_SUBWEIGHTS = {
    "covenant_compliance_flag": 0.30,
    "gst_ontime_filing_ratio": 0.25,
    "utility_payment_timeliness": 0.18,
    "epfo_ontime_remittance_ratio": 0.12,
    "rent_payment_timeliness": 0.10,
    "salary_payment_timeliness": 0.05,
}
assert abs(sum(COMPLIANCE_SUBWEIGHTS.values()) - 1.0) < 1e-9

# Collateral: single submetric - the type x construction-status lookup
# score computed in Module 5.
COLLATERAL_SUBWEIGHTS = {"collateral_quality_score": 1.0}

SUBWEIGHTS_BY_DIM = {
    "capacity": CAPACITY_SUBWEIGHTS,
    "character": CHARACTER_SUBWEIGHTS,
    "capital": CAPITAL_SUBWEIGHTS,
    "compliance": COMPLIANCE_SUBWEIGHTS,
    "collateral": COLLATERAL_SUBWEIGHTS,
}

# insufficient_data submetrics aren't excluded outright - there IS some
# data, just not enough to fully trust (Module 2's threshold). Included at
# a discount rather than full weight. Assumption, not derived - tune it if
# your team has a better basis.
INSUFFICIENT_DATA_WEIGHT_MULTIPLIER = 0.5

# A borrower needs at least this many of the 5 Cs carrying SOME weight to
# get a composite score at all. Below this, Module 5 should refuse to
# score rather than produce a number built on 1-2 C's dressed up as a full
# health score. Note this is now a stricter bar than the old 6-dimension
# version (3-of-5 = 60% vs the old 3-of-6 = 50%) - carried forward as the
# same raw number, but worth re-examining given the denominator shrank.
MIN_DIMENSIONS_FOR_SCORING = 3
