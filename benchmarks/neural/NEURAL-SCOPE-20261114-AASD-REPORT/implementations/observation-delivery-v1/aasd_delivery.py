"""Sanitized normalized-observation export and opaque response joins for AASD.

Construction software only: no MAT importer, fitted model, sandbox, or direct/viewer
runtime. All label creation and endpoint arithmetic remain in initial-evaluator-v1.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import tempfile

_EVALUATOR = Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "aasd_evaluator.py"
_spec = importlib.util.spec_from_file_location("aasd_delivery_evaluator", _EVALUATOR)
a = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a)
ContractError = a.ContractError
MODES = ("tool_assisted", "frozen_program")
TOKEN = re.compile(r"[0-9a-f]{32}\Z")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def fields(value, keys, name):
    a.require(isinstance(value, dict) and set(value) == set(keys), f"{name}: unexpected or missing fields")


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def token(value):
    a.require(isinstance(value, str) and TOKEN.fullmatch(value) is not None, "invalid opaque token")
    return value


def validate_observation(observation, trial, common_channels):
    """Validate normalized dimensions; do not infer native channel or clock identities."""
    fields(observation, ("schema", "channels", "eeg_unit", "eeg_samples", "audio"), "observation")
    a.require(observation["schema"] == "aasd-normalized-observation-v1", "unknown observation schema")
    channels = observation["channels"]
    a.require(isinstance(channels, list) and channels, "channels must be a nonempty ordered list")
    a.require(all(isinstance(c, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,15}", c) for c in channels), "channel names must be electrode tokens")
    a.require(len(set(channels)) == len(channels), "duplicate channel")
    a.require(observation["eeg_unit"] in ("V", "uV"), "explicit EEG unit must be V or uV")
    signature = (tuple(channels), observation["eeg_unit"])
    a.require(common_channels is None or signature == common_channels, "common channel order and units differ")
    eeg = observation["eeg_samples"]
    a.require(isinstance(eeg, list) and len(eeg) == len(channels), "EEG must be channel-major")
    a.require(all(isinstance(row, list) and len(row) == trial["sample_count"] for row in eeg), "EEG length differs from inventory")
    audio = observation["audio"]
    fields(audio, ("sample_rate_hz", "sample_origin_ns", "samples"), "audio")
    hz = a.integer(audio["sample_rate_hz"], "audio sample rate", 1)
    a.integer(audio["sample_origin_ns"], "audio origin")
    samples = audio["samples"]
    a.require(isinstance(samples, list) and len(samples) == 2, "audio must have two channel-major streams")
    a.require(all(isinstance(row, list) and row for row in samples) and len(samples[0]) == len(samples[1]), "audio channels must have equal nonzero length")
    a.require(all(finite(v) and -1 <= v <= 1 for row in samples for v in row), "audio samples must be finite normalized PCM in [-1,1]")
    # Integer cross-products avoid rounding an alignment error into an admitted case.
    a.require(audio["sample_origin_ns"] <= 0, "audio starts after trial onset")
    a.require(audio["sample_origin_ns"] * hz + len(samples[0]) * a.NS >= trial["duration_ns"] * hz, "audio does not cover the entire presented trial")
    return signature


def write_json(path, value):
    with path.open("xb") as stream:
        stream.write(canonical(value) + b"\n")
    # Remove export ordering as a filesystem timestamp cue. The runner must still
    # enforce access isolation; this is not a claim of a secure execution service.
    os.utime(path, (0, 0))


def export(inventory, load_observation, public_root, private_binding):
    """Export both numerical modes with byte-identical observations, random IDs.

    load_observation(trial_id) returns one full normalized trial. Full stereo audio
    is stored once per distinct waveform in each arm. Only eligible 256-sample EEG
    slices are written. Atomic publication prevents exposing incomplete exports.
    """
    public_root, private_binding = Path(public_root).resolve(), Path(private_binding).resolve()
    a.require(public_root != private_binding and public_root not in private_binding.parents,
              "private binding must be outside the public delivery tree")
    a.require(not public_root.exists() and not private_binding.exists(), "outputs must not already exist")
    prepared = a.prepare(inventory)
    cases = prepared["cases"]
    a.require(bool(cases), "cannot export a cohort with zero eligible observations")
    by_trial = {}
    for case in cases:
        by_trial.setdefault(case["trial_id"], []).append(case)
    public_root.parent.mkdir(parents=True, exist_ok=True)
    private_binding.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".aasd-delivery-", dir=public_root.parent))
    binding = {"schema": "aasd-private-delivery-binding-v1", "task_id": a.TASK_ID,
               "inventory_sha256": digest(inventory), "modes": list(MODES), "rows": []}
    indexes = {mode: [] for mode in MODES}
    audio_ids = {mode: {} for mode in MODES}
    used = set()
    def opaque():
        value = secrets.token_hex(16)
        a.require(value not in used, "random token collision; export aborted")
        used.add(value)
        return value
    common_channels = None
    published = False
    try:
        for mode in MODES:
            (staging / mode / "packets").mkdir(parents=True)
            (staging / mode / "audio").mkdir()
        for trial in inventory["trials"]:
            trial_cases = by_trial.get(trial["trial_id"], [])
            if not trial_cases:
                continue
            observation = load_observation(trial["trial_id"])
            common_channels = validate_observation(observation, trial, common_channels)
            audio = observation["audio"]
            # No source path, source filename, trial, mixture, or key marker is copied.
            resource = {"schema": "aasd-stereo-pcm-v1", "sample_rate_hz": audio["sample_rate_hz"],
                        "samples": audio["samples"]}
            audio_hash = digest(resource)
            for mode in MODES:
                if audio_hash not in audio_ids[mode]:
                    audio_ids[mode][audio_hash] = opaque()
                    write_json(staging / mode / "audio" / (audio_ids[mode][audio_hash] + ".json"), resource)
            for case in trial_cases:
                left, right = case["eeg_sample_span"]
                eeg = [row[left:right] for row in observation["eeg_samples"]]
                a.require(right-left == 256 and all(finite(v) for row in eeg for v in row), "eligible EEG context contains nonfinite data or wrong length")
                content = {"schema": "aasd-common-observation-v1", "channels": observation["channels"],
                           "eeg_unit": observation["eeg_unit"], "eeg_sample_period_ns": a.SAMPLE_NS,
                           "eeg_start_relative_to_target_ns": -a.NS//2, "target_duration_ns": a.NS,
                           "eeg_samples": eeg, "valid_samples": [True]*256,
                           "audio_origin_relative_to_target_ns": audio["sample_origin_ns"]-case["start_ns"],
                           "audio_sha256": audio_hash}
                # The content hash excludes opaque names/mode; paired arms use the
                # same numerical payload and the same complete waveform hash.
                content_hash = digest(content)
                joins = {}
                for mode in MODES:
                    request_id = opaque()
                    packet = {"schema": "aasd-participant-packet-v1", "request_id": request_id,
                              "observation": content, "audio_resource": audio_ids[mode][audio_hash]}
                    write_json(staging / mode / "packets" / (request_id + ".json"), packet)
                    indexes[mode].append({"request_id": request_id})
                    joins[mode] = request_id
                binding["rows"].append({"case_id": case["case_id"], "participant": case["participant"],
                    "held_mixture_fold": case["fold"], "observation_sha256": content_hash, "request_ids": joins})
        for mode in MODES:
            # Random order avoids disclosing original trial/block/window order.
            indexes[mode].sort(key=lambda row: row["request_id"])
            write_json(staging / mode / "index.json", {"schema": "aasd-participant-index-v1",
                "mode": mode, "requests": indexes[mode], "response_fields": ["request_id", "p_right"]})
        # Private binding is created with owner-only permissions, outside public_root.
        fd = os.open(private_binding, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(binding) + b"\n")
        os.replace(staging, public_root)
        published = True
        return {"eligible_cases": len(cases), "paired_modes": list(MODES),
                "inventory_sha256": binding["inventory_sha256"], "binding_sha256": digest(binding)}
    finally:
        if not published:
            shutil.rmtree(staging, ignore_errors=True)
            # Remove only this invocation's new binding, never a pre-existing file.
            if "fd" in locals():
                private_binding.unlink(missing_ok=True)


def join_responses(inventory, binding, mode, responses):
    """Join one complete arm back to the unchanged evaluator prediction interface."""
    fields(binding, ("schema", "task_id", "inventory_sha256", "modes", "rows"), "private binding")
    a.require(binding["schema"] == "aasd-private-delivery-binding-v1" and binding["task_id"] == a.TASK_ID, "unknown binding identity")
    a.require(mode in MODES and binding["modes"] == list(MODES), "unsupported or changed delivery mode")
    a.require(binding["inventory_sha256"] == digest(inventory), "inventory changed after delivery")
    prepared = a.prepare(inventory)
    expected = {c["case_id"]: c for c in prepared["cases"]}
    a.require(isinstance(binding["rows"], list) and len(binding["rows"]) == len(expected), "binding changed cohort coverage")
    joins, seen_cases, all_tokens = {}, set(), set()
    for row in binding["rows"]:
        fields(row, ("case_id", "participant", "held_mixture_fold", "observation_sha256", "request_ids"), "binding row")
        cid = row["case_id"]
        a.require(isinstance(cid, str) and cid in expected and cid not in seen_cases, "duplicate or unknown evaluator case")
        seen_cases.add(cid)
        a.require(row["participant"] == expected[cid]["participant"] and type(row["held_mixture_fold"]) is int and row["held_mixture_fold"] == expected[cid]["fold"], "cell binding changed")
        a.require(isinstance(row["observation_sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", row["observation_sha256"]), "invalid observation digest")
        fields(row["request_ids"], MODES, "request IDs")
        for value in row["request_ids"].values():
            token(value)
            a.require(value not in all_tokens, "duplicate opaque request ID")
            all_tokens.add(value)
        joins[row["request_ids"][mode]] = cid
    a.require(isinstance(responses, list), "responses must be a list")
    predictions, seen_requests = [], set()
    for row in responses:
        fields(row, ("request_id", "p_right"), "response")
        rid = token(row["request_id"])
        a.require(rid in joins and rid not in seen_requests, "unknown, cross-mode or duplicate response ID")
        a.require(finite(row["p_right"]) and 0 <= row["p_right"] <= 1, "response probability must be finite and in [0,1]")
        seen_requests.add(rid)
        predictions.append({"case_id": joins[rid], "p_right": row["p_right"]})
    # This enforces completeness, finite probabilities and the passive cases too.
    a.validate_predictions(prepared["cases"], predictions)
    return predictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    exp = sub.add_parser("export")
    exp.add_argument("inventory")
    exp.add_argument("observation_map", help="evaluator-only trial_id to normalized JSON path object")
    exp.add_argument("public_root")
    exp.add_argument("private_binding")
    join = sub.add_parser("join")
    join.add_argument("inventory")
    join.add_argument("private_binding")
    join.add_argument("mode", choices=MODES)
    join.add_argument("responses")
    join.add_argument("output")
    args = parser.parse_args()
    try:
        inventory = a.strict_load(args.inventory)
        if args.operation == "export":
            paths = a.strict_load(args.observation_map)
            a.require(isinstance(paths, dict), "observation map must be an object")
            base = Path(args.observation_map).resolve().parent
            def load(tid):
                a.require(tid in paths and isinstance(paths[tid], str), "missing normalized observation")
                return a.strict_load(base / paths[tid])
            export(inventory, load, args.public_root, args.private_binding)
        else:
            result = join_responses(inventory, a.strict_load(args.private_binding), args.mode, a.strict_load(args.responses))
            write_json(Path(args.output), result)
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"aasd delivery: {exc}\n")


if __name__ == "__main__":
    main()
