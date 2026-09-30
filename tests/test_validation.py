from __future__ import annotations

from datetime import date, datetime

import pytest

from hl7_infectious.ingestion import ingest
from hl7_infectious.models import Severity, parse_hl7_datetime
from hl7_infectious.validation import validate

from .conftest import DETECTED, MSH, PID, hl7, obx


def run(*segments: str):
    raw, _ = ingest(hl7(*segments))
    return validate(raw)


def codes(result) -> set[str]:
    return {i.code for i in result.issues}


def errors(result) -> list:
    return [i for i in result.issues if i.severity is Severity.ERROR]


def test_clean_message_has_no_issues(covid_positive: str) -> None:
    raw, _ = ingest(covid_positive)
    result = validate(raw)
    assert result.issues == ()
    assert result.header.message_type == "ORU" and result.header.trigger_event == "R01"
    assert result.header.timestamp == datetime(2025, 1, 1, 12, 0)
    assert result.patient.mrn == "123456"
    assert result.patient.birth_date == date(1980, 1, 1)
    assert result.patient.display_name == "JANE DOE"


def test_missing_mrn_is_an_error_pointing_at_pid3() -> None:
    result = run(MSH, "PID|1||||DOE^JANE||19800101|F", obx(1, "94500-6", DETECTED))
    assert result.patient is None
    issue = next(i for i in result.issues if i.location == "PID-3")
    assert issue.severity is Severity.ERROR and issue.line == 2


def test_bad_dob_is_reported_but_patient_is_salvaged() -> None:
    result = run(MSH, "PID|1||123||DOE^JANE||19801345|F", obx(1, "94500-6", DETECTED))
    assert result.patient is not None and result.patient.mrn == "123"
    assert result.patient.birth_date is None
    assert any(i.location == "PID-7" for i in errors(result))


def test_future_dob_is_rejected() -> None:
    result = run(MSH, "PID|1||123||DOE^JANE||29990101|F", obx(1, "94500-6", DETECTED))
    assert any("future" in i.message for i in result.issues)


def test_invalid_sex_code_is_reported() -> None:
    result = run(MSH, "PID|1||123||DOE^JANE||19800101|X", obx(1, "94500-6", DETECTED))
    assert any(i.location == "PID-8" for i in result.issues)
    assert result.patient.sex is None


def test_empty_name_and_dob_are_warnings() -> None:
    result = run(MSH, "PID|1||123", obx(1, "94500-6", DETECTED))
    assert {"PID_NAME_MISSING", "PID_DOB_MISSING"} <= codes(result)
    assert errors(result) == []


def test_oru_without_pid_or_obx_is_flagged() -> None:
    assert {"PID_MISSING", "OBX_MISSING"} <= codes(run(MSH))


def test_adt_does_not_require_obx() -> None:
    adt = MSH.replace("ORU^R01^ORU_R01", "ADT^A01")
    assert "OBX_MISSING" not in codes(run(adt, PID))


def test_missing_control_id_is_an_error() -> None:
    result = run(MSH.replace("|MSG001|", "||"), PID, obx(1, "94500-6", DETECTED))
    assert any(i.location == "MSH-10" for i in errors(result))


def test_non_v2_version_is_rejected() -> None:
    result = run(MSH.replace("|2.5.1", "|3.0"), PID, obx(1, "94500-6", DETECTED))
    assert any(i.location == "MSH-12" for i in result.issues)


@pytest.mark.parametrize(
    ("loinc", "expected_code", "severity"),
    [
        ("94500-7", "OBX_LOINC_INVALID", Severity.ERROR),     # wrong check digit
        ("XXXXX", "OBX_LOINC_INVALID", Severity.ERROR),       # not LOINC-shaped
        ("2345-7", "OBX_LOINC_UNMAPPED", Severity.WARNING),   # real LOINC (glucose), not in registry
    ],
)
def test_loinc_problems(loinc: str, expected_code: str, severity: Severity) -> None:
    result = run(MSH, PID, obx(1, loinc, DETECTED))
    issue = next(i for i in result.issues if i.code == expected_code)
    assert issue.severity is severity and issue.location == "OBX[1]-3"


def test_non_loinc_coding_system_is_a_warning() -> None:
    result = run(MSH, PID, "OBX|1|CWE|FLU^Local flu^L||" + DETECTED + "|||A|||F")
    assert "OBX_NOT_LOINC" in codes(result)


def test_nm_result_must_be_numeric() -> None:
    result = run(MSH, PID, obx(1, "25836-8", "BADVALUE", value_type="NM"))
    assert result.observations == ()
    assert any(i.location == "OBX[1]-5" and "numeric" in i.message for i in result.issues)


def test_missing_result_value_drops_only_that_observation() -> None:
    result = run(MSH, PID, obx(1, "94500-6", ""), obx(2, "92141-1", DETECTED))
    assert [o.loinc_code for o in result.observations] == ["92141-1"]
    assert any(i.location == "OBX[1]-5" for i in errors(result))


def test_invalid_result_status_is_salvaged() -> None:
    result = run(MSH, PID, obx(1, "94500-6", DETECTED, status="Z"))
    assert len(result.observations) == 1 and result.observations[0].result_status is None
    assert any(i.location == "OBX[1]-11" for i in result.issues)


def test_coded_value_keeps_code_and_displays_text() -> None:
    obs = run(MSH, PID, obx(1, "94500-6", DETECTED)).observations[0]
    assert obs.value == "Detected" and obs.value_code == "260373001"


@pytest.mark.parametrize(("flag", "abnormal"), [("A", True), ("H", True), ("LL", True),
                                                 ("N", False), ("", False)])
def test_abnormal_flags_follow_hl7_table_0078(flag: str, abnormal: bool) -> None:
    obs = run(MSH, PID, obx(1, "94500-6", DETECTED, flag=flag)).observations[0]
    assert obs.is_abnormal is abnormal


@pytest.mark.parametrize(("value", "expected"), [
    ("2025", datetime(2025, 1, 1)),
    ("202501021530", datetime(2025, 1, 2, 15, 30)),
    ("20250102153045.123", datetime(2025, 1, 2, 15, 30, 45)),
])
def test_hl7_timestamp_precisions(value: str, expected: datetime) -> None:
    assert parse_hl7_datetime(value).replace(tzinfo=None) == expected


def test_hl7_timestamp_with_offset() -> None:
    ts = parse_hl7_datetime("202501021530-0700")
    assert ts.utcoffset().total_seconds() == -7 * 3600


@pytest.mark.parametrize("bad", ["2025-01-01", "abc", "20251"])
def test_malformed_timestamps_raise(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_hl7_datetime(bad)
