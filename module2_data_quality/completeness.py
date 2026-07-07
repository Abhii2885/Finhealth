"""
Per-borrower, per-source completeness metrics.

The key design rule (per architecture doc): a source that doesn't apply to
a borrower (e.g. EPFO for a Tier A/thin-file borrower) is "not_applicable",
NOT "missing" and NOT scored as zero. Only a source that SHOULD have data
but doesn't (or has too little) is flagged "insufficient_data". Conflating
the two penalizes exactly the credit-invisible borrowers this whole
project is supposed to help.
"""

import pandas as pd
from config import (
    GST_EPFO_MONTHS, BANK_DAYS,
    GST_MIN_FILING_COVERAGE, BANK_MIN_ACTIVE_DAY_COVERAGE, BANK_MIN_ANNUAL_TXN_COUNT,
    EPFO_MIN_FILING_COVERAGE,
)


def gst_completeness(gst_df):
    g = gst_df.groupby("borrower_id").agg(
        periods_present=("period", "count"),
        periods_filed=("filing_date", lambda s: s.notna().sum()),
    ).reset_index()
    g["gst_filing_coverage"] = g["periods_filed"] / GST_EPFO_MONTHS
    g["gst_status"] = g["gst_filing_coverage"].apply(
        lambda c: "sufficient" if c >= GST_MIN_FILING_COVERAGE else "insufficient_data"
    )
    return g[["borrower_id", "gst_filing_coverage", "gst_status"]]


def bank_completeness(bank_df):
    active_days = bank_df.groupby("borrower_id")["txn_date"].nunique().rename("bank_active_days")
    txn_count = bank_df.groupby("borrower_id").size().rename("bank_txn_count")
    b = pd.concat([active_days, txn_count], axis=1).reset_index()
    b["bank_active_day_coverage"] = b["bank_active_days"] / BANK_DAYS
    b["bank_status"] = b.apply(
        lambda r: "sufficient" if (
            r["bank_active_day_coverage"] >= BANK_MIN_ACTIVE_DAY_COVERAGE
            and r["bank_txn_count"] >= BANK_MIN_ANNUAL_TXN_COUNT
        ) else "insufficient_data",
        axis=1,
    )
    return b[["borrower_id", "bank_active_day_coverage", "bank_txn_count", "bank_status"]]


def epfo_completeness(epfo_df, master_df):
    has_epfo_ids = master_df.loc[master_df["has_epfo"], "borrower_id"]
    all_ids = master_df["borrower_id"]

    e = epfo_df.groupby("borrower_id").agg(
        periods_present=("period", "count"),
        periods_remitted=("remittance_date", lambda s: s.notna().sum()),
    ).reset_index()
    e["epfo_filing_coverage"] = e["periods_remitted"] / GST_EPFO_MONTHS

    out = pd.DataFrame({"borrower_id": all_ids})
    out = out.merge(e[["borrower_id", "epfo_filing_coverage"]], on="borrower_id", how="left")

    def status(row):
        if row["borrower_id"] not in set(has_epfo_ids):
            return "not_applicable"
        if pd.isna(row["epfo_filing_coverage"]) or row["epfo_filing_coverage"] < EPFO_MIN_FILING_COVERAGE:
            return "insufficient_data"
        return "sufficient"

    out["epfo_status"] = out.apply(status, axis=1)
    out["epfo_filing_coverage"] = out["epfo_filing_coverage"].fillna(0.0)
    return out


def build_completeness_report(lake):
    master = lake["master"]
    gst_c = gst_completeness(lake["gst"])
    bank_c = bank_completeness(lake["bank"])
    epfo_c = epfo_completeness(lake["epfo"], master)

    report = master[["borrower_id", "tier", "sector", "has_epfo"]].copy()
    report = report.merge(gst_c, on="borrower_id", how="left")
    report = report.merge(bank_c, on="borrower_id", how="left")
    report = report.merge(epfo_c, on="borrower_id", how="left")
    return report
