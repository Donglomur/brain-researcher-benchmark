"""Explicit isolated package bootstrap; no cwd or user-site imports."""
from pathlib import Path
import runpy
import sys
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
if len(sys.argv) != 2 or sys.argv[1] not in ('worker', 'provider_worker'):
    raise SystemExit('Exact trusted entry target required')
target = sys.argv[1]; sys.argv = [str(Path(__file__))]
runpy.run_module('program.' + target, run_name='__main__')
