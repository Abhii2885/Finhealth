"""
Collateral features (10% composite weight): raw pass-through only
(collateral_type, construction_status, estimated_value_inr) - the
residential > commercial > industrial and constructed > bare_plot scoring
lookup lives in Module 5, not here. NaN/None when has_collateral=False.
"""

import pandas as pd


def build_collateral_features(collateral_df):
    return collateral_df[["borrower_id", "collateral_type", "construction_status", "estimated_value_inr"]].copy()
