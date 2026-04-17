"""Placeholder allocator: stability, idempotency, name-variant collapse."""

from __future__ import annotations

from docshield.core.placeholder import PlaceholderAllocator, canonicalise


def test_same_entity_returns_same_placeholder() -> None:
    a = PlaceholderAllocator()
    p1 = a.allocate("PERSON", "Giulia Rossi")
    p2 = a.allocate("PERSON", "Giulia Rossi")
    assert p1 == p2 == "[PERSON_1]"


def test_different_entities_get_different_placeholders() -> None:
    a = PlaceholderAllocator()
    assert a.allocate("PERSON", "Giulia Rossi") == "[PERSON_1]"
    assert a.allocate("PERSON", "Mario Bianchi") == "[PERSON_2]"
    assert a.allocate("ORG", "ACME S.p.A.") == "[ORG_1]"


def test_name_variants_collapse() -> None:
    """FR-3.3: Ms. Rossi / G. Rossi / Giulia Rossi → same placeholder."""
    a = PlaceholderAllocator()
    p = a.allocate("PERSON", "Giulia Rossi")
    assert a.allocate("PERSON", "Ms. Rossi") == p
    assert a.allocate("PERSON", "G. Rossi") == p
    assert sorted(a.aliases(p)) == ["G. Rossi", "Giulia Rossi", "Ms. Rossi"]


def test_canonicalise_strips_accents_and_punct() -> None:
    assert canonicalise("ORG", "ACME S.p.A.") == canonicalise("ORG", "acme spa")
    assert canonicalise("LOC", "Milán") == "milan"


def test_session_stability_across_documents() -> None:
    """One allocator reused across docs ⇒ shared numbering (FR-3.2)."""
    a = PlaceholderAllocator()
    a.allocate("PERSON", "Giulia Rossi")  # doc 1
    a.allocate("ORG", "ACME S.p.A.")  # doc 1
    # doc 2 sees the same name again
    assert a.allocate("PERSON", "Giulia Rossi") == "[PERSON_1]"
    assert a.allocate("ORG", "Globex") == "[ORG_2]"


def test_entries_records_first_seen_form() -> None:
    a = PlaceholderAllocator()
    a.allocate("PERSON", "Giulia Rossi")
    a.allocate("PERSON", "Ms. Rossi")
    [entry] = a.entries()
    assert entry.original == "Giulia Rossi"
    assert entry.placeholder == "[PERSON_1]"
