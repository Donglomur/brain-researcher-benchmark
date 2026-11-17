"""Operator-only staged readout/target release; never runtime qualification.

The complete original grid is retained. Stage A contains 64,000 readouts and
13,824 explicitly data-free GLM NONRESULTS. Stage B contains the real GLM and
covariance operands. The final join takes readouts exclusively from pinned A.

Overlapping draws require independently isolated, fresh participant contexts or
an independently qualified fixed-programme execution service. This module's
abstract adapter and hashed receipts describe that obligation, not its physical
enforcement. There is no qualified adapter in this release; EVERY artifact is
ineligible and isolation_qualified=False. A context ID or operator-supplied hash
is not proof of isolation. Source balanced-teacher selection uses all 500 labels
and is retained and disclosed; only the 300 training labels are delivered.

Trusted operator callbacks must authenticate their inputs, exclude concurrent
writers, and keep receipts, paths and full references outside participant access.
This is not a hostile-code sandbox. Numeric storage uses the unchanged frozen
collector runtime, including its compatible NumPy requirements.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import copy
from dataclasses import dataclass
from pathlib import Path
import re
import numpy as np
from dependency_loader import C, GB, GLB, K, P, R, V, need

GATE_CAP = 8192
JOIN_CAP = 8192
FALSE = {"isolation_qualified": False, "eligible": False}
IDENTITIES = ("row_ids", "unit_ids", "training_row_ids", "test_row_ids", "valid_teacher_indices")
A_SCHEMA = "population_stage_a_readout_v1"
NONRESULT_SCHEMA = "population_stage_a_glm_nonresult_v1"
B_SCHEMA = "population_stage_b_covariance_v1"
POLICY = "fresh_context_per_geometry_coordinate_no_shared_participant_state"
BALANCE = "source_valid_teacher_selection_uses_all_500_labels_unchanged"


def _hash(value):
    return C.digest(C.canonical(value))


def _sha(value):
    return GB.digest(value)


def _source_pins():
    here = C._directory(Path(__file__).resolve().parent)
    return {name: {"bytes": len(raw), "sha256": C.digest(raw)}
            for name in ("staged_delivery.py", "dependency_loader.py")
            for raw in (C._read(here / name, 1024 * 1024),)}


def make_protocol(*, method_sha256, operator_input_sha256, information_condition,
                  runtime_contract_sha256):
    base = C.make_binding(method_sha256=method_sha256,
                          operator_input_sha256=operator_input_sha256,
                          information_condition=information_condition)
    return {"schema": "population_staged_protocol_v1", "base_binding": base,
            "staged_source_pins": _source_pins(),
            "runtime_contract_sha256": _sha(runtime_contract_sha256),
            "context_policy": POLICY, "balanced_teacher_policy": BALANCE,
            "stage_a": "all_geometry_readouts_plus_data_free_glm_nonresults",
            "stage_b": "real_glm_and_covariance_operands_after_global_a_seal",
            "external_runtime_qualification_required": True, **FALSE}


def _protocol(protocol, expected_protocol_sha256):
    need(isinstance(protocol, dict) and isinstance(protocol.get("base_binding"), dict),
         "exact staged protocol required")
    base = protocol["base_binding"]
    expected = make_protocol(method_sha256=base.get("method_sha256"),
                             operator_input_sha256=base.get("operator_input_sha256"),
                             information_condition=base.get("information_condition"),
                             runtime_contract_sha256=protocol.get("runtime_contract_sha256"))
    need(protocol == expected and all(protocol[k] is False for k in FALSE)
         and protocol["base_binding"]["upstream_phase_isolation_attested"] is False
         and _hash(protocol) == _sha(expected_protocol_sha256),
         "staged protocol, source, method, condition or external pin differs")
    return copy.deepcopy(expected)


def stage_binding(protocol, stage, *, stage_a_sha256=None, gate_sha256=None,
                  stage_b_sha256=None):
    """Deterministic storage binding; callers still authenticate the protocol."""
    need(stage in ("a", "b", "joined"), "unknown delivery stage")
    if stage == "a":
        need(stage_a_sha256 is gate_sha256 is stage_b_sha256 is None, "stage A has no later-stage pins")
    else:
        _sha(stage_a_sha256)
        _sha(gate_sha256)
        need(stage_b_sha256 is None if stage == "b" else bool(_sha(stage_b_sha256)),
             "stage B/join pin differs")
    base = protocol["base_binding"]
    lineage = {"protocol_sha256": _hash(protocol), "stage": stage,
               "stage_a_sha256": stage_a_sha256, "gate_sha256": gate_sha256,
               "stage_b_sha256": stage_b_sha256}
    return C.make_binding(method_sha256=base["method_sha256"],
                          operator_input_sha256=_hash(lineage),
                          information_condition=base["information_condition"])


@dataclass(frozen=True)
class ContextLease:
    """Opaque operator handle plus declared provisioning evidence, NOT attestation."""
    context_id: str
    handle: object
    provision_evidence_sha256: str


@dataclass(frozen=True)
class RuntimeOutput:
    predictions: object
    execution_evidence_sha256: str


class FreshCoordinateRuntime(ABC):
    """Trusted adapter seam, requiring independent external qualification.

    Implementations must provision independent contexts with no retained state,
    caches, communications or filesystem access across coordinates, run the
    frozen programme, and close each context. This interface cannot establish
    those properties and provides NO qualification/promotion API. Evidence hashes
    must refer to independently reviewable external logs, not self-attestations.
    No operator loader, full reference, or target array is passed to this seam.
    """
    @abstractmethod
    def provision_fresh_context(self, request: dict) -> ContextLease:
        raise NotImplementedError

    @abstractmethod
    def run_fixed_programme(self, lease: ContextLease, observation: dict) -> RuntimeOutput:
        raise NotImplementedError

    @abstractmethod
    def close_context(self, lease: ContextLease) -> str:
        """Return a SHA256 pin to external teardown evidence; not a boolean."""
        raise NotImplementedError


def require_production_qualification(*args, **kwargs):
    raise ValueError("no independently qualified runtime adapter exists in this release")


def _public_observation(reference, coordinate, protocol):
    need(isinstance(reference, dict) and
         reference.get("schema") == "population_geometry_operator_reference_v1",
         "authenticated operator geometry reference required")
    job = GB._job(reference["job"])
    need(job == coordinate["job"] and P.geometry_id(job) == coordinate["id"],
         "operator geometry coordinate differs")
    points = np.asarray(reference["points"])
    need(points.shape == (500, 19) and points.dtype.kind in "fiu" and np.isfinite(points).all(),
         "original 500 by 19 neural points required")
    rows = R.identities(reference["row_ids"], 500, "row IDs")
    units = R.identities(reference["unit_ids"], 19, "unit IDs")
    train = R.indices(reference["training_positions"], 500, "training positions", count=300)
    test = R.indices(reference["test_positions"], 500, "test positions", count=200)
    need(np.array_equal(test, np.setdiff1d(np.arange(500), train)), "source ordered train/test partition differs")
    teachers = R.indices(reference["valid_teacher_indices"], 500, "valid teachers")
    need(100 < len(teachers) <= 500 and np.array_equal(teachers, np.sort(teachers)),
         "source balanced teacher identities differ")
    labels = np.asarray(reference["labels"])
    need(labels.shape == (500, len(teachers)) and labels.dtype.kind in "fiu", "source label matrix shape differs")
    training_labels = labels[train].copy()
    need(np.isfinite(training_labels).all() and np.isin(training_labels, (-1, 0, 1)).all(),
         "finite signed 300 training labels required")
    # Only these explicitly enumerated fields cross the participant boundary.
    return {"schema": "population_readout_observation_v1", "job_id": coordinate["id"],
            "method_sha256": protocol["base_binding"]["method_sha256"],
            "protocol_sha256": _hash(protocol), "neural_points": points.copy(),
            "row_ids": rows.copy(), "unit_ids": units.copy(),
            "training_row_ids": rows[train].copy(), "test_row_ids": rows[test].copy(),
            "training_positions": train.copy(), "test_positions": test.copy(),
            "valid_teacher_indices": teachers.copy(), "training_labels": training_labels,
            "balanced_teacher_policy": BALANCE}


def project_stage_a(reference, protocol, *, expected_protocol_sha256):
    protocol = _protocol(protocol, expected_protocol_sha256)
    coordinate = {"family": "geometry", "id": P.geometry_id(reference["job"]), "job": reference["job"]}
    return _public_observation(reference, coordinate, protocol)


def _predictions(value, teachers):
    a = np.asarray(value)
    need(a.shape == (200, teachers) and a.dtype.kind in "fiu" and np.isfinite(a).all()
         and np.isin(a, (-1, 0, 1)).all(), "exact 200 by valid-teacher signed readout predictions required")
    return a.copy()


def _nonresult(coordinate, protocol):
    return {"schema": NONRESULT_SCHEMA, "job_id": coordinate["id"],
            "method_sha256": protocol["base_binding"]["method_sha256"],
            "protocol_sha256": _hash(protocol), "status": "no_glm_inputs_or_result",
            "scientific_result": False, **FALSE}


def _request(observation, protocol, source_sha256):
    return {"schema": "population_fresh_context_request_v1", "job_id": observation["job_id"],
            "method_sha256": protocol["base_binding"]["method_sha256"],
            "protocol_sha256": _hash(protocol), "operator_input_sha256": protocol["base_binding"]["operator_input_sha256"],
            "source_revision": K.SOURCE_REVISION, "source_checkpoint_sha256": _sha(source_sha256),
            "runtime_contract_sha256": protocol["runtime_contract_sha256"],
            "observation_sha256": GB._value_identity(observation), "context_policy": POLICY, **FALSE}


def _context_id(value):
    need(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value),
         "bounded context identity required")
    return value


def collect_stage_a(root, geometry_loader, runtime, protocol, *, expected_protocol_sha256,
                    max_result_bytes, max_total_bytes):
    """Freeze readouts and declared NONRESULTS, with no GLM/reference exposure.

    Output receives engineering status only. Failure retains partial collector
    artifacts. Runtime provisioning/teardown are operator obligations, not proven
    by successful calls. The entire grid must complete before any Stage B gate.
    """
    protocol = _protocol(protocol, expected_protocol_sha256)
    need(isinstance(runtime, FreshCoordinateRuntime) and callable(geometry_loader),
         "explicit unqualified fresh-coordinate runtime adapter and geometry loader required")
    binding = stage_binding(protocol, "a")
    seen = set()

    def records():
        for coordinate in C.full_plan():
            if coordinate["family"] == "glm":
                candidate = _nonresult(coordinate, protocol)
            else:
                reference = geometry_loader(copy.deepcopy(coordinate["job"]))
                observation = _public_observation(reference, coordinate, protocol)
                request = _request(observation, protocol, reference["source_checkpoint_sha256"])
                # No reference/callback/raw target is retained in participant request.
                lease = runtime.provision_fresh_context(copy.deepcopy(request))
                need(type(lease) is ContextLease, "typed context lease required")
                try:
                    context = _context_id(lease.context_id)
                    need(context not in seen, "duplicate runtime context identity")
                    seen.add(context)
                    provision = _sha(lease.provision_evidence_sha256)
                    output = runtime.run_fixed_programme(lease, copy.deepcopy(observation))
                    need(type(output) is RuntimeOutput, "typed runtime output required")
                    predictions = _predictions(output.predictions, len(observation["valid_teacher_indices"]))
                    execution = _sha(output.execution_evidence_sha256)
                finally:
                    close = _sha(runtime.close_context(lease))
                receipt = {"schema": "population_runtime_evidence_receipt_v1", "request": request,
                           "context_id": context, "provision_evidence_sha256": provision,
                           "execution_evidence_sha256": execution, "close_evidence_sha256": close,
                           "prediction_sha256": GB._value_identity(predictions),
                           "external_independent_qualification_required": True, **FALSE}
                candidate = {"schema": A_SCHEMA, "job_id": coordinate["id"],
                             "method_sha256": binding["method_sha256"],
                             "protocol_sha256": expected_protocol_sha256,
                             **{k: observation[k].copy() for k in IDENTITIES},
                             "readout_predictions": predictions, "runtime_receipt": receipt, **FALSE}
            yield {"family": coordinate["family"], "id": coordinate["id"], "candidate": candidate}

    seal = C.freeze_submission(root, records(), binding, max_result_bytes=max_result_bytes,
                               max_total_bytes=max_total_bytes)
    return {**seal, "stage": "a", "readout_records": C.EXPECTED_COUNTS["geometry"],
            "glm_nonresults": C.EXPECTED_COUNTS["glm"], "evaluated_scientific_results": 0,
            "protocol_sha256": expected_protocol_sha256, "binding": binding, **FALSE}


def _candidate_identities(candidate):
    rows = R.identities(candidate["row_ids"], 500, "candidate rows")
    R.identities(candidate["unit_ids"], 19, "candidate units")
    train = R.identities(candidate["training_row_ids"], 300, "candidate training rows")
    test = R.identities(candidate["test_row_ids"], 200, "candidate test rows")
    need(not np.isin(train, test).any() and np.isin(train, rows).all() and np.isin(test, rows).all(),
         "candidate training/test identities do not partition original rows")
    expected_test = rows[~np.isin(rows, train)]
    need(np.array_equal(test, expected_test), "source test identity order differs")
    teachers = R.indices(candidate["valid_teacher_indices"], 500, "candidate valid teachers")
    need(100 < len(teachers) <= 500 and np.array_equal(teachers, np.sort(teachers)),
         "candidate valid teacher identities differ")
    return len(teachers)


def _validate_a(candidate, coordinate, protocol, seen):
    if coordinate["family"] == "glm":
        need(candidate == _nonresult(coordinate, protocol)
             and all(candidate[k] is False for k in (*FALSE, "scientific_result")),
             "stage A GLM records must be exact data-free NONRESULTS")
        return
    fields = {"schema", "job_id", "method_sha256", "protocol_sha256", "readout_predictions",
              "runtime_receipt", *IDENTITIES, *FALSE}
    need(isinstance(candidate, dict) and set(candidate) == fields and candidate["schema"] == A_SCHEMA
         and candidate["job_id"] == coordinate["id"]
         and candidate["method_sha256"] == protocol["base_binding"]["method_sha256"]
         and candidate["protocol_sha256"] == _hash(protocol)
         and all(candidate[k] is False for k in FALSE), "exact unqualified Stage A readout required")
    predictions = _predictions(candidate["readout_predictions"], _candidate_identities(candidate))
    receipt = candidate["runtime_receipt"]
    need(isinstance(receipt, dict) and set(receipt) == {"schema", "request", "context_id",
         "provision_evidence_sha256", "execution_evidence_sha256", "close_evidence_sha256",
         "prediction_sha256", "external_independent_qualification_required", *FALSE},
         "exact runtime evidence receipt required")
    need(receipt["schema"] == "population_runtime_evidence_receipt_v1"
         and receipt["external_independent_qualification_required"] is True
         and all(receipt[k] is False for k in FALSE), "runtime evidence cannot qualify isolation")
    context = _context_id(receipt["context_id"])
    need(context not in seen, "duplicate runtime context identity")
    seen.add(context)
    for key in ("provision_evidence_sha256", "execution_evidence_sha256", "close_evidence_sha256"):
        _sha(receipt[key])
    need(receipt["prediction_sha256"] == GB._value_identity(predictions), "readout output evidence differs")
    request = receipt["request"]
    need(isinstance(request, dict) and set(request) == {"schema", "job_id", "method_sha256",
         "protocol_sha256", "operator_input_sha256", "source_revision", "source_checkpoint_sha256",
         "runtime_contract_sha256", "observation_sha256", "context_policy", *FALSE}, "exact runtime request required")
    expected = {"schema": "population_fresh_context_request_v1", "job_id": coordinate["id"],
                "method_sha256": protocol["base_binding"]["method_sha256"], "protocol_sha256": _hash(protocol),
                "operator_input_sha256": protocol["base_binding"]["operator_input_sha256"],
                "source_revision": K.SOURCE_REVISION,
                "source_checkpoint_sha256": _sha(request["source_checkpoint_sha256"]),
                "runtime_contract_sha256": protocol["runtime_contract_sha256"],
                "observation_sha256": _sha(request["observation_sha256"]), "context_policy": POLICY, **FALSE}
    need(request == expected and all(request[k] is False for k in FALSE), "runtime request lineage differs")


def _read_candidates(root, binding, seal, max_result_bytes, max_total_bytes):
    root = C._directory(root)
    for coordinate, descriptor in C._descriptors(root, seal, max_total_bytes):
        yield coordinate, C._load_candidate(root, coordinate, descriptor, binding, max_result_bytes)


def verify_stage_a(root, protocol, *, expected_protocol_sha256, expected_complete_sha256,
                   max_result_bytes, max_total_bytes):
    protocol = _protocol(protocol, expected_protocol_sha256)
    binding = stage_binding(protocol, "a")
    seal = C.verify_submission(root, binding, expected_complete_sha256=expected_complete_sha256,
                               max_result_bytes=max_result_bytes, max_total_bytes=max_total_bytes)
    seen = set()
    for coordinate, candidate in _read_candidates(root, binding, seal, max_result_bytes, max_total_bytes):
        _validate_a(candidate, coordinate, protocol, seen)
    need(len(seen) == C.EXPECTED_COUNTS["geometry"], "entire Stage A readout census required")
    return seal


def _gate_doc(a_root, a_sha, protocol):
    return {"schema": "population_stage_b_operator_gate_v1", "stage_a_root": str(C._directory(a_root)),
            "stage_a_complete_sha256": _sha(a_sha), "protocol_sha256": _hash(protocol),
            "protocol": protocol, "stage_a_binding": stage_binding(protocol, "a"),
            "readout_records": C.EXPECTED_COUNTS["geometry"], "glm_nonresults": C.EXPECTED_COUNTS["glm"],
            "evaluated_scientific_results": 0, "both_stages_bound": True, **FALSE}


def _write_gate(path, document, cap):
    path = Path(path).absolute()
    C._directory(path.parent)
    need(not path.exists() and not path.is_symlink(), "create-only ordinary operator receipt required")
    raw = C.canonical(document) + b"\n"
    need(len(raw) <= cap, "operator receipt exceeds byte ceiling")
    C._write_exclusive(path, raw)
    return {"path": str(path), "sha256": C.digest(raw), "bytes": len(raw), **FALSE}


def create_stage_b_gate(gate_path, stage_a_root, protocol, *, expected_protocol_sha256,
                        expected_stage_a_sha256, max_result_bytes, max_total_bytes):
    """Complete A authentication and semantics before create-only engineering gate."""
    protocol = _protocol(protocol, expected_protocol_sha256)
    verify_stage_a(stage_a_root, protocol, expected_protocol_sha256=expected_protocol_sha256,
                   expected_complete_sha256=expected_stage_a_sha256,
                   max_result_bytes=max_result_bytes, max_total_bytes=max_total_bytes)
    return _write_gate(gate_path, _gate_doc(stage_a_root, expected_stage_a_sha256, protocol), GATE_CAP)


def _verify_gate(gate_path, protocol, expected_protocol_sha256, expected_gate_sha256,
                 max_result_bytes, max_total_bytes):
    protocol = _protocol(protocol, expected_protocol_sha256)
    path = Path(gate_path).absolute()
    C._directory(path.parent)
    raw = C._read(path, GATE_CAP)
    need(C.digest(raw) == _sha(expected_gate_sha256), "operator gate external pin differs")
    gate = C._json(raw)
    need(isinstance(gate, dict), "operator gate must be a mapping")
    expected = _gate_doc(gate.get("stage_a_root"), gate.get("stage_a_complete_sha256"), protocol)
    need(gate == expected and all(gate[k] is False for k in FALSE), "operator gate lineage or qualification differs")
    seal = verify_stage_a(gate["stage_a_root"], protocol, expected_protocol_sha256=expected_protocol_sha256,
                          expected_complete_sha256=gate["stage_a_complete_sha256"],
                          max_result_bytes=max_result_bytes, max_total_bytes=max_total_bytes)
    return gate, seal


def iter_stage_b_inputs(gate_path, protocol, loader, *, expected_protocol_sha256,
                        expected_gate_sha256, max_result_bytes, max_total_bytes):
    """Operator-only stream: no loader call until every A output passes.

    This makes no participant delivery/isolation claim. Caller must consume all
    coordinates; possession of the Python loader is an operator trust boundary.
    """
    need(callable(loader), "operator Stage B loader required")
    _verify_gate(gate_path, protocol, expected_protocol_sha256, expected_gate_sha256,
                 max_result_bytes, max_total_bytes)
    for coordinate in C.full_plan():
        yield {"coordinate": copy.deepcopy(coordinate),
               "payload": loader(coordinate["family"], copy.deepcopy(coordinate["job"])), **FALSE}


def _validate_b(candidate, coordinate, protocol):
    need(isinstance(candidate, dict) and candidate.get("job_id") == coordinate["id"]
         and candidate.get("method_sha256") == protocol["base_binding"]["method_sha256"],
         "Stage B method/coordinate differs")
    if coordinate["family"] == "glm":
        need(set(candidate) == GLB.CANDIDATE_KEYS and candidate["schema"] == "population_glm_candidate_v1",
             "actual raw GLM operands required; no placeholders or readout replacement")
        full = np.asarray(candidate["full_predictions"])
        need(full.ndim == 2 and full.shape[0] >= 10 and full.shape[1] > 0, "all GLM rows/units required")
        nrows, nunits = full.shape
        R.identities(candidate["row_ids"], nrows, "GLM rows")
        R.identities(candidate["unit_ids"], nunits, "GLM units")
        for value, shape in ((full, (nrows, nunits)), (candidate["alpha_oof_predictions"], (nrows, nunits, 10))):
            a = np.asarray(value)
            need(a.shape == shape and a.dtype.kind in "fiu" and np.isfinite(a).all() and (a > 0).all(),
                 "finite positive full/all-alpha GLM predictions required")
        folds = np.asarray(candidate["fold_ids"])
        need(folds.dtype.kind in "iu" and np.array_equal(folds, V.source_fold_ids(nrows)), "source ten-fold assignments required")
        alphas = np.asarray(candidate["selected_alpha_indices"])
        need(alphas.shape == (nunits,) and alphas.dtype.kind in "iu" and ((0 <= alphas) & (alphas < 10)).all(),
             "original ten-alpha selected identities required")
    else:
        need(set(candidate) == GB.FIELDS - {"readout_predictions"} and candidate["schema"] == B_SCHEMA,
             "exact covariance-only Stage B fields required; replacement readouts forbidden")
        _candidate_identities(candidate)
        cov = np.asarray(candidate["joint_covariance"])
        need(cov.shape == (23, 23) and cov.dtype.kind in "fiu" and np.isfinite(cov).all()
             and np.array_equal(cov, cov.T), "finite symmetric 23 by 23 joint covariance required")


def freeze_stage_b(root, records, gate_path, protocol, *, expected_protocol_sha256,
                   expected_gate_sha256, max_result_bytes, max_total_bytes):
    gate, _ = _verify_gate(gate_path, protocol, expected_protocol_sha256, expected_gate_sha256,
                           max_result_bytes, max_total_bytes)
    binding = stage_binding(protocol, "b", stage_a_sha256=gate["stage_a_complete_sha256"],
                            gate_sha256=expected_gate_sha256)

    def checked():
        expected = iter(C.full_plan())
        for item in records:
            coordinate = next(expected, None)
            need(coordinate is not None and isinstance(item, dict) and set(item) == {"family", "id", "candidate"}
                 and item["family"] == coordinate["family"] and item["id"] == coordinate["id"], "Stage B complete grid order differs")
            _validate_b(item["candidate"], coordinate, protocol)
            yield item
        need(next(expected, None) is None, "Stage B complete grid required")

    seal = C.freeze_submission(root, checked(), binding, max_result_bytes=max_result_bytes,
                               max_total_bytes=max_total_bytes)
    return {**seal, "binding": binding, "stage": "b", **FALSE}


def join_stages(root, stage_b_root, gate_path, protocol, *, expected_protocol_sha256,
                expected_gate_sha256, expected_stage_b_sha256, max_result_bytes, max_total_bytes):
    """Create unchanged phase15 candidate schema, taking readouts ONLY from A.

    Full A and B integrity scans complete before creating the joined submission.
    Scores remain evaluator-derived later; no scientific outcome is asserted.
    The joined storage operator-input hash binds both stages and the global gate.
    max_total_bytes covers new joined artifacts including JOIN.json, separately
    from each already existing input package's validated byte ceiling.
    """
    gate, a_seal = _verify_gate(gate_path, protocol, expected_protocol_sha256, expected_gate_sha256,
                               max_result_bytes, max_total_bytes)
    a_binding = stage_binding(protocol, "a")
    b_binding = stage_binding(protocol, "b", stage_a_sha256=gate["stage_a_complete_sha256"], gate_sha256=expected_gate_sha256)
    b_seal = C.verify_submission(stage_b_root, b_binding, expected_complete_sha256=expected_stage_b_sha256,
                                 max_result_bytes=max_result_bytes, max_total_bytes=max_total_bytes)
    # Semantic validation also completes before output creation, not just hashes.
    for coordinate, candidate in _read_candidates(stage_b_root, b_binding, b_seal, max_result_bytes, max_total_bytes):
        _validate_b(candidate, coordinate, protocol)
    binding = stage_binding(protocol, "joined", stage_a_sha256=gate["stage_a_complete_sha256"],
                            gate_sha256=expected_gate_sha256, stage_b_sha256=expected_stage_b_sha256)
    root = Path(root).absolute()
    C._directory(root.parent)
    need(not root.exists() and not root.is_symlink(), "fresh joined destination required")
    C._limits(max_result_bytes, max_total_bytes - JOIN_CAP)
    root.mkdir(mode=0o700)

    def records():
        aa = _read_candidates(gate["stage_a_root"], a_binding, a_seal, max_result_bytes, max_total_bytes)
        bb = _read_candidates(stage_b_root, b_binding, b_seal, max_result_bytes, max_total_bytes)
        sentinel = object()
        for ca, a in aa:
            item = next(bb, sentinel)
            need(item is not sentinel, "Stage B ended before Stage A")
            cb, b = item
            need(ca == cb, "stage coordinate identity differs")
            if ca["family"] == "geometry":
                for key in IDENTITIES:
                    GB._same(b[key], a[key], "joined " + key)
                b = {**b, "schema": GB.SCHEMA, "readout_predictions": a["readout_predictions"].copy()}
            yield {"family": ca["family"], "id": ca["id"], "candidate": b}
        need(next(bb, sentinel) is sentinel, "extra Stage B output")

    final = C.freeze_submission(root / "submission", records(), binding, max_result_bytes=max_result_bytes,
                                max_total_bytes=max_total_bytes - JOIN_CAP)
    receipt = {"schema": "population_staged_join_v1", "protocol_sha256": expected_protocol_sha256,
               "protocol": protocol, "stage_a_sha256": gate["stage_a_complete_sha256"],
               "stage_b_sha256": expected_stage_b_sha256, "gate_sha256": expected_gate_sha256,
               "joined_complete_sha256": final["complete_sha256"], "joined_binding": binding,
               "readout_source": "exclusively_pinned_stage_a", "evaluated_scientific_results": 0, **FALSE}
    pin = _write_gate(root / "JOIN.json", receipt, JOIN_CAP)
    return {"submission_root": str(root / "submission"), "complete_sha256": final["complete_sha256"],
            "join_receipt": pin, "binding": binding,
            "cumulative_logical_write_bytes": final["cumulative_logical_write_bytes"] + pin["bytes"], **FALSE}
