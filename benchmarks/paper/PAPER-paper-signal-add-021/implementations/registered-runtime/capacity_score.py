#!/usr/bin/env python3
"""Staged package facade for the reviewed TMS capacity successor; not installed."""
from pathlib import Path
import runpy
import sys

sys.dont_write_bytecode = True
# Intended destination: benchmarks/neuroscience/paper-signal-add-021/capacity_score.py.
ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'authoring/task-capacity-successors-20261102/tms'
sys.path.insert(0, str(SOURCE))
runpy.run_path(str(SOURCE / 'score.py'), run_name='__main__')
