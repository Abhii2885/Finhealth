"""
Synthetic bank statement / UPI transaction-level data (trailing 12 months,
daily granularity) - the AA-pulled source in Module 1.

Each row is one transaction. Categories are chosen so Module 3 behavioral
features (inflow/outflow volatility, cheque bounce rate, limit
utilization, salary/vendor regularity) can be computed directly:
  sales_inflow, vendor_payment, salary_payment, loan_emi, utility_payment,
  upi_transfer_in, upi_transfer_out, cash_withdrawal, cheque_bounce_fee

Archetype -> behavior:
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

CATEGORIES_CREDIT = ["sales_inflow", "upi_transfer_in"]
CATEGORIES_DEBIT = ["vendor_payment", "salary_payment", "loan_emi", "utility_payment",
                     "upi_transfer_out", "cash_withdrawal"]


def _date_range(n_days):
    end = pd.Timestamp(OBS_END_DATE)
    return pd.date_range(end=end, periods=n_days, freq="D")


def generate_bank_upi(internal_borrowers):
    rows = []
    dates = _date_range(BANK_DAYS)
    n_days = len(dates)

    for _, b in internal_borrowers.iterrows():
        params = ARCHETYPE_PARAMS[b["true_archetype"]]
        # Scale is anchored to the SAME true_monthly_turnover_base_inr used
        # by the GST generator (not an independent draw) - this is what
        # makes bank inflow and declared GST turnover correlate for honest
        # reporters, and diverge specifically for under-reporters. Clipped
        # so the biggest borrowers don't blow up transaction volume/file size.
        scale = np.clip(b["true_monthly_turnover_base_inr"] / 1_000_000, 0.3, 3.0)
        balance = rng.uniform(50_000, 300_000) * scale

        # salary run day-of-month (regular businesses pay salary on ~same day)
        salary_day = int(rng.integers(1, 5))
        month_seen_salary = set()

        for day_idx, date in enumerate(dates):
            # linear interpolation from 1.0 (day 0) to credit/debit_trend (last day)
            progress = day_idx / max(n_days - 1, 1)
            credit_mult = 1.0 + (params["credit_trend"] - 1.0) * progress
            debit_mult = 1.0 + (params["debit_trend"] - 1.0) * progress

            n_txn = rng.poisson(params["daily_txn_lambda"] * scale)
            for _ in range(n_txn):
                is_credit = rng.random() < 0.45
                bounced = (not is_credit) and (rng.random() < params["bounce_prob"])

                if is_credit:
                    category = rng.choice(CATEGORIES_CREDIT, p=[0.7, 0.3])
                    amount = round(rng.lognormal(mean=9.5, sigma=params["vol"]) * scale * credit_mult, 2)
                else:
                    if date.day == salary_day and (date.year, date.month) not in month_seen_salary and rng.random() < 0.8:
                        category = "salary_payment"
                        month_seen_salary.add((date.year, date.month))
                        amount = round(rng.uniform(15_000, 40_000) * scale * rng.integers(1, 6) * debit_mult, 2)
                    else:
                        category = rng.choice(
                            ["vendor_payment", "loan_emi", "utility_payment", "upi_transfer_out", "cash_withdrawal"],
                            p=[0.45, 0.10, 0.15, 0.20, 0.10],
                        )
                        amount = round(rng.lognormal(mean=8.8, sigma=params["vol"]) * scale * debit_mult, 2)

                if bounced:
                    category = "cheque_bounce_fee"
                    amount = round(rng.uniform(300, 750), 2)  # bounce fee, not the bounced amount itself
                    is_credit = False

                # Balance moves ADDITIVELY (sum of txns), never multiplicatively -
                # multiplicative compounding across ~2000 txns/year is what
                # produced unrealistic crore-scale balances in an earlier draft.
                balance = max(balance + (amount if is_credit else -amount), -50_000)

                rows.append({
                    "borrower_id": b["borrower_id"],
                    "txn_date": date.date(),
                    "txn_type": "credit" if is_credit else "debit",
                    "category": category,
                    "amount_inr": amount,
                    "running_balance_inr": round(balance, 2),
                    "bounce_flag": bounced,
                })

    return pd.DataFrame(rows)
