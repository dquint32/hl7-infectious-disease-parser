"""Validation: RawMessage -> ValidatedMessage (typed models + issues).

Every clinical record is built through a Pydantic model. When a model rejects a
field, the error is converted to an :class:`Issue` that points at the exact HL7
location (e.g. ``PID-7``) and the record is *salvaged* with that field blanked,
so one bad date of birth does not throw away an otherwise usable patient.
Only when a *required* field is bad is the record dropped.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from .ingestion import component
from .loinc import LOINC_REGISTRY, is_valid_loinc
from .models import (
    Issue,
    MessageHeader,
    Observation,
    PatientIdentity,
    RawMessage,
    RawSegment,
    Severity,
    ValidatedMessage,
)

M = TypeVar("M", bound=BaseModel)

# Message types whose summary depends on a patient / on lab results.
_NEEDS_PID = frozenset({"ADT", "ORU", "ORM", "OML", "VXU"})
_NEEDS_OBX = frozenset({"ORU"})


def _err(code: str, message: str, location: str | None = None, line: int | None = None,
         severity: Severity = Severity.ERROR) -> Issue:
    return Issue(severity=severity, code=code, message=message, location=location, line=line)


def _friendly(err: Any) -> str:
    if err["type"] in {"missing", "string_too_short"}:
        return "required value is empty"
    return str(err["msg"]).removeprefix("Value error, ")


def _build(model: type[M], data: dict[str, Any], *, segment: str, line: int,
           issues: list[Issue], ordinal: int | None = None) -> M | None:
    """Validate ``data`` into ``model``; on failure record issues and salvage if possible."""
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        prefix = f"{segment}[{ordinal}]" if ordinal else segment
        hl7_map: dict[str, str] = getattr(model, "HL7_FIELDS", {})
        bad_fields: set[str] = set()
        for err in exc.errors():
            field = str(err["loc"][0]) if err["loc"] else ""
            bad_fields.add(field)
            hl7 = hl7_map.get(field)
            location = hl7.replace(segment, prefix, 1) if hl7 else prefix
            issues.append(_err(
                code=f"{segment}_INVALID_{field.upper() or 'RECORD'}",
                message=f"{location}: {_friendly(err)}", location=location, line=line,
            ))
        required = {name for name, f in model.model_fields.items() if f.is_required()}
        if "" in bad_fields or bad_fields & required:
            return None  # cannot salvage a record whose required data is unusable
        salvaged = {k: v for k, v in data.items() if k not in bad_fields}
        try:
            return model.model_validate(salvaged)
        except ValidationError:
            return None


def _header(seg: RawSegment, msg: RawMessage, issues: list[Issue]) -> MessageHeader | None:
    d = msg.delimiters
    return _build(MessageHeader, {
        "sending_application": component(seg.field(3), 1, d),
        "sending_facility": component(seg.field(4), 1, d),
        "timestamp": seg.field(7),
        "message_type": component(seg.field(9), 1, d),
        "trigger_event": component(seg.field(9), 2, d),
        "control_id": seg.field(10),
        "version": component(seg.field(12), 1, d),
    }, segment="MSH", line=seg.line, issues=issues)


def _patient(seg: RawSegment, msg: RawMessage, issues: list[Issue]) -> PatientIdentity | None:
    d = msg.delimiters
    data = {
        "mrn": component(seg.field(3), 1, d),
        "family_name": component(seg.field(5), 1, d),
        "given_name": component(seg.field(5), 2, d),
        "birth_date": seg.field(7),
        "sex": component(seg.field(8), 1, d),
    }
    patient = _build(PatientIdentity, data, segment="PID", line=seg.line, issues=issues)
    if patient and not patient.family_name:
        issues.append(_err("PID_NAME_MISSING", "PID-5: patient name is empty", "PID-5",
                           seg.line, Severity.WARNING))
    if patient and patient.birth_date is None and not seg.field(7).strip():
        issues.append(_err("PID_DOB_MISSING", "PID-7: date of birth is empty", "PID-7",
                           seg.line, Severity.WARNING))
    return patient


_CODED_TYPES = frozenset({"CE", "CWE", "CNE"})


def _observation(seg: RawSegment, ordinal: int, msg: RawMessage,
                 issues: list[Issue]) -> Observation | None:
    d = msg.delimiters
    prefix = f"OBX[{ordinal}]"
    value_type = seg.field(2).strip()
    raw_value = seg.field(5)
    if value_type in _CODED_TYPES:  # coded answer: keep the code, display the text
        value_code = component(raw_value, 1, d)
        value = component(raw_value, 2, d) or value_code
    else:
        value_code, value = "", component(raw_value, 1, d)

    code = component(seg.field(3), 1, d).strip()
    system = component(seg.field(3), 3, d).strip()
    # Code checks run on the raw field so they are reported even if the record is dropped.
    if system and system != "LN":
        issues.append(_err("OBX_NOT_LOINC", f"{prefix}-3: coding system is {system!r}, expected 'LN'",
                           f"{prefix}-3", seg.line, Severity.WARNING))
    elif code and not is_valid_loinc(code):
        issues.append(_err("OBX_LOINC_INVALID", f"{prefix}-3: {code!r} is not a valid LOINC code "
                           "(bad format or check digit)", f"{prefix}-3", seg.line))
    elif code and code not in LOINC_REGISTRY:
        issues.append(_err("OBX_LOINC_UNMAPPED", f"{prefix}-3: LOINC {code} is valid but not in the "
                           "infectious-disease registry", f"{prefix}-3", seg.line, Severity.WARNING))

    return _build(Observation, {
        "line": seg.line,
        "set_id": seg.field(1),
        "value_type": value_type,
        "loinc_code": code,
        "test_name": component(seg.field(3), 2, d),
        "coding_system": system,
        "value": value,
        "value_code": value_code,
        "units": component(seg.field(6), 1, d),
        "reference_range": seg.field(7),
        "abnormal_flag": component(seg.field(8), 1, d),
        "result_status": seg.field(11),
    }, segment="OBX", ordinal=ordinal, line=seg.line, issues=issues)


def validate(msg: RawMessage) -> ValidatedMessage:
    issues: list[Issue] = []

    msh = msg.segments[0]
    header = _header(msh, msg, issues)
    msg_type = header.message_type if header else None

    pid = msg.first("PID")
    patient = _patient(pid, msg, issues) if pid else None
    if pid is None and msg_type in _NEEDS_PID:
        issues.append(_err("PID_MISSING", f"{msg_type} message has no PID segment", "PID"))

    obx_segments = msg.all("OBX")
    observations = tuple(
        obs for i, seg in enumerate(obx_segments, start=1)
        if (obs := _observation(seg, i, msg, issues)) is not None
    )
    if not obx_segments and msg_type in _NEEDS_OBX:
        issues.append(_err("OBX_MISSING", f"{msg_type} message has no OBX result segments", "OBX"))

    return ValidatedMessage(header=header, patient=patient,
                            observations=observations, issues=tuple(issues))
