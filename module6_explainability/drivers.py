"""
Top-drivers explainability: for each borrower and dimension, which
underlying feature (from Module 5's exposed per-feature percentile scores)
is pulling the dimension score up the most, and which is pulling it down
the most.

Dimensions with only one scoring feature (repayment_credit_behavior, which
only has cheque_bounce_rate in this prototype - see Module 3's documented
gap on bureau/limit-utilization data) have nothing to differentiate a
"top" driver from - flagged as such rather than fabricating a comparison.
"""

import pandas as pd
from config import DIMENSIONS, FEATURE_LABELS


def _dimension_feature_cols(feature_scores_df, dimension):
    prefix = f"featscore__{dimension}__"
    return [c for c in feature_scores_df.columns if c.startswith(prefix)]


def build_drivers(feature_scores_df):
    rows = []
    for _, r in feature_scores_df.iterrows():
        row = {"borrower_id": r["borrower_id"]}
        for dimension in DIMENSIONS:
            cols = _dimension_feature_cols(feature_scores_df, dimension)
            values = {c.split("__")[-1]: r[c] for c in cols if pd.notna(r[c])}

            if len(values) == 0:
                row[f"{dimension}_top_positive"] = None
                row[f"{dimension}_top_negative"] = None
                row[f"{dimension}_driver_note"] = "no data available for this dimension"
            elif len(values) == 1:
                only_feature = list(values.keys())[0]
                label = FEATURE_LABELS.get(only_feature, only_feature)
                row[f"{dimension}_top_positive"] = label if values[only_feature] >= 50 else None
                row[f"{dimension}_top_negative"] = label if values[only_feature] < 50 else None
                row[f"{dimension}_driver_note"] = "only one scoring feature available in this prototype - no comparison possible"
            else:
                best_feature = max(values, key=values.get)
                worst_feature = min(values, key=values.get)
                row[f"{dimension}_top_positive"] = FEATURE_LABELS.get(best_feature, best_feature)
                row[f"{dimension}_top_negative"] = FEATURE_LABELS.get(worst_feature, worst_feature)
                row[f"{dimension}_driver_note"] = ""
        rows.append(row)
    return pd.DataFrame(rows)
