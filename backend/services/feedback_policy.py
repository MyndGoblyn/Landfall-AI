"""Privacy and promotion boundaries for user recommendation feedback.

Feedback is deliberately stored as private evaluation history.  This module
does not expose a scoring hook: a future offline release process must satisfy
the documented cohort and provenance gates before a behavioral aggregate can
become reviewed semantic evidence.
"""

from __future__ import annotations

from typing import Dict


FEEDBACK_SCHEMA_VERSION = 1
MINIMUM_UNIQUE_USERS = 25
MINIMUM_EVENTS_PER_COHORT = 50


def feedback_policy_status() -> Dict:
    return {
        "schema_version": FEEDBACK_SCHEMA_VERSION,
        "storage_scope": "private_user_history",
        "production_ranking_influence": False,
        "automatic_learning": False,
        "aggregation": {
            "enabled": False,
            "minimum_unique_users": MINIMUM_UNIQUE_USERS,
            "minimum_events_per_cohort": MINIMUM_EVENTS_PER_COHORT,
            "requires_provenance": True,
            "requires_offline_review": True,
            "requires_versioned_release": True,
            "requires_rollback": True,
        },
    }
