"""
Compliance Discipline features (from GST returns).

- gst_ontime_filing_ratio: share of periods filed on or before due_date
- gst_missed_filing_rate: share of periods never filed at all
- gst_avg_filing_delay_days: mean delay in days among returns that WERE
  filed (excludes never-filed periods, which are captured separately)

NOT computable in this prototype: utility_payment_timeliness - Module 1
has no utility payment generator, despite the architecture doc calling
this out as a good NTC-friendly signal. Worth building in Module 1 if
this dimension needs to carry more weight later.
"""

import pandas as pd


def build_compliance_features(gst_df):
    rows = []
    for bid, g in gst_df.groupby("borrower_id"):
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
            "utility_payment_timeliness": None,  # not computable in this prototype
        })
    return pd.DataFrame(rows)
