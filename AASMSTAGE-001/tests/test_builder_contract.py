"""Bounded source-free EDF, PSD and model-mechanics fixtures; no source fits."""
from pathlib import Path
from types import SimpleNamespace
import os

import numpy as np
import pytest
from scipy.signal import welch

import build_reference as b
import metric_contract as q


def tiny_edf(path):
    """Synthetic three-channel, four-record EDF with unequal sample layouts."""
    fixed = bytearray(b" "*256)
    for start, stop, value in ((0, 8, "0"), (168, 176, "01.01.00"), (176, 184, "00.00.00"),
                               (184, 192, "1024"), (236, 244, "4"), (244, 252, "10"), (252, 256, "3")):
        fixed[start:stop] = value.encode().ljust(stop-start)
    fields = [(16, ["EEG Fpz-Cz", "EEG Pz-Oz", "dummy"]), (80, ["", "", ""]),
              (8, ["uV", "uV", "count"]), (8, ["-100", "-250", "-1"]),
              (8, ["200", "150", "1"]), (8, ["-2048"]*3), (8, ["2047"]*3),
              (80, ["", "", ""]), (8, ["1000", "1000", "2"]), (32, ["", "", ""])]
    header = bytes(fixed)+b"".join(v.encode().ljust(width) for width, values in fields for v in values)
    assert len(header) == 1024
    raw = np.vstack((np.arange(4000)-2048, 2047-np.arange(4000))).astype("<i2")
    payload = np.concatenate([np.concatenate((raw[0, r*1000:(r+1)*1000], raw[1, r*1000:(r+1)*1000], [r, -r]))
                              for r in range(4)]).astype("<i2")
    path.write_bytes(header+payload.tobytes())
    return raw


def test_direct_edf_record_layout_and_distinct_channel_calibration(tmp_path):
    path = tmp_path/"synthetic.edf"; raw = tiny_edf(path)
    header, channels = b.edf_header(path)
    assert header["n_records"] == 4 and header["n_signals"] == 3 and header["header_bytes"] == 1024
    assert [c["samples_per_record_text"] for c in channels] == ["1000", "1000", "2"]
    result = b.extract_epochs(path, header, channels, [{"onset_sample": 500, "end_sample_exclusive": 3500}])
    for channel, (lo, hi) in enumerate(((-100, 200), (-250, 150))):
        expected = (raw[channel, 500:3500].astype(float)*(hi-lo)/4095+(lo+2048*(hi-lo)/4095))*1e-6
        assert np.allclose(result[0, channel], expected, atol=1e-19, rtol=1e-14)
    assert result.shape == (1, 2, 3000)


@pytest.mark.parametrize("mode", ["fixed_header", "channel_header", "payload"])
def test_truncated_edf_fails(tmp_path, mode):
    path = tmp_path/"synthetic.edf"; tiny_edf(path)
    original = path.read_bytes()
    path.write_bytes(original[:100] if mode == "fixed_header" else original[:800] if mode == "channel_header" else original[:-2])
    with pytest.raises(AssertionError):
        b.edf_header(path)


@pytest.mark.parametrize("mode", ["fifo", "directory", "symlink", "dangling"])
def test_manifest_must_be_regular_before_read(tmp_path, mode):
    source = tmp_path/"source"; source.mkdir(); manifest = source/"source_manifest.json"
    if mode == "fifo": os.mkfifo(manifest)
    elif mode == "directory": manifest.mkdir()
    else: manifest.symlink_to(Path(__file__) if mode == "symlink" else tmp_path/"absent")
    method = Path(__file__).parents[1]/"environment"/"method_contract.json"
    with pytest.raises(AssertionError, match="regular file|symlink"):
        b.load_inputs(source, method)


def source_annotations():
    return [{"annotation_index": i, "tal_index": i+1, "onset_s": float(i*30), "duration_s": 30.0,
             "description": "Sleep stage W"} for i in range(5)]


def test_packed_tal_identity_and_timekeeper():
    rows, clocks = b.parse_tals(b"+0\x14\x14\x00+0\x1530\x14Sleep stage W\x14\x00+30\x1530\x14Movement time\x14\x00")
    assert clocks == [{"tal_index": 0, "onset_s": 0.0}]
    assert [r["tal_index"] for r in rows] == [1, 2]
    assert rows[1]["description"] == "Movement time"


