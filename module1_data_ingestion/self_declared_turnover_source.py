"""
Synthetic self-declared turnover for borrowers below the GST registration
threshold (is_gst_registered == False, config.NON_GST_SHARE_TIER_A).

Same archetype-conditioned growth mechanics as gst_source.py (shared
true_monthly_turnover_base_inr anchor, same random-walk-with-drift growth
and sector seasonality) minus the tax/filing fields - this isn't a
regulatory filing, so there's no due_date/filing_date/timeliness concept.
Module 3's turnover_unify.py merges this with GST returns into one series
so non-GST borrowers get real revenue features instead of permanent NaN.
"""

import pandas as pd
from config import rng, GST_EPFO_MONTHS, OBS_END_DATE
from gst_source import ARCHETYPE_PARAMS, SECTOR_SEASONALITY


def _period_range(n_months):
    end = pd.Timestamp(OBS_END_DATE).to_period("M")
    return [end - i for i in range(n_months - 1, -1, -1)]


def generate_self_declared_turnover(internal_borrowers):
    rows = []
    periods = _period_range(GST_EPFO_MONTHS)
    non_gst_borrowers = internal_borrowers[~internal_borrowers["is_gst_registered"]]

    for _, b in non_gst_borrowers.iterrows():
        params = ARCHETYPE_PARAMS[b["true_archetype"]]
        seasonality = SECTOR_SEASONALITY.get(b["sector"], {})
        turnover_level = b["true_monthly_turnover_base_inr"]

        for period in periods:
            season_mult = seasonality.get(period.month, 1.0)
            growth_shock = rng.normal(params["monthly_growth"], params["noise_sd"])
            turnover_level = max(turnover_level * (1 + growth_shock), 5000)
            self_declared_turnover = round(turnover_level * season_mult, 2)

            rows.append({
                "borrower_id": b["borrower_id"],
                "period": str(period),
                "self_declared_turnover_inr": self_declared_turnover,
            })

    return pd.DataFrame(rows)
