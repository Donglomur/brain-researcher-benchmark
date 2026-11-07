#!/usr/bin/env python3
"""Proposed installed bridge; source-only until root admission/installation."""
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
if Path(__file__).resolve() != ROOT / 'benchmarks/neuroscience/paper-find-003/score_capacity_v1.py':
    raise RuntimeError('Capacity bridge requires its exact reviewed installation path')
os.execv(sys.executable, [sys.executable, str(ROOT / 'authoring/task-capacity-successors-20261102/human-ripple/score.py'), *sys.argv[1:]])
