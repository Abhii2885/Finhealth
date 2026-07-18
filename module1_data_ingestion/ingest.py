"""
Ingestion orchestrator - Module 1 output layer.

Takes each source generator's raw output and:
  1. Tags every record with source name, ingestion timestamp, and the
     borrower's consent_id (traceability requirement, not optional -
     RBI DEPA-style consent architecture expects this).
  2. Writes each source to its own file under data_lake/<source>/ -
     separate connectors, separate refresh cadence, separate failure
     domains, per the architecture doc.
  3. Builds a consent/audit log: one row per (borrower, source) pull,
     independent of whether that source actually returned data for a
     given borrower (a Tier A borrower's absent EPFO record still needs
     an audit trail entry saying "not applicable / not consented", not
     just silence).

v3: run_ingestion takes a {source_name: df} dict instead of positional
args - with 11 sources now (up from 3), positional args stopped being
readable.
"""

import os
import uuid
import pandas as pd
from datetime import datetime, timezone

INGESTED_AT = datetime.now(timezone.utc).isoformat()

# Sources large enough to gzip.
COMPRESS_SOURCES = {"bank_upi_transactions"}

# source_name -> applies_fn(master_row) -> bool. Drives both which
# borrowers get a "granted" vs "not_applicable" consent-audit-log row.
SOURCES_PRESENT = {
    "gst_returns": lambda b: bool(b["is_gst_registered"]),
    "self_declared_turnover": lambda b: not bool(b["is_gst_registered"]),
    "bank_upi_transactions": lambda b: True,
    "epfo_contributions": lambda b: bool(b["has_epfo"]),
    "balance_sheet": lambda b: bool(b["balance_sheet_available"]),
    "owners": lambda b: True,
    "bureau_data": lambda b: bool(b["has_bureau_record"]),
    "legal_disputes": lambda b: True,
    "collateral": lambda b: bool(b["has_collateral"]),
    "loan_facilities": lambda b: bool(b["has_existing_loan"]),
    "loan_application": lambda b: True,
}


def _tag_source(df, source_name, consent_lookup):
    if df.empty:
        return df
    df = df.copy()
    df["source"] = source_name
    df["ingested_at"] = INGESTED_AT
    df["record_id"] = [str(uuid.uuid4()) for _ in range(len(df))]
    df["consent_id"] = df["borrower_id"].map(consent_lookup)
    return df


def _write(df, output_dir, source_name, compress=False):
    source_dir = os.path.join(output_dir, source_name)
    os.makedirs(source_dir, exist_ok=True)
    ext = ".csv.gz" if compress else ".csv"
    path = os.path.join(source_dir, f"{source_name}{ext}")
    df.to_csv(path, index=False, compression="gzip" if compress else None)
    return path


def build_consent_audit_log(master_df, sources_present):
    """
    One row per borrower per source that was *attempted*, including
    sources that don't apply to that borrower (e.g. EPFO for Tier A).
    This is the traceability layer regulators / auditors would expect.
    """
    rows = []
    for _, b in master_df.iterrows():
        for source_name, applies_fn in sources_present.items():
            applies = applies_fn(b)
            rows.append({
                "borrower_id": b["borrower_id"],
                "source": source_name,
                "consent_id": b["consent_id"],
                "consent_status": "granted" if applies else "not_applicable",
                "consent_timestamp": INGESTED_AT,
                "purpose": "msme_financial_health_score",
            })
    return pd.DataFrame(rows)


def run_ingestion(output_dir, master, source_dfs):
    """
    source_dfs: {source_name: df} for every entry in SOURCES_PRESENT.
    """
    consent_lookup = dict(zip(master["borrower_id"], master["consent_id"]))

    os.makedirs(output_dir, exist_ok=True)

    paths = {}
    for source_name, df in source_dfs.items():
        tagged = _tag_source(df, source_name, consent_lookup)
        paths[source_name] = _write(tagged, output_dir, source_name, compress=source_name in COMPRESS_SOURCES)

    master_path = os.path.join(output_dir, "borrower_master.csv")
    master.drop(columns=["true_archetype"], errors="ignore").to_csv(master_path, index=False)
    paths["borrower_master"] = master_path

    audit_log = build_consent_audit_log(master, SOURCES_PRESENT)
    audit_path = os.path.join(output_dir, "consent_audit_log.csv")
    audit_log.to_csv(audit_path, index=False)
    paths["consent_audit_log"] = audit_path

    return paths
