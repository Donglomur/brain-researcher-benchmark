"""Bounded synthetic mechanics plus explicitly gated genuine-output regressions.

No fixture bank is scientific evidence. Genuine-output cases require artifacts
from parent-authorized original-source runs; this module never executes them.
"""
from __future__ import annotations
import copy
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import h5py
import numpy as np
import pytest

TASK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TASK/"tests"))
import proof_of_work as q
SPEC=importlib.util.spec_from_file_location("allen2p_independent_builder",Path(__file__).with_name("build_reference.py"))
BUILD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(BUILD)


def dump_json(path,value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+"\n")


def write_csv(path,fields,rows):
    with Path(path).open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def csv_rows(path):
    with Path(path).open(newline="") as stream:
        reader=csv.DictReader(stream)
        return reader.fieldnames,list(reader)


def synthetic_reference():
    """Four cells, two frequencies, sparse split support; no source-derived answers."""
    contract=q.read_json(TASK/"environment/method_contract.json")
    orientations=[];frequencies=[];blank=[]
    for direction in range(0,360,45):
        for frequency in (1.,2.):
            for _ in range(3):
                orientations.append(float(direction));frequencies.append(frequency);blank.append(0)
        if direction in (45,180,270):
            orientations.append(np.nan);frequencies.append(np.nan);blank.append(1)
    d=np.asarray(orientations);f=np.asarray(frequencies);p=len(d)
    phase=np.nan_to_num(d)*np.pi/180
    rng=np.random.RandomState(72)
    response=np.stack([.5+.4*np.cos(phase)+.2*np.cos(2*phase)+.01*rng.normal(size=p),
                       -.1+.2*np.cos(phase-.2)+.02*rng.normal(size=p),
                       np.zeros(p),np.ones(p)])
    ids=np.array([104,102,109,101]);rois=np.array(["r01","r03","r02","r09"])
    arrays=dict(cell_ids=ids,roi_ids=rois,source_row_ids=np.roll(np.arange(p),7),
        start_frame=np.arange(p)*3+20,end_frame=np.arange(p)*3+22,
        direction=d,temporal_frequency=f,blank_sweep=np.asarray(blank),trial_response=response)
    metadata=dict(status="ok",task_id=q.TASK_ID,method="same_trials",source_manifest_sha256="a"*64,
        source_nwb_sha256="b"*64,method_contract_sha256=hashlib.sha256((TASK/"environment/method_contract.json").read_bytes()).hexdigest(),
        source_sha256={"synthetic-only.nwb":"b"*64},ophys_experiment_id=501271265,targeted_structure="VISp",session_type="three_session_A",
        n_neurons_total=4,n_source_frames=1000,n_presentations_total=p,n_presentations_nonblank=int((arrays["blank_sweep"]==0).sum()),
        n_conditions=16,directions_deg=list(range(0,360,45)),temporal_frequencies_hz=[1.,2.],
        software_versions={"mechanics-fixture":"not-scientific-source"},method_contract=contract)
    return q.validate_reference({**arrays,"stats":{"pipeline_id":q.PIPELINE_ID,"metadata":metadata}})


def emit(output,ref,method):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    analysis=q.analyze(ref,method)
    write_csv(output/"presentations.csv",q.PRESENTATION_FIELDS,q.expected_presentations(ref))
    write_csv(output/"trial_responses.csv",q.TRIAL_FIELDS,
        (dict(cell_specimen_id=int(cid),source_row_id=int(rowid),mean_dff=float(ref["trial_response"][c,p]))
         for c,cid in enumerate(ref["cell_ids"]) for p,rowid in enumerate(ref["source_row_ids"])))
    write_csv(output/"condition_means.csv",q.CONDITION_FIELDS,analysis["condition_rows"])
    write_csv(output/"estimates.csv",q.ESTIMATE_FIELDS,analysis["estimates"])
    write_csv(output/"per_neuron.csv",q.CELL_FIELDS,analysis["neurons"])
    dump_json(output/"results.json",analysis["results"])
    metadata=dict(ref["stats"]["metadata"],method=method)
    dump_json(output/"run_metadata.json",metadata)
    (output/"findings.md").write_text("Descriptive calculation; no population inference.\n")
    return analysis


