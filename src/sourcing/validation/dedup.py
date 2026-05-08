"""Deduplicate contacts by email, keeping the highest-scored entry."""
from typing import Any


def deduplicate_contacts(
    contacts: list[dict[str, Any]],
    key_field: str = "email",
) -> list[dict[str, Any]]:
    """Remove duplicate contacts, keeping the one with the highest icp_score."""
    seen: dict[str, dict[str, Any]] = {}

    for contact in contacts:
        key = contact.get(key_field, "").lower().strip()
        if not key:
            continue

        existing = seen.get(key)
        if existing is None:
            seen[key] = contact
        else:
            # Keep whichever has the higher ICP score
            if contact.get("icp_score", 0) > existing.get("icp_score", 0):
                seen[key] = contact

    return list(seen.values())
