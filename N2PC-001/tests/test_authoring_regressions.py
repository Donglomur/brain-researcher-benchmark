"""Authoring-only regression fixtures, not evidence of raw-data execution."""
import importlib.util
from pathlib import Path

import pytest

from measurement_contract import SUBJECTS, summarize


def test_signed_complete_subject_measurements():
    rows = [dict(subject=s, n_left_trials=10, n_right_trials=11, contra_uv=-s / 10,
                 ipsi_uv=0, n2pc_uv=-s / 10, fixed_po8_minus_po7_pooled_uv=0)
            for s in sorted(SUBJECTS)]
    assert summarize(rows)["n_left_target_trials_total"] == 120
    for corrupt in (lambda r: r.pop(), lambda r: r.append(dict(r[0])),
                    lambda r: r[0].update(n2pc_uv=0.1),
                    lambda r: r[0].update(n_right_trials=1.5)):
        bad = [dict(row) for row in rows]
        corrupt(bad)
        with pytest.raises(AssertionError):
            summarize(bad)


def test_explicit_cache_requires_fdt(tmp_path):
    path = Path(__file__).parents[1] / "solution" / "cache_contract.py"
    spec = importlib.util.spec_from_file_location("cache_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "sub-001_task-N2pc_eeg.set").write_bytes(b"header")
    with pytest.raises(FileNotFoundError, match="fdt"):
        module.require_pairs(tmp_path, [1])
    (tmp_path / "sub-001_task-N2pc_eeg.fdt").write_bytes(b"data")
    assert len(module.require_pairs(tmp_path, [1])) == 2
