"""NEURAL-027 direct numeric prompts and paired, complete response collection.

Operator software only: no model calls, fitting, source pickle loading or access
enforcement. Serve one rendered prompt in a fresh no-tools context per item/arm.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import hmac
import importlib.util
import io
import json
import math
from pathlib import Path
import secrets

import numpy as np

BASE_PATH = Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "evaluator.py"
BASE_SHA256 = "5f15b481e16bde099ce1df514d7d9ecff22a8902339cdaa2998839a51903e145"
if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
    raise RuntimeError("reviewed predecessor evaluator changed")
_spec = importlib.util.spec_from_file_location("neural027_evaluator", BASE_PATH)
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

SCHEMA = "neural027-direct/v1"
FEATURES = {"neural": ["V1", "mHV", "lHV", "aHV"],
            "movement_position": ["mean_movement", "mean_normalized_position"]}
INSTRUCTIONS = (
    "Identify the recorded visual stimulus category from the numeric observation. "
    "The labeled examples come only from prereward training animals; the query "
    "comes from a held-out animal and exposure phase. Use only this prompt: no "
    "tools, code, external sources, persistent memory, or feedback from other cases. "
    "Each case and each observation condition requires a fresh context. Neural "
    "values are calcium-derived regional means, not electrode spikes; movement "
    "uses source units and normalized position is dimensionless. There is no "
    "individual-cell, time-course, or spatial image information. Return exactly "
    "one JSON object with item_id and probabilities; probabilities must be finite, "
    "nonnegative, sum to one, and follow classes_in_probability_order. Do not add "
    "explanations, class labels, markdown, or additional fields."
)


def require(value, message):
    if not value:
        raise ValueError(message)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def decode_json(raw):
    """Parse one captured byte stream, preserving strict JSON checks."""
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON object key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("nonfinite JSON constant: " + value)

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def read_json(path):
    return decode_json(Path(path).read_bytes())


def load_sessions(plan, directory):
    """Same safe-array boundary as v1; pin every actual input byte stream."""
    base.validate_plan(plan)
    sessions, pins = [], []
    for meta in plan["sessions"]:
        name = meta["session_id"]
        require(Path(name).name == name and "/" not in name and "\\" not in name, "unsafe source basename")
        path = Path(directory) / (name + ".npz")
        raw = path.read_bytes()
        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            require(set(archive.files) == {"spks", "iarea", *base.SOURCE_FIELDS,
                                          "Corridor_Length", "UniqWalls", "stim_id"}, "safe export fields mismatch")
            sessions.append(dict(meta, spks=archive["spks"], iarea=archive["iarea"],
                                 behavior={k: archive[k] for k in (*base.SOURCE_FIELDS, "Corridor_Length", "UniqWalls", "stim_id")}))
        pins.append({"session_id": name, "bytes": len(raw),
                     "sha256": hashlib.sha256(raw).hexdigest()})
    return sessions, pins


def build(sessions, plan, demonstration_ids, *, key=None):
    """Prepare both direct conditions without fitting or reading model outcomes.

    Demonstrations are explicit predeclared training IDs, with equal packet
    counts in every training mouse/class cell and complete selected trials.
    Empty IDs define a distinct zero-demonstration condition.
    """
    train, expected, audit = base.prepare(sessions, plan)
    require(isinstance(demonstration_ids, list) and all(isinstance(x, str) for x in demonstration_ids), "demonstration IDs must be strings")
    require(len(set(demonstration_ids)) == len(demonstration_ids), "duplicate demonstration IDs")
    train_by_id = {r["item_id"]: r for r in train}
    require(set(demonstration_ids) <= set(train_by_id), "demonstrations must be training-only IDs")
    demonstrations = [train_by_id[x] for x in demonstration_ids]
    if demonstrations:
        cells = Counter((r["mname"], r["label"]) for r in demonstrations)
        required = {(m, c) for m in plan["train_mice"] for c in plan["classes"]}
        require(set(cells) == required and len(set(cells.values())) == 1, "demonstrations must balance every training mouse/class")
        trials = {(r["session_id"], r["trial_id"]) for r in demonstrations}
        complete = {r["item_id"] for r in train if (r["session_id"], r["trial_id"]) in trials}
        require(set(demonstration_ids) == complete, "demonstrations must retain complete trial-position grids")
    if key is None:
        key = secrets.token_bytes(32)
    require(isinstance(key, bytes) and len(key) >= 32, "private identity key requires at least 32 bytes")

    def public_id(row):
        return hmac.new(key, (SCHEMA + "\0" + row["item_id"]).encode(), hashlib.sha256).hexdigest()

    ordered = sorted(expected, key=public_id)
    public = {}
    for arm, feature in (("neural", "neural"), ("movement_position", "context")):
        public[arm] = {
            "schema": SCHEMA, "task_id": "NEURAL-027", "requested_access_mode": "direct_observation",
            "observation_condition": arm,
            "demonstration_condition": "fixed_training_demonstrations" if demonstrations else "zero_demonstrations",
            "classes_in_probability_order": list(plan["classes"]), "feature_order": FEATURES[arm],
            "instructions": INSTRUCTIONS,
            "demonstrations": [{"values": list(r[feature]), "label": r["label"]} for r in demonstrations],
            "items": [{"item_id": public_id(r), "values": list(r[feature])} for r in ordered],
        }
    private = {
        "schema": SCHEMA, "task_id": "NEURAL-027", "plan_sha256": digest(plan),
        "predecessor_sha256": BASE_SHA256, "private_identity_key_hex": key.hex(),
        "demonstration_source_ids": list(demonstration_ids),
        "public_sha256": {arm: digest(payload) for arm, payload in public.items()},
        "classes_in_probability_order": list(plan["classes"]),
        "expected": [{"item_id": public_id(r), "source_item_id": r["item_id"],
                      "label": r["label"], "mname": r["mname"], "phase": r["phase"]} for r in ordered],
        "extraction_audit": audit,
    }
    return public, private


def validate_packet(packet):
    """Reject extra fields before rendering anything into a participant prompt."""
    fields = {"schema", "task_id", "requested_access_mode", "observation_condition",
              "demonstration_condition", "classes_in_probability_order", "feature_order",
              "instructions", "demonstrations", "items"}
    require(isinstance(packet, dict) and set(packet) == fields, "public packet fields mismatch")
    require(packet["schema"] == SCHEMA and packet["task_id"] == "NEURAL-027", "public packet identity mismatch")
    require(packet["requested_access_mode"] == "direct_observation" and packet["instructions"] == INSTRUCTIONS, "direct prompt instructions changed")
    arm = packet["observation_condition"]
    require(isinstance(arm, str) and arm in FEATURES, "unknown observation condition")
    require(packet["feature_order"] == FEATURES[arm], "feature ordering mismatch")
    classes = base.checked_classes(packet["classes_in_probability_order"]).tolist()
    demos, items = packet["demonstrations"], packet["items"]
    require(isinstance(demos, list) and isinstance(items, list) and items, "public record lists required")
    require(packet["demonstration_condition"] == ("fixed_training_demonstrations" if demos else "zero_demonstrations"), "demonstration condition mismatch")
    for rows, keys in ((demos, {"values", "label"}), (items, {"item_id", "values"})):
        for row in rows:
            require(isinstance(row, dict) and set(row) == keys, "public observation fields mismatch")
            values = row["values"]
            require(isinstance(values, list) and len(values) == len(FEATURES[arm]), "public feature width mismatch")
            require(all(type(x) in (int, float) and math.isfinite(x) for x in values), "public features must be finite JSON numbers")
    require(all(type(r["label"]) is int and r["label"] in classes for r in demos), "invalid demonstration target")
    ids = [r["item_id"] for r in items]
    require(all(isinstance(x, str) and len(x) == 64 and all(c in "0123456789abcdef" for c in x) for x in ids), "invalid opaque query identity")
    require(len(set(ids)) == len(ids), "duplicate public item IDs")


def render_prompt(packet, item_id):
    """Return only one query plus the identical frozen context/demonstrations."""
    validate_packet(packet)
    matches = [r for r in packet["items"] if r["item_id"] == item_id]
    require(len(matches) == 1, "unknown or duplicate public item ID")
    payload = {k: v for k, v in packet.items() if k != "items"}
    payload["query"] = matches[0]
    return json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"


def collect(public, private, responses, *, bootstrap_draws=2000):
    """Grade complete paired responses; never fill missing predictions or retry."""
    require(set(public) == set(FEATURES) and set(responses) == set(FEATURES), "both paired observation conditions required")
    require(private["schema"] == SCHEMA and private["task_id"] == "NEURAL-027", "private bundle identity mismatch")
    require(private["predecessor_sha256"] == BASE_SHA256, "private predecessor mismatch")
    classes = private["classes_in_probability_order"]
    expected = private["expected"]
    scores = {}
    for arm in FEATURES:
        validate_packet(public[arm])
        require(public[arm]["observation_condition"] == arm, "paired condition mismatch")
        require(digest(public[arm]) == private["public_sha256"][arm], "public packet changed after freeze")
        require(public[arm]["classes_in_probability_order"] == classes, "class ordering mismatch")
        require([r["item_id"] for r in public[arm]["items"]] == [r["item_id"] for r in expected], "expected item binding mismatch")
        require(isinstance(responses[arm], list), "responses must be a list")
        for row in responses[arm]:
            require(isinstance(row, dict) and set(row) == {"item_id", "probabilities"}, "response fields mismatch")
            p = row["probabilities"]
            require(isinstance(p, list) and all(type(x) in (int, float) for x in p), "probabilities must be JSON numbers")
        scores[arm] = base.score(expected, responses[arm], classes)
    return {
        "schema": SCHEMA, "task_id": "NEURAL-027", "implementation": "direct-packets-v1",
        "requested_access_mode": "direct_observation", "access_enforcement_verified": False,
        "scientific_qualification": "not_established", "development_only": True,
        "demonstration_condition": public["neural"]["demonstration_condition"],
        "training_examples_per_prompt": len(public["neural"]["demonstrations"]),
        "query_cases_per_context_requested": 1,
        "public_sha256": private["public_sha256"], "private_binding_sha256": digest(private),
        "response_sha256": {arm: digest(rows) for arm, rows in responses.items()},
        **scores, "paired_uncertainty": base.compare(scores["neural"], scores["movement_position"], draws=bootstrap_draws),
        "limits": ["No model invocation or no-tools/per-case reset enforcement is implemented.",
                   "This report is operator-private: it includes original mouse and phase grouping.",
                   "Authentic input, complete native cohort, phase/position semantics and source export equality remain unverified.",
                   "A direct-mode claim requires external transport evidence; frozen-program predictions are not direct interpretation."],
    }


def write_new(path, value):
    with Path(path).open("x") as handle:
        json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("build")
    for flag in ("plan", "session-dir", "demonstration-ids", "public-dir", "private-dir"):
        create.add_argument("--" + flag, type=Path, required=True)
    prompt = sub.add_parser("prompt")
    prompt.add_argument("--packet", type=Path, required=True)
    prompt.add_argument("--item-id", required=True)
    grade = sub.add_parser("score")
    for flag in ("public-dir", "private-binding", "neural-responses", "movement-position-responses", "output"):
        grade.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        public_dir, private_dir = args.public_dir.resolve(), args.private_dir.resolve()
        require(public_dir != private_dir and public_dir not in private_dir.parents and private_dir not in public_dir.parents,
                "public and private directories must be disjoint")
        require(not public_dir.exists() and not private_dir.exists(), "output directories must be new")
        plan_raw = args.plan.read_bytes()
        plan = decode_json(plan_raw)
        sessions, pins = load_sessions(plan, args.session_dir)
        packets, private = build(sessions, plan, read_json(args.demonstration_ids))
        private["input_pins"] = pins
        private["plan_file_sha256"] = hashlib.sha256(plan_raw).hexdigest()
        public_dir.mkdir(parents=True, mode=0o700)
        private_dir.mkdir(parents=True, mode=0o700)
        for arm, packet in packets.items():
            write_new(public_dir / (arm + ".json"), packet)
        write_new(private_dir / "binding.json", private)
    elif args.command == "prompt":
        print(render_prompt(read_json(args.packet), args.item_id), end="")
    else:
        output, public_dir = args.output.resolve(), args.public_dir.resolve()
        require(output != public_dir and public_dir not in output.parents, "scoring report must remain outside public directory")
        packets = {arm: read_json(args.public_dir / (arm + ".json")) for arm in FEATURES}
        responses = {"neural": read_json(args.neural_responses), "movement_position": read_json(args.movement_position_responses)}
        report = collect(packets, read_json(args.private_binding), responses)
        write_new(args.output, report)


if __name__ == "__main__":
    main()
