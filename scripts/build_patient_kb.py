#!/usr/bin/env python3
"""Build the isolated patient-facing prototype corpus."""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.rag.patient_corpus import DEFAULT_OUTPUT, build_patient_corpus

manifest = build_patient_corpus()
archive = shutil.make_archive(str(DEFAULT_OUTPUT), "zip", DEFAULT_OUTPUT.parent, DEFAULT_OUTPUT.name)
print(json.dumps(manifest, ensure_ascii=False, indent=2))
print(f"Archive: {archive}")
