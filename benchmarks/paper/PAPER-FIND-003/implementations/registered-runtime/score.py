#!/usr/bin/env python3
"""Installed common-CLI bridge to the frozen local ordinary artifact scorer."""
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
if Path(__file__).resolve()!=ROOT/'benchmarks/neuroscience/paper-find-003/score.py':
    raise RuntimeError('Bridge requires its exact reviewed installation path')
os.execv(sys.executable,[sys.executable,str(ROOT/'authoring/human-ripple-learning-v1/mixed-model-scorer-cli-v1/score.py'),*sys.argv[1:]])
