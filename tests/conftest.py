from __future__ import annotations

from pathlib import Path

import pytest

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "hl-samples"

MSH = "MSH|^~\\&|LAB|HOSPITAL|STATE|CO|202501011200||ORU^R01^ORU_R01|MSG001|P|2.5.1"
PID = "PID|1||123456^^^HOSPITAL^MR||DOE^JANE||19800101|F"


def hl7(*segments: str, sep: str = "\r") -> str:
    """Build a mock HL7 payload from segment strings."""
    return sep.join(segments)


def obx(set_id: int, loinc: str, value: str, *, value_type: str = "CWE",
        units: str = "", ref: str = "", flag: str = "N", status: str = "F",
        name: str = "Test") -> str:
    return f"OBX|{set_id}|{value_type}|{loinc}^{name}^LN||{value}|{units}|{ref}|{flag}|||{status}"


DETECTED = "260373001^Detected^SCT"
NOT_DETECTED = "260415000^Not detected^SCT"


@pytest.fixture
def covid_positive() -> str:
    return hl7(MSH, PID, obx(1, "94500-6", DETECTED, flag="A"))


@pytest.fixture
def samples_dir() -> Path:
    return SAMPLES_DIR
