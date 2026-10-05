"""Independent source-bound arithmetic for the two declared descriptive methods."""
from __future__ import annotations
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import numpy as np

PIPELINE_ID="allen2p-original-trial-means-v2"
TASK_ID="ALLEN2P-001"
METHODS=("same_trials","repeated_split_mean_ratio")
MEAN_ATOL,MEAN_RTOL,RATIO_ATOL,RATIO_RTOL,FRACTION_ATOL=1e-10,1e-8,1e-6,1e-6,1e-10
SOURCE_ARRAYS=("cell_ids","roi_ids","source_row_ids","start_frame","end_frame","direction","temporal_frequency","blank_sweep","trial_response")
ESTIMATE_FIELDS=("cell_specimen_id","replicate","selection_half","measurement_half","selection_status",
 "preferred_direction_deg","preferred_temporal_frequency_hz","n_selection_pref","selection_pref_mean_dff",
 "n_measure_pref","n_measure_orth_plus","n_measure_orth_minus","n_measure_null","r_pref","r_orth_plus","r_orth_minus",
 "r_orth","r_null","osi_denominator","dsi_denominator","osi","dsi","osi_status","dsi_status")
CELL_FIELDS=("source_cell_index","cell_specimen_id","roi_id","osi","dsi","n_valid_osi","n_valid_dsi","osi_status","dsi_status","selective")
PRESENTATION_FIELDS=("trial_index","source_row_id","start_frame","end_frame","n_frames","direction_deg","temporal_frequency_hz","blank_sweep","tuning_included")
TRIAL_FIELDS=("cell_specimen_id","source_row_id","mean_dff")
CONDITION_FIELDS=("cell_specimen_id","direction_deg","temporal_frequency_hz","n_trials","mean_dff")
FILES=("presentations.csv","trial_responses.csv","condition_means.csv","estimates.csv","per_neuron.csv","results.json","run_metadata.json","findings.md")
TEXT_FIELDS={"selection_half","measurement_half","selection_status","osi_status","dsi_status","roi_id"}
INT_FIELDS={"trial_index","source_row_id","start_frame","end_frame","n_frames","blank_sweep","tuning_included",
 "source_cell_index","cell_specimen_id","replicate","n_selection_pref","n_measure_pref","n_measure_orth_plus",
 "n_measure_orth_minus","n_measure_null","n_valid_osi","n_valid_dsi","selective","n_trials"}
CATEGORY_FIELDS={"preferred_direction_deg","preferred_temporal_frequency_hz","direction_deg","temporal_frequency_hz"}


def integer(value,name="integer"):
    assert not isinstance(value,(bool,np.bool_)),f"{name}: boolean is not an integer"
    try: number=Decimal(str(value).strip())
    except (ValueError,InvalidOperation) as error: raise AssertionError(f"{name}: exact integer required") from error
    assert number.is_finite() and number==number.to_integral_value() and abs(number)<=2**63-1,f"{name}: exact int64 required"
    return int(number)


def number(value,name="number"):
    assert not isinstance(value,(bool,np.bool_)),f"{name}: boolean is not numeric"
    try: answer=float(value)
    except (TypeError,ValueError,OverflowError) as error: raise AssertionError(f"{name}: finite number required") from error
    assert np.isfinite(answer),f"{name}: finite number required"
    return answer


def read_json(path):
    try: value=json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (ValueError,OSError) as error: raise AssertionError(f"invalid JSON: {path}") from error
    assert isinstance(value,dict),"JSON object required"
    return value


def rows(path,fields):
    try:
        with Path(path).open(newline="",encoding="utf-8-sig") as stream:
            reader=csv.DictReader(stream)
            assert reader.fieldnames,"CSV header required"
            reader.fieldnames=[field.strip() for field in reader.fieldnames]
            assert len(reader.fieldnames)==len(set(reader.fieldnames)),"duplicate CSV header"
            assert set(fields)<=set(reader.fieldnames),f"missing columns in {Path(path).name}"
            result=[]
            for row in reader:
                assert None not in row,"unlabelled CSV cells"
                if not any(str(x or "").strip() for x in row.values()): continue
                assert all(row.get(field) is not None for field in fields),"truncated row"
                result.append({k:v.strip() if isinstance(v,str) else v for k,v in row.items()})
    except OSError as error: raise AssertionError(f"missing CSV: {path}") from error
    return result


