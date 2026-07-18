"""
Unifies GST-declared turnover and self-declared turnover (non-GST
borrowers) into one series: borrower_id, period, turnover_inr,
turnover_source. Built once here rather than duplicated inside
revenue_features.py and capacity_features.py (both need it - GST-vs-bank
matching, CAGR, and projected-revenue-growth all key off "this borrower's
turnover history", regardless of which regulatory status produced it).

Per borrower, only ONE source ever contributes rows - a GST-registered
borrower has zero self_declared rows and vice versa (Module 1 gates
generation on is_gst_registered), so this is a concat, not a merge.
"""

import pandas as pd


def build_unified_turnover(gst_df, self_declared_df):
    gst_part = gst_df[["borrower_id", "period", "declared_turnover_inr"]].rename(
        columns={"declared_turnover_inr": "turnover_inr"}
    ).copy()
    gst_part["turnover_source"] = "gst"

    if len(self_declared_df):
        sdt_part = self_declared_df[["borrower_id", "period", "self_declared_turnover_inr"]].rename(
            columns={"self_declared_turnover_inr": "turnover_inr"}
        ).copy()
        sdt_part["turnover_source"] = "self_declared"
    else:
        sdt_part = pd.DataFrame(columns=["borrower_id", "period", "turnover_inr", "turnover_source"])

    return pd.concat([gst_part, sdt_part], ignore_index=True)
