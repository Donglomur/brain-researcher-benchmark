#!/usr/bin/env python3
"""Run the current repository framework without an installation step."""
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

if __name__ == "__main__":
    runpy.run_module("neurobench.paired_study", run_name="__main__")
