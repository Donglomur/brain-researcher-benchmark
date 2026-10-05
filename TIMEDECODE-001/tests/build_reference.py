"""Third original-source route: explicit epochs, custom scaling, SciPy trust-exact.

MNE is used only for FIF/event reading. No oracle/checker numerical imports.
Source analysis runs only under the separately approved scientific/resource gate.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path,PurePosixPath
import platform
import warnings
import numpy as np
import scipy
from scipy.optimize import minimize
from scipy.special import expit
import prediction_contract as q
import proof_of_work as proof


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_path(path):
    path = Path(path).absolute()
    q.require(not any(item.is_symlink() for item in (path,*path.parents)),"Source path/ancestor is a symlink")


def validate_destinations(output,report):
    output,report = Path(output),Path(report)
    for path in (output,report):
        safe_path(path)
        q.require(not path.exists(),"Refuse to overwrite scientific evidence")
    q.require(output.resolve()!=report.resolve(),"Bank and report destinations must differ")
    q.require(output.resolve() not in report.resolve().parents and report.resolve() not in output.resolve().parents,
        "Bank/report file destinations cannot contain one another")


def load_sources(source_dir,method_path):
    root,method_path = Path(source_dir),Path(method_path)
    safe_path(root)
    safe_path(method_path)
    q.require(sha256(method_path)==proof.METHOD_SHA256,"Frozen method checksum mismatch")
    manifest_path = root/"source_manifest.json"
    safe_path(manifest_path)
    q.require(sha256(manifest_path)==proof.SOURCE_MANIFEST_SHA256,"Frozen source manifest checksum mismatch")
    method,manifest = q.json_load(method_path),q.json_load(manifest_path)
    names,roles = {"source_manifest.json"},{}
    for row in manifest["files"]:
        name = row["path"]
        pure = PurePosixPath(name)
        q.require(not pure.is_absolute() and ".." not in pure.parts and str(pure)==name and name not in names,"Invalid/duplicate source member")
        names.add(name)
        path = root/name
        safe_path(path)
        q.require(path.is_file() and path.stat().st_size==q.integer(row["size_bytes"]) and sha256(path)==row["sha256"],"Original source file identity mismatch")
        q.require(row["role"] not in roles,"Duplicate source role")
        roles[row["role"]] = path
    q.require(set(roles)=={"raw","events","version"},"Exact three source roles required")
    actual = set()
    for path in root.rglob("*"):
        q.require(not path.is_symlink(),"Unexpected staged source symlink")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    q.require(actual==names,"Unexpected/missing source member")
    return method,manifest,roles


def trial_folds(labels):
    """Independent reproduction of the public shuffled SKF class allocation."""
    labels = np.asarray(labels)
    q.require(labels.ndim==1 and set(labels.tolist())=={0,1} and min(np.bincount(labels,minlength=2))>=5,"Five folds require both classes and at least five trials each")
    _,first,inverse = np.unique(labels,return_index=True,return_inverse=True)
    _,appearance = np.unique(first,return_inverse=True)
    encoded = appearance[inverse]
    ordered = np.sort(encoded)
    allocation = np.array([np.bincount(ordered[index::5],minlength=2) for index in range(5)])
    rng = np.random.RandomState(42)
    result = np.empty(len(labels),dtype=np.int64)
    for category in range(2):
        membership = np.repeat(np.arange(1,6),allocation[:,category])
        rng.shuffle(membership)
        result[encoded==category] = membership
    return result


def overlap_counts(samples,epoch_offsets,analysis_offsets,baseline_offsets):
    output = {}
    for name,left,right in (("full_epoch_overlap_pairs",epoch_offsets,epoch_offsets),
            ("analysis_overlap_pairs",analysis_offsets,analysis_offsets),
            ("prior_analysis_next_baseline_overlap_pairs",analysis_offsets,baseline_offsets)):
        count = 0
        for earlier,later in zip(samples,samples[1:]):
            if max(int(earlier+left[0]),int(later+right[0]))<=min(int(earlier+left[-1]),int(later+right[-1])):
                count += 1
        output[name] = count
    return output


def explicit_epochs(data,events,first_samp,sfreq,names):
    """Slice original sample positions; no mne.Epochs/rejection implementation."""
    data = np.asarray(data,dtype=np.float64)
    events = np.asarray(events,dtype=np.int64)
    q.require(data.ndim==2 and np.isfinite(data).all(),"Nonfinite selected original signal")
    q.require(events.ndim==2 and events.shape[1]==3 and np.all(np.diff(events[:,0])>0),"Invalid original chronological events")
    offsets = np.arange(round(-.2*sfreq),round(.5*sfreq)+1,dtype=np.int64)
    baseline = offsets<=0
    selected = (offsets/sfreq>=.05)&(offsets/sfreq<=.45)
    rows,retained,epochs,maximizers = [],[],[],{}
    for index,(sample,previous,code) in enumerate(events):
        row = dict(source_event_index=index,event_sample=int(sample),previous_value=int(previous),event_code=int(code),
            modality=None,retained=0,drop_reason="not_target",trial_id=None,max_ptp_T_per_m=None,max_ptp_channel=None)
        if code in (1,2,3,4):
            row["modality"] = int(code in (3,4))
            start,stop = int(sample-first_samp+offsets[0]),int(sample-first_samp+offsets[-1]+1)
            if start<0 or stop>data.shape[1]:
                row["drop_reason"] = "out_of_bounds"
            else:
                epoch = data[:,start:stop].copy()
                epoch -= epoch[:,baseline].mean(axis=1,keepdims=True)
                ptp = epoch.max(axis=1)-epoch.min(axis=1)
                maximum = float(ptp.max())
                ties = [names[i] for i in np.flatnonzero(ptp==maximum)]
                maximizers[str(index)] = ties
                row.update(max_ptp_T_per_m=maximum,max_ptp_channel=ties[0])
                if maximum>4e-10:
                    row["drop_reason"] = "amplitude"
                else:
                    row.update(retained=1,drop_reason="retained",trial_id=len(retained))
                    retained.append(index)
                    epochs.append(epoch)
        rows.append(row)
    q.require(epochs,"No retained task epochs")
    full = np.array(epochs,dtype=np.float64)
    retained = np.array(retained,dtype=np.int64)
    labels = np.isin(events[retained,2],[3,4]).astype(np.int64)
    return dict(events=events,retained_event_indices=retained,labels=labels,folds=trial_folds(labels),
        features=np.ascontiguousarray(full[:,:,selected]),full_epochs=full,analysis_offsets=offsets[selected],epoch_offsets=offsets,
        channel_names=np.array(names),source_rows=rows,max_ptp_channels=maximizers,times=offsets[selected]/sfreq)


def source_recompute(source_dir,method_path):
    import mne
    method,manifest,paths = load_sources(source_dir,method_path)
    raw = mne.io.read_raw_fif(paths["raw"],preload=False,verbose="warning")
    try:
        events = mne.read_events(paths["events"],verbose="warning")
        picks = [i for i in range(len(raw.ch_names)) if mne.channel_type(raw.info,i)=="grad" and raw.ch_names[i] not in raw.info["bads"]]
        names = [raw.ch_names[i] for i in picks]
        q.require(len(names)==203 and len(raw.annotations)==0,"Unexpected source sensor/annotation support")
        q.require(not any(set(projector["data"]["col_names"])&set(names) for projector in raw.info["projs"]),"Unexpected source grad projector; no silent new projection")
        reference = explicit_epochs(raw.get_data(picks=picks),events,int(raw.first_samp),float(raw.info["sfreq"]),names)
        source_meta = dict(sfreq_hz=float(raw.info["sfreq"]),highpass_hz=float(raw.info["highpass"]),lowpass_hz=float(raw.info["lowpass"]),
            first_samp=int(raw.first_samp),last_samp=int(raw.last_samp),n_times=int(raw.n_times),n_source_channels=len(raw.ch_names),
            selected_grad_names=names,source_bads=list(raw.info["bads"]),source_projector_descriptions=[p["desc"] for p in raw.info["projs"]],
            grad_projector_rank=0,annotation_count=0,source_event_code_counts={str(int(code)):int(count) for code,count in Counter(events[:,2]).items()})
        candidates = np.flatnonzero(np.isin(events[:,2],[1,2,3,4]))
        retained = reference["retained_event_indices"]
        offsets,analysis = reference["epoch_offsets"],reference["analysis_offsets"]
        support = dict(n_source_events=len(events),n_candidate_trials=len(candidates),n_retained_trials=len(retained),n_rejected_trials=len(candidates)-len(retained),
            retained_event_code_counts={str(code):int(np.sum(events[retained,2]==code)) for code in (1,2,3,4)},
            epoch_offsets=offsets.tolist(),analysis_offsets=analysis.tolist(),baseline_offsets=offsets[offsets<=0].tolist())
        for prefix,indices in (("candidate",candidates),("retained",retained)):
            support.update({prefix+"_"+key:value for key,value in overlap_counts(events[indices,0],offsets,analysis,offsets[offsets<=0]).items()})
        reference["metadata"] = dict(status="ok",source_manifest_sha256=proof.SOURCE_MANIFEST_SHA256,method_contract_sha256=proof.METHOD_SHA256,
            source_metadata=source_meta,support_metadata=support,software_versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,mne=mne.__version__))
        reference["provenance"] = dict(builder_id=proof.BUILDER_ID,source_manifest_sha256=proof.SOURCE_MANIFEST_SHA256,
            method_contract_sha256=proof.METHOD_SHA256,source_sha256={row["path"]:row["sha256"] for row in manifest["files"]})
    finally:
        raw.close()
    return reference


def scale_training(values):
    values = np.asarray(values,dtype=np.float64)
    q.require(values.ndim==2 and len(values)>0 and np.isfinite(values).all(),"Invalid training observations")
    mean = values.mean(axis=0)
    centered = values-mean
    correction = centered.sum(axis=0)
    variance = (np.sum(centered*centered,axis=0)-correction*correction/len(values))/len(values)
    q.require(np.isfinite(variance).all() and np.all(variance>=0),"Invalid population variance")
    eps = np.finfo(np.float64).eps
    constant = variance<=len(values)*eps*variance+(len(values)*mean*eps)**2
    scale = np.sqrt(variance)
    scale[constant] = 1.
    return mean,scale,centered/scale


def objective(parameter,design,labels):
    z = design@parameter[:-1]+parameter[-1]
    # Positive and negative classes evaluated separately avoid loss cancellation.
    signs = 1-2*labels
    value = float(np.sum(np.logaddexp(0,signs*z))+.5*np.dot(parameter[:-1],parameter[:-1]))
    probability = expit(z)
    residual = probability-labels
    gradient = np.r_[design.T@residual+parameter[:-1],residual.sum()]
    weight = probability*(1-probability)
    weighted = design*weight[:,None]
    hessian = np.empty((len(parameter),len(parameter)),dtype=float)
    hessian[:-1,:-1] = design.T@weighted+np.eye(design.shape[1])
    hessian[:-1,-1] = weighted.sum(axis=0)
    hessian[-1,:-1] = hessian[:-1,-1]
    hessian[-1,-1] = weight.sum()
    return value,gradient,hessian


def independent_fit(train,labels,test):
    mean,scale,standardized = scale_training(train)
    labels = np.asarray(labels,dtype=np.float64)
    q.require(labels.shape==(len(train),) and set(labels.tolist())=={0.,1.},"Binary training labels required")
    cache = {}
    def evaluate(parameter):
        if "parameter" not in cache or not np.array_equal(parameter,cache["parameter"]):
            cache["parameter"] = parameter.copy()
            cache["value"] = objective(parameter,standardized,labels)
        return cache["value"]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = minimize(lambda p:evaluate(p)[0],np.zeros(train.shape[1]+1),method="trust-exact",
            jac=lambda p:evaluate(p)[1],hess=lambda p:evaluate(p)[2],options=dict(gtol=len(train)*1e-11,maxiter=500))
    warning_rows = [dict(category=w.category.__name__,message=str(w.message)) for w in caught]
    q.require(not warning_rows,"Independent solver warning requires explicit review")
    _,gradient,_ = evaluate(result.x)
    norm = float(np.max(np.abs(gradient))/len(train))
    q.require(np.isfinite(result.x).all() and math_finite(norm) and norm<=1e-9,"Independent solver did not satisfy public mean-gradient gate")
    score = ((test-mean)/scale)@result.x[:-1]+result.x[-1]
    q.require(np.isfinite(score).all(),"Nonfinite independent decision")
    return score,dict(scaler_mean=mean,scaler_scale=scale,coef=result.x[:-1],intercept=float(result.x[-1]),gradient_inf=norm,
        optimizer_status=int(result.status),optimizer_success=bool(result.success),optimizer_message=str(result.message),iterations=int(result.nit),warnings=warning_rows)


def math_finite(value):
    return bool(np.isfinite(value))


def fit_all(reference,pilot=False):
    features,labels,folds = reference["features"],reference["labels"],reference["folds"]
    n,c,t = features.shape
    scores = {name:np.full((n,t),np.nan) for name in q.ESTIMATORS}
    specs = [("pooled",-1,fold) for fold in range(1,6)]+[("per_time",ti,fold) for ti in range(t) for fold in range(1,6)]
    if pilot:
        specs = [("pooled",-1,1)]+[("per_time",ti,1) for ti in (0,29,59)]
    models = []
    for name,ti,fold in specs:
        train,test = folds!=fold,folds==fold
        X_train = features[train].transpose(0,2,1).reshape(-1,c) if name=="pooled" else features[train,:,ti]
        X_test = features[test].transpose(0,2,1).reshape(-1,c) if name=="pooled" else features[test,:,ti]
        y_train = np.repeat(labels[train],t) if name=="pooled" else labels[train]
        score,model = independent_fit(X_train,y_train,X_test)
        model.update(model_estimator=name,model_time_index=ti,model_fold=fold)
        models.append(model)
        if name=="pooled":
            scores[name][test] = score.reshape(test.sum(),t)
        else:
            scores[name][test,ti] = score
        print(json.dumps(dict(estimator=name,time_index=ti,fold=fold,mean_gradient_inf=model["gradient_inf"],optimizer_status=model["optimizer_status"])),flush=True)
    reference.update({name+"_scores":value for name,value in scores.items()})
    for key in ("model_estimator","model_time_index","model_fold","scaler_mean","scaler_scale","coef","intercept","gradient_inf"):
        reference[key] = np.array([row[key] for row in models])
    reference["metadata"]["status"] = "resource_pilot" if pilot else "ok"
    reference["metadata"]["fitting_diagnostics"] = dict(n_models=len(models),all_converged=True,
        max_mean_gradient_inf=max(row["gradient_inf"] for row in models),warnings=[warning for row in models for warning in row["warnings"]])
    reference["optimizer_diagnostics"] = [{key:row[key] for key in ("model_estimator","model_time_index","model_fold","optimizer_status","optimizer_success","optimizer_message","iterations")} for row in models]
    return reference


def save_bank(path,reference):
    safe_path(path)
    q.require(not Path(path).exists(),"Refuse to overwrite existing bank")
    metadata = {key:reference[key] for key in ("source_rows","max_ptp_channels","metadata","provenance","optimizer_diagnostics")}
    with Path(path).open("xb") as stream:
        np.savez_compressed(stream,**{key:reference[key] for key in proof.ARRAYS},reference_json=np.array(json.dumps(metadata,allow_nan=False)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir",type=Path,default=Path("/app/data/timedecode"))
    parser.add_argument("--method-contract",type=Path,default=Path("/app/method_contract.json"))
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    parser.add_argument("--oracle-output",type=Path)
    parser.add_argument("--pilot",action="store_true")
    args = parser.parse_args()
    validate_destinations(args.output,args.report)
    reference = fit_all(source_recompute(args.source_dir,args.method_contract),args.pilot)
    if not args.pilot:
        q.require(args.oracle_output is not None,"Full reference requires validation against independently generated oracle output")
        q.validate_output_directory(args.oracle_output,reference)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    save_bank(args.output,reference)
    if not args.pilot:
        checked = proof.load_reference(args.output)
        q.validate_output_directory(args.oracle_output,checked)
    report = dict(status="resource_pilot" if args.pilot else "ok",builder_id=proof.BUILDER_ID,
        source_manifest_sha256=proof.SOURCE_MANIFEST_SHA256,method_contract_sha256=proof.METHOD_SHA256,
        reference_sha256=sha256(args.output),n_trials=len(reference["labels"]),n_times=len(reference["analysis_offsets"]),
        n_models=len(reference["model_fold"]),max_mean_gradient_inf=reference["metadata"]["fitting_diagnostics"]["max_mean_gradient_inf"],
        optimizer_diagnostics=reference["optimizer_diagnostics"],source_route="MNE low-level readers; independent explicit slicing/baseline/PTP, SKF allocation, custom scaling, analytic logistic derivatives and SciPy trust-exact")
    args.report.parent.mkdir(parents=True,exist_ok=True)
    with args.report.open("x") as stream:
        json.dump(report,stream,indent=2,allow_nan=False)


if __name__=="__main__":
    main()
