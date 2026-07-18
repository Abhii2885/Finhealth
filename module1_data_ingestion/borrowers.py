"""
Generates the base MSME borrower population.

Two files come out of this module:
  1. borrower_master  - tier, sector, business age, consent_id. This is the
     "public" record any downstream module (feature engineering, scoring)
     is allowed to see.
  2. ground_truth      - hidden fields per borrower (true_archetype,
     gst_underreport_pct, true_monthly_turnover_base). Kept deliberately
     separate. Used only to backtest downstream modules later (e.g. "does
     Module 2's consistency check actually catch the borrowers who were
     generated to under-report GST turnover?"), never as a model input.

true_monthly_turnover_base is shared between the GST and bank/UPI
generators so a borrower's declared turnover and bank inflow correlate
realistically. Earlier draft drew these independently per source, which
made a GST-vs-bank cross-source consistency check (Module 2) meaningless -
every borrower would look "inconsistent" for no real reason, since the
two numbers had no relationship to begin with.

gst_underreport_pct is a deliberate, minority-only synthetic fraud signal:
most borrowers report GST turnover close to their true bank-verified
revenue (small noise only); a minority under-report it, skewed toward the
distressed archetype (consistent with the idea that businesses under cash
pressure are more likely to under-declare tax turnover), giving Module 2's
consistency check something real to detect.
"""

import uuid
import pandas as pd
import numpy as np
from config import (
    rng, N_BORROWERS, TIER_MIX, SECTORS, SECTOR_MIX, ARCHETYPES, ARCHETYPE_MIX,
    NON_GST_SHARE_TIER_A, BALANCE_SHEET_AVAILABLE_PROB_BY_TIER,
    BUREAU_RECORD_PROB_BY_TIER, EXISTING_LOAN_PROB_BY_TIER, COLLATERAL_PROB_BY_TIER,
)

# Probability a borrower is a GST "under-reporter" (fraud-like minority),
# by archetype. Distressed businesses skew higher - not because distress
# causes fraud, but because this generator treats them as correlated
# stylized facts for demo purposes. Document this as an assumption, not a
# claim about real-world MSME behavior.
UNDERREPORT_PROB_BY_ARCHETYPE = {"healthy": 0.05, "stagnant": 0.15, "distressed": 0.30}
UNDERREPORT_PCT_RANGE = (0.15, 0.45)   # under-reporters hide this fraction of true turnover
NORMAL_NOISE_RANGE = (0.0, 0.05)       # everyone else: small reporting/timing noise only


def _weighted_choice(options, weights, size):
    return rng.choice(options, size=size, p=weights)


