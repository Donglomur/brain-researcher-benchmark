"""Source-indexed trial-generalization contract; no accuracy/direction gates."""
import csv
from decimal import Decimal,InvalidOperation
import json
import math
from pathlib import Path
import numpy as np

SOURCE_FIELDS = ("source_event_index","event_sample","previous_value","event_code","modality","retained","drop_reason","trial_id","max_ptp_T_per_m","max_ptp_channel")
PREDICTION_FIELDS = ("estimator","source_event_index","trial_id","time_index","sample_offset","time_s","fold","true_class","predicted_class","decision_score")
FOLD_FIELDS = ("estimator","time_index","fold","n_train_trials","n_test_trials","n_train_samples","n_test_samples","n_train_class0","n_train_class1","n_test_class0","n_test_class1","n_correct","accuracy")
TIME_FIELDS = ("time_index","sample_offset","time_s","accuracy","pooled_accuracy","n_test_trials")
ESTIMATORS = ("pooled","per_time")


def require(condition,message):
    if not condition:
        raise AssertionError(message)


def integer(value):
    require(not isinstance(value,(bool,np.bool_)) and isinstance(value,(str,int,float,np.integer,np.floating)),"Invalid integer identity/count type")
    try:
        result = Decimal(str(value).strip())
    except InvalidOperation as error:
        raise AssertionError("Invalid integer notation") from error
    require(result.is_finite() and result==result.to_integral_value(),"Nonintegral/nonfinite identity/count")
    return int(result)


def number(value):
    require(not isinstance(value,(bool,np.bool_)) and isinstance(value,(str,int,float,np.integer,np.floating)),"Invalid numeric type")
    try:
        result = float(value)
    except (ValueError,TypeError,OverflowError) as error:
        raise AssertionError("Invalid number") from error
    require(math.isfinite(result),"Nonfinite number")
    return result


def source_modality(value):
    """Normalize only the two public source-ledger class encodings."""
    if isinstance(value,str):
        label = value.strip()
        if label in ("auditory","visual"):
            return {"auditory":0,"visual":1}[label]
    result = integer(value)
    require(result in (0,1),"Unknown source modality")
    return result


def close(actual,expected,atol=1e-6,rtol=0,name="measurement"):
    require(abs(number(actual)-float(expected))<=atol+rtol*abs(float(expected)),f"{name} differs from source/declared arithmetic")


def json_load(path):
    def pairs(items):
        result = {}
        for key,value in items:
            require(key not in result,"Duplicate JSON key")
            result[key] = value
        return result
    def invalid(token):
        raise AssertionError("Nonfinite JSON token")
    try:
        return json.loads(Path(path).read_text(),object_pairs_hook=pairs,parse_constant=invalid)
    except (OSError,ValueError) as error:
        raise AssertionError("Required JSON is missing or malformed") from error


