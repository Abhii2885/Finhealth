# MSME Financial Health Score Using Alternate Data

An end-to-end prototype of a credit-assessment platform that scores Micro, Small and Medium Enterprises (MSMEs) on the **5 Cs of Credit** — Capacity, Character, Capital, Compliance, and Collateral — using alternate data sources (GST filings, bank/UPI transaction flows, EPFO remittances, utility and rent payment behaviour, bureau records, balance sheets, collateral records, and legal-dispute registries) rather than collateral-first or financial-statement-only underwriting. A transparent, rule-based scorecard serves as the score of record, with a champion–challenger machine-learning layer running in parallel for anomaly detection and independent risk validation.

Developed as a submission for the **IDBI Innovate** hackathon.

---

## 1. Background and Context

### The problem

A large share of Indian MSMEs remains outside the formal credit system. Traditional underwriting depends on audited financial statements, established bureau histories, and hard collateral — precisely the artefacts that new-to-credit (NTC), informal, or early-stage enterprises lack. The result is a well-documented credit gap: enterprises that are genuinely creditworthy, and demonstrably so through their day-to-day digital footprint, are declined or priced out because the evidence of their health is not in the format lenders conventionally read.

### The proposition

An MSME's financial health is continuously visible in data it already generates: GST return filings, bank and UPI transaction flows, EPFO remittances, utility and rent payments, and salary discipline. This project demonstrates that such alternate data can be assembled into a **transparent, explainable, lender-calibrated composite score** — one in which every point is traceable to a named rule, every submetric shows its actual underlying value with its source and date, and a credit manager can override any component with a recorded justification.

### Design principles

1. **Explainability over opacity.** The score of record is a rule-based scorecard. Every submetric's scoring method is documented on the dashboard itself via per-row information buttons.
2. **Missing data is handled by exclusion and renormalisation, never penalisation.** A borrower without a balance sheet is not punished for lacking one; the affected submetrics are excluded and the remaining weights renormalise proportionally.
3. **ML augments; it does not silently decide.** The machine-learning layer flags anomalies and disagreements for human review. It never overrides the scorecard.
4. **Honest disclosure of limitations.** Each module's README records what is real, what is simulated, and what is a documented assumption. This discipline is maintained deliberately throughout the codebase.

---

## 2. Synthetic Data Generation (Module 1)

No real borrower data is used anywhere in this project. Module 1 generates a fully synthetic population of **400 MSME borrowers** with internally consistent, cross-correlated data across eleven sources.

### How generation works

- Each borrower is assigned a hidden **archetype** — `healthy`, `stagnant`, or `distressed` — that conditions every downstream source (revenue trajectory, filing discipline, leverage, bureau score, litigation propensity, payment lateness). The archetype is written to a `ground_truth` file used **only for backtesting** — no scoring module is permitted to read it.
- Borrowers belong to a **tier** (A: thin-file/new-to-credit-leaning; C: more formalised), which conditions the probability of having a balance sheet, bureau record, existing loan, collateral, and GST registration — so data availability itself mirrors real-world patterns.
- Five master-level gating flags (`is_gst_registered`, `balance_sheet_available`, `has_bureau_record`, `has_existing_loan`, `has_collateral`) determine which sources exist for each borrower. Roughly 10% of Tier A borrowers are non-GST-registered and provide self-declared turnover instead.
- All sources are anchored to a common turnover base per borrower, so bank inflows, GST turnover, balance-sheet magnitudes, and collateral values are mutually consistent rather than independently random.

### What the data contains

| Source | Contents |
|---|---|
| `borrower_master.csv` | Borrower identity, sector, tier, business age, gating flags |
| `gst_returns/` | 36 months of monthly GST filings: declared turnover, due date, filing date (or missed) |
| `self_declared_turnover/` | Monthly turnover series for non-GST-registered borrowers |
| `bank_upi_transactions/` | ~1 year of transaction-level bank/UPI data: sales inflows, vendor payments, salary, utility, rent, loan EMIs (with due dates and counterparty identifiers), cheque bounces |
| `epfo_contributions/` | Monthly EPFO remittances with due and remittance dates |
| `balance_sheet/` | Point-in-time balance sheet: assets, liabilities, debt, net worth |
| `bureau_data/` | CIBIL-style bureau records (300–900 scale) for entity and owners |
| `loan_facilities/` | Existing loan detail: principal, EMI, tenure, covenant status |
| `collateral/` | Collateral type (residential/commercial/industrial), construction status, estimated value |
| `legal_disputes/` | Civil suits and other disputes with filed/resolved dates and status |
| `owners/` | Owner/guarantor records with time in business |
| `loan_application/` | Self-reported projected revenue growth from the loan application |
| `ground_truth/` | Hidden archetype labels — backtesting only |

The generated data lake (~61 MB) is **not committed to the repository**; it is regenerated deterministically with one command (see Setup below).