def close(actual,expected,name,atol=MEAN_ATOL,rtol=MEAN_RTOL):
    actual,expected=np.asarray(actual,float),np.asarray(expected,float)
    assert actual.shape==expected.shape and np.isfinite(actual).all() and np.isfinite(expected).all(),f"{name}: shape/nonfinite mismatch"
    assert np.all(abs(actual-expected)<=atol+rtol*abs(expected)),f"{name}: numerical mismatch"


def match(actual,expected,name="metadata"):
    if isinstance(expected,dict):
        assert isinstance(actual,dict),f"{name}: object required"
        for key,value in expected.items():
            assert key in actual,f"{name}: missing {key}"
            match(actual[key],value,name+"."+key)
    elif isinstance(expected,list):
        assert isinstance(actual,list) and len(actual)==len(expected),f"{name}: list mismatch"
        for i,value in enumerate(expected): match(actual[i],value,name+"["+str(i)+"]")
    elif isinstance(expected,(str,bool)) or expected is None:
        assert type(actual) is type(expected) and actual==expected,f"{name}: categorical mismatch"
    elif isinstance(expected,int):
        assert integer(actual,name)==expected,f"{name}: count mismatch"
    else:
        assert number(actual,name)==expected,f"{name}: fixed contract mismatch"


def validate_versions(metadata):
    values=metadata.get("software_versions")
    assert isinstance(values,dict) and values,"software_versions must describe the actual implementation"
    assert all(isinstance(k,str) and k.strip() and isinstance(v,str) and v.strip() for k,v in values.items()),"invalid software_versions"


def normalize_source_hash(metadata,expected):
    """Accept a digest string only for the one independently declared source.

    Normalize a fresh in-memory mapping; do not rewrite submitted artifacts or
    relax exact source identities, other hash fields, or unrelated metadata.
    """
    assert "source_sha256" in metadata,"metadata: missing source_sha256"
    actual=metadata["source_sha256"]
    wanted=expected["source_sha256"]
    assert isinstance(wanted,dict) and wanted,"reference source identity required"
    if isinstance(actual,str):
        assert len(wanted)==1,"digest string requires exactly one declared source"
        filename,digest=next(iter(wanted.items()))
        assert actual==digest,"metadata.source_sha256: source identity mismatch"
        actual={filename:actual}
    assert isinstance(actual,dict) and actual==wanted,"metadata.source_sha256: source identity mismatch"
    return {**metadata,"source_sha256":actual}


def included(reference):
    return (reference["blank_sweep"]<=0)&np.isfinite(reference["direction"])&np.isfinite(reference["temporal_frequency"])


def condition_values(reference,response,mask):
    dirs=reference["directions"];freqs=reference["frequencies"]
    means=np.full((len(reference["cell_ids"]),len(dirs),len(freqs)),np.nan)
    counts=np.zeros((len(dirs),len(freqs)),dtype=np.int64)
    for i,direction in enumerate(dirs):
        for j,freq in enumerate(freqs):
            chosen=mask&included(reference)&(reference["direction"]==direction)&(reference["temporal_frequency"]==freq)
            counts[i,j]=chosen.sum()
            if counts[i,j]: means[:,i,j]=response[:,chosen].mean(axis=1,dtype=np.float64)
    assert np.isfinite(means[:,counts>0]).all(),"nonfinite condition mean"
    return means,counts


def split_masks(n_presentations,n_replicates=50):
    rng=np.random.default_rng(0)
    return np.stack([rng.random(n_presentations)<.5 for _ in range(n_replicates)])


def nullable(value):
    return None if value is None or np.isnan(value) else float(value)


