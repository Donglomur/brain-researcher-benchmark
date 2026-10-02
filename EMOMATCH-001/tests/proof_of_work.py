"""Source-bound complete EMOMATCH proof; no historical answer bank or sign gate."""
import hashlib
import numpy as np
import artifact_reader as io
import numerical_contract as n
import reference_composition as c

METHOD_SHA256 = "d86db9e607dfe1668b2aa6883c83a463895beb352712c8d6a53ebfe895e99234"
SCHEMA_SHA256 = "7beec618b63f86fbe66d6223be7e3702ca3bdb8bcc384ed2c651fbf02ccd8b8b"
SOURCE_SHA256 = "70000c5c93c2c43f1e7968feb38aaebb4e7622a5f6d2ec1167191337614ef950"
require = io.require


def authenticated_json(path, pin):
    raw=io.read_bytes(path,io.CAPS["json"])
    require(hashlib.sha256(raw).hexdigest()==pin,"private public-contract pin")
    return io.parse_json(raw)


def load_reference(data_dir="/app/data/emomatch",manifest_path="/app/source_manifest.json",
                   method_path="/app/method_contract.json",schema_path="/app/output_schema.json"):
    method=authenticated_json(method_path,METHOD_SHA256)
    schema=authenticated_json(schema_path,SCHEMA_SHA256)
    require(method["source_manifest_sha256"]==schema["source_manifest_sha256"]==SOURCE_SHA256,"source pin disagreement")
    import source_reconstruction as source  # Grader-owned, never public stage_data.
    require(source.SOURCE_MANIFEST_SHA256==SOURCE_SHA256,"private source module pin")
    primitives=source.reconstruct(data_dir,manifest_path)
    require(primitives["participant_ids"]==list(source.IDS)==method["participant_ids"],"complete fixed20")
    require(primitives["source_proof"]["file_count_authenticated"]==131,"full source authentication")
    for person in primitives["subjects"]:
        require(person["header"]["shape"]==method["source_preconditions"]["bold_shape"],"source shape")
    ref=c.compile_reference(primitives,method,METHOD_SHA256)
    ref["schema"]=schema
    return ref


def texts(value,label):
    require(isinstance(value,np.ndarray) and value.ndim==1 and value.dtype.kind in "US",label+": text axis")
    out=np.char.decode(value,"utf-8").tolist() if value.dtype.kind=="S" else value.tolist()
    require(all(isinstance(v,str) and v for v in out),label+": empty identity")
    return out


def permutation(keys,wanted,label):
    require(len(keys)==len(set(keys)),label+": duplicate key")
    require(set(keys)==set(wanted),label+": complete key set")
    lookup={k:i for i,k in enumerate(keys)}
    return np.asarray([lookup[k] for k in wanted],dtype=np.int64)


def mask(value,label):
    require(value.dtype.kind in "biuf" and np.isin(value,(0,1)).all(),label+": Boolean values")
    return value.astype(bool)


def canonical_arrays(arrays,reference):
    expected=reference["arrays"]
    require(set(expected)<=set(arrays),"required NPZ keys")
    for key,ref in expected.items():
        require(arrays[key].shape==ref.shape,key+": shape")
        io.checked_array(arrays[key])
    axes={k:texts(arrays[k],k) for k in ("participant_id","roi_id","confound_name","column_key","fit_model")}
    perms={k:permutation(axes[k],expected[k].tolist(),k) for k in ("participant_id","roi_id","confound_name","column_key")}
    ix={k:io.integer_array(arrays[k]) for k in ("frame_subject_index","source_frame_index","fit_subject_index","observation_fit_index","observation_frame_index")}
    for key,limit in (("frame_subject_index",len(axes["participant_id"])),("fit_subject_index",len(axes["participant_id"])),
                      ("observation_fit_index",len(axes["fit_model"])),("observation_frame_index",len(ix["source_frame_index"]))):
        require(np.all((ix[key]>=0)&(ix[key]<limit)),key+": index domain")
    fk=[(axes["participant_id"][s],int(t)) for s,t in zip(ix["frame_subject_index"],ix["source_frame_index"])]
    ef=[(expected["participant_id"][s],int(t)) for s,t in zip(expected["frame_subject_index"],expected["source_frame_index"])]
    fp=permutation(fk,ef,"frame axis")
    mk=[(axes["participant_id"][s],m) for s,m in zip(ix["fit_subject_index"],axes["fit_model"])]
    em=[(expected["participant_id"][s],m) for s,m in zip(expected["fit_subject_index"],expected["fit_model"])]
    mp=permutation(mk,em,"fit axis")
    ok=[(mk[m],fk[f]) for m,f in zip(ix["observation_fit_index"],ix["observation_frame_index"])]
    eo=[(em[m],ef[f]) for m,f in zip(expected["observation_fit_index"],expected["observation_frame_index"])]
    op=permutation(ok,eo,"observation axis")
    sp,rp,cp,jp=[perms[k] for k in ("participant_id","roi_id","confound_name","column_key")]
    out={k:v.copy() for k,v in expected.items() if k in axes or k in ix}
    out["frame_time_s"]=n.array(arrays["frame_time_s"],1)[fp]
    for k in ("roi_mean","roi_normalized"): out[k]=n.array(arrays[k],2)[np.ix_(fp,rp)]
    for k in ("roi_raw_mean","roi_raw_sd","normalization_denominator"): out[k]=n.array(arrays[k],2)[np.ix_(sp,rp)]
    out["confound_effective"]=n.array(arrays["confound_effective"],2)[np.ix_(fp,cp)]
    out["confound_was_missing"]=mask(arrays["confound_was_missing"],"missing")[np.ix_(fp,cp)]
    out["design_matrix"]=n.array(arrays["design_matrix"],2)[np.ix_(op,jp)]
    out["column_present"]=mask(arrays["column_present"],"column presence")[np.ix_(mp,jp)]
    out["beta"]=n.array(arrays["beta"],3)[np.ix_(mp,jp,rp)]
    out["contrast_vector"]=n.array(arrays["contrast_vector"],2)[np.ix_(mp,jp)]
    for k in ("contrast_estimate","residual_sse"): out[k]=n.array(arrays[k],2)[np.ix_(mp,rp)]
    out["contrast_defined"]=mask(arrays["contrast_defined"],"defined")[np.ix_(mp,rp)]
    out["contrast_estimable"]=mask(arrays["contrast_estimable"],"estimable")[mp]
    for k in ("design_rank","residual_df"): out[k]=io.integer_array(arrays[k])[mp]
    return out


