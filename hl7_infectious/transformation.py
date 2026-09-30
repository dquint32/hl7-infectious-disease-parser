"""Transformation: ValidatedMessage -> InfectiousDiseaseReport.

Replaces nine loose ``let covid = ""; let fluA = ""; ...`` variables and a chain
of nine ``if`` checks per OBX with a single registry lookup per observation.
Findings are grouped per disease and *all* are kept (the original overwrote
earlier results, so a HBsAg result was silently lost when HBc IgM followed it).
"""

from __future__ import annotations

from collections import defaultdict

from .loinc import LOINC_REGISTRY, Disease
from .models import Finding, InfectiousDiseaseReport, ValidatedMessage


def summarize(validated: ValidatedMessage) -> InfectiousDiseaseReport:
    grouped: dict[Disease, list[Finding]] = defaultdict(list)
    for obs in validated.observations:
        entry = LOINC_REGISTRY.get(obs.loinc_code)
        if entry is None or not entry.reportable:
            continue
        grouped[entry.disease].append(Finding(
            loinc_code=obs.loinc_code, test_name=obs.test_name,
            value=obs.value, value_code=obs.value_code,
            units=obs.units, reference_range=obs.reference_range,
            abnormal=obs.is_abnormal, line=obs.line,
        ))
    return InfectiousDiseaseReport(
        header=validated.header,
        patient=validated.patient,
        findings={disease: tuple(items) for disease, items in grouped.items()},
        issues=validated.issues,
    )


def render_text(report: InfectiousDiseaseReport) -> str:
    """Human-readable summary for the CLI."""
    out: list[str] = []
    h, p = report.header, report.patient
    if h:
        event = f"^{h.trigger_event}" if h.trigger_event else ""
        out.append(f"Message   {h.message_type}{event}  control={h.control_id}  v{h.version or '?'}")
    if p:
        dob = p.birth_date.isoformat() if p.birth_date else "unknown"
        out.append(f"Patient   {p.display_name or '(no name)'}  MRN={p.mrn}  DOB={dob}")
    out.append("")
    for disease in Disease:
        for f in report.findings.get(disease, ()):
            flag = "  ⚠ ABNORMAL" if f.abnormal else ""
            units = f" {f.units}" if f.units else ""
            out.append(f"  {disease.value:<22} {f.value}{units}  [{f.loinc_code}]{flag}")
    if not report.findings:
        out.append("  (no infectious-disease results)")
    if report.issues:
        out.append("")
        out.append("Issues")
        for i in report.issues:
            where = f"line {i.line}, " if i.line else ""
            out.append(f"  [{i.severity.value.upper():7}] {where}{i.message}")
    return "\n".join(out)
