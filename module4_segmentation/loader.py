"""Loads Module 2's dimension availability + Module 3's feature table."""

import os
import pandas as pd


def load_dimension_availability(quality_dir):
    return pd.read_csv(os.path.join(quality_dir, "dimension_availability.csv"))


def load_features(features_dir):
    return pd.read_csv(os.path.join(features_dir, "borrower_features.csv"))