def ratio_values(pref,other,selection_status):
    if selection_status!="ok": return None,None,"no_selection_conditions"
    if pref is None or other is None: return None,None,"missing_measurement_condition"
    denominator=pref+other
    assert np.isfinite(denominator),"nonfinite ratio denominator"
    if denominator==0: return 0.,None,"zero_denominator"
    value=(pref-other)/denominator
    assert np.isfinite(value),"nonfinite ratio"
    return float(denominator),float(value),"ok"


def estimate_rows(reference,training,train_counts,evaluation,test_counts,replicate,selection_half,measurement_half,preferences=None):
    result=[]
    directions,frequencies=reference["directions"],reference["frequencies"]
    for index,cid in enumerate(reference["cell_ids"]):
        row={key:None for key in ESTIMATE_FIELDS}
        row.update(cell_specimen_id=int(cid),replicate=replicate,selection_half=selection_half,
                   measurement_half=measurement_half,selection_status="no_selection_conditions")
        selected=np.isfinite(training[index]).any() if preferences is None else preferences[index]["selection_status"]=="ok"
        if selected:
            if preferences is None:
                flat=int(np.argmax(np.where(np.isfinite(training[index]),training[index],-np.inf)))
                d,t=np.unravel_index(flat,training[index].shape)
            else:
                d=int(np.flatnonzero(directions==preferences[index]["preferred_direction_deg"])[0])
                t=int(np.flatnonzero(frequencies==preferences[index]["preferred_temporal_frequency_hz"])[0])
            row.update(selection_status="ok",preferred_direction_deg=float(directions[d]),
                       preferred_temporal_frequency_hz=float(frequencies[t]),n_selection_pref=int(train_counts[d,t]),
                       selection_pref_mean_dff=float(training[index,d,t]))
            for suffix,delta in (("pref",0),("orth_plus",2),("orth_minus",-2),("null",4)):
                dd=(d+delta)%len(directions)
                row["n_measure_"+suffix]=int(test_counts[dd,t])
                row["r_"+suffix]=float(evaluation[index,dd,t]) if test_counts[dd,t] else None
            if row["r_orth_plus"] is not None and row["r_orth_minus"] is not None:
                row["r_orth"]=float((row["r_orth_plus"]+row["r_orth_minus"])/2)
                assert np.isfinite(row["r_orth"]),"nonfinite orthogonal response"
        for metric,other in (("osi","r_orth"),("dsi","r_null")):
            denominator,value,status=ratio_values(row["r_pref"],row[other],row["selection_status"])
            row[metric+"_denominator"],row[metric],row[metric+"_status"]=denominator,value,status
        result.append(row)
    return result


