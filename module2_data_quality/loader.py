"""Loads Module 1's data lake output."""

import os
import pandas as pd


def load_data_lake(data_lake_dir):
    master = pd.read_csv(os.path.join(data_lake_dir, "borrower_master.csv"))
    gst = pd.read_csv(os.path.join(data_lake_dir, "gst_returns", "gst_returns.csv"))
    bank = pd.read_csv(os.path.join(data_lake_dir, "bank_upi_transactions", "bank_upi_transactions.csv.gz"))
    epfo = pd.read_csv(os.path.join(data_lake_dir, "epfo_contributions", "epfo_contributions.csv"))
    audit = pd.read_csv(os.path.join(data_lake_dir, "consent_audit_log.csv"))

    gst["due_date"] = pd.to_datetime(gst["due_date"])
    gst["filing_date"] = pd.to_datetime(gst["filing_date"])
    bank["txn_date"] = pd.to_datetime(bank["txn_date"])
    epfo["due_date"] = pd.to_datetime(epfo["due_date"])
    epfo["remittance_date"] = pd.to_datetime(epfo["remittance_date"])

    return {"master": master, "gst": gst, "bank": bank, "epfo": epfo, "audit": audit}


def load_ground_truth(data_lake_dir):
    """Hidden ground truth - only for backtesting this module's own checks,
    never used as an input to the checks themselves."""
    path = os.path.join(data_lake_dir, "ground_truth", "ground_truth_labels.csv")
    return pd.read_csv(path)
