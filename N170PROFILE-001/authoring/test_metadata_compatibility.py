"""Manufactured schema equivalence, never original EEG or scientific calibration."""
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

import grader_bootstrap as boot
import proof_of_work as pw
import proof_fixture_support as f


PREFIX = "/app/data/n170profile/"


@pytest.fixture
def metadata():
    reference = f.manufactured_reference()
    return copy.deepcopy(f.documents(reference)[2]), reference


def aliases(document):
    for row in document["source_files"]:
        row["manifest_path"] = row["path"]
        row["path"] = PREFIX+row["path"]
    for row in document["source_observed"]["persons"]:
        for key in ("set_path", "fdt_path"):
            row[key] = PREFIX+row[key]
    for row in document["analysis_observed"]["persons"]:
        row["condition_defined"] = dict(zip(pw.CONDITIONS, row["condition_defined"]))


@pytest.mark.parametrize("encoding", ("canonical", "aliases", "mixed", "map_reordered"))
def test_equivalent_metadata_encodings(metadata, encoding):
    document, reference = metadata
    if encoding != "canonical":
        aliases(document)
    if encoding == "mixed":
        document["source_files"][0]["path"] = document["source_files"][0]["manifest_path"]
        person = document["source_observed"]["persons"][0]
        person["set_path"] = person["set_path"].removeprefix(PREFIX)
    if encoding == "map_reordered":
        for person in document["analysis_observed"]["persons"]:
            person["condition_defined"] = dict(reversed(list(person["condition_defined"].items())))
        document["source_files"].reverse()
        document["source_observed"]["persons"].reverse()
        document["analysis_observed"]["persons"].reverse()
    before = copy.deepcopy(document)
    pw.validate_metadata(document, reference)
    assert document == before


@pytest.mark.parametrize("flags", ([True, True], [False, True], [True, False], [False, False]))
def test_flags_preserve_named_order_and_exact_support(metadata, flags):
    document, reference = metadata
    reference["analysis_observed"]["persons"][0]["condition_defined"] = flags
    document["analysis_observed"]["persons"][0]["condition_defined"] = dict(zip(pw.CONDITIONS, flags))
    pw.validate_metadata(document, reference)
    document["analysis_observed"]["persons"][0]["condition_defined"]["face"] = not flags[0]
    with pytest.raises(ValueError, match="Boolean"):
        pw.validate_metadata(document, reference)


@pytest.mark.parametrize("value", (None, True, [True], [True, False, True], [1, 0], ["true", "false"],
    {"face": True}, {"face": True, "car": True, "extra": False}, {"car": True, "Face": True},
    {"face": 1, "car": True}, {"face": True, "car": None}))
def test_invalid_flag_encodings_rejected(metadata, value):
    document, reference = metadata
    document["analysis_observed"]["persons"][0]["condition_defined"] = value
    with pytest.raises(ValueError):
        pw.validate_metadata(document, reference)


@pytest.mark.parametrize("value", ("scalar_EEG_struct", "EEG", "flat_fields"))
def test_documented_mat_layout_encodings(metadata, value):
    document, reference = metadata
    expected = "flat_fields" if value == "flat_fields" else "scalar_EEG_struct"
    reference["source_observed"]["persons"][0]["mat_layout"] = expected
    document["source_observed"]["persons"][0]["mat_layout"] = value
    pw.validate_metadata(document, reference)


@pytest.mark.parametrize("value", ("EEG", "unknown", "scalar_EEG_struct", "", None))
def test_wrong_source_layout_rejected(metadata, value):
    document, reference = metadata
    reference["source_observed"]["persons"][0]["mat_layout"] = "flat_fields"
    document["source_observed"]["persons"][0]["mat_layout"] = value
    with pytest.raises(ValueError):
        pw.validate_metadata(document, reference)


