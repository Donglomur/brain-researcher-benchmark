"""Authentication and tiny synthetic NIfTI fixtures; never opens real sources."""
import json
import os
import sys
import types

import numpy as np
import pytest

import source_reference as r
from fixture_support import digest, json_write, synthetic_sources


def test_all_ten_auth_then_independent_reconstruction(tmp_path, monkeypatch):
    root, method, schema = synthetic_sources(tmp_path, monkeypatch)
    basis = r.reconstruct(root, method, schema)
    assert basis["raw_coefficients"].shape == (64, 39)
    assert basis["cleaned_series"].shape == (64, 2)
    assert len(basis["metadata"]["source_files"]) == 10
    assert basis["metadata"]["analysis_observed"]["map_rank"] == 39
    assert basis["metadata"]["source_observed"]["frame_count"] == 64
    assert len(basis["metadata"]["source_observed"]["confound_columns"]) == 17
    assert basis["participant_id"] == "0010064" and basis["active"].all()


@pytest.mark.parametrize("n", [40, 56])
def test_frame_count_is_declared_not_historical(tmp_path, monkeypatch, n):
    root, method, schema = synthetic_sources(tmp_path, monkeypatch, n=n)
    assert r.reconstruct(root, method, schema)["raw_coefficients"].shape == (n, 39)


@pytest.mark.parametrize("mutation", ["corrupt", "missing", "extra", "extra_dir", "symlink", "dangling", "fifo", "manifest"])
def test_closed_source_identity_before_any_numerical_parse(tmp_path, monkeypatch, mutation):
    root, method, schema = synthetic_sources(tmp_path, monkeypatch)
    target = root / "phenotype.csv"
    if mutation == "corrupt": target.write_bytes(b"X" + target.read_bytes()[1:])
    if mutation == "missing": target.unlink()
    if mutation == "extra": (root / "unexpected").write_text("x")
    if mutation == "extra_dir": (root / "unexpected").mkdir()
    if mutation == "symlink": target.unlink(); target.symlink_to(root / "ids.txt")
    if mutation == "dangling": (root / "dangling").symlink_to(root / "absent")
    if mutation == "fifo": (root / "pipe").parent.mkdir(exist_ok=True); os.mkfifo(root / "pipe")
    if mutation == "manifest":
        obj = json.loads((root / "source_manifest.json").read_text()); obj["participant_ids"] = ["10064"]
        json_write(root / "source_manifest.json", obj)
    monkeypatch.setattr(r, "image", lambda *_: pytest.fail("source parsing occurred before authentication"))
    with pytest.raises(ValueError): r.reconstruct(root, method, schema)


@pytest.mark.parametrize("name", ["SOURCE_SHA256", "METHOD_SHA256", "SCHEMA_SHA256"])
def test_unfrozen_pin_fails_closed(tmp_path, monkeypatch, name):
    root, method, schema = synthetic_sources(tmp_path, monkeypatch)
    monkeypatch.setattr(r, name, None)
    with pytest.raises(ValueError, match="pin not frozen"): r.reconstruct(root, method, schema)


def test_no_agent_visible_helper_or_cached_module_is_trusted(tmp_path, monkeypatch):
    root, _, _ = synthetic_sources(tmp_path, monkeypatch)
    fake = types.SimpleNamespace(verify_staged=lambda *_: pytest.fail("mutable stage helper imported"))
    monkeypatch.setitem(sys.modules, "stage_data", fake)
    monkeypatch.setitem(sys.modules, "source_reader", fake)
    r.authenticate_source(root)
    path = root / "ids.txt"; path.write_text("0010065\n0099999\n")
    with pytest.raises(ValueError, match="digest mismatch"): r.authenticate_source(root)


