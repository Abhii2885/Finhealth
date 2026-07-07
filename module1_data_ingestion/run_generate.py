"""
Entry point for Module 1: Data Ingestion Layer (synthetic).

Run:
    python run_generate.py

Produces data_lake/ with:
    borrower_master.csv
    consent_audit_log.csv
    gst_returns/gst_returns.csv
    bank_upi_transactions/bank_upi_transactions.csv
    epfo_contributions/epfo_contributions.csv
    ground_truth/ground_truth_labels.csv   <- NOT a feature, see README
"""

import os
import time
import pandas as pd

from config import OUTPUT_DIR
from borrowers import generate_borrowers
from gst_source import generate_gst
from bank_upi_source import generate_bank_upi
from epfo_source import generate_epfo
from ingest import run_ingestion
from truncate_history import truncate_gst, truncate_epfo, truncate_bank


def main():
    t0 = time.time()
    print("Generating borrower population...")
    master, ground_truth, internal = generate_borrowers()
    print(f"  {len(master)} borrowers "
          f"({(master['tier'] == 'A').sum()} Tier A, {(master['tier'] == 'C').sum()} Tier C)")

    print("Generating GST returns...")
    gst_df = generate_gst(internal)
    print(f"  {len(gst_df)} rows")

    print("Generating bank/UPI transactions...")
    bank_df = generate_bank_upi(internal)
    print(f"  {len(bank_df)} rows")

    print("Generating EPFO contributions (Tier C only)...")
    epfo_df = generate_epfo(internal)
    print(f"  {len(epfo_df)} rows")

    n_short = int(internal["history_available_frac"].lt(1.0).sum())
    print(f"Truncating history for {n_short} borrowers with genuinely short track records...")
    gst_df = truncate_gst(gst_df, internal)
    bank_df = truncate_bank(bank_df, internal)
    epfo_df = truncate_epfo(epfo_df, internal)
    print(f"  post-truncation: {len(gst_df)} GST rows, {len(bank_df)} bank rows, {len(epfo_df)} EPFO rows")

    print("Running ingestion (tagging, consent audit log, writing data lake)...")
    paths = run_ingestion(OUTPUT_DIR, master, gst_df, bank_df, epfo_df)

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
