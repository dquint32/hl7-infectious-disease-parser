"""Ingestion: raw text -> RawMessage.

Responsibilities (and nothing else):
* normalise CR / LF / CRLF segment terminators (the original code split on "\\n"
  only, leaving a trailing "\\r" glued to the last field of every segment);
* read the delimiters the message *declares* in MSH-1/MSH-2 instead of assuming "|^~\\&";
* tokenise segments so that ``fields[n]`` is SEG-n for MSH and non-MSH alike;
* split a multi-message feed into individual messages.

Anything unrecoverable raises :class:`HL7IngestionError`; anything recoverable
(e.g. a garbage line in the middle of a message) is returned as an :class:`Issue`.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError

from .models import Delimiters, Issue, RawMessage, RawSegment, Severity

_SEGMENT_SPLIT = re.compile(r"\r\n|\r|\n")
_BATCH_ENVELOPE = frozenset({"FHS", "BHS", "BTS", "FTS"})


class HL7IngestionError(ValueError):
    """The input cannot be interpreted as an HL7 v2 message at all."""


def read_text(path: str | Path) -> str:
    """Read a file as text, tolerating a UTF-8 BOM and legacy Latin-1 feeds."""
    raw = Path(path).read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _lines(text: str) -> Iterator[tuple[int, str]]:
    for number, line in enumerate(_SEGMENT_SPLIT.split(text), start=1):
        if line.strip():
            yield number, line


def split_messages(text: str) -> list[str]:
    """Split a feed containing one or more messages at every MSH segment."""
    messages: list[list[str]] = []
    for _, line in _lines(text):
        name = line[:3]
        if name in _BATCH_ENVELOPE:
            continue
        if name == "MSH" or not messages:
            messages.append([])
        messages[-1].append(line)
    return ["\r".join(m) for m in messages]


def parse_delimiters(msh_line: str) -> Delimiters:
    if not msh_line.startswith("MSH") or len(msh_line) < 8:
        raise HL7IngestionError("message must start with an MSH segment declaring its delimiters")
    field_sep = msh_line[3]
    encoding = msh_line[4:].split(field_sep, 1)[0]
    if len(encoding) < 4:
        raise HL7IngestionError(f"MSH-2 must hold 4 encoding characters, got {encoding!r}")
    try:
        return Delimiters(
            field=field_sep, component=encoding[0], repetition=encoding[1],
            escape=encoding[2], subcomponent=encoding[3],
        )
    except ValidationError as exc:
        raise HL7IngestionError(f"invalid MSH delimiters: {exc.errors()[0]['msg']}") from exc


def _tokenise(line: str, number: int, delims: Delimiters) -> RawSegment:
    parts = line.split(delims.field)
    if parts[0] == "MSH":
        # MSH-1 *is* the field separator, so re-insert it to keep fields[n] == MSH-n.
        parts.insert(1, delims.field)
    return RawSegment(line=number, name=parts[0], fields=tuple(parts))


def ingest(text: str) -> tuple[RawMessage, list[Issue]]:
    """Tokenise a single HL7 v2 message."""
    if not text or not text.strip():
        raise HL7IngestionError("input is empty")

    lines = list(_lines(text.lstrip("﻿")))
    delims = parse_delimiters(lines[0][1])

    segments: list[RawSegment] = []
    issues: list[Issue] = []
    for number, line in lines:
        try:
            segments.append(_tokenise(line, number, delims))
        except ValidationError:
            issues.append(Issue(
                severity=Severity.ERROR, code="SEGMENT_MALFORMED", line=number,
                message=f"not a valid HL7 segment: {line[:40]!r}",
            ))
    return RawMessage(delimiters=delims, segments=tuple(segments)), issues


# --------------------------------------------------------------------------- field access

_ESCAPES = {"F": "field", "S": "component", "T": "subcomponent", "R": "repetition", "E": "escape"}


def unescape(value: str, delims: Delimiters) -> str:
    """Resolve HL7 escape sequences such as ``\\F\\`` and ``\\S\\``."""
    esc = delims.escape
    if esc not in value:
        return value
    pattern = re.compile(re.escape(esc) + r"([FSTRE])" + re.escape(esc))
    return pattern.sub(lambda m: getattr(delims, _ESCAPES[m.group(1)]), value)


def component(value: str, index: int, delims: Delimiters) -> str:
    """1-based component of the first repetition of a field, unescaped."""
    first_rep = value.split(delims.repetition, 1)[0]
    parts = first_rep.split(delims.component)
    return unescape(parts[index - 1], delims) if 0 < index <= len(parts) else ""
