"""
Module 2 - Data Quality & Completeness Tiering (Track 3)

Purpose (per architecture doc): decide which of the health-score dimensions
(Module 3+) can actually be computed for a given borrower, and flag data
problems - missing data, schema violations, and cross-source
inconsistencies - explicitly rather than silently defaulting to zero or
ignoring them.

All thresholds below are assumptions made for this prototype, not
regulatory or industry standards. They're centralized here so they can be
challenged/tuned without hunting through the code.
"""

import os
import pandas as pd

# "Future date" validation needs a reference point representing when this
# data lake was notionally pulled/frozen - NOT the real wall-clock date the
# validator happens to run on. Module 1 generates data up to OBS_END_DATE
# (2026-06-30), but GST/EPFO due dates fall ~15-20 days after period end,
# and late filers can push filing/remittance dates weeks past that again.
# A fixed snapshot date safely past the whole window avoids flagging
# legitimate (if late) filings as "future" just because real-world today
# hasn't caught up to the synthetic dataset's own timeline yet.
DATA_SNAPSHOT_DATE = pd.Timestamp("2027-01-01")

# Where Module 1's output lives, relative to this file by default.
DEFAULT_DATA_LAKE_DIR = os.path.join(os.path.dirname(__file__), "..", "msme_data_gen", "data_lake")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "quality_output")

GST_EPFO_MONTHS = 24
BANK_DAYS = 365

# --- Completeness thresholds ---
# Below these, a source is treated as too thin to trust for that borrower,
# not just "some data missing."
GST_MIN_FILING_COVERAGE = 0.60      # >=60% of expected periods filed
BANK_MIN_ACTIVE_DAY_COVERAGE = 0.50  # >=50% of days have >=1 transaction
BANK_MIN_ANNUAL_TXN_COUNT = 40       # fewer than this = "thin banking history"
EPFO_MIN_FILING_COVERAGE = 0.60

# Quality tier cutoffs (re-derived from actual observed completeness,
# independent of Module 1's assumed Tier A/C assignment)
QUALITY_TIER_FULL_MIN = 0.90    # both GST & bank coverage >= this -> "Full"
QUALITY_TIER_PARTIAL_MIN = 0.60  # >= this -> "Partial", else "Thin"

# --- Cross-source consistency check ---
# Flag borrowers whose bank sales-inflow-to-declared-GST-turnover ratio
# falls outside the population's [LOW_PCT, HIGH_PCT] band. Deliberately
# data-driven (percentile-based) rather than a fixed universal ratio,
# because there's no real calibration reference in a synthetic prototype -
# see README for the honest precision/recall this achieves against the
# hidden ground truth.
CONSISTENCY_LOW_PCT = 0.10
CONSISTENCY_HIGH_PCT = 0.90

# --- Dimension -> required source(s) map (Module 3's eventual 6 dimensions) ---
# "bureau" and "utility" are referenced in the architecture doc but have no
# generator in Module 1 - flagged as systemically unavailable in this
# prototype, not a per-borrower gap.
DIMENSION_SOURCE_MAP = {
    "liquidity_cash_flow": ["bank"],
    "repayment_credit_behavior": ["bank"],       # + bureau (unavailable in prototype)
    "revenue_growth_signal": ["gst"],
    "operational_stability": ["epfo"],
    "compliance_discipline": ["gst"],             # + utility (unavailable in prototype)
    "concentration_risk": [],                     # not computable at all - see README
}
