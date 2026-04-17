# DocShield — Requirements (MVP)

**Version:** 0.1 (MVP scope)
**Date:** 2026-04-17
**Owner:** Jose
**Primary user:** Lawyer preparing `.docx` files for use with an LLM without leaking client-confidential data.

---

## 1. Problem statement

Lawyers routinely need to feed documents (contracts, briefs, correspondence, deposition transcripts) into LLMs for summarisation, drafting help, and research. Doing so risks leaking privileged and client-identifying information to a third-party model provider. Existing redaction tools are either enterprise-grade (expensive, admin-install, cloud-based) or generic regex scripts (miss names, break formatting).

**DocShield** is a lightweight, offline, cross-platform desktop tool that:

1. Detects Personally Identifiable Information (PII) and other sensitive entities in Word documents.
2. Replaces them with stable, reversible placeholders (e.g. `[PERSON_1]`, `[ORG_2]`).
3. Produces an anonymised `.docx` that preserves original formatting.
4. Stores the mapping encrypted locally, so the user can **re-hydrate** the LLM's response back to real names when needed.

---

## 2. Target user

| | |
|---|---|
| **Persona** | Solo or small-firm lawyer, moderate tech comfort, not a developer. |
| **Environment** | Personal or work laptop, **no admin rights**. Windows, macOS, or Linux. |
| **Data sensitivity** | Attorney–client privileged. Must never leave the device. |
| **Languages** | English and Italian documents (MVP). |
| **Volume** | 1–20 documents per session, typical size 1–50 pages. |

---

## 3. Goals and non-goals

### 3.1 Goals (MVP)

- One-click install with no admin rights (portable single-file executable).
- Fully offline operation: no network calls at runtime.
- Accurate detection of common PII types in EN + IT.
- Reversible anonymisation with encrypted mapping.
- Preserve `.docx` formatting (styles, tables, headers, footers, lists, bold/italic).
- Desktop GUI: drag-and-drop, preview, accept/override detections.
- Audit log of every anonymisation run.

### 3.2 Non-goals (MVP)

- Cloud sync, multi-user collaboration, or SaaS deployment.
- PDF, email, or image (OCR) input — `.docx` only for MVP.
- Legal-jurisdiction-specific compliance certifications (GDPR DPIA, SOC 2, etc.) — documented but not certified.
- Automatic LLM integration — the user copies the anonymised text out and pastes the LLM response back in for re-hydration.
- Handling of tracked changes and comments is best-effort in MVP; see §11.

---

## 4. Functional requirements

### 4.1 Input

- **FR-1.1** Accept `.docx` files via drag-and-drop onto the GUI window.
- **FR-1.2** Accept `.docx` via a "Choose file…" button.
- **FR-1.3** Support batch input: multiple files dropped together.
- **FR-1.4** Reject unsupported file types with a clear error message.
- **FR-1.5** File size limit: 50 MB per document (MVP).

### 4.2 Detection

- **FR-2.1** Detect the following entity types out of the box:
  - `PERSON` — full names
  - `ORG` — organisations, law firms, companies
  - `LOC` / `ADDRESS` — addresses, cities, countries
  - `EMAIL` — email addresses
  - `PHONE` — phone numbers (international formats)
  - `IBAN` — bank account numbers (Italian IBANs especially)
  - `CREDIT_CARD`
  - `DATE_OF_BIRTH`
  - `ID_NUMBER` — national IDs (IT *codice fiscale*, US SSN, generic patterns)
  - `CASE_NUMBER` — docket/case reference patterns (configurable)
  - `URL`
  - `MONEY` (optional flag; off by default)
- **FR-2.2** Support a **user-editable allowlist** (terms that should never be redacted, e.g. "Supreme Court") and **denylist** (custom terms to always redact, e.g. firm-specific client codes).
- **FR-2.3** Language auto-detection per document (EN / IT), with manual override.
- **FR-2.4** Confidence threshold configurable in settings (default 0.6).

### 4.3 Anonymisation

