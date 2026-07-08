"""
Revenue & Growth Signal features (from GST returns).

- turnover_growth_rate: last-3-month avg declared turnover / first-3-month
  avg, over whatever window the borrower actually has (short-history
  borrowers use their available window, not a hardcoded 24 months)
- turnover_volatility: coefficient of variation of monthly declared turnover
- avg_monthly_turnover_inr

Also carries forward Module 2's consistency_flag as a passthrough - this
is NOT recomputed here, it's Module 2's finding attached to the same
borrower row so Module 5 can see "this borrower's turnover growth looks
good, but Module 2 flagged a GST-vs-bank mismatch" side by side.
"""

import pandas as pd
import numpy as np
from config import TREND_WINDOW_MONTHS


def _cov(series):
    if len(series) < 2 or series.mean() == 0:
        return np.nan
    return series.std() / abs(series.mean())


def build_revenue_features(gst_df, consistency_df):
    rows = []
    for bid, g in gst_df.groupby("borrower_id"):
        g = g.sort_values("period")
        n = len(g)
        w = min(TREND_WINDOW_MONTHS, max(n // 2, 1))

        first_avg = g["declared_turnover_inr"].iloc[:w].mean()
        last_avg = g["declared_turnover_inr"].iloc[-w:].mean()
        growth_rate = (last_avg / first_avg) if first_avg else np.nan

        rows.append({
            "borrower_id": bid,
            "turnover_growth_rate": round(growth_rate, 3) if pd.notna(growth_rate) else np.nan,
            "turnover_volatility": round(_cov(g["declared_turnover_inr"]), 3),
            "avg_monthly_turnover_inr": round(g["declared_turnover_inr"].mean(), 2),
            "gst_periods_observed": n,
        })

    features = pd.DataFrame(rows)
    passthrough = consistency_df[["borrower_id", "turnover_bank_ratio", "consistency_flag"]].rename(
        columns={"consistency_flag": "gst_bank_consistency_flag"}
    )
    return features.merge(passthrough, on="borrower_id", how="left")
