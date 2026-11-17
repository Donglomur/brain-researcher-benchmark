"""Generated engineering controls only; no authentic neuroscience observations."""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

MODULE = Path(__file__).resolve().parents[1] / "sensor_rsa.py"
spec = importlib.util.spec_from_file_location("sensor_rsa", MODULE)
rsa = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rsa
spec.loader.exec_module(rsa)


def test_two_run_cross_products_and_negative_estimates():
    x = np.array([[[1], [2]], [[0], [0]], [[3], [4]], [[0], [0]]])
    labels, runs = ["a", "b", "a", "b"], ["1", "1", "2", "2"]
    got, _ = rsa.crossnobis(x, labels, runs, shape_order=("a", "b"))
    assert got.item() == 5.5
    x[2] = [[-1], [-2]]
    got, _ = rsa.crossnobis(x, labels, runs, shape_order=("a", "b"))
    assert got.item() == -2.5


def test_reference_smoothing_preserves_quadratic_and_no_mutation():
    time = np.linspace(-1, 1, 31)
    curve = 1 + time + time**2
    x = np.stack([curve, np.zeros(31), curve * 2, np.zeros(31)])[:, None, :]
    original = x.copy()
    unsmoothed, _ = rsa.crossnobis(x, ["a", "b"] * 2, ["1"] * 2 + ["2"] * 2,
                                 shape_order=("a", "b"))
    smoothed, _ = rsa.crossnobis(x, ["a", "b"] * 2, ["1"] * 2 + ["2"] * 2,
                               shape_order=("a", "b"), smooth=True)
    np.testing.assert_allclose(smoothed, unsmoothed, rtol=1e-12)
    np.testing.assert_array_equal(x, original)


@pytest.mark.parametrize("mutator", [
    lambda x, s, r: (x[:3], s[:3], r[:3]),
    lambda x, s, r: (x, s, ["1"] * 4),
    lambda x, s, r: (np.full_like(x, np.nan), s, r),
    lambda x, s, r: (x, ["a", "c", "a", "b"], r),
])
def test_invalid_folds_and_labels_fail(mutator):
    args = mutator(np.ones((4, 2, 31)), ["a", "b", "a", "b"], ["1", "1", "2", "2"])
    with pytest.raises(ValueError):
        rsa.crossnobis(*args, shape_order=("a", "b"))


def test_whitened_correlation_and_scaling():
    x = np.arange(6.)
    y = np.array([1., 0, 4, 2, 8, 3])
    got = rsa.corr_cov(x[None], y[None], n_shapes=4).item()
    assert got == pytest.approx(0.5765999761251577)
    assert abs(got - np.corrcoef(x, y)[0, 1]) > 0.02
    assert rsa.corr_cov((x * 1e-30)[None], (y * 2 + 100)[None], n_shapes=4).item() == pytest.approx(got)
    assert rsa.corr_cov(x[None], -x[None], n_shapes=4).item() == pytest.approx(-1)
    with pytest.raises(ValueError, match="constant"):
        rsa.corr_cov(np.ones((1, 6)), y[None], n_shapes=4)


def test_finite_extreme_correlation_does_not_overflow():
    x = np.array([[1e308, 1e308, -1e308]])
    result = rsa.corr_cov(x, x, n_shapes=3)
    assert result.item() == pytest.approx(1)


def test_native_cluster_adapter_negative_control():
    pytest.importorskip("mne")
    values = np.random.default_rng(51).uniform(-.8, -.4, (20, 301, 2))
    with pytest.warns(RuntimeWarning, match="No clusters found"):
        result = rsa.cluster_inference(values, seed=3)
    assert result["seed_policy"] == "prospective reproducibility choice"
    for model, row in enumerate(result["results"]):
        x = values[:, 25:226, model]
        np.testing.assert_allclose(row["t_statistics"], x.mean(0) / (x.std(0, ddof=1) / np.sqrt(20)))
        assert row["clusters"] == []
        assert row["null_max_cluster_statistics"] == []


def test_native_cluster_undefined_statistics_reject():
    with pytest.raises(ValueError, match="zero subject variance"):
        rsa.cluster_inference(np.zeros((20, 301, 2)), seed=1)
    with pytest.raises(ValueError, match="lie in"):
        rsa.cluster_inference(np.full((20, 301, 2), 2.0))
    with pytest.raises(ValueError, match="seed"):
        rsa.cluster_inference(np.zeros((20, 301, 2)), seed=True)


