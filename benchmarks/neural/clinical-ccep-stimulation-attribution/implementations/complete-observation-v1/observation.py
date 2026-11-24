"""Complete normalized CCEP observations and per-case response transport.

Source-only bridge; not a native converter, cohort runner or access sandbox.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types

PAIRING_BYTES = 24583
PAIRING_SHA256 = "d3b0b2765d56904fb565099e876562d3f327df52a3489868aa774ac1a27b90a3"


def _pairing():
    path = Path(__file__).resolve().parent.parent / "clinical-ccep-pairing/pairing.py"
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != PAIRING_BYTES:
            raise ValueError("pairing source identity")
        body = stream.read(PAIRING_BYTES + 1)
    if hashlib.sha256(body).hexdigest() != PAIRING_SHA256:
        raise ValueError("pairing source identity")
    module = types.ModuleType("fixed_ccep_pairing")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


C = _pairing()
P = C.P


def encoded(value):
    return C.canonical(value) + b"\n"


def _public(block, row, observation_id, max_bytes):
    P.token(observation_id)
    P.require(type(max_bytes) is int and 1 <= max_bytes <= P.MAX_BYTES, "public byte capacity")
    response = C._decoded(block["response_b64"], row["response_sha256"])
    layout = C._decoded(block["layout_b64"], row["layout_sha256"])
    context = C._decoded(block["context_b64"], row["context_sha256"])
    public = {"schema": "ccep-observation-v1", "task_id": P.TASK,
              "observation_id": observation_id, "class_order": list(P.CLASSES),
              "response": response, "relative_times_seconds": layout["relative_times_seconds"],
              "units": layout["units"], "missing": layout["missing"], "artifact": layout["artifact"],
              "recording_location": context["recording_location"],
              "response_schema": "ccep-observation-response-v1"}
    public["response_token"] = C.digest(encoded(public))
    P.require(len(encoded(public)) <= max_bytes, "complete observation exceeds public capacity")
    return public


def export(policy_path, policy_sha256, control_path, control_sha256, case_id,
           packet_path, observation_id, max_bytes, *, map_path=None, map_sha256=None,
           transform_id=None, donor_packet_path=None):
    """Return public observation and evaluator-private response binding.

    Original export does not require a pairing map or supported null stratum.
    The cap includes the complete emitted JSON and final newline; no truncation.
    """
    _, ph, cases, _, _, ch, rows, _ = C._policy(
        policy_path, policy_sha256, control_path, control_sha256)
    P.token(case_id)
    P.require(case_id in cases and cases[case_id]["coverage"] == "ready", "ready declared case")
    paired_arguments = (map_path, map_sha256, transform_id, donor_packet_path)
    if all(value is None for value in paired_arguments):
        block = C._envelope(packet_path, cases[case_id], rows[case_id])
        row = rows[case_id]
        condition = "original_full_scope"
        mh = None
    else:
        P.require(all(value is not None for value in paired_arguments), "complete paired arguments")
        manifest, mh = C._frozen_map(map_path, map_sha256, ph, ch, cases, rows)
        block = C.packet(policy_path, policy_sha256, control_path, control_sha256,
                         map_path, map_sha256, transform_id, case_id, packet_path, donor_packet_path)
        selected = next(t for t in manifest["transforms"] if t["id"] == transform_id)
        donor = next(pair["donor"] for pair in selected["donors"] if pair["recipient"] == case_id)
        row = {**rows[case_id], "response_sha256": rows[donor]["response_sha256"]}
        condition = "paired_support_only"
    public = _public(block, row, observation_id, max_bytes)
    binding = {"schema": "ccep-observation-binding-v1", "task_id": P.TASK,
               "policy_sha256": ph, "control_sha256": ch, "case_id": case_id,
               "observation_id": observation_id, "public_sha256": C.digest(encoded(public)),
               "response_token": public["response_token"],
               "condition": condition, "map_sha256": mh, "transform_id": transform_id}
    return public, binding


def collect(policy_path, policy_sha256, binding_path, binding_sha256, response_path):
    """Return one row for the existing primary/paired prediction artifact.

    The binding digest is operator-owned and frozen at export. This is not a
    full-census artifact assembler or a substitute for either existing scorer.
    """
    P.sha(binding_sha256); P.sha(policy_sha256)
    policy, ph = P.read_document(policy_path, policy_sha256)
    cases, _ = P.validate_policy(policy)
    binding, _ = P.read_document(binding_path, binding_sha256)
    P.keys(binding, {"schema", "task_id", "policy_sha256", "control_sha256", "case_id",
                     "observation_id", "public_sha256", "response_token", "condition", "map_sha256", "transform_id"},
           "private observation binding")
    P.require(binding["schema"] == "ccep-observation-binding-v1" and binding["task_id"] == P.TASK and
              binding["policy_sha256"] == ph, "binding policy/task")
    for key in ("control_sha256", "public_sha256", "response_token"):
        P.sha(binding[key])
    name = P.token(binding["case_id"])
    P.require(name in cases and cases[name]["coverage"] == "ready", "binding ready case")
    P.token(binding["observation_id"])
    if binding["condition"] == "original_full_scope":
        P.require(binding["map_sha256"] is None and binding["transform_id"] is None, "original binding")
    else:
        P.require(binding["condition"] == "paired_support_only", "binding condition")
        P.sha(binding["map_sha256"]); P.token(binding["transform_id"])
    response, _ = P.read_document(response_path)
    P.keys(response, {"schema", "observation_id", "response_token", "probabilities"}, "response")
    P.require(response["schema"] == "ccep-observation-response-v1" and
              response["observation_id"] == binding["observation_id"] and
              response["response_token"] == binding["response_token"], "response observation identity")
    row = {"case_id": name, "probabilities": response["probabilities"]}
    proxy = {"schema": "ccep-predictions-v1", "task_id": P.TASK, "policy_sha256": ph,
             "class_order": list(P.CLASSES), "condition": "original_full_scope", "rows": [row]}
    P.validate_predictions(proxy, policy, ph, {name: cases[name]})
    return {"schema": "ccep-collected-observation-v1", "task_id": P.TASK,
            "policy_sha256": ph, "condition": binding["condition"],
            "map_sha256": binding["map_sha256"], "transform_id": binding["transform_id"], "row": row}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("export", "collect"):
        command = commands.add_parser(name)
        command.add_argument("--policy", required=True)
        command.add_argument("--policy-sha256", required=True)
        if name == "export":
            command.add_argument("--control", required=True)
            command.add_argument("--control-sha256", required=True)
            command.add_argument("--case-id", required=True)
            command.add_argument("--packet", required=True)
            command.add_argument("--observation-id", required=True)
            command.add_argument("--max-public-bytes", required=True, type=int)
            command.add_argument("--binding-output", required=True)
            command.add_argument("--map")
            command.add_argument("--map-sha256")
            command.add_argument("--transform-id")
            command.add_argument("--donor-packet")
        else:
            command.add_argument("--binding", required=True)
            command.add_argument("--binding-sha256", required=True)
            command.add_argument("--response", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            public, binding = export(args.policy, args.policy_sha256, args.control, args.control_sha256,
                                     args.case_id, args.packet, args.observation_id, args.max_public_bytes,
                                     map_path=args.map, map_sha256=args.map_sha256,
                                     transform_id=args.transform_id, donor_packet_path=args.donor_packet)
            body = encoded(public)
            # Freeze only after the entire observation passed validation and capacity.
            fd = os.open(args.binding_output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded(binding))
        else:
            body = encoded(collect(args.policy, args.policy_sha256, args.binding,
                                   args.binding_sha256, args.response))
    except (P.Invalid, OSError, TypeError, ValueError, OverflowError, RecursionError, StopIteration):
        print('{"schema":"ccep-observation-refusal-v1","status":"invalid_or_incomplete"}')
        return 2
    sys.stdout.buffer.write(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