def validate_arrays(arrays,reference):
    a,e=canonical_arrays(arrays,reference),reference["arrays"]
    for k in ("column_present","confound_was_missing","contrast_vector","contrast_defined","contrast_estimable","design_rank","residual_df"):
        require(np.array_equal(a[k],e[k]),k+": source exact")
    for k in ("roi_raw_sd","normalization_denominator","residual_sse"):
        require(np.all(a[k]>0 if k=="normalization_denominator" else a[k]>=0),k+": domain")
    for k in ("frame_time_s","roi_mean","roi_raw_mean","roi_raw_sd","normalization_denominator","roi_normalized",
              "confound_effective","design_matrix","beta","contrast_estimate","residual_sse"):
        tol=n.FIT_TOL if k in ("beta","contrast_estimate","residual_sse") else n.SOURCE_TOL
        n.check_close(a[k],e[k],n.EVENT_TOL if k=="frame_time_s" else tol,k)
    require(np.all(a["contrast_estimate"][~a["contrast_defined"]]==0),"undefined contrast placeholder")
    for m in range(len(a["fit_model"])):
        present=a["column_present"][m]
        obs=a["observation_fit_index"]==m
        require(np.all(a["design_matrix"][obs][:,~present]==0) and np.all(a["beta"][m,~present]==0) and
                np.all(a["contrast_vector"][m,~present]==0),"absent column exact zero")
        for r in np.flatnonzero(a["contrast_defined"][m]):
            n.validate_linear_receipt(a["beta"][m,present,r],e["beta"][m,present,r],e["contrast_vector"][m,present],a["contrast_estimate"][m,r])
    return a


def match(actual,expected,tolerance=n.GEOMETRY_TOL,*,closed=False,label="JSON"):
    if expected is None: require(actual is None,label+": null")
    elif isinstance(expected,bool): require(type(actual) is bool and actual==expected,label+": Boolean")
    elif isinstance(expected,(int,np.integer)): require(io.integer(actual,json_number=True)==expected,label+": integer")
    elif isinstance(expected,(float,np.floating)) or hasattr(expected,"is_finite"):
        n.check_close(io.real(actual,json_number=True),float(expected),tolerance,label)
    elif isinstance(expected,str): require(type(actual) is str and actual==expected,label+": text")
    elif isinstance(expected,list):
        require(isinstance(actual,list) and len(actual)==len(expected),label+": list")
        for a,b in zip(actual,expected): match(a,b,tolerance,closed=closed,label=label)
    elif isinstance(expected,dict):
        require(isinstance(actual,dict) and set(expected)<=set(actual),label+": object keys")
        if closed: require(set(actual)==set(expected),label+": closed object")
        for k in expected: match(actual[k],expected[k],tolerance,closed=closed,label=label+"."+k)
    else: raise ValueError("unsupported expected JSON type")


