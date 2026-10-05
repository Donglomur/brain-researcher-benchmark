"""Source-free mechanical tests; generated arrays are fixtures, not task input."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "solution/compute.py"
spec = importlib.util.spec_from_file_location("oracle_mechanics", SCRIPT)
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def test_import_and_method_pin():
    assert oracle.locate_method()["source"]["decim"] == 1


@pytest.mark.parametrize("bad", ["output", "private"])
def test_existing_evidence_preserved(tmp_path, bad):
    out, private = tmp_path / "output", tmp_path / "private"
    target = out if bad == "output" else private
    target.mkdir()
    (target / "evidence").write_text("retain")
    with pytest.raises(FileExistsError):
        oracle.prepare_destinations(out, private)
    assert (target / "evidence").read_text() == "retain"


@pytest.mark.parametrize("relation", ["equal", "nested_output", "nested_private"])
def test_nested_destinations_rejected(tmp_path, relation):
    out, private = tmp_path / "out", tmp_path / "private"
    if relation == "equal":
        private = out
    elif relation == "nested_output":
        out = private / "out"
    else:
        private = out / "private"
    with pytest.raises(ValueError):
        oracle.prepare_destinations(out, private)


def test_symlink_destination_rejected(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    out = tmp_path / "out"
    out.symlink_to(target, target_is_directory=True)
    with pytest.raises(FileExistsError):
        oracle.prepare_destinations(out, tmp_path / "private")


def test_output_primitive_no_overwrite(tmp_path):
    path = tmp_path / "x.json"
    oracle.write_json(path, {"x": 1})
    with pytest.raises(FileExistsError):
        oracle.write_json(path, {"x": 2})
    assert json.loads(path.read_text()) == {"x": 1}


@pytest.mark.parametrize("which", ["output", "private"])
def test_symlink_ancestor_rejected(tmp_path, which):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "linked_parent"
    link.symlink_to(target, target_is_directory=True)
    output, private = tmp_path / "output", tmp_path / "private"
    if which == "output":
        output = link / "new"
    else:
        private = link / "new"
    with pytest.raises(ValueError, match="symlink ancestor"):
        oracle.prepare_destinations(output, private)
    assert list(target.iterdir()) == []


def test_finite_json(tmp_path):
    with pytest.raises(ValueError):
        oracle.write_json(tmp_path / "x.json", {"x": float("nan")})


def test_private_evidence_exclusive_write(tmp_path):
    path = tmp_path / "source_features.npz"
    path.write_bytes(b"preserve")
    with pytest.raises(FileExistsError):
        oracle.save_private(tmp_path,{},np.zeros((1,1)),np.zeros((1,1)),[])
    assert path.read_bytes() == b"preserve"


def test_missing_source_writes_explicit_failure(tmp_path, monkeypatch):
    out, private = tmp_path / "out", tmp_path / "private"
    monkeypatch.setattr("sys.argv",[str(SCRIPT),"--source-dir",str(tmp_path/"missing"),"--output-dir",str(out),"--private-dir",str(private)])
    assert oracle.main() == 1
    for name in ("run_metadata.json","decoding_results.json"):
        result = json.loads((out/name).read_text())
        assert result["status"] == "failed_precondition" and result["reason"]
    assert (out/"findings.md").read_text().strip()


def test_wrong_method_digest(tmp_path):
    path = tmp_path / "method.json"
    path.write_text("{}")
    with pytest.raises(ValueError, match="SHA256"):
        oracle.locate_method(path)


@pytest.mark.parametrize("labels", [[0]*10, [0]*5+[1]*4, [0]*5+[2]*5, []])
def test_infeasible_folds(labels):
    with pytest.raises(ValueError):
        oracle.trial_folds(np.asarray(labels, dtype=int))


def test_fixed_whole_trial_folds():
    labels = np.tile([0, 1], 23)
    folds = oracle.trial_folds(labels)
    np.testing.assert_array_equal(folds, oracle.trial_folds(labels))
    assert set(folds) == set(range(1, 6))
    assert np.bincount(folds)[1:].max()-np.bincount(folds)[1:].min() <= 1


@pytest.mark.parametrize("gap,full,analysis,baseline", [(89,1,0,1),(105,1,0,0),(106,0,0,0),(59,1,1,1)])
def test_inclusive_sample_overlap(gap, full, analysis, baseline):
    counts = oracle.overlap_counts([1000, 1000+gap], np.arange(-30, 76), np.arange(8, 68), np.arange(-30, 1))
    assert counts == {"full_epoch_overlap_pairs":full,"analysis_overlap_pairs":analysis,"prior_analysis_next_baseline_overlap_pairs":baseline}


def test_gradient_matches_finite_difference():
    rng = np.random.default_rng(18)
    X, y = rng.normal(size=(31, 4)), rng.integers(0, 2, 31)
    theta = rng.normal(size=5)
    def loss(t):
        z = X@t[:-1]+t[-1]
        return (np.sum(np.logaddexp(0,z)-y*z)+0.5*np.dot(t[:-1],t[:-1]))/len(y)
    eps = 1e-6
    numeric = np.array([(loss(theta+eps*np.eye(5)[i])-loss(theta-eps*np.eye(5)[i]))/(2*eps) for i in range(5)])
    np.testing.assert_allclose(oracle.mean_gradient(X,y,theta[:-1],theta[-1]),numeric,atol=1e-9,rtol=1e-8)


def test_fit_uses_only_train_scaling_and_converges():
    rng = np.random.default_rng(20)
    X, y = rng.normal(size=(51, 3)), np.tile([0,1],26)[:51]
    X[:, 2] = 7
    test = rng.normal(size=(7,3))+100
    score, model = oracle.fit_one(X,y,test)
    np.testing.assert_allclose(model["scaler_mean"],X.mean(0))
    assert model["scaler_scale"][2] == 1
    assert model["gradient_inf"] <= 1e-9
    np.testing.assert_allclose(score,((test-model["scaler_mean"])/model["scaler_scale"])@model["coef"]+model["intercept"])


def test_equal_below_chance_and_zero_scores_are_valid():
    n, nt = 10, 2
    source = dict(features=np.zeros((n,3,nt)),labels=np.array([0,1]*5),folds=np.repeat(np.arange(1,6),2),
                  retained_event_indices=np.arange(n)+2,analysis_offsets=np.array([8,9]))
    zero = np.zeros((n,nt))
    pred, folds, curve, result = oracle.public_tables(source,{"sfreq_hz":150.0},zero,zero)
    assert result["accuracy"] == 0.5
    assert all(row["predicted_class"] == 0 for row in pred)
    opposite = np.repeat((1-2*source["labels"])[:,None],nt,axis=1)
    assert oracle.public_tables(source,{"sfreq_hz":150.0},opposite,opposite)[-1]["accuracy"] == 0


def test_incomplete_predictions_cannot_succeed():
    source = dict(features=np.zeros((10,3,2)),labels=np.array([0,1]*5),folds=np.repeat(np.arange(1,6),2))
    with pytest.raises(ValueError,match="Incomplete"):
        oracle.public_tables(source,{"sfreq_hz":150},np.full((10,2),np.nan),np.zeros((10,2)))


def test_original_event_clock_baseline_and_full_rate_ptp(tmp_path):
    import mne
    sfreq = 150.15374755859375
    rng = np.random.default_rng(44)
    data = rng.normal(scale=1e-12,size=(2,7000))
    info = mne.create_info(["MEG 0012","MEG 0013"],sfreq,["grad","grad"])
    raw = mne.io.RawArray(data,info,first_samp=100,verbose=False)
    events = np.array([[200+i*150,0,(i%4)+1] for i in range(40)])
    # A full-rate odd-offset artifact must be rejected; no hidden decimation.
    raw._data[0,events[3,0]-raw.first_samp+9] = 1e-9
    root = tmp_path/"MEG/sample"
    root.mkdir(parents=True)
    raw.save(root/"sample_audvis_filt-0-40_raw.fif",fmt="double",verbose=False)
    mne.write_events(root/"sample_audvis_filt-0-40_raw-eve.fif",events,verbose=False)
    source, ledger, sm, support = oracle.construct_source(tmp_path)
    assert support["n_retained_trials"] == 39
    assert ledger[3]["drop_reason"] == "amplitude" and ledger[3]["trial_id"] == ""
    assert source["features"].shape == (39,2,60)
    assert sm["first_samp"] == 100
    np.testing.assert_array_equal(source["analysis_offsets"],np.arange(8,68))
    np.testing.assert_allclose(source["full_epochs"][:,:,:31].mean(2),0,atol=1e-27)
    np.testing.assert_array_equal(source["retained_event_indices"],np.delete(np.arange(40),3))
