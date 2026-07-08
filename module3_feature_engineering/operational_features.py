"""
Operational Stability features (from EPFO contributions).

Only meaningful for borrowers who have EPFO records at all (Tier C in
this prototype). Tier A borrowers get NULL here, not zero - a thin-file
borrower with no registered employees is not "operationally unstable",
the dimension simply doesn't apply. Module 2's dimension_availability
already marks this not_applicable; this module just needs to not
contradict that by filling in a zero.
"""

import pandas as pd
import numpy as np
from config import TREND_WINDOW_MONTHS


def _cov(series):
    if len(series) < 2 or series.mean() == 0:
        return np.nan
    return series.std() / abs(series.mean())


def build_operational_features(epfo_df):
    rows = []
    for bid, g in epfo_df.groupby("borrower_id"):
        g = g.sort_values("period")
        n = len(g)
        w = min(TREND_WINDOW_MONTHS, max(n // 2, 1))

        first_hc = g["employee_count"].iloc[:w].mean()
        last_hc = g["employee_count"].iloc[-w:].mean()
        headcount_growth_rate = (last_hc / first_hc) if first_hc else np.nan

        first_wage = g["wage_bill_inr"].iloc[:w].mean()
        last_wage = g["wage_bill_inr"].iloc[-w:].mean()
        wage_growth_rate = (last_wage / first_wage) if first_wage else np.nan

        rows.append({
            "borrower_id": bid,
            "headcount_growth_rate": round(headcount_growth_rate, 3) if pd.notna(headcount_growth_rate) else np.nan,
            "headcount_volatility": round(_cov(g["employee_count"]), 3),
            "wage_bill_growth_rate": round(wage_growth_rate, 3) if pd.notna(wage_growth_rate) else np.nan,
            "avg_employee_count": round(g["employee_count"].mean(), 1),
            "epfo_periods_observed": n,
        })
    # NOTE: intentionally NOT reindexed against the full borrower_master list -
    # borrowers with no EPFO rows (Tier A) simply get no row here, and the
    # orchestrator (build_features.py) left-joins this in, producing NaN for
    # them, which is the correct "not_applicable" representation.
    return pd.DataFrame(rows)
