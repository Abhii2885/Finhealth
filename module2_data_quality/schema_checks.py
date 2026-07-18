"""
Schema / range / referential-integrity validation for each Module 1 source.

Each check function returns a list of issue dicts:
    {"source": ..., "check": ..., "borrower_id": ... or None, "detail": ...}

Deliberately simple, rule-based checks - no ML here. This is the layer that
catches "this data is malformed" before anything downstream tries to
compute features on it.
"""

import pandas as pd
from config import DATA_SNAPSHOT_DATE


def check_gst(gst_df, valid_borrower_ids, today):
    issues = []

    dup = gst_df.duplicated(subset=["borrower_id", "period"], keep=False)
    if dup.any():
        for bid in gst_df.loc[dup, "borrower_id"].unique():
            issues.append({"source": "gst", "check": "duplicate_period", "borrower_id": bid,
                            "detail": "More than one return filed for the same period"})

    dup_record = gst_df.duplicated(subset=["record_id"], keep=False)
    if dup_record.any():
        issues.append({"source": "gst", "check": "duplicate_record_id", "borrower_id": None,
                        "detail": f"{dup_record.sum()} rows share a record_id"})

    orphan = ~gst_df["borrower_id"].isin(valid_borrower_ids)
    if orphan.any():
        for bid in gst_df.loc[orphan, "borrower_id"].unique():
            issues.append({"source": "gst", "check": "orphan_borrower_id", "borrower_id": bid,
                            "detail": "borrower_id not present in borrower_master"})

    neg_turnover = gst_df["declared_turnover_inr"] < 0
    if neg_turnover.any():
        for bid in gst_df.loc[neg_turnover, "borrower_id"].unique():
            issues.append({"source": "gst", "check": "negative_turnover", "borrower_id": bid,
                            "detail": "declared_turnover_inr < 0"})

    neg_tax = gst_df["tax_paid_inr"] < 0
    if neg_tax.any():
        for bid in gst_df.loc[neg_tax, "borrower_id"].unique():
            issues.append({"source": "gst", "check": "negative_tax_paid", "borrower_id": bid,
                            "detail": "tax_paid_inr < 0"})

    future_filing = gst_df["filing_date"] > today
    if future_filing.any():
        for bid in gst_df.loc[future_filing, "borrower_id"].unique():
            issues.append({"source": "gst", "check": "future_filing_date", "borrower_id": bid,
                            "detail": "filing_date is after today"})

    return issues


def check_bank(bank_df, valid_borrower_ids, today):
    issues = []

    dup_record = bank_df.duplicated(subset=["record_id"], keep=False)
    if dup_record.any():
        issues.append({"source": "bank", "check": "duplicate_record_id", "borrower_id": None,
                        "detail": f"{dup_record.sum()} rows share a record_id"})

    orphan = ~bank_df["borrower_id"].isin(valid_borrower_ids)
    if orphan.any():
        for bid in bank_df.loc[orphan, "borrower_id"].unique():
            issues.append({"source": "bank", "check": "orphan_borrower_id", "borrower_id": bid,
                            "detail": "borrower_id not present in borrower_master"})

    neg_amount = bank_df["amount_inr"] <= 0
    if neg_amount.any():
        for bid in bank_df.loc[neg_amount, "borrower_id"].unique():
            issues.append({"source": "bank", "check": "non_positive_amount", "borrower_id": bid,
                            "detail": "amount_inr <= 0"})

    future_txn = bank_df["txn_date"] > today
    if future_txn.any():
        for bid in bank_df.loc[future_txn, "borrower_id"].unique():
            issues.append({"source": "bank", "check": "future_txn_date", "borrower_id": bid,
                            "detail": "txn_date is after today"})

    bad_type = ~bank_df["txn_type"].isin(["credit", "debit"])
    if bad_type.any():
        issues.append({"source": "bank", "check": "invalid_txn_type", "borrower_id": None,
                        "detail": f"{bad_type.sum()} rows have an unrecognized txn_type"})

    return issues