- **FR-3.1** Replace each detected entity with a **stable placeholder** of the form `[TYPE_N]` (e.g. `[PERSON_1]`, `[ORG_3]`).
- **FR-3.2** Identical entity mentions must map to the **same placeholder** throughout the document and across documents in the same session.
- **FR-3.3** Name variants (e.g. "Giulia Rossi", "Ms. Rossi", "G. Rossi") should resolve to the same placeholder where confidence permits; otherwise treated as distinct with a warning.
- **FR-3.4** Output is written as a new `.docx` alongside the original (`<name>_anon.docx`) — never overwrite the source.
- **FR-3.5** Preserve all formatting: paragraph styles, runs (bold/italic/underline), tables, lists, headers/footers, footnotes.
- **FR-3.6** Replacement must touch only text inside `<w:t>` runs of the underlying OOXML. Styles and structural elements must not be modified.

### 4.4 Preview & review

- **FR-4.1** Before writing output, show a preview listing every detected entity, its type, and proposed placeholder.
- **FR-4.2** User can uncheck individual detections (skip replacement) or add custom replacements for missed items.
- **FR-4.3** Side-by-side before/after of the text for spot-checking.
- **FR-4.4** User confirms with "Anonymise" button; can cancel without changes.

### 4.5 Mapping store & re-hydration

- **FR-5.1** On each run, save a mapping file `<name>_mapping.dsm` (DocShield Mapping) containing placeholder→original pairs.
- **FR-5.2** The mapping file must be **encrypted at rest** with AES-256 (via `cryptography.fernet`), key derived from a user-supplied password using PBKDF2 (≥ 200k iterations) or Argon2id.
- **FR-5.3** User sets a master password on first run; password is stored only as a salted hash for verification.
- **FR-5.4** Provide a **Rehydrate** function: paste LLM output text, select the mapping file, enter password, receive text with real names restored.
- **FR-5.5** Rehydration must handle partial/fuzzy matches (placeholder could appear with surrounding punctuation or formatting in LLM output).

### 4.6 Audit log

- **FR-6.1** Append a local log entry per run: timestamp, source filename, number of entities by type, output path, mapping path, user name.
- **FR-6.2** Log stored as append-only JSON lines in the app data folder.
- **FR-6.3** Viewable from a "History" tab in the GUI.

### 4.7 Configuration

- **FR-7.1** Settings screen: allowlist/denylist editing, confidence threshold, default output folder, language preference, which entity types to detect.
- **FR-7.2** Settings persist in a user-writable config directory (`%APPDATA%` / `~/.config` / `~/Library/Application Support`).

---

## 5. Non-functional requirements

### 5.1 Privacy & security

- **NFR-1.1** Zero network traffic at runtime. No telemetry. The executable must function in fully airgapped environments.
- **NFR-1.2** No data written outside user-scoped directories.
- **NFR-1.3** Mapping files encrypted; master password never stored in plaintext.
- **NFR-1.4** Temporary files (if any) zeroed and deleted on exit.
- **NFR-1.5** Dependencies vetted; no code pulled at runtime.

### 5.2 Performance

- **NFR-2.1** Cold start ≤ 10 seconds (acceptable because NER model is large).
- **NFR-2.2** Process a 20-page document in ≤ 15 seconds on a typical 4-core laptop.
- **NFR-2.3** Memory footprint ≤ 1.5 GB.

### 5.3 Installability

- **NFR-3.1** Single portable executable per OS; no installer, no admin rights.
- **NFR-3.2** Size target ≤ 400 MB per bundle (spaCy + Presidio + Qt can push this; acceptable up to 600 MB).
- **NFR-3.3** First run unpacks to a user-writable cache directory.

### 5.4 Reliability

- **NFR-4.1** Malformed `.docx` must produce a clear error, never crash.
- **NFR-4.2** All file writes are atomic (write-to-temp-then-rename).
- **NFR-4.3** Unit test coverage ≥ 80% on core anonymisation logic.

### 5.5 Usability

- **NFR-5.1** No command-line interaction required for primary workflow.
- **NFR-5.2** All error messages in plain English (no stack traces in UI).
- **NFR-5.3** Built-in first-run tutorial (≤ 5 slides or tooltips).

### 5.6 Compliance posture

- **NFR-6.1** Design aligned with GDPR principles (data minimisation, local processing). No DPIA claim for MVP.
- **NFR-6.2** All third-party dependencies must be OSI-approved permissive licences (MIT, Apache-2.0, BSD). Document in `THIRD_PARTY_LICENSES.md`.

---

## 6. Technology stack (recommended)

