"""Generated replacement controls; no authentic observations or model evidence."""
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pytest

PACKAGE = Path(__file__).resolve().parents[1]
PREDECESSOR = PACKAGE.parent / "initial-evaluator-v1"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


e = load("neural050_snapshot", PACKAGE / "evaluator.py")
old = load("neural050_pre_snapshot", PREDECESSOR / "evaluator.py")
controls = load("neural050_snapshot_controls", PREDECESSOR / "tests/test_evaluator.py")


def replace_at_decoder_entry(subject, tmp_path, monkeypatch):
    original = controls.raw_manifest(tmp_path, amplitude=1.0)
    replacement = controls.raw_manifest(tmp_path, amplitude=2.0)
    original_path = Path(original["recordings"][0]["path"])
    replacement_path = Path(replacement["recordings"][0]["path"])
    real_load = np.load
    calls = []

    def replacing_load(source, **kwargs):
        # Simulate an atomic pathname replacement after authentication and
        # before the decoder receives its source. Both archives are valid.
        replacement_path.replace(original_path)
        calls.append(1)
        return real_load(source, **kwargs)

    with monkeypatch.context() as context:
        context.setattr(subject.np, "load", replacing_load)
        prepared = subject.prepare(original)
    assert calls == [1]
    assert hashlib.sha256(original_path.read_bytes()).hexdigest() != original["recordings"][0]["sha256"]
    assert prepared["source_pins"][0]["sha256"] == original["recordings"][0]["sha256"]
    return prepared


def test_predecessor_reads_replaced_signal_under_original_hash(tmp_path, monkeypatch):
    prepared = replace_at_decoder_entry(old, tmp_path, monkeypatch)
    assert np.exp([r["gamma"] for r in prepared["rows"]]) == pytest.approx([2.0] * 4, rel=1e-5)


def test_preparation_decodes_authenticated_snapshot_after_path_replacement(tmp_path, monkeypatch):
    prepared = replace_at_decoder_entry(e, tmp_path, monkeypatch)
    assert np.exp([r["gamma"] for r in prepared["rows"]]) == pytest.approx([0.5] * 4, rel=1e-5)
    assert [r["movement"] for r in prepared["rows"]] == pytest.approx([5.0] * 4)


def test_mismatched_snapshot_rejected_before_decoder(tmp_path, monkeypatch):
    manifest = controls.raw_manifest(tmp_path)
    manifest["recordings"][0]["sha256"] = "0" * 64

    def forbidden_decoder(*args, **kwargs):
        raise AssertionError("decoder reached before authentication")

    monkeypatch.setattr(e.np, "load", forbidden_decoder)
    with pytest.raises(ValueError, match="SHA256"):
        e.prepare(manifest)
