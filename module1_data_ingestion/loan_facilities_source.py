"""
Synthetic existing-loan-facility record - closes the gap where bank_upi's
loan_emi category used to be a single undifferentiated amount with no
principal, no loan ID, no outstanding balance, and no covenant concept.

Generated BEFORE bank_upi_source.py in run_generate.py: bank_upi's
scheduled loan_emi rows are now generated FROM this file's monthly_emi_inr
and loan_id, not independently - see bank_upi_source.py.

Gated on has_existing_loan (config.EXISTING_LOAN_PROB_BY_TIER). One
facility per borrower in this prototype (no multi-loan modeling).
covenant_status is archetype-conditioned: distressed borrowers are far
more likely to be in breach, mirroring every other archetype-conditioned
compliance signal in this generator.
"""

import uuid
import numpy as np
import pandas as pd
from config import rng, OBS_END_DATE

HAS_COVENANT_PROB = 0.50
COVENANT_BREACH_PROB_BY_ARCHETYPE = {"healthy": 0.03, "stagnant": 0.15, "distressed": 0.40}
INTEREST_RATE_RANGE = (0.09, 0.16)
TENURE_MONTHS_RANGE = (12, 84)

# Loan principal sized relative to annual turnover - a rough stylized
# assumption (not a real underwriting sizing rule).
PRINCIPAL_TO_TURNOVER_RANGE = (0.15, 0.6)


def generate_loan_facilities(internal_borrowers):
    rows = []
    loan_borrowers = internal_borrowers[internal_borrowers["has_existing_loan"]]
    end = pd.Timestamp(OBS_END_DATE)

    for _, b in loan_borrowers.iterrows():
        annual_turnover = b["true_monthly_turnover_base_inr"] * 12
        original_principal = round(annual_turnover * rng.uniform(*PRINCIPAL_TO_TURNOVER_RANGE), 2)
        tenure_months = int(rng.integers(*TENURE_MONTHS_RANGE))
        interest_rate = round(rng.uniform(*INTEREST_RATE_RANGE), 4)

        origination_months_ago = int(rng.integers(1, tenure_months))
        origination_date = (end - pd.DateOffset(months=origination_months_ago)).date()

        # Simple straight-line amortization approximation for the prototype
        # (not a real amortization schedule) - enough to give a plausible
        # outstanding balance and a stable monthly EMI figure.
        principal_paid_down_frac = min(origination_months_ago / tenure_months, 0.95)
        principal_outstanding = round(original_principal * (1 - principal_paid_down_frac), 2)
        monthly_emi = round(original_principal / tenure_months * (1 + interest_rate / 2), 2)

        has_covenant = rng.random() < HAS_COVENANT_PROB
        if has_covenant:
            breach_prob = COVENANT_BREACH_PROB_BY_ARCHETYPE[b["true_archetype"]]
            covenant_status = "breached" if rng.random() < breach_prob else "compliant"
        else:
            covenant_status = None

        rows.append({
            "borrower_id": b["borrower_id"],
            "loan_id": str(uuid.uuid4()),
            "principal_outstanding_inr": principal_outstanding,
            "original_principal_inr": original_principal,
            "interest_rate_pct_annual": round(interest_rate * 100, 2),
            "tenure_months": tenure_months,
            "monthly_emi_inr": monthly_emi,
            "has_covenant": has_covenant,
            "covenant_status": covenant_status,
            "origination_date": origination_date,
        })

    return pd.DataFrame(rows)