def keyed_json(rows,keys,label):
    require(isinstance(rows,list),label+": list")
    out={}
    for row in rows:
        require(isinstance(row,dict) and all(type(row.get(k)) is str and row[k] for k in keys),label+": key types")
        key=tuple(row[k] for k in keys)
        require(key not in out,label+": duplicate key")
        out[key]=row
    return out


def csv_value(value,descriptor):
    if descriptor.startswith("nullable:"):
        if value=="": return None
        descriptor=descriptor[9:]
    if descriptor=="boolean": return io.csv_boolean(value)
    if descriptor in ("index","count","integer"):
        result=io.integer(value)
        require(descriptor=="integer" or result>=0,"CSV nonnegative integer")
        return result
    if descriptor in ("real","nonnegative_real","positive_real"):
        result=io.real(value)
        require(descriptor=="real" or (result>0 if descriptor=="positive_real" else result>=0),"CSV numeric domain")
        return result
    require(isinstance(value,str),"CSV text")
    if descriptor in ("id","sha256"): require(bool(value),"CSV empty identity")
    return value


def table(actual,expected,name,reference,tolerance):
    schema=reference["schema"]["tables"][name]
    columns=schema["required_columns"]
    typed=[]
    for row in actual:
        require(set(columns)<=set(row),name+": missing columns")
        typed.append({k:csv_value(row[k],d) for k,d in columns.items()})
    def index(rows):
        result={}
        for row in rows:
            key=tuple(row[k] for k in schema["key"])
            require(key not in result,name+": duplicate key")
            result[key]=row
        return result
    got,want=index(typed),index(expected)
    require(set(got)==set(want),name+": row membership")
    for key in want: match(got[key],want[key],tolerance,label=name)
    return [got[key] for key in want]


def activation_table(rows,arrays,reference):
    actual=table(rows,reference["activation"],"activation.csv",reference,n.FIT_TOL)
    rois=reference["arrays"]["roi_id"].tolist()
    for s,row in enumerate(actual):
        for j,model in enumerate(c.MODELS):
            m=2*s+j
            for name,members in c.AGGREGATES.items():
                value=row[name+"_"+model]
                if value is not None:
                    ix=[rois.index(r) for r in members]
                    n.validate_linear_receipt(arrays["contrast_estimate"][m,ix],reference["arrays"]["contrast_estimate"][m,ix],
                                              np.full(len(ix),1/len(ix)),value)
    return actual


def metadata(actual,reference):
    expected=reference["metadata"]
    require(isinstance(actual,dict) and set(expected)<=set(actual),"metadata keys")
    for k in ("schema_id","task_id","status","source_manifest_sha256","method_contract_sha256"):
        match(actual[k],expected[k],label="metadata."+k)
    match(actual["method"],expected["method"],n.Tolerance(0,0),closed=True,label="public method")
    require(isinstance(actual["selected_participant_ids"],list),"metadata cohort")
    permutation(actual["selected_participant_ids"],expected["selected_participant_ids"],"metadata people")
    for field,keys in (("source_files",("path",)),("fits",("participant_id","model"))):
        got,want=keyed_json(actual[field],keys,field),keyed_json(expected[field],keys,field)
        require(set(got)==set(want),field+": keys")
        for key,ref in want.items():
            match(got[key],ref,n.DIAGNOSTIC_TOL if field=="fits" else n.Tolerance(0,0),label=field)
            if field=="fits":
                require("solver" in got[key] and bool(got[key]["solver"]),"solver description")
                require(isinstance(got[key].get("warnings"),list),"fit warnings")
                for name in ("singular_values","rank_cutoff","contrast_rowspace_residual","estimability_bound"):
                    require(np.all(n.array(got[key][name])>=0),"negative fit diagnostic")
    got,want=actual["source_observed"],expected["source_observed"]
    require(isinstance(got,dict) and set(want)<=set(got),"source observations")
    for field,keys,tol in (("participants",("participant_id",),n.GEOMETRY_TOL),
                          ("duration_rt_comparison",("participant_id",),n.EVENT_TOL),
                          ("documentary_duplicate_keys",("path","key"),n.Tolerance(0,0))):
        ga,ex=keyed_json(got[field],keys,field),keyed_json(want[field],keys,field)
        require(set(ga)==set(ex),field+": keys")
        for key,ref in ex.items():
            value=ga[key].copy()
            if field=="participants":
                require(type(value.get("source_dtype")) is str,"dtype text")
                require(np.dtype(value["source_dtype"])==np.dtype(ref["source_dtype"]),"source dtype semantics")
                value["source_dtype"]=ref["source_dtype"]
            match(value,ref,tol,label=field)
            if field=="duration_rt_comparison":
                for name in ("max_abs_source_duration_minus_rt_s","max_abs_source_duration_minus_imputed_modelB_s"):
                    if value[name] is not None:
                        require(io.real(value[name],json_number=True)>=0,"nonnegative duration magnitude")
    atlas=got["atlas"].copy()
    for key in ("label_ids","network_names"):
        require(isinstance(atlas.get(key),list),"atlas axis")
        vals=[io.integer(v,json_number=True) for v in atlas[key]] if key=="label_ids" else atlas[key]
        permutation(vals,want["atlas"][key],"atlas "+key)
        atlas[key]=want["atlas"][key]
    match(atlas,want["atlas"],n.GEOMETRY_TOL,label="atlas")
    for field in ("event_column_names","confound_column_names"):
        match(got[field],want[field],n.EVENT_TOL,closed=True,label=field)
    match(got["documented_timing"],want["documented_timing"],n.EVENT_TOL,label="documented timing")
    for field in ("raw_bold_paths","preproc_bold_paths","scanner_discarded_volumes"):
        match(got["documented_timing"][field],want["documented_timing"][field],n.EVENT_TOL,
              closed=True,label="timing participant map")
    versions=actual.get("software_versions")
    require(isinstance(versions,dict) and versions and all(type(k) is str and k for k in versions),"software versions")
    require(isinstance(actual.get("warnings"),list),"warnings list")