| Layer | Choice | Rationale |
|---|---|---|
| Language | **Python 3.11+** | Rich NLP ecosystem; fast enough for this workload. |
| DOCX I/O | **`python-docx`** + direct `lxml` on OOXML | `python-docx` for simple runs; `lxml` fallback for tables/headers/footnotes to preserve everything. |
| PII detection | **Microsoft Presidio** (`presidio-analyzer`, `presidio-anonymizer`) | Purpose-built for PII, extensible, Apache-2.0. |
| NER backbone | **spaCy** models `en_core_web_lg` + `it_core_news_lg` | Best free models for EN + IT. Ship both. |
| Custom recognisers | Presidio `PatternRecognizer` | For *codice fiscale*, IBAN IT, case/docket numbers, firm-specific patterns. |
| GUI | **PySide6** (Qt for Python, LGPL) | Native look, cross-platform, mature. Tkinter is a fallback if bundle size becomes critical. |
| Encryption | **`cryptography`** (Fernet, PBKDF2) or **Argon2** via `argon2-cffi` | Industry-standard. |
| Packaging | **PyInstaller** `--onefile --noconsole` per OS | Produces portable binaries, no admin. |
| Logging | stdlib `logging` + JSON lines | No external service. |
| Testing | `pytest`, `pytest-cov`, `hypothesis` for property tests | Standard. |
| Lint/format | `ruff`, `black`, `mypy --strict` | Quality gate. |

### 6.1 Alternative stacks (if blocked)

- **BeeWare Briefcase** instead of PyInstaller for a more native packaging story.
- **Transformers.js/ONNX-runtime** + a distilled NER model for smaller bundle, if size becomes critical.
- **Flet** or **Toga** if PySide6 feels too heavy.

---

## 7. Architecture

```
┌─────────────────────────────────────────────┐
│                   GUI (PySide6)             │
│  Drag-drop │ Preview │ Settings │ History   │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│          Orchestrator (controller)          │
└────┬────────────┬──────────────┬────────────┘
     │            │              │
┌────▼─────┐ ┌────▼──────┐ ┌─────▼─────────┐
│ DOCX I/O │ │ Detector  │ │ Mapping Store │
│ (docx +  │ │(Presidio+ │ │  (Fernet /    │
│  lxml)   │ │  spaCy)   │ │   Argon2id)   │
└──────────┘ └───────────┘ └───────────────┘
```

### 7.1 Processing pipeline

1. **Load** `.docx` → extract ordered list of text runs with a reference back to the XML node.
2. **Detect** PII across the concatenated text, keeping a char-offset map to runs.
3. **Resolve** co-references and assign stable placeholders.
4. **Preview** to user → user approves / edits.
5. **Write** placeholders back into the XML runs preserving style.
6. **Save** anonymised `.docx` + encrypted mapping + log entry.

---

## 8. User flows

### 8.1 First run

1. Launch app → set master password → confirm password → password hash stored in config.
2. App offers a 30-second tour.

### 8.2 Anonymise a document

1. User drags `Contract_ACME.docx` onto the window.
2. App detects language (IT), runs pipeline, shows preview with 42 detections grouped by type.
3. User unticks 2 false positives, adds 1 custom term ("Project Falcon").
4. User clicks **Anonymise**.
5. App writes `Contract_ACME_anon.docx` and `Contract_ACME_mapping.dsm` to the chosen output folder.
6. History tab records the run.

### 8.3 Rehydrate LLM output

1. User pastes the LLM's redacted response into the **Rehydrate** tab.
2. User selects `Contract_ACME_mapping.dsm`, enters password.
3. App outputs the de-anonymised text, copyable to clipboard.

---

## 9. Data model

### 9.1 Mapping file (`.dsm`)

Encrypted JSON:

```json
{
  "version": 1,
  "created_at": "2026-04-17T12:00:00Z",
  "source_file": "Contract_ACME.docx",
  "language": "it",
  "entries": [
    {"placeholder": "[PERSON_1]", "original": "Giulia Rossi", "type": "PERSON"},
    {"placeholder": "[ORG_1]",    "original": "ACME S.p.A.",  "type": "ORG"}
  ]
}
```

### 9.2 Audit log entry

```json
{"ts":"2026-04-17T12:00:05Z","file":"Contract_ACME.docx","entities":{"PERSON":7,"ORG":3,"EMAIL":2},"output":".../Contract_ACME_anon.docx","mapping":".../Contract_ACME_mapping.dsm"}
```

---

