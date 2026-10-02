"""Manufactured FCSTAB verifier fixtures. No originals, caches or bank paths."""
import copy
import hashlib
import json
import sys
import types

import numpy as np
import pytest

import artifact_reader as io
import fixture_support as fs
import output_contract as contract


@pytest.fixture
def prepared(monkeypatch):
    fs.freeze_manufactured_authority(monkeypatch)
    ref = fs.reference()
    return ref,fs.artifacts(ref)


def grade(tmp_path,ref,data):
    return contract.validate(fs.write_output(tmp_path/"output",data),ref)


def test_full40_200_source_bound_genuine(tmp_path,prepared):
    ref,data = prepared
    assert len(data["summary.json"]["source_observed"]["phenotype_ledger"]) == 1112
    assert data["connectivity.npz"]["fisher_z"].shape == (40,3,6)
    assert grade(tmp_path,ref,data) == dict(status="accepted",n_subjects=40,n_edges=6,k=1)


def test_all_axes_keyed_lists_and_storage_orders_permute(tmp_path,prepared):
    ref,data = prepared
    fs.permute_axes(data)
    assert grade(tmp_path,ref,data)["status"] == "accepted"


def test_integral_numeric_axes_and_numeric_json_counts(tmp_path,prepared):
    ref,data = prepared
    for key in ("roi_ids","edge_roi_i","edge_roi_j"):
        data["connectivity.npz"][key] = data["connectivity.npz"][key].astype(float)
    for row in data["stability.csv"]: row["n_edges"] = "6e0"
    for row in data["selection_evidence.json"]["subjects"]:
        for scheme in contract.SCHEMES: row[scheme+"_edge_indices"] = list(map(float,row[scheme+"_edge_indices"]))
    data["summary.json"]["n_subjects"] = 40.0
    assert grade(tmp_path,ref,data)["status"] == "accepted"


def test_float32_source_close_own_replay(tmp_path,prepared):
    ref,_ = prepared
    data = fs.artifacts(ref,z=ref["fisher_z"].astype(np.float32))
    assert grade(tmp_path,ref,data)["status"] == "accepted"


def test_descriptive_extras_are_not_hidden_targets(tmp_path,prepared):
    ref,data = prepared
    data["connectivity.npz"]["descriptive"] = np.zeros((1,1,1,2),dtype=np.int16)
    data["summary.json"]["optional_average"] = 17.25
    data["summary.json"]["source_inference_support"]["forward"]["diagnostic_norm"] = 3.0
    for row in data["stability.csv"]: row["note"] = "ordinary descriptive extra"
    root = fs.write_output(tmp_path/"output",data)
    (root/"README.txt").write_text("bounded harmless extra",encoding="utf-8")
    assert contract.validate(root,ref)["status"] == "accepted"


def test_utf8_bom_and_csv_column_reorder(tmp_path,prepared):
    ref,data = prepared
    data["stability.csv"] = [dict(reversed(list(row.items()))) for row in data["stability.csv"]]
    root = fs.write_output(tmp_path/"output",data)
    for name in ("stability.csv","summary.json","selection_evidence.json"):
        path = root/name
        path.write_bytes(b"\xef\xbb\xbf"+path.read_bytes())
    assert contract.validate(root,ref)["status"] == "accepted"


def test_duplicate_means_are_independently_rounded_receipts(tmp_path,prepared):
    ref,data = prepared
    for row in data["selection_evidence.json"]["subjects"]:
        for means in row["means"].values():
            for key in ("first","second"): means[key] = round(means[key],6)
    # Do not force equality to independently serialized forward CSV means.
    assert grade(tmp_path,ref,data)["status"] == "accepted"


def test_accepted_reliability_receipts_drive_summary(tmp_path,prepared):
    ref,data = prepared
    rel = {row["subject_id"]:copy.deepcopy(row["reliability"]) for row in data["selection_evidence.json"]["subjects"]}
    for row in rel.values():
        row["edge_pearson"] = round(row["edge_pearson"],6)
        row["edge_spearman"] = round(row["edge_spearman"],6)
    modified = fs.artifacts(ref,accepted_reliability=rel)
    assert grade(tmp_path,ref,modified)["status"] == "accepted"


def test_source_constant_accepted_jitter_keeps_inference_unavailable(tmp_path,monkeypatch):
    fs.freeze_manufactured_authority(monkeypatch)
    ref = fs.reference(constant_edges=True)
    z = ref["fisher_z"] + np.linspace(-1e-8,1e-8,6)[None,None,:]
    data = fs.artifacts(ref,z=z)
    assert all(row["reliability"]["edge_pearson"] is None for row in data["selection_evidence.json"]["subjects"])
    assert grade(tmp_path,ref,data)["status"] == "accepted"


