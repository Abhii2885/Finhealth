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
    if anomalous:
        parts.append(
            "Separately, Isolation Forest flags this borrower's overall data pattern as statistically unusual "
            "for this 400-borrower portfolio - verify the underlying source documents for accuracy."
        )

    return " ".join(parts), [key for _, key, _, _ in weakest] if flagged else []