## 10. Testing strategy

- **Unit tests** for: detector wrappers, placeholder allocator (idempotency + cross-doc stability), DOCX run-level replacer, encryption round-trip, rehydrator.
- **Golden-file tests**: a corpus of synthetic EN + IT docs with known entities; CI asserts exact anonymised output.
- **Property tests** (`hypothesis`): replacement must never change XML structure outside `<w:t>` nodes.
- **Manual test set**: 10 representative real-world-shaped synthetic contracts supplied by Jose's friend (anonymised already, for fixtures).
- **Security review checklist** before v1.0: no network calls (verify with packet capture), password handling, mapping encryption correctness.

---

## 11. Known limitations (MVP)

- Comments, tracked changes, and embedded objects (images with text, OLE) are not anonymised in MVP; they are flagged and the user is warned.
- Scanned / image-based PDFs inside `.docx` require OCR (out of scope).
- Homonyms (two different people with the same name) may collapse into a single placeholder; flagged in preview.
- Italian fiscal codes containing embedded DOB are detected but not further parsed.

---

## 12. Milestones

| # | Milestone | Est. effort |
|---|---|---|
| M0 | Repo scaffold, CI (lint/type/test), licence headers | 0.5 day |
| M1 | DOCX round-trip with no changes (parse → write identical file) | 1 day |
| M2 | Presidio + spaCy EN pipeline; CLI-only anonymisation | 2 days |
| M3 | Italian language support + custom recognisers (codice fiscale, IT IBAN) | 1 day |
| M4 | Stable placeholder allocator + encrypted mapping store | 1.5 days |
| M5 | PySide6 GUI (drag-drop, preview, settings, history) | 2.5 days |
| M6 | Rehydrate tab | 0.5 day |
| M7 | PyInstaller bundles for Win/macOS/Linux + smoke tests | 1 day |
| M8 | User documentation + first-run tour | 0.5 day |
| **Total MVP** | | **~10 working days** |

---

## 13. Open questions

1. Should the master password unlock the whole app on launch, or only decrypt mapping files on demand? *(Default: on-demand, to avoid blocking first-use.)*
2. Should we ship a portable "USB-stick mode" that keeps config + logs next to the executable? Useful for lawyers on shared machines.
3. Do we need a "redact in place with black boxes" output for court filings, in addition to placeholder substitution? Possibly v1.1.
4. Should we integrate optional local-LLM (e.g. llama.cpp) de-identification as a second pass? Probably v2.
5. Licensing model: open-source MIT, or source-available? Affects contribution model.

---

## 14. Suggested repository layout

```
docshield/
├── pyproject.toml
├── README.md
├── LICENSE
├── THIRD_PARTY_LICENSES.md
├── requirements.md                # this file
├── src/docshield/
│   ├── __init__.py
│   ├── app.py                     # GUI entry point
│   ├── cli.py                     # optional CLI
│   ├── core/
│   │   ├── docx_io.py
│   │   ├── detector.py
│   │   ├── recognisers_it.py
│   │   ├── placeholder.py
│   │   ├── mapping_store.py
│   │   └── rehydrate.py
│   ├── gui/
│   │   ├── main_window.py
│   │   ├── preview_dialog.py
│   │   └── settings_dialog.py
│   ├── config.py
│   └── logging_setup.py
├── tests/
│   ├── fixtures/
│   ├── test_docx_io.py
│   ├── test_detector.py
│   ├── test_placeholder.py
│   ├── test_mapping_store.py
│   └── test_rehydrate.py
└── packaging/
    ├── build_windows.ps1
    ├── build_macos.sh
    └── build_linux.sh
```

---

## 15. Acceptance criteria for MVP sign-off

- [ ] Installs on Windows, macOS, and Linux without admin rights.
- [ ] Runs fully offline (verified by packet capture).
- [ ] Anonymises a 20-page EN contract and a 20-page IT contract with ≥ 95% PERSON / ORG / EMAIL recall on the test corpus.
- [ ] Round-trip: open anonymised `.docx` in Word → formatting identical to original.
- [ ] Rehydrate restores every placeholder in a copied-back LLM response.
- [ ] Mapping file cannot be decrypted without the master password.
- [ ] No data written outside user directories; no network traffic during run.
- [ ] First-time user completes the "anonymise → copy → paste LLM response → rehydrate" cycle in < 5 minutes without reading docs.