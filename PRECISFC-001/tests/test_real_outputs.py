"""Genuine-output acceptance/mutation controls; never generates original data.

Parent supplies complete independently constructed outputs after its execution
gate. Each owned temporary directory is removed after its case to bound disk.
"""
import csv
import json
import os
from pathlib import Path
import shutil
import tempfile
import numpy as np
import pytest
import proof_of_work as p
import qc_contract as q
from fixture_support import emit


@pytest.fixture(scope="module")
def genuine():
    value=os.environ.get("REPAIR_ORACLE_OUTPUT")
    if not value: pytest.skip("parent has not supplied a complete original-source output")
    source=Path(value); assert source.is_dir(), "provided genuine output path must exist"
    return source,p.load_reference()


@pytest.fixture
def case(genuine):
    source,ref=genuine
    with tempfile.TemporaryDirectory(prefix="precisfc-regression-") as temporary:
        root=Path(temporary)/"output";shutil.copytree(source,root)
        yield root,ref


def reject(root,ref,pattern=None):
    with pytest.raises((AssertionError,ValueError,TypeError,KeyError,EOFError,UnicodeError),match=pattern):
        p.validate_output_directory(root,ref)


def csv_rows(path):
    with path.open(newline="") as stream:
        reader=csv.DictReader(stream);return list(reader.fieldnames),list(reader)


def csv_write(path,fields,rows):
    with path.open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def arrays_read(root):
    with np.load(root/"connectivity_arrays.npz",allow_pickle=False) as archive:
        return {k:archive[k] for k in archive.files}


def arrays_write(root,arrays):
    np.savez_compressed(root/"connectivity_arrays.npz",**arrays)


def independent_fidelity_check(means,ref):
    """Explicit test-side predicate; never infer source equivalence from a pass."""
    original=ref["roi_means"]
    tolerance=1e-10*ref["roi_source_peak_abs"][:,None,:]+1e-9*np.abs(original)
    if not np.isfinite(means).all() or np.any(np.abs(means-original)>tolerance):return False
    def state(x):
        if np.max(x)==np.min(x):return "constant",np.zeros_like(x)
        scale=np.max(np.abs(x));u=x/scale;d=u-np.mean(u)
        zero=10*len(x)*np.finfo(float).eps*np.sqrt(np.sum(u*u))
        return ("inactive" if np.sqrt(np.sum(d*d))<=zero else "ok"),scale*d
    def norm(x):
        scale=np.max(np.abs(x))
        return 0. if scale==0 else scale*np.sqrt(np.sum((x/scale)**2))
    for run in range(len(means)):
        for mask in (np.ones(means.shape[1],bool),ref["tmask"][run]):
            if np.sum(mask)<2:continue
            for roi in range(means.shape[2]):
                x,y=means[run,mask,roi],original[run,mask,roi]
                a,dx=state(x);b,dy=state(y)
                if b=="constant":
                    if a!="constant":return False
                elif a=="ok" or b=="ok":
                    if norm(dx-dy)>1e-6*norm(dy):return False
    return True


def explicit_downstream_coherence(root,arrays,ref):
    own=q.derive(arrays)
    for key in ("common_roi","edge_valid"):
        if not np.array_equal(arrays[key],own[key]):return False
    for key in ("raw_r","fisher_z"):
        if not np.allclose(arrays[key],own[key],atol=1e-8,rtol=1e-7,equal_nan=True):return False
    try:
        for name in ("session_qc","roi_status","session_pairs","reliability"):
            p.table_match(root/f"{name}.csv",own[name],ref["method"]["outputs"][f"{name}.csv"],ref,own)
        p.match_summary(p.read_json(root/"reliability_stats.json"),own["stats"])
        p.validate_metadata(p.read_json(root/"run_metadata.json"),ref,own["stats"])
    except AssertionError:return False
    return True


def test_genuine_original_output(genuine):
    p.validate_output_directory(*genuine)


def test_genuine_independent_output(genuine):
    value=os.environ.get("REPAIR_INDEPENDENT_OUTPUT")
    if not value: pytest.skip("independent original-source output is not supplied")
    assert Path(value).is_dir(), "provided independent output must be complete"
    p.validate_output_directory(value,genuine[1])


def test_public_contract_identity(genuine):
    _,ref=genuine
    path=Path(__file__).parents[1]/"environment"/"method_contract.json"
    p.require(p.sha256(path)==p.METHOD_SHA,"public contract digest")
    p.match(p.read_json(path),ref["method"],closed=True)


def test_reordered_rows_columns_and_integral_notation(case):
    root,ref=case
    for path in root.glob("*.csv"):
        fields,rows=csv_rows(path)
        for row in rows:
            for field in ref["method"]["outputs"][path.name].get("integer_fields",[]):
                original=p.integer(row[field]);row[field]=format(original,".17e")
                assert p.integer(row[field])==original
            row["extra_note"]="ungraded"
        csv_write(path,list(reversed(fields))+["extra_note"],list(reversed(rows)))
    p.validate_output_directory(root,ref)


