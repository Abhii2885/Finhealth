"""
Generates the base MSME borrower population.

Two files come out of this module:
  1. borrower_master  - tier, sector, business age, consent_id. This is the
     "public" record any downstream module (feature engineering, scoring)
     is allowed to see.
  2. ground_truth      - hidden archetype label per borrower. Kept
     deliberately separate. This is for backtesting the scoring engine
     later ("do distressed-archetype borrowers actually land in the
     bottom score band?"), not for training.
"""

import uuid
import pandas as pd
import numpy as np
from config import rng, N_BORROWERS, TIER_MIX, SECTORS, SECTOR_MIX, ARCHETYPES, ARCHETYPE_MIX


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

    borrower_ids = [f"MSME-{i+1:05d}" for i in range(N_BORROWERS)]
    consent_ids = [str(uuid.uuid4()) for _ in range(N_BORROWERS)]

    master = pd.DataFrame({
        "borrower_id": borrower_ids,
        "tier": tiers,
        "sector": sectors,
        "business_age_years": business_age,
        "has_epfo": has_epfo,
        "consent_id": consent_ids,
    })

    ground_truth = pd.DataFrame({
        "borrower_id": borrower_ids,
        "true_archetype": archetypes,
    })

    # Attach archetype temporarily so source generators can condition on it
    # without touching the ground_truth file directly (they receive it as
    # an argument, not by reading the file).
    internal = master.copy()
    internal["true_archetype"] = archetypes

    return master, ground_truth, internal
