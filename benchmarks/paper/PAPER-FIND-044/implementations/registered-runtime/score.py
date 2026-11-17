#!/usr/bin/env python3
"""Local bridge to the qualified reward-learning numerical-file scorer."""
from pathlib import Path
import runpy
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'authoring/reward-spacing-v1/scoring-runtime-v1'
sys.path.insert(0,str(SOURCE))
runpy.run_path(str(SOURCE/'score.py'),run_name='__main__')
