"""Manufactured full400 evidence; assignment double is explicitly not package QA."""
import csv
from copy import deepcopy
import json

import numpy as np
import pytest

import artifact_reader as a
import fixture_support as f
import proof_of_work as p
import spin_math as m


@pytest.fixture
def manufactured(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "construct", f.fake_construct)
    ref = f.reference()
    return f.emit(tmp_path/"output", ref), ref


def read_json(root, name="results.json"):
    return json.loads((root/name).read_text())


def edit_json(root, mutate, name="results.json"):
    value = read_json(root, name); mutate(value); f.write_json(root/name, value)


def edit_npz(root, mutate):
    value = a.parse_npz((root/"spin_evidence.npz").read_bytes())
    mutate(value); np.savez_compressed(root/"spin_evidence.npz", **value)


def edit_csv(root, mutate):
    rows = a.parse_csv((root/"parcels.csv").read_bytes()); mutate(rows)
    with (root/"parcels.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def test_complete_source_bound_positive(manufactured):
    root, ref = manufactured
    assert p.validate_output_directory(root, ref)["source_bound"]


@pytest.mark.parametrize("method", m.METHODS)
def test_all_declared_methods_are_legitimate(tmp_path, monkeypatch, method):
    monkeypatch.setattr(m, "construct", f.fake_construct)
    ref = f.reference(); root = f.emit(tmp_path/"output", ref, method=method, seed=2**32-1)
    assert p.validate_output_directory(root, ref)["status"] == "accepted"


def test_coherent_csv_npz_json_axis_permutations(manufactured):
    root, ref = manufactured
    edit_csv(root, lambda rows: rows.reverse())
    def permute(z):
        po = np.arange(399, -1, -1); ro = np.arange(99, -1, -1)
        for key in ("parcel_ids", "hemisphere", "centroids"): z[key] = z[key][po]
        z["rotation_ids"] = z["rotation_ids"][ro]
        z["spin_parcel_ids"] = z["spin_parcel_ids"][np.ix_(po, ro)]
    edit_npz(root, permute)
    edit_json(root, lambda x: x["null_distribution"].reverse())
    edit_json(root, lambda x: x["analysis_observed"]["map_support"].reverse(), "run_metadata.json")
    assert p.validate_output_directory(root, ref)["status"] == "accepted"


def test_integral_float_keys_and_scientific_csv_ids(manufactured):
    root, ref = manufactured
    def convert(z):
        for key in ("parcel_ids", "rotation_ids", "hemisphere", "spin_parcel_ids"): z[key] = z[key].astype(float)
    edit_npz(root, convert)
    edit_csv(root, lambda rows: [row.update(parcel_id=f'{int(row["parcel_id"])}e0') for row in rows])
    assert p.validate_output_directory(root, ref)["status"] == "accepted"


def test_rounded_scalar_receipts_not_rank_inputs(manufactured):
    root, ref = manufactured
    def rounded(x):
        x["pearson_r"] = round(x["pearson_r"], 6)
        x["p_spin"] = round(x["p_spin"], 6)
        for row in x["null_distribution"]: row["r"] = round(row["r"], 6)
    edit_json(root, rounded)
    assert p.validate_output_directory(root, ref)["status"] == "accepted"


def test_harmless_extra_evidence_and_free_prose(manufactured):
    root, ref = manufactured
    edit_npz(root, lambda z: z.update(extra=np.ones((1,)*16)))
    edit_json(root, lambda x: x.update(note="No claim about absence of a relationship."))
    edit_csv(root, lambda rows: [row.update(note="literal extra text") for row in rows])
    (root/"findings.md").write_text("A signed descriptive conclusion of my own choosing.")
    assert p.validate_output_directory(root, ref)["status"] == "accepted"


def test_own_source_close_maps_recompute_downstream(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "construct", f.fake_construct)
    ref = f.reference(); own = ref["maps"].copy()
    own[:, 0] += 1e-8*np.sin(np.arange(400))
    root = f.emit(tmp_path/"output", ref, own=own)
    assert p.validate_output_directory(root, ref)["status"] == "accepted"


@pytest.mark.parametrize("column", [0, 1])
def test_canonical_inactive_maps_allow_complete_null_reports(tmp_path, monkeypatch, column):
    monkeypatch.setattr(m, "construct", f.fake_construct)
    ref = f.reference(); ref["maps"][:, column] = .1
    root = f.emit(tmp_path/"output", ref)
    assert p.validate_output_directory(root, ref)["inference_status"] == "incomplete_support"


@pytest.mark.parametrize("field,value", [("spin_method", "shuffle"), ("seed", True), ("seed", "0"),
    ("n_permutations", 99), ("n_permutations", 4097), ("n_parcels", True), ("pearson_r", True),
    ("pearson_r", "0.2"), ("n_exceedances", True), ("significant_after_spatial_null", 0),
    ("observed_status", "inactive_gradient"), ("p_spin", 0.), ("status", "failed")])
def test_result_type_or_replay_mismatch_rejected(manufactured, field, value):
    root, ref = manufactured
    edit_json(root, lambda x: x.update({field: value}))
    with pytest.raises(ValueError): p.validate_output_directory(root, ref)


@pytest.mark.parametrize("field", ["gradient2", "thickness", "label", "network", "hemisphere", "n_vertices", "support_sha256"])
def test_source_parcel_fabrication(manufactured, field):
    root, ref = manufactured
    def mutate(rows):
        row = rows[0]
        row[field] = str(float(row[field])+1.) if field in ("gradient2", "thickness", "n_vertices") else "wrong"
    edit_csv(root, mutate)
    with pytest.raises(ValueError): p.validate_output_directory(root, ref)


@pytest.mark.parametrize("mode", ["missing", "duplicate", "numeric_alias", "digit_alias"])
def test_parcel_key_corruption(manufactured, mode):
    root, ref = manufactured
    def mutate(rows):
        if mode == "missing": rows.pop()
        elif mode == "duplicate": rows[1] = dict(rows[0])
        elif mode == "numeric_alias": rows[1]["parcel_id"] = "1e0"
        else: rows[0]["parcel_id"] = "parcel_1"
    edit_csv(root, mutate)
    with pytest.raises(ValueError): p.validate_output_directory(root, ref)


@pytest.mark.parametrize("mode", ["centroids", "hemisphere", "mapping", "row_offsets", "boolean_ids", "fractional_ids", "duplicate_rotations"])
def test_discrete_or_geometry_binding(manufactured, mode):
    root, ref = manufactured
    def mutate(z):
        if mode == "centroids": z[mode][0, 0] += 1.
        elif mode == "hemisphere": z[mode][0] = 1
        elif mode == "mapping": z["spin_parcel_ids"][0, 0] = z["spin_parcel_ids"][1, 0]
        elif mode == "row_offsets": z["spin_parcel_ids"] -= 1
        elif mode == "boolean_ids": z["parcel_ids"] = z["parcel_ids"].astype(bool)
        elif mode == "fractional_ids": z["parcel_ids"] = z["parcel_ids"].astype(float)+.1
        else: z["rotation_ids"][1] = z["rotation_ids"][0]
    edit_npz(root, mutate)
    with pytest.raises(ValueError): p.validate_output_directory(root, ref)


def test_wrong_declared_seed_rejected_by_assignment(manufactured):
    root, ref = manufactured
    edit_json(root, lambda x: x.update(seed=1))
    with pytest.raises(ValueError, match="assignments"): p.validate_output_directory(root, ref)


@pytest.mark.parametrize("mode", ["drop", "duplicate", "bool_id", "null", "value", "denominator"])
def test_null_slots_counts_and_numeric_replay(manufactured, mode):
    root, ref = manufactured
    def mutate(x):
        if mode == "drop": x["null_distribution"].pop()
        elif mode == "duplicate": x["null_distribution"][1] = dict(x["null_distribution"][0])
        elif mode == "bool_id": x["null_distribution"][0]["rotation_id"] = False
        elif mode == "null": x["null_distribution"][0].update(status="inactive_gradient", r=None)
        elif mode == "value": x["null_distribution"][0]["r"] += .01
        else: x["n_null_defined"] -= 1
    edit_json(root, mutate)
    with pytest.raises(ValueError): p.validate_output_directory(root, ref)


@pytest.mark.parametrize("mode", ["pin", "extra_source", "header", "active", "remap_count", "bool_count"])
def test_source_provenance_and_support(manufactured, mode):
    root, ref = manufactured
    def mutate(x):
        if mode == "pin": x["source_manifest_sha256"] = "0"*64
        elif mode == "extra_source": x["source_files"].append(dict(x["source_files"][0], path="extra"))
        elif mode == "header": x["source_observed"]["gradient_l"]["arrays"][0]["shape"] = [1]
        elif mode == "active": x["analysis_observed"]["map_support"][0]["active"] = False
        elif mode == "remap_count": x["analysis_observed"]["remapped_gradient"]["n_active"] -= 1
        else: x["analysis_observed"]["remapped_gradient"]["n_expected"] = True
    edit_json(root, mutate, "run_metadata.json")
    with pytest.raises(ValueError): p.validate_output_directory(root, ref)


def test_all_null_cannot_forge_finite_results(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "construct", f.fake_construct)
    ref = f.reference(); ref["maps"][:, 0] = 1.
    root = f.emit(tmp_path/"output", ref)
    edit_json(root, lambda x: x.update(pearson_r=0., n_exceedances=100, p_spin=1., significant_after_spatial_null=False))
    with pytest.raises(ValueError): p.validate_output_directory(root, ref)


def test_late_failure_overrides_complete_success(manufactured):
    root, ref = manufactured
    (root/"failure_report.json").symlink_to(root/"absent")
    with pytest.raises(ValueError, match="authoritative"): p.validate_output_directory(root, ref)


@pytest.mark.parametrize("field", ["n_null_expected", "p_spin_numerator", "p_spin_denominator"])
@pytest.mark.parametrize("change", ["missing", "wrong", "bool"])
def test_exact_inference_fraction_fields_required(manufactured, field, change):
    root, ref = manufactured
    def mutate(x):
        if change == "missing": del x[field]
        elif change == "wrong": x[field] += 1
        else: x[field] = True
    edit_json(root, mutate)
    with pytest.raises(ValueError): p.validate_output_directory(root, ref)


@pytest.mark.parametrize("alias", ["float32", "f4", "=f4", "<f4"])
def test_explicit_source_array_dtype_aliases(manufactured, alias):
    root, ref = manufactured
    assert np.little_endian  # Qualification image is the declared x86_64 environment.
    def mutate(x):
        for role in p.GIFTI_ROLES: x["source_observed"][role]["arrays"][0]["dtype"] = alias
    edit_json(root, mutate, "run_metadata.json")
    assert p.validate_output_directory(root, ref)["status"] == "accepted"


@pytest.mark.parametrize("bad", [True, None, "object", "V4", "f8", ">f4", "i4", "(2,)f4", "i4,f4"])
def test_bad_source_array_dtype_receipt(manufactured, bad):
    root, ref = manufactured
    edit_json(root, lambda x: x["source_observed"]["gradient_l"]["arrays"][0].update(dtype=bad), "run_metadata.json")
    with pytest.raises(ValueError): p.validate_output_directory(root, ref)


def test_documentary_dtype_key_is_not_semantic_magic(manufactured):
    root, ref = manufactured
    edit_json(root, lambda x: x["source_observed"]["gradient_l"]["arrays"][0]["metadata"].update(dtype="float32"), "run_metadata.json")
    with pytest.raises(ValueError, match="literal exact"): p.validate_output_directory(root, ref)


@pytest.mark.parametrize("field,description", [
    ("cortical_join", "Joined original hemisphere-local vertex identities from the brain-model axis."),
    ("sphere_coordinate_transform", "none"),
    ("map_support", "All nonbackground cortical vertices retained without imputation.")])
def test_authored_atlas_descriptions_have_no_private_prose_fingerprint(manufactured, field, description):
    root, ref = manufactured
    edit_json(root, lambda x: x["source_observed"]["atlas"].update({field: description}), "run_metadata.json")
    before = (root/"run_metadata.json").read_bytes()
    assert p.validate_output_directory(root, ref)["status"] == "accepted"
    assert (root/"run_metadata.json").read_bytes() == before


@pytest.mark.parametrize("field", p.ATLAS_DESCRIPTION_FIELDS)
@pytest.mark.parametrize("value", [None, "", "  \n", True, 0, {}, []])
def test_atlas_descriptions_reject_empty_or_malformed_values(manufactured, field, value):
    root, ref = manufactured
    edit_json(root, lambda x: x["source_observed"]["atlas"].update({field: value}), "run_metadata.json")
    with pytest.raises(ValueError): p.validate_output_directory(root, ref)


@pytest.mark.parametrize("field", p.ATLAS_DESCRIPTION_FIELDS)
def test_atlas_descriptions_remain_required(manufactured, field):
    root, ref = manufactured
    edit_json(root, lambda x: x["source_observed"]["atlas"].pop(field), "run_metadata.json")
    with pytest.raises(ValueError): p.validate_output_directory(root, ref)


def test_structured_support_receipts_accept_correct_reordered_source_counts(manufactured):
    root, ref = manufactured
    edit_json(root, lambda x: x["source_observed"]["atlas"].update(
        map_support=deepcopy(ref["source_map_support"])[::-1]), "run_metadata.json")
    assert p.validate_output_directory(root, ref)["status"] == "accepted"


@pytest.mark.parametrize("defect", ["included_vertices", "finite_vertices", "nonfinite_vertices", "zero_vertices",
                                    "missing_count", "bool_count", "fractional_count", "string_count",
                                    "missing_map", "duplicate_map", "extra_map"])
def test_structured_support_receipts_reject_false_or_incomplete_counts(manufactured, defect):
    root, ref = manufactured
    records = deepcopy(ref["source_map_support"])
    if defect in ("included_vertices", "finite_vertices", "nonfinite_vertices", "zero_vertices"):
        records[0][defect] += 1
    elif defect == "missing_count": del records[0]["zero_vertices"]
    elif defect == "bool_count": records[0]["zero_vertices"] = False
    elif defect == "fractional_count": records[0]["zero_vertices"] = .5
    elif defect == "string_count": records[0]["zero_vertices"] = "0"
    elif defect == "missing_map": records.pop()
    elif defect == "duplicate_map": records[1] = dict(records[0])
    else: records.append(dict(records[0], map_id="invented"))
    edit_json(root, lambda x: x["source_observed"]["atlas"].update(map_support=records), "run_metadata.json")
    with pytest.raises(ValueError): p.validate_output_directory(root, ref)


def test_structured_support_requires_private_source_count_authority(manufactured):
    root, ref = manufactured
    counts = ref.pop("source_map_support")
    edit_json(root, lambda x: x["source_observed"]["atlas"].update(map_support=counts), "run_metadata.json")
    with pytest.raises(ValueError, match="private source map support required"):
        p.validate_output_directory(root, ref)


@pytest.mark.parametrize("defect", ["source_hash", "support_hash", "hemisphere", "map", "centroid",
                                    "structure_digest", "zero_count", "label_name", "original_metadata"])
def test_documentary_prose_never_replaces_source_or_join_correctness(manufactured, defect):
    root, ref = manufactured
    edit_json(root, lambda x: x["source_observed"]["atlas"].update(
        cortical_join="An independent description of the original vertex join.",
        sphere_coordinate_transform="none", map_support="The complete cortical support."), "run_metadata.json")
    if defect == "source_hash":
        edit_json(root, lambda x: x["source_files"][0].update(sha256="0"*64), "run_metadata.json")
    elif defect == "support_hash": edit_csv(root, lambda rows: rows[0].update(support_sha256="0"*64))
    elif defect == "hemisphere": edit_csv(root, lambda rows: rows[0].update(hemisphere="R"))
    elif defect == "map": edit_csv(root, lambda rows: rows[0].update(gradient2=str(float(rows[0]["gradient2"])+1)))
    elif defect == "centroid": edit_npz(root, lambda z: z["centroids"].__setitem__((0, 0), z["centroids"][0, 0]+1))
    elif defect == "structure_digest":
        edit_json(root, lambda x: x["source_observed"]["atlas"]["structures"][0].update(vertex_ids_sha256="0"*64), "run_metadata.json")
    elif defect == "zero_count":
        edit_json(root, lambda x: x["source_observed"]["atlas"].update(excluded_zero_entries=1), "run_metadata.json")
    elif defect == "label_name":
        edit_json(root, lambda x: x["source_observed"]["atlas"].update(label_map_name="changed"), "run_metadata.json")
    else:
        edit_json(root, lambda x: x["source_observed"]["gradient_l"]["arrays"][0]["metadata"].update(dtype="made up"), "run_metadata.json")
    with pytest.raises(ValueError): p.validate_output_directory(root, ref)


@pytest.mark.parametrize("kind", ["empty", "dangling", "directory"])
def test_failure_marker_appearing_after_math_and_metadata(manufactured, monkeypatch, kind):
    root, ref = manufactured
    original = p.validate_metadata
    def wrapped(*args, **kwargs):
        original(*args, **kwargs)
        marker = root/"failure_report.json"
        if kind == "empty": marker.touch()
        elif kind == "dangling": marker.symlink_to(root/"absent")
        else: marker.mkdir()
    monkeypatch.setattr(p, "validate_metadata", wrapped)
    with pytest.raises(ValueError, match="appeared during validation"): p.validate_output_directory(root, ref)