def summary(actual,expected):
    require(isinstance(actual,dict),"statistic object")
    normalized=actual.copy()
    for key in ("n_expected","n_defined","df"):
        if normalized.get(key) is not None: normalized[key]=io.integer(normalized[key],json_number=True)
    n.validate_summary(normalized,expected)


def group_stats(actual,arrays,activation,reference):
    require(isinstance(actual,dict) and isinstance(actual.get("rt_summary"),dict),"group/RT object")
    rt=actual["rt_summary"]
    got=keyed_json(rt.get("per_subject"),("participant_id",),"RT people")
    want={(r["participant_id"],):r for r in reference["rt_records"]}
    require(set(got)==set(want),"RT people membership")
    accepted=[]
    for key,ref in want.items():
        match(got[key],ref,n.EVENT_TOL,label="RT source")
        row={k:got[key][k] for k in ref}
        for field in ("mean_emotion_s","mean_control_s","difference_s"):
            row[field]=None if row[field] is None else io.real(row[field],json_number=True)
        for field in ("n_valid_emotion","n_valid_control"): row[field]=io.integer(row[field],json_number=True)
        if row["difference_s"] is not None:
            n.validate_linear_receipt([row["mean_emotion_s"],row["mean_control_s"]],
                [ref["mean_emotion_s"],ref["mean_control_s"]],[1.,-1.],row["difference_s"],n.EVENT_TOL,n.EVENT_TOL)
        accepted.append(row)
    expected=c.own_groups(reference,arrays["contrast_estimate"],activation,accepted)
    for key in ("schema_id","status","n_expected"): match(actual.get(key),expected[key],label="group "+key)
    for field,keys in (("models",("model","endpoint")),("paired_changes",("endpoint",))):
        ga,ex=keyed_json(actual.get(field),keys,field),keyed_json(expected[field],keys,field)
        require(set(ga)==set(ex),field+": endpoint family")
        for key,ref in ex.items():
            value=ga[key]
            if field=="models":
                require(isinstance(value.get("roi_ids"),list) and isinstance(value.get("weights"),list),"endpoint weights")
                require(len(value["roi_ids"])==len(value["weights"]),"weight axis")
                order=permutation(value["roi_ids"],ref["roi_ids"],"endpoint ROI membership")
                n.check_close(n.array(value["weights"],1)[order],ref["weights"],n.GROUP_TOL,"fixed endpoint weights")
            summary(value.get("statistic"),ref["statistic"])
    for key in ("emotion","control","emotion_minus_control"): summary(rt.get(key),expected["rt_summary"][key])


def validate_output_directory(output_dir,reference):
    parsed=io.read_artifacts(output_dir)
    arrays=validate_arrays(parsed["glm_arrays.npz"],reference)
    table(parsed["cohort.csv"],reference["cohort"],"cohort.csv",reference,n.EVENT_TOL)
    table(parsed["events.csv"],reference["events"],"events.csv",reference,n.EVENT_TOL)
    table(parsed["roi_support.csv"],reference["supports"],"roi_support.csv",reference,n.GEOMETRY_TOL)
    activation=activation_table(parsed["activation.csv"],arrays,reference)
    metadata(parsed["run_metadata.json"],reference)
    group_stats(parsed["group_stats.json"],arrays,activation,reference)
    return dict(status="accepted",participants=len(arrays["participant_id"]),rois=len(arrays["roi_id"]),
                fits=len(arrays["fit_model"]),frames=len(arrays["source_frame_index"]),
                source_bound=True,own_group_recomputation=True,historical_bank_used=False)
