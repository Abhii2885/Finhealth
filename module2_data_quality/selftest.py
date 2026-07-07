"""
Self-test: prove the schema validator actually catches defects, rather than
just reporting a clean bill on data it was never going to flag anyway.

Takes a copy of the loaded data lake, injects a small, known set of defects,
re-runs run_all_checks, and confirms each injected defect type produced at
least one matching issue. This is checked into the pipeline output so the
validator's detection capability is demonstrated, not asserted.
"""

import pandas as pd
import numpy as np
from schema_checks import run_all_checks
from config import DATA_SNAPSHOT_DATE

INJECTED_DEFECTS = [
    "duplicate_gst_period",
    "negative_turnover",
    "orphan_borrower_id_bank",
    "future_txn_date",
    "non_positive_amount",
]


def inject_defects(lake):
    lake = {k: v.copy() for k, v in lake.items()}
    gst = lake["gst"]
    bank = lake["bank"]

    # 1. Duplicate GST period: clone one borrower's most recent return
    row = gst.iloc[[0]].copy()
    gst = pd.concat([gst, row], ignore_index=True)

    # 2. Negative declared turnover
    idx = gst.index[5]
    gst.loc[idx, "declared_turnover_inr"] = -12345.0

    # 3. Orphan borrower_id in bank data (borrower not in master)
    fake_row = bank.iloc[[0]].copy()
    fake_row["borrower_id"] = "MSME-99999"
    bank = pd.concat([bank, fake_row], ignore_index=True)

    # 4. Future-dated bank transaction (relative to the data lake's own
    # snapshot date, not real wall-clock time - see config.DATA_SNAPSHOT_DATE)
    idx2 = bank.index[10]
    bank.loc[idx2, "txn_date"] = DATA_SNAPSHOT_DATE + pd.Timedelta(days=30)

    # 5. Non-positive transaction amount
    idx3 = bank.index[20]
    bank.loc[idx3, "amount_inr"] = -500.0

    lake["gst"] = gst
    lake["bank"] = bank
    return lake


def run_selftest(lake):
    defected_lake = inject_defects(lake)
    issues = run_all_checks(defected_lake)

    found_checks = set(issues["check"])
    expected_checks = {"duplicate_period", "negative_turnover", "orphan_borrower_id",
                        "future_txn_date", "non_positive_amount"}

    results = []
    for chk in sorted(expected_checks):
        caught = chk in found_checks
        results.append({"expected_defect": chk, "caught": caught})

    results_df = pd.DataFrame(results)
    all_caught = results_df["caught"].all()
    return results_df, all_caught, issues
