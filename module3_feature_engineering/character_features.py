"""
Character features (25% composite weight): bureau score + credit-limit
utilization (entity-level CIBIL/Equifax, NaN when has_bureau_record=False),
primary owner's time in business, civil-suit/other-legal-dispute RECENCY
(not a boolean, not a flat severity - see below), and cheque_bounce_rate/
cheque_bounce_count_annualized (moved here from the old
repayment_credit_behavior dimension per the 5C restructure - a behavioral
reliability signal, not a capacity metric).

Dispute recency (per the user-supplied Score Band scorecard):
civil_suit_years_since_active / other_legal_dispute_years_since_active is
0.0 if a dispute of that type is CURRENTLY ONGOING (worst), the number of
years since the most recent one was RESOLVED if all are closed (smaller =
more recent = worse), or None if the borrower has never had one at all
(best). This replaced an earlier flat 3-value severity (0/0.5/1.0) that
couldn't distinguish "resolved last month" from "resolved 9 years ago" -
the scorecard's tiers explicitly reward a longer clean track record, not
just "currently clean."
"""

import pandas as pd
import numpy as np
from config import SNAPSHOT_DATE

CHEQUE_BOUNCE_RATE_MAX = 0.10  # 10%
OWNER_TIME_IN_BUSINESS_MAX = 50  # years

# "Never had a dispute" is the BEST case, not missing data - it must NOT be
# NaN, because this pipeline's convention is NaN = not_applicable = EXCLUDED
# from scoring (Module 4 zeroes that submetric's weight). A clean record
# needs an actual value that scores as "best", not a value that vanishes
# from the composite entirely. A large sentinel (in years) does this
# correctly: it's comfortably past every named tier boundary in the Score
# Band scorecard (10yr), so it falls into the same "flat best score" bucket
# a genuinely long clean record would, without a special-case in Module 5.
NEVER_HAD_DISPUTE_SENTINEL_YEARS = 100.0


def _years_since_active(borrower_id, disputes_by_borrower):
    disputes = disputes_by_borrower.get(borrower_id)
    if not disputes:
        return NEVER_HAD_DISPUTE_SENTINEL_YEARS
    if any(d["status"] == "ongoing" for d in disputes):
        return 0.0  # currently active - worst case
    resolved_dates = [d["resolved_date"] for d in disputes if pd.notna(d["resolved_date"])]
    if not resolved_dates:
        return 0.0  # defensive: resolved status but no date somehow - treat as unresolved
    most_recent_resolution = max(resolved_dates)
    return round((SNAPSHOT_DATE - most_recent_resolution).days / 365.25, 2)


def build_character_features(bank_df, bureau_df, owners_df, legal_disputes_df):
    entity_bureau = bureau_df[bureau_df["entity_type"] == "msme_commercial"] if len(bureau_df) else bureau_df
    bureau_lookup = entity_bureau.set_index("borrower_id").to_dict("index") if len(entity_bureau) else {}

    primary_owners = owners_df[owners_df["relationship_type"] == "owner"]
    owner_tib_lookup = dict(zip(primary_owners["borrower_id"], primary_owners["owner_time_in_business_years"]))

    civil_suit_disputes = {}
    other_disputes = {}
    if len(legal_disputes_df):
        for _, d in legal_disputes_df.iterrows():
            target = civil_suit_disputes if d["dispute_type"] == "civil_suit" else other_disputes
            target.setdefault(d["borrower_id"], []).append({"status": d["status"], "resolved_date": d["resolved_date"]})

    rows = []
    for bid, g in bank_df.groupby("borrower_id"):
        n_debit_txns = (g["txn_type"] == "debit").sum()
        n_bounces = g["bounce_flag"].sum()
        bounce_rate = n_bounces / n_debit_txns if n_debit_txns else np.nan
        if pd.notna(bounce_rate):
            bounce_rate = min(bounce_rate, CHEQUE_BOUNCE_RATE_MAX)
        n_days_observed = g["txn_date"].nunique()
        observed_years = max(n_days_observed / 365, 1 / 365)
        bounce_count_annualized = n_bounces / observed_years

        bureau_rec = bureau_lookup.get(bid)
        owner_tib = owner_tib_lookup.get(bid, np.nan)
        if pd.notna(owner_tib):
            owner_tib = min(owner_tib, OWNER_TIME_IN_BUSINESS_MAX)

        rows.append({
            "borrower_id": bid,
            "bureau_score": bureau_rec["bureau_score"] if bureau_rec else np.nan,
            "credit_limit_utilization_pct": bureau_rec["credit_limit_utilization_pct"] if bureau_rec else np.nan,
            "bureau_report_date": bureau_rec["report_date"] if bureau_rec else None,
            "owner_time_in_business_years": owner_tib,
            "civil_suit_years_since_active": _years_since_active(bid, civil_suit_disputes),
            "other_legal_dispute_years_since_active": _years_since_active(bid, other_disputes),
            "cheque_bounce_rate": round(bounce_rate, 4) if pd.notna(bounce_rate) else np.nan,
            "cheque_bounce_count_annualized": round(bounce_count_annualized, 2),
        })

    return pd.DataFrame(rows)
