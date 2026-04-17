"""Re-hydrate placeholders in an LLM response back to original text.

The straightforward path is a regex-driven substitution: ``[PERSON_1]`` →
``"Giulia Rossi"``. FR-5.5 asks for fuzzy matches because LLMs sometimes
mangle placeholders by adding zero-width chars, lower-casing the type, or
stripping the brackets. We accept these deviations:

* whitespace inside brackets: ``[ PERSON_1 ]``
* mixed case: ``[person_1]``, ``[Person_1]``
* missing brackets but unique-enough form: ``PERSON_1`` standalone

Anything else we leave alone — silent miscorrection is worse than visible
breakage.
"""

from __future__ import annotations

import re

from .mapping_store import MappingFile


def rehydrate(text: str, mapping: MappingFile) -> str:
    by_canonical: dict[str, str] = {}
    for e in mapping.entries:
        ph = e["placeholder"].strip("[] ").lower()
        by_canonical[ph] = e["original"]

    if not by_canonical:
        return text

    # Build one alternation that catches all known placeholders in any of
    # the accepted shapes. We sort longest-key-first so PERSON_10 wins over
    # PERSON_1 when both exist.
    keys = sorted(by_canonical.keys(), key=len, reverse=True)
    alternation = "|".join(re.escape(k) for k in keys)
    pattern = re.compile(rf"\[\s*({alternation})\s*\]|\b({alternation})\b", re.IGNORECASE)

    def _repl(m: re.Match[str]) -> str:
        hit = (m.group(1) or m.group(2) or "").lower()
        return by_canonical.get(hit, m.group(0))

    return pattern.sub(_repl, text)
