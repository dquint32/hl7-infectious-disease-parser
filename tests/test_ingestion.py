from __future__ import annotations

import pytest

from hl7_infectious.ingestion import (
    HL7IngestionError,
    component,
    ingest,
    parse_delimiters,
    read_text,
    split_messages,
    unescape,
)
from hl7_infectious.models import Delimiters

from .conftest import MSH, PID, hl7


@pytest.mark.parametrize("sep", ["\r", "\n", "\r\n"])
def test_all_segment_terminators_are_equivalent(sep: str) -> None:
    raw, issues = ingest(hl7(MSH, PID, sep=sep))
    assert [s.name for s in raw.segments] == ["MSH", "PID"]
    assert issues == []
    # No stray carriage return glued onto the last field (bug in the original split("\n")).
    assert raw.segments[1].fields[-1] == "F"


def test_msh_field_numbering_matches_the_spec() -> None:
    raw, _ = ingest(MSH)
    msh = raw.segments[0]
    assert msh.field(1) == "|"
    assert msh.field(2) == "^~\\&"
    assert msh.field(9) == "ORU^R01^ORU_R01"
    assert msh.field(10) == "MSG001"


def test_out_of_range_field_returns_empty_string() -> None:
    raw, _ = ingest(hl7(MSH, "PID|1"))
    assert raw.segments[1].field(30) == ""


def test_custom_delimiters_declared_in_msh_are_honoured() -> None:
    text = hl7("MSH#*~\\&#LAB#HOSP#####ORU*R01#X1#P#2.5.1", "PID#1##42##DOE*JANE")
    raw, _ = ingest(text)
    assert raw.delimiters.field == "#"
    assert component(raw.segments[1].field(5), 2, raw.delimiters) == "JANE"


@pytest.mark.parametrize("text", ["", "   ", "\r\n\r\n"])
def test_empty_input_is_rejected(text: str) -> None:
    with pytest.raises(HL7IngestionError, match="empty"):
        ingest(text)


def test_message_must_start_with_msh() -> None:
    with pytest.raises(HL7IngestionError, match="MSH"):
        ingest(PID)


@pytest.mark.parametrize("msh", ["MSH|^~", "MSH|^^\\&|X", "MSH|^~\\"])
def test_bad_encoding_characters_are_rejected(msh: str) -> None:
    with pytest.raises(HL7IngestionError):
        parse_delimiters(msh)


def test_garbage_line_becomes_an_issue_not_a_crash() -> None:
    raw, issues = ingest(hl7(MSH, "not a segment", PID))
    assert [s.name for s in raw.segments] == ["MSH", "PID"]
    assert len(issues) == 1 and issues[0].code == "SEGMENT_MALFORMED" and issues[0].line == 2


def test_utf8_bom_is_stripped() -> None:
    raw, _ = ingest("﻿" + MSH)
    assert raw.segments[0].name == "MSH"


def test_read_text_falls_back_to_latin1(tmp_path) -> None:
    path = tmp_path / "latin1.hl7"
    path.write_bytes(hl7(MSH, "PID|1||1||PEÑA^JOSÉ").encode("latin-1"))
    assert "PEÑA" in read_text(path)


def test_split_messages_handles_batches_and_envelopes() -> None:
    feed = hl7("FHS|^~\\&", "BHS|^~\\&", MSH, PID, MSH.replace("MSG001", "MSG002"), PID, "BTS|2", "FTS|1")
    messages = split_messages(feed)
    assert len(messages) == 2
    assert all(m.startswith("MSH") for m in messages)


def test_escape_sequences_are_resolved() -> None:
    d = Delimiters()
    assert unescape(r"A\F\B\S\C\T\D\R\E\E\F", d) == "A|B^C&D~E\\F"
    assert unescape("plain", d) == "plain"


def test_component_uses_first_repetition_only() -> None:
    d = Delimiters()
    assert component("111^^^A~222^^^B", 1, d) == "111"
    assert component("111", 4, d) == ""
