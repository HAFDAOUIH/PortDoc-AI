"""Personas — job-function identities that drive RBAC, grounded in the real org.

CIRES Technologies (Tanger Med's security/sovereignty subsidiary: SOC + NOC,
electronic security, digital sovereignty) builds solutions for Tanger Med, whose
staff span public-facing, operations, and security roles. Each persona maps to a
clearance level; switching persona re-runs retrieval under that clearance — real
row-level access control, demonstrated as "logged in as".
"""

from __future__ import annotations

PERSONAS = [
    {
        "id": "nadia",
        "name": "Nadia Cherkaoui",
        "role": "Reception / User Relations Agent",
        "department": "Reception",
        "clearance": 0,
        "initials": "NC",
    },
    {
        "id": "karim",
        "name": "Karim El Idrissi",
        "role": "Port Operations Agent",
        "department": "Operations",
        "clearance": 1,
        "initials": "KE",
    },
    {
        "id": "salma",
        "name": "Salma Bennani",
        "role": "Port Facility Security Officer (PFSO)",
        "department": "Port Security",
        "clearance": 2,
        "initials": "SB",
    },
    {
        "id": "yassine",
        "name": "Yassine Alaoui",
        "role": "SOC Analyst",
        "department": "CIRES · Security Operations Center",
        "clearance": 2,
        "initials": "YA",
    },
]

_BY_ID = {p["id"]: p for p in PERSONAS}


def clearance_for(persona_id: str | None) -> int:
    if persona_id and persona_id in _BY_ID:
        return _BY_ID[persona_id]["clearance"]
    return 0  # unknown identity -> least privilege