def test_source_constant_delta_keeps_own_descriptors_and_count(tmp_path,monkeypatch):
    fs.freeze_manufactured_authority(monkeypatch)
    ref = fs.reference(zero_delta=True)
    rows = fs.artifacts(ref)["stability.csv"]
    for i,row in enumerate(rows):
        for scheme in contract.SCHEMES: row[scheme+"_delta"] = (-1 if i%2 else 1)*2e-8
    data = fs.artifacts(ref,accepted_rows=rows)
    for group in data["summary.json"]["selection_schemes"].values():
        assert group["n_negative"] == 20 and group["delta_sd"] > 0
        assert group["t"] is None and group["inference_status"] == "source_zero_variance"
    assert grade(tmp_path,ref,data)["status"] == "accepted"


def test_accepted_close_tie_change_selects_own_set_not_source_set(tmp_path,prepared):
    ref,_ = prepared
    ref["fisher_z"][:,0,:] = [.2,.2,.1,0,-.1,-.2]
    z = ref["fisher_z"].copy(); z[:,0,1] += 1e-10
    data = fs.artifacts(ref,z=z)
    assert data["selection_evidence.json"]["subjects"][0]["forward_edge_indices"] == [1]
    assert grade(tmp_path,ref,data)["status"] == "accepted"


def test_numerical_uniform_delta_shift_caught_before_stale_summary(tmp_path,prepared):
    ref,_ = prepared
    ref["fisher_z"][:,0,:] = [-.3,-.2,-.1,.1,.2,.3]
    ref["fisher_z"][:,2,:] = ref["fisher_z"][:,0,:]
    for i in range(40): ref["fisher_z"][i,1,:] = ref["fisher_z"][i,0,:] + .125 + (-1 if i%2 else 1)*2**-20
    data = fs.artifacts(ref)
    for row in data["stability.csv"]:
        for scheme in contract.SCHEMES: row[scheme+"_delta"] += 2**-24
    with pytest.raises(io.ArtifactError,match="delta full-error fidelity"):
        grade(tmp_path,ref,data)


def test_source_small_centered_edge_relative_fidelity_is_enforced(tmp_path,prepared):
    ref,_ = prepared
    ref["fisher_z"][:,0,:] = .1+np.arange(6)*1e-10
    data = fs.artifacts(ref)
    data["connectivity.npz"]["fisher_z"][:,0,0] += 1e-8
    with pytest.raises(io.ArtifactError,match="edge centered fidelity"):
        grade(tmp_path,ref,data)


