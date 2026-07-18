"""
Entry point for Module 1: Data Ingestion Layer (synthetic).

Run:
    python run_generate.py

Produces data_lake/ with borrower_master.csv, consent_audit_log.csv, and
one dir per source (gst_returns, self_declared_turnover,
bank_upi_transactions, epfo_contributions, balance_sheet, owners,
bureau_data, legal_disputes, collateral, loan_facilities,
loan_application), plus ground_truth/ground_truth_labels.csv (NOT a
feature, see README).

Generation order matters: loan_facilities must exist before bank_upi
(loan_emi rows are generated FROM loan_facilities' monthly_emi_inr/loan_id,
not independently), and owners must exist before bureau_data (owner/
guarantor bureau rows join on owner_id).
"""

import os
import time
import pandas as pd

from config import OUTPUT_DIR
from borrowers import generate_borrowers
from gst_source import generate_gst
from self_declared_turnover_source import generate_self_declared_turnover
from bank_upi_source import generate_bank_upi
from epfo_source import generate_epfo
from balance_sheet_source import generate_balance_sheet
from owners_source import generate_owners
from bureau_source import generate_bureau_data
from legal_disputes_source import generate_legal_disputes
from collateral_source import generate_collateral
from loan_facilities_source import generate_loan_facilities
from application_source import generate_loan_applications
from ingest import run_ingestion
from truncate_history import truncate_gst, truncate_epfo, truncate_bank, truncate_self_declared_turnover


def main():
    t0 = time.time()
    print("Generating borrower population...")
    master, ground_truth, internal = generate_borrowers()
    print(f"  {len(master)} borrowers "
          f"({(master['tier'] == 'A').sum()} Tier A, {(master['tier'] == 'C').sum()} Tier C)")
    print(f"  is_gst_registered={internal['is_gst_registered'].sum()}, "
          f"balance_sheet_available={internal['balance_sheet_available'].sum()}, "
          f"has_bureau_record={internal['has_bureau_record'].sum()}, "
          f"has_existing_loan={internal['has_existing_loan'].sum()}, "
          f"has_collateral={internal['has_collateral'].sum()}")

    print("Generating loan facilities (needed before bank/UPI for loan_emi linkage)...")
    loan_facilities_df = generate_loan_facilities(internal)
    print(f"  {len(loan_facilities_df)} rows")

    print("Generating GST returns...")
    gst_df = generate_gst(internal)
    print(f"  {len(gst_df)} rows")

    print("Generating self-declared turnover (non-GST-registered borrowers)...")
    self_declared_df = generate_self_declared_turnover(internal)
    print(f"  {len(self_declared_df)} rows")

    print("Generating bank/UPI transactions...")
    bank_df = generate_bank_upi(internal, loan_facilities_df)
    print(f"  {len(bank_df)} rows")

    print("Generating EPFO contributions (Tier C only)...")
    epfo_df = generate_epfo(internal)
    print(f"  {len(epfo_df)} rows")

    print("Generating balance sheets...")
    balance_sheet_df = generate_balance_sheet(internal)
    print(f"  {len(balance_sheet_df)} rows")

    print("Generating owners/guarantors/related parties...")
    owners_df = generate_owners(internal)
    print(f"  {len(owners_df)} rows")

    print("Generating bureau data...")
    bureau_df = generate_bureau_data(internal, owners_df)
    print(f"  {len(bureau_df)} rows")

    print("Generating legal disputes...")
    legal_disputes_df = generate_legal_disputes(internal)
    print(f"  {len(legal_disputes_df)} rows")

    print("Generating collateral...")
    collateral_df = generate_collateral(internal)
    print(f"  {len(collateral_df)} rows")

    n_short = int(internal["history_available_frac"].lt(1.0).sum())
    print(f"Truncating turnover history for {n_short} borrowers with genuinely short track records...")
    gst_df = truncate_gst(gst_df, internal)
    self_declared_df = truncate_self_declared_turnover(self_declared_df, internal)
    bank_df = truncate_bank(bank_df, internal)
    epfo_df = truncate_epfo(epfo_df, internal)
    print(f"  post-truncation: {len(gst_df)} GST rows, {len(self_declared_df)} self-declared rows, "
          f"{len(bank_df)} bank rows, {len(epfo_df)} EPFO rows")

    print("Generating loan applications (projected revenue, anchored to real realized turnover)...")
    loan_application_df = generate_loan_applications(internal, gst_df, self_declared_df)
    print(f"  {len(loan_application_df)} rows")

    print("Running ingestion (tagging, consent audit log, writing data lake)...")
    source_dfs = {
        "gst_returns": gst_df,
        "self_declared_turnover": self_declared_df,
        "bank_upi_transactions": bank_df,
        "epfo_contributions": epfo_df,
        "balance_sheet": balance_sheet_df,
        "owners": owners_df,
        "bureau_data": bureau_df,
        "legal_disputes": legal_disputes_df,
        "collateral": collateral_df,
        "loan_facilities": loan_facilities_df,
        "loan_application": loan_application_df,
    }
    paths = run_ingestion(OUTPUT_DIR, master, source_dfs)

    # Ground truth written separately, clearly labeled as held-out.
    gt_dir = os.path.join(OUTPUT_DIR, "ground_truth")
    os.makedirs(gt_dir, exist_ok=True)
    gt_path = os.path.join(gt_dir, "ground_truth_labels.csv")
    ground_truth.to_csv(gt_path, index=False)
    paths["ground_truth"] = gt_path

    print("\nWritten files:")
    for name, path in paths.items():
        print(f"  {name}: {path}")

    print(f"\nDone in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
