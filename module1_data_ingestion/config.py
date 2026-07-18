"""
Module 1 - Data Ingestion Layer (synthetic)
Global configuration and reproducibility settings for the MSME Financial
Health Score synthetic data generator.

NOTE ON HONESTY: every number in this file is an assumption made for a
demo, not a calibrated industry parameter. They are documented so a
teammate (or a judge) can see exactly what was assumed and challenge it.
"""

import os
import numpy as np

# Overridable via env var so Module 8 can generate a genuinely independent
# second cohort (for real drift comparison) without editing this file.
RANDOM_SEED = int(os.environ.get("MSME_SEED", 42))
rng = np.random.default_rng(RANDOM_SEED)

N_BORROWERS = 400

# Tier mix. Tier A = thin-file/NTC (no EPFO, weaker bureau footprint).
# Tier C = full-financials (has EPFO, longer credit history).
# Matches Module 4 segmentation logic from the architecture doc.
TIER_MIX = {"A": 0.60, "C": 0.40}

SECTORS = ["retail", "manufacturing", "services", "trading"]
SECTOR_MIX = [0.35, 0.20, 0.30, 0.15]

# Hidden ground-truth archetype. NOT a feature - lives only in the
# ground-truth file, used later to validate the scoring engine's rank
# ordering. Feeding this into feature engineering directly would be
# label leakage.
ARCHETYPES = ["healthy", "stagnant", "distressed"]
ARCHETYPE_MIX = [0.50, 0.30, 0.20]

# Observation windows
GST_EPFO_MONTHS = 36           # trailing 36 months (3yr) - needed for Module 3's revenue_cagr_3yr
BANK_DAYS = 365                # trailing 12 months of daily bank/UPI activity - CAGR only needs
                                # GST/self-declared turnover, not bank, so this stays at 1yr.

OBS_END_DATE = np.datetime64("2026-06-30")  # "today" for generation purposes

OUTPUT_DIR = "data_lake"

# --- 5C-framework borrower attributes (v3) -----------------------------
# All five are always-known borrower attributes (like tier/sector/has_epfo),
# not hidden ground truth - they're the precursor to balance_sheet_available
# eventually being a real Module 7 user input. Tier-conditioned because
# formal, larger (Tier C) businesses are more likely in reality to have
# these records than thin-file Tier A ones - this is a realistic signal
# for Module 8's bias check to surface, not an artificial confound.

# Fraction of Tier A borrowers below the GST registration turnover
# threshold - they get self-declared turnover instead of GST returns.
# Tier C is assumed always GST-registered (formal employer, has EPFO).
NON_GST_SHARE_TIER_A = 0.10

BALANCE_SHEET_AVAILABLE_PROB_BY_TIER = {"A": 0.35, "C": 0.80}
BUREAU_RECORD_PROB_BY_TIER = {"A": 0.45, "C": 0.85}
EXISTING_LOAN_PROB_BY_TIER = {"A": 0.30, "C": 0.55}
COLLATERAL_PROB_BY_TIER = {"A": 0.25, "C": 0.60}