def test_joint_npz_axis_permutations(case):
    root,ref=case;a=arrays_read(root);R,T,P=a["roi_means"].shape
    runs=np.arange(R)[::-1];frames=np.arange(T)[::-1];rois=np.arange(P)[::-1]
    for k in ("run_subject","run_session"):a[k]=a[k][runs]
    for k in ("frame_indices","tmask"):a[k]=a[k][runs][:,frames]
    a["roi_means"]=a["roi_means"][runs][:,frames][:,:,rois]
    a["roi_source_peak_abs"]=a["roi_source_peak_abs"][runs][:,rois]
    segments=[a["voxel_ijk"][a["voxel_offsets"][i]:a["voxel_offsets"][i+1]][::-1] for i in rois]
    a["voxel_offsets"]=np.r_[0,np.cumsum([len(s) for s in segments])]
    a["voxel_ijk"]=np.concatenate(segments)
    for k in ("roi_ids","common_roi"):a[k]=a[k][rois]
    for k in ("arm_names","edge_roi_ids","edge_valid"):a[k]=a[k][::-1]
    for k in ("raw_r","fisher_z"):a[k]=a[k][runs][:,::-1,::-1]
    arrays_write(root,a);p.validate_output_directory(root,ref)


def test_harmless_extras_versions_and_free_prose(case):
    root,ref=case
    for name in ("run_metadata.json","reliability_stats.json"):
        path=root/name;value=p.read_json(path);value["optional_context"]={"claim":"descriptive only","value":1}
        if name=="run_metadata.json":
            value["software_versions"]={"python":"alternate","numpy":"alternate","nibabel":"not_used"}
            value["source_files"].reverse();value["source_observed"]["headers"].reverse()
        path.write_text(json.dumps(value))
    (root/"findings.md").write_text("Computed the requested tables. No further claim.")
    p.validate_output_directory(root,ref)


def test_derived_decimal_rounding_without_touching_fullprecision_means(case):
    root,ref=case
    for path in root.glob("*.csv"):
        schema=ref["method"]["outputs"][path.name];fields,rows=csv_rows(path)
        excluded=set(schema["key"]+schema.get("integer_fields",[])+schema.get("boolean_fields",[]))
        for row in rows:
            for k in fields:
                if k in excluded or row[k]=="":continue
                try:v=float(row[k])
                except ValueError:continue
                row[k]=format(v,".12g")
        csv_write(path,fields,rows)
    p.validate_output_directory(root,ref)


@pytest.mark.parametrize("name",["session_qc.csv","roi_geometry.csv","roi_status.csv","connectivity_arrays.npz",
    "session_pairs.csv","reliability.csv","reliability_stats.json","run_metadata.json","findings.md"])
@pytest.mark.parametrize("mode",["missing","empty"])
def test_missing_or_empty_required(case,name,mode):
    root,ref=case
    if mode=="missing":(root/name).unlink()
    else:(root/name).write_bytes(b"")
    reject(root,ref)


@pytest.mark.parametrize("name",["session_qc.csv","roi_geometry.csv","roi_status.csv","session_pairs.csv","reliability.csv"])
@pytest.mark.parametrize("mode",["duplicate","missing","foreign"])
def test_table_identity_coverage(case,name,mode):
    root,ref=case;fields,rows=csv_rows(root/name)
    if mode=="duplicate":rows.append(dict(rows[0]))
    elif mode=="missing":rows.pop()
    else:
        key=ref["method"]["outputs"][name]["key"][0]
        rows[0][key]="999999" if key=="roi_id" else "foreign"
    csv_write(root/name,fields,rows);reject(root,ref)


@pytest.mark.parametrize("mode",["mean_scale","mean_offset","means_unit_swap","means_frame_swap","peak_scale",
    "mask","frame_duplicate","roi_duplicate","foreign_run","voxel_shift","voxel_duplicate","offset",
    "common_roi","edge_valid","edge_duplicate","edge_reverse","raw_value","z_value","raw_inf",
    "mean_nan","peak_negative","boolean_roi","float32_means"])
