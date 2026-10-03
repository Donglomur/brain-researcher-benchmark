"""Manufactured metadata regressions; no EEG, model output or reference bank.

Only the reference load is replaced by a literal fixture. The real production
metadata test and its final whole-head comparison execute unchanged.
"""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest


TASK = Path(__file__).resolve().parents[1]


def module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def manufactured(monkeypatch, tmp_path):
    proof = module_from_path("metadata_fixture_proof", TASK / "tests/proof_of_work.py")
    monkeypatch.setitem(sys.modules, "proof_of_work", proof)

    def fixture_reference(path, *, allow_pickle):
        assert Path(path) == TASK / "tests/reference.npz"
        assert allow_pickle is False
        return {"wholehead_mean": 4.0}

    monkeypatch.setattr(np, "load", fixture_reference)
    verifier = module_from_path("metadata_fixture_verifier", TASK / "tests/test_outputs.py")
    verifier.OUT = tmp_path
    metadata = {
        "dataset_id": "eegmmidb", "dataset_version": "1.0.0",
        "subjects": [1, 2, 3, 4, 5],
        "runs": {"eyes_open": 1, "eyes_closed": 2},
        "band_hz": [8, 13], "channels": ["O1", "Oz", "O2"],
        "reference": "common average over all 64 EEG channels",
        "power_units": "V^2/Hz", "aggregation": "mean_of_subject_ratios",
        "welch": {"segment_sec": 2, "n_fft": 320, "n_overlap": 0,
                  "window": "hamming", "remove_dc": True, "average": "mean"},
    }
    result = {"band_hz": [8, 13], "channels": ["O1", "Oz", "O2"],
              "n_subjects": 5, "wholehead_alpha_ratio_for_reference": 4.0}

    def check():
        (tmp_path / "run_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        (tmp_path / "alpha_ratio.json").write_text(json.dumps(result), encoding="utf-8")
        verifier.test_public_analysis_metadata()

    return metadata, result, check


def test_public_welch_object_without_psd_method(manufactured):
    metadata, _, check = manufactured
    assert "psd_method" not in metadata
    check()


def test_implementation_details_are_optional(manufactured):
    metadata, _, check = manufactured
    metadata["welch_details"] = {"implementation": "scipy.signal.welch"}
    check()


@pytest.mark.parametrize("optional", [None, 17, {"implementation": "Welch"}, "Welch"])
def test_unrequired_extra_key_does_not_become_a_format_gate(manufactured, optional):
    metadata, _, check = manufactured
    metadata["psd_method"] = optional
    metadata["description"] = "Additional documentary fields are not required schema."
    check()


@pytest.mark.parametrize("key,value", [
    ("segment_sec", 4), ("n_fft", 640), ("n_overlap", 160),
    ("window", "hann"), ("remove_dc", False), ("average", "median"),
])
def test_incorrect_required_welch_setting_rejected(manufactured, key, value):
    metadata, _, check = manufactured
    metadata["welch"][key] = value
    # Optional implementation labels cannot excuse incorrect public settings.
    metadata["psd_method"] = "Welch"
    with pytest.raises(AssertionError):
        check()


@pytest.mark.parametrize("key", ["segment_sec", "n_fft", "n_overlap", "window", "remove_dc", "average"])
def test_missing_required_welch_setting_rejected(manufactured, key):
    metadata, _, check = manufactured
    del metadata["welch"][key]
    with pytest.raises(KeyError):
        check()


def test_missing_public_welch_object_rejected(manufactured):
    metadata, _, check = manufactured
    del metadata["welch"]
    metadata["psd_method"] = "Welch"
    with pytest.raises(KeyError):
        check()


def test_final_wholehead_numeric_check_still_rejects(manufactured):
    _, result, check = manufactured
    result["wholehead_alpha_ratio_for_reference"] = 8.0
    with pytest.raises(AssertionError):
        check()
