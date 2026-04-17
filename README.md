# DocShield

Offline `.docx` PII anonymiser for lawyers preparing documents for LLMs.

Detects PII (names, organisations, addresses, IBANs, codice fiscale, etc.) in
English and Italian Word documents, replaces them with stable placeholders
(`[PERSON_1]`, `[ORG_2]`, …), and stores an encrypted mapping so the LLM's
response can be re-hydrated back to real names.

See `SPEC.md` for the full requirements.

## Status

MVP under construction. See `SPEC.md` §12 for milestones.

## Quick start (dev)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_lg
python -m spacy download it_core_news_lg
pytest
```

## License

MIT. See `LICENSE`.
