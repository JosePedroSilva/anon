"""Detector wrapper around Presidio + spaCy (FR-2.1–2.4, M2/M3).

Builds one ``AnalyzerEngine`` configured with both EN and IT spaCy models
plus our custom Italian recognisers. Per request we pick the language via
``langdetect`` (or honour an override), run the analyser on the flat text
of a Document, and translate Presidio's ``RecognizerResult`` records into
``Detection`` objects in the same coordinate system.

Allowlist/denylist are applied here so the rest of the pipeline never has
to know they exist:

* allowlist → drop any detection whose normalised surface form matches.
* denylist  → scan flat text for each phrase and append synthetic
  detections at score 1.0 with type ``CUSTOM``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider

from .entities import Detection
from .placeholder import _normalise  # noqa: PLC2701 — internal reuse on purpose
from .recognisers_it import (
    case_number_recogniser,
    codice_fiscale_recogniser,
    iban_it_recogniser,
)
from .stoplists import STOPLISTS_BY_LANGUAGE

# Subset of Presidio entity names we surface to the user, mapped to the
# placeholder type names used in the spec (FR-2.1).
PRESIDIO_TO_TYPE = {
    "PERSON": "PERSON",
    "ORGANIZATION": "ORG",
    "NRP": "ORG",  # nationality/religion/political — close enough for our needs
    "LOCATION": "LOC",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "IBAN_CODE": "IBAN",
    "IBAN": "IBAN",
    "CREDIT_CARD": "CREDIT_CARD",
    "DATE_TIME": "DATE_OF_BIRTH",  # narrowed by context downstream if needed
    "US_SSN": "ID_NUMBER",
    "ID_NUMBER": "ID_NUMBER",
    "URL": "URL",
    "CASE_NUMBER": "CASE_NUMBER",
}

# Presidio types we always ignore (too noisy for legal docs).
IGNORED_PRESIDIO_TYPES = frozenset({"DATE_TIME"})  # opt-in via DETECT_DATES flag

DEFAULT_CONFIDENCE = 0.6
SUPPORTED_LANGUAGES = ("en", "it")


@dataclass
class DetectorConfig:
    languages: tuple[str, ...] = SUPPORTED_LANGUAGES
    confidence_threshold: float = DEFAULT_CONFIDENCE
    allowlist: list[str] = field(default_factory=list)
    denylist: list[str] = field(default_factory=list)
    detect_dates: bool = False
    detect_money: bool = False  # FR-2.1 says off by default
    enabled_types: set[str] | None = None  # None = all known types


@lru_cache(maxsize=1)
def _build_analyzer(languages: tuple[str, ...]) -> AnalyzerEngine:
    """Construct (and cache) the Presidio analyser. Cold-start is slow
    because spaCy loads the large models; LRU keeps it to once per
    process.
    """
    spacy_models = []
    for lang in languages:
        model_name = "en_core_web_lg" if lang == "en" else "it_core_news_lg"
        spacy_models.append({"lang_code": lang, "model_name": model_name})
    config = {"nlp_engine_name": "spacy", "models": spacy_models}
    nlp_engine = NlpEngineProvider(nlp_configuration=config).create_engine()

    registry = RecognizerRegistry(supported_languages=list(languages))
    registry.load_predefined_recognizers(languages=list(languages), nlp_engine=nlp_engine)

    # Italian pattern recognisers are high-precision regexes — register
    # for every supported language so a stray codice fiscale in an
    # otherwise-English document still gets caught.
    for lang in languages:
        registry.add_recognizer(codice_fiscale_recogniser(lang))
        registry.add_recognizer(iban_it_recogniser(lang))
        registry.add_recognizer(case_number_recogniser(lang))

    return AnalyzerEngine(
        registry=registry, nlp_engine=nlp_engine, supported_languages=list(languages)
    )


def detect_language(text: str, fallback: str = "en") -> str:
    """Auto-detect language; default to ``fallback`` on empty input or
    detector failure (e.g. text too short)."""
    sample = text.strip()
    if not sample:
        return fallback
    try:
        from langdetect import LangDetectException, detect

        code = detect(sample[:4000])
    except LangDetectException:
        return fallback
    return code if code in SUPPORTED_LANGUAGES else fallback


def _filter_allowlist(detections: Iterable[Detection], allowlist: list[str]) -> list[Detection]:
    if not allowlist:
        return list(detections)
    blocked = {_normalise(a) for a in allowlist if a.strip()}
    return [d for d in detections if _normalise(d.text) not in blocked]


# spaCy NER types we apply the noise filter to. Pattern-based hits
# (IBAN, EMAIL, ID_NUMBER, CASE_NUMBER, CREDIT_CARD, URL) are
# regex-precise and shouldn't be second-guessed.
_NER_TYPES_FOR_FILTER = frozenset({"PERSON", "ORG", "LOC"})

def _is_noise(det: Detection, language: str) -> bool:
    """Return True if ``det`` looks like a spaCy NER false positive.

    Rules (only applied to PERSON/ORG/LOC — pattern hits are trusted):

    1. Surface < 2 visible chars → almost always a stray initial.
    2. Surface starts with a lowercase letter — proper nouns must be
       capitalised in EN/IT.
    3. **Every token** of the canonicalised surface is in the language's
       legal stoplist. This catches "Servizi dell'Advisor" because
       "servizi", "dell" and "advisor" are all stoplisted, while letting
       "Mario Bianchi" through (neither token is stoplisted).
    """
    if det.entity_type not in _NER_TYPES_FOR_FILTER:
        return False
    surface = det.text.strip()
    if len(surface) < 2:
        return True
    first_alpha = next((c for c in surface if c.isalpha()), "")
    if first_alpha and first_alpha.islower():
        return True
    stoplist = STOPLISTS_BY_LANGUAGE.get(language, frozenset())
    if not stoplist:
        return False
    # Tokenise on whitespace AND apostrophes BEFORE normalising — Italian
    # elisions ("dell'", "all'", "nell'") attach to the next word. If we
    # let ``_normalise`` strip the apostrophe first, "dell'Advisor"
    # collapses to "delladvisor" and stoplist matching fails.
    import re as _re
    raw_tokens = [t for t in _re.split(r"[\s'’]+", surface) if t]
    tokens = [_normalise(t) for t in raw_tokens]
    tokens = [t for t in tokens if t]
    if not tokens:
        return True
    return all(t in stoplist for t in tokens)


def _filter_noise(detections: Iterable[Detection], language: str) -> list[Detection]:
    return [d for d in detections if not _is_noise(d, language)]


def _denylist_hits(text: str, denylist: list[str]) -> list[Detection]:
    out: list[Detection] = []
    for term in denylist:
        if not term.strip():
            continue
        for m in re.finditer(re.escape(term), text):
            out.append(
                Detection(
                    entity_type="CUSTOM",
                    start=m.start(),
                    end=m.end(),
                    text=m.group(0),
                    score=1.0,
                )
            )
    return out


def _resolve_overlaps(detections: list[Detection]) -> list[Detection]:
    """Drop overlapping detections — only one redaction can cover any
    given character, otherwise the replacer applies them on top of each
    other and the last-writer-wins (see ORG "IBAN IT..." swallowing a
    high-confidence IBAN).

    Priority when spans overlap:

    1. Longer span loses to the higher-score one.
    2. Ties broken by narrower span (more specific wins).
    3. Remaining ties broken by earlier start.
    """

    def sort_key(d: Detection) -> tuple[float, int, int]:
        return (-d.score, d.end - d.start, d.start)

    ordered = sorted(detections, key=sort_key)
    accepted: list[Detection] = []
    for d in ordered:
        if any(_overlaps(d, a) for a in accepted):
            continue
        accepted.append(d)
    accepted.sort(key=lambda d: d.start)
    return accepted


def _overlaps(a: Detection, b: Detection) -> bool:
    return a.start < b.end and b.start < a.end


def detect(
    text: str,
    config: DetectorConfig | None = None,
    language: str | None = None,
) -> tuple[str, list[Detection]]:
    """Return ``(language, detections)`` for ``text``.

    Detections are filtered by confidence threshold and allowlist, with
    denylist phrases appended. Overlaps on identical spans are collapsed.
    """
    cfg = config or DetectorConfig()
    lang = language or detect_language(text)
    analyzer = _build_analyzer(cfg.languages)

    raw = analyzer.analyze(text=text, language=lang, score_threshold=cfg.confidence_threshold)

    out: list[Detection] = []
    for r in raw:
        if r.entity_type in IGNORED_PRESIDIO_TYPES and not cfg.detect_dates:
            continue
        mapped = PRESIDIO_TO_TYPE.get(r.entity_type, r.entity_type)
        if cfg.enabled_types is not None and mapped not in cfg.enabled_types:
            continue
        # Trim whitespace at the edges of the detection — spaCy sometimes
        # extends a PERSON span over a trailing newline or space, which
        # both bloats the placeholder and breaks cross-document
        # canonicalisation ("Rossi" vs "Rossi\n").
        s, e = r.start, r.end
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if e <= s:
            continue
        out.append(
            Detection(
                entity_type=mapped,
                start=s,
                end=e,
                text=text[s:e],
                score=float(r.score),
            )
        )

    out = _filter_noise(out, lang)
    out = _filter_allowlist(out, cfg.allowlist)
    out.extend(_denylist_hits(text, cfg.denylist))
    out = _resolve_overlaps(out)
    return lang, out
