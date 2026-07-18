"""Loads Module 1's data lake + Module 2's quality outputs."""

import os
import pandas as pd


def load_data_lake(data_lake_dir):
    master = pd.read_csv(os.path.join(data_lake_dir, "borrower_master.csv"))
    gst = pd.read_csv(os.path.join(data_lake_dir, "gst_returns", "gst_returns.csv"))
    bank = pd.read_csv(os.path.join(data_lake_dir, "bank_upi_transactions", "bank_upi_transactions.csv.gz"))
    epfo = pd.read_csv(os.path.join(data_lake_dir, "epfo_contributions", "epfo_contributions.csv"))
    self_declared = pd.read_csv(os.path.join(data_lake_dir, "self_declared_turnover", "self_declared_turnover.csv"))
    balance_sheet = pd.read_csv(os.path.join(data_lake_dir, "balance_sheet", "balance_sheet.csv"))
    owners = pd.read_csv(os.path.join(data_lake_dir, "owners", "owners.csv"))
    bureau = pd.read_csv(os.path.join(data_lake_dir, "bureau_data", "bureau_data.csv"))
    legal_disputes = pd.read_csv(os.path.join(data_lake_dir, "legal_disputes", "legal_disputes.csv"))
    if len(legal_disputes):
        legal_disputes["filed_date"] = pd.to_datetime(legal_disputes["filed_date"])
        legal_disputes["resolved_date"] = pd.to_datetime(legal_disputes["resolved_date"])
    collateral = pd.read_csv(os.path.join(data_lake_dir, "collateral", "collateral.csv"))
    loan_facilities = pd.read_csv(os.path.join(data_lake_dir, "loan_facilities", "loan_facilities.csv"))
    loan_application = pd.read_csv(os.path.join(data_lake_dir, "loan_application", "loan_application.csv"))

    gst["due_date"] = pd.to_datetime(gst["due_date"])
    gst["filing_date"] = pd.to_datetime(gst["filing_date"])
    bank["txn_date"] = pd.to_datetime(bank["txn_date"])
    bank["due_date"] = pd.to_datetime(bank["due_date"])
    epfo["due_date"] = pd.to_datetime(epfo["due_date"])
    epfo["remittance_date"] = pd.to_datetime(epfo["remittance_date"])

    return {
        "master": master, "gst": gst, "bank": bank, "epfo": epfo,
        "self_declared": self_declared, "balance_sheet": balance_sheet, "owners": owners,
        "bureau": bureau, "legal_disputes": legal_disputes, "collateral": collateral,
        "loan_facilities": loan_facilities, "loan_application": loan_application,
    }


def load_ground_truth(data_lake_dir):
    path = os.path.join(data_lake_dir, "ground_truth", "ground_truth_labels.csv")
    return pd.read_csv(path)


def load_quality_outputs(quality_dir):
    submetric_avail = pd.read_csv(os.path.join(quality_dir, "submetric_availability.csv"))
    consistency = pd.read_csv(os.path.join(quality_dir, "consistency_report.csv"))
    return {"submetric_availability": submetric_avail, "consistency": consistency}