def test_npz_source_and_algebra_mutations(case,mode,record_property):
    root,ref=case;a=arrays_read(root)
    if mode=="mean_scale":a["roi_means"]*=1.1
    elif mode=="mean_offset":a["roi_means"]+=np.maximum(ref["roi_source_peak_abs"],1)[:,None,:]*.001
    elif mode=="means_unit_swap":a["roi_means"][:,:,[0,1]]=a["roi_means"][:,:,[1,0]]
    elif mode=="means_frame_swap":a["roi_means"][:,[0,1],:]=a["roi_means"][:,[1,0],:]
    elif mode=="peak_scale":a["roi_source_peak_abs"]=np.maximum(a["roi_source_peak_abs"]*1.1,1.)
    elif mode=="mask":a["tmask"][0,0]=not a["tmask"][0,0]
    elif mode=="frame_duplicate":a["frame_indices"][0,0]=a["frame_indices"][0,1]
    elif mode=="roi_duplicate":a["roi_ids"][0]=a["roi_ids"][1]
    elif mode=="foreign_run":a["run_subject"]=a["run_subject"].astype("U20");a["run_subject"][0]="foreign"
    elif mode=="voxel_shift":a["voxel_ijk"][0,0]+=100
    elif mode=="voxel_duplicate":a["voxel_ijk"][0]=a["voxel_ijk"][1]
    elif mode=="offset":a["voxel_offsets"][0]=1
    elif mode=="common_roi":a["common_roi"][0]=not a["common_roi"][0]
    elif mode=="edge_valid":a["edge_valid"][0]=not a["edge_valid"][0]
    elif mode=="edge_duplicate":a["edge_roi_ids"][0]=a["edge_roi_ids"][1]
    elif mode=="edge_reverse":a["edge_roi_ids"][0]=a["edge_roi_ids"][0,::-1]
    elif mode in ("raw_value","z_value","raw_inf"):
        key="fisher_z" if mode=="z_value" else "raw_r"
        a[key][0,0,0]=float("inf") if mode=="raw_inf" else 5.
    elif mode=="mean_nan":a["roi_means"][0,0,0]=np.nan
    elif mode=="peak_negative":a["roi_source_peak_abs"][0,0]=-1
    elif mode=="boolean_roi":a["roi_ids"]=a["roi_ids"].astype(bool)
    elif mode=="float32_means":a["roi_means"]=a["roi_means"].astype(np.float32)
    arrays_write(root,a)
    if mode in ("mean_scale", "means_unit_swap", "means_frame_swap"):
        if not independent_fidelity_check(a["roi_means"],ref) or not explicit_downstream_coherence(root,a,ref):
            reject(root,ref)
            record_property("control_status","effective_negative_control")
        else:
            p.validate_output_directory(root,ref)
            record_property("control_status","control_not_discriminating")
    else:
        reject(root,ref);record_property("control_status","effective_negative_control")


@pytest.mark.parametrize("mode",["method","method_bool","source_digest","source_file","missing_header","header_time",
    "header_geometry","original_modified","pipeline","failed_status","versions","extra_inf"])
def test_metadata_provenance(case,mode):
    root,ref=case;path=root/"run_metadata.json";v=p.read_json(path)
    if mode=="method":v["method_contract"]["geometry"]["radius_mm"]=6
    elif mode=="method_bool":v["method_contract"]["timing"]["raw_header_interval_seconds"]=True
    elif mode=="source_digest":v["source_manifest_sha256"]="0"*64
    elif mode=="source_file":v["source_files"][0]["sha256"]="0"*64
    elif mode=="missing_header":v["source_observed"]["headers"].pop()
    elif mode=="header_time":v["source_observed"]["headers"][0]["raw_header_tr_seconds"]=2.2
    elif mode=="header_geometry":v["source_observed"]["headers"][0]["sform"][0][3]+=3
    elif mode=="original_modified":v["source_observed"]["original_files_modified"]=True
    elif mode=="pipeline":v["pipeline_id"]="legacy"
    elif mode=="failed_status":v["status"]="resource_pilot"
    elif mode=="versions":v["software_versions"]["numpy"]=""
    elif mode=="extra_inf":v["extra"]={"v":float("inf")}
    path.write_text(json.dumps(v));reject(root,ref)


@pytest.mark.parametrize("mode",["group_mean","common_count","retained_count","false_qc","unknown_status","missing_null","bool_count"])
def test_wrong_summary(case,mode):
    root,ref=case;path=root/"reliability_stats.json";v=p.read_json(path)
    if mode=="group_mean":
        key="all_six_censored";old=v["group_mean_reliability"][key]["value"]
        v["group_mean_reliability"][key]["value"]=0 if old is None else (old+.1 if old<=.8 else old-.1)
    elif mode=="common_count":v["n_common_edges"]+=1
    elif mode=="retained_count":v["n_frames_retained"]+=1
    elif mode=="false_qc":v["qc_included_subject_ids"],v["qc_excluded_subject_ids"]=v["qc_excluded_subject_ids"],v["qc_included_subject_ids"]
    elif mode=="unknown_status":v["roi_status_counts"]["invented"]=0
    elif mode=="missing_null":del v["group_mean_reliability"]["conditional_qc_censored"]["value"]
    else:v["n_subjects"]=True
    path.write_text(json.dumps(v));reject(root,ref)


@pytest.mark.parametrize("mode",["scaled","shifted"])
def test_coherent_source_fabrication(case,mode):
    root,ref=case
    means=ref["roi_means"]*1.1 if mode=="scaled" else ref["roi_means"]+.01*np.maximum(ref["roi_source_peak_abs"],1)[:,None,:]
    if np.array_equal(means,ref["roi_means"]):
        means=means+.01
    emit(root,ref,means)
    reject(root,ref,"original source")