def csv_load(path,fields):
    try:
        with Path(path).open(newline="",encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            names = reader.fieldnames
            require(names is not None and len(names)==len(set(names)) and set(fields)<=set(names),"Missing/duplicate required CSV columns")
            rows = list(reader)
    except OSError as error:
        raise AssertionError("Missing required CSV") from error
    require(all(None not in row and all(row[name] is not None for name in fields) for row in rows),"Malformed CSV row")
    return rows


def match(actual,expected,path="value",atol=0,rtol=0,closed=False):
    if isinstance(expected,dict):
        require(isinstance(actual,dict) and set(expected)<=set(actual),f"Missing required {path} field")
        if closed:
            require(set(actual)==set(expected),f"Changed scientific identity set {path}")
        for key,value in expected.items():
            match(actual[key],value,f"{path}.{key}",atol,rtol,closed)
    elif isinstance(expected,list):
        require(isinstance(actual,list) and len(actual)==len(expected),f"Wrong list support {path}")
        for a,b in zip(actual,expected):
            match(a,b,path,atol,rtol,closed)
    elif isinstance(expected,bool):
        require(isinstance(actual,bool) and actual==expected,f"Wrong boolean {path}")
    elif expected is None:
        require(actual is None,f"Undefined {path} must be null")
    elif isinstance(expected,int):
        require(integer(actual)==expected,f"Wrong integer {path}")
    elif isinstance(expected,float):
        close(actual,expected,atol,rtol,path)
    else:
        require(isinstance(actual,str) and actual==expected,f"Wrong identity/status {path}")


def validate_source(rows,reference):
    expected = {row["source_event_index"]:row for row in reference["source_rows"]}
    require(len(rows)==len(expected),"Complete original source event ledger required")
    seen = set()
    for row in rows:
        key = integer(row["source_event_index"])
        require(key in expected and key not in seen,"Duplicate/unknown original event")
        seen.add(key)
        for field in SOURCE_FIELDS:
            value = expected[key][field]
            if value is None:
                require(row[field].strip()=="",f"Undefined source field {field} must be blank")
            elif field=="modality":
                require(source_modality(row[field])==int(value),"Wrong source modality")
            elif field=="max_ptp_T_per_m":
                actual = number(row[field])
                require(actual>=0,"Negative peak-to-peak value")
                close(actual,value,1e-20,1e-7,"source peak-to-peak")
            elif field=="max_ptp_channel":
                allowed = reference.get("max_ptp_channels",{}).get(str(key),[value])
                require(row[field] in allowed,"Wrong source maximum-PTP channel")
            elif isinstance(value,str):
                require(row[field]==value,f"Wrong source {field}")
            else:
                require(integer(row[field])==int(value),f"Wrong source {field}")


def validate_predictions(rows,reference):
    labels,folds = reference["labels"],reference["folds"]
    n,t = len(labels),len(reference["analysis_offsets"])
    require(len(rows)==2*n*t,"Complete two-estimator OOF trial-time table required")
    predictions = {name:np.empty((n,t),dtype=np.int8) for name in ESTIMATORS}
    seen = set()
    for row in rows:
        name = row["estimator"]
        trial,time = integer(row["trial_id"]),integer(row["time_index"])
        key = (name,trial,time)
        require(name in ESTIMATORS and 0<=trial<n and 0<=time<t and key not in seen,"Duplicate/unknown estimator trial-time identity")
        seen.add(key)
        require(integer(row["source_event_index"])==int(reference["retained_event_indices"][trial]),"Wrong original retained event identity")
        require(integer(row["sample_offset"])==int(reference["analysis_offsets"][time]),"Wrong source sample offset")
        close(row["time_s"],reference["times"][time],1e-10,0,"source time clock")
        require(integer(row["fold"])==int(folds[trial]),"Wrong shared original-trial fold")
        require(integer(row["true_class"])==int(labels[trial]),"Wrong original modality class")
        score = number(row["decision_score"])
        close(score,reference[name+"_scores"][trial,time],1e-5,1e-6,"source model decision score")
        prediction = integer(row["predicted_class"])
        require(prediction in (0,1) and prediction==int(score>0),"Prediction must follow submitted signed score")
        predictions[name][trial,time] = prediction
    return predictions


def summaries(reference,predictions):
    labels,folds = reference["labels"],reference["folds"]
    n,t = len(labels),len(reference["analysis_offsets"])
    fold_rows = []
    for name in ESTIMATORS:
        for ti in ([None] if name=="pooled" else range(t)):
            for fold in range(1,6):
                test = folds==fold
                train = ~test
                target = labels[test,None] if name=="pooled" else labels[test]
                pred = predictions[name][test] if name=="pooled" else predictions[name][test,ti]
                count = int(np.sum(pred==target))
                factor = t if name=="pooled" else 1
                n_test = int(test.sum())*factor
                require(n_test>0,"Missing test fold")
                fold_rows.append(dict(estimator=name,time_index=ti,fold=fold,
                    n_train_trials=int(train.sum()),n_test_trials=int(test.sum()),
                    n_train_samples=int(train.sum())*factor,n_test_samples=n_test,
                    n_train_class0=int(np.sum(train&(labels==0))),n_train_class1=int(np.sum(train&(labels==1))),
                    n_test_class0=int(np.sum(test&(labels==0))),n_test_class1=int(np.sum(test&(labels==1))),
                    n_correct=count,accuracy=count/n_test))
    time_rows = [dict(time_index=ti,sample_offset=int(reference["analysis_offsets"][ti]),time_s=float(reference["times"][ti]),
        accuracy=sum(row["accuracy"] for row in fold_rows if row["estimator"]=="per_time" and row["time_index"]==ti)/5,
        pooled_accuracy=float(np.mean(predictions["per_time"][:,ti]==labels)),n_test_trials=n) for ti in range(t)]
    result = dict(status="ok",accuracy=sum(row["accuracy"] for row in fold_rows if row["estimator"]=="pooled")/5,
        pooled_oof_accuracy=float(np.mean(predictions["pooled"]==labels[:,None])),n_trials=n,
        n_time_samples_per_trial=t,n_samples_total=n*t,n_classes=2,n_channels=len(reference["channel_names"]),
        n_folds=5,classes=["auditory","visual"],chance_level=.5)
    return fold_rows,time_rows,result


def validate_aggregate_rows(rows,expected,fields,key_fields):
    def key(row):
        return tuple(row[field] if field=="estimator" else (None if row[field] is None or row[field]=="" else integer(row[field])) for field in key_fields)
    lookup = {key(row):row for row in expected}
    require(len(rows)==len(lookup),"Complete estimator/fold/time summary support required")
    seen = set()
    for row in rows:
        identity = key(row)
        require(identity in lookup and identity not in seen,"Duplicate/unknown estimator/fold/time summary")
        seen.add(identity)
        for field in fields:
            value = lookup[identity][field]
            if value is None:
                require(row[field].strip()=="",f"Undefined {field} must be blank")
            elif isinstance(value,str):
                require(row[field]==value,f"Wrong {field}")
            elif isinstance(value,int):
                require(integer(row[field])==value,f"Wrong recomputed {field}")
            else:
                close(row[field],value,1e-10 if field=="time_s" else 1e-6,0,field)
                if field in ("accuracy","pooled_accuracy"):
                    require(0<=number(row[field])<=1,"Accuracy outside [0,1]")


def validate_metadata(actual,reference):
    expected = reference["metadata"]
    for key in ("status","source_manifest_sha256","method_contract_sha256"):
        require(key in actual and actual[key]==expected[key],f"Wrong metadata {key}")
    for field in ("source_metadata","support_metadata"):
        require(field in actual,f"Missing required {field}")
        match(actual[field],expected[field],field,atol=1e-10,rtol=1e-12)
    for parent,key in (("source_metadata","source_event_code_counts"),("support_metadata","retained_event_code_counts")):
        match(actual[parent][key],expected[parent][key],key,closed=True)
    versions = actual.get("software_versions")
    require(isinstance(versions,dict) and versions and all(isinstance(k,str) and k.strip() and isinstance(v,str) and v.strip() for k,v in versions.items()),"Actual nonempty software versions required")
    diagnostic = actual.get("fitting_diagnostics")
    require(isinstance(diagnostic,dict) and {"n_models","all_converged","max_mean_gradient_inf","warnings"}<=set(diagnostic),"Missing fitting diagnostics")
    require(integer(diagnostic["n_models"])==5+5*len(reference["analysis_offsets"]),"Wrong number of required model fits")
    require(diagnostic["all_converged"] is True,"Every required model must satisfy convergence gate")
    gradient = number(diagnostic["max_mean_gradient_inf"])
    require(0<=gradient<=1e-9,"Public mean-gradient convergence criterion not met")
    warnings = diagnostic["warnings"]
    require(isinstance(warnings,list),"Warnings must be a list")
    for warning in warnings:
        require(isinstance(warning,(str,dict)),"Invalid warning record")
        text = warning if isinstance(warning,str) else json.dumps(warning,allow_nan=False)
        require("convergencewarning" not in text.lower(),"Convergence warning contradicts successful fit")


def validate_output_directory(output,reference):
    output = Path(output)
    validate_source(csv_load(output/"source_epochs.csv",SOURCE_FIELDS),reference)
    predictions = validate_predictions(csv_load(output/"oof_predictions.csv",PREDICTION_FIELDS),reference)
    folds,times,result = summaries(reference,predictions)
    validate_aggregate_rows(csv_load(output/"per_fold.csv",FOLD_FIELDS),folds,FOLD_FIELDS,("estimator","time_index","fold"))
    validate_aggregate_rows(csv_load(output/"decoding_timecourse.csv",TIME_FIELDS),times,TIME_FIELDS,("time_index",))
    actual = json_load(output/"decoding_results.json")
    match(actual,result,"results",atol=1e-6)
    for field in ("accuracy","pooled_oof_accuracy"):
        require(0<=number(actual[field])<=1,"Headline accuracy outside [0,1]")
    validate_metadata(json_load(output/"run_metadata.json"),reference)
    require((output/"findings.md").is_file() and (output/"findings.md").read_text().strip(),"Nonempty findings required")
