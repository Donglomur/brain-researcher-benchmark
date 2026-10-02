"""Typed source-bound MOVIESYNC verifier; no historical endpoint/pattern gates.

The trusted reference is reconstructed by grader-owned code from originals.
Accepted submitted series determine every defined downstream ISC value.
"""
from __future__ import annotations
import numpy as np
import artifact_reader as a
import isc_math as m


def strings(values,name):
    a.require(isinstance(values,np.ndarray) and values.ndim==1 and values.dtype.kind in "US",f"{name}: text axis")
    result=[v.decode("utf-8") if isinstance(v,bytes) else str(v) for v in values.tolist()]
    a.require(all(result) and len(set(result))==len(result),f"{name}: empty/duplicate keys")
    return result


def reorder(actual,expected,name):
    actual=list(actual); expected=list(expected)
    a.require(len(actual)==len(set(actual)) and set(actual)==set(expected),f"{name}: exact key membership")
    lookup={key:i for i,key in enumerate(actual)}
    return np.asarray([lookup[key] for key in expected],dtype=int)


def numeric_close(actual,expected,atol,rtol,name):
    a.require(np.shape(actual)==np.shape(expected),f"{name}: numeric shape")
    a.require(np.isfinite(actual).all() and np.isfinite(expected).all(),f"{name}: nonfinite")
    a.require(np.all(np.abs(np.asarray(actual)-expected)<=atol+rtol*np.abs(expected)),f"{name}: numeric mismatch")


def match(actual,expected,name,*,json_number=True,atol=1e-9,rtol=1e-9):
    if isinstance(expected,dict):
        a.require(isinstance(actual,dict) and set(expected)<=set(actual),f"{name}: missing fields")
        for key,value in expected.items(): match(actual[key],value,f"{name}.{key}",json_number=json_number,atol=atol,rtol=rtol)
    elif isinstance(expected,list):
        a.require(isinstance(actual,list) and len(actual)==len(expected),f"{name}: list support")
        for i,(x,y) in enumerate(zip(actual,expected)): match(x,y,f"{name}[{i}]",json_number=json_number,atol=atol,rtol=rtol)
    elif expected is None:
        a.require(actual is None,f"{name}: null required")
    elif isinstance(expected,bool):
        a.require(type(actual) is bool and actual==expected,f"{name}: Boolean mismatch")
    elif isinstance(expected,(int,np.integer)):
        a.require(a.integer(actual,json_number=json_number)==expected,f"{name}: integer mismatch")
    elif isinstance(expected,(float,np.floating)):
        numeric_close(a.real(actual,json_number=json_number),float(expected),atol,rtol,name)
    else:
        a.require(type(actual) is str and actual==expected,f"{name}: literal mismatch")


def scalar(value,expected,name,*,csv=False):
    if expected is None:
        a.require(value=="" if csv else value is None,f"{name}: explicit undefined null required")
    else:
        v=a.real(value,json_number=not csv)
        a.require(-1-m.SCALAR_ATOL<=v<=1+m.SCALAR_ATOL,f"{name}: correlation domain")
        numeric_close(v,expected,m.SCALAR_ATOL,0.,name)


