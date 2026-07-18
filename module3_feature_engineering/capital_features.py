"""
Capital features (20% composite weight): net_worth_to_assets_ratio only -
the "net worth as >=30% of total assets" threshold from the 5C spec.
Same balance_sheet source as Capacity's current_ratio/leverage_ratio (not
recomputed 3 times - Module 3's capacity_features.py and this file both
read the same balance_sheet_df). NaN when balance_sheet_available=False.
"""

import pandas as pd
import numpy as np


def build_capital_features(balance_sheet_df):
    rows = []
    for _, bs in balance_sheet_df.iterrows():
        ratio = np.nan
        if bs["total_assets_inr"] > 0:
            # Clipped to [0,1] (0-100%) - a defensive bound, generation-side
            # already keeps this in range (Module 1's net_worth_frac is
            # clipped to [0.02, 0.95]), but a ratio can't exceed 100% by
            # definition regardless of what upstream noise might produce.
            ratio = round(min(max(bs["net_worth_inr"] / bs["total_assets_inr"], 0.0), 1.0), 4)
        rows.append({"borrower_id": bs["borrower_id"], "net_worth_to_assets_ratio": ratio})
    return pd.DataFrame(rows)
