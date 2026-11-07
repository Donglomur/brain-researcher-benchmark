#!/usr/bin/env python3
"""ERP capacity successor dispatcher; exact task source admission remains mandatory."""
from pathlib import Path
import runpy,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
runpy.run_path(str(ROOT/'authoring/task-capacity-successors-20261102/erp/score.py'),run_name='__main__')
