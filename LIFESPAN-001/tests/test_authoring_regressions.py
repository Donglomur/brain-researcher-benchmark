"""Source-free adversarial and valid-equivalence tests; never load a bank."""
import csv
import io
import json
import os
from pathlib import Path
import struct
import zipfile

import numpy as np
import pytest

import fixture_support as f
import io_contract as c
import proof_of_work as p


@pytest.fixture(scope="module")
def reference(): return f.manufactured()


@pytest.fixture
def evidence(tmp_path, reference): return f.write_output(reference, tmp_path / "output")


def edit_json(root, name, action):
    path = root / name
    value = json.loads(path.read_text())
    action(value)
    path.write_text(json.dumps(value, allow_nan=False))


def edit_csv(root, name, action):
    path = root / name
    with path.open(newline="") as stream: rows = list(csv.DictReader(stream))
    action(rows)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def edit_npz(root, action):
    path = root / "connectome_primitives.npz"
    with np.load(path, allow_pickle=False) as z: a = {k:z[k] for k in z.files}
    action(a)
    with path.open("wb") as stream: np.savez_compressed(stream, **a)


@pytest.mark.parametrize("mode", ["ordinary", "constant", "all_constant", "fewer_clusters", "constant_age"])
def test_complete_defined_and_undefined(tmp_path, mode):
    ref = f.manufactured(mode=mode)
    out = f.write_output(ref, tmp_path / "out")
    assert p.validate(out, ref)["status"] == "ok"


def test_full_59_148_completeness(tmp_path):
    ref = f.manufactured(s=59, t=4, r=148)
    out = f.write_output(ref, tmp_path / "out")
    assert p.validate(out, ref)["n_subjects"] == 59
    edit_csv(out, "cohort.csv", lambda rows: rows.pop())
    with pytest.raises(ValueError): p.validate(out, ref)


@pytest.mark.parametrize("name", c.REQUIRED_FILES)
def test_missing_artifact(evidence, reference, name):
    (evidence / name).unlink()
    with pytest.raises(ValueError): p.validate(evidence, reference)


@pytest.mark.parametrize("name,field,value", [
    ("cohort.csv", "age_source", "99"), ("cohort.csv", "cohort_index", "1.5"),
    ("cohort.csv", "left_sha256", "forged"), ("cohort.csv", "n_valid_edges", "0"),
    ("cohort.csv", "sex", "changed"), ("parcels.csv", "annotation_id", "400"),
    ("parcels.csv", "hemisphere", "other"), ("parcels.csv", "vertex_count", "3"),
    ("connectome_summary.csv", "global_fisher_sum", "30"),
    ("connectome_summary.csv", "system_segregation", "0"),
    ("connectome_summary.csv", "n_between_edges", "1"),
    ("connectome_summary.csv", "age", "1"),
    ("roi_partition.csv", "status", "ok-but-different"),
])
def test_source_or_derived_csv_corruption(evidence, reference, name, field, value):
    edit_csv(evidence, name, lambda rows: rows[0].update({field:value}))
    with pytest.raises(ValueError): p.validate(evidence, reference)


@pytest.mark.parametrize("name", ["cohort.csv", "parcels.csv", "connectome_summary.csv", "roi_partition.csv"])
def test_duplicate_csv_identity(evidence, reference, name):
    edit_csv(evidence, name, lambda rows: rows.append(rows[0].copy()))
    with pytest.raises(ValueError): p.validate(evidence, reference)


@pytest.mark.parametrize("name", p.ARRAYS)
def test_missing_primitive(evidence, reference, name):
    edit_npz(evidence, lambda a: a.pop(name))
    with pytest.raises(ValueError): p.validate(evidence, reference)


@pytest.mark.parametrize("name", ["roi_timeseries", "raw_r", "fisher_z", "group_features"])
def test_fabricated_real_array(evidence, reference, name):
    def change(a): a[name].flat[1] += .01
    edit_npz(evidence, change)
    with pytest.raises(ValueError): p.validate(evidence, reference)


@pytest.mark.parametrize("name", ["subject_id", "roi_index", "frame_index", "vertex_index", "edge_roi_index"])
def test_duplicate_array_identity(evidence, reference, name):
    def change(a): a[name].flat[1] = a[name].flat[0]
    edit_npz(evidence, change)
    with pytest.raises(ValueError): p.validate(evidence, reference)


@pytest.mark.parametrize("name", ["edge_valid", "group_valid"])
def test_mask_mutation(evidence, reference, name):
    def change(a): a[name].flat[1] = not a[name].flat[1]
    edit_npz(evidence, change)
    with pytest.raises(ValueError): p.validate(evidence, reference)


