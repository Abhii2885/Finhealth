"""Loads Module 1's data lake output."""

import os
import pandas as pd


def load_data_lake(data_lake_dir):
    master = pd.read_csv(os.path.join(data_lake_dir, "borrower_master.csv"))
    gst = pd.read_csv(os.path.join(data_lake_dir, "gst_returns", "gst_returns.csv"))
    bank = pd.read_csv(os.path.join(data_lake_dir, "bank_upi_transactions", "bank_upi_transactions.csv.gz"))
    epfo = pd.read_csv(os.path.join(data_lake_dir, "epfo_contributions", "epfo_contributions.csv"))
    audit = pd.read_csv(os.path.join(data_lake_dir, "consent_audit_log.csv"))
    self_declared = pd.read_csv(os.path.join(data_lake_dir, "self_declared_turnover", "self_declared_turnover.csv"))
    balance_sheet = pd.read_csv(os.path.join(data_lake_dir, "balance_sheet", "balance_sheet.csv"))
    owners = pd.read_csv(os.path.join(data_lake_dir, "owners", "owners.csv"))
    bureau = pd.read_csv(os.path.join(data_lake_dir, "bureau_data", "bureau_data.csv"))
    legal_disputes = pd.read_csv(os.path.join(data_lake_dir, "legal_disputes", "legal_disputes.csv"))
    collateral = pd.read_csv(os.path.join(data_lake_dir, "collateral", "collateral.csv"))
    loan_facilities = pd.read_csv(os.path.join(data_lake_dir, "loan_facilities", "loan_facilities.csv"))
    loan_application = pd.read_csv(os.path.join(data_lake_dir, "loan_application", "loan_application.csv"))

    gst["due_date"] = pd.to_datetime(gst["due_date"])
    gst["filing_date"] = pd.to_datetime(gst["filing_date"])
    bank["txn_date"] = pd.to_datetime(bank["txn_date"])
    bank["due_date"] = pd.to_datetime(bank["due_date"])
    epfo["due_date"] = pd.to_datetime(epfo["due_date"])
    epfo["remittance_date"] = pd.to_datetime(epfo["remittance_date"])
    if len(legal_disputes):
        legal_disputes["filed_date"] = pd.to_datetime(legal_disputes["filed_date"])
    if len(loan_facilities):
        loan_facilities["origination_date"] = pd.to_datetime(loan_facilities["origination_date"])

    return {
        "master": master, "gst": gst, "bank": bank, "epfo": epfo, "audit": audit,
        "self_declared": self_declared, "balance_sheet": balance_sheet, "owners": owners,
        "bureau": bureau, "legal_disputes": legal_disputes, "collateral": collateral,
        "loan_facilities": loan_facilities, "loan_application": loan_application,
    }


def load_ground_truth(data_lake_dir):
    """Hidden ground truth - only for backtesting this module's own checks,
    never used as an input to the checks themselves."""
    path = os.path.join(data_lake_dir, "ground_truth", "ground_truth_labels.csv")
    return pd.read_csv(path)
