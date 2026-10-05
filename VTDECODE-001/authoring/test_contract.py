"""Isolated arithmetic/API checks; these are not scientific reference outputs."""
import ast
import importlib.util
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("haxby_contract", ROOT / "tests/prediction_contract.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


@pytest.mark.parametrize("value", ["0", "1.0", " 11 ", 72, np.int64(864)])
def test_integer_accepts_equivalent_numeric_formats(value):
    assert contract.integer(value) == int(float(value))


@pytest.mark.parametrize("value", [True, "1.1", -1, "nan", "inf"])
def test_integer_rejects_nonfinite_fractional_or_boolean_values(value):
    with pytest.raises(AssertionError):
        contract.integer(value)


def test_oracle_masker_runs_are_constructor_configuration():
    """Exercise the real masker calls against the pinned public API shape."""
    source = ROOT / "solution/compute.py"
    tree = ast.parse(source.read_text())
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    selected = [node for node in main.body if isinstance(node, ast.Assign) and
                isinstance(node.value, ast.Call) and
                ((isinstance(node.value.func, ast.Name) and node.value.func.id == "NiftiMasker") or
                 (isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "fit_transform"))]
    assert len(selected) == 2
    calls = []
    runs = np.array([0, 0, 1, 1])

    class MaskerAPI:
        def __init__(self, *, runs, **kwargs):
            calls.append(runs)

        def fit_transform(self, imgs, y=None, confounds=None, sample_mask=None):
            return "extracted"

    namespace = dict(NiftiMasker=MaskerAPI, runs=runs, mask_vt="mask", func="image")
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), "exec"), namespace)
    assert calls[0] is runs and namespace["X"] == "extracted"
