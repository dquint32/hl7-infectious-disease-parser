"""Command-line interface.

    python -m hl7_infectious hl-samples/covid_oru.txt
    python -m hl7_infectious hl-samples/*.txt --json

Exit codes: 0 = parsed cleanly, 1 = parsed with validation errors, 2 = unreadable input.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from . import HL7IngestionError, parse_file, render_text


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="hl7_infectious", description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+", help="HL7 v2 message file(s)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args(argv)

    exit_code = 0
    payload: list[dict] = []
    for path in args.files:
        try:
            reports = parse_file(path)
        except (OSError, HL7IngestionError) as exc:
            print(f"{path}: cannot parse: {exc}", file=sys.stderr)
            exit_code = 2
            continue
        for report in reports:
            if report.has_errors:
                exit_code = max(exit_code, 1)
            if args.json:
                payload.append({"file": path, **report.model_dump(mode="json")})
            else:
                print(f"=== {path}")
                print(render_text(report))
                print()
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
