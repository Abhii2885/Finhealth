"""
Synthetic owner/guarantor/related-party entity table - the first
genuinely multi-entity source in this generator (every prior source is
one row/borrower or one row/borrower/period; this is 1-3 rows/borrower).

Feeds Module 3's Character features: owner_time_in_business_years, and
provides the entity_id join key bureau_source.py uses to attach bureau
records to owners/guarantors, not just the borrower entity itself.

Every borrower gets exactly one "owner" row (role=proprietor and
relationship_type=owner); a minority also get a guarantor and/or a
related-party row, reflecting that most small borrowers don't have a
formal guarantor structure, but some do.
"""

import uuid
import numpy as np
import pandas as pd
from config import rng

OWNER_ROLES = {"owner": "proprietor", "guarantor": "guarantor", "related_party": "related_party_principal"}

# Probability a borrower has an additional guarantor / related-party row,
# beyond the always-present primary owner row. Independent of archetype -
# having a guarantor is a structural/product choice, not a health signal.
GUARANTOR_PROB = 0.35
RELATED_PARTY_PROB = 0.15


def generate_owners(internal_borrowers):
    rows = []

    for _, b in internal_borrowers.iterrows():
        business_age = max(b["business_age_years"], 0.5)

        # Primary owner: time-in-business correlated with (but noisier than)
        # the entity's own business_age_years - an owner who's run this
        # specific business that long, plus some prior-venture experience.
        owner_tib = round(max(business_age * rng.uniform(0.9, 1.6), 0.5), 1)
        rows.append({
            "borrower_id": b["borrower_id"],
            "owner_id": str(uuid.uuid4()),
            "owner_role": OWNER_ROLES["owner"],
            "owner_time_in_business_years": owner_tib,
            "relationship_type": "owner",
        })

        if rng.random() < GUARANTOR_PROB:
            rows.append({
                "borrower_id": b["borrower_id"],
                "owner_id": str(uuid.uuid4()),
                "owner_role": OWNER_ROLES["guarantor"],
                "owner_time_in_business_years": round(max(rng.uniform(1, 25), 0.5), 1),
                "relationship_type": "guarantor",
            })

        if rng.random() < RELATED_PARTY_PROB:
            rows.append({
                "borrower_id": b["borrower_id"],
                "owner_id": str(uuid.uuid4()),
                "owner_role": OWNER_ROLES["related_party"],
                "owner_time_in_business_years": round(max(rng.uniform(1, 25), 0.5), 1),
                "relationship_type": "related_party",
            })

    return pd.DataFrame(rows)
