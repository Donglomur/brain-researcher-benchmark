#!/usr/bin/env python3
"""Local bridge to the qualified TMS processed-table summary scorer."""
from pathlib import Path
import runpy
import sys

sys.dont_write_bytecode=True
# This proposed file is intended for benchmarks/neuroscience/paper-signal-add-021.
ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'authoring/v1-tms-memory-v1/scoring-adapter-v1'
sys.path.insert(0,str(SOURCE))
runpy.run_path(str(SOURCE/'score.py'),run_name='__main__')
