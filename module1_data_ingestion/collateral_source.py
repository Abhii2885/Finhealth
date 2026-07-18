"""
Synthetic collateral record - raw pass-through only (type + construction
status + estimated value). The residential > commercial > industrial and
constructed > bare_plot scoring lookup lives in Module 5, not here - this
file only generates what a borrower actually has, not its score.

Gated on has_collateral (config.COLLATERAL_PROB_BY_TIER); each borrower
with collateral gets exactly one row in this prototype (no multi-property
modeling).
"""

import pandas as pd
from config import rng, OBS_END_DATE

COLLATERAL_TYPE_MIX = {"residential": 0.45, "commercial": 0.35, "industrial": 0.20}
CONSTRUCTION_STATUS_MIX = {"constructed": 0.70, "bare_plot": 0.30}

# Valuations are dated, not pulled live like a bank feed - a random lag
# (0-365 days before the data-lake snapshot) reads more like a real
# appraisal than every borrower sharing one flat valuation date.
VALUATION_DATE_LAG_DAYS_RANGE = (0, 365)

# Rough value multiplier on annual turnover, by type - not a real appraisal
# model, just enough spread for a plausible estimated_value_inr.
VALUE_MULTIPLIER_RANGE_BY_TYPE = {
    "residential": (0.8, 2.5),
    "commercial": (1.0, 3.5),
    "industrial": (1.5, 5.0),
}


def generate_collateral(internal_borrowers):
    rows = []
    collateral_borrowers = internal_borrowers[internal_borrowers["has_collateral"]]

    for _, b in collateral_borrowers.iterrows():
        collateral_type = rng.choice(list(COLLATERAL_TYPE_MIX.keys()), p=list(COLLATERAL_TYPE_MIX.values()))
        construction_status = rng.choice(list(CONSTRUCTION_STATUS_MIX.keys()), p=list(CONSTRUCTION_STATUS_MIX.values()))
        lo, hi = VALUE_MULTIPLIER_RANGE_BY_TYPE[collateral_type]
        annual_turnover = b["true_monthly_turnover_base_inr"] * 12
        estimated_value = round(annual_turnover * rng.uniform(lo, hi), 2)
        lag = int(rng.integers(*VALUATION_DATE_LAG_DAYS_RANGE))
        valuation_date = (pd.Timestamp(OBS_END_DATE) - pd.Timedelta(days=lag)).date()

        rows.append({
            "borrower_id": b["borrower_id"],
            "collateral_type": collateral_type,
            "construction_status": construction_status,
            "estimated_value_inr": estimated_value,
            "valuation_date": valuation_date,
        })

    return pd.DataFrame(rows)
