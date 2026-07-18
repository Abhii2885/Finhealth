"""
Gradient Boosting challenger (HistGradientBoostingRegressor - sklearn's
histogram-based GBM, same algorithm family as LightGBM/XGBoost). Chosen
over the plain GradientBoostingRegressor specifically because it handles
NaN natively - this population's missing-ness (no balance sheet, no
bureau record, no existing loan, no collateral) is structural and
archetype-correlated, not random, so imputing it away would destroy real
signal rather than clean up noise.

Two-step fit, both steps disclosed rather than silently collapsed into
one:
1. A SPLIT model (config.TRAIN_TEST_SPLIT_FRAC) is fit on the training
   rows only, so held-out MAE/R2 on the test rows are an honest read of
   how well this model generalizes - not fit-and-report-on-the-same-rows
   numbers. Permutation importance (the explainability output) is also
   computed on this held-out split, for the same reason: importance
   computed on training data can overstate a feature that the model
   simply memorized noise on.
2. A FINAL model is then refit on the FULL 400-borrower population (now
   that step 1 has established the architecture is reasonable) to produce
   the actual challenger_score used downstream - standard practice once a
   holdout evaluation is complete, disclosed here rather than left
   implicit.

See config.TARGET_BY_ARCHETYPE for the single most important caveat: the
regression target is a proxy anchored to the synthetic true_archetype
label, not a real observed repayment outcome (none exist in this
dataset).
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.inspection import permutation_importance
from config import ML_FEATURE_COLUMNS, TARGET_BY_ARCHETYPE, GRADIENT_BOOSTING_PARAMS, \
    TRAIN_TEST_SPLIT_FRAC, SPLIT_RANDOM_STATE


def _build_target(ground_truth_df):
    target = ground_truth_df["true_archetype"].map(TARGET_BY_ARCHETYPE)
    if target.isna().any():
        unknown = ground_truth_df.loc[target.isna(), "true_archetype"].unique().tolist()
        raise ValueError(f"true_archetype values not covered by TARGET_BY_ARCHETYPE: {unknown}")
    return target


def evaluate_holdout(features_df, ground_truth_df, feature_columns=None):
    """Step 1: split-fit model, held-out metrics + permutation importance.

    feature_columns defaults to the full config.ML_FEATURE_COLUMNS set.
    run_module9.py also calls this a second time with
    config.ROBUSTNESS_CHECK_FEATURE_COLUMNS (full set minus
    projected_revenue_growth_rate) - see that config entry's comment for
    why: the full-feature run below hits a near-perfect (R2=1.0, MAE=0.0)
    fit, which is NOT the challenger being unrealistically good - it's
    this synthetic dataset's projected_revenue_growth_rate having
    essentially zero within-archetype overlap (a Module 1 generation
    artifact, verified by direct inspection, not assumed), so a
    sufficiently flexible model can perfectly recover the archetype label
    from that one feature alone. Reported plainly rather than swept under
    a cherry-picked feature list for the primary result - the second,
    excluded-feature run exists specifically to show what the model does
    once forced to rely on the other 21 (more realistic, overlapping)
    features."""
    feature_columns = feature_columns or ML_FEATURE_COLUMNS
    merged = features_df.merge(ground_truth_df[["borrower_id", "true_archetype"]], on="borrower_id")
    X = merged[feature_columns]
    y = _build_target(merged)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, train_size=TRAIN_TEST_SPLIT_FRAC, random_state=SPLIT_RANDOM_STATE
    )

    model = HistGradientBoostingRegressor(**GRADIENT_BOOSTING_PARAMS)
    model.fit(X_train, y_train)

    train_pred = model.predict(X_train)
    test_pred = model.predict(X_test)

    perm = permutation_importance(
        model, X_test, y_test, n_repeats=20, random_state=SPLIT_RANDOM_STATE, scoring="neg_mean_absolute_error"
    )
    importances = sorted(
        zip(feature_columns, perm.importances_mean),
        key=lambda kv: kv[1], reverse=True
    )

    return {
        "n_train": len(X_train),
        "n_test": len(X_test),
        "train_mae": round(float(mean_absolute_error(y_train, train_pred)), 2),
        "test_mae": round(float(mean_absolute_error(y_test, test_pred)), 2),
        "train_r2": round(float(r2_score(y_train, train_pred)), 3),
        "test_r2": round(float(r2_score(y_test, test_pred)), 3),
        "feature_importance": [{"feature": f, "importance": round(float(imp), 4)} for f, imp in importances],
    }


def build_challenger_scores(features_df, ground_truth_df):
    """Step 2: refit on the full population, return a 0-100 challenger_score
    per borrower. Target is on the same 0-100 scale as the champion
    composite_score already (see TARGET_BY_ARCHETYPE), so predictions are
    clipped to [0, 100] rather than rescaled - a prediction outside that
    range would mean the model is extrapolating past its training anchors,
    worth clipping and flagging, not silently rescaling away."""
    merged = features_df.merge(ground_truth_df[["borrower_id", "true_archetype"]], on="borrower_id")
    X = merged[ML_FEATURE_COLUMNS]
    y = _build_target(merged)

    final_model = HistGradientBoostingRegressor(**GRADIENT_BOOSTING_PARAMS)
    final_model.fit(X, y)

    raw_pred = final_model.predict(X)
    clipped = np.clip(raw_pred, 0.0, 100.0)

    return pd.DataFrame({
        "borrower_id": merged["borrower_id"],
        "challenger_score": np.round(clipped, 2),
    })
