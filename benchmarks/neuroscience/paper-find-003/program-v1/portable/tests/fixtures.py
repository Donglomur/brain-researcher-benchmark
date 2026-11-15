"""Explicitly invented numbers; no observations or fitted study answers."""
import copy
from numeric import envelope, scalar

def fixture():
    public={"schema_version":1,"task_id":"PAPER-FIND-003",
            "raw_filename":"dd_ripple_during_learning_raw.csv",
            "input_raw_bytes":100,"input_raw_sha256":"a"*64,"raw_rows":7,
            "preprocessing_spec_sha256":"b"*64,"derived_wide_sha256":"c"*64,
            "max_wide_row_id":8082}
    phases={}
    for i,phase in enumerate(scalar.PHASES):
        phases[phase]={"status":"completed","convergence_ok":True,
            "conditional_audit_status":"conditional_REML_algebra_passed",
            "REML":True,"weights":"unit","offset":"zero","col_dropped":[],
            "fixed_names":list(scalar.NAMES),"beta":[1.0+i,0.2,0.3,0.4],
            "vcov":[[1.0 if j==k else 0.0 for j in range(4)] for k in range(4)],
            "variance_by_role":{"subject":0.1,"nested_contact":0.2,"residual":0.3},
            "n":2,"subject_levels":["invented-a","invented-b"],
            "nested_contact_levels":["invented-a/x","invented-b/y"],
            "row_ids":[1,2],"reml_criterion":20.0+i}
    preprocessing={"phase_source_row_ids":{"stimulus":[2,3],"feedback":[4,5],"interval":[6,7]},
                   "source99_excluded_row_ids":[1]}
    reference={"schema_version":1,"task_id":"PAPER-FIND-003","identity":public,
               "preprocessing":preprocessing,"raw_row_to_wide":[None,1,2,1,2,1,2],
               "models":{"candidate_id":"PAPER-FIND-003","phases":phases}}
    model=scalar.project_reference(reference["models"],envelope.scalar_public(public))
    submitted={"schema_version":1,"task_id":"PAPER-FIND-003","mode":"long_input_reconstruction",
        **{k:public[k] for k in ("input_raw_sha256","preprocessing_spec_sha256","derived_wide_sha256")},
        "submission_status":"complete","preprocessing":copy.deepcopy(preprocessing),
        "model_artifact":model}
    return public,reference,submitted

def abstention(submitted):
    value=copy.deepcopy(submitted);value["submission_status"]="abstained";value["preprocessing"]=None
    value["model_artifact"]["submission_status"]="abstained"
    for row in value["model_artifact"]["models"]:
        row.update(status="abstained",reason="Invented control abstention",fit=None)
    return value

