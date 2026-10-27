#!/usr/bin/env python3
"""Audit a Clinical Compass knowledge bundle before indexing."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json

from app.rag.audit import audit_bundle, markdown_report

DEFAULT_BUNDLE = Path(__file__).resolve().parents[1] / "data" / "knowledge" / "kb_v2.zip"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 while any blocker or error remains")
    args = parser.parse_args()

    report = audit_bundle(args.source)
    rendered = markdown_report(report)
    print(rendered)

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(rendered, encoding="utf-8")

    if args.strict and (report["summary"]["errors"] or report["summary"]["blockers"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
