"""Exact paired primary/sensitivity scoring for the current NEURAL-046 endpoint.

The caller owns protected storage and closure provenance. This API does not run
models, load an authentic corpus, or replace the historical mean-response scorer.
"""
from copy import deepcopy
import hashlib
import importlib
import importlib.util
from pathlib import Path
import sys


SOURCE = Path(__file__).resolve().parents[4] / "shared/reward-spacing/programme/neural"
PINS = {
    "neuro/__init__.py": "a562b40999bbe86e85b19a67677018b2655de20d5a515f959576c66948b7a227",
    "neuro/base.py": "ce5d68bf69cddba7dc2bc018efd54707649eef7f44002600b2f7fdd700fd5ae9",
    "neuro/reward_common.py": "dd446a2dde9ce45163bf10985f48e7657dd24f30b14660a271a7baadea39c6fc",
    "neuro/contracts.py": "ae87304869db8f233ce8edfe90f0349784ece77ab3d8e289bd79dc0d0b34b64e",
    "neuro/models.py": "d58b875a3a165ed2f8055863302c1150397a79acc1d4a73e8901a489f3657394",
    "neuro/scoring.py": "0bb78d584082c259e6b88e7987fd2c14d7d3334075d96f7a93c758a6f973f722",
    "spec/APPLICABILITY_MATRIX.json": "2eba66c4f00b446bd33918fa76e90dfb45fc3fb3ffd1221df2a1f3c531f3e00e",
    "spec/PACKET_DECLARATIVE_SPEC.json": "162e1beda900010ac6c4d14a1b30f2d642c92a8768db7664956f8c9a15461a8d",
}


def _load_source():
    for relative, expected in PINS.items():
        path = SOURCE / relative
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            raise ValueError("linked scoring source")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("scoring source changed: " + relative)
    name = "_neural046_joined_source_v1"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, SOURCE / "neuro/__init__.py",
            submodule_search_locations=[str(SOURCE / "neuro")])
        package = importlib.util.module_from_spec(spec)
        sys.modules[name] = package
        spec.loader.exec_module(package)
    elif Path(sys.modules[name].__file__).resolve() != SOURCE / "neuro/__init__.py":
        raise ValueError("scoring namespace collision")
    return importlib.import_module(name + ".scoring")


shared = _load_source()
require, finite, digest = shared.require, shared.finite, shared.digest
IDENTITY = ("id", "animal", "session", "condition", "endpoint", "domain")


def _identity(row):
    require(type(row) is dict and all(k in row for k in IDENTITY), "private_case_metadata")
    value = {k: row[k] for k in IDENTITY}
    require(all(type(v) is str and v for v in value.values()), "case_metadata_strings")
    return value


def _binding(public, binding, control):
    """Check the operator's preparation-time identity map without target access."""
    query = public["query"]
    require(type(binding) is dict and set(binding) == {r["id"] for r in query},
            "exact_case_binding")
    native_ids, animals, sessions, animal_conditions = set(), {}, {}, {}
    for exposed in query:
        row = binding[exposed["id"]]
        require(set(row) == set(IDENTITY), "binding_fields")
        native = _identity(row)
        require(native["id"] not in native_ids, "duplicate_native_case")
        native_ids.add(native["id"])
        require(native["endpoint"] == public["endpoint"], "binding_endpoint")
        require(native["condition"] == exposed["condition"], "binding_condition")
        for field, mapping in (("animal", animals), ("session", sessions)):
            key, value = exposed[field], native[field]
            require(type(key) is str and key, "public_identity")
            require(key not in mapping or mapping[key] == value, "inconsistent_opaque_" + field)
            mapping[key] = value
        animal = native["animal"]
        condition = (native["condition"], native["domain"])
        require(animal not in animal_conditions or animal_conditions[animal] == condition,
                "animal_condition_inconsistent")
        animal_conditions[animal] = condition
        if control != "opaque_ID":
            require(all(exposed[k] == native[k] for k in ("id", "animal", "session")),
                    "nonopaque_identity_binding")
    require(len(set(animals.values())) == len(animals), "opaque_animal_alias_collision")
    require(len(set(sessions.values())) == len(sessions), "opaque_session_alias_collision")


def score_joined(public, submission, sensitivity_predictions, binding, closure, load_private):
    """Score primary and mandatory sensitivity on one complete bound target set.

    `binding` is operator-only metadata keyed by public query ID, frozen at
    preparation. `closure` must commit all four inputs before `load_private` is
    called. The callback returns the original prepared query rows in any order.
    A trusted operator must establish the truth of closure, source provenance,
    and the private artifact's own hash; this callable is not a hostile sandbox.
    """
    public, submission, sensitivity_predictions, binding, closure = deepcopy(
        (public, submission, sensitivity_predictions, binding, closure))
    require(public["task"] == "NEURAL-046", "task")
    require(closure.get("all_required_producers_closed") is True and
            closure.get("all_required_artifacts_sealed") is True and
            closure.get("private_targets_opened_before_closure") is False,
            "target_last_closure_required")
    for key, value in (("public_digest", public), ("submission_digest", submission),
                       ("sensitivity_digest", sensitivity_predictions), ("binding_digest", binding)):
        require(closure.get(key) == digest(value), "closure_" + key)
    cell = shared.validate_submission(submission, public)
    _binding(public, binding, cell["control"])
    expected = {"MEN_independently_tuned"} if "MEN" in cell["NEURAL-046"]["models_produced"] else set()
    require(type(sensitivity_predictions) is dict and set(sensitivity_predictions) == expected,
            "sensitivity_backfill")
    query_ids = set(binding)
    for predictions in sensitivity_predictions.values():
        require(type(predictions) is dict and set(predictions) == query_ids, "sensitivity_case_join")
        for value in predictions.values():
            finite(value, "sensitivity_prediction")
    require(callable(load_private), "private_loader")
    hidden = load_private()
    require(type(hidden) is list and len(hidden) == len(query_ids), "private_case_count")
    by_id = {}
    for row in hidden:
        identity = _identity(row)
        require(identity["id"] not in by_id, "duplicate_private_case")
        by_id[identity["id"]] = row
    require(set(by_id) == {r["id"] for r in binding.values()}, "private_case_identity")
    aligned = []
    for exposed in public["query"]:
        native = binding[exposed["id"]]
        row = by_id[native["id"]]
        require(_identity(row) == native, "private_metadata_changed")
        finite(row["target"], "private_target")
        aligned.append(row)
    # Both calls receive the very same checked, complete ordering. No model,
    # target, animal or endpoint can be silently omitted by zip truncation.
    result = shared.score(submission, public, aligned, closure)
    result["mandatory_sensitivity"] = shared.score_sensitivities(
        sensitivity_predictions, public, aligned)
    result["paired_join"] = {
        "schema": "neural046_complete_join_v1", "binding_digest": digest(binding),
        "query_cases": len(aligned), "animals": len({r["animal"] for r in aligned}),
        "sensitivity_digest": digest(sensitivity_predictions),
        "private_order": "aligned_by_committed_case_identity",
    }
    return result