def canonical_arrays(arrays,ref):
    names=("participant_ids","map_ids","map_labels","frame_indices","raw_coefficients",
           "visual_map_ids","isc_inputs","person_active","template_active")
    a.require(set(names)<=set(arrays),"missing timecourse arrays")
    pi=reorder(strings(arrays["participant_ids"],"participant_ids"),ref["participant_ids"].tolist(),"participants")
    axes={}
    for name in ("map_ids","frame_indices","visual_map_ids"):
        ar=a.integer_array(arrays[name]); a.require(ar.ndim==1,f"{name}: axis shape")
        axes[name]=reorder(ar.tolist(),ref[name].tolist(),name)
    labels=arrays["map_labels"]
    a.require(labels.ndim==1 and labels.dtype.kind in "US" and len(labels)==39,"map_labels axis")
    labels=[v.decode("utf-8") if isinstance(v,bytes) else str(v) for v in labels.tolist()]
    a.require([labels[i] for i in axes["map_ids"]]==ref["map_labels"].tolist(),"source map-label binding")
    shapes={"raw_coefficients":(40,168,39),"isc_inputs":(40,168,3),"person_active":(40,3),"template_active":(40,3)}
    for name,shape in shapes.items():
        ar=arrays[name]; a.require(ar.shape==shape,f"{name}: production shape")
        a.require(ar.dtype.kind=="b" if name.endswith("active") else ar.dtype.kind=="f",f"{name}: dtype")
    raw=np.asarray(arrays["raw_coefficients"][np.ix_(pi,axes["frame_indices"],axes["map_ids"])],dtype=np.float64)
    x=np.asarray(arrays["isc_inputs"][np.ix_(pi,axes["frame_indices"],axes["visual_map_ids"])],dtype=np.float64)
    numeric_close(raw,ref["raw_coefficients"],m.RAW_ATOL,m.RAW_RTOL,"source raw coefficients")
    support=m.source_fidelity(x,ref["isc_inputs"])
    for name in ("person_active","template_active"):
        a.require(np.array_equal(arrays[name][np.ix_(pi,axes["visual_map_ids"])],support[name]),f"{name}: source support")
    return x,support


def aggregate(values):
    values=list(values); value=m.complete_mean(values)
    return dict(value=value,status="ok" if value is not None else "incomplete_support",
                n_expected=len(values),n_defined=sum(v is not None for v in values))


def expected_tables_and_results(x,support,ref,estimator):
    a.require(estimator in ("pairwise","loo","leave-one-out"),"estimator enum")
    kind="loo" if estimator=="leave-one-out" else estimator
    own=m.replay(x,support); ids=ref["participant_ids"].tolist(); mids=ref["visual_map_ids"].tolist()
    labels={int(i):str(label) for i,label in zip(ref["map_ids"],ref["map_labels"])}
    n=len(ids); k=len(mids); pairs=[]; people=[]
    for (i,j,r),value in own["pairs"].items():
        pairs.append(dict(participant_a=ids[i],participant_b=ids[j],map_id=mids[r],map_label=labels[mids[r]],
                          r=value,status="ok" if value is not None else "inactive_person"))
    for i,person in enumerate(ids):
        for r,mid in enumerate(mids):
            v=own["per_person_region"][i][r]
            ls="inactive_target" if not support["person_active"][i,r] else ("inactive_template" if not support["template_active"][i,r] else "ok")
            people.append(dict(participant_id=person,map_id=mid,map_label=labels[mid],isc_pairwise=v["pairwise"],
                               pairwise_status="ok" if v["pairwise"] is not None else "incomplete_pair_support",
                               pairwise_n_expected=n-1,pairwise_n_defined=v["n_pairs_defined"],isc_loo=v["loo"],
                               loo_status=ls,loo_n_expected=n-1,loo_n_defined=n-1,
                               loo_n_active_contributors=int(support["person_active"][:,r].sum()-support["person_active"][i,r])))
    per_subject=[dict(participant_id=person,**{est:aggregate(own["per_person_region"][i][r][est] for r in range(k))
                  for est in ("pairwise","loo")}) for i,person in enumerate(ids)]
    per_region=[]
    for r,mid in enumerate(mids):
        per_region.append(dict(map_id=mid,map_label=labels[mid],
                               pairwise=aggregate(own["pairs"][i,j,r] for i in range(n) for j in range(i+1,n)),
                               loo=aggregate(own["per_person_region"][i][r]["loo"] for i in range(n))))
    estimators={est:aggregate(row[est]["value"] for row in per_subject) for est in ("pairwise","loo")}
    result=dict(schema_version="moviesync-results-v2",status="ok",isc_estimator=estimator,
                visual_isc=estimators[kind]["value"],visual_isc_status=estimators[kind]["status"],
                n_subjects=n,n_timepoints=x.shape[1],reference_zero=0.,estimators=estimators,
                per_region=per_region,per_subject=per_subject)
    return pairs,people,result


