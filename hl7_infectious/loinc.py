"""LOINC reference data for the infectious-disease panel.

One immutable registry replaces the scattered ``if loinc === ...`` checks and the
separate ``validLoinc`` array in the original script: a single dict lookup now
answers "is this code known?", "which disease does it report?" and "is it a
reportable result or a QC control?".

Codes were checked against loinc.org long common names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

LOINC_PATTERN = re.compile(r"^(\d{1,7})-(\d)$")


class Disease(StrEnum):
    COVID19 = "COVID-19"
    INFLUENZA_A = "Influenza A"
    INFLUENZA_B = "Influenza B"
    RSV = "RSV"
    HIV = "HIV-1 viral load"
    TUBERCULOSIS = "Tuberculosis (IGRA)"
    HEPATITIS_A = "Hepatitis A IgM"
    HEPATITIS_B = "Hepatitis B"
    HEPATITIS_C = "Hepatitis C Ab"


@dataclass(frozen=True, slots=True)
class LoincEntry:
    code: str
    disease: Disease
    long_name: str
    reportable: bool = True  # False for QC/control analytes (e.g. IGRA mitogen tube)


_ENTRIES: tuple[LoincEntry, ...] = (
    LoincEntry("94500-6", Disease.COVID19,
               "SARS-CoV-2 (COVID-19) RNA [Presence] in Respiratory system specimen by NAA with probe detection"),
    LoincEntry("92142-9", Disease.INFLUENZA_A,
               "Influenza virus A RNA [Presence] in Respiratory system specimen by NAA with probe detection"),
    LoincEntry("76078-5", Disease.INFLUENZA_A,
               "Influenza virus A RNA [Presence] in Nasopharynx by NAA with probe detection"),
    LoincEntry("92141-1", Disease.INFLUENZA_B,
               "Influenza virus B RNA [Presence] in Respiratory system specimen by NAA with probe detection"),
    LoincEntry("85479-4", Disease.RSV,
               "Respiratory syncytial virus RNA [Presence] in Upper respiratory specimen by NAA with probe detection"),
    LoincEntry("25836-8", Disease.HIV,
               "HIV 1 RNA [#/volume] (viral load) in Serum or Plasma by NAA with probe detection"),
    LoincEntry("64084-7", Disease.TUBERCULOSIS,
               "Mycobacterium tuberculosis stimulated gamma interferon release by CD4+ T-cells corrected for background in Blood"),
    LoincEntry("45323-3", Disease.TUBERCULOSIS,
               "Mycobacterium tuberculosis tuberculin stimulated gamma interferon [Presence] in Blood"),
    LoincEntry("71772-8", Disease.TUBERCULOSIS,
               "Mitogen stimulated gamma interferon [Units/volume] in Blood", reportable=False),
    LoincEntry("13950-1", Disease.HEPATITIS_A,
               "Hepatitis A virus IgM Ab [Presence] in Serum or Plasma by Immunoassay"),
    LoincEntry("5195-3", Disease.HEPATITIS_B,
               "Hepatitis B virus surface Ag [Presence] in Serum or Plasma"),
    LoincEntry("24113-3", Disease.HEPATITIS_B,
               "Hepatitis B virus core IgM Ab [Presence] in Serum or Plasma by Immunoassay"),
    LoincEntry("13955-0", Disease.HEPATITIS_C,
               "Hepatitis C virus Ab [Presence] in Serum or Plasma"),
)

LOINC_REGISTRY: Mapping[str, LoincEntry] = MappingProxyType({e.code: e for e in _ENTRIES})


def loinc_check_digit(base: str) -> int:
    """Mod-10 check digit used by LOINC (same algorithm as Luhn)."""
    total = 0
    for i, ch in enumerate(reversed(base)):
        d = int(ch)
        if i % 2 == 0:  # rightmost digit and every second one after it are doubled
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10


def is_valid_loinc(code: str) -> bool:
    """True when ``code`` is well-formed *and* its check digit is correct."""
    match = LOINC_PATTERN.match(code)
    return bool(match) and loinc_check_digit(match.group(1)) == int(match.group(2))