def analyze(reference,method,response=None,preferences=None):
    assert method in METHODS,"unknown declared method"
    response=reference["trial_response"] if response is None else np.asarray(response,float)
    assert response.shape==reference["trial_response"].shape and np.isfinite(response).all()
    all_means,all_counts=condition_values(reference,response,np.ones(response.shape[1],bool))
    condition_rows=[]
    for c,cid in enumerate(reference["cell_ids"]):
        for d,direction in enumerate(reference["directions"]):
            for t,freq in enumerate(reference["frequencies"]):
                condition_rows.append(dict(cell_specimen_id=int(cid),direction_deg=float(direction),
                    temporal_frequency_hz=float(freq),n_trials=int(all_counts[d,t]),mean_dff=nullable(all_means[c,d,t])))
    if method=="same_trials":
        estimates=estimate_rows(reference,all_means,all_counts,all_means,all_counts,0,"all","all",preferences)
    else:
        estimates=[]
        for rep,mask in enumerate(split_masks(response.shape[1]),1):
            a,ac=condition_values(reference,response,mask)
            b,bc=condition_values(reference,response,~mask)
            for training,tc,evaluation,ec,left,right in ((a,ac,b,bc,"A","B"),(b,bc,a,ac,"B","A")):
                fixed=None if preferences is None else preferences[len(estimates):len(estimates)+len(reference["cell_ids"])]
                estimates.extend(estimate_rows(reference,training,tc,evaluation,ec,rep,left,right,fixed))
    by_cell={int(cid):[] for cid in reference["cell_ids"]}
    for row in estimates: by_cell[row["cell_specimen_id"]].append(row)
    neurons=[]
    for index,cid in enumerate(reference["cell_ids"]):
        row=dict(source_cell_index=index,cell_specimen_id=int(cid),roi_id=str(reference["roi_ids"][index]))
        for metric in ("osi","dsi"):
            values=[item[metric] for item in by_cell[int(cid)] if item[metric+"_status"]=="ok"]
            value=float(np.mean(values,dtype=np.float64)) if values else None
            assert value is None or np.isfinite(value),"nonfinite mean ratio"
            row[metric]=value;row["n_valid_"+metric]=len(values)
            row[metric+"_status"]="defined" if values else "no_valid_estimates"
        row["selective"]=int(any(row[k] is not None and row[k]>.5 for k in ("osi","dsi")))
        neurons.append(row)
    n=len(neurons);assert n>0
    results=dict(method=method,n_neurons_total=n,n_selective=sum(r["selective"] for r in neurons),
        threshold=.5,n_osi_defined=sum(r["osi"] is not None for r in neurons),
        n_dsi_defined=sum(r["dsi"] is not None for r in neurons),
        n_either_defined=sum(r["osi"] is not None or r["dsi"] is not None for r in neurons),
        n_both_undefined=sum(r["osi"] is None and r["dsi"] is None for r in neurons),
        n_osi_undefined=sum(r["osi"] is None for r in neurons),n_dsi_undefined=sum(r["dsi"] is None for r in neurons),
        n_estimates_per_cell=1 if method=="same_trials" else 100)
    results["selective_fraction"]=results["n_selective"]/n
    if method=="repeated_split_mean_ratio":
        fractions=[]
        for rep in range(1,51):
            pair=[]
            for half in ("A","B"):
                selected=[r for r in estimates if r["replicate"]==rep and r["selection_half"]==half]
                assert len(selected)==n
                pair.append(sum(any(r[k] is not None and r[k]>.5 for k in ("osi","dsi")) for r in selected)/n)
            fractions.append(float(np.mean(pair)))
        results["split_fraction_mean"]=float(np.mean(fractions))
        results["split_fraction_sd"]=float(np.std(fractions,ddof=0))
    return dict(condition_rows=condition_rows,estimates=estimates,neurons=neurons,results=results)


def validate_reference(reference):
    stats=reference["stats"];metadata=stats["metadata"]
    assert stats.get("pipeline_id")==PIPELINE_ID,"obsolete reference; original-source trial bank required"
    assert metadata["status"]=="ok" and metadata["task_id"]==TASK_ID
    c=len(reference["cell_ids"]);p=len(reference["source_row_ids"])
    assert c>0 and p>0 and reference["trial_response"].shape==(c,p)
    assert reference["cell_ids"].dtype.kind in "iu" and len(set(reference["cell_ids"]))==c
    assert reference["roi_ids"].shape==(c,) and reference["roi_ids"].dtype.kind in "US"
    assert len(set(reference["roi_ids"]))==c and all(str(v) for v in reference["roi_ids"])
    for key in ("source_row_ids","start_frame","end_frame","blank_sweep"):
        assert reference[key].shape==(p,) and reference[key].dtype.kind in "iu",f"bank integer source {key}"
    assert set(reference["source_row_ids"].tolist())==set(range(p)),"original row IDs must be complete"
    assert np.all((reference["start_frame"]>=0)&(reference["end_frame"]>reference["start_frame"])&
                  (reference["end_frame"]<=metadata["n_source_frames"])),"invalid source frame bounds"
    assert np.array_equal(np.lexsort((reference["source_row_ids"],reference["end_frame"],reference["start_frame"])),np.arange(p)),"chronological source draw axis required"
    for key in ("direction","temporal_frequency"):
        assert reference[key].shape==(p,) and not np.isinf(reference[key]).any(),"invalid source stimulus values"
    assert np.isfinite(reference["trial_response"]).all(),"nonfinite source trial means"
    use=included(reference)
    reference["directions"]=np.unique(reference["direction"][use])
    reference["frequencies"]=np.unique(reference["temporal_frequency"][use])
    np.testing.assert_array_equal(reference["directions"],np.arange(0,360,45))
    assert len(reference["frequencies"])>0 and np.all(reference["frequencies"]>0)
    expected=dict(n_neurons_total=c,n_presentations_total=p,n_presentations_nonblank=int(use.sum()),
                  n_conditions=len(reference["directions"])*len(reference["frequencies"]),
                  directions_deg=reference["directions"].tolist(),temporal_frequencies_hz=reference["frequencies"].tolist())
    match(metadata,expected)
    validate_versions(metadata)
    return reference


