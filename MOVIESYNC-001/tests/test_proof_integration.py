"""Complete manufactured seven-file submissions; never load old banks/originals."""
import copy
import csv
import json
from pathlib import Path
import numpy as np
import pytest
import artifact_reader as a
import fixture_support as f
import proof_of_work as p


@pytest.fixture(scope="module")
def reference(): return f.manufactured_reference()


def read_json(path): return json.loads(Path(path).read_text())
def write_json(path,value): Path(path).write_text(json.dumps(value,allow_nan=False))
def read_rows(path):
    with open(path,newline="") as stream: return list(csv.DictReader(stream))
def write_rows(path,rows):
    with open(path,"w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
def read_npz(path):
    with np.load(path,allow_pickle=False) as z: return {k:z[k].copy() for k in z.files}
def write_npz(path,arrays):
    with open(path,"wb") as stream: np.savez_compressed(stream,**arrays)


@pytest.mark.parametrize("estimator",["pairwise","loo","leave-one-out"])
def test_all_declared_headlines(reference,tmp_path,estimator):
    assert p.validate_output_directory(f.emit(tmp_path/"out",reference,estimator),reference)["n_pairs"]==2340


@pytest.mark.parametrize("kind",["constant","identical","negative"])
def test_valid_constant_flat_negative_results(tmp_path,kind):
    ref=f.manufactured_reference(kind)
    out=f.emit(tmp_path/"out",ref,"loo")
    result=p.validate_output_directory(out,ref)
    assert result["headline_status"] == ("incomplete_support" if kind=="constant" else "ok")


def test_float32_primitives_within_public_fidelity(reference,tmp_path):
    x=reference["isc_inputs"].astype(np.float32)
    out=f.emit(tmp_path/"out",reference,inputs=x)
    arrays=read_npz(out/"timecourses.npz"); arrays["raw_coefficients"]=arrays["raw_coefficients"].astype(np.float32)
    write_npz(out/"timecourses.npz",arrays)
    assert p.validate_output_directory(out,reference)


def test_all_coherent_axes_permute_and_pair_orientation(reference,tmp_path):
    out=f.emit(tmp_path/"out",reference); ar=read_npz(out/"timecourses.npz")
    pi=np.arange(40)[::-1]; ti=np.arange(168)[::-1]; mi=np.arange(39)[::-1]; vi=np.array([2,0,1])
    for name,perm in (("participant_ids",pi),("frame_indices",ti),("map_ids",mi),("map_labels",mi),("visual_map_ids",vi)): ar[name]=ar[name][perm]
    ar["raw_coefficients"]=ar["raw_coefficients"][np.ix_(pi,ti,mi)]
    ar["isc_inputs"]=ar["isc_inputs"][np.ix_(pi,ti,vi)]
    for name in ("person_active","template_active"): ar[name]=ar[name][np.ix_(pi,vi)]
    for name in ("frame_indices","map_ids","visual_map_ids"): ar[name]=ar[name].astype(np.float64)
    ar["participant_ids"]=ar["participant_ids"].astype("S")
    write_npz(out/"timecourses.npz",ar)
    for filename in ("cohort.csv","isc_pairs.csv","isc_per_subject.csv"):
        rows=read_rows(out/filename)[::-1]
        if filename=="isc_pairs.csv":
            for row in rows: row["participant_a"],row["participant_b"]=row["participant_b"],row["participant_a"]
        write_rows(out/filename,[dict(reversed(list(row.items()))) for row in rows])
    result=read_json(out/"isc_results.json")
    result["per_subject"].reverse(); result["per_region"].reverse(); write_json(out/"isc_results.json",result)
    metadata=read_json(out/"run_metadata.json")
    for key in ("participant_ids","visual_map_ids","map_labels","headers"): metadata["source_observed"][key].reverse()
    write_json(out/"run_metadata.json",metadata)
    assert p.validate_output_directory(out,reference)


def test_independent_six_decimal_scalar_rounding(reference,tmp_path):
    out=f.emit(tmp_path/"out",reference)
    for filename,fields in (("isc_pairs.csv",["r"]),("isc_per_subject.csv",["isc_pairwise","isc_loo"])):
        rows=read_rows(out/filename)
        for row in rows:
            for key in fields: row[key]=format(float(row[key]),".6f")
        write_rows(out/filename,rows)
    def rounded(v):
        if isinstance(v,float): return round(v,6)
        if isinstance(v,list): return [rounded(x) for x in v]
        if isinstance(v,dict): return {k:rounded(x) for k,x in v.items()}
        return v
    write_json(out/"isc_results.json",rounded(read_json(out/"isc_results.json")))
    assert p.validate_output_directory(out,reference)


def test_harmless_extras_descriptions_and_dtype_alias(reference,tmp_path):
    out=f.emit(tmp_path/"out",reference)
    meta=read_json(out/"run_metadata.json")
    meta["source_observed"]["note"]="No measured movie clock."
    meta["source_observed"]["headers"][0]["source_dtype"]="i1"
    meta["software_versions"]["nilearn"]="not_used"
    write_json(out/"run_metadata.json",meta)
    result=read_json(out/"isc_results.json"); result["description"]="No direction claim."; write_json(out/"isc_results.json",result)
    ar=read_npz(out/"timecourses.npz"); ar["optional_diagnostic"]=np.array([1.]); write_npz(out/"timecourses.npz",ar)
    assert p.validate_output_directory(out,reference)


@pytest.mark.parametrize("kind",["raw","participant_values","frame_values","map_values","final_sign","constant_fabrication","person_support","template_support","id_alias","duplicate_axis","wrong_map_label"])
def test_source_primitive_mutations_reject(reference,tmp_path,kind):
    out=f.emit(tmp_path/"out",reference); ar=read_npz(out/"timecourses.npz")
    if kind=="raw": ar["raw_coefficients"][0,0,0]+=1.
    elif kind=="participant_values": ar["isc_inputs"][[0,1]]=ar["isc_inputs"][[1,0]]
    elif kind=="frame_values": ar["isc_inputs"]=ar["isc_inputs"][:,::-1,:]
    elif kind=="map_values": ar["isc_inputs"]=ar["isc_inputs"][:,:,::-1]
    elif kind=="final_sign": ar["isc_inputs"][0]*=-1
    elif kind=="constant_fabrication": ar["isc_inputs"][0]=0
    elif kind in ("person_support","template_support"): ar[kind.replace("support","active")][0,0]=False
    elif kind=="id_alias": ar["participant_ids"][0]="wrong001"
    elif kind=="duplicate_axis": ar["frame_indices"][0]=1
    elif kind=="wrong_map_label": ar["map_labels"][3]="wrong"
    write_npz(out/"timecourses.npz",ar)
    with pytest.raises((ValueError,a.ArtifactError)): p.validate_output_directory(out,reference)


@pytest.mark.parametrize("kind",["missing_pair","duplicate_reversed","self_pair","pair_value","pair_null","pair_status","missing_person","person_nan","loo_value","loo_count","active_count","pairwise_count","cohort_rank"])
def test_complete_typed_csv_evidence(reference,tmp_path,kind):
    out=f.emit(tmp_path/"out",reference)
    file="cohort.csv" if kind=="cohort_rank" else ("isc_pairs.csv" if "pair" in kind and kind not in ("pairwise_count",) or kind in ("duplicate_reversed","self_pair") else "isc_per_subject.csv")
    rows=read_rows(out/file)
    if kind in ("missing_pair","missing_person"): rows.pop()
    elif kind=="duplicate_reversed":
        row=rows[0].copy(); row["participant_a"],row["participant_b"]=row["participant_b"],row["participant_a"]; rows.append(row)
    elif kind=="self_pair": rows[0]["participant_b"]=rows[0]["participant_a"]
    elif kind=="pair_value": rows[0]["r"]=str(float(rows[0]["r"])+.01)
    elif kind=="pair_null": rows[0]["r"]=""
    elif kind=="pair_status": rows[0]["status"]="inactive_person"
    elif kind=="person_nan": rows[0]["isc_pairwise"]="nan"
    elif kind=="loo_value": rows[0]["isc_loo"]=str(float(rows[0]["isc_loo"])+.01)
    elif kind=="loo_count": rows[0]["loo_n_defined"]="38"
    elif kind=="active_count": rows[0]["loo_n_active_contributors"]="38"
    elif kind=="pairwise_count": rows[0]["pairwise_n_expected"]="38"
    else: rows[0]["map_rank"]="38"
    write_rows(out/file,rows)
    with pytest.raises((ValueError,a.ArtifactError)): p.validate_output_directory(out,reference)


@pytest.mark.parametrize("kind",["headline","wrong_estimator","bad_status","n_subjects","bool_count","text_number","duplicate_region","missing_person","source_hash","source_header","source_files","failure","failure_dangling"])
def test_results_metadata_failure_states(reference,tmp_path,kind):
    out=f.emit(tmp_path/"out",reference)
    if kind.startswith("failure"):
        if kind=="failure": (out/"failure_report.json").write_text("")
        else: (out/"failure_report.json").symlink_to(out/"absent")
    elif kind.startswith("source_"):
        meta=read_json(out/"run_metadata.json")
        if kind=="source_hash": meta["source_manifest_sha256"]="0"*64
        elif kind=="source_header": meta["source_observed"]["headers"][0]["raw_TR"]=2.
        else: meta["source_files"].append(copy.deepcopy(meta["source_files"][0]))
        write_json(out/"run_metadata.json",meta)
    else:
        result=read_json(out/"isc_results.json")
        if kind=="headline": result["visual_isc"]+=.01
        elif kind=="wrong_estimator": result["isc_estimator"]="unknown"
        elif kind=="bad_status": result["status"]="failed_precondition"
        elif kind=="n_subjects": result["n_subjects"]=39
        elif kind=="bool_count": result["n_subjects"]=True
        elif kind=="text_number": result["visual_isc"]=str(result["visual_isc"])
        elif kind=="duplicate_region": result["per_region"].append(copy.deepcopy(result["per_region"][0]))
        else: result["per_subject"].pop()
        write_json(out/"isc_results.json",result)
    with pytest.raises((ValueError,a.ArtifactError)): p.validate_output_directory(out,reference)


def test_partial_authoring_basis_never_production_success(reference,tmp_path):
    ref=copy.copy(reference); ref["participant_ids"]=ref["participant_ids"][:1]
    with pytest.raises(a.ArtifactError,match="full production"):
        p.validate_output_directory(tmp_path/"not_read",ref)