def make_packet(tmp_path):
    models = {"shape_order": list(rsa.SHAPES), "models": {}}
    positions = np.arange(11.)
    for name, feature in (("symbolic", positions), ("visual_cnn", positions**2)):
        models["models"][name] = {"source": "generated_engineering_control",
                                  "matrix": ((feature[:, None] - feature[None, :])**2).tolist()}
    model_path = tmp_path / "models.json"
    model_path.write_text(json.dumps(models))
    packet = {"source_revision": rsa.SOURCE_REVISION,
              "models": {"path": "models.json", "sha256": rsa.digest(model_path)}, "subjects": []}
    for subject in rsa.SUBJECTS:
        labels = np.tile(rsa.SHAPES, len(rsa.RUNS[subject]))
        runs = np.repeat(rsa.RUNS[subject], len(rsa.SHAPES))
        shape_codes = np.tile(positions, len(rsa.RUNS[subject]))
        curves = 1 + 0.2 * np.sin(rsa.TIMES * 4)
        data = np.stack([shape_codes[:, None] * curves, shape_codes[:, None]**2 * curves], axis=1)
        path = tmp_path / f"{subject}.npz"
        np.savez(path, data=data, shapes=labels, runs=runs, times=rsa.TIMES,
                 channel_names=np.array(["generated_mag_1", "generated_mag_2"]),
                 subject=np.array(subject), representation=np.array("reference_mne_virtual_magnetometers"))
        packet["subjects"].append({"subject": subject, "path": path.name, "sha256": rsa.digest(path)})
    manifest = tmp_path / "packet.json"
    manifest.write_text(json.dumps(packet))
    return manifest, packet


def test_full_population_pipeline_and_nonqualification(tmp_path):
    manifest, _ = make_packet(tmp_path)
    report = rsa.evaluate(manifest)
    assert len(report["subjects"]) == 20
    assert sum(len(row["reference_trial_counts"]) for row in report["coverage"]) == 158
    assert report["scientifically_qualified"] is False
    assert report["full_contract_complete"] is False
    assert len(report["holds"]) >= 8
    for mode in report["results"].values():
        assert np.array(mode["subject_rdms"]).shape == (20, 301, 55)
        assert np.array(mode["subject_model_corr_cov"]).shape == (20, 301, 2)
        np.testing.assert_allclose(mode["sem_model_corr_cov"], 0, atol=1e-15)
    json.dumps(report, allow_nan=False)


def test_population_and_integrity_fail_closed(tmp_path):
    manifest, packet = make_packet(tmp_path)
    packet["subjects"].pop()
    manifest.write_text(json.dumps(packet))
    with pytest.raises(ValueError, match="20-subject"):
        rsa.evaluate(manifest)
    packet["subjects"].append(packet["subjects"][0].copy())
    manifest.write_text(json.dumps(packet))
    with pytest.raises(ValueError, match="20-subject"):
        rsa.evaluate(manifest)


def test_changed_model_checksum_rejected(tmp_path):
    manifest, _ = make_packet(tmp_path)
    (tmp_path / "models.json").write_text("{}")
    with pytest.raises(ValueError, match="SHA-256"):
        rsa.evaluate(manifest)


def test_source_time_and_run_roster_enforced(tmp_path):
    _, packet = make_packet(tmp_path)
    path = tmp_path / packet["subjects"][9]["path"]
    with np.load(path) as f:
        fields = {k: f[k] for k in f.files}
    fields["runs"][0] = "08"
    np.savez(path, **fields)
    with pytest.raises(ValueError, match="roster"):
        rsa.load_subject(path, "sub-10")
    fields["runs"][0] = "01"
    fields["times"] = fields["times"] + .001
    np.savez(path, **fields)
    with pytest.raises(ValueError, match="250 Hz"):
        rsa.load_subject(path, "sub-10")


def test_csv_import_reorders_both_axes_and_does_not_overwrite(tmp_path):
    order = list(reversed(rsa.SHAPES))
    values = {s: i for i, s in enumerate(rsa.SHAPES)}
    path = tmp_path / "model.csv"
    text = "," + ",".join(order) + "\n"
    for s in order:
        text += s + "," + ",".join(str((values[s] - values[t])**2) for t in order) + "\n"
    path.write_text(text)
    dest = tmp_path / "models.json"
    rsa.import_models(path, path, dest)
    m, _ = rsa.read_models(dest)
    assert m[0, 0] == 1
    assert m[0, 9] == 100
    with pytest.raises(FileExistsError):
        rsa.import_models(path, path, dest)
