"""
Synthetic GSTR-3B-style monthly returns per borrower.

Fields intentionally mirror what a real GSTN pull would expose so Module 3
feature engineering (filing regularity, turnover growth, tax-to-turnover
ratio) can be built against this schema without rework later:
  - period, due_date, filing_date (None = not filed that month)
  - declared_turnover, tax_paid, itc_claimed

Archetype -> behavior:
  healthy:    turnover trending up, files on/before due date most months
  stagnant:   turnover flat, files late-but-present most months
  distressed: turnover declining, filing delays grow over the window,
              occasional missed filings entirely
"""

import numpy as np
import pandas as pd
from config import rng, GST_EPFO_MONTHS, OBS_END_DATE

SECTOR_SEASONALITY = {
    # month (1-12) -> multiplier on base turnover
    "retail":        {10: 1.35, 11: 1.45, 12: 1.15, 1: 0.85, 2: 0.9},
    "trading":       {3: 1.2, 4: 1.15, 9: 1.1, 10: 1.2},
    "manufacturing": {},   # relatively flat
    "services":      {},   # relatively flat
}

ARCHETYPE_PARAMS = {
    "healthy":    {"monthly_growth": 0.010, "noise_sd": 0.05, "late_prob": 0.08, "miss_prob": 0.005, "delay_days_mean": 2},
    "stagnant":   {"monthly_growth": 0.001, "noise_sd": 0.08, "late_prob": 0.30, "miss_prob": 0.02,  "delay_days_mean": 6},
    "distressed": {"monthly_growth": -0.018, "noise_sd": 0.14, "late_prob": 0.55, "miss_prob": 0.08,  "delay_days_mean": 14},
}

TAX_RATE_RANGE = (0.05, 0.18)  # effective GST rate varies by sector/goods mix


def _period_range(n_months):
    end = pd.Timestamp(OBS_END_DATE).to_period("M")
    return [end - i for i in range(n_months - 1, -1, -1)]


def generate_gst(internal_borrowers):
    rows = []
    periods = _period_range(GST_EPFO_MONTHS)

    for _, b in internal_borrowers.iterrows():
        params = ARCHETYPE_PARAMS[b["true_archetype"]]
        seasonality = SECTOR_SEASONALITY.get(b["sector"], {})

        # Base monthly turnover scaled loosely by business age (proxy for scale)
        base_turnover = rng.uniform(3.5, 45.0) * (1 + min(b["business_age_years"], 15) / 15) * 1e5
        tax_rate = rng.uniform(*TAX_RATE_RANGE)

        turnover_level = base_turnover
        # distressed businesses drift into worsening filing delay over time
        delay_drift = 0.0

        for idx, period in enumerate(periods):
            month_num = period.month
            season_mult = seasonality.get(month_num, 1.0)
            growth_shock = rng.normal(params["monthly_growth"], params["noise_sd"])
            turnover_level = max(turnover_level * (1 + growth_shock), 5000)
            declared_turnover = round(turnover_level * season_mult, 2)

            itc_claimed = round(declared_turnover * tax_rate * rng.uniform(0.6, 0.95), 2)
            tax_paid = round(max(declared_turnover * tax_rate - itc_claimed, 0) + rng.uniform(-500, 500), 2)

            due_date = period.to_timestamp(how="end") + pd.Timedelta(days=20)

            missed = rng.random() < params["miss_prob"]
            if missed:
                filing_date = pd.NaT
            else:
                is_late = rng.random() < params["late_prob"]
                if b["true_archetype"] == "distressed":
                    delay_drift += rng.uniform(0.1, 0.6)  # delays worsen over time
                delay_days_mean = params["delay_days_mean"] + delay_drift
                delay = rng.poisson(delay_days_mean) if is_late else -rng.integers(0, 4)
                filing_date = due_date + pd.Timedelta(days=int(delay))

            rows.append({
                "borrower_id": b["borrower_id"],
                "period": str(period),
                "due_date": due_date.date(),
                "filing_date": filing_date.date() if pd.notna(filing_date) else None,
                "declared_turnover_inr": declared_turnover,
                "tax_paid_inr": tax_paid,
                "itc_claimed_inr": itc_claimed,
            })

    return pd.DataFrame(rows)
