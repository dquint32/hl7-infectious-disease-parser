"""Pydantic v2 models for every stage of the pipeline.

Raw layer   -> Delimiters, RawSegment, RawMessage     (ingestion output)
Typed layer -> MessageHeader, PatientIdentity, Observation (validation output)
Report      -> Issue, Finding, InfectiousDiseaseReport   (transformation output)
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from enum import StrEnum
from typing import Annotated, ClassVar, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationInfo,
    computed_field,
    field_validator,
    model_validator,
)

from .loinc import Disease

# --------------------------------------------------------------------------- helpers

def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


OptStr = Annotated[str | None, BeforeValidator(_blank_to_none)]

_HL7_TS = re.compile(
    r"^(?P<Y>\d{4})(?P<m>\d{2})?(?P<d>\d{2})?(?P<H>\d{2})?(?P<M>\d{2})?(?P<S>\d{2})?"
    r"(?:\.\d{1,4})?(?P<tz>[+-]\d{4})?$"
)


def parse_hl7_datetime(value: str) -> datetime:
    """Parse an HL7 v2 TS/DTM value (``YYYY[MM[DD[HH[MM[SS[.S]]]]]][+/-ZZZZ]``)."""
    match = _HL7_TS.match(value.strip())
    if not match:
        raise ValueError(f"not an HL7 timestamp: {value!r}")
    g = match.groupdict()
    tz = None
    if g["tz"]:
        sign = 1 if g["tz"][0] == "+" else -1
        tz = timezone(sign * timedelta(hours=int(g["tz"][1:3]), minutes=int(g["tz"][3:5])))
    return datetime(
        int(g["Y"]), int(g["m"] or 1), int(g["d"] or 1),
        int(g["H"] or 0), int(g["M"] or 0), int(g["S"] or 0), tzinfo=tz,
    )


def _is_hl7_ts(value: object) -> bool:
    return isinstance(value, str) and bool(_HL7_TS.match(value.strip()))


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def _drop_computed_fields(cls, data: object) -> object:
        # Lets model_dump_json() output be re-loaded without tripping extra="forbid".
        if isinstance(data, dict) and cls.model_computed_fields:
            return {k: v for k, v in data.items() if k not in cls.model_computed_fields}
        return data


# --------------------------------------------------------------------------- raw layer

class Delimiters(_Frozen):
    """Encoding characters declared in MSH-1 / MSH-2."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=False)

    field: str = Field("|", min_length=1, max_length=1)
    component: str = Field("^", min_length=1, max_length=1)
    repetition: str = Field("~", min_length=1, max_length=1)
    escape: str = Field("\\", min_length=1, max_length=1)
    subcomponent: str = Field("&", min_length=1, max_length=1)

    @model_validator(mode="after")
    def _distinct(self) -> "Delimiters":
        chars = (self.field, self.component, self.repetition, self.escape, self.subcomponent)
        if len(set(chars)) != len(chars):
            raise ValueError(f"HL7 delimiters must be distinct, got {''.join(chars)!r}")
        return self


