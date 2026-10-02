"""Manufactured integration only; no original or old-reference access."""
import copy
from decimal import Decimal
import json

import numpy as np
import pytest

import fixture_support as f
import proof_of_work as p
import reference_composition as c
import numerical_contract as n


@pytest.fixture(scope="module")
def reference(): return f.manufactured_reference()


def accepted(tmp_path,ref,data): return p.validate_output_directory(f.emit(tmp_path/"output",data),ref)


def test_full_manufactured_positive(reference,tmp_path):
    assert accepted(tmp_path,reference,f.payload(reference))["fits"]==6


def test_coherent_all_axes_and_rows(reference,tmp_path):
    data=f.payload(reference)
    data["glm_arrays.npz"]=f.coherent_permutation(data["glm_arrays.npz"])
    for name,value in data.items():
        if name.endswith(".csv"): value.reverse()
    metadata=data["run_metadata.json"]
    metadata["selected_participant_ids"].reverse()
    metadata["fits"].reverse(); metadata["source_files"].reverse()
    metadata["source_observed"]["participants"].reverse()
    metadata["source_observed"]["atlas"]["label_ids"].reverse()
    data["group_stats.json"]["models"].reverse()
    for record in data["group_stats.json"]["models"]:
        record["roi_ids"].reverse(); record["weights"].reverse()
    assert accepted(tmp_path,reference,data)["status"]=="accepted"


def test_float32_and_integral_float_axes(reference,tmp_path):
    data=f.payload(reference)
    for k,v in data["glm_arrays.npz"].items():
        if v.dtype.kind=="f": data["glm_arrays.npz"][k]=v.astype(np.float32)
        elif v.dtype.kind in "iu": data["glm_arrays.npz"][k]=v.astype(float)
    arrays=p.canonical_arrays(data["glm_arrays.npz"],reference)
    data["group_stats.json"]=c.own_groups(reference,arrays["contrast_estimate"],data["activation.csv"])
    assert accepted(tmp_path,reference,data)["status"]=="accepted"


def test_extra_descriptions_versions_warning_types_dtype_alias(reference,tmp_path):
    data=f.payload(reference)
    meta=data["run_metadata.json"]
    meta["software_versions"]={"equivalent_solver":3}
    meta["warnings"]=[{"category":"example","message":"descriptive"}]
    for h in meta["source_observed"]["participants"]: h["source_dtype"]="float32"
    data["findings.md"]="No prescribed emotion-specific interpretation."
    assert accepted(tmp_path,reference,data)["status"]=="accepted"


def test_identical_arms_legitimate(tmp_path):
    ref=f.manufactured_reference(identical_arms=True)
    assert np.array_equal(ref["arrays"]["contrast_estimate"][::2],ref["arrays"]["contrast_estimate"][1::2])
    accepted(tmp_path,ref,f.payload(ref))


def test_missing_condition_keeps_betas_null_groups(tmp_path):
    ref=f.manufactured_reference(missing_condition=True)
    assert not ref["arrays"]["contrast_defined"].any()
    assert all(x["status"]=="missing_condition" for x in ref["metadata"]["fits"])
    accepted(tmp_path,ref,f.payload(ref))


@pytest.mark.parametrize("key",["roi_mean","roi_raw_mean","roi_raw_sd","normalization_denominator","roi_normalized",
                              "confound_effective","frame_time_s","design_matrix","beta","contrast_estimate","residual_sse"])
def test_primitive_numeric_mutations(reference,tmp_path,key):
    data=f.payload(reference)
    data["glm_arrays.npz"][key].flat[0]+=1.
    with pytest.raises(ValueError): accepted(tmp_path,reference,data)


@pytest.mark.parametrize("key",["column_present","confound_was_missing","contrast_defined","contrast_estimable"])
def test_mask_mutations(reference,tmp_path,key):
    data=f.payload(reference)
    data["glm_arrays.npz"][key].flat[0]=not data["glm_arrays.npz"][key].flat[0]
    with pytest.raises(ValueError): accepted(tmp_path,reference,data)


@pytest.mark.parametrize("key",["participant_id","roi_id","confound_name","column_key","source_frame_index","fit_model",
                              "observation_fit_index","observation_frame_index"])
