"""Generated controls for companion delivery and clock audit sources.

No Docker dispatch, authentic data, private target, model or scientific run.
"""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SUITES = {
    "portable_grading": "benchmarks/neural/NEURAL-077/implementations/portable-grading/test_portable_grading.py",
    "native_clock_audit": "benchmarks/paper/PAPER-FIND-REP-003/implementations/initial-evaluator-v1/tests/test_native_clock_audit.py",
}


def load_tests(loader, standard_tests, pattern):
    result = unittest.TestSuite()
    for name, relative in SUITES.items():
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("Missing ordinary package control: " + relative)
        module_name = "_delivery_companion_controls_" + name
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        suite = loader.loadTestsFromModule(module)
        if suite.countTestCases() == 0:
            raise RuntimeError("Package control discovered no tests: " + relative)
        result.addTests(suite)
    return result
