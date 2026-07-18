"""
Per-borrower, per-source completeness metrics.

The key design rule (per architecture doc): a source that doesn't apply to
a borrower (e.g. EPFO for a Tier A/thin-file borrower) is "not_applicable",
NOT "missing" and NOT scored as zero. Only a source that SHOULD have data
but doesn't (or has too little) is flagged "insufficient_data". Conflating
the two penalizes exactly the credit-invisible borrowers this whole
project is supposed to help.

v3: adds completeness checks for the 8 new 5C sources. Point-in-time/
snapshot sources (balance_sheet, bureau, loan_facilities, collateral,
owners) don't have a "coverage" concept the way a 36-month time series
does - completeness there just means "does the expected row exist," using
the same has-flag pattern epfo_completeness already established.
"""

import pandas as pd
from config import (
    GST_EPFO_MONTHS, BANK_DAYS,
    GST_MIN_FILING_COVERAGE, BANK_MIN_ACTIVE_DAY_COVERAGE, BANK_MIN_ANNUAL_TXN_COUNT,
    EPFO_MIN_FILING_COVERAGE, SELF_DECLARED_MIN_FILING_COVERAGE,
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


def self_declared_completeness(self_declared_df):
    if self_declared_df.empty:
        return pd.DataFrame(columns=["borrower_id", "self_declared_coverage", "self_declared_status"])
    s = self_declared_df.groupby("borrower_id").agg(
        periods_present=("period", "count"),
    ).reset_index()
    s["self_declared_coverage"] = s["periods_present"] / GST_EPFO_MONTHS
    s["self_declared_status"] = s["self_declared_coverage"].apply(
        lambda c: "sufficient" if c >= SELF_DECLARED_MIN_FILING_COVERAGE else "insufficient_data"
    )
    return s[["borrower_id", "self_declared_coverage", "self_declared_status"]]


def turnover_completeness(gst_c, self_declared_c, master_df):
    """
    Unified 'turnover' virtual-source status: whichever of GST/self-declared
    actually applies to a borrower (per is_gst_registered), not a merge of
    both. Feeds capacity.cash_flow_match_ratio / revenue_cagr_3yr /
    projected_revenue_growth_rate - these should never be penalized for a
    non-GST borrower simply lacking GST rows.
    """
    out = master_df[["borrower_id", "is_gst_registered"]].copy()
    out = out.merge(gst_c[["borrower_id", "gst_status"]], on="borrower_id", how="left")
    out = out.merge(self_declared_c[["borrower_id", "self_declared_status"]], on="borrower_id", how="left")
    out["turnover_status"] = out.apply(
        lambda r: r["gst_status"] if r["is_gst_registered"] else r["self_declared_status"], axis=1
    )
    out["turnover_status"] = out["turnover_status"].fillna("insufficient_data")
    return out[["borrower_id", "turnover_status"]]


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


def _has_flag_completeness(df, master_df, flag_col, status_col):
    """
    Shared pattern for point-in-time sources gated by a single master flag:
    not_applicable if the flag is False, sufficient if a row exists and the
    flag is True, insufficient_data if the flag is True but no row exists
    (shouldn't happen given how Module 1 generates these, but defensive).
    """
    present_ids = set(df["borrower_id"]) if len(df) else set()
    out = master_df[["borrower_id", flag_col]].copy()

    def status(row):
        if not row[flag_col]:
            return "not_applicable"
        return "sufficient" if row["borrower_id"] in present_ids else "insufficient_data"

    out[status_col] = out.apply(status, axis=1)
    return out[["borrower_id", status_col]]


def balance_sheet_completeness(balance_sheet_df, master_df):
    return _has_flag_completeness(balance_sheet_df, master_df, "balance_sheet_available", "balance_sheet_status")


def bureau_completeness(bureau_df, master_df):
    entity_rows = bureau_df[bureau_df["entity_type"] == "msme_commercial"] if len(bureau_df) else bureau_df
    return _has_flag_completeness(entity_rows, master_df, "has_bureau_record", "bureau_status")


def loan_facilities_completeness(loan_facilities_df, master_df):
    return _has_flag_completeness(loan_facilities_df, master_df, "has_existing_loan", "loan_facilities_status")


def collateral_completeness(collateral_df, master_df):
    return _has_flag_completeness(collateral_df, master_df, "has_collateral", "collateral_status")


def covenant_completeness(loan_facilities_df, master_df):
    """
    covenant_compliance_flag is only applicable if a borrower BOTH has an
    existing loan AND that loan carries a covenant (has_covenant=True) -
    a row-level attribute, not a master flag, so this needs its own check
    rather than reusing _has_flag_completeness. Adds a
    has_covenant_effective column to master-shaped output so tiering.py
    can gate on it like any other flag.
    """
    covenant_borrowers = set()
    if len(loan_facilities_df):
        covenant_borrowers = set(loan_facilities_df.loc[loan_facilities_df["has_covenant"], "borrower_id"])

    out = master_df[["borrower_id"]].copy()
    out["has_covenant_effective"] = out["borrower_id"].isin(covenant_borrowers)
    out["covenant_status"] = out["has_covenant_effective"].map({True: "sufficient", False: "not_applicable"})
    return out[["borrower_id", "has_covenant_effective", "covenant_status"]]


def owners_completeness(owners_df, master_df):
    """Every borrower always gets >=1 owner row - status is 'sufficient'
    for everyone unless the generator genuinely produced zero rows."""
    present_ids = set(owners_df["borrower_id"]) if len(owners_df) else set()
    out = master_df[["borrower_id"]].copy()
    out["owners_status"] = out["borrower_id"].apply(lambda bid: "sufficient" if bid in present_ids else "insufficient_data")
    return out[["borrower_id", "owners_status"]]


def legal_disputes_completeness(master_df):
    """Always applicable, always 'sufficient' - zero rows is a valid,
    complete 'no disputes' answer, not missing data."""
    out = master_df[["borrower_id"]].copy()
    out["legal_disputes_status"] = "sufficient"
    return out


def bank_scheduled_obligation_coverage(bank_df):
    """
    Diagnostic only (not part of any submetric gate - utility/rent/salary
    timeliness reuse bank_status, since if the bank pull itself is thin
    there's no reason to trust ANY category breakdown from it, scheduled or
    not). Reports what fraction of scheduled-obligation rows carry a
    due_date, mostly to catch a future Module 1 regression.
    """
    scheduled = bank_df[bank_df["category"].isin(["salary_payment", "utility_payment", "rent_payment", "loan_emi"])]
    if not len(scheduled):
        return pd.DataFrame(columns=["borrower_id", "scheduled_obligation_due_date_coverage"])
    cov = scheduled.groupby("borrower_id").apply(
        lambda g: g["due_date"].notna().mean(), include_groups=False
    ).rename("scheduled_obligation_due_date_coverage").reset_index()
    return cov


def counterparty_coverage(bank_df):
    """Diagnostic only - fraction of sales_inflow/vendor_payment rows with
    a non-null counterparty_id, per borrower."""
    concentration_rows = bank_df[bank_df["category"].isin(["sales_inflow", "vendor_payment"])]
    if not len(concentration_rows):
        return pd.DataFrame(columns=["borrower_id", "counterparty_id_coverage"])
    cov = concentration_rows.groupby("borrower_id").apply(
        lambda g: g["counterparty_id"].notna().mean(), include_groups=False
    ).rename("counterparty_id_coverage").reset_index()
    return cov


def build_completeness_report(lake):
    master = lake["master"]
    gst_c = gst_completeness(lake["gst"])
    self_declared_c = self_declared_completeness(lake["self_declared"])
    turnover_c = turnover_completeness(gst_c, self_declared_c, master)
    bank_c = bank_completeness(lake["bank"])
    epfo_c = epfo_completeness(lake["epfo"], master)
    balance_sheet_c = balance_sheet_completeness(lake["balance_sheet"], master)
    bureau_c = bureau_completeness(lake["bureau"], master)
    loan_facilities_c = loan_facilities_completeness(lake["loan_facilities"], master)
    covenant_c = covenant_completeness(lake["loan_facilities"], master)
    collateral_c = collateral_completeness(lake["collateral"], master)
    owners_c = owners_completeness(lake["owners"], master)
    legal_c = legal_disputes_completeness(master)

    keep_cols = ["borrower_id", "tier", "sector", "has_epfo", "is_gst_registered",
                 "balance_sheet_available", "has_bureau_record", "has_existing_loan", "has_collateral"]
    report = master[keep_cols].copy()
    for c in [gst_c, self_declared_c, turnover_c, bank_c, epfo_c, balance_sheet_c, bureau_c,
              loan_facilities_c, covenant_c, collateral_c, owners_c, legal_c]:
        report = report.merge(c, on="borrower_id", how="left")
    return report
