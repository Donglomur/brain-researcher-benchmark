#!/usr/bin/env python3
"""Package bridge for the independently qualified local RTT velocity scorer."""
from pathlib import Path
import runpy,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'authoring/rtt-transfer-v1/scoring-adapter-v2'
sys.path.insert(0,str(SOURCE))
runpy.run_path(str(SOURCE/'score.py'),run_name='__main__')