def load_reference(path=None):
    path=Path(path) if path else Path(__file__).with_name("reference.npz")
    try:
        with np.load(path,allow_pickle=False) as data:
            stats=json.loads(str(data["ref_stats"].item()))
            assert stats.get("pipeline_id")==PIPELINE_ID,"obsolete reference; original-source trial bank required"
            reference={key:data["ref_"+key] for key in SOURCE_ARRAYS}
            reference["stats"]=stats
    except (OSError,ValueError,KeyError) as error: raise AssertionError("missing/corrupt genuine reference") from error
    validate_reference(reference)
    contract_path=next((p for p in (Path("/app/method_contract.json"),Path(__file__).resolve().parents[1]/"environment/method_contract.json") if p.is_file()),None)
    assert contract_path is not None,"public method contract missing"
    metadata=stats["metadata"];contract=read_json(contract_path)
    assert metadata["method_contract"]==contract
    assert metadata["method_contract_sha256"]==hashlib.sha256(contract_path.read_bytes()).hexdigest()
    assert metadata["source_nwb_sha256"]==contract["input"]["source_sha256"]
    assert metadata["ophys_experiment_id"]==contract["input"]["ophys_experiment_id"]
    assert metadata["targeted_structure"]==contract["input"]["targeted_structure"]
    assert metadata["session_type"]==contract["input"]["session_type"]
    source=metadata["source_sha256"]
    assert isinstance(source,dict) and source=={contract["input"]["file"]:metadata["source_nwb_sha256"]},"bank source mapping mismatch"
    for key in ("source_manifest_sha256","source_nwb_sha256"):
        assert isinstance(metadata[key],str) and len(metadata[key])==64 and all(c in "0123456789abcdef" for c in metadata[key])
    return reference


def expected_presentations(reference):
    result=[];use=included(reference)
    for i,rowid in enumerate(reference["source_row_ids"]):
        result.append(dict(trial_index=i,source_row_id=int(rowid),start_frame=int(reference["start_frame"][i]),
            end_frame=int(reference["end_frame"][i]),n_frames=int(reference["end_frame"][i]-reference["start_frame"][i]),
            direction_deg=nullable(reference["direction"][i]),temporal_frequency_hz=nullable(reference["temporal_frequency"][i]),
            blank_sweep=int(reference["blank_sweep"][i]),tuning_included=int(use[i])))
    return result


def read_table(output,filename,fields,key_fields,expected_rows):
    expected={tuple(row[k] for k in key_fields):row for row in expected_rows}
    assert len(expected)==len(expected_rows),"invalid reference table keys"
    found=set();ordered=[]
    for row in rows(Path(output)/filename,fields):
        key=tuple(integer(row[k],k) if k in INT_FIELDS else number(row[k],k) if k in CATEGORY_FIELDS else row[k]
                  for k in key_fields)
        assert key in expected and key not in found,f"{filename}: duplicate or unknown key"
        found.add(key);target=expected[key];parsed={}
        for field in fields:
            value=target[field]
            if value is None:
                assert row[field]=="",f"{filename}.{field}: undefined must be empty"
                parsed[field]=None
            elif field in TEXT_FIELDS:
                assert row[field]==value,f"{filename}.{field}: categorical mismatch"
                parsed[field]=row[field]
            elif field in INT_FIELDS:
                assert integer(row[field],field)==value,f"{filename}.{field}: count/identity mismatch"
                parsed[field]=integer(row[field],field)
            elif field in CATEGORY_FIELDS:
                assert number(row[field],field)==value,f"{filename}.{field}: source preference/condition mismatch"
                parsed[field]=number(row[field],field)
            else:
                a=number(row[field],field)
                close(a,value,filename+"."+field,*( (RATIO_ATOL,RATIO_RTOL) if field in ("osi","dsi") else (MEAN_ATOL,MEAN_RTOL)))
                parsed[field]=a
        ordered.append((key,parsed))
    assert found==set(expected),f"{filename}: incomplete source membership"
    return dict(ordered)


