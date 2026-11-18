"""Enroll NEURAL-036's generated projection controls in numerical CI."""
import importlib.util
from pathlib import Path


def load_tests(loader, tests, pattern):
    path = (Path(__file__).resolve().parents[2] / "benchmarks" / "neural" /
            "NEURAL-036" / "implementations" / "source-projection-v1" /
            "test_projection.py")
    spec = importlib.util.spec_from_file_location("neural036_projection_controls", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return loader.loadTestsFromModule(module)
