#!/usr/bin/env python3
"""Create the normalized doctor-only KB v2.1 release."""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.rag.normalize import normalize_bundle

DEFAULT_SOURCE = ROOT / "data" / "knowledge" / "kb_v2.zip"
DEFAULT_OUTPUT = ROOT / "data" / "knowledge" / "kb_v2_1_doctor"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--zip", action="store_true", help="Also create a zip archive next to the output directory")
    args = parser.parse_args()
    manifest = normalize_bundle(args.source, args.output)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if args.zip:
        archive = shutil.make_archive(str(args.output), "zip", args.output.parent, args.output.name)
        print(f"Archive: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