def test_all_coherent_array_permutations(evidence, reference):
    def change(a):
        s,t,r = reference["basis"]["roi_timeseries"].shape
        sp, rp, ep, fp = np.arange(s)[::-1], np.arange(r)[::-1], np.arange(len(a["edge_roi_index"]))[::-1], np.arange(t)[::-1]
        a["subject_id"] = a["subject_id"][sp].astype("S")
        a["roi_index"] = a["roi_index"][rp].astype(float)
        a["roi_timeseries"] = a["roi_timeseries"].reshape(s,t,r)[sp][:,fp][:,:,rp].reshape(s*t,r).astype(float)
        a["frame_index"] = np.tile(fp, s)
        a["parcel_status"] = a["parcel_status"][np.ix_(sp,rp)].astype("S")
        for k in ("edge_valid", "raw_r", "fisher_z"): a[k] = a[k][np.ix_(sp,ep)]
        a["edge_valid"] = a["edge_valid"].astype(int)
        a["edge_roi_index"] = a["edge_roi_index"][ep,::-1]
        for k in ("group_valid", "group_features"): a[k] = a[k][np.ix_(rp,rp)]
        blocks = [a["vertex_index"][a["vertex_offsets"][j]:a["vertex_offsets"][j+1]][::-1] for j in rp]
        a["vertex_offsets"] = np.r_[0, np.cumsum([len(x) for x in blocks])]
        a["vertex_index"] = np.concatenate(blocks)
    edit_npz(evidence, change)
    assert p.validate(evidence, reference)["status"] == "ok"


def test_cluster_bijection_whitespace_and_rows(evidence, reference):
    mapping = {str(i):(" " if i == 0 else f"cluster-{i}") for i in range(7)}
    edit_csv(evidence, "roi_partition.csv", lambda rows: [row.update(network_id=mapping[row["network_id"]]) for row in rows])
    edit_json(evidence, "partition.json", lambda d: [row.update(network_id=mapping[row["network_id"]]) for row in d["clusters"]])
    for name in ("cohort.csv", "parcels.csv", "connectome_summary.csv", "roi_partition.csv"):
        edit_csv(evidence, name, lambda rows: rows.reverse())
    assert p.validate(evidence, reference)["status"] == "ok"


def test_wrong_coassignment_same_cluster_sizes(evidence, reference):
    def swap(rows):
        j = next(i for i, r in enumerate(rows) if r["network_id"] != rows[0]["network_id"])
        rows[0]["network_id"], rows[j]["network_id"] = rows[j]["network_id"], rows[0]["network_id"]
    edit_csv(evidence, "roi_partition.csv", swap)
    with pytest.raises(ValueError): p.validate(evidence, reference)


def test_neighbor_constant_jitter_accepted_canonical_status(tmp_path):
    ref = f.manufactured(mode="constant")
    out = f.write_output(ref, tmp_path / "out")
    def change(a): a["roi_timeseries"][::2,0] = np.nextafter(a["roi_timeseries"][::2,0], np.float32(np.inf))
    edit_npz(out, change)
    assert p.validate(out, ref)["status"] == "ok"
    edit_npz(out, change)
    with pytest.raises(ValueError): p.validate(out, ref)


def test_masked_nan_not_zero(tmp_path):
    ref = f.manufactured(mode="constant")
    out = f.write_output(ref, tmp_path / "out")
    edit_npz(out, lambda a: a["raw_r"].__setitem__(~a["edge_valid"], 0))
    with pytest.raises(ValueError): p.validate(out, ref)


def test_undefined_not_zero(tmp_path):
    ref = f.manufactured(mode="all_constant")
    out = f.write_output(ref, tmp_path / "out")
    edit_csv(out, "connectome_summary.csv", lambda rows: rows[0].update(global_connectivity="0"))
    with pytest.raises(ValueError): p.validate(out, ref)


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(status="resource_pilot"),
    lambda d: d.update(n_subjects=True),
    lambda d: d.update(n_subjects="5"),
    lambda d: d["overall_connectivity_vs_age"].update(pearson_r=str(d["overall_connectivity_vs_age"]["pearson_r"])),
    lambda d: d["overall_connectivity_vs_age"].update(p=-1e-20),
    lambda d: d["overall_connectivity_vs_age"].update(pearson_r=.99),
    lambda d: d["overall_connectivity_vs_age"].update(ci95=[1,-1]),
    lambda d: d["overall_connectivity_vs_age"].update(n_defined=4),
])
def test_endpoint_mutations(evidence, reference, mutate):
    edit_json(evidence, "results.json", mutate)
    with pytest.raises(ValueError): p.validate(evidence, reference)


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(method_contract_sha256="fake"),
    lambda d: d.update(source_manifest_sha256="fake"),
    lambda d: d["source_files"][0].update(sha256="fake"),
    lambda d: d["source_observed"].update(header_timing_unit="seconds"),
    lambda d: d["source_observed"]["subjects"][0].update(left_data_array_count=1),
    lambda d: d["cohort_order"].reverse(),
])
def test_metadata_mutations(evidence, reference, mutate):
    edit_json(evidence, "run_metadata.json", mutate)
    with pytest.raises(ValueError): p.validate(evidence, reference)