def test_duplicate_axes(reference,tmp_path,key):
    data=f.payload(reference)
    a=data["glm_arrays.npz"][key]
    a.flat[0]=a.flat[-1]
    if np.array_equal(a,reference["arrays"][key]): a.flat[0]=a.flat[1]
    with pytest.raises(ValueError): accepted(tmp_path,reference,data)


@pytest.mark.parametrize("file",["cohort.csv","events.csv","roi_support.csv","activation.csv"])
def test_duplicate_ledger(reference,tmp_path,file):
    data=f.payload(reference); data[file].append(copy.deepcopy(data[file][0]))
    with pytest.raises(ValueError): accepted(tmp_path,reference,data)


@pytest.mark.parametrize("field",["amygdala","fusiform","control"])
def test_aggregate_offset(reference,tmp_path,field):
    data=f.payload(reference)
    for row in data["activation.csv"]:
        row[field+"_modelA"]+=.1; row[field+"_modelB"]+=.1
    data["group_stats.json"]=c.own_groups(reference,activations=data["activation.csv"])
    with pytest.raises(ValueError): accepted(tmp_path,reference,data)


@pytest.mark.parametrize("field",["models","paired_changes"])
def test_incomplete_group_family(reference,tmp_path,field):
    data=f.payload(reference); data["group_stats.json"][field].pop()
    with pytest.raises(ValueError): accepted(tmp_path,reference,data)


@pytest.mark.parametrize("field",["mean","sample_sd","t","p"])
def test_own_group_arithmetic(reference,tmp_path,field):
    data=f.payload(reference)
    record=next(r for r in data["group_stats.json"]["models"] if r["statistic"]["status"]=="ok")
    record["statistic"][field]+=.1
    with pytest.raises(ValueError): accepted(tmp_path,reference,data)


def test_accepted_aggregate_authority_not_second_group_target(reference,tmp_path):
    data=f.payload(reference)
    for i,row in enumerate(data["activation.csv"]):
        row["amygdala_modelA"]+=(-1 if i%2 else 1)*.8*float(n.bound(reference["activation"][i]["amygdala_modelA"],n.FIT_TOL))
    data["group_stats.json"]=c.own_groups(reference,activations=data["activation.csv"])
    accepted(tmp_path,reference,data)


def test_rt_independent_rounding_and_own_group_authority(reference,tmp_path):
    data=f.payload(reference)
    records=data["group_stats.json"]["rt_summary"]["per_subject"]
    for row in records:
        row["mean_emotion_s"]+=.8*float(n.bound(row["mean_emotion_s"],n.EVENT_TOL))
        row["mean_control_s"]-=.8*float(n.bound(row["mean_control_s"],n.EVENT_TOL))
        row["difference_s"]-=.8*float(n.bound(row["difference_s"],n.EVENT_TOL))
    data["group_stats.json"]=c.own_groups(reference,rt_records=records)
    accepted(tmp_path,reference,data)


@pytest.mark.parametrize("field",["source_manifest_sha256","method_contract_sha256","status","schema_id"])
def test_metadata_identity(reference,tmp_path,field):
    data=f.payload(reference); data["run_metadata.json"][field]="wrong"
    with pytest.raises(ValueError): accepted(tmp_path,reference,data)


def test_boolean_json_count(reference,tmp_path):
    data=f.payload(reference); data["group_stats.json"]["n_expected"]=True
    with pytest.raises(ValueError): accepted(tmp_path,reference,data)


def test_scientific_csv_integer_duplicate(reference,tmp_path):
    data=f.payload(reference); row=copy.deepcopy(data["events.csv"][1])
    row["source_event_row"]="1e0"; data["events.csv"].append(row)
    with pytest.raises(ValueError): accepted(tmp_path,reference,data)


@pytest.mark.parametrize("kind",["empty","directory","dangling"])
def test_failure_marker(reference,tmp_path,kind):
    out=f.emit(tmp_path/"output",f.payload(reference)); marker=out/"failure_report.json"
    if kind=="empty": marker.touch()
    elif kind=="directory": marker.mkdir()
    else: marker.symlink_to(tmp_path/"absent")
    with pytest.raises(ValueError): p.validate_output_directory(out,reference)