def mutate(data,case):
    a,e,s = data["connectivity.npz"],data["selection_evidence.json"],data["summary.json"]
    row = e["subjects"][0]
    if case == "missing_array": del a["roi_ids"]
    elif case == "missing_csv_column":
        for r in data["stability.csv"]: del r["random_delta"]
    elif case == "subject_duplicate": a["subject_ids"][0] = a["subject_ids"][1]
    elif case == "subject_file_id_alias": a["subject_ids"] = np.array(["PITT_fixture_"+sid for sid in a["subject_ids"]])
    elif case == "segment_duplicate": a["segment_ids"][0] = "second"
    elif case == "roi_duplicate": a["roi_ids"][0] = 2
    elif case == "roi_fraction": a["roi_ids"] = a["roi_ids"].astype(float)+.5
    elif case == "roi_boolean": a["roi_ids"] = a["roi_ids"].astype(bool)
    elif case == "edge_swap_orientation": a["edge_roi_i"][0],a["edge_roi_j"][0] = a["edge_roi_j"][0],a["edge_roi_i"][0]
    elif case == "edge_duplicate": a["edge_roi_i"][0],a["edge_roi_j"][0] = a["edge_roi_i"][1],a["edge_roi_j"][1]
    elif case == "support_mask": a["common_roi_mask"][0] = False
    elif case == "support_float_mask": a["common_roi_mask"] = a["common_roi_mask"].astype(float)
    elif case == "z_bool": a["fisher_z"] = a["fisher_z"].astype(bool)
    elif case == "z_wrong_axes": a["fisher_z"] = a["fisher_z"].transpose(0,2,1)
    elif case == "z_wrong_sign": a["fisher_z"] *= -1
    elif case == "z_mean_replaced": a["fisher_z"][0,0] = np.mean(a["fisher_z"][0,0])
    elif case == "z_nonfinite": a["fisher_z"][0,0,0] = np.nan
    elif case == "csv_duplicate": data["stability.csv"][0] = copy.deepcopy(data["stability.csv"][1])
    elif case == "csv_n_edges_k": data["stability.csv"][0]["n_edges"] = 1
    elif case == "csv_delta": data["stability.csv"][0]["forward_delta"] += .01
    elif case == "csv_first": data["stability.csv"][0]["forward_first_half"] += .01
    elif case == "csv_nonfinite": data["stability.csv"][0]["random_delta"] = "nan"
    elif case == "training_self": row["training_subject_ids"][0] = row["subject_id"]
    elif case == "training_duplicate": row["training_subject_ids"][0] = row["training_subject_ids"][1]
    elif case == "selected_wrong": row["forward_edge_indices"][0] = (row["forward_edge_indices"][0]+1)%6
    elif case == "selected_bool": row["forward_edge_indices"] = [True]
    elif case == "selected_numeric_string": row["forward_edge_indices"] = [str(row["forward_edge_indices"][0])]
    elif case == "selected_out_of_range": row["random_edge_indices"] = [6]
    elif case == "evidence_duplicate_person": e["subjects"][0] = copy.deepcopy(e["subjects"][1])
    elif case == "evidence_mean": row["means"]["reverse"]["first"] += .01
    elif case == "reliability_value": row["reliability"]["edge_pearson"] = 0 if abs(row["reliability"]["edge_pearson"])>.1 else .8
    elif case == "reliability_bool": row["reliability"]["edge_pearson"] = True
    elif case == "reliability_status": row["reliability"]["status"] = "source_constant"
    elif case == "reliability_outside_domain": row["reliability"]["overlap"] = 1.00000001
    elif case == "evidence_pin": e["pins"]["source_manifest_sha256"] = "a"*64
    elif case == "evidence_seed": e["seed"] = 1
    elif case == "evidence_count_bool": e["n_edges"] = True
    elif case == "summary_pin": s["pins"]["method_contract_sha256"] = "b"*64
    elif case == "summary_status": s["status"] = "resource_pilot"
    elif case == "summary_count_string": s["n_subjects"] = "40"
    elif case == "summary_group_float_string": s["selection_schemes"]["forward"]["delta_mean"] = str(s["selection_schemes"]["forward"]["delta_mean"])
    elif case == "summary_own_count": s["selection_schemes"]["forward"]["n_negative"] = 41
    elif case == "summary_group_value": s["selection_schemes"]["reverse"]["delta_mean"] += .1
    elif case == "summary_abs_t": s["selection_schemes"]["independent"]["t"] = 1000.
    elif case == "summary_tost_boolean": s["equivalence"]["equivalent_within_margin"] = not s["equivalence"]["equivalent_within_margin"]
    elif case == "summary_tost_null": s["equivalence"]["tost_p"] = None
    elif case == "summary_reliability": s["reliability"]["edge_spearman"]["mean"] = .99
    elif case == "summary_support_status": s["source_inference_support"]["forward"]["status"] = "source_zero_variance"
    elif case == "cohort_crossjoin": s["cohort"][0]["subject_id"] = s["cohort"][1]["subject_id"]
    elif case == "source_record_hash": s["source_files"][0]["sha256"] = "a"*64
    elif case == "source_missing_file": s["source_files"].pop()
    elif case == "source_extra_file": s["source_files"].append(dict(path="invented",sha256="b"*64))
    elif case == "source_duplicate_file": s["source_files"].append(copy.deepcopy(s["source_files"][0]))
    elif case == "phenotype_missing": s["source_observed"]["phenotype_ledger"].pop()
    elif case == "phenotype_duplicate": s["source_observed"]["phenotype_ledger"][0] = copy.deepcopy(s["source_observed"]["phenotype_ledger"][1])
    elif case == "phenotype_token": s["source_observed"]["phenotype_ledger"][0]["tokens"]["SITE_ID"] = "OTHER"
    elif case == "phenotype_bool_integer": s["source_observed"]["phenotype_ledger"][0]["selected_derivative"] = 1
    elif case == "source_mask_metadata": next(iter(s["source_observed"]["persons"].values()))["segment_support"]["first"][0] = False
    elif case == "header_order": next(iter(s["source_observed"]["persons"].values()))["source_column_ids"].reverse()
    elif case == "source_unknown_person": s["source_observed"]["persons"]["UNKNOWN"] = copy.deepcopy(next(iter(s["source_observed"]["persons"].values())))
    elif case == "software_missing": del s["software"]["scipy"]
    elif case == "findings_empty": data["findings.md"] = " \n"
    else: raise AssertionError(case)


