# HL7 v2 Infectious Disease Parser

[![tests](https://github.com/dquint32/hl7-infectious-disease-parser/actions/workflows/tests.yml/badge.svg)](https://github.com/dquint32/hl7-infectious-disease-parser/actions/workflows/tests.yml)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![pydantic](https://img.shields.io/badge/pydantic-v2-e92063)

**Live demo:** https://dquint32.github.io/hl7-infectious-disease-parser/

## Project Overview
A parsing engine for **HL7 v2.x ORU^R01 (Observation Result)** messages used in infectious-disease
lab reporting (COVID-19, Influenza A/B, RSV, HIV, TB, Hepatitis A/B/C). It turns raw pipe-delimited
messages into typed, validated records. For every problem it finds, it reports the exact HL7
location (e.g. `PID-7`, `OBX[2]-5`).

The project has two front doors that apply the same rules:

| | Where | Use |
|---|---|---|
| **Python package** `hl7_infectious/` | CLI / backend / pipelines | Pydantic v2 models, 80+ pytest cases |
| **Browser demo** `index.html` + `script.js` | GitHub Pages | Bilingual (EN/ES) interactive viewer |

---

## 🏗 Architecture (Python)

```
text ──ingest──▶ RawMessage ──validate──▶ ValidatedMessage ──summarize──▶ InfectiousDiseaseReport
      ingestion.py            validation.py                 transformation.py
```

| Module | Responsibility |
|---|---|
| `ingestion.py` | Normalises CR/LF/CRLF terminators, reads delimiters **declared in MSH-1/MSH-2**, tokenises segments so `fields[n] == SEG-n` (MSH included), resolves `\F\ \S\ \T\ \R\ \E\` escapes, splits batch feeds (FHS/BHS). |
| `validation.py` | Builds every record through a Pydantic model. Each validation error becomes an `Issue` with an HL7 location. Records with a bad *optional* field are **salvaged**, so one bad DOB doesn't discard the patient. |
| `transformation.py` | One LOINC-registry lookup per OBX groups findings by disease. Keeps *all* results per disease. |
| `loinc.py` | Immutable LOINC registry (verified against loinc.org) + Mod-10 check-digit validation. |
| `models.py` | Pydantic v2 models: `Delimiters`, `RawSegment`, `MessageHeader`, `PatientIdentity`, `Observation`, `Issue`, `InfectiousDiseaseReport`. |

### Validation rules
* **MSH**: message type, control ID (MSH-10), v2.x version (MSH-12), HL7 `TS` timestamps with any precision and UTC offset
* **PID**: MRN (PID-3) required; DOB (PID-7) parsed and rejected if impossible or in the future; sex against HL7 table 0001
* **OBX**: LOINC format **and check digit**; `NM` results must be numeric; result status against table 0085; abnormal flags against table 0078 (`H`, `L`, `A`, `AA`, …, not just `A`)
* Coded results (`CWE`/`CE`) keep the SNOMED code and display the text (`260373001^Detected^SCT` → *Detected*)
* **IGRA mitogen control** (`71772-8`) is recognised but never reported as a TB result

---

## 🚀 Usage

```bash
pip install -e ".[test]"

python -m hl7_infectious hl-samples/covid_oru.txt        # human-readable summary
python -m hl7_infectious hl-samples/*.txt --json         # machine-readable JSON
python parser.py hl-samples/broken_oru.txt               # legacy entry point still works
```

Exit codes: `0` clean · `1` parsed with validation errors · `2` unreadable input.

```python
from hl7_infectious import parse_message, Disease

report = parse_message(raw_hl7)
report.latest(Disease.COVID19).value   # "Detected"
report.has_errors                       # False
report.model_dump_json()                # FHIR-pipeline-ready JSON
```

### Tests
```bash
pytest --cov=hl7_infectious
```
The tests use mock payloads built in `tests/conftest.py`. They cover line-ending variants, custom
delimiters, Latin-1 input, batch envelopes, escape sequences, impossible dates, bad LOINC check
digits, non-numeric `NM` values, missing required fields, and JSON round-tripping. They also run
against every file in `hl-samples/`.

---

## 📂 Sample messages (`hl-samples/`)

| File | Content |
|---|---|
| `covid_oru.txt` | SARS-CoV-2 PCR, detected |
| `flu_oru.txt` | Influenza A (92142-9) not detected, Influenza B (92141-1) detected |
| `respiratory_panel_oru.txt` | 4-analyte panel: COVID / Flu A / Flu B / RSV |
| `hepatitis_tb_oru.txt` | HAV IgM, HBsAg, HBc IgM, HCV Ab, TB IGRA + mitogen control |
| `hiv_oru.txt` | HIV-1 viral load, numeric with `H` flag |
| `adt_a01.txt`, `adt_a03.txt` | Admit / discharge (no lab results) |
| `broken_oru.txt` | **Deliberate defects:** missing MRN, impossible DOB (month 13), LOINC with a wrong check digit, non-numeric `NM` value, empty OBX-5, invalid result status, a non-segment line |

All samples follow HL7 v2.5.1 OBX positions: OBX-5 value, OBX-6 units, OBX-7 reference range, OBX-8 abnormal flag, OBX-11 status.

---

## 🛠 Browser demo features
* **Bilingual Support (EN | ES)**
* **LOINC validation** with check-digit verification, using the same registry as the Python package
* **Disease summary badges** for 9 infectious-disease categories
* **Error & abnormal detection**: missing fields, invalid codes, and abnormal flags highlighted
* **XSS-safe rendering**: all message content is HTML-escaped before display
* **Dark mode** and **print-to-PDF** export

---

## 📂 File Structure
* `hl7_infectious/`: Python package (ingestion / validation / transformation)
* `tests/`: pytest suite
* `parser.py`: backwards-compatible CLI entry point
* `index.html`, `script.js`, `style.css`: browser demo
* `.github/workflows/tests.yml`: CI on Python 3.11–3.13

---

## 🎓 Academic Purpose
<section id="purpose">
    <h3>Purpose of This Site</h3>
    <p>This website was created in partial fulfillment of the CIS 3030 course requirements at MSU Denver.</p>
    <dl>
        <dt>Student Developer</dt>
        <dd>David Quintana</dd>
        <dt>Contact</dt>
        <dd>dquint32@msudenver.edu</dd>
        <dt>Language Preference</dt>
        <dd>English | Spanish</dd>
        <dt>Course Info</dt>
        <dd>CIS 3030 - Web Development</dd>
    </dl>
</section>

---

**Disclaimer:** This tool is for educational purposes. All sample data is synthetic. Always ensure HIPAA compliance and use de-identified data for testing.
