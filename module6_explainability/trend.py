"""
Trend view: a REAL but deliberately scoped-down trajectory, computed from
robust point-in-time metrics only - NOT a replay of Module 5's full
composite methodology at each checkpoint. See config.py's module docstring
for why.

Checkpoints are fractions of EACH BORROWER'S OWN observed history (25%,
50%, 75%, 100%), not fixed calendar months - Module 1 v2 gave ~15% of
Tier A borrowers genuinely short history (3.5-11 months), so a fixed
"3/6/9/12 month" checkpoint would silently break for them. Fraction-based
checkpoints work for everyone, at the cost of "checkpoint 2" meaning a
different calendar span for a short-history vs full-history borrower -
labeled honestly as "25% / 50% / 75% / 100% of observed history", not
"quarters."

Three metrics, all direction-adjusted and percentile-ranked WITHIN each
checkpoint's cross-section (so "trend_indicator" at checkpoint 1 and
checkpoint 4 are comparable to each other and to peers at the same point):
  - avg_balance_inr (higher better)
  - cheque_bounce_rate (higher worse)
  - gst_ontime_filing_ratio (higher better)
Averaged, unweighted, into one trend_indicator per checkpoint.
"""

import pandas as pd
from config import TREND_CHECKPOINT_MONTHS

CHECKPOINT_FRACTIONS = [0.25, 0.5, 0.75, 1.0]


def _bank_checkpoint_metrics(bank_borrower_df, frac):
    g = bank_borrower_df.sort_values("txn_date")
    dates = g["txn_date"].unique()
    if len(dates) == 0:
        return None, None
    cutoff_idx = max(int(round(len(dates) * frac)) - 1, 0)
    cutoff_date = sorted(dates)[cutoff_idx]
    window = g[g["txn_date"] <= cutoff_date]

    avg_balance = window["running_balance_inr"].mean()
    n_debit = (window["txn_type"] == "debit").sum()
    n_bounce = window["bounce_flag"].sum()
    bounce_rate = (n_bounce / n_debit) if n_debit else float("nan")
    return avg_balance, bounce_rate


def _gst_checkpoint_metric(gst_borrower_df, frac):
    g = gst_borrower_df.sort_values("period")
    n = len(g)
    if n == 0:
        return float("nan")
    cutoff_idx = max(int(round(n * frac)), 1)
    window = g.iloc[:cutoff_idx]
    filed = window["filing_date"].notna()
    ontime = (window["filing_date"] <= window["due_date"]) & filed
    return ontime.sum() / len(window) if len(window) else float("nan")


def build_raw_checkpoints(lake):
    """Returns a long dataframe: borrower_id, checkpoint_frac, avg_balance_inr, cheque_bounce_rate, gst_ontime_filing_ratio"""
    rows = []
    bank_groups = dict(tuple(lake["bank"].groupby("borrower_id")))
    gst_groups = dict(tuple(lake["gst"].groupby("borrower_id")))

    for bid in lake["master"]["borrower_id"]:
        bank_g = bank_groups.get(bid)
        gst_g = gst_groups.get(bid)
        for frac in CHECKPOINT_FRACTIONS:
            avg_balance, bounce_rate = (None, None)
            if bank_g is not None:
                avg_balance, bounce_rate = _bank_checkpoint_metrics(bank_g, frac)
            ontime_ratio = _gst_checkpoint_metric(gst_g, frac) if gst_g is not None else float("nan")

            rows.append({
                "borrower_id": bid,
                "checkpoint_frac": frac,
                "avg_balance_inr": avg_balance,
                "cheque_bounce_rate": bounce_rate,
                "gst_ontime_filing_ratio": ontime_ratio,
            })
    return pd.DataFrame(rows)


def score_checkpoints(raw_checkpoints_df):
    """Percentile-ranks each metric WITHIN each checkpoint_frac cross-section,
    then averages into a single trend_indicator per borrower per checkpoint."""
    out_parts = []
    for frac, group in raw_checkpoints_df.groupby("checkpoint_frac"):
        g = group.copy()
        g["_s_balance"] = g["avg_balance_inr"].rank(pct=True, na_option="keep") * 100
        g["_s_bounce"] = 100 - (g["cheque_bounce_rate"].rank(pct=True, na_option="keep") * 100)
        g["_s_ontime"] = g["gst_ontime_filing_ratio"].rank(pct=True, na_option="keep") * 100
        g["trend_indicator"] = g[["_s_balance", "_s_bounce", "_s_ontime"]].mean(axis=1, skipna=True)
        out_parts.append(g.drop(columns=["_s_balance", "_s_bounce", "_s_ontime"]))
    return pd.concat(out_parts, ignore_index=True)


def build_trend(lake):
    raw = build_raw_checkpoints(lake)
    return score_checkpoints(raw)
