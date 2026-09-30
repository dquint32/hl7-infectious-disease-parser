"""Backwards-compatible entry point: ``python parser.py <hl7_file> [--json]``.

The logic now lives in the ``hl7_infectious`` package (ingestion / validation /
transformation). See README for details.
"""

from hl7_infectious.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