@pytest.fixture
def toy():return synthetic_reference()


@pytest.mark.parametrize("method",q.METHODS)
def test_both_methods_accept_complete_mechanics(tmp_path,toy,method):
    emit(tmp_path,toy,method)
    q.validate_output_directory(tmp_path,toy)


@pytest.mark.parametrize("value",["1","1.0","1e0",1,np.int64(1)])
def test_exact_integer_notation(value):
    assert q.integer(value)==1


@pytest.mark.parametrize("value",[True,False,"true","1.01","NaN","Inf","",2**64])
def test_invalid_integer(value):
    with pytest.raises(AssertionError):q.integer(value)


@pytest.mark.parametrize("value",[True,None,"","NaN","inf","-inf","not a number"])
def test_no_silent_nan_numeric_conversion(value):
    with pytest.raises(AssertionError):q.number(value)


@pytest.mark.parametrize("pref,other,expected",[(1.,-2.,-3.),(-2.,1.,3.),(1.,-1.+1e-12,(2.-1e-12)/1e-12)])
def test_signed_negative_and_tiny_denominator_are_not_clipped(pref,other,expected):
    denominator,value,status=q.ratio_values(pref,other,"ok")
    assert status=="ok" and denominator==pref+other
    assert value==(pref-other)/(pref+other)
    if abs(denominator)>.1:assert value==expected


def test_exact_zero_distinct_from_missing():
    assert q.ratio_values(1.,-1.,"ok")== (0.,None,"zero_denominator")
    assert q.ratio_values(1.,None,"ok")== (None,None,"missing_measurement_condition")
    assert q.ratio_values(None,None,"no_selection_conditions")== (None,None,"no_selection_conditions")


def test_zero_support_cells_retained_not_dropped(toy):
    result=q.analyze(toy,"same_trials")
    zero=result["neurons"][2]
    assert zero["osi"] is None and zero["dsi"] is None
    assert zero["n_valid_osi"]==zero["n_valid_dsi"]==0 and zero["selective"]==0
    assert result["results"]["n_neurons_total"]==4 and result["results"]["n_both_undefined"]==1


def test_condition_ties_direction_then_frequency(toy):
    result=q.analyze(toy,"same_trials")
    constant=result["estimates"][3]
    assert constant["preferred_direction_deg"]==0 and constant["preferred_temporal_frequency_hz"]==1


def test_rng_draws_include_blank_rows(toy):
    full=q.split_masks(len(toy["source_row_ids"]))
    filtered=q.split_masks(int(q.included(toy).sum()))
    assert not np.array_equal(full[:,q.included(toy)],filtered)
    generator=np.random.default_rng(0)
    for mask in full:np.testing.assert_array_equal(mask,generator.random(len(mask))<.5)


def test_mean_ratio_threshold_is_not_mean_split_flags(toy):
    result=q.analyze(toy,"repeated_split_mean_ratio")["results"]
    assert result["n_estimates_per_cell"]==100
    assert result["selective_fraction"]!=result["split_fraction_mean"]


def test_source_preference_stays_fixed_for_rounded_trial_values(toy):
    source=q.analyze(toy,"same_trials")
    rounded=toy["trial_response"].copy()
    chosen=(toy["direction"]==315)&(toy["temporal_frequency"]==2)
    rounded[3,chosen]+=1e-11
    own=q.analyze(toy,"same_trials",response=rounded,preferences=source["estimates"])
    assert own["estimates"][3]["preferred_direction_deg"]==0
    assert own["estimates"][3]["preferred_temporal_frequency_hz"]==1