def validate_cohort(rows,ref):
    keyed=a.keyed_rows(rows,["participant_id"])
    expected={row["participant_id"]:row for row in ref["cohort"]}
    a.require(set(keyed)=={(v,) for v in expected},"cohort exact membership")
    for person,row in expected.items(): match(keyed[person,],row,"cohort",json_number=False,atol=0,rtol=0)


def validate_pair_rows(rows,expected):
    def key(row):
        a.require(isinstance(row.get("participant_a"),str) and isinstance(row.get("participant_b"),str),"pair IDs")
        i,j=sorted([row["participant_a"],row["participant_b"]]); a.require(i!=j,"self pair")
        return i,j,a.integer(row["map_id"])
    got={}
    for row in rows:
        a.require({"participant_a","participant_b","map_id","map_label","r","status"}<=set(row),"pair columns")
        k=key(row); a.require(k not in got,"duplicate unordered pair"); got[k]=row
    want={key(row):row for row in expected}; a.require(set(got)==set(want),"complete pair family")
    for k,row in want.items():
        match(got[k]["map_label"],row["map_label"],"pair label")
        match(got[k]["status"],row["status"],"pair status")
        scalar(got[k]["r"],row["r"],"own pair r",csv=True)


def validate_person_rows(rows,expected):
    got=a.keyed_rows(rows,["participant_id","map_id"],integer_columns=["map_id"])
    want={(row["participant_id"],row["map_id"]):row for row in expected}
    a.require(set(got)==set(want),"complete person-region family")
    for key,row in want.items():
        actual=got[key]; a.require(set(row)<=set(actual),"person-region columns")
        for field,value in row.items():
            if field in ("isc_pairwise","isc_loo"): scalar(actual[field],value,"own "+field,csv=True)
            else: match(actual[field],value,"person-region "+field,json_number=False,atol=0,rtol=0)


def json_keyed(rows,key,*,integer=False):
    a.require(isinstance(rows,list),"JSON keyed list")
    result={}
    for row in rows:
        a.require(isinstance(row,dict) and key in row,"JSON record/key")
        value=a.integer(row[key],json_number=True) if integer else row[key]
        a.require(isinstance(value,(str,int)) and type(value) is not bool,"JSON key type")
        a.require(value not in result,"duplicate JSON key record"); result[value]=row
    return result


def validate_aggregate(actual,expected,name):
    a.require(isinstance(actual,dict) and set(expected)<=set(actual),f"{name}: aggregate fields")
    scalar(actual["value"],expected["value"],name)
    for key in ("status","n_expected","n_defined"): match(actual[key],expected[key],name+"."+key,atol=0,rtol=0)


def validate_results(actual,expected):
    a.require(isinstance(actual,dict) and set(expected)<=set(actual),"results fields")
    scalar(actual["visual_isc"],expected["visual_isc"],"own visual_isc")
    for key in ("schema_version","status","isc_estimator","visual_isc_status","n_subjects","n_timepoints","reference_zero"):
        match(actual[key],expected[key],"results "+key,atol=0,rtol=0)
    a.require(isinstance(actual["estimators"],dict) and set(actual["estimators"])=={"pairwise","loo"},"estimator family")
    for est in ("pairwise","loo"): validate_aggregate(actual["estimators"][est],expected["estimators"][est],"own "+est+" headline")
    for field,key,is_int in (("per_region","map_id",True),("per_subject","participant_id",False)):
        got=json_keyed(actual[field],key,integer=is_int); want={r[key]:r for r in expected[field]}
        a.require(set(got)==set(want),field+" membership")
        for k,row in want.items():
            for item,value in row.items():
                if item in ("pairwise","loo"): validate_aggregate(got[k].get(item),value,"own "+field+" "+item)
                else: match(got[k].get(item),value,field+" "+item)