def generate_borrowers():
    tiers = _weighted_choice(list(TIER_MIX.keys()), list(TIER_MIX.values()), N_BORROWERS)
    sectors = _weighted_choice(SECTORS, SECTOR_MIX, N_BORROWERS)
    archetypes = _weighted_choice(ARCHETYPES, ARCHETYPE_MIX, N_BORROWERS)

    # Business age: thin-file borrowers skew younger (less formal history
    # to have accumulated), full-financials skew older.
    business_age = np.where(
        tiers == "A",
        rng.gamma(shape=2.0, scale=1.5, size=N_BORROWERS) + 0.5,   # ~0.5-8 yrs, right-skewed young
        rng.gamma(shape=4.0, scale=2.2, size=N_BORROWERS) + 2.0,   # ~4-20 yrs
    ).round(1)

    # Tier C borrowers are "formal employers" in this generator -> EPFO applies.
    has_epfo = tiers == "C"

    # Shared true turnover base - both GST (subject to under-reporting) and
    # bank inflow (assumed to reflect true revenue) are derived from this.
    true_monthly_turnover_base = rng.uniform(3.5, 45.0, size=N_BORROWERS) * 1e5 * (
        1 + np.minimum(business_age, 15) / 15
    )

    underreport_prob = np.array([UNDERREPORT_PROB_BY_ARCHETYPE[a] for a in archetypes])
    is_underreporter = rng.random(N_BORROWERS) < underreport_prob
    gst_underreport_pct = np.where(
        is_underreporter,
        rng.uniform(*UNDERREPORT_PCT_RANGE, size=N_BORROWERS),
        rng.uniform(*NORMAL_NOISE_RANGE, size=N_BORROWERS),
    ).round(4)

    # A minority of Tier A (thin-file) borrowers genuinely have SHORT
    # history - recently GST-registered, or AA consent only just granted -
    # rather than the full 24mo/365-day window everyone else gets. Without
    # this, Module 2's "insufficient_data" completeness path never actually
    # fires on real data (every borrower would look fully complete), which
    # would leave that logic untested against anything but hand-injected
    # defects. history_available_frac scales down GST/EPFO period count and
    # bank day count for these borrowers only.
    short_history_prob = np.where(tiers == "A", 0.15, 0.0)
    has_short_history = rng.random(N_BORROWERS) < short_history_prob
    history_available_frac = np.where(
        has_short_history,
        rng.uniform(0.15, 0.45, size=N_BORROWERS),   # ~3.5-11 months of a 24mo window
        1.0,
    ).round(3)

    # --- 5C-framework attributes (v3) - always-known borrower flags, same
    # tier-conditioned boolean-mask pattern as has_epfo above. Not hidden
    # ground truth: these gate which real (if synthetic) data sources exist
    # for a borrower, the same way has_epfo already gates EPFO.
    non_gst_prob = np.where(tiers == "A", NON_GST_SHARE_TIER_A, 0.0)
    is_gst_registered = rng.random(N_BORROWERS) >= non_gst_prob

    def _tier_prob(prob_by_tier):
        return np.where(tiers == "A", prob_by_tier["A"], prob_by_tier["C"])

    balance_sheet_available = rng.random(N_BORROWERS) < _tier_prob(BALANCE_SHEET_AVAILABLE_PROB_BY_TIER)
    has_bureau_record = rng.random(N_BORROWERS) < _tier_prob(BUREAU_RECORD_PROB_BY_TIER)
    has_existing_loan = rng.random(N_BORROWERS) < _tier_prob(EXISTING_LOAN_PROB_BY_TIER)
    has_collateral = rng.random(N_BORROWERS) < _tier_prob(COLLATERAL_PROB_BY_TIER)

    borrower_ids = [f"MSME-{i+1:05d}" for i in range(N_BORROWERS)]
    consent_ids = [str(uuid.uuid4()) for _ in range(N_BORROWERS)]

    master = pd.DataFrame({
        "borrower_id": borrower_ids,
        "tier": tiers,
        "sector": sectors,
        "business_age_years": business_age,
        "has_epfo": has_epfo,
        "is_gst_registered": is_gst_registered,
        "balance_sheet_available": balance_sheet_available,
        "has_bureau_record": has_bureau_record,
        "has_existing_loan": has_existing_loan,
        "has_collateral": has_collateral,
        "consent_id": consent_ids,
    })

    ground_truth = pd.DataFrame({
        "borrower_id": borrower_ids,
        "true_archetype": archetypes,
        "true_monthly_turnover_base_inr": true_monthly_turnover_base.round(2),
        "gst_underreport_pct": gst_underreport_pct,
        "is_gst_underreporter": is_underreporter,
        "history_available_frac": history_available_frac,
        "has_short_history": has_short_history,
    })

    # Attach hidden fields temporarily so source generators can condition on
    # them without touching the ground_truth file directly (they receive it
    # as an argument, not by reading the file).
    internal = master.copy()
    internal["true_archetype"] = archetypes
    internal["true_monthly_turnover_base_inr"] = true_monthly_turnover_base
    internal["gst_underreport_pct"] = gst_underreport_pct
    internal["history_available_frac"] = history_available_frac

    return master, ground_truth, internal
