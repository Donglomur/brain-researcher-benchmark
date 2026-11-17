"""Run the four delivery/lifecycle packages' generated portable controls in CI.

These software tests do not run candidates, load authentic private assets, or
qualify a scientific endpoint. Numerical/native preparation checks remain in
the packages and are documented separately.
"""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SUITES = {
    "cardiac_delivery": "benchmarks/paper/PAPER-ROOT-ADD-016/implementations/candidate-delivery-v1/test_delivery.py",
    "opto_delivery": "benchmarks/paper/PAPER-FIND-REP-003/implementations/authentic-delivery-v1/tests/test_contract.py",
    "neural077_direct": "benchmarks/neural/NEURAL-077/implementations/complete-direct-condition-v1/test_portable.py",
    "frozen_lifecycle": "benchmarks/shared/frozen-neural-lifecycle-v1/tests/test_lifecycle.py",
}


def load_tests(loader, standard_tests, pattern):
    result = unittest.TestSuite()
    for name, relative in SUITES.items():
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("Missing ordinary package control: " + relative)
        module_name = "_next_wave_controls_" + name
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        suite = loader.loadTestsFromModule(module)
        if suite.countTestCases() == 0:
            raise RuntimeError("Package control discovered no tests: " + relative)
        result.addTests(suite)
    return result