@pytest.mark.parametrize("method",q.METHODS)
def test_metadata_minimal_extra_order_versions(tmp_path,toy,method):
    emit(tmp_path,toy,method)
    metadata=q.read_json(tmp_path/"run_metadata.json")
    metadata["software_versions"]={"independent":"different-actual-stack"}
    metadata["optional_note"]="ignored"
    dump_json(tmp_path/"run_metadata.json",metadata)
    for filename in ("presentations.csv","trial_responses.csv","condition_means.csv","estimates.csv","per_neuron.csv"):
        fields,rows=csv_rows(tmp_path/filename)
        for row in rows:
            row["extra"]="not graded"
            for field in set(fields)&q.INT_FIELDS:
                if row[field]:
                    before=q.integer(row[field])
                    row[field]=format(float(before),".17e")
                    assert q.integer(row[field])==before
        write_csv(tmp_path/filename,list(reversed(fields))+["extra"],list(reversed(rows)))
    q.validate_output_directory(tmp_path,toy)


def test_sourceclose_denominator_tampering_cannot_bypass_algebra():
    denominator,ratio,_=q.ratio_values(1.,-1.+1e-12,"ok")
    estimate={key:None for key in q.ESTIMATE_FIELDS}
    estimate.update(cell_specimen_id=1,replicate=0,selection_half="all",measurement_half="all",selection_status="ok",
        r_pref=1.,r_orth_plus=-1.+1e-12,r_orth_minus=-1.+1e-12,r_orth=-1.+1e-12,r_null=-1.+1e-12,
        osi_denominator=denominator,dsi_denominator=denominator,osi=ratio,dsi=ratio,osi_status="ok",dsi_status="ok")
    neuron=dict(cell_specimen_id=1,osi=ratio,dsi=ratio,n_valid_osi=1,n_valid_dsi=1,osi_status="defined",dsi_status="defined",selective=1)
    result=dict(method="same_trials",n_neurons_total=1,n_selective=1,selective_fraction=1.)
    q.validate_submitted_algebra({0:estimate},{0:neuron},result)
    changed=copy.deepcopy(estimate);changed["osi_denominator"]+=5e-11
    q.close(changed["osi_denominator"],denominator,"deliberately source-close denominator")
    with pytest.raises(AssertionError,match="denominator-derived ratio"):
        q.validate_submitted_algebra({0:changed},{0:neuron},result)


def test_independent_undefined_support_per_metric(toy):
    training=np.full((4,8,2),np.nan);training[:,0,0]=2
    counts=np.zeros((8,2),int);counts[0,0]=3
    measured=np.full_like(training,np.nan);measured[:,0,0]=2;measured[:,4,0]=1
    measurement_counts=counts.copy();measurement_counts[4,0]=2
    rows=q.estimate_rows(toy,training,counts,measured,measurement_counts,1,"A","B")
    assert all(r["osi_status"]=="missing_measurement_condition" and r["osi"] is None for r in rows)
    assert all(r["dsi_status"]=="ok" and r["dsi"]==1/3 for r in rows)
    empty=q.estimate_rows(toy,np.full_like(training,np.nan),np.zeros_like(counts),measured,measurement_counts,1,"A","B")
    assert all(r["selection_status"]=="no_selection_conditions" and r["n_selection_pref"] is None for r in empty)


def test_split_summary_categories_come_from_unrounded_source():
    pref=3.+8e-11;other=1.;denominator=pref+other;exact=(pref-other)/denominator
    source=[];submitted={}
    for rep in range(1,51):
        for half,other_half in (("A","B"),("B","A")):
            row=dict(cell_specimen_id=1,replicate=rep,selection_half=half,measurement_half=other_half,
                selection_status="ok",r_pref=pref,r_orth_plus=other,r_orth_minus=other,r_orth=other,r_null=other,
                osi_denominator=denominator,dsi_denominator=denominator,osi=exact,dsi=exact,osi_status="ok",dsi_status="ok")
            source.append(row);submitted[(rep,half)]=dict(row,osi=.5,dsi=.5)
    cells={1:dict(cell_specimen_id=1,osi=.5,dsi=.5,n_valid_osi=100,n_valid_dsi=100,
        osi_status="defined",dsi_status="defined",selective=1)}
    result=dict(method="repeated_split_mean_ratio",n_neurons_total=1,n_selective=1,selective_fraction=1.,
                split_fraction_mean=1.,split_fraction_sd=0.)
    q.validate_submitted_algebra(submitted,cells,result,source)


