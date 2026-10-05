"""Small synthetic mechanics only; these fixtures are not source calibration."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from scipy.optimize._numdiff import approx_derivative
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
import build_reference as builder
import prediction_contract as q
import proof_of_work as proof


def write_csv(path,fields,rows):
    with path.open("w",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def toy_reference(n=12,t=3):
    labels = np.arange(n)%2
    folds = builder.trial_folds(labels)
    source = [dict(source_event_index=i,event_sample=100+100*i,previous_value=0,event_code=1+2*int(labels[i]),
        modality=int(labels[i]),retained=1,drop_reason="retained",trial_id=i,max_ptp_T_per_m=1e-11,max_ptp_channel="g0") for i in range(n)]
    metadata = dict(status="ok",source_manifest_sha256=proof.SOURCE_MANIFEST_SHA256,method_contract_sha256=proof.METHOD_SHA256,
        source_metadata=dict(sfreq_hz=100.,source_event_code_counts={"1":n//2,"3":n//2}),
        support_metadata=dict(retained_event_code_counts={"1":n//2,"2":0,"3":n//2,"4":0}),
        software_versions={"mechanics_fixture":"not-scientific-evidence"},
        fitting_diagnostics=dict(n_models=5+5*t,all_converged=True,max_mean_gradient_inf=0.,warnings=[]))
    return dict(source_rows=source,retained_event_indices=np.arange(n),labels=labels,folds=folds,
        analysis_offsets=np.arange(5,5+t),times=np.arange(5,5+t)/100,channel_names=np.array(["g0","g1"]),
        pooled_scores=np.ones((n,t)),per_time_scores=np.ones((n,t)),metadata=metadata)


def prediction_rows(reference):
    return [dict(estimator=name,source_event_index=int(reference["retained_event_indices"][trial]),trial_id=trial,time_index=ti,
        sample_offset=int(reference["analysis_offsets"][ti]),time_s=float(reference["times"][ti]),fold=int(reference["folds"][trial]),
        true_class=int(reference["labels"][trial]),predicted_class=int(reference[name+"_scores"][trial,ti]>0),
        decision_score=float(reference[name+"_scores"][trial,ti])) for name in q.ESTIMATORS for trial in range(len(reference["labels"])) for ti in range(len(reference["times"]))]


def write_toy_output(path,reference):
    predictions = {name:(reference[name+"_scores"]>0).astype(int) for name in q.ESTIMATORS}
    folds,times,result = q.summaries(reference,predictions)
    write_csv(path/"source_epochs.csv",q.SOURCE_FIELDS,reference["source_rows"])
    write_csv(path/"oof_predictions.csv",q.PREDICTION_FIELDS,prediction_rows(reference))
    write_csv(path/"per_fold.csv",q.FOLD_FIELDS,folds)
    write_csv(path/"decoding_timecourse.csv",q.TIME_FIELDS,times)
    (path/"decoding_results.json").write_text(json.dumps(result))
    (path/"run_metadata.json").write_text(json.dumps(reference["metadata"]))
    (path/"findings.md").write_text("A synthetic arithmetic fixture, not an experiment.")


@pytest.mark.parametrize("value",[1,1.,"1","001","1.0","1e0"," 1 "])
def test_valid_integer_notation(value):
    assert q.integer(value)==1


@pytest.mark.parametrize("value",[True,False,"true","NaN","inf","1.1",None,[],{},"trial1"])
def test_invalid_integer_identity(value):
    with pytest.raises(AssertionError):
        q.integer(value)


@pytest.mark.parametrize("value",[True,"NaN","inf",float("nan"),float("inf"),None,[],{},""])
def test_invalid_numeric_measurement(value):
    with pytest.raises(AssertionError):
        q.number(value)


@pytest.mark.parametrize("text",['{"a":NaN}','{"a":Infinity}','{"a":1,"a":2}'])
def test_malformed_json(tmp_path,text):
    path = tmp_path/"bad.json"
    path.write_text(text)
    with pytest.raises(AssertionError):
        q.json_load(path)


@pytest.mark.parametrize("text",["a,a\n1,1\n","a,b\n1\n","a,b\n1,2,3\n"])
def test_malformed_csv(tmp_path,text):
    path = tmp_path/"bad.csv"
    path.write_text(text)
    with pytest.raises(AssertionError):
        q.csv_load(path,("a","b"))


@pytest.mark.parametrize("first",[0,1])
@pytest.mark.parametrize("n",[10,12,31,100])
def test_independent_trial_split_matches_declared_sklearn(first,n):
    labels = (np.arange(n)+first)%2
    expected = np.zeros(n,int)
    for fold,(_,test) in enumerate(StratifiedKFold(5,shuffle=True,random_state=42).split(np.zeros((n,1)),labels),1):
        expected[test] = fold
    np.testing.assert_array_equal(builder.trial_folds(labels),expected)


@pytest.mark.parametrize("labels",[np.zeros(10,int),np.array([0]*10+[1]*4)])
def test_split_feasibility(labels):
    with pytest.raises(AssertionError):
        builder.trial_folds(labels)


def test_epoch_clock_baseline_and_amplitude_boundaries():
    data = np.zeros((2,1400))
    events = np.array([[100+100*i,0,1+2*(i%2)] for i in range(12)])
    data[0,101] = 4e-10
    output = builder.explicit_epochs(data,events,0,100.,["g0","g1"])
    assert len(output["labels"])==12 and output["source_rows"][0]["retained"]==1
    np.testing.assert_array_equal(output["analysis_offsets"],np.arange(5,46))
    assert np.max(np.abs(output["full_epochs"][:,:,:21].mean(axis=2)))==0
    data[0,101] = 4e-10+1e-20
    output = builder.explicit_epochs(data,events,0,100.,["g0","g1"])
    assert len(output["labels"])==11 and output["source_rows"][0]["drop_reason"]=="amplitude"


def test_original_event_identity_nontarget_and_out_of_bounds():
    data = np.zeros((2,1500))
    events = np.array([[1,0,1]]+[[100+100*i,0,1+2*(i%2)] for i in range(12)]+[[1450,0,5]])
    output = builder.explicit_epochs(data,events,0,100.,["g0","g1"])
    assert output["source_rows"][0]["drop_reason"]=="out_of_bounds"
    assert output["source_rows"][-1]["drop_reason"]=="not_target"
    assert output["source_rows"][-1]["modality"] is None
    np.testing.assert_array_equal(output["retained_event_indices"],np.arange(1,13))


def test_overlap_uses_original_samples_and_inclusive_boundaries():
    observed = builder.overlap_counts(np.array([100,106]),np.arange(-2,5),np.arange(1,5),np.arange(-2,1))
    assert observed==dict(full_epoch_overlap_pairs=1,analysis_overlap_pairs=0,prior_analysis_next_baseline_overlap_pairs=1)


def test_scaling_matches_public_population_variance_and_constant_rule():
    X = np.random.RandomState(3).normal(size=(25,4))
    X[:,0] = 2
    X[:,1] *= 1e-12
    mean,scale,values = builder.scale_training(X)
    expected = StandardScaler().fit(X)
    np.testing.assert_allclose(mean,expected.mean_,atol=1e-15,rtol=1e-14)
    np.testing.assert_allclose(scale,expected.scale_,atol=1e-25,rtol=1e-13)
    np.testing.assert_allclose(values,expected.transform(X),atol=1e-13,rtol=1e-13)
    assert scale[0]==1


def test_logistic_objective_gradient_and_hessian_are_independent_derivatives():
    rng = np.random.RandomState(3)
    X,y,p = rng.normal(size=(30,4)),np.arange(30)%2,rng.normal(size=5)
    value,gradient,hessian = builder.objective(p,X,y)
    numeric_gradient = approx_derivative(lambda z:builder.objective(z,X,y)[0],p).ravel()
    numeric_hessian = approx_derivative(lambda z:builder.objective(z,X,y)[1],p)
    np.testing.assert_allclose(gradient,numeric_gradient,atol=1e-7,rtol=1e-7)
    np.testing.assert_allclose(hessian,numeric_hessian,atol=1e-7,rtol=1e-7)
    assert np.isfinite(value) and np.all(np.linalg.eigvalsh(hessian)>0)


def test_independent_trust_exact_agrees_with_public_objective():
    rng = np.random.RandomState(7)
    X = rng.normal(size=(40,5))
    y = (X[:,0]+rng.normal(size=40)>.1).astype(int)
    test = rng.normal(size=(12,5))
    score,receipt = builder.independent_fit(X,y,test)
    scaler = StandardScaler().fit(X)
    estimator = LogisticRegression(solver="newton-cholesky",C=1,l1_ratio=0,tol=1e-10,max_iter=100).fit(scaler.transform(X),y)
    np.testing.assert_allclose(score,estimator.decision_function(scaler.transform(test)),atol=1e-7,rtol=1e-7)
    assert receipt["gradient_inf"]<=1e-9


def test_equal_or_below_chance_outputs_have_no_shape_or_performance_gate(tmp_path):
    reference = toy_reference()
    reference["pooled_scores"] = np.repeat((1-2*reference["labels"])[:,None],3,axis=1).astype(float)
    reference["per_time_scores"] = reference["pooled_scores"].copy()
    write_toy_output(tmp_path,reference)
    q.validate_output_directory(tmp_path,reference)
    assert json.loads((tmp_path/"decoding_results.json").read_text())["accuracy"]==0


def test_near_zero_equivalent_score_can_change_class_but_must_follow_own_sign():
    reference = toy_reference()
    reference["pooled_scores"][0,0] = 1e-7
    rows = prediction_rows(reference)
    rows[0].update(decision_score=-1e-7,predicted_class=0)
    output = q.validate_predictions(rows,reference)
    assert output["pooled"][0,0]==0
    rows[0]["predicted_class"] = 1
    with pytest.raises(AssertionError,match="signed score"):
        q.validate_predictions(rows,reference)


@pytest.mark.parametrize("field,value",[("source_event_index",999),("sample_offset",999),("time_s",999),
    ("fold",99),("true_class",9),("predicted_class",9),("decision_score",999),("estimator","invented")])
def test_prediction_source_identity_and_scores(field,value):
    reference = toy_reference()
    rows = prediction_rows(reference)
    rows[0][field] = value
    with pytest.raises(AssertionError):
        q.validate_predictions(rows,reference)


def test_row_order_is_not_fold_identity(tmp_path):
    reference = toy_reference()
    write_toy_output(tmp_path,reference)
    for name,fields in (("source_epochs.csv",q.SOURCE_FIELDS),("oof_predictions.csv",q.PREDICTION_FIELDS),
            ("per_fold.csv",q.FOLD_FIELDS),("decoding_timecourse.csv",q.TIME_FIELDS)):
        rows = q.csv_load(tmp_path/name,fields)
        write_csv(tmp_path/name,list(reversed(fields)),list(reversed(rows)))
    q.validate_output_directory(tmp_path,reference)


def test_unweighted_fold_mean_is_not_pooled_accuracy():
    reference = toy_reference(n=12)
    predictions = {name:np.ones((12,3),int) for name in q.ESTIMATORS}
    predictions["pooled"][:] = reference["labels"][:,None]
    largest = max(range(1,6),key=lambda fold:int(np.sum(reference["folds"]==fold)))
    predictions["pooled"][reference["folds"]==largest] = 1-reference["labels"][reference["folds"]==largest,None]
    _,_,result = q.summaries(reference,predictions)
    assert result["accuracy"]==.8 and result["pooled_oof_accuracy"]!=.8


def test_legacy_bank_always_rejected(tmp_path):
    path = tmp_path/"obsolete.npz"
    np.savez(path,ref_fold_acc=np.ones(5),ref_stats=np.array("{}"))
    with pytest.raises(AssertionError,match="Legacy"):
        proof.load_reference(path)


def test_method_pin_fails_before_any_source_signal_read(tmp_path):
    method = tmp_path/"method.json"
    method.write_text("{}")
    with pytest.raises(AssertionError,match="method checksum"):
        builder.load_sources(tmp_path,method)


def test_public_frozen_identities_and_offline_entrypoint():
    task = Path(__file__).parents[1]
    assert hashlib.sha256((task/"environment/method_contract.json").read_bytes()).hexdigest()==proof.METHOD_SHA256
    assert hashlib.sha256((task/"environment/source_manifest.json").read_bytes()).hexdigest()==proof.SOURCE_MANIFEST_SHA256
    text = (task/"tests/test.sh").read_text()
    assert "python3 -m pytest" in text and not any(name in text for name in ("curl","apt-get","uvx"))
    source = (task/"tests/build_reference.py").read_text()
    assert "solution.compute" not in source and "check_independent" not in source


@pytest.mark.parametrize("which",["bank","report"])
def test_builder_refuses_existing_evidence(tmp_path,which):
    output,report = tmp_path/"bank.npz",tmp_path/"report.json"
    selected = output if which=="bank" else report
    selected.write_bytes(b"preserved evidence")
    with pytest.raises(AssertionError,match="overwrite"):
        builder.validate_destinations(output,report)
    assert selected.read_bytes()==b"preserved evidence"


@pytest.mark.parametrize("which",["bank","report","ancestor"])
def test_builder_refuses_dangling_and_ancestor_symlinks(tmp_path,which):
    output,report = tmp_path/"bank.npz",tmp_path/"report.json"
    if which=="ancestor":
        real = tmp_path/"real"
        real.mkdir()
        alias = tmp_path/"alias"
        alias.symlink_to(real,target_is_directory=True)
        output = alias/"bank.npz"
    else:
        (output if which=="bank" else report).symlink_to(tmp_path/"missing-target")
    with pytest.raises(AssertionError,match="symlink"):
        builder.validate_destinations(output,report)


def test_builder_output_and_report_must_differ(tmp_path):
    with pytest.raises(AssertionError,match="differ"):
        builder.validate_destinations(tmp_path/"same",tmp_path/"same")


def test_bank_publication_is_exclusive_and_preserves_existing_bytes(tmp_path):
    path = tmp_path/"bank.npz"
    path.write_bytes(b"old evidence")
    with pytest.raises(AssertionError,match="overwrite"):
        builder.save_bank(path,{})
    assert path.read_bytes()==b"old evidence"
