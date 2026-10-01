"""Verifier fixtures use the retained reference for grading tests, not scientific validation."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("moviesync_grader", ROOT / "tests/test_outputs.py")
grader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grader)


@pytest.fixture
def reference_rows(monkeypatch):
    ref = grader._reference()
    rows = {i: (ref["pairwise"][i], ref["loo"][i]) for i in ref["ids"]}
    monkeypatch.setattr(grader, "_submitted", lambda: (rows, True, True))
    return ref


@pytest.mark.parametrize("estimator,column", [("pairwise", "pairwise"), ("loo", "loo")])
def test_both_legitimate_estimators(monkeypatch, reference_rows, estimator, column):
    monkeypatch.setattr(grader, "_metadata", lambda: {"isc_estimator": estimator})
    monkeypatch.setattr(grader, "_results", lambda: {"visual_isc": reference_rows["stats"][column]})
    for name in dir(grader):
        if name.startswith("test_"):
            getattr(grader, name)()


@pytest.mark.parametrize("estimator", [None, "custom", "loo"])
def test_missing_unknown_and_mislabeled_fail(monkeypatch, reference_rows, estimator):
    monkeypatch.setattr(grader, "_metadata", lambda: {"isc_estimator": estimator})
    monkeypatch.setattr(grader, "_results", lambda: {"visual_isc": reference_rows["stats"]["pairwise"]})
    with pytest.raises(AssertionError):
        grader.test_headline_matches_declared_estimator()


def test_duplicate_ids_fail(tmp_path):
    path = tmp_path / "rows.csv"
    path.write_text("subject,isc_pairwise\nsub-001,0.1\nsub-001,0.2\n")
    with pytest.raises(AssertionError, match="duplicate"):
        grader.pw.load_submitted(path)