def check_epfo(epfo_df, valid_borrower_ids, has_epfo_ids, today):
    issues = []

    orphan = ~epfo_df["borrower_id"].isin(valid_borrower_ids)
    if orphan.any():
        for bid in epfo_df.loc[orphan, "borrower_id"].unique():
            issues.append({"source": "epfo", "check": "orphan_borrower_id", "borrower_id": bid,
                            "detail": "borrower_id not present in borrower_master"})

    # Business-rule check: EPFO records should only exist for borrowers
    # flagged has_epfo=True in borrower_master (Tier C in this prototype).
    not_flagged = ~epfo_df["borrower_id"].isin(has_epfo_ids)
    if not_flagged.any():
        for bid in epfo_df.loc[not_flagged, "borrower_id"].unique():
            issues.append({"source": "epfo", "check": "epfo_without_has_epfo_flag", "borrower_id": bid,
                            "detail": "EPFO records exist but borrower_master.has_epfo is False"})

    neg_headcount = epfo_df["employee_count"] <= 0
    if neg_headcount.any():
        for bid in epfo_df.loc[neg_headcount, "borrower_id"].unique():
            issues.append({"source": "epfo", "check": "non_positive_headcount", "borrower_id": bid,
                            "detail": "employee_count <= 0"})

    future_remit = epfo_df["remittance_date"] > today
    if future_remit.any():
        for bid in epfo_df.loc[future_remit, "borrower_id"].unique():
            issues.append({"source": "epfo", "check": "future_remittance_date", "borrower_id": bid,
                            "detail": "remittance_date is after today"})

    return issues


def check_balance_sheet(balance_sheet_df, valid_borrower_ids):
    issues = []
    if not len(balance_sheet_df):
        return issues

    orphan = ~balance_sheet_df["borrower_id"].isin(valid_borrower_ids)
    if orphan.any():
        for bid in balance_sheet_df.loc[orphan, "borrower_id"].unique():
            issues.append({"source": "balance_sheet", "check": "orphan_borrower_id", "borrower_id": bid,
                            "detail": "borrower_id not present in borrower_master"})

    bad_liabilities = balance_sheet_df["current_liabilities_inr"] <= 0
    if bad_liabilities.any():
        for bid in balance_sheet_df.loc[bad_liabilities, "borrower_id"].unique():
            issues.append({"source": "balance_sheet", "check": "non_positive_current_liabilities", "borrower_id": bid,
                            "detail": "current_liabilities_inr <= 0"})

    bad_assets = balance_sheet_df["total_assets_inr"] <= 0
    if bad_assets.any():
        for bid in balance_sheet_df.loc[bad_assets, "borrower_id"].unique():
            issues.append({"source": "balance_sheet", "check": "non_positive_total_assets", "borrower_id": bid,
                            "detail": "total_assets_inr <= 0"})

    return issues


def check_loan_facilities(loan_facilities_df, valid_borrower_ids):
    issues = []
    if not len(loan_facilities_df):
        return issues

    orphan = ~loan_facilities_df["borrower_id"].isin(valid_borrower_ids)
    if orphan.any():
        for bid in loan_facilities_df.loc[orphan, "borrower_id"].unique():
            issues.append({"source": "loan_facilities", "check": "orphan_borrower_id", "borrower_id": bid,
                            "detail": "borrower_id not present in borrower_master"})

    over_outstanding = loan_facilities_df["principal_outstanding_inr"] > loan_facilities_df["original_principal_inr"]
    if over_outstanding.any():
        for bid in loan_facilities_df.loc[over_outstanding, "borrower_id"].unique():
            issues.append({"source": "loan_facilities", "check": "outstanding_exceeds_original", "borrower_id": bid,
                            "detail": "principal_outstanding_inr > original_principal_inr"})

    return issues


def run_all_checks(lake, today=None):
    if today is None:
        today = DATA_SNAPSHOT_DATE
    valid_ids = set(lake["master"]["borrower_id"])
    has_epfo_ids = set(lake["master"].loc[lake["master"]["has_epfo"], "borrower_id"])

    issues = []
    issues += check_gst(lake["gst"], valid_ids, today)
    issues += check_bank(lake["bank"], valid_ids, today)
    issues += check_epfo(lake["epfo"], valid_ids, has_epfo_ids, today)
    issues += check_balance_sheet(lake["balance_sheet"], valid_ids)
    issues += check_loan_facilities(lake["loan_facilities"], valid_ids)
    return pd.DataFrame(issues, columns=["source", "check", "borrower_id", "detail"])
