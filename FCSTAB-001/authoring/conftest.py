"""Expose only this task's reviewed modules to source-free authoring fixtures."""
from pathlib import Path
import sys

TASK = Path(__file__).resolve().parents[1]
for directory in (TASK/'solution', TASK/'environment', TASK/'tests'):
    sys.path.insert(0, str(directory))