@pytest.mark.parametrize("field",["source_sha256","method_contract"])
def test_fixed_nested_identity_no_extra_sources_or_settings(tmp_path,toy,field):
    emit(tmp_path,toy,"same_trials")
    metadata=q.read_json(tmp_path/"run_metadata.json")
    metadata[field]["undeclared"]=True
    dump_json(tmp_path/"run_metadata.json",metadata)
    with pytest.raises(AssertionError):q.validate_output_directory(tmp_path,toy)


@pytest.mark.parametrize("method",q.METHODS)
@pytest.mark.parametrize("encoding",["mapping","digest"])
def test_single_source_hash_equivalent_encodings(tmp_path,toy,method,encoding):
    emit(tmp_path,toy,method)
    metadata=q.read_json(tmp_path/"run_metadata.json")
    if encoding=="digest":metadata["source_sha256"]=next(iter(metadata["source_sha256"].values()))
    dump_json(tmp_path/"run_metadata.json",metadata)
    before=(tmp_path/"run_metadata.json").read_bytes()
    q.validate_output_directory(tmp_path,toy)
    assert (tmp_path/"run_metadata.json").read_bytes()==before,"validation must not rewrite artifacts"


@pytest.mark.parametrize("value",[None,"",False,[],{},"c"*64,
    {"synthetic-only.nwb":"c"*64},{"wrong.nwb":"b"*64},
    {"synthetic-only.nwb":"b"*64,"extra.nwb":"b"*64}])
def test_source_hash_alias_rejects_missing_wrong_or_extra_identity(tmp_path,toy,value):
    emit(tmp_path,toy,"same_trials")
    metadata=q.read_json(tmp_path/"run_metadata.json");metadata["source_sha256"]=value
    dump_json(tmp_path/"run_metadata.json",metadata)
    with pytest.raises(AssertionError,match="source_sha256"):
        q.validate_output_directory(tmp_path,toy)


def test_source_hash_field_cannot_be_omitted(tmp_path,toy):
    emit(tmp_path,toy,"same_trials")
    metadata=q.read_json(tmp_path/"run_metadata.json");del metadata["source_sha256"]
    dump_json(tmp_path/"run_metadata.json",metadata)
    with pytest.raises(AssertionError,match="source_sha256"):
        q.validate_output_directory(tmp_path,toy)


def test_digest_alias_is_not_allowed_for_multiple_declared_sources():
    expected={"source_sha256":{"first.nwb":"b"*64,"second.nwb":"b"*64}}
    with pytest.raises(AssertionError,match="exactly one declared source"):
        q.normalize_source_hash({"source_sha256":"b"*64},expected)


@pytest.mark.parametrize("defect",["nwb_hash","manifest_hash","contract_hash","contract", "status", "count", "versions", "response", "result"])
def test_digest_alias_preserves_other_identity_and_scientific_checks(tmp_path,toy,defect):
    emit(tmp_path,toy,"same_trials")
    metadata=q.read_json(tmp_path/"run_metadata.json")
    metadata["source_sha256"]=next(iter(metadata["source_sha256"].values()))
    if defect=="nwb_hash":metadata["source_nwb_sha256"]="c"*64
    elif defect=="manifest_hash":metadata["source_manifest_sha256"]="c"*64
    elif defect=="contract_hash":metadata["method_contract_sha256"]="c"*64
    elif defect=="contract":metadata["method_contract"]["threshold"]=.6
    elif defect=="status":metadata["status"]="failed_precondition"
    elif defect=="count":metadata["n_neurons_total"]+=1
    elif defect=="versions":metadata["software_versions"]={}
    elif defect=="response":
        fields,records=csv_rows(tmp_path/"trial_responses.csv")
        records[0]["mean_dff"]=float(records[0]["mean_dff"])+1
        write_csv(tmp_path/"trial_responses.csv",fields,records)
    elif defect=="result":
        result=q.read_json(tmp_path/"results.json");result["selective_fraction"]+=.1
        dump_json(tmp_path/"results.json",result)
    dump_json(tmp_path/"run_metadata.json",metadata)
    with pytest.raises(AssertionError):q.validate_output_directory(tmp_path,toy)