def test_numeric_json_equivalence(reference,tmp_path):
    data=f.payload(reference); data["group_stats.json"]["n_expected"]=float(len(reference["arrays"]["participant_id"]))
    for r in data["group_stats.json"]["models"]:
        r["statistic"]["n_expected"]=float(r["statistic"]["n_expected"])
    accepted(tmp_path,reference,data)


def test_equal_network_means_use_fsum_then_divide(reference):
    # Same exact sums from differently arranged cancellation terms. The public
    # person authority is fsum(v)/R, not fsum(v/R) or fsum(v*weight).
    values=reference["arrays"]["contrast_estimate"].copy()
    rois=reference["arrays"]["roi_id"].tolist()
    selected=c.endpoints(reference)["Vis"]
    ix=[rois.index(key) for key in selected]
    sequences=([1e16,1.,-1e16],[1.,1e16,-1e16],[-1e16,1e16,1.])
    for s in range(len(reference["arrays"]["participant_id"])):
        values[2*s,ix]=0
        values[2*s,ix[:3]]=sequences[s%3]
    result=c.own_groups(reference,contrasts=values)
    record=next(row for row in result["models"] if row["model"]=="modelA" and row["endpoint"]=="Vis")
    assert record["statistic"]["status"]=="zero_variance"
    assert record["statistic"]["mean"]==1./len(ix)
    assert record["statistic"]["sample_sd"]==0.


def test_documentary_timing_extra_note(reference,tmp_path):
    data=f.payload(reference)
    data["run_metadata.json"]["source_observed"]["documented_timing"]["note"]="Extra documentary context."
    accepted(tmp_path,reference,data)


@pytest.mark.parametrize("field",["raw_bold_paths","preproc_bold_paths","scanner_discarded_volumes"])
def test_documentary_timing_subject_maps_remain_closed(reference,tmp_path,field):
    data=f.payload(reference)
    data["run_metadata.json"]["source_observed"]["documented_timing"][field]["sub-impostor"]=0
    with pytest.raises(ValueError): accepted(tmp_path,reference,data)


@pytest.mark.parametrize("second,identical",[('{"a":true}',True),('{"a":1}',False),('{"a":false}',False)])
def test_documentary_duplicate_type_identity(second,identical):
    rows=c.documentary_duplicates('{"NEO_A":{"a":true},"NEO_A":'+second+'}',"participants.json")
    assert rows==[dict(path="participants.json",key="NEO_A",occurrences=2,identical=identical,analysis_use=False)]


def test_documentary_single_key_not_fabricated():
    assert c.documentary_duplicates('{"NEO_A":{"a":true}}',"participants.json")==[]


def test_accepted_primitive_network_group_authority(reference,tmp_path):
    data=f.payload(reference)
    values=data["glm_arrays.npz"]["contrast_estimate"]
    original=reference["arrays"]["contrast_estimate"]
    # Shift tiny source-bound receipts, then derive ONLY their own network/sphere
    # group values. The verifier must not additionally use canonical group t.
    values[:,1]+=.1*n.bound(original[:,1],n.FIT_TOL)
    data["group_stats.json"]=c.own_groups(reference,contrasts=values)
    accepted(tmp_path,reference,data)


@pytest.mark.parametrize("key",["fits","source_files"])
def test_duplicate_metadata_rows(reference,tmp_path,key):
    data=f.payload(reference);rows=data["run_metadata.json"][key]
    rows.append(copy.deepcopy(rows[0]))
    with pytest.raises(ValueError): accepted(tmp_path,reference,data)


def test_same_model_relabelled_cannot_hide_source_design(reference,tmp_path):
    data=f.payload(reference);a=data["glm_arrays.npz"]
    for m in range(1,len(a["fit_model"]),2):
        b_rows=a["observation_fit_index"]==m;a_rows=a["observation_fit_index"]==m-1
        a["design_matrix"][b_rows]=a["design_matrix"][a_rows]
        a["beta"][m]=a["beta"][m-1];a["contrast_estimate"][m]=a["contrast_estimate"][m-1]
    with pytest.raises(ValueError): accepted(tmp_path,reference,data)


