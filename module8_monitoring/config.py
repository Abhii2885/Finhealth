"""
Module 8 - Monitoring & Feedback (Track 3, lighter than the Track 4 version)

Per the architecture doc: score drift tracking, periodic recompute
triggers, and a basic bias check across segments - specifically calling
out "are NTC borrowers systematically scored lower due to
missing-dimension penalties" as a real risk in this design. That bias
check is the priority deliverable here, not an afterthought.
"""

import os

DEFAULT_SCORING_DIR = os.path.join(os.path.dirname(__file__), "..", "module5_scoring", "scoring_output")
DEFAULT_SEGMENTATION_DIR = os.path.join(os.path.dirname(__file__), "..", "module4_segmentation", "segmentation_output")
DEFAULT_DATA_LAKE_DIR = os.path.join(os.path.dirname(__file__), "..", "module1_data_ingestion", "data_lake")
DEFAULT_INTEGRATION_DIR = os.path.join(os.path.dirname(__file__), "..", "module7_integration", "integration_output")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "monitoring_output")

# PSI (Population Stability Index) thresholds - standard industry
# heuristic for credit scorecard monitoring, not something we derived:
# <0.10 no significant shift, 0.10-0.25 moderate, >0.25 significant.
PSI_MODERATE_THRESHOLD = 0.10
PSI_SIGNIFICANT_THRESHOLD = 0.25
PSI_BINS = 10

# A borrower's score is "stale" if computed more than this many days ago.
STALENESS_THRESHOLD_DAYS = 90
