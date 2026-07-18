"""
Compliance Discipline features (15% composite weight).

v3 update: every ratio here is now computed over the TRAILING 6 MONTHS
only, not the full observed history - per explicit user instruction
("last 6 months period track record"). This is a genuine methodology
change from the original whole-window ratios: a borrower who filed late
for 2 years but has been clean for the last 6 months now scores well on
Compliance, which is the intended behavior (compliance is about recent
discipline, not permanent record) but is worth knowing if you compare
against pre-this-change numbers.

- gst_ontime_filing_ratio / gst_missed_filing_rate / gst_avg_filing_delay_days:
  last 6 GST periods only (fewer for short-history/non-GST-registered
  borrowers - non-GST borrowers get NaN via the orchestrator's left-join,
  not_applicable, gated by is_gst_registered in Module 2).
- epfo_ontime_remittance_ratio: last 6 EPFO periods only, same pattern.
- utility_payment_timeliness / rent_payment_timeliness /
  salary_payment_timeliness: last 6 CALENDAR MONTHS of bank data.
  Denominator is MONTHS OBSERVED in that 6-month window, not rows of that
  category present - a missed payment (no row that month) counts against
  timeliness, it doesn't just vanish from the average.
- covenant_compliance_flag: 1.0/0.0 from loan_facilities' covenant_status -
  UNCHANGED, still a point-in-time status, not a 6-month ratio. Module 1's
  loan_facilities models covenants as a single current test result, not a
  testing history, so there's no real 6-month time series to window here -
  flagged as a scope boundary, not silently faked with an invented series.
  NaN when a borrower has no existing loan or no covenant on it
  (not_applicable, not a 0 - a borrower with no covenant hasn't breached
  one).
"""

import pandas as pd
import numpy as np

SCHEDULED_CATEGORIES = {"utility_payment": "utility_payment_timeliness",
                         "rent_payment": "rent_payment_timeliness",
                         "salary_payment": "salary_payment_timeliness"}

TRAILING_MONTHS = 6


def build_gst_compliance(gst_df):
    rows = []
    for bid, g in gst_df.groupby("borrower_id"):
        g = g.sort_values("period").tail(TRAILING_MONTHS)
        n = len(g)
        filed = g["filing_date"].notna()
        n_filed = filed.sum()

        ontime = (g["filing_date"] <= g["due_date"]) & filed
        ontime_ratio = ontime.sum() / n if n else float("nan")
        missed_rate = (n - n_filed) / n if n else float("nan")

        delay_days = (g.loc[filed, "filing_date"] - g.loc[filed, "due_date"]).dt.days
        avg_delay = delay_days.mean() if n_filed else float("nan")

        rows.append({
            "borrower_id": bid,
            "gst_ontime_filing_ratio": round(ontime_ratio, 3) if pd.notna(ontime_ratio) else float("nan"),
            "gst_missed_filing_rate": round(missed_rate, 3) if pd.notna(missed_rate) else float("nan"),
            "gst_avg_filing_delay_days": round(avg_delay, 2) if pd.notna(avg_delay) else float("nan"),
            "gst_compliance_window_periods": n,
        })
    return pd.DataFrame(rows)


def build_epfo_compliance(epfo_df):
    rows = []
    for bid, g in epfo_df.groupby("borrower_id"):
        g = g.sort_values("period").tail(TRAILING_MONTHS)
        n = len(g)
        remitted = g["remittance_date"].notna()
        n_remitted = remitted.sum()
        ontime = (g["remittance_date"] <= g["due_date"]) & remitted
        ontime_ratio = ontime.sum() / n if n else float("nan")
        rows.append({
            "borrower_id": bid,
            "epfo_ontime_remittance_ratio": round(ontime_ratio, 3) if pd.notna(ontime_ratio) else float("nan"),
            "epfo_compliance_window_periods": n,
        })
    return pd.DataFrame(rows)


def _last_n_months(g, n):
    months = sorted(g["txn_date"].dt.to_period("M").unique())[-n:]
    return g[g["txn_date"].dt.to_period("M").isin(months)], len(months)


def build_scheduled_obligation_timeliness(bank_df):
    rows = []
    for bid, g in bank_df.groupby("borrower_id"):
        g_window, n_months = _last_n_months(g, TRAILING_MONTHS)
        row = {"borrower_id": bid, "compliance_window_months": n_months}
        for category, col_name in SCHEDULED_CATEGORIES.items():
            cat_rows = g_window[g_window["category"] == category]
            if n_months == 0:
                row[col_name] = np.nan
                continue
            ontime = (cat_rows["txn_date"] <= cat_rows["due_date"]).sum()
            row[col_name] = round(ontime / n_months, 3)
        rows.append(row)
    return pd.DataFrame(rows)


def build_covenant_compliance(loan_facilities_df):
    rows = []
    for _, l in loan_facilities_df.iterrows():
        flag = np.nan
        if l["has_covenant"]:
            flag = 1.0 if l["covenant_status"] == "compliant" else 0.0
        rows.append({"borrower_id": l["borrower_id"], "covenant_compliance_flag": flag})
    return pd.DataFrame(rows)


def build_compliance_features(gst_df, epfo_df, bank_df, loan_facilities_df):
    gst_c = build_gst_compliance(gst_df)
    epfo_c = build_epfo_compliance(epfo_df)
    scheduled_c = build_scheduled_obligation_timeliness(bank_df)
    covenant_c = build_covenant_compliance(loan_facilities_df)

    out = scheduled_c  # every borrower has bank data, so this anchors the full population
    for df in [gst_c, epfo_c, covenant_c]:
        out = out.merge(df, on="borrower_id", how="left")
    return out
