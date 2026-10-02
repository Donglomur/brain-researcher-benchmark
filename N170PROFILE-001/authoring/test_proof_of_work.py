"""Manufactured whole37 bundles only. No original reference or source imports."""
import copy
import csv
import json

import numpy as np
import pytest

import proof_of_work as pw
import proof_fixture_support as f


@pytest.fixture
def bundle(tmp_path):
    reference=f.manufactured_reference()
    return f.emit(tmp_path/"output",reference),reference


def read_json(path): return json.loads(path.read_text())
def read_csv(path):
    with path.open(newline="") as stream:return list(csv.DictReader(stream))
def read_npz(path):
    with np.load(path,allow_pickle=False) as z:return {k:z[k].copy() for k in z.files}


@pytest.mark.parametrize("kind",["ordinary","zero","positive","constant_amplitude","missing_one","missing_all"])
def test_full37_defined_constant_positive_and_endpoint_null_cases(tmp_path,kind):
    reference=f.manufactured_reference(kind);out=f.emit(tmp_path/"output",reference)
    result=pw.validate_bundle(out,reference)
    assert result["status"]=="accepted" and result["n_subjects"]==37
    report=read_json(out/"n170.json")
    if kind=="positive":
        assert report["amp_po8_uv"]>0 and report["onset_latency_ms"] is None
    if kind=="zero":
        assert report["amp_po8_ci95"]==[0,0] and report["onset_summary"]["n_defined"]==0
    if kind.startswith("missing"):
        assert report["amp_po8_uv"] is None


def test_all_named_axes_and_rows_may_be_coherently_permuted(bundle):
    out,reference=bundle;a=read_npz(out/"erp_evidence.npz")
    so=np.arange(37)[::-1];co=[1,0];ko=np.arange(154)[::-1];ho=np.arange(30)[::-1];eo=np.arange(len(a["epoch_subject_ids"]))[::-1]
    a["subject_ids"]=a["subject_ids"][so];a["condition_labels"]=a["condition_labels"][co]
    a["sample_offsets"]=a["sample_offsets"][ko]
    a["condition_defined"]=a["condition_defined"][np.ix_(so,co)]
    a["evoked_po8_uv"]=a["evoked_po8_uv"][np.ix_(so,co,ko)]
    a["rejection_channel_labels"]=a["rejection_channel_labels"][ho]
    a["epoch_subject_ids"]=a["epoch_subject_ids"][eo];a["epoch_source_event_index"]=a["epoch_source_event_index"][eo]
    a["epoch_peak_to_peak_uv"]=a["epoch_peak_to_peak_uv"][np.ix_(eo,ho)]
    a["epoch_po8_baseline_uv"]=a["epoch_po8_baseline_uv"][eo]
    np.savez(out/"erp_evidence.npz",**a)
    for name in ("annotations.csv","trials.csv","per_subject.csv"):
        rows=read_csv(out/name);f.write_csv(out/name,rows[::-1],list(rows[0])[::-1])
    meta=read_json(out/"run_metadata.json")
    meta["cohort"].reverse();meta["source_files"].reverse()
    for key in ("source_observed","analysis_observed"):meta[key]["persons"].reverse()
    f.write_json(out/"run_metadata.json",meta)
    assert pw.validate_bundle(out,reference)["status"]=="accepted"


def test_integral_numeric_axes_and_csv_scientific_notation_are_value_typed(bundle):
    out,reference=bundle;a=read_npz(out/"erp_evidence.npz")
    for key in ("sample_offsets","epoch_source_event_index"):a[key]=a[key].astype(float)
    np.savez(out/"erp_evidence.npz",**a)
    rows=read_csv(out/"trials.csv")
    for row in rows:
        for key in ("source_event_index","event_sample","epoch_first_sample","epoch_last_sample"):
            row[key]=str(row[key])+"e0"
    f.write_csv(out/"trials.csv",rows)
    assert pw.validate_bundle(out,reference)["status"]=="accepted"


