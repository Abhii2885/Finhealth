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
            "items": {
                "type": "object",
                "required": ["key", "label", "score", "weight", "status"],
                "properties": {
                    "key": {"type": "string"},
                    "label": {"type": "string"},
                    "score": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
                    "weight": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                    "status": {"type": "string", "enum": ["available", "insufficient_data", "not_applicable", "not_computable_in_prototype"]},
                    "top_positive_driver": {"type": ["string", "null"]},
                    "top_negative_driver": {"type": ["string", "null"]},
                },
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