@pytest.mark.parametrize("raw", [b"+0\x14\x14\x00+0\x1530\x14Sleep stage W", b"+0\x14\x14\x00+1e308\x151e308\x14W\x14\x00", b"+1\x14\x14\x00", b"+0\x14\x14\x00+0\x15-1\x14W\x14\x00", b"+0\x14\x14\x00+nan\x1530\x14W\x14\x00", b"+0\x14\x14\x00+30\x1530\x14W\x14\x00+0\x1530\x14W\x14\x00"])
def test_malformed_tals_fail(raw):
    with pytest.raises(AssertionError):
        b.parse_tals(raw)


def test_recording_clip_precedes_chunk_anchor_and_unmapped_retained():
    original = source_annotations(); original[0]["onset_s"] = -5.; original[0]["duration_s"] = 35.
    original[2]["description"] = "Movement time"
    ann, epochs, meta = b.annotation_support(original, 0, 15000, {"Sleep stage W": 1})
    assert epochs[0]["onset_sample"] == 0 and epochs[0]["n_samples"] == 3000
    assert ann[2]["n_complete_chunks"] == 1 and ann[2]["status"] == "unsupported_stage"
    assert epochs[2]["stage_id"] is None and not epochs[2]["retained"]
    assert meta["n_dropped_epochs"] == 1


def test_zero_duration_boundary_and_incomplete_tail():
    original = source_annotations(); original[-1]["onset_s"] = 150.; original[-1]["duration_s"] = 0.
    original[2]["duration_s"] = 29.
    ann, epochs, _ = b.annotation_support(original, 0, 15000, {"Sleep stage W": 1})
    assert ann[-1]["effective_onset_s"] == ann[-1]["effective_stop_s"] == 150
    assert ann[-1]["status"] == "no_complete_chunk" and ann[-1]["discarded_tail_s"] == 0
    assert ann[2]["n_complete_chunks"] == 0 and ann[2]["discarded_tail_s"] == 29
    assert len(epochs) == 3


def test_zero_duration_bad_does_not_overlap():
    original = source_annotations()
    original.insert(2, {"annotation_index": 10, "tal_index": 11, "onset_s": 40., "duration_s": 0., "description": "BAD test"})
    _, epochs, _ = b.annotation_support(original, 0, 15000, {"Sleep stage W": 1})
    assert all(r["retained"] for r in epochs)


def test_positive_duration_bad_has_half_open_overlap():
    original = source_annotations()
    original.insert(2, {"annotation_index": 10, "tal_index": 11, "onset_s": 30., "duration_s": 30., "description": "bad test"})
    # A second complete candidate at the same onset would violate source identity.
    with pytest.raises(AssertionError, match="duplicate"):
        b.annotation_support(original, 0, 15000, {"Sleep stage W": 1})
    original[2]["duration_s"] = 1.
    _, epochs, _ = b.annotation_support(original, 0, 15000, {"Sleep stage W": 1})
    assert epochs[0]["retained"] and epochs[1]["drop_reason"] == "overlap_bad_annotation"
    assert epochs[2]["retained"]


def test_annotation_gap_overlap_original_order():
    original = source_annotations(); original[1]["onset_s"] = 31.
    original[1]["duration_s"] = 29.
    original[3]["onset_s"] = 89.; original[3]["duration_s"] = 29.
    _, _, meta = b.annotation_support(original, 0, 15000, {"Sleep stage W": 1})
    assert meta["n_annotation_gaps"] == 2 and meta["n_annotation_overlaps"] == 1


def test_mapped_overlap_fails():
    original = source_annotations(); original[1]["onset_s"] = 29.
    with pytest.raises(AssertionError, match="overlapping"):
        b.annotation_support(original, 0, 15000, {"Sleep stage W": 1})


def test_sample_grid_misalignment_fails():
    original = source_annotations(); original[1]["onset_s"] += .005
    with pytest.raises(AssertionError, match="sample aligned"):
        b.annotation_support(original, 0, 15000, {"Sleep stage W": 1})


