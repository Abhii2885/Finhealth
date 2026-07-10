"""
Liquidity & Cash Flow Health features (from bank/UPI transactions).

- avg_balance_inr: mean running balance across the observed window
- balance_trend_pct: balance trend, normalized to a fixed time unit
  (% of avg balance moved per 30 days), NOT raw % change over whatever
  window happens to be available.

  BUG FIX (see module8_monitoring bias check + module4 README correction):
  the original version compared first-decile-of-days vs last-decile-of-days
  and reported raw % change over the WHOLE observed window. That is not
  comparable across borrowers with different history lengths - a 24-month
  window lets the same underlying trend compound for far longer than a
  3.5-month window, so short-history borrowers' raw % change was smaller
  by roughly an order of magnitude for reasons having nothing to do with
  how healthy they actually are. Percentile-ranking that raw number in
  Module 5 against a population dominated by full-history borrowers then
  crushed every short-history borrower toward the bottom of this feature's
  distribution regardless of true archetype (verified: short-history
  distressed, stagnant, AND healthy borrowers all landed in the single
  digit percentiles on the old formula).

  Fix: fit a linear trend (OLS slope of balance vs. day-index) using ALL
  available days, not just the first/last decile, then express it as a
  rate (% of average balance per 30 days) rather than a cumulative % over
  the whole window. This is time-normalized (comparable regardless of
  history length) and uses the full window's data (less sensitive to
  noise in any single decile). It does NOT fully close the gap for
  short-history borrowers - with genuinely less time observed there is
  genuinely less trend signal, and some residual gap is a real information
  limit, not a bug. See module8_monitoring/README.md for the measured
  before/after.
- monthly_inflow_volatility / monthly_outflow_volatility: coefficient of
  variation of total monthly credit / debit amounts - higher = less
  predictable cash flow
- txn_frequency_stability: coefficient of variation of monthly transaction
  counts (lower = more regular business activity)
"""

import pandas as pd
import numpy as np


def _cov(series):
    """Coefficient of variation; NaN-safe for borrowers with <2 months of data."""
    if len(series) < 2 or series.mean() == 0:
        return np.nan
    return series.std() / abs(series.mean())


def _monthly_trend_pct(g):
    """OLS slope of balance vs. day-index, expressed as % of avg balance
    per 30 days. Time-normalized so it's comparable across different
    history lengths (see module docstring for why this replaced a raw
    first-decile-vs-last-decile % change)."""
    if len(g) < 2:
        return np.nan
    avg_bal = g["running_balance_inr"].mean()
    if avg_bal == 0:
        return np.nan
    day_idx = (g["txn_date"] - g["txn_date"].iloc[0]).dt.days.values
    if len(np.unique(day_idx)) < 2:
        return np.nan
    slope, _ = np.polyfit(day_idx, g["running_balance_inr"].values, 1)
    return (slope * 30 / abs(avg_bal)) * 100


def build_liquidity_features(bank_df):
    rows = []
    for bid, g in bank_df.groupby("borrower_id"):
        g = g.sort_values("txn_date")

        avg_balance = g["running_balance_inr"].mean()
        balance_trend_pct = _monthly_trend_pct(g)

        g["month"] = g["txn_date"].dt.to_period("M")
        monthly_credit = g[g["txn_type"] == "credit"].groupby("month")["amount_inr"].sum()
        monthly_debit = g[g["txn_type"] == "debit"].groupby("month")["amount_inr"].sum()
        monthly_txn_count = g.groupby("month").size()

        rows.append({
            "borrower_id": bid,
            "avg_balance_inr": round(avg_balance, 2),
            "balance_trend_pct": round(balance_trend_pct, 2) if pd.notna(balance_trend_pct) else np.nan,
            "monthly_inflow_volatility": round(_cov(monthly_credit), 3) if pd.notna(_cov(monthly_credit)) else np.nan,
            "monthly_outflow_volatility": round(_cov(monthly_debit), 3) if pd.notna(_cov(monthly_debit)) else np.nan,
            "txn_frequency_stability": round(_cov(monthly_txn_count), 3) if pd.notna(_cov(monthly_txn_count)) else np.nan,
        })
    return pd.DataFrame(rows)