def test_nwb_reader_preserves_row_pairing_and_custom_half_open_windows(tmp_path):
    path=tmp_path/"mechanics-only.nwb"
    data=np.arange(40,dtype=np.float32).reshape(2,20)-10
    with h5py.File(path,"w") as h:
        h[BUILD.CELLS+"/cell_specimen_ids"]=np.array([9,2])
        h[BUILD.CELLS+"/roi_ids"]=np.array([b"roi09",b"roi02"])
        h[BUILD.DFF+"/data"]=data
        h[BUILD.DFF+"/timestamps"]=np.arange(20,dtype=float)
        h[BUILD.STIM+"/features"]=np.array([b"blank_sweep",b"orientation",b"temporal_frequency"])
        h[BUILD.STIM+"/data"]=np.array([[0,45,2],[1,np.nan,np.nan]],np.float32)
        h[BUILD.STIM+"/frame_duration"]=np.array([[10,13],[2,4]],np.float32)
        h["/general/session_id"]=np.bytes_("501271265")
        h["/general/session_type"]=np.bytes_("three_session_A")
        h["/general/optophysiology/imaging_plane_1/location"]=np.bytes_("VISp")
    arrays,metadata=BUILD.read_nwb_arrays(path)
    np.testing.assert_array_equal(arrays["cell_ids"],[9,2])
    np.testing.assert_array_equal(arrays["roi_ids"],["roi09","roi02"])
    np.testing.assert_array_equal(arrays["source_row_ids"],[1,0])
    np.testing.assert_array_equal(arrays["trial_response"],np.stack([data[:,2:4].mean(1),data[:,10:13].mean(1)],axis=1))
    assert metadata["n_source_frames"]==20


def test_legacy_bank_fails_after_any_future_rebuild(tmp_path):
    path=tmp_path/"obsolete.npz"
    np.savez_compressed(path,ref_stats=np.asarray(json.dumps({"n_neurons":215})))
    with pytest.raises(AssertionError,match="obsolete"):q.load_reference(path)


@pytest.mark.parametrize("exit_code",[0,4])
def test_offline_python3_shell_control_flow(tmp_path,exit_code):
    script=(TASK/"tests/test.sh").read_text()
    binary=tmp_path/"bin";binary.mkdir()
    stub=binary/"python3";stub.write_text("#!/bin/sh\nexit \"$FAKE_EXIT\"\n");stub.chmod(0o755)
    local=tmp_path/"test.sh";local.write_text(script.replace("/logs/verifier",str(tmp_path/"logs")))
    process=subprocess.run(["/bin/bash",str(local)],env=dict(os.environ,PATH=str(binary)+os.pathsep+os.environ["PATH"],
                            FAKE_EXIT=str(exit_code)),capture_output=True,text=True,timeout=10)
    assert process.returncode==exit_code
    assert (tmp_path/"logs/reward.txt").read_text().strip()==("1" if exit_code==0 else "0")


@pytest.fixture(scope="module")
def real_reference():
    if not os.environ.get("REPAIR_SAME_OUTPUT") or not os.environ.get("REPAIR_SPLIT_OUTPUT"):
        pytest.skip("requires parent-executed original-source output for both methods")
    return q.load_reference()


@pytest.fixture(params=q.METHODS)
def real_submission(request,tmp_path,real_reference):
    key="REPAIR_SAME_OUTPUT" if request.param=="same_trials" else "REPAIR_SPLIT_OUTPUT"
    source=Path(os.environ[key]);assert source.is_dir()
    output=tmp_path/"copy";shutil.copytree(source,output)
    return output,real_reference,request.param


