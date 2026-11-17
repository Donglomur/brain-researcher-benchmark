#!/usr/bin/env python3
"""Qualified local ERP summary scorer; no candidate program is executed."""
from pathlib import Path
import runpy
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
runpy.run_path(str(ROOT / 'authoring/reward-emotion-erp/scoring-adapter-v1/run_outer.py'), run_name='__main__')
