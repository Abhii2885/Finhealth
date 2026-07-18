"""
Orchestrates all 5C feature builders into one borrower-level table.

Key rule enforced here: a left-join against the full borrower_master list
(400 rows) means any borrower a builder didn't produce a row for (e.g.
Tier A borrowers have no balance_sheet row) comes out as NaN, not zero.
NaN is the correct representation of "not applicable" - Module 5 must not
silently fillna(0) on these columns.
"""

import pandas as pd

from capacity_features import build_capacity_features
from character_features import build_character_features
from capital_features import build_capital_features
from collateral_features import build_collateral_features
from compliance_features import build_compliance_features
from turnover_unify import build_unified_turnover


def build_all_features(lake, quality):
    master = lake["master"][["borrower_id", "tier", "sector", "has_epfo", "is_gst_registered",
                              "balance_sheet_available", "has_bureau_record", "has_existing_loan",
                              "has_collateral"]]

    turnover_df = build_unified_turnover(lake["gst"], lake["self_declared"])

    capacity = build_capacity_features(
        lake["bank"], turnover_df, lake["balance_sheet"], lake["loan_facilities"], lake["loan_application"],
        quality["consistency"]
    )
    character = build_character_features(lake["bank"], lake["bureau"], lake["owners"], lake["legal_disputes"])
    capital = build_capital_features(lake["balance_sheet"])
    collateral = build_collateral_features(lake["collateral"])
    compliance = build_compliance_features(lake["gst"], lake["epfo"], lake["bank"], lake["loan_facilities"])

    out = master.copy()
    for df in [capacity, character, capital, collateral, compliance]:
        out = out.merge(df, on="borrower_id", how="left")

    # Attach Module 2's per-(dimension, submetric) availability status so
    # Module 4/5 know WHY a value is null (not_applicable vs
    # insufficient_data) rather than having to re-derive that from scratch.
    # Columns are already named "{dimension}__{submetric}_status".
    submetric_avail = quality["submetric_availability"]
    out = out.merge(submetric_avail, on="borrower_id", how="left")

    return out
