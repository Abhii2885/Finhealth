"""
Repayment & Credit Behavior features.

Computable from Module 1 data: cheque bounce rate and count from
bank/UPI transactions.

NOT computable in this prototype (see config.UNAVAILABLE_SUBFEATURES):
- bureau_dpd_history: no bureau data source exists in Module 1
- credit_limit_utilization_pct: Module 1's bank generator has no
  sanctioned overdraft/credit-limit field, so "utilization %" cannot be
  derived - there's no limit to divide against. Adding a fake limit would
  just be inventing a number; flagged as missing instead.

This means this dimension is ALWAYS partial in this prototype, for every
borrower, not a per-borrower gap Module 2 would catch.
"""

import pandas as pd


def build_repayment_features(bank_df):
    rows = []
    for bid, g in bank_df.groupby("borrower_id"):
        n_days_observed = g["txn_date"].nunique()
        n_debit_txns = (g["txn_type"] == "debit").sum()
        n_bounces = g["bounce_flag"].sum()

        bounce_rate = n_bounces / n_debit_txns if n_debit_txns else float("nan")
        # annualize bounce count to the observed window so short-history
        # borrowers (Module 1 v2) aren't penalized for having fewer days
        observed_years = max(n_days_observed / 365, 1 / 365)
        bounce_count_annualized = n_bounces / observed_years

        rows.append({
            "borrower_id": bid,
            "cheque_bounce_rate": round(bounce_rate, 4) if pd.notna(bounce_rate) else float("nan"),
            "cheque_bounce_count_annualized": round(bounce_count_annualized, 2),
            "bureau_dpd_history": None,             # not computable in this prototype
            "credit_limit_utilization_pct": None,   # not computable in this prototype
        })
    return pd.DataFrame(rows)
