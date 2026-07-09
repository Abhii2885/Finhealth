"""Loads everything Module 6 needs from Modules 1, 3, 4, and 5."""

import os
import pandas as pd


def load_scores(scoring_dir):
    return pd.read_csv(os.path.join(scoring_dir, "borrower_scores.csv"))


def load_feature_scores(scoring_dir):
    return pd.read_csv(os.path.join(scoring_dir, "feature_scores.csv"))


def load_segmentation(segmentation_dir):
    return pd.read_csv(os.path.join(segmentation_dir, "segmentation_policy.csv"))


def load_raw_lake(data_lake_dir):
    gst = pd.read_csv(os.path.join(data_lake_dir, "gst_returns", "gst_returns.csv"))
    bank = pd.read_csv(os.path.join(data_lake_dir, "bank_upi_transactions", "bank_upi_transactions.csv.gz"))
    master = pd.read_csv(os.path.join(data_lake_dir, "borrower_master.csv"))

    gst["due_date"] = pd.to_datetime(gst["due_date"])
    gst["filing_date"] = pd.to_datetime(gst["filing_date"])
    bank["txn_date"] = pd.to_datetime(bank["txn_date"])
    return {"gst": gst, "bank": bank, "master": master}


def load_ground_truth(data_lake_dir):
    return pd.read_csv(os.path.join(data_lake_dir, "ground_truth", "ground_truth_labels.csv"))