EMPTY_FIELDS = [("header_fields", name) for name in ("subject", "group", "condition", "session")]
EMPTY_FIELDS += [("channel_records", name) for name in (
    "ref", "theta", "radius", "X", "Y", "Z", "sph_theta", "sph_phi", "sph_radius", "type", "urchan")]


def documentary_record(person, section):
    value = person[section]
    return value[0] if section == "channel_records" else value


@pytest.mark.parametrize("section,field", EMPTY_FIELDS)
def test_only_source_proven_empty_optional_fields_accept_null_or_empty_list(metadata, section, field):
    document, reference = metadata
    expected = documentary_record(reference["source_observed"]["persons"][0], section)
    actual = documentary_record(document["source_observed"]["persons"][0], section)
    expected[field] = None
    for value in (None, []):
        actual[field] = value
        before = copy.deepcopy(document)
        pw.validate_metadata(document, reference)
        assert document == before
    actual[field] = [0]
    with pytest.raises(ValueError):
        pw.validate_metadata(document, reference)
    del actual[field]
    with pytest.raises(ValueError):
        pw.validate_metadata(document, reference)


@pytest.mark.parametrize("section,field", EMPTY_FIELDS)
@pytest.mark.parametrize("value", (None, []))
def test_nonempty_documentary_source_cannot_be_discarded(metadata, section, field, value):
    document, reference = metadata
    documentary_record(reference["source_observed"]["persons"][0], section)[field] = "source value"
    documentary_record(document["source_observed"]["persons"][0], section)[field] = value
    with pytest.raises(ValueError):
        pw.validate_metadata(document, reference)


@pytest.mark.parametrize("section,field", (("header_fields", "filename"), ("channel_records", "labels")))
def test_empty_alias_not_applied_to_other_fields(metadata, section, field):
    document, reference = metadata
    documentary_record(reference["source_observed"]["persons"][0], section)[field] = None
    documentary_record(document["source_observed"]["persons"][0], section)[field] = []
    with pytest.raises(ValueError):
        pw.validate_metadata(document, reference)


@pytest.mark.parametrize("field", ("path", "set_path", "fdt_path", "manifest_path"))
@pytest.mark.parametrize("value", ("", "../2_N170_shifted_ds.set", "./2_N170_shifted_ds.set",
    "/tmp/2_N170_shifted_ds.set", "/app/data/n170profile-other/2_N170_shifted_ds.set",
    PREFIX+"../n170profile/2_N170_shifted_ds.set", PREFIX+"./2_N170_shifted_ds.set",
    PREFIX+"/2_N170_shifted_ds.set", "2_N170_shifted_ds.set/", "folder\\file.set",
    "file\x00.set", None, 7))
def test_invalid_source_paths_rejected(metadata, field, value):
    document, reference = metadata
    if field in ("path", "manifest_path"):
        document["source_files"][0][field] = value
    else:
        document["source_observed"]["persons"][0][field] = value
    with pytest.raises(ValueError):
        pw.validate_metadata(document, reference)


@pytest.mark.parametrize("defect", ("wrong_file", "wrong_hash", "wrong_size", "duplicate",
    "missing_file", "role_conflict", "person_path_conflict", "manifest_conflict", "raw_pointer_changed",
    "source_header_changed", "channel_labels_changed", "condition_mask_missing", "count_changed"))
