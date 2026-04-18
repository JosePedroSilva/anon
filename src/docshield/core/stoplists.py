"""Built-in stoplists of common false positives.

spaCy's ``it_core_news_lg`` is weak on legal Italian: it tags ordinary
capitalised legal terms ("Parti", "Stretto Familiare", "Servizi
dell'Advisor", "Abbandono") as LOC or ORG because Italian capitalisation
in contracts looks similar to proper-noun usage in news text (the
training corpus). We filter these out *before* showing the preview so
the user isn't drowning in noise.

Membership is checked against the canonicalised surface form (lowercase,
accent-stripped, punctuation-removed) to catch trivial variants.
Anything in here is *never* shown as a detection — if a real client is
genuinely called "Parti S.r.l." we'll miss them, but that's a much
rarer failure than the current over-detection.
"""

from __future__ import annotations

# Italian legal/contract words spaCy NER routinely mis-tags. Stored as
# individual word tokens (not phrases) so the detector can drop any
# detection whose tokens are *all* in this set — that catches multi-word
# false positives like "Servizi dell'Advisor" or "Stretto Familiare"
# without needing every phrase enumerated.
IT_LEGAL_STOPLIST = frozenset(
    {
        # parties / roles
        "parti", "parte", "cliente", "clienti", "advisor", "consulente",
        "consulenti", "controparte", "incaricato", "mandatario", "fornitore",
        "appaltatore", "beneficiario", "intermediario", "incaricati",
        "rappresentante", "rappresentanti",
        # family / relationships
        "stretto", "stretti", "familiare", "familiari", "affine", "affini",
        "coniuge", "convivente", "erede", "eredi", "parente", "parenti",
        # legal concepts
        "abbandono", "rinuncia", "risoluzione", "recesso", "decadenza",
        "scioglimento", "esclusione", "cessazione", "estinzione",
        "inadempimento", "adempimento", "obbligazione", "obbligazioni",
        "responsabilita", "garanzia", "garanzie", "manleva",
        # services / objects
        "servizi", "servizio", "prestazione", "prestazioni", "incarico",
        "mandato", "consulenza", "consulenze", "advisory",
        "contratto", "contrato", "accordo",
        # common nouns frequently capitalised in contracts
        "premesse", "premessa", "considerato", "considerate", "definizioni",
        "allegato", "allegati", "clausola", "clausole", "articolo", "articoli",
        "comma", "commi", "paragrafo", "paragrafi", "oggetto", "scopo",
        # dates/times often capitalised
        "data", "termine", "scadenza", "decorrenza", "durata",
        # short determiners / particles
        "il", "la", "i", "le", "lo", "gli", "un", "una", "uno",
        "di", "da", "del", "della", "delle", "dei", "dell",
        "in", "a", "e", "o", "su", "con", "per", "tra", "fra",
        "nel", "nella", "nelle", "nei", "negli", "nell",
        "sul", "sulla", "sulle", "sui", "sugli", "sull",
        "al", "alla", "alle", "ai", "agli", "all",
        "dal", "dalla", "dalle", "dai", "dagli", "dall",
        "col", "colla", "colle", "coi", "cogli", "coll",
    }
)

# English equivalents for legal docs.
EN_LEGAL_STOPLIST = frozenset(
    {
        "parties", "party", "client", "clients", "counsel", "advisor",
        "advisors", "agreement", "contract", "exhibit", "exhibits",
        "schedule", "schedules", "annex", "annexes", "appendix",
        "section", "sections", "clause", "clauses", "article", "articles",
        "paragraph", "paragraphs", "recitals", "definitions",
        "buyer", "seller", "lessor", "lessee", "licensor", "licensee",
        # determiners / common particles
        "the", "a", "an", "of", "and", "or", "in", "on", "at", "to", "for",
        "by", "with", "as", "is",
    }
)


STOPLISTS_BY_LANGUAGE = {
    "it": IT_LEGAL_STOPLIST,
    "en": EN_LEGAL_STOPLIST,
}
