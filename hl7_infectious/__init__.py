"""HL7 v2.x infectious-disease parser.

Pipeline::

    text --ingest--> RawMessage --validate--> ValidatedMessage --summarize--> InfectiousDiseaseReport
"""

from __future__ import annotations

from pathlib import Path

from .ingestion import HL7IngestionError, ingest, read_text, split_messages
from .loinc import LOINC_REGISTRY, Disease, is_valid_loinc
from .models import InfectiousDiseaseReport, Issue, Severity
from .transformation import render_text, summarize
from .validation import validate

__all__ = [
    "Disease", "HL7IngestionError", "InfectiousDiseaseReport", "Issue", "LOINC_REGISTRY",
    "Severity", "is_valid_loinc", "parse_file", "parse_message", "parse_messages", "render_text",
]


def parse_message(text: str) -> InfectiousDiseaseReport:
    """Run one HL7 message through ingestion -> validation -> transformation."""
    raw, ingest_issues = ingest(text)
    validated = validate(raw)
    issues = sorted((*ingest_issues, *validated.issues), key=lambda i: i.line or 0)
    return summarize(validated.model_copy(update={"issues": tuple(issues)}))


def parse_messages(text: str) -> list[InfectiousDiseaseReport]:
    """Parse a feed that may contain several MSH-delimited messages."""
    return [parse_message(m) for m in split_messages(text)]


def parse_file(path: str | Path) -> list[InfectiousDiseaseReport]:
    return parse_messages(read_text(path))
