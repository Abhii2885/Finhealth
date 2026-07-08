"""
Liquidity & Cash Flow Health features (from bank/UPI transactions).

- avg_balance_inr: mean running balance across the observed window
- balance_trend_pct: % change from the first decile of days to the last
  decile (same method used to sanity-check Module 1's generator, now
  formalized as an actual feature)
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


def build_liquidity_features(bank_df):
    rows = []
    for bid, g in bank_df.groupby("borrower_id"):
        g = g.sort_values("txn_date")
        n = len(g)
        decile = max(n // 10, 1)

        avg_balance = g["running_balance_inr"].mean()
        first_bal = g["running_balance_inr"].iloc[:decile].mean()
        last_bal = g["running_balance_inr"].iloc[-decile:].mean()
        balance_trend_pct = ((last_bal - first_bal) / abs(first_bal) * 100) if first_bal != 0 else np.nan

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
