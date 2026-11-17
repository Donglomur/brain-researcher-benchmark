#!/usr/bin/env python3
"""Local package bridge to the qualified Figure 2C numerical-file scorer."""
from pathlib import Path
import runpy
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'authoring/sequence-filtering-v1/scoring-adapter-v2'
sys.path.insert(0, str(SOURCE))
runpy.run_path(str(SOURCE / 'score.py'), run_name='__main__')