def test_six_decimal_derived_receipts_do_not_become_downstream_inputs(bundle):
    out,reference=bundle;rows=read_csv(out/"per_subject.csv")
    for row in rows:
        for key in ("amp_po8_uv","onset_ms","measurement_baseline_uv","peak_time_ms","peak_uv","half_height_uv"):
            if row[key]!="":row[key]=f"{float(row[key]):.6f}"
    f.write_csv(out/"per_subject.csv",rows)
    def rounded(value):
        if type(value) is float:return round(value,6)
        if type(value) is dict:return {k:rounded(v) for k,v in value.items()}
        if type(value) is list:return [rounded(v) for v in value]
        return value
    f.write_json(out/"n170.json",rounded(read_json(out/"n170.json")))
    assert pw.validate_bundle(out,reference)["status"]=="accepted"


def test_bounded_extras_and_unstructured_prose_are_not_new_estimators(bundle):
    out,reference=bundle
    for name in ("run_metadata.json","n170.json"):
        doc=read_json(out/name);doc["description"]={"note":"optional","example":0}
        f.write_json(out/name,doc)
    rows=read_csv(out/"per_subject.csv")
    for row in rows:row["optional_note"]="descriptive"
    f.write_csv(out/"per_subject.csv",rows)
    a=read_npz(out/"erp_evidence.npz");a["extra"]=np.zeros((2,3,1));np.savez(out/"erp_evidence.npz",**a)
    (out/"findings.md").write_text("No prescribed words or numerical fingerprint.\n")
    (out/"extra.txt").write_text("Optional regular file.\n")
    assert pw.validate_bundle(out,reference)["status"]=="accepted"


def test_coherent_source_close_accepted_wave_replay_is_authoritative(tmp_path):
    reference=f.manufactured_reference();waves=reference["evoked_po8_uv"].copy()
    waves[:,0]*=1+2e-9
    out=f.emit(tmp_path/"output",reference,waves)
    assert np.any(waves!=reference["evoked_po8_uv"])
    assert pw.validate_bundle(out,reference)["status"]=="accepted"


@pytest.mark.parametrize("key",list(pw.ARRAYS))
def test_every_required_npz_array_is_required(bundle,key):
    out,reference=bundle;a=read_npz(out/"erp_evidence.npz");del a[key];np.savez(out/"erp_evidence.npz",**a)
    with pytest.raises(ValueError):pw.validate_bundle(out,reference)


@pytest.mark.parametrize("kind",["condition_flag","subject_alias","subject_duplicate","sample_shift","condition_alias",
    "channel_swap_values","event_duplicate","event_subject_alias","condition_swap_values","sign_flip","ptp_change","baseline_change","float_mask","bool_offset"])
def test_primitive_and_axis_bindings_reject_effective_mutations(bundle,kind):
    out,reference=bundle;a=read_npz(out/"erp_evidence.npz")
    if kind=="condition_flag":a["condition_defined"][0,0]=False
    elif kind=="subject_alias":a["subject_ids"]=a["subject_ids"].astype("U20");a["subject_ids"][0]="sub-2"
    elif kind=="subject_duplicate":a["subject_ids"][0]=a["subject_ids"][1]
    elif kind=="sample_shift":a["sample_offsets"][0]-=1
    elif kind=="condition_alias":a["condition_labels"][0]="Face"
    elif kind=="channel_swap_values":a["epoch_peak_to_peak_uv"][:,[0,1]]=a["epoch_peak_to_peak_uv"][:,[1,0]]
    elif kind=="event_duplicate":a["epoch_source_event_index"][1]=a["epoch_source_event_index"][0]
    elif kind=="event_subject_alias":a["epoch_subject_ids"]=a["epoch_subject_ids"].astype("U20");a["epoch_subject_ids"][0]="02"
    elif kind=="condition_swap_values":a["evoked_po8_uv"]=a["evoked_po8_uv"][:,::-1,:]
    elif kind=="sign_flip":a["evoked_po8_uv"]*=-1
    elif kind=="ptp_change":a["epoch_peak_to_peak_uv"][0,0]+=1
    elif kind=="baseline_change":a["epoch_po8_baseline_uv"][0]+=1
    elif kind=="float_mask":a["condition_defined"]=a["condition_defined"].astype(float)
    else:a["sample_offsets"]=a["sample_offsets"].astype(bool)
    np.savez(out/"erp_evidence.npz",**a)
    with pytest.raises(ValueError):pw.validate_bundle(out,reference)