@pytest.fixture
def real_split_submission(tmp_path,real_reference):
    source=Path(os.environ["REPAIR_SPLIT_OUTPUT"]);assert source.is_dir()
    output=tmp_path/"copy";shutil.copytree(source,output)
    return output,real_reference,"repeated_split_mean_ratio"


def reject(output,reference):
    with pytest.raises(AssertionError):q.validate_output_directory(output,reference)


def mutate_csv(path,callback):
    fields,rows=csv_rows(path);callback(rows);write_csv(path,fields,rows)


def test_real_genuine_both_methods(real_submission):
    output,reference,_method=real_submission
    q.validate_output_directory(output,reference)


@pytest.mark.parametrize("method",q.METHODS)
def test_real_independent_positive(real_reference,method):
    key="REPAIR_INDEPENDENT_SAME_OUTPUT" if method=="same_trials" else "REPAIR_INDEPENDENT_SPLIT_OUTPUT"
    value=os.environ.get(key)
    if not value:pytest.skip("requires independent parent-executed participant files")
    assert Path(value).is_dir()
    q.validate_output_directory(value,real_reference)


def test_real_minimal_metadata_and_free_prose(real_submission):
    output,reference,_method=real_submission
    metadata=q.read_json(output/"run_metadata.json")
    required=reference["stats"]["metadata"]["method_contract"]["outputs"]["run_metadata.json"]
    metadata={key:metadata[key] for key in required}
    metadata["software_versions"]={"equivalent-implementation":"own-stack"}
    assert metadata["method_contract"]==q.read_json(TASK/"environment/method_contract.json")
    dump_json(output/"run_metadata.json",metadata)
    (output/"findings.md").write_text("A descriptive result from this recording.")
    q.validate_output_directory(output,reference)


def test_real_row_column_order_and_numeric_notation(real_submission):
    output,reference,_method=real_submission
    for filename in ("presentations.csv","trial_responses.csv","condition_means.csv","estimates.csv","per_neuron.csv"):
        fields,rows=csv_rows(output/filename)
        for row in rows:
            row["extra"]="ignored"
            for field in set(fields)&q.INT_FIELDS:
                if row[field]:
                    before=q.integer(row[field]);row[field]=format(float(before),".17e")
                    assert q.integer(row[field])==before
        write_csv(output/filename,list(reversed(fields))+["extra"],list(reversed(rows)))
    q.validate_output_directory(output,reference)


@pytest.mark.parametrize("filename",q.FILES)
def test_real_missing_outputs(real_submission,filename):
    output,reference,_method=real_submission;(output/filename).unlink();reject(output,reference)


@pytest.mark.parametrize("filename",["presentations.csv","trial_responses.csv","condition_means.csv","estimates.csv","per_neuron.csv"])
@pytest.mark.parametrize("operation",["drop","duplicate"])
def test_real_key_completeness(real_submission,filename,operation):
    output,reference,_method=real_submission
    mutate_csv(output/filename,lambda rows:rows.pop() if operation=="drop" else rows.append(dict(rows[0])))
    reject(output,reference)


@pytest.mark.parametrize("filename,field,bad",[
 ("trial_responses.csv","mean_dff","NaN"),("trial_responses.csv","mean_dff","Infinity"),
 ("trial_responses.csv","cell_specimen_id","true"),("presentations.csv","source_row_id","1.5"),
 ("condition_means.csv","mean_dff","garbage"),("estimates.csv","osi","NaN"),
 ("per_neuron.csv","osi","Infinity"),("per_neuron.csv","n_valid_osi",""),("per_neuron.csv","roi_id","alias")])
def test_real_malformed_required_numbers_or_ids(real_submission,filename,field,bad):
    output,reference,_method=real_submission
    mutate_csv(output/filename,lambda rows:rows[0].__setitem__(field,bad));reject(output,reference)