@pytest.mark.parametrize("payload", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":{"v":1e999}}'])
def test_pinned_json_still_requires_strict_finite_structure(tmp_path, payload):
    path = tmp_path / "m.json"; path.write_bytes(payload)
    with pytest.raises(ValueError): r.authenticated_json(path, digest(path), "test")


def test_same_buffer_hash_and_parse_prevents_manifest_reopen_race(tmp_path, monkeypatch):
    path = tmp_path / "m.json"; path.write_bytes(b'{"safe":true}')
    expected = digest(path); original = r.a.parse_json
    def swap_then_parse(payload):
        path.write_bytes(b'{"unsafe":true}')
        return original(payload)
    monkeypatch.setattr(r.a, "parse_json", swap_then_parse)
    assert r.authenticated_json(path, expected, "same bytes") == {"safe": True}


def test_replaced_image_between_authentication_and_decode_rejected(tmp_path, monkeypatch):
    root, _, _ = synthetic_sources(tmp_path, monkeypatch)
    manifest, identity = r.authenticate_source(root); row = next(v for v in manifest["files"] if v["role"] == "bold")
    path = root / row["path"]; payload = path.read_bytes(); path.unlink(); path.write_bytes(payload)
    with pytest.raises(ValueError, match="changed"): r.image(root, row, identity)


def test_nonempty_nifti_extensions_are_honored_without_352_payload_assumption(tmp_path, monkeypatch):
    import nibabel as nib
    root, _, _ = synthetic_sources(tmp_path, monkeypatch)
    path = root / "bold.nii.gz"
    obj = nib.load(path); values = obj.get_fdata().astype(np.float32)
    image = nib.Nifti1Image(values, obj.affine)
    image.header.extensions.append(nib.nifti1.Nifti1Extension(6, b"manufactured extension" * 200))
    nib.save(image, path)
    row = dict(path=path.name, role="bold", participant_id="0010064", size_bytes=path.stat().st_size, sha256=digest(path))
    identities = {path.name: r.verify_file(path, row)}
    loaded, _ = r.image(root, row, identities)
    assert loaded.dataobj.offset > 352
    assert np.array_equal(loaded.get_fdata(), values)


@pytest.mark.parametrize("change", ["wrong_frames", "wrong_subject", "wrong_target", "nuisance_order", "wrong_sourcepin"])
def test_declared_source_identity_not_inferred(tmp_path, monkeypatch, change):
    root, method, schema = synthetic_sources(tmp_path, monkeypatch)
    obj = json.loads(method.read_text())
    if change == "wrong_frames": obj["source"]["n_frames"] += 1
    if change == "wrong_subject": obj["source"]["participant_id"] = "10064"
    if change == "wrong_target": obj["source"]["target_map_ids"].reverse()
    if change == "nuisance_order": obj["temporal_cleaning"]["confound_columns"].reverse()
    if change == "wrong_sourcepin": obj["source"]["source_manifest_sha256"] = "0"*64
    json_write(method, obj); monkeypatch.setattr(r, "METHOD_SHA256", digest(method))
    with pytest.raises(ValueError): r.reconstruct(root, method, schema)


def test_source_nonselected_confound_is_not_hidden_finite_gate(tmp_path, monkeypatch):
    root, method, schema = synthetic_sources(tmp_path, monkeypatch)
    path = root / "confounds.csv"; lines = path.read_text().splitlines(); fields = lines[1].split("\t"); fields[0] = "NaN"
    lines[1] = "\t".join(fields); path.write_text("\n".join(lines)+"\n")
    manifest = json.loads((root / "source_manifest.json").read_text())
    for row in manifest["files"]:
        if row["role"] == "confounds": row.update(size_bytes=path.stat().st_size, sha256=digest(path))
    json_write(root / "source_manifest.json", manifest); monkeypatch.setattr(r, "SOURCE_SHA256", digest(root / "source_manifest.json"))
    obj = json.loads(method.read_text()); obj["source"]["source_manifest_sha256"] = r.SOURCE_SHA256
    json_write(method, obj); monkeypatch.setattr(r, "METHOD_SHA256", digest(method))
    assert r.reconstruct(root, method, schema)["raw_coefficients"].shape[1] == 39


def test_production_source_pin_exact():
    assert r.SOURCE_SHA256 == "465cfd8f113be362b39172782713c504432c51e529d82f222bda8ba9f1fb734e"


def test_csv_suffix_does_not_override_declared_tab_separator(tmp_path, monkeypatch):
    root, _, _ = synthetic_sources(tmp_path, monkeypatch)
    manifest, identities = r.authenticate_source(root)
    row = next(v for v in manifest["files"] if v["role"] == "confounds")
    columns, values = r.source_table(root, row, identities, "\t")
    assert len(columns) == 17 and len(values) == 64 and len(values[0]) == 17
    wrong, _ = r.source_table(root, row, identities, ",")
    assert len(wrong) == 1 and not r.NUISANCE <= set(wrong)
