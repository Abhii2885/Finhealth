"""
Synthetic CIBIL/Equifax-style bureau records - covers "entity + owners +
guarantors + related parties" (per the 5C Character requirement) via an
entity_type column, rather than a separate table per party type.

The commercial (entity-level) row only exists for borrowers with
has_bureau_record == True (config.BUREAU_RECORD_PROB_BY_TIER - Tier A
thin-file borrowers are much less likely to have one, by definition).
Owner/guarantor/related-party rows are independent of the entity's own
bureau-record flag (an individual can have a personal bureau file even if
the business itself has no commercial bureau footprint yet) but still
require owners_source.py's rows to exist first (this file reads them).
"""

import numpy as np
import pandas as pd
from config import rng, OBS_END_DATE

# Bureau reports are pulled at some point before the data-lake snapshot,
# not exactly on it - a small random lag (0-60 days) reads more like a
# real bureau pull than every borrower sharing one flat date.
REPORT_DATE_LAG_DAYS_RANGE = (0, 60)

BUREAU_PARAMS_BY_ARCHETYPE = {
    # bureau_score on a 300-900 scale (CIBIL-style), higher is healthier.
    "healthy":    {"score_mean": 760, "score_sd": 40, "dpd_weights": {"0": 0.85, "30": 0.10, "60": 0.04, "90+": 0.01}},
    "stagnant":   {"score_mean": 680, "score_sd": 55, "dpd_weights": {"0": 0.55, "30": 0.25, "60": 0.13, "90+": 0.07}},
    "distressed": {"score_mean": 570, "score_sd": 70, "dpd_weights": {"0": 0.25, "30": 0.25, "60": 0.25, "90+": 0.25}},
}

# Individual (owner/guarantor) bureau records are correlated with the same
# archetype but slightly less extreme than the commercial score - an
# owner's personal credit discipline tends to track but not perfectly
# mirror the business's health.
INDIVIDUAL_SCORE_DAMPING = 0.6
INDIVIDUAL_HAS_RECORD_PROB = 0.70

DPD_BUCKETS = ["0", "30", "60", "90+"]


def _draw_score(mean, sd):
    return int(np.clip(rng.normal(mean, sd), 300, 900))


def _draw_dpd_summary(weights):
    return rng.choice(DPD_BUCKETS, p=[weights[b] for b in DPD_BUCKETS])


def _report_date():
    lag = int(rng.integers(*REPORT_DATE_LAG_DAYS_RANGE))
    return (pd.Timestamp(OBS_END_DATE) - pd.Timedelta(days=lag)).date()


def generate_bureau_data(internal_borrowers, owners_df):
    rows = []

    entity_borrowers = internal_borrowers[internal_borrowers["has_bureau_record"]]
    for _, b in entity_borrowers.iterrows():
        params = BUREAU_PARAMS_BY_ARCHETYPE[b["true_archetype"]]
        rows.append({
            "borrower_id": b["borrower_id"],
            "entity_id": b["borrower_id"],
            "entity_type": "msme_commercial",
            "bureau_score": _draw_score(params["score_mean"], params["score_sd"]),
            "dpd_bucket_summary": _draw_dpd_summary(params["dpd_weights"]),
            "credit_limit_utilization_pct": round(float(np.clip(rng.normal(
                40 if b["true_archetype"] == "healthy" else 65 if b["true_archetype"] == "stagnant" else 88,
                15), 0, 100)), 1),
            "num_active_facilities": int(rng.integers(1, 6)),
            "report_date": _report_date(),
        })

    archetype_lookup = dict(zip(internal_borrowers["borrower_id"], internal_borrowers["true_archetype"]))
    entity_type_map = {"owner": "owner_individual", "guarantor": "guarantor_individual", "related_party": "related_party"}

    for _, o in owners_df.iterrows():
        if rng.random() >= INDIVIDUAL_HAS_RECORD_PROB:
            continue
        archetype = archetype_lookup.get(o["borrower_id"])
        params = BUREAU_PARAMS_BY_ARCHETYPE[archetype]
        damped_mean = 700 + (params["score_mean"] - 700) * INDIVIDUAL_SCORE_DAMPING
        rows.append({
            "borrower_id": o["borrower_id"],
            "entity_id": o["owner_id"],
            "entity_type": entity_type_map[o["relationship_type"]],
            "bureau_score": _draw_score(damped_mean, params["score_sd"] * 0.8),
            "dpd_bucket_summary": _draw_dpd_summary(params["dpd_weights"]),
            "credit_limit_utilization_pct": round(float(np.clip(rng.normal(45, 20), 0, 100)), 1),
            "num_active_facilities": int(rng.integers(0, 4)),
            "report_date": _report_date(),
        })

    return pd.DataFrame(rows)
