"""Descriptive paired retinal assessment with unbound scientific qualification.

Public layout: implementations/retinal-paired-episode-v1/{paired_assessment,
paired_episode}.py alongside the unchanged retinal-heldout and registered-runtime
implementations. Source roots are trusted operator configuration, never fields
of candidate, episode, or policy JSON. This revision binds no policy evaluator
or enforcing transport adapter and therefore cannot issue a scientific win.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import threading
import types


SCHEMA = "jaxley-paired-retinal-assessment-v1"
LEGACY_PINS = {
    "retinal-heldout/score.py": (10745, "b2ac5156fe01d600d32b35e0bbf716bd6dea69f59b6bd3a062a6a6c2b0bb126c"),
    "registered-runtime/programme/scientific/retina_model.py": (13596, "102830b9474dff42c9dcb938d1fd463bb26934e0b22bc70f42f9febccac0993f"),
    "registered-runtime/programme/scientific/retina_inputs.py": (14403, "a9724675ee673f211cbb3cec0b7e5411a3c40913a3799a009c24d6d7d5e18e83"),
}
# Immutable sibling episode source; participant JSON cannot change this pin.
EPISODE_PIN = (25944, "563bbf84b2efce0a9beffabbef6308ce40cd1d6bcd4921f0492984a33d7d6e14")
_SOURCE_LOCK = threading.RLock()
_METRIC_PACKAGE = "_jaxley_retinal_heldout_102830b9474d"


class AssessmentError(ValueError):
    """An assessment source, transport envelope, or JSON boundary was invalid."""

    def __init__(self, code, path=""):
        self.code, self.path = code, path
        super().__init__(code + (":" + path if path else ""))


def _require(condition, code, path=""):
    if not condition:
        raise AssessmentError(code, path)


def _digest(value):
    try:
        body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise AssessmentError("json:not_canonical") from exc
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _read_source(path, pin):
    """Read exactly a pinned regular source file; do not trust an import search."""
    path = Path(path)
    size, expected = pin
    _require(type(size) is int and 0 < size <= 131072 and len(expected) == 64,
             "source:unsealed", path.name)
    before = path.lstat()
    _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             not before.st_mode & 0o022, "source:custody", path.name)
    _require(before.st_size == size, "source:size", path.name)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        _require(_stamp(os.fstat(fd)) == _stamp(before), "source:open_changed", path.name)
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(size + 1)
        _require(_stamp(os.fstat(fd)) == _stamp(before) == _stamp(path.lstat()),
                 "source:changed", path.name)
    finally:
        os.close(fd)
    _require(len(body) == size and hashlib.sha256(body).hexdigest() == expected,
             "source:digest", path.name)
    return body


def _module_from_body(name, path, body, package=None):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = package
    exec(compile(body, str(path), "exec", dont_inherit=True), module.__dict__)
    return module


@contextmanager
def _legacy_module(implementations_root):
    """Execute authenticated, unchanged sources in their original relative tree.

    The legacy metric loader uses a fixed private package. Populate that namespace
    from the authenticated exact bytes for this call, then restore any prior
    occupants. A previously imported or poisoned cache cannot replace the metric.
    No numerical function is copied, rewritten, or substituted.
    """
    root = Path(implementations_root).resolve(strict=True)
    bodies = {rel: _read_source(root / rel, pin) for rel, pin in LEGACY_PINS.items()}
    names = (_METRIC_PACKAGE, _METRIC_PACKAGE + ".retina_inputs",
             _METRIC_PACKAGE + ".retina_model")
    absent = object()
    saved = {name: sys.modules.get(name, absent) for name in names}
    try:
        package = types.ModuleType(_METRIC_PACKAGE)
        directory = root / "registered-runtime/programme/scientific"
        package.__path__ = [str(directory)]
        sys.modules[_METRIC_PACKAGE] = package
        for stem in ("retina_inputs", "retina_model"):
            rel = "registered-runtime/programme/scientific/" + stem + ".py"
            name = _METRIC_PACKAGE + "." + stem
            module = _module_from_body(name, root / rel, bodies[rel], _METRIC_PACKAGE)
            sys.modules[name] = module
        rel = "retinal-heldout/score.py"
        yield _module_from_body("_jaxley_paired_retinal_frozen_score", root / rel, bodies[rel])
    finally:
        for name in names:
            if saved[name] is absent:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = saved[name]


def _episode_module(episode_source_root):
    path = Path(episode_source_root).resolve(strict=True) / "paired_episode.py"
    body = _read_source(path, EPISODE_PIN)
    return _module_from_body("_jaxley_paired_retinal_frozen_episode", path, body)


def _pin_descriptor(value, field):
    _require(type(value) is dict and set(value) == {"bytes", "sha256"},
             "policy:descriptor_keys", field)
    _require(type(value["bytes"]) is int and 0 < value["bytes"] <= 1048576,
             "policy:descriptor_bytes", field)
    sha = value["sha256"]
    _require(type(sha) is str and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha),
             "policy:descriptor_sha256", field)


def inspect_policy_precommit(policy_precommit):
    """Describe a claimed commitment without treating JSON as trusted authority.

    No artifact path, import, callable, threshold, uncertainty procedure, or
    acceptance criterion is read or executed. A later selected policy requires
    an authenticated operator commitment chronology and a separately implemented
    decision rule. Neither is supplied by this source-only revision.
    """
    if policy_precommit is None:
        return {"status": "MISSING", "metadata_sha256": None,
                "authority_verified": False, "chronology_verified": False,
                "scientific_rule_bound": False,
                "reasons": ["POLICY_PRECOMMIT_MISSING", "SCIENTIFIC_DECISION_RULE_UNBOUND"]}
    try:
        _require(type(policy_precommit) is dict and set(policy_precommit) == {
            "schema", "policy_artifact", "commitment_receipt", "commit_event_id"},
            "policy:keys")
        _require(policy_precommit["schema"] == "jaxley-retinal-policy-precommit-v1",
                 "policy:schema")
        _pin_descriptor(policy_precommit["policy_artifact"], "policy_artifact")
        _pin_descriptor(policy_precommit["commitment_receipt"], "commitment_receipt")
        event = policy_precommit["commit_event_id"]
        _require(type(event) is str and 0 < len(event) <= 128 and
                 all(c.isalnum() or c in "-_.:" for c in event), "policy:commit_event_id")
        claimed_sha = _digest(policy_precommit)
    except AssessmentError as exc:
        return {"status": "INVALID", "metadata_sha256": None,
                "authority_verified": False, "chronology_verified": False,
                "scientific_rule_bound": False,
                "error": {"code": exc.code, "path": exc.path},
                "reasons": ["POLICY_PRECOMMIT_INVALID", "SCIENTIFIC_DECISION_RULE_UNBOUND"]}
    return {"status": "PRESENT_UNVERIFIED", "metadata_sha256": claimed_sha,
            "authority_verified": False, "chronology_verified": False,
            "scientific_rule_bound": False,
            "reasons": ["POLICY_PRECOMMIT_AUTHORITY_UNBOUND",
                        "PRECOMMIT_BEFORE_CANDIDATE_AND_TEST_ACCESS_UNVERIFIED",
                        "SCIENTIFIC_DECISION_RULE_UNBOUND"]}


def assess_pair(operator, author, candidate, *, episode,
                trusted_operator_evidence=None, policy_precommit=None,
                implementations_root=None, episode_source_root=None):
    """Return strict descriptive scores, never a self-certified scientific win.

    Invalid numerical operands raise the unchanged legacy Refusal. Valid operands
    still receive scores if qualification metadata is missing, invalid, or
    unverified. One call compares the declared author reference with the specified
    A or B candidate; it is not evidence that both experimental conditions ran.
    Optional source roots are trusted process configuration only.
    """
    here = Path(__file__).resolve().parent
    implementations_root = here.parent if implementations_root is None else implementations_root
    episode_source_root = here if episode_source_root is None else episode_source_root
    with _SOURCE_LOCK:
        with _legacy_module(implementations_root) as legacy:
            comparison = legacy.compare(operator, author, candidate)
        paired = _episode_module(episode_source_root)
        reasons = []
        try:
            validation = paired.validate_pair(episode, trusted_operator_evidence=trusted_operator_evidence)
        except paired.EpisodeContractError as exc:
            validation = {"schema": "jaxley-paired-retinal-episode-validation-v1",
                          "contract_valid": False, "qualification": False,
                          "error": {"code": exc.code, "path": exc.path}}
            reasons.append("EPISODE_CONTRACT_INVALID")
        if validation.get("contract_valid") is True:
            _require(validation.get("schema") == "jaxley-paired-retinal-episode-validation-v1",
                     "episode:validator_schema")
            if validation.get("scored_packet_sha256") != comparison["input_sha256"]:
                reasons.append("EPISODE_SCORED_PACKET_BINDING_MISMATCH")
            if validation.get("identity_sha256") != comparison["identity_sha256"]:
                reasons.append("EPISODE_TARGET_IDENTITY_MISMATCH")
            if validation.get("evaluated_condition") not in ("A", "B"):
                reasons.append("EPISODE_EVALUATED_CONDITION_INVALID")
            episode_reasons = validation.get("qualification_reasons")
            _require(type(episode_reasons) is list and
                     all(type(value) is str for value in episode_reasons),
                     "episode:validator_reasons")
            reasons.extend(episode_reasons)
    policy = inspect_policy_precommit(policy_precommit)
    reasons.extend(policy["reasons"])
    # These are implementation capabilities, never participant-supplied flags.
    reasons.extend(["PHYSICAL_TRANSPORT_VERIFIER_UNBOUND",
                    "COMPLETE_PAIRED_EXECUTION_AUTHORITY_UNBOUND"])
    if comparison["paired_delta"] is None:
        reasons.append("COMPLETE_ALL_SITE_METRIC_UNDEFINED")
    report = {"schema": SCHEMA, "qualification": "UNQUALIFIED",
              "qualification_reasons": list(dict.fromkeys(reasons)),
              "reproduced": None, "improved": None, "uncertainty": None,
              "legacy_comparison": comparison,
              "descriptive_paired_delta": comparison["paired_delta"],
              "episode_validation": validation, "policy_precommit": policy,
              "evaluated_condition": validation.get("evaluated_condition"),
              "both_candidate_conditions_completed": None,
              "published_rounded_score_used_as_threshold": False,
              "historical_paper_run_equivalence": "UNPROVEN",
              "inference_scope": "conditional on one cell and the declared complete target/split/mask; neither sites nor stimulus rows are independent biological replicates",
              "generalization_claims": {"cross_cell": False, "unique_stimulus_disjoint": False,
                                        "historical_paper_reproduction": False},
              "implementation": {
                  "strict_legacy_sources": {name: {"bytes": pin[0], "sha256": pin[1]}
                                            for name, pin in LEGACY_PINS.items()},
                  "episode_source": {"bytes": EPISODE_PIN[0], "sha256": EPISODE_PIN[1]},
                  "scientific_policy_evaluator_bound": False,
                  "transport_verifier_bound": False,
                  "runtime_scientifically_qualified_by_this_assessment": False}}
    _digest(report)  # Refuse accidental non-JSON or nonfinite report fields.
    return report


def read_json(path, max_bytes):
    """Bounded strict JSON input; no duplicate keys or nonfinite constants."""
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "json:duplicate_key", key[:128])
            result[key] = value
        return result
    def constant(_value):
        raise AssessmentError("json:nonfinite_constant")
    with Path(path).open("rb") as stream:
        body = stream.read(max_bytes + 1)
    _require(len(body) <= max_bytes, "json:byte_limit")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("targets", "author", "candidate", "episode", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--trusted-operator-evidence")
    parser.add_argument("--policy-precommit")
    parser.add_argument("--implementations-root", help="trusted operator source-layout override")
    parser.add_argument("--episode-source-root", help="trusted operator source-layout override")
    args = parser.parse_args()
    try:
        report = assess_pair(
            read_json(args.targets, 64 * 1048576), read_json(args.author, 32 * 1048576),
            read_json(args.candidate, 32 * 1048576), episode=read_json(args.episode, 1048576),
            trusted_operator_evidence=(read_json(args.trusted_operator_evidence, 1048576)
                                       if args.trusted_operator_evidence else None),
            policy_precommit=read_json(args.policy_precommit, 131072) if args.policy_precommit else None,
            implementations_root=args.implementations_root, episode_source_root=args.episode_source_root)
        with Path(args.output).open("x", encoding="utf-8") as stream:
            json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
    except (ValueError, OSError) as exc:
        parser.exit(2, "paired retinal assessment refused: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
