"""
Module 4 - Segmentation & Scoring-Eligibility Policy (Track 3)

IMPORTANT SCOPE NOTE: the architecture doc's original Module 4 ("route
borrower to Tier A/B/C, each tier gets a fixed dimension set") is already
substantially done, at finer granularity, by Module 2 (quality_tier:
Full/Partial/Thin, re-derived from real completeness) and Module 3
(per-borrower per-dimension availability: available / insufficient_data /
not_applicable / not_computable_in_prototype). Rebuilding a coarse 3-bucket
router on top of that would be a step BACKWARD in precision.

What Module 2/3 don't do yet, and what this module actually adds:
1. A documented WEIGHT policy - base weight per dimension, and what
   happens to a dimension's weight when it's unavailable for a borrower
   (excluded vs discounted, and by how much).
2. A scoring-ELIGIBILITY check - is there enough usable data to
   responsibly produce a composite score for this borrower at all, or
   should Module 5 refuse to score them rather than produce a number that
   looks precise but isn't.
3. A human-readable SEGMENT LABEL per borrower, derived from their actual
   dimension combination - not a static assumption about what "Tier A"
   means.

Base weights sum to 1.0 across all 6 architecture-doc dimensions.
concentration_risk is currently not_computable_in_prototype for every
borrower (Module 3), so in THIS prototype its weight is always
redistributed away - included here so the policy is ready the moment
Module 1 gains counterparty data, without needing a rewrite.
"""

import os

DEFAULT_QUALITY_DIR = os.path.join(os.path.dirname(__file__), "..", "module2_data_quality", "quality_output")
DEFAULT_FEATURES_DIR = os.path.join(os.path.dirname(__file__), "..", "module3_feature_engineering", "features_output")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "segmentation_output")

BASE_DIMENSION_WEIGHTS = {
    "liquidity_cash_flow": 0.20,
    "repayment_credit_behavior": 0.15,
    "revenue_growth_signal": 0.20,
    "operational_stability": 0.15,
    "compliance_discipline": 0.20,
    "concentration_risk": 0.10,
}
assert abs(sum(BASE_DIMENSION_WEIGHTS.values()) - 1.0) < 1e-9

# insufficient_data dimensions aren't excluded outright - there IS some
# data, just not enough to fully trust (Module 2's threshold). Included at
# a discount rather than full weight. This multiplier is an assumption,
# not derived from anything - tune it if your team has a better basis.
INSUFFICIENT_DATA_WEIGHT_MULTIPLIER = 0.5

# A borrower needs at least this many dimensions carrying SOME weight
# (available or insufficient_data) to get a composite score at all.
# Below this, Module 5 should refuse to score rather than produce a
# number built on 1-2 dimensions dressed up as a full health score.
MIN_DIMENSIONS_FOR_SCORING = 3