---

## 3. The 5C Scorecard

### Dimension weights

| Dimension | Weight | What it measures |
|---|---|---|
| **Capacity** | 30% | Ability to service debt: DSCR, cash-flow-to-turnover match, current ratio, interest coverage, leverage, revenue CAGR, projected growth, customer/supplier concentration |
| **Character** | 25% | Reliability and track record: bureau score, legal-dispute recency, cheque bounce rate, owner's time in business |
| **Capital** | 20% | Owner's stake: net worth as a share of total assets |
| **Compliance** | 15% | Statutory and payment discipline: covenant status, GST filing, EPFO remittance, utility/rent/salary timeliness (trailing 6 months) |
| **Collateral** | 10% | Security quality: type × construction status |

### Scoring methods

Each submetric is scored 0–100 by the method appropriate to its nature, and each method is disclosed on the dashboard via the row's information button:

- **Tiered (lender-calibrated).** Most Capacity/Character/Capital submetrics follow a lender-supplied Score Band rubric (four tiers scoring 0–3 / 4–6 / 7–9 / 10), implemented as continuous piecewise-linear interpolation between the named cutoffs — e.g. DSCR below 1.0× scores 0–3, above 1.5× scores 10; leverage (debt/net-worth, Indian MSME convention) below 1× scores 10, above 7× approaches 0.
- **Direct ratio.** All Compliance submetrics score as the ratio itself × 10: 50% on-time GST filing scores 5/10, 80% scores 8/10 — absolute and portable, not relative to the batch.
- **Band distance.** Cash-flow match targets the 70–80% band; deviation in *either* direction reduces the score (a 95% match is not healthier than 75%).
- **Lookup table.** Collateral quality maps type × construction status (residential constructed = 10 … industrial bare plot = 2).
- **Percentile.** A small number of remaining submetrics rank against the 400-borrower population.

### Aggregation and grades

Submetric scores combine into dimension scores via **per-borrower effective weights**: when a submetric is not applicable (no loan → no DSCR) or its data is too thin, its weight is zeroed and the remainder renormalises within the dimension; the same mechanism operates across dimensions. Composite 0–100 maps to grades: **A – Strong** (80+), **B – Good** (65–80), **C – Fair** (50–65), **D – Weak** (35–50), **E – Poor** (below 35), with matching green/amber/red (RAG) colouring throughout the dashboard.

---

## 4. The Machine-Learning Layer (Champion–Challenger)

The rule-based scorecard is the **champion** — the score a credit manager acts on. Two ML models run in parallel as **challengers**, for monitoring only:

- **Isolation Forest** (anomaly detection): flags borrowers whose overall data *pattern* is statistically unusual for the portfolio — a multivariate signal the scorecard, which evaluates one metric at a time, structurally cannot produce. The dashboard explains each flag in plain language by naming the specific feature combination driving it.
- **Gradient Boosting** (challenger score): an independent 0–100 risk score trained on the same 22 features the scorecard sees. Where champion and challenger diverge by ≥25 points (~9% of the portfolio), the file is flagged for manual review, with an auto-generated explanation naming the submetrics most responsible.
- **Feedback loop**: every score override on the dashboard requires a written justification, exported as structured JSON — the intended training feedback once real repayment outcomes exist.

**Disclosed limitation:** no real repayment outcomes exist in synthetic data, so the challenger trains against the hidden archetype label as a proxy. Swapping in real outcomes is a one-line configuration change (`module9_ml_layer/config.py`).

---

## 5. Module Reference

| Module | Purpose |
|---|---|
| **1 — Data Ingestion** (`module1_data_ingestion/`) | Generates the synthetic 400-borrower population and all eleven data sources; simulates consent-audited ingestion into a `data_lake/` |
| **2 — Data Quality** (`module2_data_quality/`) | Schema validation, completeness checks, GST-vs-bank consistency cross-checks, and per-submetric availability tiering (`available` / `insufficient_data` / `not_applicable`) that drives downstream weight renormalisation. Self-tests by injecting known defects and confirming detection |
| **3 — Feature Engineering** (`module3_feature_engineering/`) | Transforms raw sources into the 22 scorecard submetrics (per-dimension builders); validates every directional feature separates the hidden archetypes correctly (20/20) |
| **4 — Segmentation & Weighting** (`module4_segmentation/`) | The policy layer: computes per-borrower effective weights via exclusion-and-renormalisation at both submetric and dimension level; enforces the minimum-dimensions rule for scorability |
| **5 — Scoring Engine** (`module5_scoring/`) | Applies the five scoring methods, aggregates to dimension and composite scores, assigns grades; backtests composite ordering against hidden archetypes |
| **6 — Explainability Dashboard** (`module6_explainability/`) | Generates a standalone offline HTML dashboard (all data and Chart.js embedded — no server, no network dependency). See feature list below |
| **7 — Integration Layer** (`module7_integration/`) | Mock ULI/OCEN-style presentment API with schema-validated score-card, consent-refresh, applicant-inputs, and override endpoints; an automated demo proves the contract end-to-end |
| **8 — Monitoring & Feedback** (`module8_monitoring/`) | PSI-based score-drift detection (self-tested with injected shifts), tier/archetype bias checks, short-history fairness checks, and recompute triggers from staleness and consent events |
| **9 — ML Layer** (`module9_ml_layer/`) | The champion–challenger implementation: Isolation Forest anomaly scores, Gradient Boosting challenger with held-out validation and permutation feature importance, divergence comparison and review flagging |

