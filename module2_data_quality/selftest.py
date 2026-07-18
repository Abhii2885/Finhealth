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
    "non_positive_current_liabilities",
    "outstanding_exceeds_original",
]


def inject_defects(lake):
    lake = {k: v.copy() for k, v in lake.items()}
    gst = lake["gst"]
    bank = lake["bank"]
    balance_sheet = lake["balance_sheet"]
    loan_facilities = lake["loan_facilities"]

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

    # 6. Non-positive current liabilities on a balance sheet row (v3)
    if len(balance_sheet):
        idx4 = balance_sheet.index[0]
        balance_sheet.loc[idx4, "current_liabilities_inr"] = 0.0

    # 7. Outstanding principal exceeding original principal (v3)
    if len(loan_facilities):
        idx5 = loan_facilities.index[0]
        loan_facilities.loc[idx5, "principal_outstanding_inr"] = (
            loan_facilities.loc[idx5, "original_principal_inr"] * 1.5
        )

    lake["gst"] = gst
    lake["bank"] = bank
    lake["balance_sheet"] = balance_sheet
    lake["loan_facilities"] = loan_facilities
    return lake


def run_selftest(lake):
    defected_lake = inject_defects(lake)
    issues = run_all_checks(defected_lake)

    found_checks = set(issues["check"])
    expected_checks = {"duplicate_period", "negative_turnover", "orphan_borrower_id",
                        "future_txn_date", "non_positive_amount",
                        "non_positive_current_liabilities", "outstanding_exceeds_original"}

    results = []
    for chk in sorted(expected_checks):
        caught = chk in found_checks
        results.append({"expected_defect": chk, "caught": caught})

    results_df = pd.DataFrame(results)
    all_caught = results_df["caught"].all()
    return results_df, all_caught, issues
