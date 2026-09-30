from __future__ import annotations

import json

import pytest

from hl7_infectious import Disease, InfectiousDiseaseReport, parse_file, parse_message, render_text
from hl7_infectious.cli import main
from hl7_infectious.loinc import LOINC_REGISTRY, is_valid_loinc, loinc_check_digit

from .conftest import DETECTED, MSH, NOT_DETECTED, PID, hl7, obx

# ------------------------------------------------------------------ LOINC registry

@pytest.mark.parametrize("code", sorted(LOINC_REGISTRY))
def test_every_registry_code_has_a_valid_check_digit(code: str) -> None:
    assert is_valid_loinc(code)


def test_check_digit_algorithm() -> None:
    assert loinc_check_digit("94500") == 6
    assert not is_valid_loinc("94500-5")


# ------------------------------------------------------------------ summarize

def test_covid_positive_summary(covid_positive: str) -> None:
    report = parse_message(covid_positive)
    finding = report.latest(Disease.COVID19)
    assert finding.value == "Detected" and finding.abnormal
    assert not report.has_errors


def test_flu_a_and_b_are_distinguished_by_code_not_by_free_text() -> None:
    # Deliberately misleading test names: the LOINC code must win.
    report = parse_message(hl7(MSH, PID,
                               obx(1, "92142-9", NOT_DETECTED, name="Influenza B??"),
                               obx(2, "92141-1", DETECTED, flag="A", name="Influenza A??")))
    assert report.latest(Disease.INFLUENZA_A).value == "Not detected"
    assert report.latest(Disease.INFLUENZA_B).value == "Detected"


def test_igra_mitogen_control_is_not_reported_as_a_tb_result() -> None:
    report = parse_message(hl7(MSH, PID, obx(1, "71772-8", "9.8", value_type="NM")))
    assert Disease.TUBERCULOSIS not in report.findings


def test_multiple_results_for_one_disease_are_all_kept() -> None:
    report = parse_message(hl7(MSH, PID, obx(1, "5195-3", DETECTED, flag="A"),
                               obx(2, "24113-3", NOT_DETECTED)))
    assert [f.loinc_code for f in report.findings[Disease.HEPATITIS_B]] == ["5195-3", "24113-3"]


def test_unmapped_loinc_is_not_summarised() -> None:
    report = parse_message(hl7(MSH, PID, obx(1, "2345-7", "95", value_type="NM")))
    assert report.findings == {}


def test_report_round_trips_through_json(covid_positive: str) -> None:
    report = parse_message(covid_positive)
    restored = InfectiousDiseaseReport.model_validate_json(report.model_dump_json())
    assert restored.findings == report.findings
    assert restored.patient.mrn == report.patient.mrn


def test_issues_are_ordered_by_line() -> None:
    report = parse_message(hl7(MSH, "PID|1||||||bad", "junk line", obx(1, "XXXXX", DETECTED)))
    lines = [i.line or 0 for i in report.issues]
    assert lines == sorted(lines)


def test_render_text_mentions_patient_and_abnormal(covid_positive: str) -> None:
    text = render_text(parse_message(covid_positive))
    assert "JANE DOE" in text and "ABNORMAL" in text


# ------------------------------------------------------------------ bundled sample files

EXPECTED = {
    "adt_a01.txt": {},
    "adt_a03.txt": {},
    "covid_oru.txt": {Disease.COVID19: "Detected"},
    "flu_oru.txt": {Disease.INFLUENZA_A: "Not detected", Disease.INFLUENZA_B: "Detected"},
    "hiv_oru.txt": {Disease.HIV: "54000"},
    "respiratory_panel_oru.txt": {Disease.RSV: "Detected", Disease.COVID19: "Not detected"},
    "hepatitis_tb_oru.txt": {Disease.TUBERCULOSIS: "Detected", Disease.HEPATITIS_C: "Not detected"},
}


@pytest.mark.parametrize(("name", "expected"), EXPECTED.items())
def test_clean_samples(samples_dir, name: str, expected: dict) -> None:
    [report] = parse_file(samples_dir / name)
    assert not report.has_errors, report.issues
    for disease, value in expected.items():
        assert report.latest(disease).value == value


def test_broken_sample_reports_every_defect(samples_dir) -> None:
    [report] = parse_file(samples_dir / "broken_oru.txt")
    locations = {i.location for i in report.issues}
    assert {"PID-3", "PID-7", "OBX[1]-3", "OBX[1]-5", "OBX[2]-5", "OBX[2]-11"} <= locations
    assert any(i.code == "SEGMENT_MALFORMED" for i in report.issues)


# ------------------------------------------------------------------ CLI

def test_cli_exit_codes(samples_dir, capsys) -> None:
    assert main([str(samples_dir / "covid_oru.txt")]) == 0
    assert main([str(samples_dir / "broken_oru.txt")]) == 1
    assert main([str(samples_dir / "does_not_exist.txt")]) == 2
    capsys.readouterr()


def test_cli_json_output(samples_dir, capsys) -> None:
    main([str(samples_dir / "flu_oru.txt"), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["findings"]["Influenza B"][0]["value"] == "Detected"
