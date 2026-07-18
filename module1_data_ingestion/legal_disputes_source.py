"""
Synthetic civil suits / other legal disputes - sparse by design. Most
borrowers have zero rows here, which is a valid, complete "no disputes"
answer (not missing data) - Module 3's dispute features must treat an
absent borrower_id as "never had one" (the best tier), never NaN.

v4: filed_date now spans up to 12 years back (was 3), and resolved
disputes get an explicit resolved_date - both needed for the Score Band
scorecard's recency-tiered Character scoring (active/active-in-3yrs vs
resolved-within-5yrs vs resolved-within-10yrs vs never-had-one), which
needs to know not just WHETHER a dispute happened but HOW LONG AGO it
was last active.
"""

import uuid
import pandas as pd
from config import rng, OBS_END_DATE

LEGAL_DISPUTE_PROB_BY_ARCHETYPE = {"healthy": 0.03, "stagnant": 0.08, "distressed": 0.20}
DISPUTE_TYPE_MIX = {"civil_suit": 0.6, "other_legal_dispute": 0.4}
STATUS_MIX = {"ongoing": 0.35, "resolved": 0.65}

FILED_DAYS_AGO_RANGE = (30, 12 * 365)  # up to 12 years back, for recency-tier spread
RESOLUTION_DURATION_DAYS_RANGE = (60, 730)  # typical time from filing to resolution


def generate_legal_disputes(internal_borrowers):
    rows = []
    end = pd.Timestamp(OBS_END_DATE)

    for _, b in internal_borrowers.iterrows():
        prob = LEGAL_DISPUTE_PROB_BY_ARCHETYPE[b["true_archetype"]]
        if rng.random() >= prob:
            continue
        n_disputes = 1 if rng.random() < 0.8 else 2
        for _ in range(n_disputes):
            dispute_type = rng.choice(list(DISPUTE_TYPE_MIX.keys()), p=list(DISPUTE_TYPE_MIX.values()))
            status = rng.choice(list(STATUS_MIX.keys()), p=list(STATUS_MIX.values()))
            filed_date_ts = end - pd.Timedelta(days=int(rng.integers(*FILED_DAYS_AGO_RANGE)))
            amount = round(b["true_monthly_turnover_base_inr"] * rng.uniform(0.1, 2.5), 2)

            resolved_date = None
            if status == "resolved":
                duration = int(rng.integers(*RESOLUTION_DURATION_DAYS_RANGE))
                resolved_ts = min(filed_date_ts + pd.Timedelta(days=duration), end)
                resolved_date = resolved_ts.date()
                # A dispute "resolved" after today's snapshot doesn't make
                # sense - if the random duration would push past OBS_END_DATE,
                # it's still genuinely open as of this snapshot.
                if resolved_ts >= end:
                    status = "ongoing"
                    resolved_date = None

            rows.append({
                "borrower_id": b["borrower_id"],
                "dispute_id": str(uuid.uuid4()),
                "dispute_type": dispute_type,
                "status": status,
                "filed_date": filed_date_ts.date(),
                "resolved_date": resolved_date,
                "amount_involved_inr": amount,
            })

    return pd.DataFrame(rows)
