"""Exercise the sleep witness controls in the existing NumPy CI environment."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTROL = ROOT / "benchmarks/neural/NEURAL-007/implementations/finite-attempt-audit/tests/test_audit.py"


def load_tests(loader, standard_tests, pattern):
    if CONTROL.is_symlink() or not CONTROL.is_file():
        raise RuntimeError("Missing ordinary sleep attempt audit control")
    name = "_sleep_attempt_audit_numerical_controls"
    spec = importlib.util.spec_from_file_location(name, CONTROL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    suite = loader.loadTestsFromModule(module)
    if suite.countTestCases() == 0:
        raise RuntimeError("Sleep attempt audit discovered no tests")
    return suite
