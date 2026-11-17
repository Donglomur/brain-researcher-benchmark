"""Generated engineering controls, not observations from the Herber cohort."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from scipy.ndimage import gaussian_filter1d

PATH = Path(__file__).resolve().parents[1] / "evaluator.py"
SPEC = importlib.util.spec_from_file_location("find039_evaluator", PATH)
ev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ev)


def test_epsilon_similarity_and_nonmutation():
    x = np.array([[0., 2.], [2., 0.], [1., 1.]])
    before = x.copy()
    value = 2 / (np.sqrt(2) + 1e-6) ** 2
    np.testing.assert_allclose(ev.source_similarity(x), [[value, -value, 0], [-value, value, 0], [0, 0, 0]], atol=1e-15)
    np.testing.assert_array_equal(x, before)


def test_source_neighbor_window_and_missing_neighbor():
    sim = np.fromfunction(lambda i, j: (i + j) / 30, (13, 13))
    expected = np.mean([np.mean([sim[i, j] for j in range(i - 5, i + 6) if j != i]) for i in (5, 6, 7)])
    assert ev.local_stability(sim) == pytest.approx(expected)
    assert ev.local_stability(np.eye(10)) is None
    sim[5, 0] = np.nan
    expected = np.mean([np.mean([sim[i, j] for j in range(i - 5, i + 6) if j != i]) for i in (6, 7)])
    assert ev.local_stability(sim) == pytest.approx(expected)


def test_count_occupancy_fill_smoothing_and_global_normalization():
    # A first unvisited bin remains zero; a later unvisited bin carries previous.
    counts = np.array([[[0], [4], [0], [2]], [[2], [0], [4], [2]]])
    dwell = np.array([[0, 2, 0, 1], [1, 0, 2, 1]])
    raw_expected = np.array([[[0.], [2.], [2.], [2.]], [[2.], [2.], [2.], [2.]]])
    smooth = gaussian_filter1d(raw_expected, 5, axis=1, mode="wrap")
    expected = (smooth - smooth.min()) / (smooth.max() - smooth.min())
    np.testing.assert_allclose(ev.build_rates(counts, dwell), expected)
    assert np.isnan(ev.build_rates(np.ones((2, 4, 1)), np.ones((2, 4)))).all()


@pytest.mark.parametrize("counts,dwell", [
    (np.zeros((2, 3, 1)), np.array([[0, 1, 1], [0, 1, 1]])),
    (np.ones((2, 3, 1)), np.array([[0, 1, 1], [1, 1, 1]])),
    (np.full((2, 3, 1), .5), np.ones((2, 3))),
])
def test_invalid_occupancy_count_contract(counts, dwell):
    with pytest.raises(ValueError):
        ev.build_rates(counts, dwell)


def test_source_unit_diagonal_subtraction_and_gain_normalization():
    # Analyst-derived control: actual trace removal yields 2.7, source gives 2.35.
    lengths = [2, 3, 2, 1, 3, 0]
    n = sum(lengths)
    sim = np.full((n, n), .25)
    sim[:2, :2] = .6
    np.fill_diagonal(sim[:2, :2], .8)
    sim[2:5, 2:5] = .7
    np.fill_diagonal(sim[2:5, 2:5], .9)
    # Gain row establishes 0 and 1 for whole-matrix normalization.
    sim[7, 0] = sim[0, 7] = 0
    sim[7, 7] = 1
    assert ev.context_specificity(sim, lengths)["block_specificity"] == pytest.approx(2.35)


def test_transfer_ratio_weights_every_trial_pair_not_contexts():
    lengths = [2, 3, 2, 1, 3, 0]
    sim = np.eye(sum(lengths))
    sim[5:7, :2] = .6
    sim[8:11, 2:5] = .8
    sim[8:11, :2] = .2
    sim[5:7, 2:5] = .4
    assert ev.context_specificity(sim, lengths)["transfer_specificity"] == pytest.approx(32 / 13)
    assert all(v is None for v in ev.context_specificity(np.ones((11, 11)), lengths).values())


def make_packet():
    payload = {"task_id": ev.TASK, "source_revision": ev.SOURCE_REVISION, "bin_width_cm": 2, "sessions": []}
    roster = {"task_id": ev.TASK, "source_revision": ev.SOURCE_REVISION,
              "classification_policies": ["frozen_p99", "frozen_p95"], "mice": {}}
    for mouse_id, age in [("y1", "young"), ("y2", "young"), ("a1", "aged"), ("a2", "aged")]:
        segments = ["block_A"] * 6 + ["block_B"] * 6 + ["alternation_A", "alternation_B"] * 6
        trials = [f"trial{i}" for i in range(24)]
        roster["mice"][mouse_id] = {"age_group": age, "sessions": {"s1": {
            "cell_ids": ["c1", "c2"], "trial_ids": trials, "segments": segments,
            "position_bin_ids": list(range(1, 33)),
            "masks": {"frozen_p99": [True, False], "frozen_p95": [True, True]}}}}
        bins = np.arange(32)
        counts = np.empty((24, 32, 2), dtype=int)
        for t, seg in enumerate(segments):
            counts[t, :, 0] = 1 + ((bins + (5 if seg.endswith("B") else 0)) % 13)
            counts[t, :, 1] = 1 + ((bins + t) % 9)
        payload["sessions"].append({"mouse_id": mouse_id, "session_id": "s1", "cell_ids": ["c1", "c2"],
                                     "trial_ids": trials, "spike_counts": counts.tolist(),
                                     "position_bin_ids": list(range(1, 33)),
                                     "occupancy_seconds": np.ones((24, 32)).tolist()})
    return payload, roster


def test_complete_evaluate_and_mask_sensitivity_reproducible():
    payload, roster = make_packet()
    result = ev.evaluate(payload, roster, seed=17, bootstrap_replicates=40)
    assert not result["scientifically_qualified"] and not result["full_contract_complete"]
    assert set(result["classification_sensitivity"]) == {"frozen_p99", "frozen_p95"}
    assert result == ev.evaluate(payload, roster, seed=17, bootstrap_replicates=40)
    assert result["classification_sensitivity"]["frozen_p95"]["sessions"][0]["metrics"]["block_stability"]["n_selected_cells"] == 2
    json.dumps(result, allow_nan=False)
    payload["sessions"].reverse()
    after = ev.evaluate(payload, roster, seed=17, bootstrap_replicates=40)
    assert after["classification_sensitivity"] == result["classification_sensitivity"]


@pytest.mark.parametrize("mutation", ["missing_session", "missing_cell", "missing_bin", "duplicate_session", "missing_policy", "wrong_pin"])
def test_population_and_pin_fail_closed(mutation):
    payload, roster = make_packet()
    if mutation == "missing_session":
        payload["sessions"].pop()
    elif mutation == "missing_cell":
        payload["sessions"][0]["cell_ids"].pop()
    elif mutation == "missing_bin":
        payload["sessions"][0]["position_bin_ids"].pop()
    elif mutation == "duplicate_session":
        payload["sessions"].append(copy.deepcopy(payload["sessions"][0]))
    elif mutation == "missing_policy":
        del roster["mice"]["y1"]["sessions"]["s1"]["masks"]["frozen_p95"]
    else:
        payload["source_revision"] = "wrong"
    with pytest.raises(ValueError):
        ev.evaluate(payload, roster, bootstrap_replicates=0)


def test_mouse_weighting_and_no_complete_case_silence():
    def row(mouse, session, value):
        return {"mouse_id": mouse, "session_id": session,
                "metrics": {k: {"value": value} for k in ev.METRICS}}
    mice = {"m1": {"age_group": "young"}, "m2": {"age_group": "young"}}
    rows = [row("m1", "s1", 1), row("m1", "s2", 3), row("m2", "s1", 10)]
    result = ev.aggregate_mouse_level(rows, mice, seed=3, bootstrap_replicates=40)
    assert result["age_groups"]["young"]["metrics"]["block_stability"]["value"] == 6
    rows[0]["metrics"]["block_stability"]["value"] = None
    result = ev.aggregate_mouse_level(rows, mice, seed=3, bootstrap_replicates=40)
    assert result["age_groups"]["young"]["metrics"]["block_stability"]["value"] is None
    assert result["age_groups"]["young"]["metrics"]["block_stability"]["n_defined_mice"] == 1


def test_cli(tmp_path):
    payload, roster = make_packet()
    inp, ref, out = (tmp_path / n for n in ("input.json", "roster.json", "report.json"))
    inp.write_text(json.dumps(payload)); ref.write_text(json.dumps(roster))
    proc = subprocess.run([sys.executable, str(PATH), str(inp), str(ref), str(out), "--bootstrap-replicates", "20"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(out.read_text())["task_id"] == ev.TASK
