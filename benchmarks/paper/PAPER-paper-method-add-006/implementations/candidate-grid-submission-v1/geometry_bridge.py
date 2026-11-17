"""Raw candidate reconstruction/readout operands, with trusted derived scores.

This is an operator evaluator, not a participant runner. In particular it does
not prove that readout predictions were frozen before full latent targets were
released for covariance reconstruction. Those must be separate delivery phases.
"""
from __future__ import annotations

import hashlib
import json
import numpy as np
from deps import G, K, P, R, need

SCHEMA = "population_geometry_candidate_v1"
FIELDS = {"schema", "job_id", "method_sha256", "row_ids", "unit_ids",
          "training_row_ids", "test_row_ids", "valid_teacher_indices",
          "joint_covariance", "readout_predictions"}


def digest(value):
    need(isinstance(value, str) and len(value) == 64
         and all(c in "0123456789abcdef" for c in value), "SHA256 identity required")
    return value


def _same(value, expected, label):
    a, b = np.asarray(value), np.asarray(expected)
    need(a.shape == b.shape and a.dtype.kind == b.dtype.kind
         and np.array_equal(a, b), label + " identity/order differs")
    return a.copy()


def _rng(saved):
    need(isinstance(saved, dict) and set(saved) ==
         {"algorithm", "keys", "position", "has_gauss", "cached_gaussian"},
         "complete frozen MT19937 state required")
    need(saved["algorithm"] == "MT19937" and len(saved["keys"]) == 624
         and all(type(v) is int and 0 <= v < 2**32 for v in saved["keys"])
         and type(saved["position"]) is int and 0 <= saved["position"] <= 624
         and type(saved["has_gauss"]) is int and saved["has_gauss"] in (0, 1)
         and np.isfinite(saved["cached_gaussian"]), "invalid frozen MT19937 state")
    rng = np.random.RandomState()
    P.restore_rng(rng, saved)
    return rng


def _job(job):
    need(isinstance(job, dict) and set(job) ==
         {"case_id", "animal", "session", "region", "repetition", "region_seed"},
         "complete original geometry coordinate required")
    need(job["animal"] in R.ANIMALS and type(job["session"]) is int
         and job["session"] in R.SESSIONS and job["region"] in R.REGIONS
         and type(job["repetition"]) is int and 0 <= job["repetition"] < 500
         and job["region_seed"] == R.REGION_SEEDS[job["region"]]
         and job["case_id"] == f"{job['animal']}-s{job['session']:02d}-{job['region']}",
         "original geometry coordinate differs")
    return dict(job)