def test_aliases_never_hide_source_identity_or_documentary_mismatch(metadata, defect):
    document, reference = metadata
    aliases(document)
    row = document["source_files"][0]
    person = document["source_observed"]["persons"][0]
    if defect == "wrong_file": row["path"] = PREFIX+"different.set"
    elif defect == "wrong_hash": row["sha256"] = "e"*64
    elif defect == "wrong_size": row["size_bytes"] += 1
    elif defect == "duplicate": document["source_files"][-1] = copy.deepcopy(row)
    elif defect == "missing_file": document["source_files"].pop()
    elif defect == "role_conflict": row["role"] = "fdt"
    elif defect == "person_path_conflict": person["set_path"] = PREFIX+"3_N170_shifted_ds.set"
    elif defect == "manifest_conflict": row["manifest_path"] = "3_N170_shifted_ds.set"
    elif defect == "raw_pointer_changed": person["literal_data_pointer"] = PREFIX+person["literal_data_pointer"]
    elif defect == "source_header_changed": person["header_fields"]["srate"] = 128
    elif defect == "channel_labels_changed": person["channel_labels"][0] = "wrong"
    elif defect == "condition_mask_missing": del document["analysis_observed"]["persons"][0]["condition_defined"]
    else: document["analysis_observed"]["persons"][0]["n_face_accepted"] += 1
    with pytest.raises(ValueError):
        pw.validate_metadata(document, reference)


def test_coherently_wrong_path_aliases_do_not_replace_source_authority(metadata):
    document, reference = metadata
    aliases(document)
    document["source_files"][0].update(path=PREFIX+"invented.set", manifest_path="invented.set")
    document["source_observed"]["persons"][0]["set_path"] = PREFIX+"invented.set"
    with pytest.raises(ValueError):
        pw.validate_metadata(document, reference)


def test_historical_header_path_strings_remain_literal(metadata):
    document, reference = metadata
    expected = reference["source_observed"]["persons"][0]["header_fields"]
    actual = document["source_observed"]["persons"][0]["header_fields"]
    expected["filepath"] = "/historical/source/location"
    actual["filepath"] = expected["filepath"]
    aliases(document)
    pw.validate_metadata(document, reference)
    actual["filepath"] = "/app/data/n170profile"
    with pytest.raises(ValueError):
        pw.validate_metadata(document, reference)


@pytest.mark.parametrize("defect", (None, "waveform", "amplitude", "onset", "trial", "failure"))
def test_whole_manufactured_bundle_keeps_scientific_and_failure_gates(tmp_path, defect):
    reference = f.manufactured_reference()
    out = f.emit(tmp_path/"output", reference)
    path = out/"run_metadata.json"
    document = json.loads(path.read_text())
    aliases(document)
    f.write_json(path, document)
    if defect == "waveform":
        with np.load(out/"erp_evidence.npz", allow_pickle=False) as archive:
            arrays = {key:archive[key].copy() for key in archive.files}
        arrays["evoked_po8_uv"][0,0,0] += .01
        np.savez(out/"erp_evidence.npz", **arrays)
    elif defect in ("amplitude", "onset"):
        document = json.loads((out/"n170.json").read_text())
        document["amp_po8_uv" if defect=="amplitude" else "onset_latency_ms"] += 1
        f.write_json(out/"n170.json", document)
    elif defect == "trial":
        text = (out/"trials.csv").read_text()
        (out/"trials.csv").write_text(text.replace(",accepted", ",peak_to_peak", 1))
    elif defect == "failure":
        (out/"failure_report.json").write_text('{"reason":"manufactured failure"}')
    before = path.read_bytes()
    if defect is None:
        assert pw.validate_bundle(out, reference)["status"] == "accepted"
    else:
        with pytest.raises(ValueError):
            pw.validate_bundle(out, reference)
    assert path.read_bytes() == before


def test_private_code_pin_chain_and_unchanged_documents():
    task = Path(__file__).resolve().parents[1]
    for name, digest in boot.PRIVATE_PINS.items():
        assert hashlib.sha256((task/"tests"/(name+".py")).read_bytes()).hexdigest() == digest
    for filename, digest in boot.DOCUMENT_PINS.values():
        private = (task/"tests"/filename).read_bytes()
        assert hashlib.sha256(private).hexdigest() == digest
        assert private == (task/"environment"/filename).read_bytes()
    digest = hashlib.sha256((task/"tests/grader_bootstrap.py").read_bytes()).hexdigest()
    assert digest in (task/"tests/test.sh").read_text()
