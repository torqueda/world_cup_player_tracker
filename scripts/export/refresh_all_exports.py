#!/usr/bin/env python3
"""
Run the full workbook-to-app export pipeline in the correct order:

1. export_master_workbook_to_csv.py   -> data/processed/master_exports/*.csv
2. audit_master_workbook_alignment.py -> alignment summary + birthplace review (strict)
3. export_master_workbook_to_json.py  -> data/processed/app_exports/*.json

The audit runs in strict mode, so a failed integrity check stops the pipeline
before stale or misaligned JSON can reach the app.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent

PIPELINE = [
    ["export_master_workbook_to_csv.py"],
    ["audit_master_workbook_alignment.py", "--strict"],
    ["export_master_workbook_to_json.py"],
]


def main() -> None:
    for step in PIPELINE:
        script, *extra_args = step
        print(f"\n=== Running {script} {' '.join(extra_args)} ===")
        result = subprocess.run([sys.executable, str(SCRIPTS_DIR / script), *extra_args])
        if result.returncode != 0:
            print(f"\nPipeline stopped: {script} exited with status {result.returncode}.")
            sys.exit(result.returncode)
    print("\nAll export steps completed successfully.")


if __name__ == "__main__":
    main()