def test_ptp_negative_within_rounding_tolerance_still_violates_domain(tmp_path):
    reference=f.manufactured_reference();reference["epoch_peak_to_peak_uv"][0,0]=0
    out=f.emit(tmp_path/"output",reference);a=read_npz(out/"erp_evidence.npz")
    a["epoch_peak_to_peak_uv"][0,0]=-5e-7;np.savez(out/"erp_evidence.npz",**a)
    with pytest.raises(ValueError,match="nonnegative"):pw.validate_bundle(out,reference)


def test_missing_condition_has_exact_zero_storage_not_tolerant_reactivation(tmp_path):
    reference=f.manufactured_reference("missing_one");out=f.emit(tmp_path/"output",reference)
    a=read_npz(out/"erp_evidence.npz");a["evoked_po8_uv"][0,0,0]=1e-15
    np.savez(out/"erp_evidence.npz",**a)
    with pytest.raises(ValueError,match="zero sentinel"):pw.validate_bundle(out,reference)


@pytest.mark.parametrize("file,kind",[("annotations.csv","drop"),("annotations.csv","duplicate"),
    ("annotations.csv","literal_type"),("annotations.csv","latency"),("annotations.csv","role"),
    ("annotations.csv","missing_json"),("trials.csv","drop"),("trials.csv","duplicate"),
    ("trials.csv","accepted"),("trials.csv","reason"),("trials.csv","sample"),("trials.csv","alias")])
def test_complete_source_event_and_rejection_ledger(bundle,file,kind):
    out,reference=bundle;rows=read_csv(out/file)
    if kind=="drop":rows.pop()
    elif kind=="duplicate":rows[-1]=rows[0].copy()
    elif kind=="literal_type":rows[0]["type_json"]='"0"'
    elif kind=="latency":rows[0]["latency_json"]="1002"
    elif kind=="role":rows[0]["event_role"]="face"
    elif kind=="missing_json":rows[0]["urevent_json"]=""
    elif kind=="accepted":rows[0]["accepted"]="false"
    elif kind=="reason":rows[0]["rejection_reason"]="peak_to_peak"
    elif kind=="sample":rows[0]["event_sample"]="0"
    else:rows[0]["subject_id"]="02"
    f.write_csv(out/file,rows)
    with pytest.raises(ValueError):pw.validate_bundle(out,reference)


@pytest.mark.parametrize("field,value",[("amp_po8_uv","999"),("onset_ms","77.7"),("onset_ms",""),
    ("peak_sample_offset","0"),("crossing_sample_offset","0"),("peak_selection","earliest_crossing"),
    ("amplitude_status","missing_condition"),("onset_status","numerical_zero_difference"),
    ("n_face_accepted","true"),("amp_po8_uv","NaN"),("amp_po8_uv","true"),("subject_id","02")])
def test_participant_own_measurement_and_typed_receipts(bundle,field,value):
    out,reference=bundle;rows=read_csv(out/"per_subject.csv");rows[0][field]=value
    f.write_csv(out/"per_subject.csv",rows)
    with pytest.raises(ValueError):pw.validate_bundle(out,reference)


@pytest.mark.parametrize("kind",["drop","duplicate","late","positive_fake_onset"])
def test_participant_membership_and_missing_null_patterns(tmp_path,kind):
    reference=f.manufactured_reference("positive" if kind=="positive_fake_onset" else "ordinary")
    out=f.emit(tmp_path/"output",reference);rows=read_csv(out/"per_subject.csv")
    if kind=="drop":rows.pop()
    elif kind=="duplicate":rows[-1]=rows[0].copy()
    elif kind=="late":rows[0]["onset_ms"]="200"
    else:rows[0]["onset_ms"]="80";rows[0]["onset_status"]="ok"
    f.write_csv(out/"per_subject.csv",rows)
    with pytest.raises(ValueError):pw.validate_bundle(out,reference)