@pytest.mark.parametrize("case",[
    "missing_array","missing_csv_column","subject_duplicate","subject_file_id_alias","segment_duplicate","roi_duplicate",
    "roi_fraction","roi_boolean","edge_swap_orientation","edge_duplicate","support_mask","support_float_mask",
    "z_bool","z_wrong_axes","z_wrong_sign","z_mean_replaced","z_nonfinite","csv_duplicate","csv_n_edges_k","csv_delta","csv_first","csv_nonfinite",
    "training_self","training_duplicate","selected_wrong","selected_bool","selected_numeric_string","selected_out_of_range","evidence_duplicate_person","evidence_mean",
    "reliability_value","reliability_bool","reliability_status","reliability_outside_domain","evidence_pin","evidence_seed","evidence_count_bool",
    "summary_pin","summary_status","summary_count_string","summary_group_float_string","summary_own_count","summary_group_value","summary_abs_t","summary_tost_boolean",
    "summary_tost_null","summary_reliability","summary_support_status","cohort_crossjoin","source_record_hash","source_missing_file","source_extra_file","source_duplicate_file",
    "phenotype_missing","phenotype_duplicate","phenotype_token","phenotype_bool_integer","source_mask_metadata","header_order","source_unknown_person","software_missing","findings_empty"])
def test_effective_binding_or_own_replay_mutants(tmp_path,prepared,case):
    ref,data = prepared
    mutate(data,case)
    root = fs.write_output(tmp_path/"output",data)
    with pytest.raises(io.ArtifactError): contract.validate(root,ref)


@pytest.mark.parametrize("name",io.REQUIRED)
def test_each_required_artifact_missing(tmp_path,prepared,name):
    ref,data = prepared
    root = fs.write_output(tmp_path/"output",data)
    (root/name).unlink()
    with pytest.raises(io.ArtifactError): contract.validate(root,ref)


@pytest.mark.parametrize("marker",["regular","dangling","directory"])
def test_failure_markers_are_authoritative(tmp_path,prepared,marker):
    ref,data = prepared
    root = fs.write_output(tmp_path/"output",data)
    path = root/io.FAILURE
    if marker=="regular": path.write_text("{}")
    elif marker=="dangling": path.symlink_to(root/"absent")
    else: path.mkdir()
    with pytest.raises(io.ArtifactError,match="failure"): contract.validate(root,ref)


def test_late_failure_marker(tmp_path,prepared,monkeypatch):
    ref,data = prepared
    root = fs.write_output(tmp_path/"output",data)
    load = contract.load_kernel
    def late():
        module = load(); analyze = module.analyze
        def wrapped(*args,**kwargs):
            result = analyze(*args,**kwargs)
            (root/io.FAILURE).write_text("{}")
            return result
        module.analyze = wrapped
        return module
    monkeypatch.setattr(contract,"load_kernel",late)
    with pytest.raises(io.ArtifactError,match="late authoritative"): contract.validate(root,ref)


@pytest.mark.parametrize("pin",["SOURCE_SHA","METHOD_SHA","SCHEMA_SHA","IDS_SHA","KERNEL_SHA"])
def test_unfrozen_authority_fails_closed(tmp_path,prepared,monkeypatch,pin):
    ref,data = prepared
    monkeypatch.setattr(contract,pin,None)
    with pytest.raises(io.ArtifactError,match="authority not frozen"): grade(tmp_path,ref,data)


def test_cached_kernel_substitution_not_used(tmp_path,prepared,monkeypatch):
    ref,data = prepared
    poison = types.ModuleType("_fcstab_private_selection_kernel")
    poison.analyze = lambda *args,**kwargs: pytest.fail("cached helper imported")
    monkeypatch.setitem(sys.modules,"_fcstab_private_selection_kernel",poison)
    assert grade(tmp_path,ref,data)["status"] == "accepted"
    assert sys.modules["_fcstab_private_selection_kernel"] is poison


def test_private_kernel_changed_fails_before_exec(tmp_path,prepared,monkeypatch):
    ref,data = prepared
    code = tmp_path/"private"; code.mkdir()
    (code/"selection_kernel.py").write_text("raise RuntimeError('must not execute')\n")
    monkeypatch.setattr(contract,"__file__",str(code/"output_contract.py"))
    with pytest.raises(io.ArtifactError,match="kernel identity"): grade(tmp_path,ref,data)


def test_reference_partial_scope_rejected(tmp_path,prepared):
    ref,data = prepared
    ref["status"] = "resource_pilot"
    with pytest.raises(io.ArtifactError,match="reference scope"): grade(tmp_path,ref,data)


def test_inputs_not_mutated(tmp_path,prepared):
    ref,data = prepared
    original_z = ref["fisher_z"].copy()
    original_meta = copy.deepcopy(ref["source_observed"])
    root = fs.write_output(tmp_path/"output",data)
    hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
    contract.validate(root,ref)
    assert np.array_equal(original_z,ref["fisher_z"])
    assert original_meta == ref["source_observed"]
    assert hashes == {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