class ReferenceChain:
    """Require the complete current source RNG chain in original global order."""
    def __init__(self):
        self._jobs = iter(R.geometry_plan())
        self._next = next(self._jobs, None)
        self._states = {r: R.state(np.random.RandomState(seed)) for r, seed in R.REGION_SEEDS.items()}
        self._count = 0
        self._digest = hashlib.sha256()

    def accept(self, checkpoint):
        job = _job(checkpoint["job"])
        need(self._next is not None and job == self._next, "source reference global coordinate order differs")
        need(checkpoint["rng_before"] == self._states[job["region"]],
             "source reference RNG chain differs from fixed region seed/previous draw")
        _rng(checkpoint["rng_after"])
        self._digest.update(json.dumps({"job": job, "before": checkpoint["rng_before"],
                                        "after": checkpoint["rng_after"]},
                                       sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
        self._states[job["region"]] = copy_state(checkpoint["rng_after"])
        self._count += 1
        self._next = next(self._jobs, None)

    def finish(self):
        need(self._next is None and self._count == 64000, "complete64000 source RNG chain required")
        return {"geometry_jobs": self._count, "reference_chain_sha256": self._digest.hexdigest(),
                "historical_realization_authenticated": False}


def copy_state(state):
    return {**state, "keys": list(state["keys"])}


def make_reference(prepared, checkpoint, source_svc_predictions, *, checkpoint_sha256,
                   source_prediction_sha256, reference_chain):
    """Bind an operator's frozen source draw and newly retained SVC predictions.

    Existing geometry checkpoints contain error summaries, not raw SVC test
    predictions. The latter is an explicit new required operator artifact. This
    function authenticates logical joins after the caller authenticates the two
    supplied content hashes; it cannot attest producer execution or file custody.
    No classifier is fitted or replayed here.
    """
    digest(checkpoint_sha256)
    digest(source_prediction_sha256)
    need(isinstance(reference_chain, ReferenceChain), "operator global ReferenceChain required")
    job = _job(checkpoint["job"])
    need(prepared.get("case_id", job["case_id"]) == job["case_id"], "prepared case differs")
    x, z = K.matrix(prepared["x"], "prepared geometry points"), K.matrix(
        prepared["z"], "prepared geometry latents", 4)
    need(len(x) == len(z) and len(x) >= 500 and x.shape[1] >= 19,
         "complete original prepared support required")
    rows = R.identities(prepared["row_ids"], len(x), "native rows")
    units = R.identities(prepared["unit_ids"], x.shape[1], "native units")
    rng = _rng(checkpoint["rng_before"])
    row_positions = rng.choice(len(x), 500, replace=False)
    unit_positions = rng.choice(x.shape[1], 19, replace=False)
    _same(checkpoint["row_positions"], row_positions, "source row draw")
    _same(checkpoint["unit_positions"], unit_positions, "source unit draw")
    _same(checkpoint["row_ids"], rows[row_positions], "source native rows")
    _same(checkpoint["unit_ids"], units[unit_positions], "source native units")
    xx, zz = x[row_positions][:, unit_positions], z[row_positions]
    teacher_state = R.state(rng)
    teachers = rng.randn(4, 500)
    labels = np.sign(zz @ teachers)
    valid = np.flatnonzero(np.abs(labels.mean(axis=0)) < 0.25)
    need(len(valid) > 100, "source requires more than100 balanced teachers")
    train = rng.choice(500, size=300, replace=False)
    test = np.setdiff1d(np.arange(500), train)
    rd = checkpoint["readout"]
    need(rd["teacher_identity"] == R.array_identity(teachers)
         and rd["pre_teacher_state_sha256"] == R.digest(teacher_state)
         and rd["latent_identity"] == R.array_identity(zz), "source teacher/latent state differs")
    for key, expected in (("valid_teacher_indices", valid), ("training_positions", train),
                          ("test_positions", test)):
        _same(rd[key], expected, key)
    need(checkpoint["rng_after"] == R.state(rng)
         and rd["rng_before"] == teacher_state and rd["rng_after"] == R.state(rng),
         "source geometry RNG continuation differs")
    _same(checkpoint["training_row_ids"], rows[row_positions][train], "training native rows")
    _same(checkpoint["test_row_ids"], rows[row_positions][test], "test native rows")
    need(rd["svc_policy"] in (R.SVC_POLICY, R.SVC_LITERAL_POLICY), "explicit source SVC policy required")
    source_pred = np.asarray(source_svc_predictions)
    need(source_pred.shape == (200, len(valid)) and source_pred.dtype.kind in "biuf"
         and np.isfinite(source_pred).all() and np.isin(source_pred, [0, 1]).all(),
         "raw source SVC test predictions must be complete source encoded labels")
    reference_chain.accept(checkpoint)
    return {"schema": "population_geometry_operator_reference_v1", "job": job,
            "points": xx.copy(), "latents": zz.copy(), "row_ids": rows[row_positions].copy(),
            "unit_ids": units[unit_positions].copy(), "training_positions": train,
            "test_positions": test, "valid_teacher_indices": valid,
            "labels": labels[:, valid], "source_svc_predictions": source_pred.copy(),
            "source_checkpoint_sha256": checkpoint_sha256,
            "source_prediction_sha256": source_prediction_sha256,
            "packet_pin": checkpoint["packet_pin"], "behavior": checkpoint["behavior"],
            "svc_policy": rd["svc_policy"], "source_readout_metadata": {
                k: rd[k] for k in ("teacher_identity", "pre_teacher_state_sha256", "svc_policy")},
            "new_source_prediction_artifact_required": True,
            "qualification": False}


def _geometry(covariance):
    cov = np.asarray(covariance)
    need(cov.shape == (23, 23) and cov.dtype.kind in "fiu" and np.isfinite(cov).all(),
         "joint covariance requires all529 finite numeric coordinates")
    cov = cov.astype(float)
    # Exact symmetry is required for this interchange representation: no silent
    # symmetrization can discard a participant-controlled lower-left block.
    need(np.array_equal(cov, cov.T), "complete joint covariance must be exactly symmetric")
    result = K.geometry_from_covariance(cov[:19, :19], cov[:19, 19:], cov[19:, 19:], 300)
    return cov, result


def _difference(candidate, source):
    if np.isposinf(candidate) and np.isposinf(source):
        return {"difference": None, "status": "equal_positive_infinity"}
    if np.isfinite(candidate) and np.isfinite(source):
        return {"difference": float(candidate - source), "status": "finite"}
    return {"difference": None, "status": "unequal_infinite_value",
            "candidate_positive_infinity": bool(np.isposinf(candidate)),
            "source_positive_infinity": bool(np.isposinf(source))}


def evaluate_geometry(reference, candidate):
    """Derive source and candidate reconstruction/readout quantities, never a win.

    `reference` is operator-owned. Candidate counts, labels, source scores,
    geometry summaries or source-model labels cannot enter through this schema.
    The method digest is a submitted identity, not attestation of its execution.
    """
    need(reference.get("schema") == "population_geometry_operator_reference_v1",
         "operator reference schema required")
    job = _job(reference["job"])
    need(isinstance(candidate, dict) and set(candidate) == FIELDS
         and candidate["schema"] == SCHEMA, "exact candidate geometry operands required")
    need(candidate["job_id"] == P.geometry_id(job), "candidate geometry job differs")
    method = digest(candidate["method_sha256"])
    x, z = K.matrix(reference["points"], "source points", 19), K.matrix(
        reference["latents"], "source latents", 4)
    need(x.shape == (500, 19) and z.shape == (500, 4), "original500×19 geometry support required")
    row_ids = R.identities(reference["row_ids"], 500, "source rows")
    unit_ids = R.identities(reference["unit_ids"], 19, "source units")
    train = R.indices(reference["training_positions"], 500, "training", count=300)
    test = R.indices(reference["test_positions"], 500, "test", count=200)
    need(np.array_equal(test, np.setdiff1d(np.arange(500), train)), "test partition must complement training")
    valid = R.indices(reference["valid_teacher_indices"], 500, "teacher", count=None)
    need(len(valid) > 100 and np.all(np.diff(valid) > 0), "complete sorted source balanced teacher support required")
    for key, expected in (("row_ids", row_ids), ("unit_ids", unit_ids),
                          ("training_row_ids", row_ids[train]), ("test_row_ids", row_ids[test]),
                          ("valid_teacher_indices", valid)):
        _same(candidate[key], expected, "candidate " + key)
    labels = np.asarray(reference["labels"])
    need(labels.shape == (500, len(valid)) and labels.dtype.kind in "fiu"
         and np.isin(labels, [-1, 0, 1]).all(), "complete source teacher targets required")
    prediction = np.asarray(candidate["readout_predictions"])
    need(prediction.shape == (200, len(valid)) and prediction.dtype.kind in "fiu"
         and np.isin(prediction, [-1, 0, 1]).all(), "complete signed candidate test predictions required")
    svc_pred = np.asarray(reference["source_svc_predictions"])
    need(svc_pred.shape == prediction.shape and svc_pred.dtype.kind in "biuf"
         and np.isfinite(svc_pred).all() and np.isin(svc_pred, [0, 1]).all(),
         "complete trusted raw SVC predictions required")
    joined = np.column_stack([x, z])
    joined -= joined.mean(axis=0)
    source_cov, source_geom = _geometry(joined.T @ joined / 500)
    proposed_cov, proposed_geom = _geometry(candidate["joint_covariance"])
    hebbian = np.sign(x[test] @ (labels[train].T @ x[train] / 300).T)
    hebbian_errors = np.mean(-labels[test] * hebbian > 0, axis=0)
    svc_errors = np.mean(svc_pred != (1 + labels[test]) / 2, axis=0)
    # Arbitrary zero predictions must not exploit the original Hebbian-only
    # zero-margin rule. Candidate errors use ordinary label inequality, exactly
    # the source SVC classification-error criterion in signed label encoding.
    candidate_errors = np.mean(prediction != labels[test], axis=0)
    metadata = reference["source_readout_metadata"]
    need(metadata["svc_policy"] == reference["svc_policy"]
         and reference["svc_policy"] in (R.SVC_POLICY, R.SVC_LITERAL_POLICY),
         "source SVC recipe differs")
    source_result = {
        "schema": "source_raw_geometry_repetition_v1", "job": job,
        "case_id": job["case_id"], "repetition": job["repetition"],
        "condition": "current_source_code19", "geometry_fields": list(R.GEOMETRY_FIELDS),
        "geometry_values": np.asarray([source_geom[k] for k in R.GEOMETRY_FIELDS]),
        "theory_error": source_geom["theory_error"], "packet_pin": reference["packet_pin"],
        "behavior": reference["behavior"], "row_ids": row_ids, "unit_ids": unit_ids,
        "training_row_ids": row_ids[train], "test_row_ids": row_ids[test],
        "readout": {**metadata, "hebbian_error": float(hebbian_errors.mean()),
                    "hebbian_task_errors": hebbian_errors, "svc_error": float(svc_errors.mean()),
                    "svc_task_errors": svc_errors, "valid_teacher_indices": valid},
        "historical_realization_authenticated": False,
        "source_quantities_derived_by_evaluator": True}
    return {
        "schema": "population_geometry_candidate_evaluation_v1", "job": job,
        "method_sha256": method, "source_result": source_result,
        "candidate_reconstruction": {
            "joint_covariance": proposed_cov, "source_joint_covariance": source_cov,
            "covariance_coordinate_difference": proposed_cov - source_cov,
            "max_absolute_covariance_difference": float(np.max(np.abs(proposed_cov - source_cov))),
            "geometry_fields": list(R.GEOMETRY_FIELDS),
            "geometry_values": np.asarray([proposed_geom[k] for k in R.GEOMETRY_FIELDS]),
            "geometry_differences": {k: _difference(proposed_geom[k], source_geom[k])
                                     for k in R.GEOMETRY_FIELDS},
            "theory_error": proposed_geom["theory_error"],
            "theory_error_difference": _difference(proposed_geom["theory_error"], source_geom["theory_error"])},
        "candidate_readout": {"task_errors": candidate_errors,
                              "error": float(candidate_errors.mean()),
                              "source_svc_error_difference": float(candidate_errors.mean() - svc_errors.mean()),
                              "label_rule": "ordinary inequality on signed source labels; zero is not a free correct prediction",
                              "method_role": "arbitrary candidate; not source Hebbian or LinearSVC"},
        "source_checkpoint_sha256": digest(reference["source_checkpoint_sha256"]),
        "source_prediction_sha256": digest(reference["source_prediction_sha256"]),
        "qualification": False, "scientific_improvement": None,
        "interpretation": "Geometry discrepancies assess reconstruction. Readout differences are a separate supporting result; neither is an overall paper-improvement predicate."}


def _value_identity(value):
    arrays = {}
    tree = P.encode_tree(value, arrays)
    return hashlib.sha256(P.canonical({"tree": tree, "arrays": {
        k: R.array_identity(v) for k, v in arrays.items()}})).hexdigest()


def paired_glm_pr(source_fitted, candidate_fitted, *, rng):
    """Use original PR finalizer with identical source/candidate draw identities."""
    need(source_fitted["case_id"] == candidate_fitted["case_id"]
         and source_fitted["packet_pin"] == candidate_fitted["packet_pin"],
         "source/candidate GLM packet or case differs")
    need(source_fitted["job"] == candidate_fitted["job"]
         and source_fitted["job"]["basis_index"] == G.GRID.index(G.FIGURE_BASIS),
         "original figure-basis GLM coordinate required")
    for key in ("counts", "row_ids", "unit_ids"):
        _same(candidate_fitted[key], source_fitted[key], "paired GLM " + key)
    candidate_rng = _rng(R.state(rng))
    results = []
    for fitted, generator, role in ((source_fitted, rng, "author_reference"),
                                    (candidate_fitted, candidate_rng, "candidate")):
        result = R.glm_pr_result(fitted["counts"], fitted["predictions"], fitted["cv_scores"],
                                fitted["selected_alpha_indices"], fitted["unit_ids"],
                                rng=generator, case_id=fitted["case_id"], row_ids=fitted["row_ids"])
        result.update(packet_pin=dict(fitted["packet_pin"]), operand_role=role)
        for key in ("source_asset_id", "source_epoch"):
            if key in fitted:
                result[key] = fitted[key]
        results.append(result)
    need(R.state(rng) == R.state(candidate_rng), "paired PR RNG continuation differs")
    return tuple(results)


def reduce_geometry_case(evaluated, source_glm_result, candidate_glm_result, *, case_id):
    """Complete500-draw case, joining existing source finalizer without relabeling."""
    rows = list(evaluated)
    need(len(rows) == 500 and [r["job"]["repetition"] for r in rows] == list(range(500)),
         "complete ordered500-draw case required")
    need(all(r.get("schema") == "population_geometry_candidate_evaluation_v1"
             and r["job"]["case_id"] == case_id for r in rows), "mixed geometry evaluation case")
    method = rows[0]["method_sha256"]
    need(all(r["method_sha256"] == method for r in rows), "one frozen candidate method required")
    packet = rows[0]["source_result"]["packet_pin"]
    need(source_glm_result.get("operand_role") == "author_reference"
         and candidate_glm_result.get("operand_role") == "candidate"
         and source_glm_result.get("packet_pin") == packet
         and candidate_glm_result.get("packet_pin") == packet
         and all(r["source_result"]["packet_pin"] == packet for r in rows),
         "geometry/source/candidate GLM packet identities or roles differ")
    behavior = rows[0]["source_result"]["behavior"]
    behavior_identity = _value_identity(behavior)
    need(all(_value_identity(r["source_result"]["behavior"]) == behavior_identity for r in rows),
         "geometry draw behavior provenance differs")
    source = R.session_result([r["source_result"] for r in rows], source_glm_result,
                              case_id=case_id, behavior=behavior)
    need(candidate_glm_result.get("schema") == "source_glm_pr_session_v1"
         and candidate_glm_result.get("condition") == "current_source_code19"
         and candidate_glm_result.get("case_id") == case_id
         and np.asarray(candidate_glm_result.get("subset_pr")).shape == (500, 2),
         "separate complete evaluator-derived candidate GLM PR required")
    candidate_errors = np.asarray([r["candidate_readout"]["error"] for r in rows])
    return {"schema": "population_candidate_case_v1", "case_id": case_id,
            "method_sha256": method, "source_result": source,
            "candidate_glm_result": candidate_glm_result,
            "candidate_readout_errors": candidate_errors,
            "candidate_readout_mean_error": float(candidate_errors.mean()),
            "candidate_geometry": np.stack([r["candidate_reconstruction"]["geometry_values"] for r in rows]),
            "covariance_max_absolute_differences": np.asarray([
                r["candidate_reconstruction"]["max_absolute_covariance_difference"] for r in rows]),
            "qualification": False, "scientific_improvement": None}


def reduce_panel(cases):
    """Join all128cells through existing finalizer; retain eight independent rats."""
    rows = list(cases)
    expected = [f"{a}-s{s:02d}-{r}" for a in R.ANIMALS for s in R.SESSIONS for r in R.REGIONS]
    need(len(rows) == 128 and [r["case_id"] for r in rows] == expected,
         "complete original128cell order required")
    method = rows[0]["method_sha256"]
    need(all(r.get("schema") == "population_candidate_case_v1"
             and r["method_sha256"] == method for r in rows), "one complete candidate panel required")
    need(all(r["source_result"]["case_id"] == r["case_id"]
             and r["candidate_glm_result"]["case_id"] == r["case_id"]
             and np.asarray(r["candidate_readout_errors"]).shape == (500,)
             and np.asarray(r["candidate_geometry"]).shape == (500, 8)
             and np.asarray(r["covariance_max_absolute_differences"]).shape == (500,)
             for r in rows), "source/candidate case identity or complete derived-array shape differs")
    source = R.panel_result([r["source_result"] for r in rows])
    return {"schema": "population_candidate_panel_v1", "method_sha256": method,
            "source_result": source, "case_order": expected,
            "candidate_glm_results": [r["candidate_glm_result"] for r in rows],
            "candidate_readout_errors": np.stack([r["candidate_readout_errors"] for r in rows]),
            "candidate_geometry": np.stack([r["candidate_geometry"] for r in rows]),
            "covariance_max_absolute_differences": np.stack([
                r["covariance_max_absolute_differences"] for r in rows]),
            "independent_animals": 8, "paired_sessions": 64, "geometry_coordinates": 64000,
            "qualification": False, "scientific_improvement": None,
            "limits": ["Candidate method execution and information-phase isolation are not attested.",
                       "Full geometry is a reconstruction finding, not a scalar to maximize.",
                       "Supporting readout differences do not establish the original paper's primary improvement claim."]}