def test_extras_formats_and_noncanonical_software(evidence, reference):
    edit_json(evidence, "run_metadata.json", lambda d: d.update(extra={"timing":123.5}, software_versions={"alternative":"implementation"}, warnings=["different truthful wording"]))
    edit_json(evidence, "partition.json", lambda d: d.update(fit_diagnostics={"inertia":100000, "n_iter":300, "ungraded_extra":-17}))
    edit_npz(evidence, lambda a: a.update(extra_finite=np.array([4.])))
    edit_csv(evidence, "cohort.csv", lambda rows: [row.update(cohort_index=f"{float(row['cohort_index']):.1e}", extra="ordinary") for row in rows])
    path = evidence / "cohort.csv"
    path.write_bytes(b"\xef\xbb\xbf"+path.read_bytes())
    (evidence / "findings.md").write_text("A different interpretation, without required keywords.")
    assert p.validate(evidence, reference)["status"] == "ok"


def test_optional_unoccupied_centers(tmp_path):
    ref = f.manufactured(mode="fewer_clusters")
    out = f.write_output(ref, tmp_path / "out")
    labels = [c["network_id"] for c in ref["partition_doc"]["clusters"]]
    names = labels + [f"unoccupied-{i}" for i in range(7-len(labels))]
    edit_json(out, "partition.json", lambda d: d.update(fit_diagnostics=dict(centers=np.zeros((7,8)).tolist(), network_ids=names, roi_order=list(range(8)), inertia=0,n_iter=300)))
    assert p.validate(out, ref)["status"] == "ok"


@pytest.mark.parametrize("kind", ["file", "dangling", "directory"])
def test_failure_marker(evidence, reference, kind):
    path = evidence / "failure_report.json"
    if kind == "file": path.write_bytes(b"")
    elif kind == "directory": path.mkdir()
    else: path.symlink_to(evidence / "not-present")
    with pytest.raises(ValueError): p.validate(evidence, reference)


def test_preserve_existing_and_context_cleanup(evidence, reference):
    before = (evidence / "results.json").read_bytes()
    with pytest.raises(ValueError): f.write_output(reference, evidence)
    with f.artifact_copy(evidence) as copy:
        assert copy.exists()
        temp = copy.parent
    assert not temp.exists() and (evidence / "results.json").read_bytes() == before


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}'])
def test_strict_json(raw):
    with pytest.raises(ValueError): c.json_bytes(raw)


@pytest.mark.parametrize("value", [True, False, "1.2", "nan", "inf", None])
def test_integer_no_coercion(value):
    with pytest.raises(ValueError): c.integer(value)


def test_zip_header_allocation_bound():
    payload = io.BytesIO()
    np.lib.format.write_array_header_1_0(payload, dict(descr="<f8", fortran_order=False, shape=(10**12,)))
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z: z.writestr("huge.npy", payload.getvalue())
    with pytest.raises(ValueError): c.npz_bytes(archive.getvalue())


def test_no_pickle():
    stream = io.BytesIO(); np.savez(stream, obj=np.array([{}], dtype=object))
    with pytest.raises(ValueError): c.npz_bytes(stream.getvalue())


def test_output_symlink(evidence, reference):
    (evidence / "extra").symlink_to("/tmp")
    with pytest.raises(ValueError): p.validate(evidence, reference)


def test_copy_refuses_link_before_mutator(evidence, tmp_path):
    outside = tmp_path / "protected"
    outside.write_text("preserve")
    (evidence / "results.json").unlink()
    (evidence / "results.json").symlink_to(outside)
    with pytest.raises(ValueError):
        with f.artifact_copy(evidence) as copied:
            pytest.fail("mutation scope must not be reached")
    assert outside.read_text() == "preserve"


def test_total_cap_before_read(evidence, reference, monkeypatch):
    monkeypatch.setattr(c, "LIMIT", 100)
    with pytest.raises(ValueError): p.validate(evidence, reference)


@pytest.mark.parametrize("kind", ["dangling_member", "parent_link", "fifo"])
def test_artifact_copy_additional_guards(evidence, tmp_path, kind):
    source = evidence
    if kind == "dangling_member": (evidence / "extra").symlink_to(tmp_path / "absent")
    elif kind == "fifo": os.mkfifo(evidence / "fifo")
    else:
        link = tmp_path / "parent-link"
        link.symlink_to(evidence.parent, target_is_directory=True)
        source = link / evidence.name
    with pytest.raises(ValueError):
        with f.artifact_copy(source): pytest.fail("must fail before mutation scope")
