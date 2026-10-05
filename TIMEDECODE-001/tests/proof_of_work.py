"""Primitive source-recomputed reference; historical scalar-only banks fail closed."""
import json
from pathlib import Path
import numpy as np
from prediction_contract import require,match

METHOD_SHA256 = "b4ff29fb1dcf767d6362fb944081fc7200cd77039ebacf83ca7398f761f1da73"
SOURCE_MANIFEST_SHA256 = "533bc28bbcc1e8fe53880504b75756ee4035ecb423e3be84c5fddf1660b779f6"
BUILDER_ID = "original-fif-explicit-epochs-trust-exact-v2"
ARRAYS = ("events","retained_event_indices","labels","folds","analysis_offsets","epoch_offsets","channel_names",
    "features","pooled_scores","per_time_scores","model_estimator","model_time_index","model_fold",
    "scaler_mean","scaler_scale","coef","intercept","gradient_inf")


def load_reference(path=Path(__file__).with_name("reference.npz")):
    with np.load(path,allow_pickle=False) as archive:
        require(set(archive.files)==set(ARRAYS)|{"reference_json"},"Legacy/unrecognized bank; genuine source-only regeneration required")
        scalar = archive["reference_json"]
        require(scalar.shape==() and scalar.dtype.kind in "US","Invalid primitive reference JSON")
        reference = json.loads(str(scalar),parse_constant=lambda token: (_ for _ in ()).throw(AssertionError("Nonfinite bank JSON")))
        require(isinstance(reference,dict),"Reference metadata must be an object")
        reference.update({key:np.array(archive[key]) for key in ARRAYS})
    provenance = reference["provenance"]
    match(provenance,dict(builder_id=BUILDER_ID,source_manifest_sha256=SOURCE_MANIFEST_SHA256,method_contract_sha256=METHOD_SHA256),"reference provenance")
    meta = reference["metadata"]
    require(meta["status"]=="ok" and meta["source_manifest_sha256"]==SOURCE_MANIFEST_SHA256 and meta["method_contract_sha256"]==METHOD_SHA256,"Wrong reference identity/full-run state")
    n,t,c = len(reference["labels"]),len(reference["analysis_offsets"]),len(reference["channel_names"])
    require(reference["events"].shape==(319,3) and reference["events"].dtype.kind in "iu","Complete original event table required")
    require(t==60 and c==203 and 10<=n<=288,"Reference source support invalid")
    for name in ("retained_event_indices","labels","folds","analysis_offsets","epoch_offsets","model_time_index","model_fold"):
        require(reference[name].dtype.kind in "iu",f"Invalid integer reference {name}")
    require(reference["labels"].shape==reference["folds"].shape==reference["retained_event_indices"].shape==(n,),"Invalid trial reference axes")
    require(np.all(np.isin(reference["labels"],[0,1])) and set(reference["folds"])==set(range(1,6)),"Invalid reference labels/folds")
    require(np.array_equal(reference["epoch_offsets"],np.arange(-30,76)) and np.array_equal(reference["analysis_offsets"],np.arange(8,68)),"Wrong native source time grid")
    indices = reference["retained_event_indices"]
    require(np.all((indices>=0)&(indices<319)) and np.all(np.diff(indices)>0),"Wrong retained original event order")
    source_labels = np.array([0 if code in (1,2) else 1 if code in (3,4) else -1 for code in reference["events"][indices,2]])
    require(np.array_equal(source_labels,reference["labels"]),"Reference labels not source-derived")
    require(reference["features"].shape==(n,c,t) and np.isfinite(reference["features"]).all(),"Invalid source feature tensor")
    m = 5+5*t
    require(reference["scaler_mean"].shape==reference["scaler_scale"].shape==reference["coef"].shape==(m,c),"Invalid full model state")
    require(all(reference[key].shape==(m,) for key in ("intercept","gradient_inf","model_estimator","model_time_index","model_fold")),"Invalid model axes")
    require(np.all(reference["scaler_scale"]>0) and np.all((reference["gradient_inf"]>=0)&(reference["gradient_inf"]<=1e-9)),"Invalid scaler/convergence reference")
    for key in ("scaler_mean","scaler_scale","coef","intercept","gradient_inf"):
        require(np.isfinite(reference[key]).all(),"Nonfinite model reference")
    keys = set()
    for row,(estimator,ti,fold) in enumerate(zip(reference["model_estimator"],reference["model_time_index"],reference["model_fold"])):
        estimator = str(estimator)
        key = (estimator,int(ti),int(fold))
        require(key not in keys,"Duplicate reference model")
        keys.add(key)
        test = reference["folds"]==fold
        values = reference["features"][test].transpose(0,2,1).reshape(-1,c) if estimator=="pooled" else reference["features"][test,:,ti]
        score = ((values-reference["scaler_mean"][row])/reference["scaler_scale"][row])@reference["coef"][row]+reference["intercept"][row]
        expected = reference[estimator+"_scores"][test].ravel() if estimator=="pooled" else reference[estimator+"_scores"][test,ti]
        require(np.allclose(score,expected,atol=1e-10,rtol=1e-10),"Bank score/model/source algebra mismatch")
    require(keys=={("pooled",-1,f) for f in range(1,6)}|{("per_time",ti,f) for ti in range(t) for f in range(1,6)},"Incomplete reference models")
    for name in ("pooled_scores","per_time_scores"):
        require(reference[name].shape==(n,t) and np.isfinite(reference[name]).all(),"Incomplete source OOF scores")
    reference["times"] = reference["analysis_offsets"]/meta["source_metadata"]["sfreq_hz"]
    return reference