def test_real_rank_preserving_metric_transform(real_submission):
    output,reference,_method=real_submission
    def transform(rows):
        for row in rows:
            for field in ("osi","dsi"):
                if row[field]:row[field]=.5+2*(float(row[field])-.5)
    mutate_csv(output/"per_neuron.csv",transform)
    reject(output,reference)


def test_real_source_response_scale_preserving_ratios(real_submission):
    output,reference,method=real_submission
    forged=copy.deepcopy(reference);forged["trial_response"]=reference["trial_response"]*2
    emit(output,forged,method)
    reject(output,reference)


def test_real_swapped_cell_response_identity(real_submission):
    output,reference,method=real_submission
    forged=copy.deepcopy(reference);forged["trial_response"]=reference["trial_response"][::-1].copy()
    assert not np.array_equal(forged["trial_response"],reference["trial_response"])
    emit(output,forged,method);reject(output,reference)


def test_real_swapped_trial_identity(real_submission):
    output,reference,method=real_submission
    forged=copy.deepcopy(reference);forged["trial_response"]=reference["trial_response"][:,::-1].copy()
    assert not np.array_equal(forged["trial_response"],reference["trial_response"])
    emit(output,forged,method);reject(output,reference)


def test_real_wrong_preferred_condition(real_submission):
    output,reference,_method=real_submission
    def edit(rows):
        row=next(row for row in rows if row["selection_status"]=="ok")
        row["preferred_direction_deg"]=(float(row["preferred_direction_deg"])+45)%360
    mutate_csv(output/"estimates.csv",edit);reject(output,reference)


def test_real_split_rng_dropping_blank_rows(real_split_submission,monkeypatch):
    output,reference,method=real_split_submission
    included=q.included(reference);assert (~included).any()
    original=q.split_masks
    def wrong(n_presentations,n_replicates=50):
        masks=np.zeros((n_replicates,n_presentations),bool)
        masks[:,included]=original(int(included.sum()),n_replicates)
        return masks
    assert not np.array_equal(wrong(len(included)),original(len(included)))
    with monkeypatch.context() as context:
        context.setattr(q,"split_masks",wrong)
        emit(output,reference,method)
    reject(output,reference)


def test_real_threshold_before_mean_is_different_endpoint(real_split_submission):
    output,reference,method=real_split_submission
    result=q.read_json(output/"results.json")
    assert abs(result["selective_fraction"]-result["split_fraction_mean"])>q.FRACTION_ATOL
    result["selective_fraction"]=result["split_fraction_mean"]
    dump_json(output/"results.json",result);reject(output,reference)


def test_real_ratio_clipping_is_not_the_signed_estimator(real_submission):
    output,reference,method=real_submission
    fields,rows=csv_rows(output/"estimates.csv");changed=0
    for row in rows:
        for field in ("osi","dsi"):
            if row[field] and abs(float(row[field]))>1:
                row[field]=float(np.clip(float(row[field]),-1,1));changed+=1
    assert changed>0,"this actual-source clipping control is not discriminating"
    write_csv(output/"estimates.csv",fields,rows);reject(output,reference)


@pytest.mark.parametrize("field",["source_manifest_sha256","source_nwb_sha256","method_contract_sha256","source_sha256",
                                  "n_neurons_total","n_source_frames","n_presentations_total","status","method"])
def test_real_wrong_metadata(real_submission,field):
    output,reference,method=real_submission
    metadata=q.read_json(output/"run_metadata.json")
    if field.endswith("sha256"):metadata[field]={} if field=="source_sha256" else "f"*64
    elif field=="status":metadata[field]="resource_pilot"
    elif field=="method":metadata[field]=next(m for m in q.METHODS if m!=method)
    else:metadata[field]+=1
    dump_json(output/"run_metadata.json",metadata);reject(output,reference)


def test_real_empty_findings(real_submission):
    output,reference,_method=real_submission
    (output/"findings.md").write_text(" \n");reject(output,reference)
