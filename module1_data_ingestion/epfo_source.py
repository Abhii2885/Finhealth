"""
Synthetic EPFO-style monthly employer contribution records.

Only generated for Tier C borrowers (has_epfo == True) in this prototype -
Tier A (thin-file/NTC) borrowers are informal employers by construction,
and Module 2 must flag "no EPFO record" as a missing-dimension flag, not
a zero/bad score, for exactly this reason.

Archetype -> behavior:
  healthy:    headcount/wage bill growing, contributions on time
  stagnant:   headcount flat, contributions occasionally late
  distressed: headcount shrinking, contribution delays/misses increasing
"""

import numpy as np
import pandas as pd
from config import rng, GST_EPFO_MONTHS, OBS_END_DATE

ARCHETYPE_PARAMS = {
    "healthy":    {"headcount_growth": 0.006, "late_prob": 0.05, "miss_prob": 0.005, "delay_days_mean": 2},
    "stagnant":   {"headcount_growth": 0.000, "late_prob": 0.20, "miss_prob": 0.02,  "delay_days_mean": 5},
    "distressed": {"headcount_growth": -0.012, "late_prob": 0.45, "miss_prob": 0.07,  "delay_days_mean": 12},
}

CONTRIBUTION_RATE = 0.12  # employer + employee, simplified flat rate for the prototype
AVG_WAGE_PER_EMPLOYEE = 18_000


def _period_range(n_months):
    end = pd.Timestamp(OBS_END_DATE).to_period("M")
    return [end - i for i in range(n_months - 1, -1, -1)]


def generate_epfo(internal_borrowers):
    rows = []
    periods = _period_range(GST_EPFO_MONTHS)
    epfo_borrowers = internal_borrowers[internal_borrowers["has_epfo"]]

    for _, b in epfo_borrowers.iterrows():
        params = ARCHETYPE_PARAMS[b["true_archetype"]]
        headcount = max(rng.integers(4, 60), 4)
        delay_drift = 0.0

        for period in periods:
            headcount = max(round(headcount * (1 + rng.normal(params["headcount_growth"], 0.02))), 1)
            wage_bill = round(headcount * AVG_WAGE_PER_EMPLOYEE * rng.uniform(0.9, 1.1), 2)
            employer_contribution = round(wage_bill * CONTRIBUTION_RATE / 2, 2)
            employee_contribution = round(wage_bill * CONTRIBUTION_RATE / 2, 2)

            due_date = period.to_timestamp(how="end") + pd.Timedelta(days=15)
            missed = rng.random() < params["miss_prob"]
            if missed:
                remittance_date = None
            else:
                is_late = rng.random() < params["late_prob"]
                if b["true_archetype"] == "distressed":
                    delay_drift += rng.uniform(0.1, 0.5)
                delay_days_mean = params["delay_days_mean"] + delay_drift
                delay = rng.poisson(delay_days_mean) if is_late else -rng.integers(0, 3)
                remittance_date = (due_date + pd.Timedelta(days=int(delay))).date()

            rows.append({
                "borrower_id": b["borrower_id"],
                "period": str(period),
                "employee_count": headcount,
                "wage_bill_inr": wage_bill,
                "employer_contribution_inr": employer_contribution,
                "employee_contribution_inr": employee_contribution,
                "due_date": due_date.date(),
                "remittance_date": remittance_date,
            })

    return pd.DataFrame(rows)
