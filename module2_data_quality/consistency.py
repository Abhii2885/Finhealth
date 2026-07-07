"""
Cross-source consistency check: declared GST turnover vs bank sales inflow.

Per architecture doc: "GST-declared turnover vs bank-statement inflow -
large mismatch is itself a risk signal, not just a data problem."

Method: for each borrower, compare the last 12 months of declared GST
turnover to the trailing-year bank 'sales_inflow' category total. Flag
borrowers whose ratio falls in the top or bottom decile of the population
(data-driven band - there's no external calibration reference available
in a synthetic prototype).

Honesty check built in: this module also backtests the flag against the
hidden gst_underreport_pct ground truth (Module 1) and reports precision/
recall plainly. Do not oversell what this catches - see README.
"""

import pandas as pd
from config import CONSISTENCY_LOW_PCT, CONSISTENCY_HIGH_PCT


def compute_consistency(lake):
    gst = lake["gst"]
    bank = lake["bank"]

    last12 = gst.sort_values("period").groupby("borrower_id").tail(12)
    declared_annual = last12.groupby("borrower_id")["declared_turnover_inr"].sum().rename("declared_annual_turnover_inr")

    sales_only = bank[(bank["txn_type"] == "credit") & (bank["category"] == "sales_inflow")]
    bank_annual = sales_only.groupby("borrower_id")["amount_inr"].sum().rename("bank_annual_sales_inflow_inr")

    out = pd.concat([declared_annual, bank_annual], axis=1).reset_index()
    out["bank_annual_sales_inflow_inr"] = out["bank_annual_sales_inflow_inr"].fillna(0.0)
    # avoid divide-by-zero for borrowers with ~0 declared turnover
    out["turnover_bank_ratio"] = out["bank_annual_sales_inflow_inr"] / out["declared_annual_turnover_inr"].replace(0, pd.NA)

    low_th = out["turnover_bank_ratio"].quantile(CONSISTENCY_LOW_PCT)
    high_th = out["turnover_bank_ratio"].quantile(CONSISTENCY_HIGH_PCT)

    def flag(r):
        if pd.isna(r):
            return "unscoreable"
        if r > high_th:
            return "bank_inflow_much_higher_than_declared"
        if r < low_th:
            return "bank_inflow_much_lower_than_declared"
        return "consistent"

    out["consistency_flag"] = out["turnover_bank_ratio"].apply(flag)
    out.attrs["low_threshold"] = low_th
    out.attrs["high_threshold"] = high_th
    return out


def backtest_against_ground_truth(consistency_df, ground_truth_df):
    """
    Honest validation: how well does 'bank_inflow_much_higher_than_declared'
    recover the borrowers Module 1 generated as GST under-reporters?
    Reported as-is, including when it's mediocre - see README.
    """
    m = consistency_df.merge(ground_truth_df[["borrower_id", "is_gst_underreporter"]], on="borrower_id", how="left")
    flagged = m["consistency_flag"] == "bank_inflow_much_higher_than_declared"
    actual = m["is_gst_underreporter"].fillna(False)

    tp = int((flagged & actual).sum())
    fp = int((flagged & ~actual).sum())
    fn = int((~flagged & actual).sum())
    tn = int((~flagged & ~actual).sum())

    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")

    return {
        "true_positives": tp, "false_positives": fp,
        "false_negatives": fn, "true_negatives": tn,
        "precision": round(precision, 3), "recall": round(recall, 3),
        "n_flagged": int(flagged.sum()), "n_actual_underreporters": int(actual.sum()),
    }
