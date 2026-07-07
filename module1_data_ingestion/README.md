# Module 1 — Data Ingestion Layer (Synthetic)

MSME Financial Health Score (Track 3). This is a **synthetic stand-in** for
the real ingestion connectors described in the architecture (AA, GSTN,
EPFO). No live API, consent flow, or bureau pull happens here — this
generates realistic-shaped data so Modules 2–7 can be built and demoed
without waiting on real integrations.

**Be upfront about this distinction in any pitch.** Nothing here proves the
scoring logic works on real MSME data — it proves the logic works on data
that *looks like* real MSME data by construction, because the generator
was written to match the archetype it also assigns.

## Run it

```bash
cd msme_data_gen
pip install pandas numpy
python run_generate.py
```

Produces `data_lake/`:

| File | Rows (this run) | Description |
|---|---|---|
| `borrower_master.csv` | 400 | One row per borrower: tier, sector, business age, has_epfo, consent_id |
| `gst_returns/gst_returns.csv` | ~9,600 | 24 months of GSTR-3B-style returns per borrower |
| `bank_upi_transactions/bank_upi_transactions.csv` | ~810,000 | 365 days of transaction-level bank/UPI activity |
| `epfo_contributions/epfo_contributions.csv` | ~3,700 | 24 months of EPFO contributions, Tier C only |
| `consent_audit_log.csv` | 1,200 | One row per (borrower, source) pull attempt, incl. not-applicable sources |
| `ground_truth/ground_truth_labels.csv` | 400 | **Hidden** archetype label — see warning below |

## Schema

**borrower_master.csv**
`borrower_id, tier (A/C), sector, business_age_years, has_epfo, consent_id`

- Tier A = thin-file/NTC: only GST + bank/UPI available, no EPFO (informal employer or no registered staff).
- Tier C = full-financials: GST + bank/UPI + EPFO.
- This mix (60% A / 40% C) is an assumption, not a market statistic — change `TIER_MIX` in `config.py` if your team has a better estimate.

**gst_returns.csv**
`borrower_id, period, due_date, filing_date (null = not filed), declared_turnover_inr, tax_paid_inr, itc_claimed_inr, source, ingested_at, record_id, consent_id`

**bank_upi_transactions.csv**
`borrower_id, txn_date, txn_type (credit/debit), category, amount_inr, running_balance_inr, bounce_flag, source, ingested_at, record_id, consent_id`

Categories: `sales_inflow, upi_transfer_in` (credit) / `vendor_payment, salary_payment, loan_emi, utility_payment, upi_transfer_out, cash_withdrawal, cheque_bounce_fee` (debit).

**epfo_contributions.csv**
`borrower_id, period, employee_count, wage_bill_inr, employer_contribution_inr, employee_contribution_inr, due_date, remittance_date (null = not remitted), source, ingested_at, record_id, consent_id`

**consent_audit_log.csv**
`borrower_id, source, consent_id, consent_status (granted/not_applicable), consent_timestamp, purpose`

A Tier A borrower's missing EPFO record shows up here as `not_applicable`, not silence. This matters for Module 2: **missing data must be flagged, never silently treated as bad data** — otherwise thin-file/NTC borrowers get penalized for being thin-file, which defeats the "expand access to credit-invisible MSMEs" goal in the brief and is a defensible fairness problem if a judge asks.

## The hidden ground-truth label — read this before Module 2/3

`ground_truth/ground_truth_labels.csv` assigns each borrower a `true_archetype`
(`healthy` / `stagnant` / `distressed`) that was used to *drive* every other
file's generation (turnover trend, filing delays, bounce rates, headcount
trend all shift with archetype — see the `ARCHETYPE_PARAMS` dicts in each
`*_source.py`).

**Do not join this file into feature engineering or model training.** It
exists for one purpose only: after Module 5/6 produce a health score,
check whether `distressed`-archetype borrowers actually land in the bottom
band and `healthy` ones in the top band. If they don't, the scoring logic
is wrong. If you train directly on this label, you're not testing the
scoring logic — you're just re-deriving the label you built the data from,
which will look perfect and prove nothing.

## Verified behavior (sanity-checked after generation)

Ran a distribution check across archetypes to confirm the generator
produces separable, directionally correct signal — not just noise:

| Metric | Healthy | Stagnant | Distressed |
|---|---|---|---|
| GST: % returns not filed | 0.6% | 2.2% | 8.0% |
| GST: avg filing delay (days, filed only) | -1.2 | +0.8 | +9.6 |
| GST: turnover growth ratio (last 3mo / first 3mo) | 1.23 | 1.01 | 0.74 |
| Bank: cheque bounce rate | 0.21% | 0.85% | 2.45% |
| Bank: balance trend (last decile avg − first decile avg) | +₹75.4L | +₹34.8L | +₹14.1L |
| EPFO: avg headcount change over 24mo | +4.6 | +0.6 | -7.7 |

All directionally correct (distressed borrowers file late, decline in
turnover, bounce more, and shed staff). Two known limitations to disclose,
not hide:

1. **Absolute bank balances run higher than a typical MSME current account**
   (median ~₹25L, max ~₹1.95Cr in this run). This falls out of ~2,000
   transactions/year at the amount scale chosen — it's an artifact of the
   generator's calibration, not a bug in the trend logic. If a judge
   pressure-tests absolute numbers rather than relative trends, say so
   plainly and adjust `config.py` scale parameters rather than defend it.
2. **All three archetypes are populated with independent random draws per
   borrower** — there's no correlation structure between e.g. sector and
   archetype, or macro shocks affecting multiple borrowers at once
   (seasonal demand shifts are modeled per-sector, but a sector-wide
   downturn isn't). Fine for a scoring-logic demo, not fine as evidence the
   model generalizes to a real portfolio.

## What a real Module 1 would need that this doesn't have

This generator is a placeholder for six things a production build must
still solve:
- Sahamati-compliant AA consent flow (this only logs a fake consent_id)
- Live GSTN/EPFO/bureau API contracts and auth
- Tampering detection on uploaded (non-AA) bank statements
- Real refresh-cadence handling per source (GST monthly, bank near-real-time, EPFO monthly, bureau on-pull)
- Cross-source consistency checks (GST turnover vs bank inflow mismatch) — that's Module 2, not built yet
- Data-completeness tiering as an *output* of real missing-data patterns, not an input assumption (here, tier is assigned before data is generated; in production it would be discovered by inspecting what actually came back from each source)

## Files

```
msme_data_gen/
  config.py          - all tunable assumptions (borrower count, tier mix, archetype mix, seed)
  borrowers.py        - borrower population + hidden ground truth
  gst_source.py        - GSTR-3B-style generator
  bank_upi_source.py  - bank/UPI transaction generator
  epfo_source.py       - EPFO contribution generator
  ingest.py            - tagging, consent audit log, data lake writer
  run_generate.py      - entry point
  data_lake/           - output (generated, not checked in by hand — rerun to regenerate)
```
