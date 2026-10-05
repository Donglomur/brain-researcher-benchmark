"""Bounded synthetic mechanics only; never read the original EEG bundle."""
import importlib.util
import json
from pathlib import Path
import sys
import warnings

import mne
import numpy as np
import pytest
from scipy.io import savemat
from scipy.signal import fftconvolve

TASK = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("n400_oracle_mechanics", TASK / "solution/compute.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def event(code, sample, **kwargs):
    return {"type": code, "latency": sample + 1, **kwargs}


def lowpass(length, cutoff):
    n = np.arange(length, dtype=np.float64)
    h = (2 * cutoff / 256) * np.sinc((2 * cutoff / 256) * (n - (length - 1) / 2))
    h *= .54 - .46 * np.cos(2 * np.pi * n / (length - 1))
    return h / h.sum()


def analytic_taps():
    h = -lowpass(8449, .05)
    h[4168:4281] += lowpass(113, 33.75)
    return h


def explicit_filter(x):
    h = analytic_taps()
    e = min(len(h), len(x)) - 1
    return fftconvolve(np.pad(x, (e, e), mode="edge"), h, mode="full")[e + 4224:e + 4224 + len(x)]


@pytest.mark.parametrize("code,role,condition", [
    (211, "target", "related"), (212, "target", "related"),
    (221, "target", "unrelated"), (222, "target", "unrelated"),
    (111, "prime", "related"), (112, "prime", "related"),
    (121, "prime", "unrelated"), (122, "prime", "unrelated"),
    (201, "response", ""), (202, "response", ""), (999, "other", ""),
])
def test_original_roles(code, role, condition):
    rows, _ = oracle.event_ledger(1, [event(code, 100)], 1000)
    assert rows[0]["role"] == role
    assert rows[0]["condition"] == condition
    assert rows[0]["retained"] == int(role == "target")


@pytest.mark.parametrize("latency,sample", [(101.25, 100), (101.5, 100), (102.5, 102), (101.75, 101)])
def test_original_clock_nearest_even_no_second_shift(latency, sample):
    rows, _ = oracle.event_ledger(1, [{"type": 211, "latency": latency}], 1000)
    assert rows[0]["latency_samples"] == latency
    assert rows[0]["event_sample"] == sample


def test_no_digit_stripping_or_prime_pooling():
    rows, _ = oracle.event_ledger(1, [event("label211", 100), event("211.0", 101), event(111, 102)], 1000)
    assert [r["role"] for r in rows] == ["other", "other", "prime"]
    assert all(r["retained"] == 0 for r in rows)


@pytest.mark.parametrize("bad", [True, 211.1, float("nan"), [211]])
def test_invalid_event_type_fails(bad):
    with pytest.raises(ValueError):
        oracle.canonical_type(bad)


@pytest.mark.parametrize("value,status", [(None, "empty"), ([], "empty"), (float("nan"), "nonfinite"), (float("inf"), "nonfinite"), (0, "finite")])
def test_duration_null_is_not_zero(value, status):
    number, got = oracle.duration({"duration": value})
    assert got == status
    assert number == (0 if status == "finite" else "")
    assert oracle.duration({}) == ("", "absent")


def test_boundary_half_sample_durations_and_duplicate_rows():
    original = [
        {"type": "boundary", "latency": .5, "duration": 100},
        {"type": -99, "latency": 1000.5, "duration": 1_000_000},
        {"type": "boundary", "latency": 1000.5, "duration": np.nan},
        {"type": "boundary", "latency": 2000.5},
        event(211, 794), event(212, 795), event(221, 1051), event(222, 1050),
    ]
    rows, segments = oracle.event_ledger(1, original, 2000)
    assert len(rows) == 8 and len(segments) == 2
    assert [r["boundary_cut_sample"] for r in rows[:4]] == [0, 1000, 1000, 2000]
    assert all(r["event_sample"] == "" for r in rows[:4])
    assert [r["retained"] for r in rows[4:]] == [1, 0, 1, 0]
    assert rows[5]["drop_reason"] == rows[7]["drop_reason"] == "boundary_crossing"
    assert rows[7]["segment_id"] == 1  # Anchor segment, not epoch eligibility.


@pytest.mark.parametrize("latency", [100, 100.25, -.5, 2001.5, np.nan])
def test_ambiguous_or_external_boundary_fails(latency):
    with pytest.raises(ValueError):
        oracle.event_ledger(1, [{"type": "boundary", "latency": latency}], 2000)


def test_out_of_data_precedes_boundary_and_no_event_sorting():
    rows, _ = oracle.event_ledger(1, [event(222, 1800), event(211, 20), {"type": "boundary", "latency": 30.5}], 2000)
    assert [r["event_index"] for r in rows] == [0, 1, 2]
    assert rows[0]["drop_reason"] == rows[1]["drop_reason"] == "out_of_data"


def test_duplicate_target_samples_fail_but_nontarget_collision_survives():
    with pytest.raises(ValueError, match="Duplicate"):
        oracle.event_ledger(1, [event(211, 100), event(221, 100.25)], 1000)
    rows, _ = oracle.event_ledger(1, [event(211, 100), event(201, 100)], 1000)
    assert len(rows) == 2 and rows[0]["retained"] == 1


def test_explicit_fir_matches_actual_pinned_mne_coefficients():
    np.testing.assert_allclose(oracle.filter_coefficients(), analytic_taps(), rtol=2e-14, atol=2e-16)


@pytest.mark.parametrize("length", [1, 257, 8449, 9000])
def test_filter_reference_and_short_segment_padding(length):
    x = np.random.default_rng(10).normal(size=(3, length))
    segments = [{"start_sample": 0, "end_sample_exclusive": length}]
    if length < 8449:
        with pytest.warns(RuntimeWarning, match="filter_length"):
            got = oracle.filter_segments(x, segments)
    else:
        got = oracle.filter_segments(x, segments)
    expected = explicit_filter(x[0] - (x[1] + x[2]) / 2)
    np.testing.assert_allclose(got, expected, rtol=2e-12, atol=2e-12)


def test_filter_never_bridges_source_boundary():
    rng = np.random.default_rng(11)
    x = rng.normal(size=(3, 1000))
    x[:, 500:] += np.array([1000, -400, 900])[:, None]
    segments = [{"start_sample": 0, "end_sample_exclusive": 500},
                {"start_sample": 500, "end_sample_exclusive": 1000}]
    with pytest.warns(RuntimeWarning, match="filter_length"):
        got = oracle.filter_segments(x, segments)
    reference = x[0] - (x[1] + x[2]) / 2
    expected = np.r_[explicit_filter(reference[:500]), explicit_filter(reference[500:])]
    np.testing.assert_allclose(got, expected, rtol=1e-10, atol=1e-10)
    assert np.max(np.abs(got - explicit_filter(reference))) > 1


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_nonfinite_required_channels_fail(bad):
    x = np.zeros((3, 1000)); x[2, 30] = bad
    with pytest.raises(ValueError, match="finite"):
        oracle.filter_segments(x, [{"start_sample": 0, "end_sample_exclusive": 1000}])


def measured_fixture(sign=1):
    original = [event(211, 500), event(221, 1500), event(212, 2500), event(222, 20), event(111, 1000)]
    rows, segments = oracle.event_ledger(1, original, 3000)
    x = np.full(3000, 7.0)
    x[500 + np.arange(77, 129)] += 2
    x[1500 + np.arange(77, 129)] += 2 + sign * 5
    x[2500 + np.arange(77, 129)] += 2
    return oracle.measure_subject(1, x, rows), rows, segments


@pytest.mark.parametrize("sign", [-1, 1])
def test_signed_trials_curves_and_dropped_rows(sign):
    measured, _, _ = measured_fixture(sign)
    assert len(measured["trials"]) == 4
    assert measured["trials"][3]["baseline_uv"] == ""
    assert measured["subject"]["n400_uv"] == sign * 5
    assert measured["subject"]["n_unrelated_dropped"] == 1
    assert measured["trials"][0]["baseline_uv"] == 7
    assert measured["trials"][0]["window_raw_mean_uv"] == 9
    assert measured["trials"][0]["window_baseline_corrected_uv"] == 2
    curve = np.array([r["difference_uv"] for r in measured["curves"]])
    assert curve.shape == (257,) and np.mean(curve[oracle.MEASUREMENT]) == sign * 5
    assert oracle.OFFSETS[oracle.BASELINE].tolist() == list(range(-51, 1))
    assert oracle.OFFSETS[oracle.MEASUREMENT].tolist() == list(range(77, 129))


def test_empty_condition_is_failed_precondition():
    rows, _ = oracle.event_ledger(1, [event(211, 500)], 1000)
    with pytest.raises(ValueError, match="empty retained"):
        oracle.measure_subject(1, np.zeros(1000), rows)


def test_equal_subject_weight_and_descriptive_signs():
    row = measured_fixture(-1)[0]["subject"]
    other = dict(row, subject=2, n400_uv=10.0, unrelated_uv=12.0, n_related_retained=100)
    result = oracle.summarize([row, other])
    assert result["n400_difference_amplitude_uv"] == 2.5
    assert result["n_subjects_negative"] == result["n_subjects_positive"] == 1


def test_synthetic_set_fdt_reader_unit_order_and_header(tmp_path):
    n = 1000
    values = (np.arange(33 * n).reshape(33, n) / 10).astype("<f4")
    fdt = tmp_path / "1_N400_shifted_ds.fdt"
    with fdt.open("wb") as stream:
        stream.write(values.tobytes(order="F"))
    eeg = {"pnts": n, "nbchan": 33, "srate": 256, "trials": 1,
           "data": fdt.name, "datfile": fdt.name, "ref": "common", "xmin": 0,
           "xmax": (n - 1) / 256, "history": "synthetic only\n",
           "chanlocs": np.array([{"labels": name} for name in oracle.CHANNELS], dtype=object),
           "event": np.array([event(211, 100), event(221, 600)], dtype=object),
           **{name: np.array([]) for name in ("icaweights", "icasphere", "icawinv", "icachansind")}}
    set_path = tmp_path / "1_N400_shifted_ds.set"
    savemat(set_path, {"EEG": eeg})
    header = oracle.load_subject_header(1, set_path, fdt)
    assert header["observed"]["duration_fields_present"] is False
    assert header["observed"]["readout_channel_indices"] == {"CPz": 14, "P9": 8, "P10": 26}
    raw = mne.io.read_raw_eeglab(set_path, preload=False, verbose=False)
    got = raw.get_data(picks=list(oracle.READOUT)) * 1e6
    np.testing.assert_allclose(got, values[[14, 8, 26]].astype(np.float64), atol=1e-12, rtol=1e-14)


def test_eight_public_files_private_separate_and_deterministic(tmp_path):
    measured, source_rows, segments = measured_fixture()
    contract = json.loads((TASK / "environment/method_contract.json").read_text())
    tables = {"source_events.csv": source_rows, "segments.csv": segments,
              "trial_measurements.csv": measured["trials"], "curves.csv": measured["curves"],
              "per_subject.csv": [measured["subject"]]}
    results = oracle.summarize(tables["per_subject.csv"], "resource_pilot")
    meta = oracle.make_metadata({"contract": contract, "source_sha256": {}}, [], "resource_pilot")
    for name in ("one", "two"):
        out = oracle.prepare_directory(tmp_path / name / "public")
        private = oracle.prepare_directory(tmp_path / name / "private")
        oracle.write_outputs(out, private, tables, results, meta, {"fixture": np.array([1, 2])})
        assert set(p.name for p in out.iterdir()) == set(contract["outputs"])
        assert set(p.name for p in private.iterdir()) == {"analysis_arrays.npz"}
    assert (tmp_path / "one/private/analysis_arrays.npz").read_bytes() == (tmp_path / "two/private/analysis_arrays.npz").read_bytes()
    for path in (tmp_path / "one/public").iterdir():
        assert path.read_bytes() == (tmp_path / "two/public" / path.name).read_bytes()


def test_refuse_existing_evidence_and_symlinks(tmp_path):
    folder = oracle.prepare_directory(tmp_path / "saved")
    (folder / "keep").write_text("untouched")
    with pytest.raises(FileExistsError):
        oracle.prepare_directory(folder)
    alias = tmp_path / "alias"; alias.symlink_to(folder)
    with pytest.raises(FileExistsError):
        oracle.prepare_directory(alias)
    assert (folder / "keep").read_text() == "untouched"


def test_failed_input_produces_explicit_nonempty_failure_artifacts(tmp_path, monkeypatch):
    out, private = tmp_path / "output", tmp_path / "private"
    monkeypatch.setattr(sys, "argv", ["compute.py", "--data-dir", str(tmp_path / "absent"),
                                     "--output-dir", str(out), "--private-dir", str(private)])
    with pytest.raises(FileNotFoundError):
        oracle.main()
    assert json.loads((out / "n400.json").read_text())["status"] == "failed_precondition"
    assert (out / "findings.md").read_text().strip()
    assert (private / "failure.json").is_file()


def test_pinned_public_method_identity():
    assert oracle.sha256(TASK / "environment/method_contract.json") == oracle.METHOD_SHA256
    assert oracle.sha256(TASK / "environment/data_manifest.json") == oracle.MANIFEST_SHA256


def test_warnings_remain_visible_and_retained_on_failure():
    retained = []
    with pytest.warns(UserWarning, match="synthetic warning"):
        with pytest.raises(ValueError, match="synthetic failure"):
            with oracle.visible_warnings(1, retained):
                warnings.warn("synthetic warning", UserWarning)
                raise ValueError("synthetic failure")
    assert retained == [{"subject": 1, "category": "UserWarning", "message": "synthetic warning"}]
