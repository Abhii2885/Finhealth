"""Loads everything Module 6 needs from Modules 1, 3, 4, and 5."""

import os
import pandas as pd


def load_scores(scoring_dir):
    return pd.read_csv(os.path.join(scoring_dir, "borrower_scores.csv"))


def load_feature_scores(scoring_dir):
    return pd.read_csv(os.path.join(scoring_dir, "feature_scores.csv"))


def load_segmentation(segmentation_dir):
    return pd.read_csv(os.path.join(segmentation_dir, "segmentation_policy.csv"))


def load_features(features_dir):
    """Module 3's raw (pre-score) values - what the scorecard's 'actual
    value' column shows, alongside Module 5's score for the same submetric."""
    return pd.read_csv(os.path.join(features_dir, "borrower_features.csv"))


def load_raw_lake(data_lake_dir):
    gst = pd.read_csv(os.path.join(data_lake_dir, "gst_returns", "gst_returns.csv"))
    self_declared = pd.read_csv(os.path.join(data_lake_dir, "self_declared_turnover", "self_declared_turnover.csv"))
    epfo = pd.read_csv(os.path.join(data_lake_dir, "epfo_contributions", "epfo_contributions.csv"))
    bank = pd.read_csv(os.path.join(data_lake_dir, "bank_upi_transactions", "bank_upi_transactions.csv.gz"))
    master = pd.read_csv(os.path.join(data_lake_dir, "borrower_master.csv"))
    balance_sheet = pd.read_csv(os.path.join(data_lake_dir, "balance_sheet", "balance_sheet.csv"))
    bureau = pd.read_csv(os.path.join(data_lake_dir, "bureau_data", "bureau_data.csv"))
    collateral = pd.read_csv(os.path.join(data_lake_dir, "collateral", "collateral.csv"))
    loan_facilities = pd.read_csv(os.path.join(data_lake_dir, "loan_facilities", "loan_facilities.csv"))
    loan_application = pd.read_csv(os.path.join(data_lake_dir, "loan_application", "loan_application.csv"))
    legal_disputes = pd.read_csv(os.path.join(data_lake_dir, "legal_disputes", "legal_disputes.csv"))

    gst["due_date"] = pd.to_datetime(gst["due_date"])
    gst["filing_date"] = pd.to_datetime(gst["filing_date"])
    bank["txn_date"] = pd.to_datetime(bank["txn_date"])
    if len(legal_disputes):
        legal_disputes["filed_date"] = pd.to_datetime(legal_disputes["filed_date"])

    return {
        "gst": gst, "self_declared": self_declared, "epfo": epfo, "bank": bank, "master": master,
        "balance_sheet": balance_sheet, "bureau": bureau, "collateral": collateral,
        "loan_facilities": loan_facilities, "loan_application": loan_application,
        "legal_disputes": legal_disputes,
    }


def load_ground_truth(data_lake_dir):
    return pd.read_csv(os.path.join(data_lake_dir, "ground_truth", "ground_truth_labels.csv"))


def load_ml_outputs(ml_dir):
    """Module 9's champion-challenger outputs, if that module has been run.

    Returns (df, holdout_eval_dict) - either element is None when its file
    doesn't exist. The dashboard must still build with NO Module 9 output
    at all (the ML layer is an optional add-on, not a pipeline dependency) -
    callers handle the None case, they don't get an exception here."""
    import json
    cc_path = os.path.join(ml_dir, "champion_challenger.csv")
    ml_df = pd.read_csv(cc_path) if os.path.exists(cc_path) else None

    eval_path = os.path.join(ml_dir, "challenger_holdout_eval_robustness.json")
    holdout_eval = None
    if os.path.exists(eval_path):
        with open(eval_path) as f:
            holdout_eval = json.load(f)
    return ml_df, holdout_eval
