# Module 1 — Data Ingestion Layer (Synthetic)

## v2 update (built while adding Module 2)

Building the Module 2 data-quality checks exposed two real gaps in v1 of
this generator, fixed here:

1. **GST turnover and bank inflow were drawn independently per borrower.**
   That made a GST-vs-bank cross-source consistency check meaningless -
   every borrower would look "inconsistent" for no real reason, since the
   two numbers never had a relationship to begin with. Fixed: both now
   derive from a shared `true_monthly_turnover_base_inr` (see
   `borrowers.py`), and a minority of borrowers (~14%, skewed toward the
   distressed archetype) are generated as GST "under-reporters" - a
   deliberate, disclosed fraud-like signal for Module 2 to try to catch.
   It catches it with precision ~0.40 / recall ~0.29 on a single-year
   ratio check alone - reported honestly in Module 2's README, not
   oversold.
2. **Every borrower had suspiciously complete history** (full 24
   GST/EPFO months, full 365 bank days, no gaps). That meant Module 2's
   "insufficient_data" completeness path could never actually fire on
   real data - only on hand-injected test defects. Fixed: ~15% of Tier A
   (thin-file) borrowers now get genuinely short history (3.5-11 months
   instead of 24), via `truncate_history.py`, applied after generation.

Also fixed in v1→v2: bank balances were briefly compounding
multiplicatively per transaction (crore-scale artifacts) - already
corrected before the first push; see the "known limitations" section
below, which still applies.

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
| `gst_returns/gst_returns.csv` | ~8,900 | 24 months of GSTR-3B-style returns per borrower (fewer for the ~15% of Tier A borrowers with genuinely short history) |
| `bank_upi_transactions/bank_upi_transactions.csv.gz` | ~1.5M | 365 days of transaction-level bank/UPI activity, gzip-compressed |
| `epfo_contributions/epfo_contributions.csv` | ~3,700 | 24 months of EPFO contributions, Tier C only |
| `consent_audit_log.csv` | 1,200 | One row per (borrower, source) pull attempt, incl. not-applicable sources |
| `ground_truth/ground_truth_labels.csv` | 400 | **Hidden** fields — see warning below |

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

## The hidden ground-truth fields — read this before Module 2/3

`ground_truth/ground_truth_labels.csv` has five fields, all hidden by design:

- `true_archetype` (`healthy` / `stagnant` / `distressed`) - drives turnover trend, filing delays, bounce rates, headcount trend (see `ARCHETYPE_PARAMS` in each `*_source.py`).
- `true_monthly_turnover_base_inr` - the shared revenue anchor both GST and bank/UPI generation derive from.
- `gst_underreport_pct` / `is_gst_underreporter` - ~14% of borrowers (skewed toward distressed) under-report GST turnover relative to true bank-verified revenue. This is what Module 2's cross-source consistency check is meant to catch.
- `history_available_frac` / `has_short_history` - ~15% of Tier A borrowers have genuinely short history (3.5-11 months, not the full 24) instead of a full track record.

**Do not join this file into feature engineering or model training.** It
exists for one purpose only: after Module 2/5/6 produce their outputs,
check whether they actually recover these known-by-construction patterns
(do distressed borrowers land in the bottom score band, does Module 2 flag
the under-reporters, does the completeness tier correctly identify the
short-history borrowers as thin). If you train directly on these fields,
you're not testing the logic — you're just re-deriving the label you built
the data from, which will look perfect and prove nothing.

## Verified behavior (sanity-checked after generation)

Ran a distribution check across archetypes to confirm the generator
produces separable, directionally correct signal — not just noise:

| Metric | Healthy | Stagnant | Distressed |
|---|---|---|---|
| GST: % returns not filed | 0.8% | 2.0% | 9.2% |
| GST: avg filing delay (days, filed only) | -1.3 | +0.8 | +9.1 |
| GST: turnover growth ratio (last 3mo / first 3mo) | 1.20 | 1.05 | 0.72 |
| Bank: cheque bounce rate | 0.22% | 0.82% | 2.56% |
| Bank: balance trend (last decile avg − first decile avg) | +₹336L | +₹164L | +₹66L |
| EPFO: avg headcount change over 24mo | +4.9 | +0.5 | -6.2 |

All directionally correct (distressed borrowers file late, decline in
turnover, bounce more, and shed staff). Known limitations to disclose,
not hide:

1. **Absolute bank balances run higher than a typical MSME current account**
   (median ~₹1.3Cr, max ~₹6.6Cr in this run - up from v1 after anchoring
   bank scale to turnover in the v2 correlation fix). This falls out of the
   transaction volume/amount calibration, not a bug in the trend logic. If
   a judge pressure-tests absolute numbers rather than relative trends, say
   so plainly and adjust `config.py` / the `scale` clip in
   `bank_upi_source.py` rather than defend it.
2. **All three archetypes are populated with independent random draws per
   borrower** — there's no correlation structure between e.g. sector and
   archetype, or macro shocks affecting multiple borrowers at once
   (seasonal demand shifts are modeled per-sector, but a sector-wide
   downturn isn't). Fine for a scoring-logic demo, not fine as evidence the
   model generalizes to a real portfolio.
3. **The GST-vs-bank consistency signal is real but weak on its own** -
   Module 2's backtest against `is_gst_underreporter` gets precision ~0.40,
   recall ~0.29 from a single annual ratio. See Module 2's README for the
   honest read on this (short version: one ratio isn't enough, combine
   with other signals).

## What a real Module 1 would need that this doesn't have

This generator is a placeholder for six things a production build must
still solve:
- Sahamati-compliant AA consent flow (this only logs a fake consent_id)
- Live GSTN/EPFO/bureau API contracts and auth
- Tampering detection on uploaded (non-AA) bank statements
- Real refresh-cadence handling per source (GST monthly, bank near-real-time, EPFO monthly, bureau on-pull)
- Cross-source consistency checks (GST turnover vs bank inflow mismatch) — now built, see `module2_data_quality/`
- Data-completeness tiering as an *output* of real missing-data patterns, not an input assumption — also now built in Module 2, though the "insufficient_data" path is only exercised by the ~15% short-history Tier A minority; it's still not modeling gradual data decay, service outages, or partial-month gaps

## Files

```
msme_data_gen/
  config.py              - all tunable assumptions (borrower count, tier mix, archetype mix, seed)
  borrowers.py            - borrower population + hidden ground truth
  gst_source.py           - GSTR-3B-style generator
  bank_upi_source.py      - bank/UPI transaction generator
  epfo_source.py          - EPFO contribution generator
  truncate_history.py     - post-generation truncation for the short-history borrower minority
  ingest.py               - tagging, consent audit log, data lake writer
  run_generate.py         - entry point
  data_lake/              - output (generated, not checked in by hand — rerun to regenerate)
```