def read_trial_responses(output,reference):
    cell={int(v):i for i,v in enumerate(reference["cell_ids"])}
    trial={int(v):i for i,v in enumerate(reference["source_row_ids"])}
    actual=np.empty_like(reference["trial_response"],dtype=float);found=set()
    for row in rows(Path(output)/"trial_responses.csv",TRIAL_FIELDS):
        c,p=integer(row["cell_specimen_id"]),integer(row["source_row_id"])
        assert c in cell and p in trial and (c,p) not in found,"duplicate/unknown cell-trial response"
        found.add((c,p));actual[cell[c],trial[p]]=number(row["mean_dff"],"mean_dff")
    assert len(found)==actual.size,"complete all-cell/all-presentation responses required"
    close(actual,reference["trial_response"],"source trial responses")
    return actual


def check_result(actual,expected):
    for key,value in expected.items():
        assert key in actual,f"results missing {key}"
        if key in ("selective_fraction","split_fraction_mean","split_fraction_sd"):
            close(number(actual[key],key),value,"results."+key,FRACTION_ATOL,0)
        else: match(actual[key],value,"results."+key)


def validate_submitted_algebra(estimates,neurons,result,authoritative_estimates=None):
    """Check actual submitted numbers, especially cancellation-sensitive ratios."""
    by_cell={row["cell_specimen_id"]:[] for row in neurons.values()}
    for row in estimates.values():
        by_cell[row["cell_specimen_id"]].append(row)
        plus,minus=row["r_orth_plus"],row["r_orth_minus"]
        orth=None if plus is None or minus is None else (plus+minus)/2
        if orth is None: assert row["r_orth"] is None,"undefined orthogonal component"
        else: close(row["r_orth"],orth,"submitted orthogonal arithmetic")
        for metric,other in (("osi","r_orth"),("dsi","r_null")):
            denom,ratio,status=ratio_values(row["r_pref"],row[other],row["selection_status"])
            assert row[metric+"_status"]==status,"submitted ratio status/zero-denominator mismatch"
            if denom is None:
                assert row[metric+"_denominator"] is None and row[metric] is None
            elif status=="zero_denominator":
                assert row[metric+"_denominator"]==0 and row[metric] is None,"exact-zero denominator required"
            else:
                given=row[metric+"_denominator"]
                assert given is not None and given!=0,"defined ratio needs nonzero denominator"
                close(given,denom,"submitted denominator arithmetic")
                close(row[metric],ratio,"submitted response-derived ratio",RATIO_ATOL,RATIO_RTOL)
                # Do not let a tiny but source-close altered denominator hide
                # behind the absolute dF/F tolerance.
                close(row[metric],(row["r_pref"]-row[other])/given,"submitted denominator-derived ratio",RATIO_ATOL,RATIO_RTOL)
    for row in neurons.values():
        for metric in ("osi","dsi"):
            values=[r[metric] for r in by_cell[row["cell_specimen_id"]] if r[metric+"_status"]=="ok"]
            assert row["n_valid_"+metric]==len(values),"submitted valid-ratio support mismatch"
            assert row[metric+"_status"]==("defined" if values else "no_valid_estimates")
            if values: close(row[metric],float(np.mean(values)),"submitted mean ratio",RATIO_ATOL,RATIO_RTOL)
            else: assert row[metric] is None
    n=len(neurons);nsel=sum(r["selective"] for r in neurons.values())
    assert integer(result["n_neurons_total"])==n and integer(result["n_selective"])==nsel
    close(number(result["selective_fraction"]),nsel/n,"submitted selective fraction",FRACTION_ATOL,0)
    if result["method"]=="repeated_split_mean_ratio":
        category_rows=list(estimates.values()) if authoritative_estimates is None else authoritative_estimates
        paired=[]
        for rep in range(1,51):
            fractions=[]
            for half in ("A","B"):
                selected=[r for r in category_rows if r["replicate"]==rep and r["selection_half"]==half]
                assert len(selected)==n
                fractions.append(sum(any(r[k] is not None and r[k]>.5 for k in ("osi","dsi")) for r in selected)/n)
            paired.append(float(np.mean(fractions)))
        close(number(result["split_fraction_mean"]),float(np.mean(paired)),"submitted paired split mean",FRACTION_ATOL,0)
        close(number(result["split_fraction_sd"]),float(np.std(paired,ddof=0)),"submitted paired split SD",FRACTION_ATOL,0)


