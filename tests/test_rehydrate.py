"""Rehydrate placeholders, including the fuzzy-match shapes."""

from __future__ import annotations

from docshield.core.mapping_store import MappingFile
from docshield.core.rehydrate import rehydrate


def _mapping() -> MappingFile:
    return MappingFile(
        source_file="x.docx",
        language="en",
        entries=[
            {"placeholder": "[PERSON_1]", "original": "Giulia Rossi", "type": "PERSON"},
            {"placeholder": "[PERSON_10]", "original": "Mario Bianchi", "type": "PERSON"},
            {"placeholder": "[ORG_1]", "original": "ACME S.p.A.", "type": "ORG"},
        ],
    )


def test_basic_substitution() -> None:
    out = rehydrate("[PERSON_1] works at [ORG_1].", _mapping())
    assert out == "Giulia Rossi works at ACME S.p.A.."


def test_longer_placeholder_wins() -> None:
    """[PERSON_10] must not be truncated to [PERSON_1] + '0'."""
    assert rehydrate("[PERSON_10]", _mapping()) == "Mario Bianchi"


def test_case_insensitive_and_inner_whitespace() -> None:
    assert rehydrate("[ person_1 ]", _mapping()) == "Giulia Rossi"
    assert rehydrate("[Person_1]", _mapping()) == "Giulia Rossi"


def test_bare_form_without_brackets() -> None:
    assert rehydrate("As PERSON_1 noted, …", _mapping()) == "As Giulia Rossi noted, …"


def test_unknown_placeholders_are_left_alone() -> None:
    assert rehydrate("[PERSON_99] said hi.", _mapping()) == "[PERSON_99] said hi."
