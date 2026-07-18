"""Loads Module 3's features, Module 5's champion scores, and Module 1's
hidden ground truth (used here as a repayment-outcome proxy - see
config.TARGET_BY_ARCHETYPE - not as a scoring input for either ML model)."""

import os
import pandas as pd
from config import ML_FEATURE_COLUMNS


def load_features(features_dir):
    df = pd.read_csv(os.path.join(features_dir, "borrower_features.csv"))
    missing = [c for c in ML_FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Module 3 features missing expected ML columns: {missing}")
    return df


def load_champion_scores(scoring_dir):
    return pd.read_csv(os.path.join(scoring_dir, "borrower_scores.csv"))


def load_ground_truth(data_lake_dir):
    return pd.read_csv(os.path.join(data_lake_dir, "ground_truth", "ground_truth_labels.csv"))