class RawSegment(_Frozen):
    """One segment, with ``fields[n]`` == SEG-n for every segment type (MSH included)."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=False)

    line: int = Field(ge=1)
    name: str = Field(pattern=r"^[A-Z][A-Z0-9]{2}$")
    fields: tuple[str, ...]

    def field(self, n: int) -> str:
        return self.fields[n] if 0 < n < len(self.fields) else ""


class RawMessage(_Frozen):
    delimiters: Delimiters
    segments: tuple[RawSegment, ...] = Field(min_length=1)

    def first(self, name: str) -> RawSegment | None:
        return next((s for s in self.segments if s.name == name), None)

    def all(self, name: str) -> list[RawSegment]:
        return [s for s in self.segments if s.name == name]


# --------------------------------------------------------------------------- issues

class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class Issue(_Frozen):
    severity: Severity
    code: str                     # machine-readable, e.g. "PID_MRN_MISSING"
    message: str
    location: str | None = None   # HL7 path, e.g. "PID-7" or "OBX[2]-5"
    line: int | None = None


# --------------------------------------------------------------------------- typed layer

class MessageHeader(_Frozen):
    HL7_FIELDS: ClassVar[dict[str, str]] = {
        "sending_application": "MSH-3", "sending_facility": "MSH-4",
        "timestamp": "MSH-7", "message_type": "MSH-9.1", "trigger_event": "MSH-9.2",
        "control_id": "MSH-10", "version": "MSH-12",
    }

    sending_application: OptStr = None
    sending_facility: OptStr = None
    timestamp: datetime | None = None
    message_type: str = Field(min_length=3, max_length=3)
    trigger_event: OptStr = None
    control_id: str = Field(min_length=1)
    version: OptStr = None

    @field_validator("timestamp", mode="before")
    @classmethod
    def _ts(cls, v: object) -> object:
        v = _blank_to_none(v)
        return parse_hl7_datetime(v) if _is_hl7_ts(v) else v  # else: ISO, handled by pydantic

    @field_validator("version")
    @classmethod
    def _v2(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("2."):
            raise ValueError(f"expected an HL7 v2.x version, got {v!r}")
        return v


Sex = Literal["M", "F", "O", "U", "A", "N"]  # HL7 table 0001


class PatientIdentity(_Frozen):
    HL7_FIELDS: ClassVar[dict[str, str]] = {
        "mrn": "PID-3", "family_name": "PID-5.1", "given_name": "PID-5.2",
        "birth_date": "PID-7", "sex": "PID-8",
    }

    mrn: str = Field(min_length=1)
    family_name: OptStr = None
    given_name: OptStr = None
    birth_date: date | None = None
    sex: Annotated[Sex | None, BeforeValidator(_blank_to_none)] = None

    @field_validator("birth_date", mode="before")
    @classmethod
    def _dob(cls, v: object) -> object:
        v = _blank_to_none(v)
        if _is_hl7_ts(v):
            if len(v.strip()) < 8:
                raise ValueError("birth date needs at least YYYYMMDD precision")
            v = parse_hl7_datetime(v).date()
        if isinstance(v, date) and v > date.today():
            raise ValueError("birth date is in the future")
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def display_name(self) -> str:
        return " ".join(p for p in (self.given_name, self.family_name) if p)


ABNORMAL_FLAGS = frozenset({"L", "H", "LL", "HH", "<", ">", "A", "AA"})  # HL7 table 0078
RESULT_STATUSES = frozenset("CDFINOPRSUWX")                              # HL7 table 0085


class Observation(_Frozen):
    HL7_FIELDS: ClassVar[dict[str, str]] = {
        "set_id": "OBX-1", "value_type": "OBX-2", "loinc_code": "OBX-3.1",
        "test_name": "OBX-3.2", "coding_system": "OBX-3.3", "value": "OBX-5",
        "value_code": "OBX-5.1", "units": "OBX-6", "reference_range": "OBX-7",
        "abnormal_flag": "OBX-8", "result_status": "OBX-11",
    }

    line: int = Field(ge=1)
    set_id: Annotated[int | None, BeforeValidator(_blank_to_none)] = None
    value_type: OptStr = None
    loinc_code: str = Field(min_length=1)
    test_name: OptStr = None
    coding_system: OptStr = None
    value: str = Field(min_length=1)
    value_code: OptStr = None
    units: OptStr = None
    reference_range: OptStr = None
    abnormal_flag: OptStr = None
    result_status: OptStr = None

    @field_validator("result_status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None and v not in RESULT_STATUSES:
            raise ValueError(f"{v!r} is not an HL7 result status (table 0085)")
        return v

    @field_validator("value")
    @classmethod
    def _numeric_value(cls, v: str, info: ValidationInfo) -> str:
        if info.data.get("value_type") == "NM":
            try:
                float(v)
            except ValueError:
                raise ValueError(f"OBX-2 is NM but the value {v!r} is not numeric") from None
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_abnormal(self) -> bool:
        return self.abnormal_flag in ABNORMAL_FLAGS


class ValidatedMessage(_Frozen):
    header: MessageHeader | None
    patient: PatientIdentity | None
    observations: tuple[Observation, ...] = ()
    issues: tuple[Issue, ...] = ()


# --------------------------------------------------------------------------- report

class Finding(_Frozen):
    loinc_code: str
    test_name: str | None
    value: str
    value_code: str | None
    units: str | None
    reference_range: str | None
    abnormal: bool
    line: int


class InfectiousDiseaseReport(_Frozen):
    header: MessageHeader | None
    patient: PatientIdentity | None
    findings: dict[Disease, tuple[Finding, ...]] = Field(default_factory=dict)
    issues: tuple[Issue, ...] = ()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_errors(self) -> bool:
        return any(i.severity is Severity.ERROR for i in self.issues)

    def latest(self, disease: Disease) -> Finding | None:
        results = self.findings.get(disease, ())
        return results[-1] if results else None
