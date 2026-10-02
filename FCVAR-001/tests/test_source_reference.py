"""Manufactured bytes only: independent authentication/streaming contracts."""
import gzip
import hashlib
import json
import os

import nibabel as nib
import numpy as np
import pytest

import artifact_reader as a
import source_reference as s


def source_file(root, name, payload, role="provenance", sid=None):
    path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(payload)
    return dict(path=name, role=role, participant_id=sid, size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())


def source_fixture(root, monkeypatch):
    root.mkdir()
    rows = [source_file(root, sid+"."+role, (sid+role).encode(), role, sid)
            for sid in s.IDS for role in ("bold", "confounds")]
    roles = ("cohort_ids", "phenotype_metadata", "slice_timing_metadata", "atlas_image", "atlas_labels", "provenance_adhd_notice", "provenance_ho_notice")
    rows += [source_file(root, role+".txt", role.encode(), role) for role in roles]
    body = json.dumps(dict(participant_ids=s.IDS, files=rows)).encode()
    (root / "source_manifest.json").write_bytes(body)
    monkeypatch.setattr(s, "SOURCE_SHA256", hashlib.sha256(body).hexdigest())
    monkeypatch.setattr(s, "SOURCE_FILE_COUNT", len(rows))
    return rows


def test_authenticate_closed67_manufactured_members(tmp_path, monkeypatch):
    root = tmp_path / "source"; rows = source_fixture(root, monkeypatch)
    got_root, manifest, identities = s.authenticate_source(root)
    assert got_root == root and manifest["files"] == rows and len(identities) == 67


@pytest.mark.parametrize("change", ["manifest", "same_size", "missing", "extra", "extra_dir", "symlink", "dangling", "fifo"])
def test_source_namespace_and_checksum_fail_closed(tmp_path, monkeypatch, change):
    root = tmp_path / "source"; rows = source_fixture(root, monkeypatch)
    path = root / rows[0]["path"]
    if change == "manifest": (root / "source_manifest.json").write_text("{}")
    elif change == "same_size": path.write_bytes(b"x" * path.stat().st_size)
    elif change == "missing": path.unlink()
    elif change == "extra": (root / "extra").write_text("extra")
    elif change == "extra_dir": (root / "extra").mkdir()
    elif change in ("symlink", "dangling"):
        path.unlink(); path.symlink_to(root / (rows[1]["path"] if change == "symlink" else "absent"))
    elif change == "fifo": path.unlink(); os.mkfifo(path)
    with pytest.raises(ValueError): s.authenticate_source(root)


def test_post_consumption_hash_not_only_stat_identity(tmp_path, monkeypatch):
    root = tmp_path / "source"; rows = source_fixture(root, monkeypatch)
    _, _, identities = s.authenticate_source(root)
    row = rows[0]; (root / row["path"]).write_bytes(b"x"*row["size_bytes"])
    # Even if an adversarial metadata-check stub claims unchanged identity,
    # mandatory full source rehash must still detect altered consumed bytes.
    monkeypatch.setattr(s, "unchanged", lambda root, row, identities: root / row["path"])
    with pytest.raises(ValueError, match="checksum"):
        s.consumed(root, row, identities)


def test_authenticated_json_hash_and_parse_same_buffer(tmp_path, monkeypatch):
    path = tmp_path / "manifest.json"; path.write_text('{"value":1}')
    raw = path.read_bytes(); expected = hashlib.sha256(raw).hexdigest()
    original = a.read_bytes
    def swap_after_read(path, cap):
        body = original(path, cap); path.write_text('{"value":2}'); return body
    monkeypatch.setattr(a, "read_bytes", swap_after_read)
    assert s.authenticated_json(path, expected, "manufactured") == {"value": 1}


@pytest.mark.parametrize("payload", [b'{"a":1,"a":2}', b'{"a":NaN}', b'[]'])
def test_pinned_json_still_requires_strict_grammar(tmp_path, payload):
    path = tmp_path / "manifest.json"; path.write_bytes(payload)
    with pytest.raises(ValueError): s.authenticated_json(path, hashlib.sha256(payload).hexdigest(), "manufactured")


def test_tab_delimited_nuisance_and_literal_identifier(tmp_path):
    root = tmp_path
    payload = ("\t".join(s.n.CONFOUNDS)+"\n"+"\t".join(["1"]*13)+"\n").encode()
    row = source_file(root, "confounds.tsv", payload)
    identities = {row["path"]: s.verify_file(root / row["path"], row)}
    names, records = s.source_table(root, row, identities, "\t")
    assert names == list(s.n.CONFOUNDS) and len(records) == 1


def test_only_phenotype_leading_documentary_index_allowed(tmp_path):
    row = source_file(tmp_path, "phenotype.csv", b',Subject,site\n1,10042,NYU\n', "phenotype_metadata")
    identities = {row["path"]: s.verify_file(tmp_path/row["path"], row)}
    columns, rows = s.source_table(tmp_path, row, identities, ",", allow_leading_unnamed=True)
    assert columns == ["", "Subject", "site"] and rows[0][""] == "1"
    with pytest.raises(ValueError): s.source_table(tmp_path, row, identities, ",")


