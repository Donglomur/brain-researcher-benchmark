"""Build a bank only from a complete source-checked production oracle receipt.

This command reopens all original EDFs and recomputes the declared preprocessing,
but does not refit classifiers. All retained epochs and all held-out decision
scores are verified from the genuine private CSP/LDA parameter receipt. The
separate independent checker audits the estimator with sampled fresh refits.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

import numpy as np

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK/"tests"))
import proof_of_work as q


def reconstruct_scores(receipt):
    """Reapply every saved CSP/LDA fold, not a second training pass."""
    x = np.asarray(receipt["X"], float)
    subjects = np.asarray(receipt["subject"])
    runs = np.asarray(receipt["run"])
    scores = np.asarray(receipt["decision_score"], float)
    assert x.ndim == 3 and x.shape[0] == len(subjects) and np.isfinite(x).all(), "invalid private epoch array"
    assert scores.ndim == 2 and scores.shape[1] == len(subjects) and np.isfinite(scores).all()
    count = len(receipt["fold_subject"])
    n_components = receipt["csp_filters"].shape[1]
    assert receipt["csp_filters"].shape == (count,n_components,x.shape[1])
    assert receipt["lda_coef"].shape == (count,n_components)
    assert receipt["lda_intercept"].shape == (count,)
    assert receipt["lda_classes"].shape == (count,2)
    assert np.array_equal(receipt["lda_classes"],np.tile([0,1],(count,1)))
    assert receipt["csp_eigenvalues"].shape == (count,n_components)
    for key in ("csp_filters","lda_coef","lda_intercept","csp_eigenvalues"):
        assert np.isfinite(receipt[key]).all(), f"nonfinite private {key}"
    rank = np.asarray(receipt["csp_rank"])
    assert rank.shape == (count,) and np.array_equal(rank,rank.astype(int))
    assert np.all((rank>=n_components)&(rank<=x.shape[1]))
    expected = {(int(s),rep,r) for s in np.unique(subjects) for rep in range(len(scores)) for r in q.RUNS}
    actual = set(); recovered = np.empty_like(scores)
    heldout = {(int(s),r):np.flatnonzero((subjects==s)&(runs==r)) for s in np.unique(subjects) for r in q.RUNS}
    for index in range(count):
        key = tuple(q.integer(receipt["fold_"+name][index],name) for name in ("subject","replicate","test_run"))
        assert key in expected and key not in actual, "missing/duplicate private fold model"
        actual.add(key); subject,rep,run=key; take=heldout[(subject,run)]
        assert len(take), "empty source held-out fold"
        projected = receipt["csp_filters"][index] @ x[take]
        power = np.mean(projected**2,axis=-1)
        assert np.isfinite(power).all() and np.all(power>0), "undefined CSP log-power"
        recovered[rep,take] = np.log(power) @ receipt["lda_coef"][index] + receipt["lda_intercept"][index]
    assert actual == expected, "incomplete private model receipt"
    assert np.isfinite(recovered).all()
    assert np.allclose(recovered,scores,atol=1e-8,rtol=1e-10), "private CSP/LDA parameters do not reconstruct OOF scores"
    return float(np.max(np.abs(recovered-scores)))


def build(output, data_dir, destination):
    spec=importlib.util.spec_from_file_location("motorimagery_oracle_authoring",TASK/"solution"/"compute.py")
    oracle=importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)
    oracle.check_software()
    with np.load(output/"analysis_arrays.npz",allow_pickle=False) as archive:
        receipt={key:archive[key] for key in archive.files}
    assert receipt["pipeline_id"].item()==q.PIPELINE_ID
    assert np.array_equal(receipt["subjects"],q.SUBJECTS) and receipt["n_permutations"].item()==q.N_PERM, "reduced pilot cannot create a production bank"
    manifest,paths,hashes=oracle.load_manifest(data_dir)
    prepared={subject:oracle.subject_epochs(subject,paths) for subject in q.SUBJECTS}
    source_rows=[row for subject in q.SUBJECTS for row in prepared[subject]["source_rows"]]
    observations=[row for subject in q.SUBJECTS for row in prepared[subject]["run_observations"]]
    source_x=np.concatenate([prepared[s]["X"] for s in q.SUBJECTS])
    assert receipt["X"].shape==source_x.shape and np.allclose(receipt["X"],source_x,atol=1e-15,rtol=1e-12), "private epochs differ from original EDF preprocessing"
    retained={name:np.concatenate([prepared[s][name] for s in q.SUBJECTS])
              for name in ("run","event_index","event_sample","source_class")}
    retained["subject"]=np.concatenate([np.full(len(prepared[s]["X"]),s,dtype=np.int64) for s in q.SUBJECTS])
    for name,value in retained.items():
        assert np.array_equal(receipt[name],value), f"private retained-source {name} mismatch"
    assert q.parse_source_rows(json.loads(receipt["source_epochs_json"].item()))==q.parse_source_rows(source_rows)
    assert json.loads(receipt["run_observations_json"].item())==observations
    channels=prepared[q.SUBJECTS[0]]["channels"]
    assert all(prepared[s]["channels"]==channels for s in q.SUBJECTS)
    contract=oracle.metadata_contract(manifest)
    assert contract["channels"]==channels and contract["sfreq"]==160, "public channel identity is not source-derived"
    metadata=q.load_json(output/"run_metadata.json")
    assert json.loads(receipt["metadata_json"].item())==metadata
    rows,folds,results=q.statistics_from_predictions(retained["subject"],retained["run"],receipt["target_class"],receipt["predicted_class"])
    stats=dict(pipeline_id=q.PIPELINE_ID,source_sha256=hashes,metadata_contract=contract,
               results=results,n_source_events=len(source_rows),n_retained_epochs=len(source_x),
               n_epochs_by_run=observations)
    reference=dict(source_rows=source_rows,stats=stats,**retained,targets=receipt["target_class"],
                   predictions=receipt["predicted_class"],scores=receipt["decision_score"])
    q.validate_reference(reference)
    q.validate_output_directory(output,reference)
    reconstruction_error=reconstruct_scores(receipt)
    stats["authoring_validation"]={"original_edf_sha256_verified":True,"all_source_epochs_reconstructed":True,
        "all_fold_scores_reconstructed":True,"n_fold_models":len(folds),
        "max_score_reconstruction_error":reconstruction_error,
        "scope":"all_saved_models_reapplied; independent_estimator_refits_audited_separately"}
    arrays={"ref_"+key:value for key,value in retained.items()}
    for key in q.EVENT_FIELDS:
        arrays["ref_source_"+key]=np.asarray([row[key] for row in source_rows])
    arrays.update(ref_target_class=reference["targets"],ref_predicted_class=reference["predictions"],
                  ref_decision_score=reference["scores"],ref_stats=np.array(json.dumps(stats,allow_nan=False)))
    destination.parent.mkdir(parents=True,exist_ok=True)
    handle,name=tempfile.mkstemp(prefix=".genuine-reference-",suffix=".npz",dir=destination.parent)
    os.close(handle)
    temporary=Path(name)
    try:
        np.savez_compressed(temporary,**arrays)
        checked=q.load_reference(temporary)
        q.validate_output_directory(output,checked)
        os.replace(temporary,destination)
    finally:
        if temporary.exists(): temporary.unlink()
    return {"pipeline_id":q.PIPELINE_ID,"reference":str(destination),"n_epochs":len(source_x),
            "n_fold_models":len(folds),"max_score_reconstruction_error":reconstruction_error}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output","--oracle-output",dest="output",type=Path,required=True)
    parser.add_argument("--data",type=Path,default=Path("/app/data/eegbci"))
    parser.add_argument("--reference",type=Path,default=TASK/"tests"/"reference.npz")
    args=parser.parse_args()
    print(json.dumps(build(args.output,args.data,args.reference),indent=2,allow_nan=False))


if __name__=="__main__": main()
