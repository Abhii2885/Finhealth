"""
Orchestrates all dimension feature builders into one borrower-level table.

Key rule enforced here: a left-join against the full borrower_master list
(400 rows) means any borrower a dimension builder didn't produce a row for
(e.g. Tier A borrowers have no EPFO rows) comes out as NaN, not zero. NaN
is the correct representation of "not applicable" - Module 5 must not
silently fillna(0) on these columns.
"""

import pandas as pd

from liquidity_features import build_liquidity_features
from repayment_features import build_repayment_features
from revenue_features import build_revenue_features
from operational_features import build_operational_features
from compliance_features import build_compliance_features


def build_all_features(lake, quality):
    master = lake["master"][["borrower_id", "tier", "sector", "has_epfo"]]

    liquidity = build_liquidity_features(lake["bank"])
    repayment = build_repayment_features(lake["bank"])
    revenue = build_revenue_features(lake["gst"], quality["consistency"])
    operational = build_operational_features(lake["epfo"])
    compliance = build_compliance_features(lake["gst"])

    out = master.copy()
    for df in [liquidity, repayment, revenue, operational, compliance]:
        out = out.merge(df, on="borrower_id", how="left")

    # Attach Module 2's per-dimension availability status so Module 5 knows
    # WHY a value is null (not_applicable vs insufficient_data) rather than
    # having to re-derive that from scratch.
    dim_avail = quality["dimension_availability"].copy()
    rename_map = {c: f"{c}_status" for c in dim_avail.columns if c != "borrower_id"}
    dim_avail = dim_avail.rename(columns=rename_map)
    out = out.merge(dim_avail, on="borrower_id", how="left")

    return out
