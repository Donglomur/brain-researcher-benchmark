#!/usr/bin/env python3
"""Local isolated score adapter; source-only pending qualification."""
from pathlib import Path
import runpy
import sys
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'authoring/astrocyte-sequences/scoring-adapter-v1'
sys.path.insert(0, str(SOURCE))
runpy.run_path(str(SOURCE / 'run_outer.py'), run_name='__main__')
