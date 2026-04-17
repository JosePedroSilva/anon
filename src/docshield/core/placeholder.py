"""Stable placeholder allocator (FR-3.1, FR-3.2, FR-3.3).

For each ``(type, original)`` pair seen, hand out a placeholder of the form
``[TYPE_N]`` where ``N`` is a monotonically increasing index per type.
Subsequent requests for the same pair return the same placeholder, and the
allocator is intentionally session-scoped so the same name in two
documents in one batch maps to one placeholder.

Name-variant resolution (FR-3.3) is handled by ``canonicalise``: PERSON-type
mentions are reduced to a normalised key so "Giulia Rossi", "Ms. Rossi",
and "G. Rossi" collapse onto the same placeholder. Other types compare
case-insensitively after stripping punctuation.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

# Honorifics we strip when canonicalising person names. Kept short on
# purpose — false positives here can collapse two distinct people into one
# placeholder, which is worse than missing a co-reference.
_HONORIFICS = {
    "mr", "mrs", "ms", "miss", "dr", "prof", "sir", "madam",
    "sig", "sigg", "sigra", "sigrina", "dott", "ing", "avv", "on",
}

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _normalise(s: str) -> str:
    s = _strip_accents(s).lower()
    # Drop punctuation entirely so "S.p.A." → "spa", not "s p a".
    s = _PUNCT_RE.sub("", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def canonicalise(entity_type: str, text: str) -> str:
    """Map a surface form to a key for de-duplication.

    For ``PERSON``: strip honorifics and initials, keep the surname-bearing
    tokens. ``"Ms. Giulia Rossi"`` and ``"G. Rossi"`` both reduce to
    ``"rossi"`` — crude but correct in the common case. Edge cases
    (homonyms, two-token surnames) are flagged as warnings by the caller.

    For everything else: lowercase + accent-strip + collapse whitespace.
    """
    if entity_type == "PERSON":
        tokens = [t for t in _normalise(text).split() if t and t not in _HONORIFICS]
        # drop single-letter initials like "g"
        tokens = [t for t in tokens if len(t) > 1]
        if not tokens:
            return _normalise(text)
        # surname is usually the last meaningful token in EN/IT
        return tokens[-1]
    return _normalise(text)


@dataclass
class PlaceholderEntry:
    placeholder: str
    original: str
    entity_type: str


@dataclass
class PlaceholderAllocator:
    """Session-scoped allocator. Reuse one instance for a batch run."""

    counters: dict[str, int] = field(default_factory=dict)
    # canonical key → placeholder
    _by_key: dict[tuple[str, str], str] = field(default_factory=dict)
    # placeholder → entry (preserves first-seen original surface form)
    _by_placeholder: dict[str, PlaceholderEntry] = field(default_factory=dict)
    # alternates we've seen for the same placeholder, for the audit log
    _aliases: dict[str, set[str]] = field(default_factory=dict)

    def allocate(self, entity_type: str, original: str) -> str:
        key = (entity_type, canonicalise(entity_type, original))
        existing = self._by_key.get(key)
        if existing is not None:
            self._aliases.setdefault(existing, set()).add(original)
            return existing
        self.counters[entity_type] = self.counters.get(entity_type, 0) + 1
        placeholder = f"[{entity_type}_{self.counters[entity_type]}]"
        self._by_key[key] = placeholder
        self._by_placeholder[placeholder] = PlaceholderEntry(
            placeholder=placeholder, original=original, entity_type=entity_type
        )
        self._aliases[placeholder] = {original}
        return placeholder

    def entries(self) -> list[PlaceholderEntry]:
        return list(self._by_placeholder.values())

    def aliases(self, placeholder: str) -> list[str]:
        return sorted(self._aliases.get(placeholder, set()))

    def extend(self, items: Iterable[tuple[str, str]]) -> list[str]:
        return [self.allocate(t, o) for t, o in items]
