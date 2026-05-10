"""Unit tests for contact deduplication."""
from src.sourcing.validation.dedup import deduplicate_contacts


def test_dedup_by_email():
    contacts = [
        {"email": "alice@acme.com", "name": "Alice", "icp_score": 0.8},
        {"email": "alice@acme.com", "name": "Alice A", "icp_score": 0.9},
        {"email": "bob@corp.com", "name": "Bob", "icp_score": 0.7},
    ]
    result = deduplicate_contacts(contacts)
    assert len(result) == 2
    # Should keep the higher-scored Alice
    alice = [r for r in result if "alice" in r["email"]][0]
    assert alice["icp_score"] == 0.9


def test_dedup_empty_email():
    contacts = [
        {"email": "", "name": "NoEmail"},
        {"email": "valid@test.com", "name": "Valid"},
    ]
    result = deduplicate_contacts(contacts)
    assert len(result) == 1
    assert result[0]["email"] == "valid@test.com"


def test_dedup_case_insensitive():
    contacts = [
        {"email": "Test@Example.COM", "icp_score": 0.5},
        {"email": "test@example.com", "icp_score": 0.6},
    ]
    result = deduplicate_contacts(contacts)
    assert len(result) == 1
    assert result[0]["icp_score"] == 0.6