def validate_output_directory(output,reference):
    output=Path(output)
    for name in FILES: assert (output/name).is_file(),f"missing {name}"
    result=read_json(output/"results.json");method=result.get("method")
    assert method in METHODS,"declare one accepted method"
    authoritative=analyze(reference,method)
    read_table(output,"presentations.csv",PRESENTATION_FIELDS,("source_row_id",),expected_presentations(reference))
    response=read_trial_responses(output,reference)
    submitted=analyze(reference,method,response=response,preferences=authoritative["estimates"])
    read_table(output,"condition_means.csv",CONDITION_FIELDS,("cell_specimen_id","direction_deg","temporal_frequency_hz"),authoritative["condition_rows"])
    read_table(output,"condition_means.csv",CONDITION_FIELDS,("cell_specimen_id","direction_deg","temporal_frequency_hz"),submitted["condition_rows"])
    # Source categories remain authoritative; approximate input values may not
    # silently change preference, metric definedness, or threshold membership.
    submitted_tables={}
    for name,fields,keys,kind in (
      ("estimates.csv",ESTIMATE_FIELDS,("cell_specimen_id","replicate","selection_half","measurement_half"),"estimates"),
      ("per_neuron.csv",CELL_FIELDS,("cell_specimen_id",),"neurons")):
        submitted_tables[kind]=read_table(output,name,fields,keys,authoritative[kind])
        # Independently check all arithmetic against the submitted raw receipt.
        # Keep discrete source decisions fixed when tolerable rounded inputs tie.
        adapted=[]
        for source_row,own_row in zip(authoritative[kind],submitted[kind]):
            row=dict(source_row)
            for field in fields:
                if field not in INT_FIELDS|TEXT_FIELDS|CATEGORY_FIELDS and source_row[field] is not None and own_row[field] is not None:
                    row[field]=own_row[field]
            adapted.append(row)
        read_table(output,name,fields,keys,adapted)
    check_result(result,authoritative["results"])
    validate_submitted_algebra(submitted_tables["estimates"],submitted_tables["neurons"],result,authoritative["estimates"])
    metadata=read_json(output/"run_metadata.json")
    expected=dict(reference["stats"]["metadata"]);expected["method"]=method
    for optional in ("software_versions",): expected.pop(optional,None)
    metadata=normalize_source_hash(metadata,expected)
    # Bank metadata includes only the public required fields; harmless extras
    # in participant metadata are permitted.
    required=reference["stats"]["metadata"]["method_contract"]["outputs"]["run_metadata.json"]
    match(metadata,{key:expected[key] for key in required if key!="software_versions"})
    assert metadata["source_sha256"]==expected["source_sha256"],"undeclared source identity"
    assert metadata["method_contract"]==expected["method_contract"],"method contract must be the supplied object"
    validate_versions(metadata)
    assert (output/"findings.md").read_text(encoding="utf-8-sig").strip(),"empty findings"
    return authoritative
