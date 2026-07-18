"""
Synthetic bank statement / UPI transaction-level data (trailing 12 months,
daily granularity) - the AA-pulled source in Module 1.

Two transaction streams, generated separately then merged and re-sorted by
date so running_balance_inr reflects both correctly:

1. Ambient/unscheduled stream (daily Poisson arrivals): sales_inflow,
   upi_transfer_in (credit); vendor_payment, upi_transfer_out,
   cash_withdrawal (debit). Cheque-bounce logic applies only here -
   unchanged from v1/v2, preserves the existing validated
   cheque_bounce_rate feature's meaning exactly.
2. Scheduled monthly obligations (v3): salary_payment, utility_payment,
   rent_payment, loan_emi - one row/month, each with a due_date and an
   actual txn_date offset by archetype-conditioned lateness, using the
   same late_prob/miss_prob/delay_days_mean pattern gst_source.py already
   uses for GST filings. This is what makes "timely" assessable for
   utility/rent/salary at all - previously these were single undated
   amounts with no due-date concept.

sales_inflow/vendor_payment rows also carry a counterparty_id, drawn from
a small per-borrower Zipf-weighted customer/supplier pool - enables
Module 3's customer/supplier concentration features. loan_emi is gated on
has_existing_loan and generated FROM loan_facilities_source.py's output
(loan_id, monthly_emi_inr), not independently.

Archetype -> behavior (unchanged from v1/v2 for the ambient stream):
  healthy:    balance trending up/stable, low bounce rate, regular salary runs
  stagnant:   balance flat with more noise, occasional bounce
  distressed: balance declining, volatile, frequent bounces, erratic salary
"""

import numpy as np
import pandas as pd
from config import rng, BANK_DAYS, OBS_END_DATE

ARCHETYPE_PARAMS = {
    # credit_trend / debit_trend: total multiplicative change in transaction
    # size from day 1 to day N over the observation window (additive to
    # balance via cumulative sum, NOT compounded balance-on-balance -
    # compounding the balance itself blew values up to unrealistic crores
    # in an earlier version of this generator).
    "healthy":    {"daily_txn_lambda": 6, "bounce_prob": 0.004, "credit_trend": 1.25, "debit_trend": 1.05, "vol": 0.06},
    "stagnant":   {"daily_txn_lambda": 4, "bounce_prob": 0.015, "credit_trend": 1.00, "debit_trend": 1.05, "vol": 0.10},
    "distressed": {"daily_txn_lambda": 3, "bounce_prob": 0.045, "credit_trend": 0.75, "debit_trend": 1.15, "vol": 0.18},
}

# Scheduled monthly obligations (salary/utility/rent/loan_emi) - same
# late/miss pattern already established for GST/EPFO filings.
SCHEDULED_OBLIGATION_PARAMS_BY_ARCHETYPE = {
    "healthy":    {"late_prob": 0.05, "miss_prob": 0.01, "delay_days_mean": 2},
    "stagnant":   {"late_prob": 0.20, "miss_prob": 0.03, "delay_days_mean": 6},
    "distressed": {"late_prob": 0.45, "miss_prob": 0.10, "delay_days_mean": 12},
}

CATEGORIES_CREDIT = ["sales_inflow", "upi_transfer_in"]
CATEGORIES_DEBIT_AMBIENT = ["vendor_payment", "upi_transfer_out", "cash_withdrawal"]
CATEGORIES_DEBIT = CATEGORIES_DEBIT_AMBIENT + ["salary_payment", "loan_emi", "utility_payment", "rent_payment"]

N_COUNTERPARTIES_RANGE = (3, 15)


def _date_range(n_days):
    end = pd.Timestamp(OBS_END_DATE)
    return pd.date_range(end=end, periods=n_days, freq="D")


def _month_range(n_days):
    """Calendar months fully or partially covered by the BANK_DAYS window."""
    dates = _date_range(n_days)
    return sorted(set((d.year, d.month) for d in dates))


def _counterparty_pool(n):
    ids = [f"CP-{i+1:03d}" for i in range(n)]
    # Zipf-like decay so a few counterparties dominate - realistic
    # concentration structure, not a uniform spread.
    raw_weights = np.array([1.0 / (i + 1) for i in range(n)])
    weights = raw_weights / raw_weights.sum()
    return ids, weights


def _scheduled_row(borrower_id, category, due_date, amount, obligation_params, loan_id=None):
    missed = rng.random() < obligation_params["miss_prob"]
    if missed:
        return None
    is_late = rng.random() < obligation_params["late_prob"]
    delay = rng.poisson(obligation_params["delay_days_mean"]) if is_late else -rng.integers(0, 3)
    txn_date = due_date + pd.Timedelta(days=int(delay))
    row = {
        "borrower_id": borrower_id,
        "txn_date": txn_date.date(),
        "txn_type": "debit",
        "category": category,
        "amount_inr": round(amount, 2),
        "counterparty_id": None,
        "due_date": due_date.date(),
        "loan_id": loan_id,
        "bounce_flag": False,
    }
    return row


