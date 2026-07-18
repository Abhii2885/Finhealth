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
import pandas as pd

DEFAULT_DATA_LAKE_DIR = os.path.join(os.path.dirname(__file__), "..", "module1_data_ingestion", "data_lake")
DEFAULT_QUALITY_DIR = os.path.join(os.path.dirname(__file__), "..", "module2_data_quality", "quality_output")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "features_output")

# Matches Module 1's OBS_END_DATE - duplicated (not imported cross-module,
# same convention as every other module boundary in this project) so
# character_features.py can compute "years since a dispute was last
# active" relative to the data lake's own snapshot date, not real
# wall-clock time.
SNAPSHOT_DATE = pd.Timestamp("2026-06-30")

GST_EPFO_MONTHS = 36           # 3yr window (v3) - matches Module 1, needed for revenue_cagr_3yr
BANK_DAYS = 365

# Window used for "recent" trend features (last N of the GST/EPFO periods,
# or last N days of bank data) vs the full-window baseline.
TREND_WINDOW_MONTHS = 3
TREND_WINDOW_DAYS = 90

# v3: this restructure adds real Module 1 sources for every gap the old
# 6-dimension system flagged as absent (bureau, utility timeliness,
# concentration, collateral) - both lists below are now empty. Kept (not
# deleted) so run_module3.py's excluded-dimensions manifest still runs and
# explicitly shows "0 rows" rather than the concept disappearing silently.
NOT_COMPUTABLE_DIMENSIONS = []
UNAVAILABLE_SUBFEATURES = {}

# --- 5C submetric thresholds (v3) ---
# CAGR requires 3 full annual buckets - a bucket needs at least this many
# non-null months to count as "full" (avoids extrapolating a partial year).
CAGR_MIN_MONTHS_PER_YEAR = 8

# Concentration % is meaningless on a handful of transactions - below this
# count, customer/supplier_concentration_pct is NaN rather than a noisy
# number driven by small-sample luck (same risk family as the already-fixed
# balance_trend_pct window-length bug).
MIN_CONCENTRATION_TXN_COUNT = 20
