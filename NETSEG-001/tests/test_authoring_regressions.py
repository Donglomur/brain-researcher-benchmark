"""Manufactured verifier mechanics only, never evidence about original BOLD.

emit() also serializes a genuinely source-reconstructed reference when called
by a separately gated authoring driver. It never reads oracle output.
"""
import copy
import csv
import json
import os
from pathlib import Path
import zipfile

import numpy as np
import pytest

import proof_of_work as p
import source_math as s


def write_csv(path, rows, fields, exclusive=False):
    with Path(path).open("x" if exclusive else "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def emit(output, reference, arrays=None, versions=None):
    """Fresh output from source primitives, shared serialization not oracle math."""
    output = Path(output).absolute()
    for node in (output, *output.parents):
        assert not node.is_symlink()
    output.mkdir(parents=True, exist_ok=False)
    ref = reference
    method = ref["method"]
    values = {k: np.array(ref[k], copy=True) for k in
              ("participant_id", "frame_index", "parcel_id", "raw_mean", "standardized_clean", "raw_sd", "residual_sd")}
    if arrays is not None:
        values.update(arrays)
    own = s.derived(values["standardized_clean"], ref["participant_id"],
                    [r["group"] for r in ref["participants"]], ref["parcel_id"],
                    [r["network"] for r in ref["parcels"]], method)
    i, j = np.triu_indices(len(ref["parcel_id"]), 1)
    values.update(edge_i=ref["parcel_id"][i], edge_j=ref["parcel_id"][j])
    values.update({k: own[k] for k in ("pearson_r", "fisher_z", "positive_z")})
    with (output / "connectivity.npz").open("xb") as handle:
        np.savez_compressed(handle, **values)
    for name, rows in (("participants.csv", ref["participants"]), ("parcels.csv", ref["parcels"]),
                       ("segregation.csv", own["segregation"])):
        write_csv(output / name, rows, method["artifacts"][name]["columns"], exclusive=True)
    metadata = copy.deepcopy(ref["metadata"])
    metadata.update(software_versions=versions or {"implementation": "source-only-authoring", "numpy": np.__version__}, warnings=[])
    with (output / "run_metadata.json").open("x") as handle:
        json.dump(metadata, handle, allow_nan=False)
    with (output / "cohort_results.json").open("x") as handle:
        json.dump(own["results"], handle, allow_nan=False)
    with (output / "findings.md").open("x") as handle:
        handle.write("Descriptive calculation; no inference beyond the selected released derivatives.\n")
    return output


@pytest.fixture
def reference():
    method = s.read_json(Path(__file__).parents[1] / "environment/method_contract.json")
    ids = np.array(["person-a", "person-b", "person-c", "person-d"])
    rng = np.random.default_rng(1234)
    nuisance = rng.normal(size=(32, 3))
    raw = rng.normal(size=(4, 32, 4)) * 3 + 100
    # Deliberately supported within-pair correlations for these arithmetic
    # fixtures; undefined endpoints have their own separate manufactured case.
    raw[:, :, 1] = raw[:, :, 0] + .2 * (raw[:, :, 1] - 100)
    raw[:, :, 3] = raw[:, :, 2] + .2 * (raw[:, :, 3] - 100)
    clean, raw_sd, residual_sd, ranks = [], [], [], []
    for person in raw:
        c, rank, r, e = s.clean_parcels(person, nuisance)
        clean.append(c); raw_sd.append(r); residual_sd.append(e); ranks.append(rank)
    people = [dict(participant_id=str(person), source_row_index=i, group="child" if i < 2 else "adult",
                   age=4.0 if i < 2 else 25.0, bold_path=f"{person}.nii.gz", confounds_path=f"{person}.tsv",
                   n_frames=32, n_parcels=4, n_confounds=3, nuisance_rank=ranks[i], grid_id="synthetic_grid")
              for i, person in enumerate(ids)]
    parcels = [dict(parcel_id=i+1, source_lut_row_index=i, label=f"synthetic-{i}", hemisphere="LH",
                    network="A" if i < 2 else "B", native_voxel_count=2, target_voxel_count=1,
                    grid_id="synthetic_grid") for i in range(4)]
    header = dict(source_path="synthetic.nii", shape=[2, 2, 1, 32], affine=np.eye(4).tolist(),
                  storage_dtype="float32", intensity_slope=1.0, intensity_intercept=0.0,
                  zooms=[1.0]*4, spatial_units="unknown", temporal_units="unknown", qform_code=0, sform_code=2)
    headers = [dict(header, source_path=f"{person}.nii.gz", participant_id=str(person)) for person in ids]
    metadata = dict(status="ok", task_id=method["task_id"], method_id=method["method_id"],
                    source_manifest_sha256="a"*64, method_contract_sha256=s.METHOD_SHA256,
                    source_sha256={f"{person}.nii.gz": "b"*64 for person in ids},
                    source_observed=dict(n_source_participants=4, n_selected_participants=4, n_frames=32,
                                         n_parcels=4, group_counts={"child": 2, "adult": 2}, bold_headers=headers,
                                         atlas_header=header, selected_confound_columns=["x", "y", "z"], tr_seconds_used=None))
    return dict(method=method, participant_id=ids, frame_index=np.arange(32), parcel_id=np.arange(1, 5),
                raw_mean=raw, standardized_clean=np.array(clean), raw_sd=np.array(raw_sd),
                residual_sd=np.array(residual_sd), participants=people, parcels=parcels, metadata=metadata)


def mutate_npz(output, mutate):
    path = output / "connectivity.npz"
    with np.load(path, allow_pickle=False) as z:
        arrays = {k: z[k].copy() for k in z.files}
    mutate(arrays)
    np.savez_compressed(path, **arrays)


def mutate_json(output, filename, mutate):
    path = output / filename
    obj = json.loads(path.read_text())
    mutate(obj)
    path.write_text(json.dumps(obj))


def reject(output, ref, match=None):
    with pytest.raises((AssertionError, ValueError, KeyError, TypeError, OSError, EOFError), match=match):
        p.validate_output_directory(output, ref)


def test_complete_manufactured_output(tmp_path, reference):
    assert p.validate_output_directory(emit(tmp_path / "out", reference), reference)["n_participants"] == 4


def test_equivalent_axes_float32_columns_metadata(tmp_path, reference):
    out = emit(tmp_path / "out", reference, versions={"other_library": 12, "none": None})
    def permute(a):
        pi, fi, ri, ei = [3, 1, 0, 2], np.arange(31, -1, -1), [2, 0, 3, 1], [5, 3, 0, 2, 1, 4]
        a["participant_id"] = a["participant_id"][pi].astype("S")
        a["frame_index"] = a["frame_index"][fi].astype(float)
        a["parcel_id"] = a["parcel_id"][ri].astype(float)
        for k in ("raw_mean", "standardized_clean"):
            a[k] = a[k][np.ix_(pi, fi, ri)].astype(np.float32)
        for k in ("raw_sd", "residual_sd"):
            a[k] = a[k][np.ix_(pi, ri)].astype(np.float32)
        for k in ("pearson_r", "fisher_z", "positive_z"):
            a[k] = a[k][np.ix_(pi, ei)].astype(np.float32)
        for k in ("edge_i", "edge_j"):
            a[k] = a[k][ei].astype(float)
    mutate_npz(out, permute)
    for name in ("participants.csv", "parcels.csv", "segregation.csv"):
        rows = list(csv.DictReader((out / name).open()))
        write_csv(out / name, rows[::-1], list(rows[0])[::-1])
    mutate_json(out, "run_metadata.json", lambda m: (m.update(extra={"note": "allowed"}, warnings=[{"message": "diagnostic"}]), m["source_observed"]["bold_headers"].reverse()))
    p.validate_output_directory(out, reference)


def test_source_close_clean_own_recompute_not_secret_target(tmp_path, reference):
    c = reference["standardized_clean"].copy()
    c[0, :, 0] += 1e-6 * c[0, :, 1]
    out = emit(tmp_path / "out", reference, {"standardized_clean": c})
    p.validate_output_directory(out, reference)


@pytest.mark.parametrize("value,expected", [("9007199254740993", 9007199254740993),
                                             ("9.007199254740993e15", 9007199254740993),
                                             ("-9223372036854775808", -(2**63)), ("1e0", 1)])
def test_exact_integer_not_float_cast(value, expected):
    assert p.integer(value) == expected


@pytest.mark.parametrize("value", [True, "1.1", "NaN", "Infinity", "1e100000000", "9223372036854775808", "-9223372036854775809"])
def test_bad_integer(value):
    with pytest.raises(AssertionError):
        p.integer(value)


@pytest.mark.parametrize("axis", [np.array([True]), np.array([1.5]), np.array([np.nan]),
                                 np.array([np.inf]), np.array([2**63], dtype=np.uint64),
                                 np.array([float(2**63)]), np.array([1, 1])])
def test_bad_npz_integer_axes(axis):
    with pytest.raises(AssertionError):
        p.int_axis(axis, "key")


def test_json_integer_large_exact():
    p.match(9007199254740993, 9007199254740993, {"atol": 0, "rtol": 0})
    with pytest.raises(AssertionError):
        p.match(float(9007199254740993), 9007199254740993, {"atol": 0, "rtol": 0})


@pytest.mark.parametrize("text", ['{"x":NaN}', '{"x":Infinity}', '{"x":1e999}',
                                  '{"extra":{"deep":[1e999]}}', '{"x":1,"x":2}'])
def test_json_nonfinite_duplicates(tmp_path, text):
    f = tmp_path / "x.json"; f.write_text(text)
    with pytest.raises(AssertionError):
        s.read_json(f)


@pytest.mark.parametrize("field", ["raw_mean", "standardized_clean", "raw_sd", "residual_sd", "pearson_r", "fisher_z", "positive_z"])
def test_numeric_mismatch_each_array(tmp_path, reference, field):
    out = emit(tmp_path / "out", reference)
    mutate_npz(out, lambda a: a[field].__setitem__(tuple([0]*a[field].ndim), a[field].flat[0]+0.1))
    reject(out, reference)


@pytest.mark.parametrize("mode", ["missing", "duplicate_person", "duplicate_frame", "duplicate_parcel", "duplicate_edge",
                                  "bad_edge_orientation", "wrong_person", "nan", "inf", "boolean", "object", "partial"])
def test_malformed_npz(tmp_path, reference, mode):
    out = emit(tmp_path / "out", reference)
    def wrong(a):
        if mode == "missing": del a["raw_sd"]
        elif mode == "duplicate_person": a["participant_id"][0] = a["participant_id"][1]
        elif mode == "duplicate_frame": a["frame_index"][0] = a["frame_index"][1]
        elif mode == "duplicate_parcel": a["parcel_id"][0] = a["parcel_id"][1]
        elif mode == "duplicate_edge":
            a["edge_i"][0] = a["edge_i"][1]; a["edge_j"][0] = a["edge_j"][1]
        elif mode == "bad_edge_orientation": a["edge_j"][0] = a["edge_i"][0]
        elif mode == "wrong_person": a["participant_id"][0] = "person-X"
        elif mode in ("nan", "inf"): a["raw_mean"][0, 0, 0] = float(mode)
        elif mode == "boolean": a["raw_mean"] = np.ones(a["raw_mean"].shape, dtype=bool)
        elif mode == "object": a["raw_mean"] = a["raw_mean"].astype(object)
        else: a["raw_mean"] = a["raw_mean"][:, :-1]
    mutate_npz(out, wrong)
    reject(out, reference)


@pytest.mark.parametrize("mode", ["status", "source_hash", "extra_source", "method_hash", "rank", "units", "dtype", "header_duplicate", "bool_count", "tr", "group_extra"])
def test_source_metadata_contradictions(tmp_path, reference, mode):
    out = emit(tmp_path / "out", reference)
    def wrong(m):
        if mode == "status": m["status"] = "resource_pilot"
        elif mode == "source_hash": m["source_sha256"]["person-a.nii.gz"] = "c"*64
        elif mode == "extra_source": m["source_sha256"]["fake"] = "c"*64
        elif mode == "method_hash": m["method_contract_sha256"] = "0"*64
        elif mode == "units": m["source_observed"]["bold_headers"][0]["temporal_units"] = "sec"
        elif mode == "dtype": m["source_observed"]["bold_headers"][0]["storage_dtype"] = "int8"
        elif mode == "header_duplicate": m["source_observed"]["bold_headers"][0] = m["source_observed"]["bold_headers"][1]
        elif mode == "bool_count": m["source_observed"]["n_frames"] = True
        elif mode == "tr": m["source_observed"]["tr_seconds_used"] = 1
        elif mode == "group_extra": m["source_observed"]["group_counts"]["other"] = 0
    if mode == "rank":
        rows = list(csv.DictReader((out / "participants.csv").open())); rows[0]["nuisance_rank"] = "1"
        write_csv(out / "participants.csv", rows, list(rows[0]))
    else:
        mutate_json(out, "run_metadata.json", wrong)
    reject(out, reference)


@pytest.mark.parametrize("mode", ["mean", "contrast", "variance", "bool_count", "missing_null", "extra_group", "numeric_string"])
def test_summary_forgery(tmp_path, reference, mode):
    out = emit(tmp_path / "out", reference)
    def wrong(m):
        if mode == "mean": m["cohort"]["mean"] += .04
        elif mode == "contrast": m["adult_minus_child"]["estimate"] *= -1
        elif mode == "variance": m["cohort"]["sample_variance"] = -1e-10
        elif mode == "bool_count": m["n_undefined"] = False
        elif mode == "missing_null": del m["adult_minus_child"]["status"]
        elif mode == "extra_group": m["groups"]["other"] = m["groups"]["child"]
        else: m["n_defined"] = "4"
    mutate_json(out, "cohort_results.json", wrong)
    reject(out, reference)


@pytest.mark.parametrize("name", ["participants.csv", "parcels.csv", "segregation.csv", "connectivity.npz", "cohort_results.json", "run_metadata.json", "findings.md"])
def test_missing_artifact(tmp_path, reference, name):
    out = emit(tmp_path / "out", reference)
    (out / name).unlink()
    reject(out, reference)


@pytest.mark.parametrize("kind", ["empty", "json", "dangling", "fifo"])
def test_reserved_failure_receipt(tmp_path, reference, kind):
    out = emit(tmp_path / "out", reference)
    f = out / "failure_receipt.json"
    if kind == "dangling": f.symlink_to(out / "absent")
    elif kind == "fifo": os.mkfifo(f)
    else: f.write_text("" if kind == "empty" else '{"status":"failed_precondition"}')
    reject(out, reference, "failure_receipt")


@pytest.mark.parametrize("kind", ["file_link", "ancestor_link", "fifo"])
def test_output_io_nonregular(tmp_path, reference, kind):
    out = emit(tmp_path / "out", reference)
    if kind == "ancestor_link":
        link = tmp_path / "alias"; link.symlink_to(out, target_is_directory=True)
        reject(link, reference)
    else:
        f = out / "findings.md"; f.unlink()
        if kind == "file_link": f.symlink_to(tmp_path / "absent")
        else: os.mkfifo(f)
        reject(out, reference)


def test_coherent_wrong_source_primitives_fail(tmp_path, reference):
    c = reference["standardized_clean"].copy()
    c[:, :, 0] *= -1
    out = emit(tmp_path / "out", reference, {"standardized_clean": c})
    reject(out, reference, "source standardized_clean")


def test_fixed_own_derived_not_cascading_rounded_receipts(tmp_path, reference):
    out = emit(tmp_path / "out", reference)
    # Each receipt is independently near its own unrounded primitive-derived value.
    mutate_npz(out, lambda a: a["pearson_r"].__iadd__(9e-7))
    p.validate_output_directory(out, reference)


def test_zero_within_full_groups_null_and_accepted_boundary_change(tmp_path, reference):
    # Disjoint support and exactly representable L2=4 avoid asserting that a
    # floating reduction of cancelling irrational products is literally zero.
    a = np.r_[np.tile([1., -1.], 8), np.zeros(16)]
    b = np.r_[np.zeros(16), np.tile([1., -1.], 8)]
    values = np.column_stack([a, b, a, -b])
    ref = copy.deepcopy(reference)
    ref["standardized_clean"] = np.repeat(values[None], 4, axis=0)
    out = emit(tmp_path / "zero", ref)
    assert p.validate_output_directory(out, ref)["n_undefined"] == 4
    result = s.read_json(out / "cohort_results.json")
    assert result["cohort"]["mean"] is None and result["adult_minus_child"]["estimate"] is None
    perturbed = ref["standardized_clean"].copy()
    perturbed[:, :, 1] += 1e-6 * a
    out2 = emit(tmp_path / "small-positive", ref, {"standardized_clean": perturbed})
    assert p.validate_output_directory(out2, ref)["n_undefined"] == 0


@pytest.mark.parametrize("kind", ["constant", "nuisance_span", "nan", "too_small"])
def test_source_support_preconditions(kind):
    rng = np.random.default_rng(7)
    c = rng.normal(size=(32, 3)); raw = rng.normal(size=(32, 4))
    if kind == "constant": raw[:, 0] = .1
    elif kind == "nuisance_span": raw[:, 0] = c[:, 0]
    elif kind == "nan": c[0, 0] = np.nan
    else: raw *= 1e-13
    with pytest.raises(AssertionError): s.clean_parcels(raw, c)


def test_cleaning_center_scale_rank_and_constant_confound():
    rng = np.random.default_rng(5)
    c = rng.normal(size=(64, 2)); c = np.column_stack([c, c[:, 0], np.full(64, .1)])
    raw = rng.normal(size=(64, 4)) + 100
    cleaned, rank, raw_sd, residual_sd = s.clean_parcels(raw, c)
    assert rank == 2
    assert np.max(np.abs(cleaned.mean(0))) < 1e-14
    assert np.max(np.abs(cleaned.std(0, ddof=1)-1)) < 1e-14
    assert np.all(raw_sd > 0) and np.all(residual_sd > 0)


def test_geometry_continuous_boundary_and_half_ties():
    atlas = np.arange(3).reshape(3, 1, 1) + 1
    transform = np.eye(4); transform[0, 0] = .5
    result = s.nearest_labels(atlas, np.eye(4), (6, 1, 1), transform).ravel()
    assert result.tolist() == [1, 2, 2, 3, 3, 0]
    transform[0, 3] = -1e-10
    assert s.nearest_labels(atlas, np.eye(4), (1, 1, 1), transform).item() == 0


def test_parcel_means_full_data_finite_and_no_selection():
    labels = np.array([1, 1, 2, 0]).reshape(4, 1, 1)
    data = np.arange(12).reshape(4, 1, 1, 3).astype(float)
    means, counts = s.parcel_means(data, labels, [1, 2])
    assert counts.tolist() == [2, 1]
    assert np.array_equal(means[:, 0], [1.5, 2.5, 3.5])
    data[3, 0, 0, 0] = np.nan  # Even background nonfinite source is a failure.
    with pytest.raises(AssertionError): s.parcel_means(data, labels, [1, 2])


def test_scalar_metadata_tolerance_not_units_or_dtype_gate(tmp_path, reference):
    out = emit(tmp_path / "out", reference)
    mutate_json(out, "run_metadata.json", lambda m: m["source_observed"]["bold_headers"][0].update(intensity_slope=1+1e-9))
    p.validate_output_directory(out, reference)


def test_frozen_method_identity():
    assert s.digest(Path(__file__).parents[1] / "environment/method_contract.json") == s.METHOD_SHA256


def test_fresh_emitter_no_overwrite(tmp_path, reference):
    out = emit(tmp_path / "out", reference)
    before = s.digest(out / "connectivity.npz")
    with pytest.raises(FileExistsError): emit(out, reference)
    assert s.digest(out / "connectivity.npz") == before


def test_duplicate_npz_members(tmp_path, reference):
    out = emit(tmp_path / "out", reference)
    with zipfile.ZipFile(out / "connectivity.npz", "a") as archive:
        contents = archive.read("raw_mean.npy")
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("raw_mean.npy", contents)
    reject(out, reference, "Duplicate NPZ")


def test_cap_boundary_float32_receipts(tmp_path, reference):
    ref = copy.deepcopy(reference)
    ref["standardized_clean"][:, :, 1] = ref["standardized_clean"][:, :, 0]
    ref["standardized_clean"][:, :, 3] = -ref["standardized_clean"][:, :, 2]
    out = emit(tmp_path / "out", ref)
    mutate_npz(out, lambda a: a.update({k: a[k].astype(np.float32)
                                      for k in ("fisher_z", "positive_z")}))
    p.validate_output_directory(out, ref)
