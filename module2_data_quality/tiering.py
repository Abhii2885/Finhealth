"""
Dimension availability matrix + data-driven quality tier.

Two distinct outputs:
1. Per borrower, per Module-3 scoring dimension: can it be computed, and
   if not, why (insufficient_data vs not_applicable vs not_computable_in_
   prototype). This is what lets Module 5 re-normalize composite score
   weights over only the available dimensions instead of silently
   defaulting missing ones to zero.
2. A quality_tier re-derived purely from what Module 2 actually observed
   in the data (Full / Partial / Thin), compared against Module 1's
   assumed tier (A/C) so disagreements get surfaced - e.g. a Tier C
   borrower whose EPFO contributions are barely filed shouldn't quietly
   inherit "full financials" treatment downstream.
"""

import pandas as pd
from config import DIMENSION_SOURCE_MAP, QUALITY_TIER_FULL_MIN, QUALITY_TIER_PARTIAL_MIN


def _source_status(row, source):
    if source == "gst":
        return row["gst_status"]
    if source == "bank":
        return row["bank_status"]
    if source == "epfo":
        return row["epfo_status"]
    raise ValueError(source)


def build_dimension_availability(completeness_df):
    rows = []
    for _, r in completeness_df.iterrows():
        row = {"borrower_id": r["borrower_id"]}
        for dim, sources in DIMENSION_SOURCE_MAP.items():
            if not sources:
                row[dim] = "not_computable_in_prototype"
                continue
            statuses = [_source_status(r, s) for s in sources]
            if "not_applicable" in statuses:
                row[dim] = "not_applicable"
            elif "insufficient_data" in statuses:
                row[dim] = "insufficient_data"
            else:
                row[dim] = "available"
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
    out = completeness_df.copy()
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
