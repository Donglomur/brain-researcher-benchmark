"""Lossless participant transport and complete response collection for worm traces.

No participant execution, source extraction, model call or biological identity
authentication is performed. The predecessor's scientific scorer is unchanged.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import importlib.util
import json
import math
from pathlib import Path

MODES = ("direct_observation", "typed_viewer", "tool_assisted", "frozen_program")
SCHEMA = "worm-participant-transport/v2"
EVALUATOR_SHA256 = "4fde8b08dc090d6b0b3d79d8fb8e10b0e0145e78620c184c6880d83f9f6e0485"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def read_json(path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("nonfinite JSON constant: " + value)

    return json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=unique_pairs, parse_constant=invalid_constant)


def evaluator():
    path = Path(__file__).resolve().parents[1] / "initial-evaluator-v1/worm_evaluator.py"
    source = path.read_bytes()
    require(hashlib.sha256(source).hexdigest() == EVALUATOR_SHA256,
            "predecessor evaluator changed; review and repin transport before use")
    spec = importlib.util.spec_from_file_location("worm_transport_predecessor", path)
    module = importlib.util.module_from_spec(spec)
    # Execute the authenticated snapshot, not a second read of the pathname.
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


def build_transport(data, key):
    """Alias only administrative identities; keep every permitted value unchanged.

    The operator supplies a secret, random, >=32-byte key. Namespaced tuple HMACs
    preserve grouping without publishing reversible source IDs or a key hash.
    Target values/masks/QC never enter the public bundle or its digest for held or
    development roles. Authentic biological identities still require an audit.
    """
    require(isinstance(key, bytes) and len(key) >= 32, "operator key must contain at least 32 secret bytes")
    predecessor = evaluator()
    predecessor.validate_dataset(data)
    aliases = {}

    def alias(namespace, *identity):
        encoded = canonical_bytes([namespace, *identity])
        name = namespace + "_" + hmac.new(key, encoded, hashlib.sha256).hexdigest()
        require(aliases.setdefault(name, encoded) == encoded, "alias collision")
        return name

    roles, held = {}, []
    for role in predecessor.ROLES:
        packet = predecessor.public_packet(data, role)
        for case in packet["cases"]:
            original = {field: case[field] for field in ("case_id", "worm_id", "acquisition_id", "trial_id")}
            case["case_id"] = alias("case", original["case_id"])
            case["worm_id"] = alias("worm", original["worm_id"])
            case["acquisition_id"] = alias("acquisition", original["acquisition_id"])
            case["trial_id"] = alias("trial", original["worm_id"], original["acquisition_id"], original["trial_id"])
            if role == "held":
                held.append({"case_id": case["case_id"], "original_case_id": original["case_id"],
                             "times_s": copy.deepcopy(case["response_times_s"])})
        roles[role] = packet
    bundle = {"schema_version": SCHEMA, "task_id": predecessor.TASK_ID,
              "access_modes": list(MODES), "roles": roles}
    custody = {"schema_version": SCHEMA, "task_id": predecessor.TASK_ID,
               "bundle_sha256": digest(bundle), "dataset_sha256": digest(data),
               "evaluator_sha256": EVALUATOR_SHA256, "held_mapping": held}
    return bundle, custody


def response_template(bundle, mode):
    require(mode in MODES, "unknown access mode")
    packet = bundle["roles"]["held"]
    return {"schema_version": SCHEMA, "task_id": bundle["task_id"],
            "bundle_sha256": digest(bundle), "access_mode": mode, "units": packet["units"],
            "cases": [{"case_id": case["case_id"], "times_s": copy.deepcopy(case["response_times_s"]),
                       "values": [None] * len(case["response_times_s"])} for case in packet["cases"]]}


def collect_response(bundle, custody, submission, *, expected_mode, key):
    """Collect the complete exact-grid answer without reading any target value.

    expected_mode comes from the operator's assigned condition, not the answer.
    The original export key authenticates each alias-to-original-case mapping;
    a dataset digest alone cannot detect a swapped private mapping. The key is
    never returned or written to participant artifacts. This verifies identity
    and information parity, not compliance of a runtime.
    """
    require(expected_mode in MODES, "unknown assigned access mode")
    require(isinstance(key, bytes) and len(key) >= 32, "original operator key must contain at least 32 secret bytes")
    require(bundle.get("schema_version") == SCHEMA and custody.get("schema_version") == SCHEMA,
            "transport schema mismatch")
    require(custody.get("bundle_sha256") == digest(bundle), "public bundle differs from frozen custody")
    require(custody.get("evaluator_sha256") == EVALUATOR_SHA256, "custody evaluator mismatch")
    require(set(submission) == {"schema_version", "task_id", "bundle_sha256", "access_mode", "units", "cases"},
            "submission fields differ from response template")
    require(submission["schema_version"] == SCHEMA and submission["task_id"] == bundle["task_id"]
            and custody["task_id"] == bundle["task_id"], "submission task/schema mismatch")
    require(submission["access_mode"] == expected_mode, "submission mode differs from assigned condition")
    require(submission["bundle_sha256"] == custody["bundle_sha256"], "submission belongs to a different bundle")
    packet = bundle["roles"]["held"]
    require(submission["units"] == packet["units"], "prediction units mismatch")
    mapping = {row["case_id"]: row for row in custody["held_mapping"]}
    require(len(mapping) == len(custody["held_mapping"]), "duplicate custody alias")
    for alias, row in mapping.items():
        require(isinstance(row["original_case_id"], str), "custody original case ID must be text")
        expected_alias = "case_" + hmac.new(
            key, canonical_bytes(["case", row["original_case_id"]]), hashlib.sha256).hexdigest()
        require(hmac.compare_digest(alias, expected_alias),
                "custody case mapping does not match original operator key")
    require(len({row["original_case_id"] for row in mapping.values()}) == len(mapping),
            "custody maps multiple aliases onto one original case")
    public = {row["case_id"]: row["response_times_s"] for row in packet["cases"]}
    require(len(public) == len(packet["cases"]) and public
            and public == {key: row["times_s"] for key, row in mapping.items()},
            "custody roster or times differ from public held packet")
    entries = submission["cases"]
    require(isinstance(entries, list), "response cases must be a list")
    seen, predictions = set(), []
    for row in entries:
        require(isinstance(row, dict) and set(row) == {"case_id", "times_s", "values"},
                "response row fields differ from template")
        name = row["case_id"]
        require(isinstance(name, str) and name in mapping and name not in seen,
                "extra, duplicate or original instead of aliased case_id")
        seen.add(name)
        require(isinstance(row["times_s"], list) and all(finite(t) for t in row["times_s"])
                and row["times_s"] == mapping[name]["times_s"], "response grid differs from original timestamps")
        require(isinstance(row["values"], list) and len(row["values"]) == len(row["times_s"])
                and all(finite(value) for value in row["values"]),
                "finite prediction required at every requested time, including unobserved targets")
        predictions.append({"case_id": mapping[name]["original_case_id"],
                            "times_s": copy.deepcopy(row["times_s"]), "values": copy.deepcopy(row["values"])})
    require(seen == set(mapping), "response omits held cases")
    predictions.sort(key=lambda row: row["case_id"])
    result = {"units": packet["units"], "cases": predictions}
    receipt = {"schema_version": SCHEMA, "task_id": bundle["task_id"],
               "bundle_sha256": custody["bundle_sha256"], "submission_sha256": digest(submission),
               "access_mode": expected_mode, "complete_cases": len(predictions),
               "requested_samples": sum(len(row["values"]) for row in predictions),
               "runtime_compliance_verified": False}
    return result, receipt


def validate_custody_dataset(data, custody):
    """Operator check before passing recovered predictions to the existing scorer."""
    require(digest(data) == custody["dataset_sha256"], "custody dataset changed after transport freeze")
    evaluator().validate_dataset(data)


def write_new(path, value, *, private=False):
    path = Path(path)
    # Exclusive creation prevents accidental replacement of a frozen artifact.
    with path.open("x", encoding="utf-8") as stream:
        if private:
            import os
            os.fchmod(stream.fileno(), 0o600)
        json.dump(value, stream, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("dataset", type=Path)
    export.add_argument("key_file", type=Path)
    export.add_argument("public_directory", type=Path)
    export.add_argument("custody_file", type=Path)
    collect = commands.add_parser("collect")
    for name in ("bundle", "custody", "submission", "dataset", "predictions", "receipt"):
        collect.add_argument(name, type=Path)
    collect.add_argument("--mode", choices=MODES, required=True)
    collect.add_argument("--key-file", type=Path, required=True,
                         help="original secret export key, kept outside participant access")
    args = parser.parse_args()
    if args.command == "export":
        public = args.public_directory.resolve()
        private = args.custody_file.resolve()
        require(public != private and public not in private.parents,
                "custody file must be outside participant directory")
        require(not public.exists() and not private.exists(), "export paths must be new")
        bundle, custody = build_transport(read_json(args.dataset), args.key_file.read_bytes())
        # Parent directories are operator provisioned; no private target copy is made.
        public.mkdir(mode=0o700)
        write_new(private, custody, private=True)
        write_new(public / "packet.json", bundle)
        for mode in MODES:
            write_new(public / ("response-" + mode + ".json"), response_template(bundle, mode))
    else:
        public = args.bundle.resolve().parent
        for output in (args.predictions, args.receipt):
            require(output.resolve() != public and public not in output.resolve().parents,
                    "collected outputs must remain outside participant directory")
            require(not output.exists(), "collected output paths must be new")
        bundle, custody = read_json(args.bundle), read_json(args.custody)
        validate_custody_dataset(read_json(args.dataset), custody)
        predictions, receipt = collect_response(bundle, custody, read_json(args.submission),
                                                expected_mode=args.mode, key=args.key_file.read_bytes())
        write_new(args.predictions, predictions, private=True)
        write_new(args.receipt, receipt, private=True)


if __name__ == "__main__":
    main()
