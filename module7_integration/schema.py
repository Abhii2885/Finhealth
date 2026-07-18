"""
API contracts (JSON Schema, draft-07 style) for the two endpoints this
module exposes. See config.py's module docstring for the honesty caveat:
these are illustrative, not a certified ULI/OCEN reproduction.
"""

SCORE_CARD_RESPONSE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "MSMEFinancialHealthScoreCard",
    "description": "Illustrative presentment payload a loan service provider (LSP) "
                   "would pull via a ULI/OCEN-style presentment layer. NOT a "
                   "certified reproduction of the official spec.",
    "type": "object",
    "required": ["borrower_id", "consent_id", "as_of_date", "composite_score", "grade",
                 "dimensions", "scorable", "data_provenance"],
    "properties": {
        "borrower_id": {"type": "string"},
        "consent_id": {"type": "string", "description": "AA consent artifact ID this pull was authorized under"},
        "as_of_date": {"type": "string", "format": "date", "description": "Date the underlying data was last ingested/computed"},
        "composite_score": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
        "grade": {"type": "string"},
        "segment_label": {"type": "string"},
        "scorable": {"type": "boolean", "description": "False if too few dimensions had usable data (Module 4's eligibility floor)"},
        "dimensions": {
            "type": "array",
            "description": "The 5 Cs of Credit: capacity, character, capital, compliance, collateral",
            "items": {
                "type": "object",
                "required": ["key", "label", "score", "weight", "status"],
                "properties": {
                    "key": {"type": "string"},
                    "label": {"type": "string"},
                    "score": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
                    "weight": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                    "status": {"type": "string", "enum": ["available", "insufficient_data", "not_applicable"]},
                    "top_positive_driver": {"type": ["string", "null"]},
                    "top_negative_driver": {"type": ["string", "null"]},
                    "submetrics": {
                        "type": "array",
                        "description": "Optional per-submetric breakdown within this C",
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "score": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
                                "weight": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                                "status": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "context": {
            "type": "object",
            "description": "Applicant-level flags that gate which submetrics apply - the real "
                            "future-user-input surface (see APPLICANT_INPUT_REQUEST_SCHEMA); "
                            "Module 1 simulates these across the synthetic population today.",
            "properties": {
                "is_gst_registered": {"type": "boolean"},
                "balance_sheet_available": {"type": "boolean"},
                "has_bureau_record": {"type": "boolean"},
                "has_existing_loan": {"type": "boolean"},
                "has_collateral": {"type": "boolean"},
                "projected_revenue_next_year_inr": {"type": ["number", "null"]},
            },
        },
        "data_provenance": {
            "type": "object",
            "description": "Honesty metadata - what this score is and isn't, attached to every response",
            "properties": {
                "source": {"type": "string"},
                "schema_label": {"type": "string"},
                "disclaimer": {"type": "string"},
            },
        },
    },
}

CONSENT_REFRESH_REQUEST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "AAConsentRefreshEvent",
    "description": "Illustrative webhook payload representing 'new statement data "
                    "landed for this borrower, consider recomputing their score.' "
                    "NOT a certified AA/Sahamati event schema reproduction.",
    "type": "object",
    "required": ["borrower_id", "consent_id", "event_type"],
    "properties": {
        "borrower_id": {"type": "string"},
        "consent_id": {"type": "string"},
        "event_type": {"type": "string", "enum": ["new_data_available", "consent_renewed", "consent_revoked"]},
        "source": {"type": "string", "description": "e.g. 'bank_upi_transactions', 'gst_returns', 'epfo_contributions'"},
    },
}

CONSENT_REFRESH_RESPONSE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "AAConsentRefreshAck",
    "type": "object",
    "required": ["borrower_id", "status", "note"],
    "properties": {
        "borrower_id": {"type": "string"},
        "status": {"type": "string", "enum": ["queued"]},
        "received_at": {"type": "string"},
        "note": {"type": "string", "description": "Honesty note: recompute is NOT actually triggered in this prototype"},
    },
}

# Real future-user-input surface: this is the one place the synthetic
# population simulation (Module 1 randomly assigns balance_sheet_available
# etc. across 400 borrowers) and "a real applicant supplies this" genuinely
# diverge. Structurally parallel to CONSENT_REFRESH_* - logged only, same
# honesty caveat, does not trigger a live recompute.
APPLICANT_INPUT_REQUEST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ApplicantInputSubmission",
    "description": "A real applicant/loan-officer supplying data Module 1 otherwise "
                    "simulates for the synthetic population (e.g. 'balance sheet not "
                    "available' or a projected-revenue figure from an application PDF).",
    "type": "object",
    "properties": {
        "balance_sheet_available": {"type": "boolean"},
        "projected_revenue_next_year_inr": {"type": ["number", "null"], "minimum": 0},
    },
}

APPLICANT_INPUT_RESPONSE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ApplicantInputAck",
    "type": "object",
    "required": ["borrower_id", "status", "note"],
    "properties": {
        "borrower_id": {"type": "string"},
        "status": {"type": "string", "enum": ["queued"]},
        "received_at": {"type": "string"},
        "note": {"type": "string", "description": "Honesty note: recompute is NOT actually triggered in this prototype"},
    },
}

# Server-side counterpart to the Module 6 dashboard's client-side override
# capability (localStorage + export) - best-effort only, used if this
# server happens to be reachable from the dashboard; the dashboard's own
# export path is the mechanism that always works, since it's a standalone
# offline file with no backend by design.
OVERRIDE_REQUEST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ScoreOverrideSubmission",
    "type": "object",
    "required": ["parameter", "overridden_score", "comment"],
    "properties": {
        "parameter": {"type": "string", "description": "e.g. 'capacity' or 'capacity.dscr'"},
        "original_score": {"type": ["number", "null"]},
        "overridden_score": {"type": "number", "minimum": 0, "maximum": 100},
        "comment": {"type": "string", "minLength": 1, "description": "Required justification - captured as feedback for future model training"},
    },
}

OVERRIDE_RESPONSE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ScoreOverrideAck",
    "type": "object",
    "required": ["borrower_id", "status", "note"],
    "properties": {
        "borrower_id": {"type": "string"},
        "status": {"type": "string", "enum": ["queued"]},
        "received_at": {"type": "string"},
        "note": {"type": "string"},
    },
}
