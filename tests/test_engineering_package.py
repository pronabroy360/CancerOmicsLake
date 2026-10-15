import pytest

from src.operations.engineering_package import _deduplicate, author_gates, no_identifiers


def test_empty_author_fields_never_become_confirmed():
    gates = author_gates({"manuscript": {"author": {"metadata_verified": True},
                                       "declarations": {"declarations_verified": True}}})
    assert not any(row["passed"] for row in gates)
    assert {row["gate"] for row in gates} >= {"independent_reproduction", "publication_approval"}
    placeholders = author_gates({"manuscript": {"author": {"metadata_verified": True,
                                "name": "Researcher", "affiliation": "[AUTHOR TO COMPLETE]",
                                "corresponding_email": "pending"}}})
    assert placeholders[0]["passed"] is False


def test_known_individual_identifiers_are_blocked_without_echoing_values(tmp_path):
    path = tmp_path / "aggregate.csv"
    identifier = "private-specimen-123456"
    path.write_text(f"cohort,count\nBRCA,30\n{identifier},1\n")
    with pytest.raises(ValueError, match="Individual specimen") as error:
        no_identifiers([path], {identifier})
    assert identifier not in str(error.value)


def test_resource_versions_cannot_be_pooled():
    one = {"path": "same.csv", "sha256": "a"}
    assert _deduplicate([one, one]) == [one]
    with pytest.raises(ValueError, match="Conflicting"):
        _deduplicate([one, {**one, "sha256": "b"}])
