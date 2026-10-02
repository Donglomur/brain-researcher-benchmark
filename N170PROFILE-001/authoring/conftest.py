"""Authoring-only installed-code paths; no original-data IO or reconstruction.

Production tests/conftest.py owns the separately scoped original_reference
fixture. These manufactured tests never request it. Private code has import
precedence; oracle and stager fixtures explicitly name their installed files.
"""
from pathlib import Path
import sys


TASK_ROOT = Path(__file__).resolve().parents[1]
AUTHORING = TASK_ROOT / 'authoring'
PRIVATE_TESTS = TASK_ROOT / 'tests'
SOLUTION = TASK_ROOT / 'solution'
ENVIRONMENT = TASK_ROOT / 'environment'
for code_path in reversed((PRIVATE_TESTS, SOLUTION, ENVIRONMENT, AUTHORING)):
    text = str(code_path)
    if text in sys.path:
        sys.path.remove(text)
    sys.path.insert(0, text)
