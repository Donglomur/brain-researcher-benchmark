"""Build only from genuine executed outputs and authenticated original inputs.

The source reader/preprocessor is shared with the oracle and explicitly not an
independent analysis. This authoring gate reconstructs training-only ANOVA,
linear pairwise decisions and libsvm votes from retained fitted state. A separate
original-source implementation is required for the independent execution audit.
No new classifier is trained by this builder.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import numpy as np

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK / "tests"))
import proof_of_work as q


def anova_scores(x, labels):
    """Explicit one-way ANOVA arithmetic over training rows only."""
    x = np.asarray(x, dtype=np.float64)
    classes = np.unique(labels)
    groups = [x[labels == label] for label in classes]
    assert len(classes) > 1 and len(x) > len(classes)
    totals = [np.sum(group, axis=0) for group in groups]
    grand = np.sum(totals, axis=0)
    total_ss = np.sum(x*x, axis=0) - grand*grand/len(x)
    between_ss = sum(total*total/len(group) for total, group in zip(totals, groups)) - grand*grand/len(x)
    within_ss = total_ss-between_ss
    with np.errstate(divide="ignore", invalid="ignore"):
        return (between_ss/(len(classes)-1))/(within_ss/(len(x)-len(classes)))


def selected_indices(scores, count):
    values = np.asarray(scores, dtype=float).copy()
    values[np.isnan(values)] = np.finfo(values.dtype).min
    chosen = np.sort(np.argsort(values, kind="mergesort")[-count:])
    assert np.isfinite(scores[chosen]).all(), "selected ANOVA F must be finite"
    return chosen


def pairwise_outputs(decision, classes):
    """libsvm prediction votes and sklearn OVR display scores (not identical)."""
    decision = np.asarray(decision, dtype=float)
    n, c = len(decision), len(classes)
    votes = np.zeros((n, c), dtype=int)
    display_votes = np.zeros((n, c), dtype=int)
    confidence = np.zeros((n, c), dtype=float)
    column = 0
    for first in range(c):
        for second in range(first+1, c):
            value = decision[:, column]
            votes[:, first] += value > 0
            votes[:, second] += value <= 0
            display_votes[:, first] += value >= 0
            display_votes[:, second] += value < 0
            confidence[:, first] += value
            confidence[:, second] -= value
            column += 1
    assert column == decision.shape[1]
    ovr = display_votes + confidence/(3*(np.abs(confidence)+1))
    return np.asarray(classes)[np.argmax(votes, axis=1)], ovr


def validate_fit_state(source, arrays):
    x = source["X"]
    assert x.dtype == np.float64 and np.isfinite(x).all(), "cleaned source must be finite float64"
    run_ids = np.unique(source["run"])
    np.testing.assert_array_equal(arrays["run_ids"], run_ids)
    classes = np.asarray(q.CATEGORIES)
    np.testing.assert_array_equal(arrays["classes"], classes)
    n, v, c = len(x), x.shape[1], len(classes)
    pairs = c*(c-1)//2
    k = arrays["selected_indices"].shape[1]
    assert arrays["anova_f"].shape == (len(run_ids), v)
    assert arrays["selected_indices"].shape == (len(run_ids), k)
    assert arrays["selected_f"].shape == (len(run_ids), k)
    assert arrays["classifier_coef"].shape == (len(run_ids), pairs, k)
    assert arrays["classifier_intercept"].shape == (len(run_ids), pairs)
    assert arrays["decision_ovo"].shape == (n, pairs)
    assert arrays["decision_ovr"].shape == (n, c)
    assert arrays["classifier_n_support"].shape == (len(run_ids), c)
    assert arrays["classifier_fit_status"].shape == (len(run_ids),)
    assert np.all(arrays["classifier_fit_status"] == 0), "failed SVC fit cannot become a bank"
    assert arrays["classifier_n_iter"].shape == (len(run_ids), pairs)
    assert arrays["classifier_n_iter"].dtype.kind in "iu" and (arrays["classifier_n_iter"] > 0).all()
    volume_lookup = {int(value): index for index, value in enumerate(source["volume_id"])}
    for fold, run in enumerate(run_ids):
        train, test = source["run"] != run, source["run"] == run
        scores = anova_scores(x[train], source["true_label"][train])
        retained_scores = arrays["anova_f"][fold]
        assert np.array_equal(np.isfinite(scores), np.isfinite(retained_scores)), "ANOVA score availability mismatch"
        assert np.array_equal(np.isnan(scores), np.isnan(retained_scores)), "ANOVA undefined scores mismatch"
        finite = np.isfinite(scores)
        np.testing.assert_allclose(retained_scores[finite], scores[finite], atol=q.F_ATOL, rtol=q.F_RTOL)
        chosen = selected_indices(scores, k)
        np.testing.assert_array_equal(arrays["selected_indices"][fold], chosen)
        np.testing.assert_allclose(arrays["selected_f"][fold], scores[chosen], atol=q.F_ATOL, rtol=q.F_RTOL)
        retained_ids = arrays[f"svc_support_volume_ids_{int(run)}"]
        assert retained_ids.ndim == 1 and retained_ids.dtype.kind in "iu"
        assert len(set(retained_ids)) == len(retained_ids), "duplicate support vector identity"
        assert all(int(value) in volume_lookup for value in retained_ids), "non-source support vector"
        support_indices = np.array([volume_lookup[int(value)] for value in retained_ids])
        assert np.all(train[support_indices]), "test-run support vectors leak into fitting"
        n_support = arrays["classifier_n_support"][fold]
        assert n_support.dtype.kind in "iu" and (n_support >= 0).all() and n_support.sum() == len(support_indices)
        bounds = np.r_[0, np.cumsum(n_support)]
        support_x = x[support_indices][:, chosen]
        dual = arrays[f"svc_dual_coef_{int(run)}"]
        assert dual.shape == (c-1, len(support_indices)) and np.isfinite(dual).all()
        for index, label in enumerate(classes):
            assert np.all(source["true_label"][support_indices[bounds[index]:bounds[index+1]]] == label), "support class order mismatch"
        coefficients = []
        for first in range(c):
            for second in range(first+1, c):
                a, b = slice(bounds[first], bounds[first+1]), slice(bounds[second], bounds[second+1])
                coefficients.append(dual[second-1, a] @ support_x[a] + dual[first, b] @ support_x[b])
        np.testing.assert_allclose(arrays["classifier_coef"][fold], coefficients, atol=1e-8, rtol=1e-6)
        decision = x[test][:, chosen] @ arrays["classifier_coef"][fold].T + arrays["classifier_intercept"][fold]
        np.testing.assert_allclose(arrays["decision_ovo"][test], decision, atol=1e-8, rtol=1e-6)
        predicted, ovr = pairwise_outputs(decision, classes)
        np.testing.assert_array_equal(arrays["predicted_label"][test], predicted)
        np.testing.assert_allclose(arrays["decision_ovr"][test], ovr, atol=1e-8, rtol=1e-6)
        assert int(arrays["fold_n_train"][fold]) == int(train.sum())
        assert int(arrays["fold_n_test"][fold]) == int(test.sum())
        np.testing.assert_allclose(arrays["fold_accuracy"][fold], np.mean(predicted == source["true_label"][test]), atol=1e-12, rtol=0)


def build(data_dir, output_dir, reference_path, template_path):
    spec = importlib.util.spec_from_file_location("objcat_authoring_oracle", TASK / "solution/compute.py")
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    inputs = oracle.load_inputs(Path(data_dir))
    contract = oracle.metadata_contract(inputs)
    assert q.load_json(template_path) == contract, "public template differs from source contract"
    source = oracle.prepare_source(inputs)
    output_dir, reference_path = Path(output_dir), Path(reference_path)
    with np.load(output_dir / "analysis_arrays.npz", allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    for key in ("mask_ijk", "volume_id", "run", "true_label", "full_volume_id", "full_run", "full_label"):
        np.testing.assert_array_equal(arrays[key], source[key], err_msg=f"source receipt mismatch: {key}")
    metadata = json.loads(str(arrays["metadata_json"].item()))
    results = json.loads(str(arrays["results_json"].item()))
    assert metadata == q.load_json(output_dir / "run_metadata.json")
    assert results == q.load_json(output_dir / "decoding_results.json")
    q.match_metadata(metadata, contract)
    assert metadata["status"] == "ok"
    validate_fit_state(source, arrays)
    reference = {key: arrays[key] for key in ("volume_id", "run", "true_label", "predicted_label",
                   "run_ids", "mask_ijk", "selected_indices", "selected_f")}
    assert reference["selected_indices"].shape == (12, 500), "production feature support must be complete"
    assert len(reference["volume_id"]) == 864
    assert np.array_equal(reference["run_ids"], np.arange(12))
    assert np.all(np.bincount(reference["run"]) == 72)
    assert source["X"].shape == (864, len(reference["mask_ijk"]))
    reference["stats"] = dict(pipeline_id=q.PIPELINE_ID, source_sha256=contract["source_sha256"],
                              metadata_contract=contract, results=results, n_full_volumes=len(source["full_volume_id"]),
                              public_template_sha256=hashlib.sha256(Path(template_path).read_bytes()).hexdigest(),
                              authoring_evidence={"source_preprocessor": "shared_with_oracle",
                                                  "anova_and_linear_state": "recomputed_from_original_source",
                                                  "independent_execution": "separate_checker_required"})
    q.validate_reference(reference)
    q.validate_output_directory(output_dir, reference)
    bank = {"ref_"+key: value for key, value in reference.items() if key != "stats"}
    bank["ref_stats"] = np.array(json.dumps(reference["stats"], allow_nan=False))
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=reference_path.parent, prefix=".genuine-source-", suffix=".npz", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        np.savez_compressed(temporary, **bank)
        q.validate_output_directory(output_dir, q.load_reference(temporary))
        temporary.replace(reference_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(json.dumps(dict(status="passed", reference=str(reference_path), n_samples=864, n_selected_rows=6000)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="/app/data/objcat")
    parser.add_argument("--output", default="/app/output")
    parser.add_argument("--reference", "--bank", default=str(TASK/"tests/reference.npz"))
    parser.add_argument("--template", default=str(TASK/"environment/method_contract.json"))
    args = parser.parse_args()
    build(args.data, args.output, args.reference, args.template)


if __name__ == "__main__":
    main()