@pytest.mark.parametrize("kind",["mean","ci","df","count","bool_count","bool_mean","negative_sd","negative_se","schema","electrode"])
def test_group_replay_domains_and_exact_counts(bundle,kind):
    out,reference=bundle;doc=read_json(out/"n170.json")
    if kind=="mean":doc["amp_po8_uv"]+=.1
    elif kind=="ci":doc["amp_po8_ci95"].reverse()
    elif kind=="df":doc["amplitude_summary"]["df"]=35
    elif kind=="count":doc["n_subjects"]=36
    elif kind=="bool_count":doc["n_subjects"]=True
    elif kind=="bool_mean":doc["amp_po8_uv"]=True
    elif kind=="negative_sd":doc["onset_summary"]["sample_sd"]=-5e-7
    elif kind=="negative_se":doc["onset_summary"]["standard_error"]=-5e-7
    elif kind=="schema":doc["schema_version"]="old"
    else:doc["electrode"]="PO7"
    f.write_json(out/"n170.json",doc)
    with pytest.raises(ValueError):pw.validate_bundle(out,reference)


def test_incomplete_cohort_cannot_report_available_case_summary(tmp_path):
    reference=f.manufactured_reference("missing_one");out=f.emit(tmp_path/"output",reference)
    doc=read_json(out/"n170.json");doc["amp_po8_uv"]=-2
    doc["amplitude_summary"].update(mean=-2,df=35,ci95=[-3,-1],status="ok")
    f.write_json(out/"n170.json",doc)
    with pytest.raises(ValueError):pw.validate_bundle(out,reference)


@pytest.mark.parametrize("kind",["source_pin","method_pin","schema_pin","kernel_pin","pilot","cohort_drop","source_sha",
    "file_drop","person_drop","person_duplicate","header_change","channel_change","analysis_count","software_type","warnings_type"])
def test_metadata_is_source_bound_not_a_description_only(bundle,kind):
    out,reference=bundle;doc=read_json(out/"run_metadata.json")
    if kind.endswith("_pin"):
        key={"source_pin":"source_manifest_sha256","method_pin":"method_contract_sha256","schema_pin":"output_schema_sha256",
             "kernel_pin":"measurement_kernel_sha256"}[kind];doc[key]="0"*64
    elif kind=="pilot":doc["status"]="resource_pilot"
    elif kind=="cohort_drop":doc["cohort"].pop()
    elif kind=="source_sha":doc["source_files"][0]["sha256"]="e"*64
    elif kind=="file_drop":doc["source_files"].pop()
    elif kind=="person_drop":doc["source_observed"]["persons"].pop()
    elif kind=="person_duplicate":doc["source_observed"]["persons"][-1]=doc["source_observed"]["persons"][0]
    elif kind=="header_change":doc["source_observed"]["persons"][0]["header_fields"]["srate"]=512
    elif kind=="channel_change":doc["source_observed"]["persons"][0]["channel_labels"][0]="PO8"
    elif kind=="analysis_count":doc["analysis_observed"]["persons"][0]["n_face_accepted"]=2
    elif kind=="software_type":doc["software_versions"]["python"]=3
    else:doc["warnings"]=""
    f.write_json(out/"run_metadata.json",doc)
    with pytest.raises(ValueError):pw.validate_bundle(out,reference)


@pytest.mark.parametrize("kind",["status","pins","ids","samples","channels"])
def test_private_reference_scope_cannot_be_pilot_or_mismatched(bundle,kind):
    out,reference=bundle
    if kind=="status":reference["status"]="resource_pilot"
    elif kind=="pins":reference["pins"]["method_contract_sha256"]="0"*64
    elif kind=="ids":reference["subjects"].pop()
    elif kind=="samples":reference["sample_offsets"][0]-=1
    else:reference["rejection_channel_labels"][0]="PO8"
    with pytest.raises(ValueError):pw.validate_bundle(out,reference)


def test_late_failure_marker_remains_authoritative(bundle,monkeypatch):
    out,reference=bundle;original=pw.validate_groups
    def late(*args):
        original(*args);(out/"failure_report.json").write_text('{"reason":"late"}')
    monkeypatch.setattr(pw,"validate_groups",late)
    with pytest.raises(ValueError,match="late authoritative"):pw.validate_bundle(out,reference)


@pytest.mark.parametrize("kind",["empty","failure","missing"])
def test_required_output_and_findings_failure_guards(bundle,kind):
    out,reference=bundle
    if kind=="empty":(out/"findings.md").write_text("   ")
    elif kind=="failure":(out/"failure_report.json").write_text("{}")
    else:(out/"findings.md").unlink()
    with pytest.raises(ValueError):pw.validate_bundle(out,reference)
