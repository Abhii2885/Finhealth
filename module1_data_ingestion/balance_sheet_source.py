"""
Synthetic point-in-time balance sheet snapshot - one row per borrower with
balance_sheet_available == True (see config.BALANCE_SHEET_AVAILABLE_PROB_BY_TIER).

Feeds Module 3's current_ratio, leverage_ratio (Capacity) and
net_worth_to_assets_ratio (Capital). Anchored off the same
true_monthly_turnover_base_inr used by GST/bank so total_assets scales
realistically with a borrower's actual revenue, not an independent draw.

Archetype -> behavior: healthy businesses run a higher current ratio, lower
leverage, and a stronger net-worth-to-assets cushion; distressed the
opposite - mirrors the ordering already established for every other
archetype-conditioned source in this module.
"""

import numpy as np
import pandas as pd
from config import rng, OBS_END_DATE

BALANCE_SHEET_PARAMS_BY_ARCHETYPE = {
    # leverage_target: Total Debt / Net Worth. Per the user-supplied Score
    # Band scorecard, Indian MSME leverage bands run 0-7x+ (>=7x = worst
    # tier, <1x = best), not the 0-1x range this generator originally
    # produced - that compression meant almost every borrower landed in
    # the single best tier with the new bands, killing differentiation.
    # Widened here (and noise_sd raised specifically for leverage's own
    # lognormal draw - see leverage_noise_sd below) so distressed
    # borrowers genuinely reach into the >=7x worst tier and stagnant
    # borrowers spread across the middle tiers.
    "healthy":    {"current_ratio_target": 2.4, "leverage_target": 0.45, "net_worth_to_assets_target": 0.45, "noise_sd": 0.15, "leverage_noise_sd": 0.35},
    "stagnant":   {"current_ratio_target": 1.6, "leverage_target": 3.00, "net_worth_to_assets_target": 0.32, "noise_sd": 0.20, "leverage_noise_sd": 0.45},
    "distressed": {"current_ratio_target": 0.9, "leverage_target": 6.50, "net_worth_to_assets_target": 0.18, "noise_sd": 0.25, "leverage_noise_sd": 0.40},
}

# Asset turnover ratio range (annual turnover / total assets) - a rough
# stylized assumption, not a sector-calibrated figure.
ASSET_TURNOVER_RANGE = (0.6, 1.3)
CURRENT_LIABILITIES_TO_ASSETS_RANGE = (0.15, 0.35)


def generate_balance_sheet(internal_borrowers):
    rows = []
    bs_borrowers = internal_borrowers[internal_borrowers["balance_sheet_available"]]

    for _, b in bs_borrowers.iterrows():
        params = BALANCE_SHEET_PARAMS_BY_ARCHETYPE[b["true_archetype"]]
        annual_turnover = b["true_monthly_turnover_base_inr"] * 12

        total_assets = round(annual_turnover * rng.uniform(*ASSET_TURNOVER_RANGE), 2)
        current_liabilities = round(total_assets * rng.uniform(*CURRENT_LIABILITIES_TO_ASSETS_RANGE), 2)

        current_ratio_noisy = max(params["current_ratio_target"] * rng.lognormal(0, params["noise_sd"]), 0.1)
        current_assets = round(current_liabilities * current_ratio_noisy, 2)

        net_worth_frac = np.clip(params["net_worth_to_assets_target"] * rng.lognormal(0, params["noise_sd"]), 0.02, 0.95)
        net_worth = round(total_assets * net_worth_frac, 2)

        leverage_noisy = max(params["leverage_target"] * rng.lognormal(0, params["leverage_noise_sd"]), 0.0)
        total_debt_outstanding = round(net_worth * leverage_noisy, 2)

        rows.append({
            "borrower_id": b["borrower_id"],
            "as_of_date": pd.Timestamp(OBS_END_DATE).date(),
            "total_assets_inr": total_assets,
            "current_assets_inr": current_assets,
            "current_liabilities_inr": current_liabilities,
            "total_debt_outstanding_inr": total_debt_outstanding,
            "net_worth_inr": net_worth,
        })

    return pd.DataFrame(rows)