def generate_bank_upi(internal_borrowers, loan_facilities_df):
    all_rows = []
    dates = _date_range(BANK_DAYS)
    n_days = len(dates)
    months = _month_range(BANK_DAYS)
    n_months = len(months)

    loan_lookup = {}
    if len(loan_facilities_df):
        for _, l in loan_facilities_df.iterrows():
            loan_lookup[l["borrower_id"]] = l

    for _, b in internal_borrowers.iterrows():
        params = ARCHETYPE_PARAMS[b["true_archetype"]]
        obligation_params = SCHEDULED_OBLIGATION_PARAMS_BY_ARCHETYPE[b["true_archetype"]]
        borrower_rows = []

        # Scale is anchored to the SAME true_monthly_turnover_base_inr used
        # by the GST generator (not an independent draw) - this is what
        # makes bank inflow and declared GST turnover correlate for honest
        # reporters, and diverge specifically for under-reporters. Clipped
        # so the biggest borrowers don't blow up transaction volume/file size.
        scale = np.clip(b["true_monthly_turnover_base_inr"] / 1_000_000, 0.3, 3.0)
        balance = rng.uniform(50_000, 300_000) * scale

        n_customers = int(rng.integers(*N_COUNTERPARTIES_RANGE))
        n_suppliers = int(rng.integers(*N_COUNTERPARTIES_RANGE))
        customer_ids, customer_weights = _counterparty_pool(n_customers)
        supplier_ids, supplier_weights = _counterparty_pool(n_suppliers)

        # --- Stream 1: ambient/unscheduled daily transactions ---
        for day_idx, date in enumerate(dates):
            progress = day_idx / max(n_days - 1, 1)
            credit_mult = 1.0 + (params["credit_trend"] - 1.0) * progress
            debit_mult = 1.0 + (params["debit_trend"] - 1.0) * progress

            n_txn = rng.poisson(params["daily_txn_lambda"] * scale)
            for _ in range(n_txn):
                is_credit = rng.random() < 0.45
                bounced = (not is_credit) and (rng.random() < params["bounce_prob"])
                counterparty_id = None

                if is_credit:
                    category = rng.choice(CATEGORIES_CREDIT, p=[0.7, 0.3])
                    amount = round(rng.lognormal(mean=9.5, sigma=params["vol"]) * scale * credit_mult, 2)
                    if category == "sales_inflow":
                        counterparty_id = rng.choice(customer_ids, p=customer_weights)
                else:
                    category = rng.choice(CATEGORIES_DEBIT_AMBIENT, p=[0.6, 0.25, 0.15])
                    amount = round(rng.lognormal(mean=8.8, sigma=params["vol"]) * scale * debit_mult, 2)
                    if category == "vendor_payment":
                        counterparty_id = rng.choice(supplier_ids, p=supplier_weights)

                if bounced:
                    category = "cheque_bounce_fee"
                    amount = round(rng.uniform(300, 750), 2)  # bounce fee, not the bounced amount itself
                    is_credit = False
                    counterparty_id = None

                borrower_rows.append({
                    "borrower_id": b["borrower_id"],
                    "txn_date": date.date(),
                    "txn_type": "credit" if is_credit else "debit",
                    "category": category,
                    "amount_inr": amount,
                    "counterparty_id": counterparty_id,
                    "due_date": None,
                    "loan_id": None,
                    "bounce_flag": bounced,
                })

        # --- Stream 2: scheduled monthly obligations ---
        salary_day = int(rng.integers(1, 6))
        utility_day = int(rng.integers(5, 16))
        rent_day = int(rng.integers(1, 4))
        loan = loan_lookup.get(b["borrower_id"])

        for month_idx, (year, month) in enumerate(months):
            month_progress = month_idx / max(n_months - 1, 1)
            debit_mult = 1.0 + (params["debit_trend"] - 1.0) * month_progress

            salary_due = pd.Timestamp(year=year, month=month, day=min(salary_day, 28))
            salary_amount = rng.uniform(15_000, 40_000) * scale * rng.integers(1, 6) * debit_mult
            row = _scheduled_row(b["borrower_id"], "salary_payment", salary_due, salary_amount, obligation_params)
            if row:
                borrower_rows.append(row)

            utility_due = pd.Timestamp(year=year, month=month, day=min(utility_day, 28))
            utility_amount = rng.lognormal(mean=8.5, sigma=params["vol"]) * scale * debit_mult
            row = _scheduled_row(b["borrower_id"], "utility_payment", utility_due, utility_amount, obligation_params)
            if row:
                borrower_rows.append(row)

            rent_due = pd.Timestamp(year=year, month=month, day=min(rent_day, 28))
            rent_amount = rng.lognormal(mean=8.9, sigma=0.05) * scale  # rent is stable, low volatility
            row = _scheduled_row(b["borrower_id"], "rent_payment", rent_due, rent_amount, obligation_params)
            if row:
                borrower_rows.append(row)

            if loan is not None:
                loan_due = pd.Timestamp(year=year, month=month, day=min(5, 28))
                row = _scheduled_row(
                    b["borrower_id"], "loan_emi", loan_due, loan["monthly_emi_inr"],
                    obligation_params, loan_id=loan["loan_id"],
                )
                if row:
                    borrower_rows.append(row)

        # --- Merge, sort by date, compute running balance in one pass ---
        borrower_rows.sort(key=lambda r: r["txn_date"])
        for r in borrower_rows:
            amount = r["amount_inr"]
            balance = max(balance + (amount if r["txn_type"] == "credit" else -amount), -50_000)
            r["running_balance_inr"] = round(balance, 2)

        all_rows.extend(borrower_rows)

    cols = ["borrower_id", "txn_date", "txn_type", "category", "amount_inr", "running_balance_inr",
            "bounce_flag", "counterparty_id", "due_date", "loan_id"]
    return pd.DataFrame(all_rows, columns=cols)
