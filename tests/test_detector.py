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