def varied_frame_reference(reference):
    # Manufactured union-column exercise only: public originals remain135frames.
    basis=copy.deepcopy(reference["primitives"])
    person=basis["subjects"][0]
    person["raw_roi_mean"]=np.concatenate([person["raw_roi_mean"],person["raw_roi_mean"][:55]])
    person["confound_raw"]=np.concatenate([person["confound_raw"],person["confound_raw"][:55]])
    person["confound_missing"]=np.zeros(person["confound_raw"].shape,dtype=bool)
    person["header"]["shape"][3]=135
    ref=c.compile_reference(basis,reference["metadata"]["method"],p.METHOD_SHA256)
    ref["schema"]=reference["schema"]
    return ref


def test_global_union_column_padding_and_coherent_permutation(reference,tmp_path):
    ref=varied_frame_reference(reference)
    assert not ref["arrays"]["column_present"].all()
    data=f.payload(ref)
    data["glm_arrays.npz"]=f.coherent_permutation(data["glm_arrays.npz"])
    accepted(tmp_path,ref,data)


@pytest.mark.parametrize("key",["beta","design_matrix"])
def test_absent_column_tiny_nonzero_rejected_despite_float_tolerance(reference,tmp_path,key):
    ref=varied_frame_reference(reference)
    data=f.payload(ref);a=data["glm_arrays.npz"]
    m,j=np.argwhere(~a["column_present"])[0]
    if key=="beta": a[key][m,j,0]=1e-12
    else: a[key][np.flatnonzero(a["observation_fit_index"]==m)[0],j]=1e-12
    with pytest.raises(ValueError,match="absent column exact zero"):
        accepted(tmp_path,ref,data)


def test_prediction_equivalent_nonminimum_norm_beta_rejected(reference,tmp_path):
    basis=copy.deepcopy(reference["primitives"])
    for person in basis["subjects"]:
        person["confound_raw"][:,1]=person["confound_raw"][:,0]
    ref=c.compile_reference(basis,reference["metadata"]["method"],p.METHOD_SHA256)
    ref["schema"]=reference["schema"]
    data=f.payload(ref);a=data["glm_arrays.npz"]
    j0,j1=[a["column_key"].tolist().index(k) for k in ("trans_x","trans_y")]
    for m in range(len(a["fit_model"])):
        x=a["design_matrix"][a["observation_fit_index"]==m]
        before=x@a["beta"][m]
        a["beta"][m,j0]+=.5;a["beta"][m,j1]-=.5
        np.testing.assert_allclose(x@a["beta"][m],before,atol=1e-12,rtol=1e-12)
    with pytest.raises(ValueError,match="beta: outside public tolerance"):
        accepted(tmp_path,ref,data)


@pytest.mark.parametrize("field",["design_rank","residual_df"])
def test_coherent_rank_receipt_forgery_rejected(reference,tmp_path,field):
    data=f.payload(reference)
    data["glm_arrays.npz"][field][0]+=1
    metadata_key="rank" if field=="design_rank" else "residual_df"
    data["run_metadata.json"]["fits"][0][metadata_key]+=1
    with pytest.raises(ValueError,match=field+": source exact"):
        accepted(tmp_path,reference,data)


@pytest.mark.parametrize("field",["max_abs_source_duration_minus_rt_s","max_abs_source_duration_minus_imputed_modelB_s"])
def test_metadata_tiny_negative_magnitude_is_not_legal_rounding(reference,field):
    # Manufactured canonical zero isolates the declared natural domain from the
    # event-timing tolerance; no original receipt or target is changed.
    ref=copy.deepcopy(reference)
    ref["metadata"]["source_observed"]["duration_rt_comparison"][0][field]=0.
    actual=f.payload(ref)["run_metadata.json"]
    actual["source_observed"]["duration_rt_comparison"][0][field]=-1e-12
    with pytest.raises(ValueError,match="nonnegative duration magnitude"):
        p.metadata(actual,ref)


@pytest.mark.parametrize("value",[0.,1e-12])
def test_metadata_zero_magnitude_allows_nonnegative_rounding(reference,value):
    ref=copy.deepcopy(reference)
    fields=("max_abs_source_duration_minus_rt_s","max_abs_source_duration_minus_imputed_modelB_s")
    for field in fields: ref["metadata"]["source_observed"]["duration_rt_comparison"][0][field]=0.
    actual=f.payload(ref)["run_metadata.json"]
    for field in fields: actual["source_observed"]["duration_rt_comparison"][0][field]=value
    p.metadata(actual,ref)
