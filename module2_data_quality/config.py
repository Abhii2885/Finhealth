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

GST_EPFO_MONTHS = 36           # 3yr window (v3) - needed for Module 3's revenue_cagr_3yr
BANK_DAYS = 365

# --- Completeness thresholds ---
# Below these, a source is treated as too thin to trust for that borrower,
# not just "some data missing."
GST_MIN_FILING_COVERAGE = 0.60      # >=60% of expected periods filed
BANK_MIN_ACTIVE_DAY_COVERAGE = 0.50  # >=50% of days have >=1 transaction
BANK_MIN_ANNUAL_TXN_COUNT = 40       # fewer than this = "thin banking history"
EPFO_MIN_FILING_COVERAGE = 0.60
SELF_DECLARED_MIN_FILING_COVERAGE = 0.60  # same bar as GST, applied to non-GST borrowers

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

# --- (dimension, submetric) -> {sources, gating_flag} map (5C framework, v3) ---
# gating_flag names a boolean column on borrower_master: if False for a
# borrower, the submetric is "not_applicable" (genuinely doesn't apply,
# never a data gap) regardless of what completeness.py computed for its
# sources. gating_flag=None means the submetric applies to everyone; its
# status then depends purely on source completeness (insufficient_data vs
# available). "turnover" is a virtual source resolved per-borrower to
# either gst or self_declared_turnover, whichever applies
# (is_gst_registered) - see completeness.turnover_completeness.
SUBMETRIC_SOURCE_MAP = {
    ("capacity", "current_ratio"): {"sources": ["balance_sheet"], "gating_flag": "balance_sheet_available"},
    ("capacity", "leverage_ratio"): {"sources": ["balance_sheet"], "gating_flag": "balance_sheet_available"},
    ("capacity", "dscr"): {"sources": ["bank", "loan_facilities"], "gating_flag": "has_existing_loan"},
    ("capacity", "interest_coverage_ratio"): {"sources": ["bank", "loan_facilities"], "gating_flag": "has_existing_loan"},
    ("capacity", "cash_flow_match_ratio"): {"sources": ["bank", "turnover"], "gating_flag": None},
    ("capacity", "revenue_cagr_3yr"): {"sources": ["turnover"], "gating_flag": None},
    ("capacity", "projected_revenue_growth_rate"): {"sources": ["turnover"], "gating_flag": None},
    ("capacity", "customer_concentration_pct"): {"sources": ["bank"], "gating_flag": None},
    ("capacity", "supplier_concentration_pct"): {"sources": ["bank"], "gating_flag": None},

    ("character", "bureau_score"): {"sources": ["bureau_data"], "gating_flag": "has_bureau_record"},
    ("character", "civil_suit_years_since_active"): {"sources": ["legal_disputes"], "gating_flag": None},
    ("character", "other_legal_dispute_years_since_active"): {"sources": ["legal_disputes"], "gating_flag": None},
    ("character", "owner_time_in_business_years"): {"sources": ["owners"], "gating_flag": None},
    ("character", "cheque_bounce_rate"): {"sources": ["bank"], "gating_flag": None},

    ("capital", "net_worth_to_assets_ratio"): {"sources": ["balance_sheet"], "gating_flag": "balance_sheet_available"},

    ("compliance", "covenant_compliance_flag"): {"sources": ["loan_facilities"], "gating_flag": "has_covenant_effective"},
    ("compliance", "gst_ontime_filing_ratio"): {"sources": ["gst"], "gating_flag": "is_gst_registered"},
    ("compliance", "epfo_ontime_remittance_ratio"): {"sources": ["epfo"], "gating_flag": "has_epfo"},
    ("compliance", "utility_payment_timeliness"): {"sources": ["bank"], "gating_flag": None},
    ("compliance", "rent_payment_timeliness"): {"sources": ["bank"], "gating_flag": None},
    ("compliance", "salary_payment_timeliness"): {"sources": ["bank"], "gating_flag": None},

    ("collateral", "collateral_quality_score"): {"sources": ["collateral"], "gating_flag": "has_collateral"},
}
