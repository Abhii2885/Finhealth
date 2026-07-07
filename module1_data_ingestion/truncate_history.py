"""
Truncates GST/EPFO/bank history for the minority of borrowers flagged
has_short_history=True in borrowers.py, keeping only their most recent
N periods/days. Represents a recently GST-registered or newly
AA-consented borrower who genuinely doesn't have a full 24-month/365-day
track record yet - as opposed to a full-history borrower with gaps, which
this generator does not otherwise simulate.

Applied AFTER generation (source generators always build the full window
first) so the archetype-driven trends/values themselves don't need to
change - we just drop the older rows for the flagged subset.
"""

import numpy as np
import pandas as pd
from config import GST_EPFO_MONTHS, BANK_DAYS


def _short_history_lookup(internal_borrowers):
    return dict(zip(internal_borrowers["borrower_id"], internal_borrowers["history_available_frac"]))


def truncate_gst(gst_df, internal_borrowers):
    frac_lookup = _short_history_lookup(internal_borrowers)
    keep_n = {bid: max(int(round(GST_EPFO_MONTHS * frac)), 1) for bid, frac in frac_lookup.items()}

    def _keep(group):
        bid = group.name
        n = keep_n.get(bid, GST_EPFO_MONTHS)
        if n >= GST_EPFO_MONTHS:
            return group
        return group.sort_values("period").tail(n)

    return gst_df.groupby("borrower_id", group_keys=False).apply(_keep).reset_index(drop=True)


def truncate_epfo(epfo_df, internal_borrowers):
    # same logic, only affects Tier C borrowers already (EPFO only exists for them)
    return truncate_gst(epfo_df, internal_borrowers)


def truncate_bank(bank_df, internal_borrowers):
    frac_lookup = _short_history_lookup(internal_borrowers)
    keep_days = {bid: max(int(round(BANK_DAYS * frac)), 30) for bid, frac in frac_lookup.items()}

    def _keep(group):
        bid = group.name
        n = keep_days.get(bid, BANK_DAYS)
        if n >= BANK_DAYS:
            return group
        cutoff = group["txn_date"].max() - pd.Timedelta(days=n)
        return group[group["txn_date"] > cutoff]

    bank_df = bank_df.copy()
    bank_df["txn_date"] = pd.to_datetime(bank_df["txn_date"])
    result = bank_df.groupby("borrower_id", group_keys=False).apply(_keep).reset_index(drop=True)
    result["txn_date"] = result["txn_date"].dt.date
    return result
