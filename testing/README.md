# DocShield — manual test fixtures

Generate the `.docx` files:

```
.venv/bin/python testing/generate_fixtures.py
```

Then launch the GUI:

```
PYTHONPATH=src .venv/bin/python -m docshield.app
```

## Suggested test order

| # | File | What it exercises |
|---|---|---|
| 01 | `01_simple_english.docx` | Baseline: PERSON, EMAIL, ORG, PHONE in plain EN |
| 02 | `02_italian_contract.docx` | IT language path: codice fiscale, IT IBAN, case number |
| 03 | `03_formatted_runs.docx` | Multi-run replacement (name split across bold runs) |
| 04 | `04_with_table.docx` | Table cells; headers must survive unchanged |
| 05 | `05_repeated_mentions.docx` | Name-variant collapse: "Giulia Rossi" / "Ms. Rossi" / "G. Rossi" → one `[PERSON_N]` |
| 06 | `06_allow_deny_candidates.docx` | Settings: add "Supreme Court" to allowlist, "Project Falcon" to denylist, re-run |
| 07 | `07a_batch_part1.docx` + `07b_batch_part2.docx` | Drop both at once; same names keep the same placeholders across files |

## What to check on each anonymised output

* Open `<name>_anon.docx` in Word/Pages — formatting (bold, table grid, paragraph styles) should be identical to the source.
* Placeholders are `[TYPE_N]` form, numbering stable.
* A `<name>_mapping.dsm` sits next to each output. Encrypted — opening with the wrong password should error cleanly in the Rehydrate tab.

## Rehydrate round-trip

For `01_simple_english.docx`, after anonymising, paste into the Rehydrate tab:

```
[PERSON_1] (reachable at [EMAIL_1]) signed on behalf of [ORG_1].
The case is handled by [PERSON_2] at [EMAIL_2].
```

With the correct password, original names + emails come back. Wrong password → "invalid password or corrupt file".
