"""Loads everything Module 8 needs from Modules 1, 4, 5, and 7."""

import os
import json
import pandas as pd


def load_scores(scoring_dir):
    return pd.read_csv(os.path.join(scoring_dir, "borrower_scores.csv"))


def load_segmentation(segmentation_dir):
    return pd.read_csv(os.path.join(segmentation_dir, "segmentation_policy.csv"))


def load_master(data_lake_dir):
    return pd.read_csv(os.path.join(data_lake_dir, "borrower_master.csv"))


def load_ground_truth(data_lake_dir):
    return pd.read_csv(os.path.join(data_lake_dir, "ground_truth", "ground_truth_labels.csv"))


def load_consent_refresh_log(integration_dir):
    path = os.path.join(integration_dir, "demo_run_log.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        log = json.load(f)
    events = []
    for call in log.get("calls", []):
        if call.get("call") == "POST /uli/v1/consent-refresh" and call.get("status") == 202:
            events.append(call["request"])
    return events
