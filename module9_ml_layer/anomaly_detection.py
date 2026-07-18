"""
Isolation Forest anomaly detection over the same submetric feature matrix
Module 5 scores (config.ML_FEATURE_COLUMNS). NaN is passed through as-is -
scikit-learn's IsolationForest (>=1.4) handles missing values natively, so
a borrower's missing-ness pattern (e.g. no balance sheet, no bureau
record) is treated as real information rather than being imputed away.

Output is an anomaly_score on a 0-100 scale (higher = more unusual) rather
than sklearn's raw signed decision_function output, so it sits on the same
scale as everything else in this pipeline and a reader doesn't need to
know sklearn's sign convention to interpret it.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from config import ML_FEATURE_COLUMNS, ISOLATION_FOREST_PARAMS


def build_anomaly_scores(features_df):
    X = features_df[ML_FEATURE_COLUMNS]

    model = IsolationForest(**ISOLATION_FOREST_PARAMS)
    model.fit(X)

    # decision_function: higher = more normal, lower/negative = more
    # anomalous. Flip and min-max scale to 0-100 so "higher = more
    # anomalous" reads naturally next to every other 0-100 score in this
    # pipeline.
    raw = model.decision_function(X)
    inverted = -raw
    lo, hi = inverted.min(), inverted.max()
    anomaly_score = (inverted - lo) / (hi - lo) * 100.0 if hi > lo else np.zeros_like(inverted)

    is_anomaly = model.predict(X) == -1  # sklearn: -1 = anomaly, 1 = normal

    return pd.DataFrame({
        "borrower_id": features_df["borrower_id"],
        "anomaly_score": np.round(anomaly_score, 2),
        "is_anomaly": is_anomaly,
    })
