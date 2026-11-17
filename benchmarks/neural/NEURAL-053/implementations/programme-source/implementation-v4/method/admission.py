"""Protected operator admission boundary; no function mints scientific authority.

The operator must supply independently verified current bindings and an exact
registry pin from outside the candidate namespace. Matching files/JSON are not
OS isolation or independent review. Actual runtime qualification remains external.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import stat

from .plan import canonical_bytes, digest, evaluate, validate_plan_object


class AdmissionError(ValueError):
    pass


ARTIFACTS = frozenset({
    "design", "math", "method", "selection", "plan", "state", "source_closure",
    "evaluator", "admission", "dependencies", "environment", "training_features",
    "training_labels", "training_groups", "fit_support", "inner_support",
    "selection_lineage", "refit_support", "random_lineage", "trained_tools",
    "query_descriptor", "query_artifact", "input_admission", "runtime_qualification",
    "namespace_qualification", "resource_qualification", "challenge_process", "method_review",
})
QUALIFICATIONS = frozenset({"runtime_qualification", "namespace_qualification",
                            "resource_qualification", "challenge_process", "method_review"})
CHALLENGES = ("scalar_anchors", "ordered", "reversed", "permuted", "partitioned",
              "duplicated", "fresh_repeat", "after_repeat")
ARMS = {"neural": 542, "ocular": 6, "joint": 548, "neural_availability": 271}


def _sha(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise AdmissionError("invalid SHA256 identity")
    return value


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise AdmissionError("missing or unexpected admission fields")


def _pin(value):
    _keys(value, {"bytes", "sha256"})
    if type(value["bytes"]) is not int or value["bytes"] < 0:
        raise AdmissionError("invalid artifact byte extent")
    _sha(value["sha256"])


def byte_identity(data):
    if type(data) is not bytes:
        raise AdmissionError("expected immutable bytes")
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def file_identity(path, *, max_bytes=2097152):
    """Bounded source/registry read. Do not use on keys or unapproved data files."""
    path = Path(path)
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_size > max_bytes:
        raise AdmissionError("source/registry must be a bounded regular file")
    data = path.read_bytes()
    if len(data) != s.st_size:
        raise AdmissionError("source changed during read")
    return byte_identity(data)


def current_engine_identities():
    here = Path(__file__)
    return {"admission": file_identity(here), "evaluator": file_identity(here.with_name("plan.py"))}


@dataclass(frozen=True, slots=True)
class TrustedRegistry:
    """Exact operator-pinned registry, not candidate-provided self-approval.

    Python object privacy is not a security boundary. Only the separately
    qualified operator process may choose the expected pin or provide bindings.
    """
    encoded: bytes
    expected_sha256: str

    @classmethod
    def from_file(cls, path, *, expected_bytes, expected_sha256):
        _sha(expected_sha256)
        p = Path(path)
        st = p.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_size != expected_bytes or not 0 < expected_bytes <= 2097152:
            raise AdmissionError("registry type/extent mismatch")
        data = p.read_bytes()
        if len(data) != expected_bytes or hashlib.sha256(data).hexdigest() != expected_sha256:
            raise AdmissionError("registry identity mismatch")
        result = cls(data, expected_sha256)
        result.document()
        return result

    def document(self):
        if type(self.encoded) is not bytes or hashlib.sha256(self.encoded).hexdigest() != self.expected_sha256:
            raise AdmissionError("stale registry identity")
        try:
            obj = json.loads(self.encoded)
        except (ValueError, UnicodeError) as exc:
            raise AdmissionError("invalid registry JSON") from exc
        _keys(obj, {"schema", "task_id", "profile", "approved_receipts", "approved_qualifications"})
        if obj["schema"] != "neural053_trusted_admission_registry_v1" or obj["task_id"] != "NEURAL-053":
            raise AdmissionError("registry scope mismatch")
        if obj["profile"] not in {"canonical", "invented_engineering"}:
            raise AdmissionError("unknown registry profile")
        for key in ("approved_receipts", "approved_qualifications"):
            if type(obj[key]) is not list or len(set(obj[key])) != len(obj[key]):
                raise AdmissionError("invalid registry allowlist")
            for x in obj[key]: _sha(x)
        return obj


def validate_bindings(bindings, plan, *, required_profile="canonical"):
    _keys(bindings, {"schema", "task_id", "profile", "context", "input_dim", "class_count",
                     "query_rows", "backend", "entrypoint", "artifacts"})
    if bindings["schema"] != "neural053_method_bindings_v2" or bindings["task_id"] != "NEURAL-053":
        raise AdmissionError("binding schema/task mismatch")
    if required_profile not in {"canonical", "invented_engineering"} or bindings["profile"] != required_profile:
        raise AdmissionError("engineering evidence cannot qualify canonical execution")
    context = bindings["context"]
    _keys(context, {"fold_token", "arm", "mode", "replication", "attempt_id", "reference_family", "comparison_scope"})
    for key in ("fold_token", "attempt_id", "comparison_scope"):
        if type(context[key]) is not str or not context[key]:
            raise AdmissionError("empty context identity")
    if context["arm"] not in ARMS or context["mode"] not in {"fixed_program", "training_investigation", "independent_reference"}:
        raise AdmissionError("unknown arm/mode")
    if context["mode"] == "independent_reference":
        if context["replication"] is not None or context["reference_family"] not in {"ridge", "lda", "fourier_ridge", "centroid"}:
            raise AdmissionError("reference context mismatch")
    elif type(context["replication"]) is not int or context["replication"] not in (0, 1, 2) or context["reference_family"] is not None:
        raise AdmissionError("author replication mismatch")
    for field in ("input_dim", "class_count", "query_rows"):
        if type(bindings[field]) is not int or bindings[field] < 1:
            raise AdmissionError("invalid numerical extent")
    if bindings["input_dim"] != plan.input_dim or bindings["class_count"] != plan.class_count:
        raise AdmissionError("plan input/output extent mismatch")
    if required_profile == "canonical" and (plan.input_dim != ARMS[context["arm"]] or plan.class_count != 1854 or bindings["query_rows"] != 3708):
        raise AdmissionError("incomplete canonical query support")
    if bindings["backend"] not in {"scalar", "vectorized"} or bindings["entrypoint"] != "method.plan:evaluate":
        raise AdmissionError("unsupported or alternate entrypoint")
    artifacts = bindings["artifacts"]
    _keys(artifacts, ARTIFACTS)
    for value in artifacts.values(): _pin(value)
    if artifacts["plan"] != byte_identity(plan.encoded):
        raise AdmissionError("plan pin mismatch")
    state_bytes = canonical_bytes(json.loads(plan.encoded)["constants"])
    if artifacts["state"] != byte_identity(state_bytes):
        raise AdmissionError("state pin mismatch")
    for name, value in current_engine_identities().items():
        if artifacts[name] != value:
            raise AdmissionError("current evaluator/admission source changed")


def validate_admission(receipt, current_bindings, registry, plan, *, required_profile="canonical"):
    """Reject before query access. Current bindings must come from trusted custody.

    The caller independently authenticates every current artifact/support manifest;
    this gate compares the complete exact set and directly rechecks its own engine.
    It cannot prove a supplied source-closure manifest is complete by hashing it.
    """
    if type(registry) is not TrustedRegistry:
        raise AdmissionError("operator-pinned registry required")
    trusted = registry.document()
    if trusted["profile"] != required_profile:
        raise AdmissionError("registry profile mismatch")
    _keys(receipt, {"schema", "bindings", "review", "challenges"})
    if receipt["schema"] != "neural053_method_admission_v2":
        raise AdmissionError("unsupported admission receipt")
    receipt_digest = digest(receipt)
    if receipt_digest not in trusted["approved_receipts"]:
        raise AdmissionError("receipt has no independent operator approval")
    plan = validate_plan_object(plan)
    validate_bindings(current_bindings, plan, required_profile=required_profile)
    if canonical_bytes(receipt["bindings"]) != canonical_bytes(current_bindings):
        raise AdmissionError("stale or mismatched source/state/support/context")
    for name in QUALIFICATIONS:
        if current_bindings["artifacts"][name]["sha256"] not in trusted["approved_qualifications"]:
            raise AdmissionError("missing independent qualification: " + name)
    review = receipt["review"]
    _keys(review, {"author_id", "reviewer_id", "decision", "reviewed_bindings_sha256",
                   "row_local_reasoning", "source_closure_complete", "no_query_values",
                   "supported_operations"})
    if (type(review["author_id"]) is not str or not review["author_id"] or
        type(review["reviewer_id"]) is not str or not review["reviewer_id"] or
        review["reviewer_id"] == review["author_id"] or review["decision"] != "accepted" or
        review["source_closure_complete"] is not True or review["no_query_values"] is not True or
        type(review["row_local_reasoning"]) is not str or not review["row_local_reasoning"].strip() or
        review["supported_operations"] != list(plan.operations) or
        review["reviewed_bindings_sha256"] != digest(current_bindings)):
        raise AdmissionError("unsupported or nonindependent method review")
    challenge = receipt["challenges"]
    _keys(challenge, {"schema", "profile", "backend", "plan_sha256", "state_sha256",
                     "training_support_sha256", "selected_ids_sha256", "rows", "results",
                     "source_before", "source_after", "state_before", "state_after",
                     "query_values_used", "numerical_checks_only"})
    if (challenge["schema"] != "neural053_training_only_challenges_v2" or
        challenge["profile"] != required_profile or challenge["backend"] != current_bindings["backend"] or
        challenge["plan_sha256"] != plan.digest or challenge["state_sha256"] != plan.state_digest or
        challenge["training_support_sha256"] != current_bindings["artifacts"]["fit_support"]["sha256"] or
        challenge["query_values_used"] is not False or challenge["numerical_checks_only"] is not True or
        challenge["source_before"] != {x: current_bindings["artifacts"][x] for x in ("admission", "evaluator")} or
        challenge["source_after"] != challenge["source_before"] or
        challenge["state_before"] != plan.state_digest or challenge["state_after"] != plan.state_digest):
        raise AdmissionError("challenge support/source/state mismatch")
    _sha(challenge["selected_ids_sha256"])
    rows = challenge["rows"]
    if type(rows) is not int or rows < 2 or (required_profile == "canonical" and rows != 64):
        raise AdmissionError("incomplete training-only challenge support")
    results = challenge["results"]
    if type(results) is not list or [x.get("name") for x in results if type(x) is dict] != list(CHALLENGES):
        raise AdmissionError("missing or reordered consistency challenges")
    import math
    for result in results:
        _keys(result, {"name", "rows", "max_abs_difference", "max_tolerance_excess", "finite_probabilities"})
        expected_rows = rows * (2 if result["name"] == "duplicated" else 1)
        if result["rows"] != expected_rows or result["finite_probabilities"] is not True:
            raise AdmissionError("invalid challenge extent/probabilities")
        for field in ("max_abs_difference", "max_tolerance_excess"):
            if type(result[field]) not in (int, float) or not math.isfinite(result[field]):
                raise AdmissionError("invalid challenge discrepancy")
        if (not 0 <= result["max_abs_difference"] <= 1.1e-6 or
            not -1.1e-6 <= result["max_tolerance_excess"] <= 0):
            raise AdmissionError("consistency challenge failed")
    return {"receipt_sha256": receipt_digest, "bindings_sha256": digest(current_bindings),
            "profile": required_profile, "backend": current_bindings["backend"]}


def execute_admitted(receipt, current_bindings, registry, plan, query_loader, *, required_profile="canonical"):
    """Gate first; then the trusted loader, exact evaluator and post-source check.

    Query custody/type/order/artifact validation is the trusted loader's contract.
    No user-provided inference callback is accepted. Protected grading is elsewhere.
    """
    admitted = validate_admission(receipt, current_bindings, registry, plan, required_profile=required_profile)
    # Freeze all operands before the trusted loader runs; a loader cannot switch
    # the reviewed backend or expected shape through caller-owned mutable dicts.
    frozen = json.loads(canonical_bytes(current_bindings))
    matrix = query_loader()
    if getattr(matrix, "shape", None) != (frozen["query_rows"], frozen["input_dim"]):
        raise AdmissionError("query matrix does not have complete admitted support")
    result = evaluate(plan, matrix, backend=frozen["backend"])
    if current_engine_identities() != {x: frozen["artifacts"][x] for x in ("admission", "evaluator")}:
        raise AdmissionError("source changed during prediction")
    validate_plan_object(plan)
    if digest(current_bindings) != admitted["bindings_sha256"]:
        raise AdmissionError("operator bindings mutated during prediction")
    return result, admitted


def run_training_challenges(plan, training_matrix, training_ids, *, training_support_sha256,
                            backend="vectorized", profile="canonical", engineering_rows=4):
    """Numerical evidence only; cannot create a registry approval or runtime receipt."""
    import numpy as np
    plan = validate_plan_object(plan)
    _sha(training_support_sha256)
    if profile not in {"canonical", "invented_engineering"}:
        raise AdmissionError("unknown challenge profile")
    count = 64 if profile == "canonical" else engineering_rows
    if type(count) is not int or count < 2 or count > 64:
        raise AdmissionError("invalid challenge row count")
    ids = list(training_ids)
    if len(set(ids)) != len(ids) or any(type(x) is not str or not x for x in ids):
        raise AdmissionError("training IDs must be unique opaque strings")
    matrix = np.asarray(training_matrix, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape != (len(ids), plan.input_dim) or len(ids) < count or not np.isfinite(matrix).all():
        raise AdmissionError("incomplete finite allowed training support")
    rank = lambda prefix, value: (hashlib.sha256((prefix + value).encode("utf-8")).digest(), value.encode("utf-8"))
    order = sorted(range(len(ids)), key=lambda i: rank("NEURAL-053/method-admission-v2/probe/", ids[i]))[:count]
    chosen = [ids[i] for i in order]
    x = matrix[order]
    before = current_engine_identities()
    anchor = evaluate(plan, x, backend="scalar")
    results = []

    def check(name, actual, mapping):
        expected = anchor[mapping]
        difference = np.abs(actual - expected)
        excess = difference - (1e-7 + 1e-6 * np.abs(expected))
        good = actual.shape == expected.shape and np.isfinite(actual).all() and np.all(actual >= 0) and np.all(actual <= 1) and np.all(np.abs(actual.sum(axis=1) - 1) <= 1e-6)
        record = {"name": name, "rows": len(mapping), "max_abs_difference": float(difference.max()),
                  "max_tolerance_excess": float(excess.max()), "finite_probabilities": bool(good)}
        results.append(record)
        if not good or record["max_tolerance_excess"] > 0:
            raise AdmissionError("training-only challenge failed: " + name)

    check("scalar_anchors", anchor, list(range(count)))
    check("ordered", evaluate(plan, x, backend=backend), list(range(count)))
    rev = list(reversed(range(count)))
    check("reversed", evaluate(plan, x[rev], backend=backend), rev)
    perm = sorted(range(count), key=lambda i: rank("NEURAL-053/method-admission-v2/permute/", chosen[i]))
    check("permuted", evaluate(plan, x[perm], backend=backend), perm)
    partitioned = np.concatenate([evaluate(plan, x[start:start+7], backend=backend) for start in range(0, count, 7)])
    check("partitioned", partitioned, list(range(count)))
    dup = list(range(count)) * 2
    check("duplicated", evaluate(plan, x[dup], backend=backend), dup)
    # RowPlan contains only immutable bytes; re-admission constructs a fresh
    # interpreter state for every call. Process/namespace independence is external.
    from .plan import load_plan
    fresh = load_plan(json.loads(plan.encoded))
    check("fresh_repeat", evaluate(fresh, x, backend=backend), list(range(count)))
    check("after_repeat", evaluate(plan, x, backend=backend), list(range(count)))
    after = current_engine_identities()
    if before != after or validate_plan_object(plan).state_digest != plan.state_digest:
        raise AdmissionError("source or state changed during challenges")
    return {"schema": "neural053_training_only_challenges_v2", "profile": profile, "backend": backend,
            "plan_sha256": plan.digest, "state_sha256": plan.state_digest,
            "training_support_sha256": training_support_sha256, "selected_ids_sha256": digest(chosen),
            "rows": count, "results": results, "source_before": before, "source_after": after,
            "state_before": plan.state_digest, "state_after": plan.state_digest,
            "query_values_used": False, "numerical_checks_only": True}