def test_manual_welch_matches_independent_signal_welch_fixture():
    x = np.random.default_rng(37).normal(size=(3, 2, 3000))*1e-5
    features, sums = b.welch_features(x)
    freq, psd = welch(x, fs=100, window="hamming", nperseg=256, noverlap=0, nfft=256,
                      detrend="constant", return_onesided=True, scaling="density", average="mean", axis=-1)
    norm = psd/psd[..., 2:77].sum(axis=-1, keepdims=True)
    expected = np.concatenate([norm[..., (freq >= lo) & (freq < hi)].mean(axis=-1)
                               for lo, hi in ((.5, 4.5), (4.5, 8.5), (8.5, 11.5), (11.5, 15.5), (15.5, 30))], axis=1)
    assert np.allclose(features, expected, atol=1e-15, rtol=1e-13)
    assert np.allclose(sums, psd[..., 2:77].sum(axis=-1), atol=0, rtol=1e-13)


def test_unused_tail_and_dc_invariance():
    x = np.random.default_rng(0).normal(size=(1, 2, 3000))
    a, ad = b.welch_features(x)
    x[..., 2816:] = 1e8
    c, cd = b.welch_features(x)
    assert np.array_equal(a, c) and np.array_equal(ad, cd)
    c, cd = b.welch_features(x+3.)
    assert np.allclose(a, c, atol=1e-15, rtol=1e-13)
    assert np.allclose(ad, cd, atol=0, rtol=1e-13)


def test_amplitude_scaling_changes_denominator_not_relative_features():
    x = np.random.default_rng(4).normal(size=(1, 2, 3000))
    a, d = b.welch_features(x); c, e = b.welch_features(x*1e-6)
    assert np.allclose(a, c, atol=1e-15, rtol=1e-13)
    assert np.allclose(e, d*1e-12, atol=0, rtol=1e-13)


@pytest.mark.parametrize("value", [0., np.nan, np.inf])
def test_bad_signal_fails(value):
    with pytest.raises(AssertionError):
        b.welch_features(np.full((1, 2, 3000), value))


def test_tree_threshold_and_float32_input():
    tree = SimpleNamespace(children_left=np.array([1, -1, -1]), children_right=np.array([2, -1, -1]),
                           feature=np.array([0, -2, -2]), threshold=np.array([.5, -2., -2.]),
                           value=np.array([[[1., 1.]], [[2., 0.]], [[0., 2.]]]))
    x = np.array([[.5], [.5+1e-10], [.5+1e-6]])
    result = b.tree_probabilities(tree, x)
    assert np.array_equal(result, [[1, 0], [1, 0], [0, 1]])


def test_evidence_existing_and_source_nesting_rejected(tmp_path):
    source = tmp_path/"source"; source.mkdir()
    with pytest.raises(AssertionError, match="outside source"):
        b.destinations(source, source/"bank.npz", tmp_path/"report.json")
    existing = tmp_path/"bank.npz"; existing.write_bytes(b"evidence")
    with pytest.raises(AssertionError, match="already exists"):
        b.destinations(source, existing, tmp_path/"report.json")
    assert existing.read_bytes() == b"evidence" and list(source.iterdir()) == []


@pytest.mark.parametrize("mode", ["leaf", "ancestor", "dangling"])
def test_evidence_symlinks_rejected(tmp_path, mode):
    source = tmp_path/"source"; source.mkdir()
    parent = tmp_path/"real"; parent.mkdir()
    link = tmp_path/"link"
    link.symlink_to(parent if mode == "ancestor" else tmp_path/("missing" if mode == "dangling" else "real"))
    output = link/"bank.npz" if mode == "ancestor" else link
    with pytest.raises(AssertionError, match="symlink"):
        b.destinations(source, output, tmp_path/"report.json")


def test_wrong_method_pin_fails_before_source_access(tmp_path):
    method = tmp_path/"method.json"; method.write_text("{}")
    with pytest.raises(AssertionError, match="method digest"):
        b.load_inputs(tmp_path/"nonexistent", method)


def test_test_entrypoint_executable():
    assert Path(__file__).with_name("test.sh").stat().st_mode & 0o777 == 0o755
