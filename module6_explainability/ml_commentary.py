"""
Auto-generated, template-based (not LLM-generated - same rule-based
transparency principle as commentary.py) 2-3 line explanation of what the
ML challenger/anomaly detector found for a borrower, plus which submetrics
are the strongest candidates to revisit.

"Advised to revisit" is computed once, from THIS pipeline run's champion
scores/weights - it is a diagnostic explanation of why the flag was
raised, not something that silently changes as a user overrides other
values. The candidates are found by ranking every scored submetric on how
much it drags the COMPOSITE down: dimension's effective weight x
submetric's effective subweight x (100 - submetric score) - the same
weighted-average mechanism dimension_scores.py/aggregate.py already use to
build the composite, just read in reverse to find where the score is
"spent" losing points on a weak signal.
"""

import pandas as pd
from config import ML_FEATURE_COLUMNS, ML_ANOMALY_EXPLANATION_PERCENTILE_CUTOFF, ML_ANOMALY_EXPLANATION_MAX_FEATURES
from formatting import format_submetric_value

WEAK_SCORE_THRESHOLD = 50.0
MAX_ADVISED_SUBMETRICS = 2


def _weakest_submetrics(dims):
    candidates = []
    for d in dims:
        dim_weight = d.get("weight") or 0.0
        for sm in d.get("submetrics", []):
            score = sm.get("score")
            sub_weight = sm.get("weight") or 0.0
            if score is None or score >= WEAK_SCORE_THRESHOLD or sub_weight <= 0 or dim_weight <= 0:
                continue
            drag = dim_weight * sub_weight * (100.0 - score)
            candidates.append((drag, sm["key"], d["key"], score))
    candidates.sort(key=lambda c: c[0], reverse=True)
    return candidates[:MAX_ADVISED_SUBMETRICS]


def build_ml_explanation(dims, ml_block, feature_labels):
    """Returns (explanation_text, advised_submetric_keys) or (None, [])
    when there's nothing to explain (ML not run, or the model agrees /
    nothing unusual)."""
    if not ml_block.get("available"):
        return None, []

    flagged = ml_block.get("flagged_for_review")
    anomalous = ml_block.get("is_anomaly")
    if not flagged and not anomalous:
        return "The ML challenger model's independent score agrees closely with the scorecard for this borrower, and no unusual data pattern was flagged. No specific submetrics are advised for review.", []

    weakest = _weakest_submetrics(dims)
    labels = [feature_labels.get(key, key) for _, key, _, _ in weakest]

    parts = []
    if flagged:
        divergence = ml_block.get("divergence")
        direction = "higher (less risk)" if (divergence or 0) > 0 else "lower (more risk)"
        parts.append(
            f"The ML challenger model (Gradient Boosting) scores this borrower {direction} than the "
            f"rule-based scorecard by {abs(divergence):.1f} points."
        )
        if labels:
            parts.append(
                f"This gap is most influenced by {' and '.join(labels)}, which carry significant weight "
                f"in the scorecard's calculation but are weighed differently by the challenger's learned pattern. "
                f"Recommend revisiting: {', '.join(labels)}."
            )
        else:
            parts.append("No single weak submetric explains the gap - recommend a general file review.")
    if anomalous and not flagged:
        parts.append(
            "Separately, Isolation Forest flags this borrower's overall data pattern as statistically unusual "
            "for this 400-borrower portfolio - see the anomaly explanation below for specifics."
        )

    return " ".join(parts), [key for _, key, _, _ in weakest] if flagged else []


# ---------- Anomaly (Isolation Forest) explanation ----------
# Isolation Forest has no built-in per-prediction feature attribution, so
# this approximates "why is this borrower unusual" the standard honest
# way: rank every ML input feature by how extreme this borrower's value
# is relative to the population (percentile distance from the center),
# and name the 1-3 most extreme ones. This is a real, borrower-specific
# computation - not a canned message - but it is an approximation of the
# model's reasoning, not an exact decomposition of its anomaly score.


def compute_feature_percentiles(features_df):
    """Population-wide percentile rank (0-100) for every ML feature,
    computed once and reused per-borrower - NaN stays NaN (not_applicable
    isn't itself evidence of being unusual, see build_anomaly_explanation)."""
    out = pd.DataFrame({"borrower_id": features_df["borrower_id"]})
    for col in ML_FEATURE_COLUMNS:
        out[col] = features_df[col].rank(pct=True, na_option="keep") * 100.0
    return out.set_index("borrower_id")


def build_anomaly_explanation(borrower_id, features_df_row, percentiles_row, feature_labels):
    """Returns a 2-3 line string naming the specific features driving this
    borrower's anomaly flag, or a generic fallback if nothing clears the
    percentile cutoff (rare - Isolation Forest can occasionally flag a
    borrower on a subtle multivariate combination no single feature
    captures)."""
    extremes = []
    for col in ML_FEATURE_COLUMNS:
        pct = percentiles_row.get(col)
        raw = features_df_row.get(col)
        if pct is None or pd.isna(pct) or raw is None or pd.isna(raw):
            continue
        distance_from_center = min(pct, 100.0 - pct)
        if distance_from_center > ML_ANOMALY_EXPLANATION_PERCENTILE_CUTOFF:
            continue
        tail = f"bottom {pct:.0f}%" if pct <= 50 else f"top {100.0 - pct:.0f}%"
        display = format_submetric_value(col, raw)
        extremes.append((distance_from_center, col, display, tail))

    extremes.sort(key=lambda e: e[0])
    extremes = extremes[:ML_ANOMALY_EXPLANATION_MAX_FEATURES]

    if not extremes:
        return (
            "Isolation Forest flags this borrower's overall combination of values as statistically unusual "
            "for this 400-borrower portfolio, even though no single value is individually extreme - the model "
            "is detecting an unusual multivariate pattern across several inputs together. Recommend a general "
            "file review rather than focusing on one metric."
        )

    items = [f"{feature_labels.get(col, col)} ({display}, {tail} of the portfolio)" for _, col, display, tail in extremes]
    if len(items) == 1:
        item_str = items[0]
    elif len(items) == 2:
        item_str = " and ".join(items)
    else:
        item_str = ", ".join(items[:-1]) + ", and " + items[-1]

    return (
        f"This borrower's overall data pattern is flagged as unusual mainly due to: {item_str}. "
        f"No single value here is necessarily extreme in isolation, but this specific combination is rare "
        f"in the 400-borrower portfolio - a signal the rule-based scorecard, which scores each metric "
        f"independently, cannot surface on its own."
    )
