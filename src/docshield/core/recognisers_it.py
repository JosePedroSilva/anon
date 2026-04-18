"""Italian-specific custom recognisers (FR-2.1, M3).

Presidio ships a generic IBAN recogniser and an SSN one, but no
*codice fiscale* and no docket-number patterns. We register them here so
the analyser picks them up when the document is detected as Italian (or
always — they're high-precision regexes).

The IT IBAN recogniser exists in Presidio but we re-register a tightened
variant that requires the leading ``IT`` to keep noise down on EN docs.
"""

from __future__ import annotations

import re

from presidio_analyzer import Pattern, PatternRecognizer

# Codice fiscale: 16 alphanumerics with a fixed letter/digit pattern.
# https://en.wikipedia.org/wiki/Italian_fiscal_code
_CF = Pattern(
    name="codice_fiscale",
    regex=r"\b[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]\b",
    score=0.85,
)

# Italian IBAN: country (IT), 2 check digits, 1 CIN letter, 5 ABI, 5 CAB,
# 12 alphanumeric account = 27 chars total. Allow optional spaces.
_IBAN_IT = Pattern(
    name="iban_it",
    regex=r"\bIT[0-9]{2}[A-Z][0-9]{10}[A-Z0-9]{12}\b",
    score=0.9,
)

# Generic case/docket numbers in IT/EN courts. Examples: "R.G. 1234/2024",
# "Case No. 21-cv-04567", "N. 567/2023".
#
# Two precision rules baked in to stop the v1 regex from tagging every
# Italian ``nel`` / ``nella`` / ``non`` (Presidio compiles patterns with
# ``re.IGNORECASE``, so ``N`` matched lowercase ``n`` as well):
#
# 1. Abbreviation markers (``N.``, ``Num.``) require the trailing dot.
# 2. The marker MUST be followed by at least one digit. Pure-letter
#    bodies are no longer accepted.
_CASE = Pattern(
    name="case_number",
    regex=(
        r"\b(?:"
        r"R\.\s?G\.\s+\d+(?:[\-/]\d{2,4})?"          # R.G. 1234/2024
        r"|N(?:um)?\.\s*\d+(?:[\-/]\d{2,4})?"        # N. 567/2023, Num. 12
        r"|Case\s+No\.?\s*[A-Za-z0-9\-]*\d[A-Za-z0-9\-]*(?:[\-/]\d{2,4})?"
        r"|Docket\s+No\.?\s*[A-Za-z0-9\-]*\d[A-Za-z0-9\-]*(?:[\-/]\d{2,4})?"
        r")\b"
    ),
    score=0.85,
)


def codice_fiscale_recogniser(language: str) -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="ID_NUMBER",
        supported_language=language,
        patterns=[_CF],
        context=["codice", "fiscale", "cf"],
    )


def iban_it_recogniser(language: str) -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="IBAN",
        supported_language=language,
        patterns=[_IBAN_IT],
        context=["iban", "conto", "bancario"],
    )


def case_number_recogniser(language: str) -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="CASE_NUMBER",
        supported_language=language,
        patterns=[_CASE],
        context=["case", "docket", "ruolo", "causa", "procedimento"],
    )


# Sanity tests for the regexes themselves (used by test_detector.py).
def _self_check() -> None:  # pragma: no cover - dev helper
    flags = re.IGNORECASE  # match Presidio's compile flags
    assert re.fullmatch(_CF.regex, "BNCMRA80A01F205X")
    assert re.fullmatch(_IBAN_IT.regex, "IT60X0542811101000000123456")
    assert re.search(_CASE.regex, "R.G. 1234/2024", flags)
    assert re.search(_CASE.regex, "Case No. 21-cv-04567", flags)
    assert re.search(_CASE.regex, "N. 567/2023", flags)
    # Negatives — these are what the v1 regex got wrong.
    for word in ("nel", "nella", "nei", "non", "novembre", "natura"):
        assert not re.search(_CASE.regex, word, flags), word