def validate_metadata(actual,ref,estimator):
    expected=ref["metadata"]
    for key in ("schema_version","status","task_id","method_sha256","output_schema_sha256","source_manifest_sha256"):
        match(actual.get(key),expected[key],"metadata "+key)
    a.require(actual.get("isc_estimator")==estimator,"metadata/result estimator disagreement")
    got=json_keyed(actual.get("source_files"),"path"); want={row["path"]:row for row in expected["source_files"]}
    a.require(set(got)==set(want),"source file membership")
    for key,row in want.items(): match(got[key],row,"source file",atol=0,rtol=0)
    obs=actual.get("source_observed"); source=expected["source_observed"]
    a.require(isinstance(obs,dict) and set(source)<=set(obs),"source observations")
    for key in ("participant_ids","visual_map_ids"):
        values=obs[key]; a.require(isinstance(values,list),"source axis list")
        if key=="visual_map_ids": values=[a.integer(v,json_number=True) for v in values]
        else: a.require(all(type(v) is str for v in values),"source participant literal types")
        reorder(values,source[key],"source "+key)
    for key,axis,is_int in (("map_labels","map_id",True),("headers","participant_id",False)):
        items=json_keyed(obs[key],axis,integer=is_int); original={row[axis]:row for row in source[key]}
        a.require(set(items)==set(original),"source "+key+" membership")
        for ident,row in original.items():
            value=dict(items[ident]); target=dict(row)
            if "source_dtype" in row:
                try: equivalent=np.dtype(value.pop("source_dtype"))==np.dtype(target.pop("source_dtype"))
                except (TypeError,ValueError,KeyError): equivalent=False
                a.require(equivalent,"source dtype")
            match(value,target,"source "+key)
    a.require(isinstance(obs["atlas_header"],dict),"atlas header object")
    atlas=dict(obs["atlas_header"]); atlas_expected=dict(source["atlas_header"])
    try: equivalent=np.dtype(atlas.pop("source_dtype"))==np.dtype(atlas_expected.pop("source_dtype"))
    except (TypeError,ValueError,KeyError): equivalent=False
    a.require(equivalent,"atlas dtype"); match(atlas,atlas_expected,"atlas header")
    a.require(isinstance(obs["confound_column_names"],dict) and set(obs["confound_column_names"])==set(source["confound_column_names"]),"confound header participant keys")
    for key in ("confound_column_names","participant_column_names","effective_TR_s","effective_origin_s","frame_alignment"):
        match(obs[key],source[key],"source "+key)
    versions=actual.get("software_versions")
    a.require(isinstance(versions,dict) and {"python","numpy","scipy","nibabel","nilearn"}<=set(versions),"software metadata")
    a.require(all(isinstance(versions[key],str) and versions[key].strip() for key in ("python","numpy","scipy","nibabel","nilearn")),"actual version strings")


def validate_output_directory(output,reference):
    a.require(len(reference["participant_ids"])==40 and reference["raw_coefficients"].shape==(40,168,39),"full production source basis required")
    artifacts=a.read_artifacts(output)
    validate_cohort(artifacts["cohort.csv"],reference)
    x,support=canonical_arrays(artifacts["timecourses.npz"],reference)
    result=artifacts["isc_results.json"]; estimator=result.get("isc_estimator")
    pairs,people,expected=expected_tables_and_results(x,support,reference,estimator)
    validate_pair_rows(artifacts["isc_pairs.csv"],pairs)
    validate_person_rows(artifacts["isc_per_subject.csv"],people)
    validate_results(result,expected)
    validate_metadata(artifacts["run_metadata.json"],reference,estimator)
    return dict(n_subjects=40,n_timepoints=168,n_pairs=len(pairs),n_person_region=len(people),
                isc_estimator=estimator,headline_status=expected["visual_isc_status"])
