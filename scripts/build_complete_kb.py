#!/usr/bin/env python3
"""Build the complete doctor retrieval corpus KB v2.2."""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.rag.complete import build_complete_bundle

source = ROOT / "data" / "knowledge" / "kb_v2.zip"
output = ROOT / "data" / "knowledge" / "kb_v2_2_complete_doctor"
manifest = build_complete_bundle(source, output)
archive = shutil.make_archive(str(output), "zip", output.parent, output.name)
print(json.dumps(manifest, ensure_ascii=False, indent=2))
print(f"Archive: {archive}")
