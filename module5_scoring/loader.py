"""Loads Module 3's features + Module 4's segmentation policy."""

import os
import pandas as pd


def load_features(features_dir):
    return pd.read_csv(os.path.join(features_dir, "borrower_features.csv"))


def load_segmentation(segmentation_dir):
    return pd.read_csv(os.path.join(segmentation_dir, "segmentation_policy.csv"))


def load_ground_truth(data_lake_dir):
    return pd.read_csv(os.path.join(data_lake_dir, "ground_truth", "ground_truth_labels.csv"))
