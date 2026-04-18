"""Detector smoke tests. Hit Presidio + spaCy for real, no mocking.

These tests are slow on first run because the spaCy models are ~500 MB each
and have to load into memory. The ``_build_analyzer`` cache makes
subsequent calls cheap.
"""

from __future__ import annotations

import pytest

from docshield.core import detector

# Skip the whole module if the large models aren't installed locally.
spacy = pytest.importorskip("spacy")
for _model in ("en_core_web_lg", "it_core_news_lg"):
    if not spacy.util.is_package(_model):
        pytest.skip(f"spaCy model {_model} not installed", allow_module_level=True)


def test_language_autodetect_english() -> None:
    assert detector.detect_language("This is a contract between ACME and Globex.") == "en"


def test_language_autodetect_italian() -> None:
    assert detector.detect_language("Il sig. Mario Bianchi risiede a Milano.") == "it"


def test_english_pii_detection() -> None:
    text = "Please contact Giulia Rossi at giulia@example.com or +39 02 1234 5678."
    lang, dets = detector.detect(text, language="en")
    assert lang == "en"
    types = {d.entity_type for d in dets}
    assert "EMAIL" in types
    assert "PERSON" in types


def test_italian_codice_fiscale_and_iban() -> None:
    text = (
        "Codice fiscale: BNCMRA80A01F205X. "
        "IBAN IT60X0542811101000000123456 intestato a Mario Bianchi."
    )
    lang, dets = detector.detect(text, language="it")
    assert lang == "it"
    types = {d.entity_type for d in dets}
    assert "ID_NUMBER" in types  # codice fiscale
    assert "IBAN" in types


def test_allowlist_drops_matches() -> None:
    text = "Filed at the Supreme Court by Giulia Rossi."
    cfg = detector.DetectorConfig(allowlist=["Supreme Court"])
    _, dets = detector.detect(text, config=cfg, language="en")
    surfaces = {d.text for d in dets}
    assert "Supreme Court" not in surfaces


def test_denylist_adds_custom_hits() -> None:
    text = "Project Falcon launches Q3."
    cfg = detector.DetectorConfig(denylist=["Project Falcon"])
    _, dets = detector.detect(text, config=cfg, language="en")
    custom = [d for d in dets if d.entity_type == "CUSTOM"]
    assert custom and custom[0].text == "Project Falcon"


def test_case_number_does_not_eat_italian_words() -> None:
    """Regression: v1 regex tagged every Italian ``nel``/``nella``/``non``
    as CASE_NUMBER because Presidio compiles patterns case-insensitively
    and the marker accepted bare ``N`` followed by any letters.
    """
    text = (
        "Nella riunione del 10 novembre, non sono state discusse le nuove "
        "negoziazioni nei termini previsti dalla normativa."
    )
    _, dets = detector.detect(text, language="it")
    case_hits = [d for d in dets if d.entity_type == "CASE_NUMBER"]
    assert case_hits == []


def test_case_number_still_matches_real_references() -> None:
    text = "Procedimento R.G. 4567/2024 e nota N. 12/2023; Case No. 21-cv-04567."
    _, dets = detector.detect(text, language="en")
    surfaces = {d.text for d in dets if d.entity_type == "CASE_NUMBER"}
    assert any("4567/2024" in s for s in surfaces)
    assert any("21-cv-04567" in s for s in surfaces)


def test_noise_filter_drops_italian_legal_terms() -> None:
    """spaCy's IT model tags 'Parti', 'Servizi dell'Advisor', 'Stretto
    Familiare', 'Abbandono' as LOC/ORG. The legal stoplist should
    suppress them so the preview isn't drowned in noise.
    """
    text = (
        "Le Parti convengono che i Servizi dell'Advisor saranno prestati "
        "secondo la normativa. Stretto Familiare e Abbandono sono definiti "
        "nelle Premesse."
    )
    _, dets = detector.detect(text, language="it")
    surfaces = {d.text for d in dets}
    for noise in ("Parti", "Servizi dell'Advisor", "Stretto Familiare", "Abbandono", "Premesse"):
        assert noise not in surfaces, f"expected {noise!r} to be filtered"


def test_noise_filter_drops_single_letter_hits() -> None:
    """Single-letter LOC hits ('F', 'A') from spaCy are always noise."""
    text = "Visto F e A. Mario Bianchi è il rappresentante."
    _, dets = detector.detect(text, language="it")
    short = [d for d in dets if len(d.text.strip()) <= 1]
    assert short == []


def test_noise_filter_keeps_real_proper_nouns() -> None:
    text = "Mario Bianchi lavora per Globex S.r.l. a Milano."
    _, dets = detector.detect(text, language="it")
    surfaces = {d.text for d in dets}
    # The real names must still come through.
    assert "Mario Bianchi" in surfaces or any("Mario" in s for s in surfaces)
