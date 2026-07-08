"""Loads Module 1's data lake + Module 2's quality outputs."""

import os
import pandas as pd


def load_data_lake(data_lake_dir):
    master = pd.read_csv(os.path.join(data_lake_dir, "borrower_master.csv"))
    gst = pd.read_csv(os.path.join(data_lake_dir, "gst_returns", "gst_returns.csv"))
    bank = pd.read_csv(os.path.join(data_lake_dir, "bank_upi_transactions", "bank_upi_transactions.csv.gz"))
    epfo = pd.read_csv(os.path.join(data_lake_dir, "epfo_contributions", "epfo_contributions.csv"))

    gst["due_date"] = pd.to_datetime(gst["due_date"])
    gst["filing_date"] = pd.to_datetime(gst["filing_date"])
    bank["txn_date"] = pd.to_datetime(bank["txn_date"])
    epfo["remittance_date"] = pd.to_datetime(epfo["remittance_date"])

    return {"master": master, "gst": gst, "bank": bank, "epfo": epfo}


def load_ground_truth(data_lake_dir):
    path = os.path.join(data_lake_dir, "ground_truth", "ground_truth_labels.csv")
    return pd.read_csv(path)


def load_quality_outputs(quality_dir):
    dim_avail = pd.read_csv(os.path.join(quality_dir, "dimension_availability.csv"))
    consistency = pd.read_csv(os.path.join(quality_dir, "consistency_report.csv"))
    return {"dimension_availability": dim_avail, "consistency": consistency}
