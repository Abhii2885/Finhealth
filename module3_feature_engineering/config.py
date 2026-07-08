"""
Module 3 - Dimension Feature Engineering (Track 3)

Turns Module 1's raw data lake into numeric, per-dimension features,
respecting Module 2's dimension_availability output: a dimension marked
not_applicable or not_computable_in_prototype for a borrower gets NO
feature value (null), never a zero. Module 5 (scoring) is responsible for
re-normalizing weights over whichever dimensions actually have features.

This module does NOT produce a 0-100 sub-score - that's Module 5's job.
This is the feature layer underneath it.
"""

import os

DEFAULT_DATA_LAKE_DIR = os.path.join(os.path.dirname(__file__), "..", "msme_data_gen", "data_lake")
DEFAULT_QUALITY_DIR = os.path.join(os.path.dirname(__file__), "..", "module2_data_quality", "quality_output")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "features_output")

GST_EPFO_MONTHS = 24
BANK_DAYS = 365

# Window used for "recent" trend features (last N of the GST/EPFO periods,
# or last N days of bank data) vs the full-window baseline.
TREND_WINDOW_MONTHS = 3
TREND_WINDOW_DAYS = 90

# Dimensions this prototype CANNOT compute at all, regardless of borrower -
# carried forward from Module 2's dimension_availability (concentration_risk)
# plus one new one Module 3 discovers: collateral/coverage has no source in
# Module 1 either. Both are systemic gaps, not per-borrower data problems.
NOT_COMPUTABLE_DIMENSIONS = ["concentration_risk", "collateral_coverage"]

# Sub-features that are individually unavailable even within a dimension
# that's otherwise partially computable (bureau, utility, credit-limit data
# have no Module 1 generator). Documented so nobody mistakes "we computed
# SOME repayment features" for "we computed all of them."
UNAVAILABLE_SUBFEATURES = {
    "repayment_credit_behavior": ["bureau_dpd_history", "credit_limit_utilization_pct"],
    "compliance_discipline": ["utility_payment_timeliness"],
}
