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
"""

import os
import uuid
import pandas as pd
from datetime import datetime, timezone

INGESTED_AT = datetime.now(timezone.utc).isoformat()


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


def run_ingestion(output_dir, master, gst_df, bank_df, epfo_df):
    consent_lookup = dict(zip(master["borrower_id"], master["consent_id"]))

    os.makedirs(output_dir, exist_ok=True)

    gst_tagged = _tag_source(gst_df, "gst_returns", consent_lookup)
    bank_tagged = _tag_source(bank_df, "bank_upi_transactions", consent_lookup)
    epfo_tagged = _tag_source(epfo_df, "epfo_contributions", consent_lookup)

    paths = {
        "gst_returns": _write(gst_tagged, output_dir, "gst_returns"),
        # bank/UPI is transaction-level and large (~800k rows) - gzip it,
        # pandas reads .csv.gz transparently via pd.read_csv().
        "bank_upi_transactions": _write(bank_tagged, output_dir, "bank_upi_transactions", compress=True),
        "epfo_contributions": _write(epfo_tagged, output_dir, "epfo_contributions"),
    }

    master_path = os.path.join(output_dir, "borrower_master.csv")
    master.drop(columns=["true_archetype"], errors="ignore").to_csv(master_path, index=False)
    paths["borrower_master"] = master_path

    sources_present = {
        "gst_returns": lambda b: True,                 # all borrowers file GST (informal or formal)
        "bank_upi_transactions": lambda b: True,       # all borrowers have bank/UPI activity
        "epfo_contributions": lambda b: bool(b["has_epfo"]),
    }
    audit_log = build_consent_audit_log(master, sources_present)
    audit_path = os.path.join(output_dir, "consent_audit_log.csv")
    audit_log.to_csv(audit_path, index=False)
    paths["consent_audit_log"] = audit_path

    return paths