### Dashboard features (Module 6)

- **Scorecard table per dimension**: Parameter | Actual value (with source and as-of date) | Model score (out of 10) | Override
- **Information button on every row** disclosing the exact scoring method and thresholds
- **Live overrides**: changing any submetric score (mandatory justification) recomputes the dimension score, composite, grade, RAG colours, and the ML divergence flag instantly; overrides export as JSON
- **ML advisory chips**: "Model divergence — review advised" and "Unusual profile (ML)", each with plain-language, per-borrower explanations; a collapsed ML Model Insights card holds the full champion/challenger detail
- **Five chart types**: radar, horizontal bar, weighted-contribution donut, composite gauge, score waterfall
- **Financial health trend** across the borrower's observed history, with a plain-language auto-generated reading
- **Auto-generated commentary** summarising each borrower's strengths and weaknesses

---

## 6. Setup and Execution

### Prerequisites

- Python 3.12+ (developed on 3.14)
- `pandas`, `numpy` (all modules), `scikit-learn` (Module 9 only)

```bash
pip install pandas numpy scikit-learn
```

### Running the pipeline

Modules must run in order on first use (each consumes the previous module's output). From the repository root:

```bash
# 1. Generate the synthetic data lake (~61 MB, deterministic)
cd module1_data_ingestion && python3 run_generate.py && cd ..

# 2. Data quality and availability tiering
cd module2_data_quality && python3 run_module2.py ../module1_data_ingestion/data_lake && cd ..

# 3. Feature engineering
cd module3_feature_engineering && python3 run_module3.py && cd ..

# 4. Per-borrower weighting policy
cd module4_segmentation && python3 run_module4.py && cd ..

# 5. Scoring and grading
cd module5_scoring && python3 run_module5.py \
    "$(python3 -c 'import config; print(config.DEFAULT_FEATURES_DIR)')" \
    "$(python3 -c 'import config; print(config.DEFAULT_SEGMENTATION_DIR)')" \
    ../module1_data_ingestion/data_lake && cd ..

# 6. Build the dashboard  ->  module6_explainability/explainability_output/dashboard.html
cd module6_explainability && python3 run_module6.py && cd ..

# 7. Integration API demo (starts a mock server, exercises every endpoint, validates schemas)
cd module7_integration && python3 verify_demo.py && cd ..

# 8. Monitoring: drift, bias, recompute triggers
cd module8_monitoring && python3 run_module8.py && cd ..

# 9. ML layer: anomaly detection + challenger + divergence report
cd module9_ml_layer && python3 run_module9.py && cd ..
```

Open `module6_explainability/explainability_output/dashboard.html` directly in any browser — it is fully self-contained and works offline. Re-run Module 6 after Module 9 so the dashboard picks up the ML outputs (it degrades gracefully if Module 9 has not run).

### Verifying correctness

Each module prints its own validation on completion. The primary regression gate is Module 5's backtest: mean composite scores must order `healthy > stagnant > distressed` on the hidden archetypes (`ordering_correct: true`). Module 3 reports per-feature direction checks (20/20 expected); Module 2's self-test confirms injected defects are caught; Module 8's PSI self-test confirms an injected score shift is detected.

---

## 7. Known Limitations (Disclosed by Design)

- **All data is synthetic.** Score distributions, thresholds, and model performance reflect the generator's assumptions, not any real portfolio. Grade bands and the ML divergence threshold are uncalibrated against real outcomes.
- **The ML challenger trains on a proxy label** (hidden archetype), not real repayment behaviour; its near-perfect holdout fit on the full feature set is a documented synthetic-data artefact, analysed honestly in `module9_ml_layer/README.md` alongside a robustness run.
- **The PSI drift self-test is noisy at this sample size** (400 borrowers ≈ 20 per bin) — a standard small-sample limitation, documented in `module8_monitoring/drift.py` rather than hidden by threshold tuning.
- **The integration layer is a mock**, implementing an illustrative ULI/OCEN-inspired contract; it is not connected to any live sandbox.
- **The trend view is a three-signal proxy** (bank balance, cheque bounces, GST timeliness), not a historical replay of the full 22-parameter score — stated on the dashboard itself.

Per-module READMEs contain deeper methodology notes, validation results, and the full record of assumptions.
