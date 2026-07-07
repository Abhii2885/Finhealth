"""
Module 1 - Data Ingestion Layer (synthetic)
Global configuration and reproducibility settings for the MSME Financial
Health Score synthetic data generator.

NOTE ON HONESTY: every number in this file is an assumption made for a
demo, not a calibrated industry parameter. They are documented so a
teammate (or a judge) can see exactly what was assumed and challenge it.
"""

import numpy as np

RANDOM_SEED = 42
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
GST_EPFO_MONTHS = 24          # trailing 24 months of return/contribution history
BANK_DAYS = 365                # trailing 12 months of daily bank/UPI activity

OBS_END_DATE = np.datetime64("2026-06-30")  # "today" for generation purposes

OUTPUT_DIR = "data_lake"
