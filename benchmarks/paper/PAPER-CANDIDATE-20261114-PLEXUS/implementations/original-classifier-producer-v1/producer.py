"""Unqualified original Figure 4 classifier stage; no upstream preprocessing.

The caller must provide the complete authenticated, ordered post-TVN/aggregation
matrices. Hash consistency does not establish that authentication. This module
does not establish publication parity, a protected evaluation, or paper wins.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import warnings

import numpy as np


SPLITTER_SHA256 = "799aa421eb7c2e8c96ce0741c012ab8357bbd77f1a549a7854fc46b1c455eb7d"
SOURCE_RECIPE = {
    "max_iter": 1000,
    "random_state": 42,
    "penalty": "elasticnet",
    "solver": "saga",
    "l1_ratio": 0.5,
}
QUALIFICATION = (
    "Unqualified classifier-stage construction output. Authentic complete inputs, "
    "upstream preprocessing, runtime/version parity, final-paper/archive mapping, "
    "competent author reference and scientific comparison remain unresolved."
)


def _load_splitter():
    path = Path(__file__).resolve().parents[1] / "original-figure4-v1" / "figure4.py"
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != SPLITTER_SHA256:
        raise ValueError("reviewed original split/scoring dependency changed")
    spec = importlib.util.spec_from_file_location("plexus_original_figure4", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


f = _load_splitter()


def _runtime():
    # Imported only for a separately admitted execution, not on module import.
    import sklearn
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    return StandardScaler, LogisticRegression, sklearn.__version__


def _validate_features(census, features, expected_features_sha256):
    f.pin(expected_features_sha256, "independently frozen feature bundle pin")
    f.require(f.digest(features) == expected_features_sha256, "feature bundle pin mismatch")
    f.require(isinstance(features, dict) and features.get("schema") == "plexus-figure4-features/v1",
              "feature bundle schema mismatch")
    f.require(features.get("census_sha256") == f.digest(census), "feature/census mismatch")
    f.require(features.get("preprocessing_receipt_sha256") == census["preprocessing_receipt_sha256"],
              "upstream preprocessing receipt mismatch")
    supplied = features.get("panels")
    f.require(isinstance(supplied, list) and len(supplied) == 4, "exactly four feature panels required")
    expected = {(p["family"], p["donor"]): p for p in census["panels"]}
    output = {}
    for panel in supplied:
        f.require(isinstance(panel, dict), "feature panel must be an object")
        key = (panel.get("family"), panel.get("donor"))
        f.require(key in expected and key not in output, "unknown or duplicate feature panel")
        ids = [row["observation_id"] for row in expected[key]["observations"]]
        f.require(panel.get("observation_ids") == ids, "feature rows differ from complete original census order")
        f.require(panel.get("upstream_stage") == "source_post_tvn_and_required_aggregation_pre_classifier_scaler",
                  "features must declare the exact upstream stage; raw embeddings are insufficient")
        f.pin(panel.get("matrix_source_sha256"), "matrix_source_sha256")
        f.require(panel.get("dtype") in ("float32", "float64"),
                  "source floating dtype must be explicitly preserved; other types require reconciliation")
        rows = panel.get("values")
        f.require(isinstance(rows, list) and len(rows) == len(ids), "feature row count mismatch")
        f.require(rows and isinstance(rows[0], list) and rows[0], "nonempty dense feature matrix required")
        columns = len(rows[0])
        for row in rows:
            f.require(isinstance(row, list) and len(row) == columns, "ragged feature matrix")
            f.require(all(type(x) in (int, float) for x in row), "feature values must be numeric, not booleans")
        try:
            values = np.asarray(rows, dtype=panel["dtype"])
        except (ValueError, TypeError, OverflowError) as exc:
            raise f.InputError("feature values cannot be represented in the declared source dtype") from exc
        f.require(np.isfinite(values).all(), "nonfinite feature values")
        output[key] = (values, {oid: i for i, oid in enumerate(ids)}, panel["matrix_source_sha256"])
    f.require(set(output) == set(expected), "missing feature panel")
    return output


def _model_diagnostics(model):
    # Record the resolved defaults too: the paper's original sklearn version is
    # unresolved, and equal explicit arguments do not establish runtime parity.
    parameters = model.get_params(deep=False)
    f.digest(parameters)
    iterations = np.asarray(getattr(model, "n_iter_", []))
    f.require(iterations.ndim == 1 and np.issubdtype(iterations.dtype, np.integer),
              "model iteration diagnostics must be integer vector")
    return {"resolved_parameters": parameters, "n_iter": [int(x) for x in iterations]}


def _probabilities(model, values):
    classes = np.asarray(model.classes_)
    f.require(classes.tolist() == [0, 1], "classifier class/probability ordering differs from source")
    probabilities = np.asarray(model.predict_proba(values))
    f.require(probabilities.shape == (len(values), 2), "classifier probability shape mismatch")
    f.require(np.isfinite(probabilities).all() and (probabilities >= 0).all() and
              (probabilities <= 1).all(), "invalid classifier probabilities")
    f.require(np.allclose(probabilities.sum(axis=1), 1, rtol=1e-10, atol=1e-12),
              "classifier rows are not probability distributions")
    return probabilities[:, 1]


def produce(census, features, expected_census_sha256, expected_features_sha256):
    """Run the source classifier stage only; requires separate execution admission.

    No script entry point is provided. Callers own frozen data provenance,
    process/resource isolation, protected references and atomic result storage.
    """
    return _produce(census, features, expected_census_sha256, expected_features_sha256, _runtime())


def _produce(census, features, expected_census_sha256, expected_features_sha256, runtime):
    """Private dependency-injection seam for non-fitting engineering controls."""
    f.pin(expected_census_sha256, "independently frozen census pin")
    f.require(f.digest(census) == expected_census_sha256, "census pin mismatch")
    plan = f.prepare(census)
    matrices = _validate_features(census, features, expected_features_sha256)
    scaler_factory, classifier_factory, sklearn_version = runtime
    f.string(sklearn_version, "sklearn version")
    scores, records, panel_records = [], [], []
    for panel in plan["panels"]:
        key = (panel["family"], panel["donor"])
        values, index, source_pin = matrices[key]
        scaler = scaler_factory()
        # This deliberately sees the entire source panel before any well split.
        # Changing to training-only scaling would be a different experiment.
        values = np.asarray(scaler.fit_transform(values.copy()))
        f.require(values.shape == (panel["n_observations"], matrices[key][0].shape[1]) and
                  np.isfinite(values).all(), "invalid full-panel scaler output")
        panel_records.append({"family": key[0], "donor": key[1],
                              "matrix_source_sha256": source_pin,
                              "n_rows_scaled_before_split": len(values),
                              "n_features": values.shape[1],
                              "input_dtype": str(matrices[key][0].dtype),
                              "scaled_dtype": str(values.dtype)})
        method = "author_plexus" if panel["family"] == "plexus" else "author_manual_features"
        for endpoint in panel["endpoints"]:
            record = {"method": method, "donor": panel["donor"], "guide_id": endpoint["guide_id"],
                      "status": "incomplete", "folds": [], "warnings": []}
            # Source creates both models, fits fold1 then fold2, and only emits
            # either AUROC if both fits and both predictions succeed.
            pending = []
            stage = "construct"
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                try:
                    models = [classifier_factory(**SOURCE_RECIPE) for _ in range(2)]
                    for fold, model in zip(endpoint["folds"], models):
                        stage = f"fit_fold_{fold['fold']}"
                        train = fold["train"]
                        model.fit(values[[index[r["observation_id"]] for r in train]],
                                  np.asarray([r["label"] for r in train], dtype=int))
                        record["folds"].append({"fold": fold["fold"], "n_train": len(train),
                                                "n_test": len(fold["test"]), **_model_diagnostics(model)})
                    for fold, model in zip(endpoint["folds"], models):
                        stage = f"predict_fold_{fold['fold']}"
                        test = fold["test"]
                        probabilities = _probabilities(model, values[[index[r["observation_id"]] for r in test]])
                        for row, probability in zip(test, probabilities):
                            pending.append({"method": method, "donor": panel["donor"],
                                            "guide_id": endpoint["guide_id"], "fold": fold["fold"],
                                            "observation_id": row["observation_id"],
                                            "probability": float(probability)})
                    record["status"] = "both_folds_emitted"
                except Exception as exc:
                    record["failure_stage"] = stage
                    record["error_type"] = type(exc).__name__
                    record["error_message"] = str(exc)[:512]
                    pending = []
                record["warnings"] = [{"category": w.category.__name__, "message": str(w.message)[:512]}
                                      for w in captured]
            scores.extend(pending)
            records.append(record)
    complete = all(r["status"] == "both_folds_emitted" for r in records)
    return {"schema": "plexus-figure4-author-stage/v1", "plan_sha256": f.digest(plan),
            "census_sha256": expected_census_sha256, "features_sha256": expected_features_sha256,
            "preprocessing_receipt_sha256": census["preprocessing_receipt_sha256"],
            "splitter_sha256": SPLITTER_SHA256, "source_figure4_sha256": f.SOURCE_SHA256,
            "runtime": {"numpy": np.__version__, "sklearn": sklearn_version},
            "explicit_classifier_parameters": dict(SOURCE_RECIPE),
            "producer_status": "complete_declared_plan" if complete else "incomplete_declared_plan",
            "scores": scores, "fit_records": records, "panel_records": panel_records,
            "source_metadata_skips": [{"family": p["family"], "donor": p["donor"],
                                       "guides": p["skipped_guides"]} for p in plan["panels"]],
            "scientific_qualification": False, "qualification": QUALIFICATION}


def assemble_submission(census, reference, candidate_scores):
    """Validate complete joint prediction support without silently dropping failures.

    This checks internal consistency only. Caller authentication of independent
    producer receipts, source competence and held-out access remains mandatory.
    """
    f.require(isinstance(reference, dict) and reference.get("schema") == "plexus-figure4-author-stage/v1",
              "author-stage schema mismatch")
    f.require(reference.get("producer_status") == "complete_declared_plan", "incomplete producer cannot be scored")
    f.require(reference.get("census_sha256") == f.digest(census), "reference census mismatch")
    plan = f.prepare(census)
    f.require(reference.get("plan_sha256") == f.digest(plan), "reference plan mismatch")
    f.require(isinstance(candidate_scores, list) and all(isinstance(r, dict) and r.get("method") == "candidate"
                                                      for r in candidate_scores), "candidate-only score rows required")
    author = reference.get("scores")
    f.require(isinstance(author, list) and all(isinstance(r, dict) and r.get("method") in
                                              ("author_manual_features", "author_plexus") for r in author),
              "author-only reference score rows required")
    submission = {"schema": "plexus-figure4-predictions/v1", "plan_sha256": reference["plan_sha256"],
                  "scores": author + candidate_scores}
    f.evaluate(census, submission, reference["census_sha256"])
    return submission