@pytest.mark.parametrize("role,header", [("confounds", ",Subject,site"), ("phenotype_metadata", "Subject,,site"),
                                         ("phenotype_metadata", ",,site"), ("phenotype_metadata", ",Subject,Subject")])
def test_unnamed_column_exception_is_narrow(tmp_path, role, header):
    row = source_file(tmp_path, "table.csv", (header+"\n1,2,3\n").encode(), role)
    identities = {row["path"]: s.verify_file(tmp_path/row["path"], row)}
    with pytest.raises(ValueError): s.source_table(tmp_path, row, identities, ",", allow_leading_unnamed=True)


@pytest.mark.parametrize("units,factor", [("sec", 1.), ("msec", .001), ("usec", .000001)])
def test_documentary_clock_respects_header_float32_units_without_override(units, factor):
    exact_header = float(np.float32(1.96/factor))*factor
    returned = s.validate_documentary_clock(exact_header, units, "1.96", "sec")
    assert returned == exact_header
    if units == "sec": assert returned != 1.96


@pytest.mark.parametrize("documented", ["2", "NaN", "True", "0", "1.96001"])
def test_documentary_clock_mismatch_or_invalid_not_used_as_override(documented):
    with pytest.raises(ValueError): s.validate_documentary_clock(float(np.float32(1.96)), "sec", documented, "sec")


def labels_xml():
    return "<atlas><data>" + "".join(f'<label index="{i}">ROI {i+1}</label>' for i in range(48)) + "</data></atlas>"


def test_xml48_labels_preserve_original_spelling():
    text = labels_xml().replace("ROI 1</", "Ventrical Operculum</", 1)
    got = s.atlas_labels(text)
    assert len(got) == 48 and got[0] == "Ventrical Operculum"


@pytest.mark.parametrize("token", ["10042", "0010042", "10042.0", "1.0042e4"])
def test_original_numeric_source_id_is_normalized_only_at_source_join(token):
    assert s.source_participant_id(token) == "0010042"


@pytest.mark.parametrize("token", [True, "", "True", "10042.1", "-1", "10000000", "NaN"])
def test_invalid_original_source_id(token):
    with pytest.raises(ValueError): s.source_participant_id(token)


@pytest.mark.parametrize("change", ["missing", "duplicate", "entity", "negative", "oversize"])
def test_xml_identity_and_entities(change):
    text = labels_xml()
    if change == "missing": text = text.replace('<label index="0">ROI 1</label>', '')
    if change == "duplicate": text = text.replace('index="1"', 'index="0"')
    if change == "entity": text = '<!DOCTYPE atlas [<!ENTITY e SYSTEM "file:///blocked">]>' + text
    if change == "negative": text = text.replace('index="0"', 'index="-1"')
    if change == "oversize": text = text.replace("ROI 1</", "a"*4097+"</", 1)
    with pytest.raises(ValueError): s.atlas_labels(text)


def nifti_fixture(root, compressed=True, extension=True):
    values = np.arange(2*3*2*4, dtype=np.float32).reshape(2, 3, 2, 4, order="F")
    obj = nib.Nifti1Image(values, np.diag([2., 2., 2., 1.]))
    obj.header.set_xyzt_units("mm", "sec"); obj.header.set_zooms((2., 2., 2., 1.5))
    if extension: obj.header.extensions.append(nib.nifti1.Nifti1Extension(6, b"manufactured extension"*300))
    body = obj.to_bytes()
    stored = gzip.compress(body) if compressed else body
    row = source_file(root, "image.nii.gz" if compressed else "image.nii", stored)
    identities = {row["path"]: s.verify_file(root / row["path"], row)}
    return values, row, identities


@pytest.mark.parametrize("compressed,extension", [(True, True), (True, False), (False, True), (False, False)])
def test_original_frame_order_extensions_and_streaming(tmp_path, compressed, extension):
    values, row, identities = nifti_fixture(tmp_path, compressed, extension)
    info = s.image_header(tmp_path, row, identities, 4)
    assert (info["offset"] > 352) == extension
    got = np.stack(list(s.image_volumes(tmp_path, row, identities, info)), axis=-1)
    assert np.array_equal(got, values)
    assert info["facts"]["temporal_units"] == "sec"


def test_rewrite_after_first_decoded_volume_fails_closed(tmp_path):
    _, row, identities = nifti_fixture(tmp_path, False, False)
    info = s.image_header(tmp_path, row, identities, 4)
    generator = s.image_volumes(tmp_path, row, identities, info)
    next(generator)
    path = tmp_path / row["path"]; body = bytearray(path.read_bytes()); body[-1] ^= 1; path.write_bytes(body)
    with pytest.raises(ValueError): list(generator)


def test_private_source_pins_default_unfrozen(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "SOURCE_SHA256", None)
    (tmp_path / "source_manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="not frozen"): s.authenticate_source(tmp_path)
