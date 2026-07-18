"""
Submetric availability matrix + data-driven quality tier.

Two distinct outputs:
1. Per borrower, per (dimension, submetric) pair from the 5C framework:
   can it be computed, and if not, why (insufficient_data vs
   not_applicable). This is what lets Module 4 re-normalize weights over
   only the available submetrics within each C, one level deeper than the
   old whole-dimension version of this file.
2. A quality_tier re-derived purely from what Module 2 actually observed
   in the GST/bank/EPFO time series (Full / Partial / Thin) - unchanged
   from v1/v2. This measures time-series depth, a different concept from
   "does a balance sheet exist at all" (the new submetric statuses below),
   so it's deliberately NOT expanded to cover the new 5C sources.
"""

import pandas as pd
from config import SUBMETRIC_SOURCE_MAP, QUALITY_TIER_FULL_MIN, QUALITY_TIER_PARTIAL_MIN

SOURCE_STATUS_COL = {
    "gst": "gst_status",
    "bank": "bank_status",
    "epfo": "epfo_status",
    "balance_sheet": "balance_sheet_status",
    "bureau_data": "bureau_status",
    "legal_disputes": "legal_disputes_status",
    "owners": "owners_status",
    "loan_facilities": "loan_facilities_status",
    "collateral": "collateral_status",
    "turnover": "turnover_status",
}


def _source_status(row, source):
    return row[SOURCE_STATUS_COL[source]]


def build_submetric_availability(completeness_df):
    rows = []
    for _, r in completeness_df.iterrows():
        row = {"borrower_id": r["borrower_id"]}
        for (dim, submetric), spec in SUBMETRIC_SOURCE_MAP.items():
            col = f"{dim}__{submetric}_status"
            gating_flag = spec["gating_flag"]
            if gating_flag is not None and not bool(r[gating_flag]):
                row[col] = "not_applicable"
                continue
            statuses = [_source_status(r, s) for s in spec["sources"]]
            if "not_applicable" in statuses:
                row[col] = "not_applicable"
            elif "insufficient_data" in statuses:
                row[col] = "insufficient_data"
            else:
                row[col] = "available"
        rows.append(row)
    return pd.DataFrame(rows)


def _quality_tier(row):
    # gst/bank coverage always apply; epfo coverage only counts if applicable
    scores = [row["gst_filing_coverage"], row["bank_active_day_coverage"]]
    if row["epfo_status"] != "not_applicable":
        scores.append(row["epfo_filing_coverage"])
    min_score = min(scores)
    if min_score >= QUALITY_TIER_FULL_MIN:
        return "Full"
    if min_score >= QUALITY_TIER_PARTIAL_MIN:
        return "Partial"
    return "Thin"


def build_quality_tier(completeness_df):
    # Non-GST borrowers have no gst_filing_coverage - substitute
    # self_declared_coverage for them so this quality-tier concept (time-
    # series depth) still works, instead of erroring on NaN.
    out = completeness_df.copy()
    out["gst_filing_coverage"] = out["gst_filing_coverage"].fillna(out.get("self_declared_coverage"))
    out["gst_filing_coverage"] = out["gst_filing_coverage"].fillna(0.0)

    out["quality_tier"] = out.apply(_quality_tier, axis=1)

    # The ONE genuinely meaningful check this generator can produce: Module 1
    # assigns Tier C = "formal employer, has EPFO" by construction, but that's
    # an input assumption, not a guarantee the EPFO data that comes back is
    # actually usable. Flag Tier C borrowers whose EPFO completeness doesn't
    # support the "full financials" label they were assumed to have.
    # (We do NOT compare Tier A borrowers' quality_tier against an expected
    # label - a Tier A borrower with clean GST/bank data legitimately earns
    # "Full" completeness on the dimensions that apply to them, and that's
    # not a disagreement with anything Module 1 claimed.)
    out["epfo_reliability_flag"] = "not_applicable"
    tier_c_mask = out["tier"] == "C"
    out.loc[tier_c_mask, "epfo_reliability_flag"] = out.loc[tier_c_mask, "epfo_status"].map(
        {"sufficient": "reliable", "insufficient_data": "unreliable_despite_tier_c"}
    )

    return out[["borrower_id", "tier", "quality_tier", "epfo_reliability_flag"]]
