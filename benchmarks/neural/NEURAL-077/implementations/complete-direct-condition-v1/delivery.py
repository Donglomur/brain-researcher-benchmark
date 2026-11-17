"""Complete pinned waveform/feature delivery and request-bound response admission.

Trusted operator preparation only: no model, training, targets, or grading.
The output directory is deliberately outside the source checkout in real use.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

HERE = Path(__file__).resolve().parent
IMPLEMENTATIONS = HERE.parent
CONDITIONS = ("legacy_waveform_no_tools", "matched_waveform_programme")
NO_TOOLS = "Do not use tools, code execution, external retrieval, files, or memory from other query trials."
PROGRAMME_TOOLS = ("Numerical tools and candidate code execution are allowed for this query. "
                   "Do not use external retrieval, other files, or memory from other query trials.")
CASES = ("development-001", "development-002")
MAX_RESPONSES = 400 * 16384


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def descriptor(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def read_regular(path, cap):
    """Bound allocation, reject final links/special files, detect in-read changes."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 < before.st_size <= cap, "Bounded ordinary single-link file required")
        body = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        require(len(body) <= cap and all(getattr(before, f) == getattr(after, f) for f in fields),
                "Input changed while read")
        return body


def pinned(path, pin):
    body = read_regular(path, pin["bytes"])
    require(descriptor(body) == pin, "Source pin mismatch: " + str(path))
    return body


def dependencies():
    bindings = json.loads((HERE / "SOURCE_BINDINGS.json").read_text())["members"]
    modules = {}
    for name, relative in (("exporter", "waveform-contexts/export_contexts.py"),
                           ("response", "direct-response/portable/response_contract.py"),
                           ("validator", "registered-runtime/validator.py")):
        path = IMPLEMENTATIONS / relative
        body = pinned(path, bindings[relative])
        # Execute the authenticated bytes, not a second unauthenticated path read.
        spec = importlib.util.spec_from_loader("neural077_complete_" + name, loader=None)
        module = importlib.util.module_from_spec(spec)
        module.__file__ = str(path)
        exec(compile(body, str(path), "exec"), module.__dict__)
        modules[name] = module
    relative = "registered-runtime/assets.json"
    modules["assets"] = json.loads(pinned(IMPLEMENTATIONS / relative, bindings[relative]))
    return modules


def packet_members(packet, exporter):
    return {name: pinned(Path(packet) / name, {"bytes": size, "sha256": sha})
            for name, (size, sha) in exporter.PINS.items()}


def context_rows(members, condition):
    require(condition in CONDITIONS, "Unknown waveform condition")
    manifest = json.loads(members["manifest.json"])
    ids = manifest["development_ids"]
    require(len(ids) == len(set(ids)) == 400 and ids == sorted(ids), "Complete sorted400 roster required")
    require(all(sum(x.startswith(case + "-") for x in ids) == 200 for case in CASES),
            "Exactly200 identities from each development person required")
    require(manifest["query_count"] == 400 and manifest["demonstration_count"] == 4
            and manifest["natural_class_prior_supplied"] is False, "Original condition required")
    prompt = members["prompt.txt"].decode("utf-8")
    require(prompt.count(NO_TOOLS) == 1, "Original tool-permission sentence required")
    if condition == "matched_waveform_programme":
        prompt = prompt.replace(NO_TOOLS, PROGRAMME_TOOLS)
    require(prompt.count("{{demonstrations_json}}") == prompt.count("{{query_json}}") == 1,
            "Original prompt slots required")
    a, b = prompt.split("{{demonstrations_json}}")
    require("{{query_json}}" not in a, "Original prompt slot order required")
    b, c = b.split("{{query_json}}")
    prefix = a + members["demonstrations.json"].decode("utf-8") + b
    lines = members["queries.jsonl"].splitlines(keepends=True)
    require(len(lines) == 400, "All400 query lines required")
    for ordinal, (identifier, line) in enumerate(zip(ids, lines)):
        query = json.loads(line)
        require(set(query) == {"trial_id", "channels"} and query["trial_id"] == identifier,
                "Query roster/order mismatch")
        context = prefix + line.decode("utf-8") + c
        yield {"ordinal": ordinal, "trial_id": identifier,
               "context_sha256": hashlib.sha256(context.encode("utf-8")).hexdigest(), "prompt": context}


def verify_signals(members, asset_root, assets):
    """Recompute all404 waveforms; touch only candidate-visible pinned assets."""
    import numpy as np
    queries = [json.loads(line) for line in members["queries.jsonl"].splitlines()]
    demos = json.loads(members["demonstrations.json"])
    require(len(demos) == 4, "Exactly four demonstrations")
    records = queries + demos
    checked = 0
    inputs = {}
    public = {**assets["public"]["cases"], **assets["public_training_lazy"]}
    feature_bodies = {}
    for case, roles in public.items():
        pin = {k: roles["features"][k] for k in ("bytes", "sha256")}
        body = pinned(Path(asset_root) / roles["features"]["path"], pin)
        feature_bodies[case] = body
        inputs[case + "/features.npz"] = pin
        import io
        with np.load(io.BytesIO(body), allow_pickle=False) as feature:
            ids = feature["trial_ids"].tolist()
            channels = feature["channel_names"].tolist()
            require(len(ids) == len(set(ids)) == 200 and feature["case_id"].item() == case,
                    "Complete feature case identity required")
            require(np.array_equal(feature["sample_offsets"], np.arange(-256, 768)),
                    "Original sample offsets required")
            selected = [r for r in records if r["trial_id"].startswith(case + "-")]
            if case in CASES:
                require(set(ids) == {r["trial_id"] for r in selected}, "Waveform/programme coverage differs")
                require("labels" not in feature.files, "Development labels are forbidden")
            if not selected:
                continue
            raw_pin = {k: roles["signal"][k] for k in ("bytes", "sha256")}
            raw_body = pinned(Path(asset_root) / roles["signal"]["path"], raw_pin)
            inputs[case + "/signal.npy"] = raw_pin
            signal = np.load(io.BytesIO(raw_body), allow_pickle=False)
            require(signal.shape == (200, 33, 1024) and signal.dtype == np.float32,
                    "Original complete raw geometry required")
            for row in selected:
                position = ids.index(row["trial_id"])
                raw = signal[position].astype(np.float64)
                expected = raw[[channels.index("Cz"), channels.index("Pz")]] - (
                    raw[channels.index("P9")] + raw[channels.index("P10")]) / 2
                expected -= expected[:, :256].mean(axis=1, keepdims=True)
                observed = np.asarray(row["channels"], dtype=np.float64)
                require(observed.shape == (2, 1024) and np.array_equal(observed, expected),
                        "Waveform differs from pinned raw source")
                if row in demos:
                    require(row["target"] == int(feature["labels"][position]), "Demo label mismatch")
                checked += 1
    require(checked == 404, "Every query and demonstration must authenticate")
    return feature_bodies, inputs


def write(path, body):
    with Path(path).open("xb") as destination:
        destination.write(body)
        destination.flush()
        os.fsync(destination.fileno())


def build(packet, asset_root, output):
    modules = dependencies()
    members = packet_members(packet, modules["exporter"])
    feature_bodies, source_inputs = verify_signals(members, asset_root, modules["assets"])
    output = Path(output)
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    inventory = {}
    try:
        public = output / "public"
        public.mkdir(mode=0o700)
        for name, body in members.items():
            write(public / name, body)
            inventory["public/" + name] = descriptor(body)
        context_inventory = {}
        for condition in CONDITIONS:
            root = output / condition
            root.mkdir(mode=0o700)
            h = hashlib.sha256()
            size = count = 0
            with (root / "contexts.jsonl").open("xb") as destination:
                for row in context_rows(members, condition):
                    raw = encoded(row)
                    destination.write(raw)
                    h.update(raw)
                    size += len(raw)
                    count += 1
                destination.flush()
                os.fsync(destination.fileno())
            require(count == 400 and size <= 128 * 1024 * 1024, "Complete bounded contexts required")
            context_inventory[condition] = {"bytes": size, "sha256": h.hexdigest()}
            inventory[condition + "/contexts.jsonl"] = context_inventory[condition]
        feature_root = output / "ordinary_feature_programme"
        feature_root.mkdir(mode=0o700)
        for case, body in feature_bodies.items():
            (feature_root / case).mkdir(mode=0o700)
            write(feature_root / case / "features.npz", body)
            inventory["ordinary_feature_programme/" + case + "/features.npz"] = descriptor(body)
        ids = json.loads(members["manifest.json"])["development_ids"]
        receipt = {"schema": "neural077_complete_condition_delivery_v1", "task_id": "NEURAL-077",
                   "status": "authentic_materialization_no_model_execution", "queries": 400,
                   "cases": {case: 200 for case in CASES}, "demonstrations": 4,
                   "case_roster_sha256": descriptor(encoded(ids))["sha256"],
                   "raw_waveforms_checked": 404, "exact_float64_sample_equality": True,
                   "feature_training_cases": 6, "feature_training_labels": 1200,
                   "condition_contexts": context_inventory, "inventory": inventory,
                   "source_inputs": source_inputs, "model_calls": 0, "private_target_reads": 0,
                   "no_tools_transport_qualified": False, "per_query_programme_isolation_qualified": False,
                   "scientific_result": False, "new_benchmark_ids": 0}
        write(output / "COMPLETE.json", encoded(receipt))
        return receipt
    except Exception as error:
        write(output / "FAILED.json", encoded({"status": "incomplete_delivery", "reason": str(error)}))
        raise


def response_values(raw, contexts, parser):
    """Bind each raw answer to its attempted query, not merely its claimed ID."""
    require(0 < len(raw) <= MAX_RESPONSES, "Bounded response ledger required")
    lines = raw.splitlines()
    require(len(lines) == 400, "Exactly400 attempts required; failures may not be omitted or retried")
    expected = {r["ordinal"]: r for r in contexts}
    seen = {}
    for line in lines:
        require(len(line) <= 16384, "Bounded attempt envelope required")
        envelope = json.loads(line.decode("utf-8"), object_pairs_hook=parser.pairs)
        require(type(envelope) is dict and set(envelope) == {
            "ordinal", "trial_id", "context_sha256", "status", "response", "error"},
            "Exact request/response envelope required")
        ordinal = envelope["ordinal"]
        require(type(ordinal) is int and ordinal in expected and ordinal not in seen,
                "Unknown/duplicate attempt ordinal")
        request = expected[ordinal]
        require(envelope["trial_id"] == request["trial_id"]
                and envelope["context_sha256"] == request["context_sha256"],
                "Original request identity/context mismatch")
        require(envelope["status"] == "ok" and envelope["error"] is None,
                "An attempted query failed; retain complete ledger, no partial submission")
        require(type(envelope["response"]) is str, "Raw UTF-8 response string required")
        seen[ordinal] = parser.parse(envelope["response"].encode("utf-8"), request["trial_id"])
    require(set(seen) == set(expected), "Missing request identities")
    return [seen[i] for i in range(400)]


def collect(delivery, condition, responses, output):
    modules = dependencies()
    members = packet_members(Path(delivery) / "public", modules["exporter"])
    contexts = list(context_rows(members, condition))
    output = Path(output)
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    raw = None
    try:
        raw = read_regular(responses, MAX_RESPONSES)
        # Preserve every returned body and every failure before admission.
        write(output / "attempts.jsonl", raw)
        values = response_values(raw, contexts, modules["response"])
        import numpy as np
        ids = [r["trial_id"] for r in contexts]
        with (output / "submission.npz").open("xb") as destination:
            np.savez(destination, trial_ids=np.asarray(ids, dtype="<U48"),
                     target_probability=np.asarray(values, dtype=np.float64))
            destination.flush()
            os.fsync(destination.fileno())
        expected = {case: np.asarray([x for x in ids if x.startswith(case + "-")]) for case in CASES}
        modules["validator"].validate(output / "submission.npz", expected)
        receipt = {"schema": "neural077_complete_response_admission_v1", "condition": condition,
                   "status": "complete_unscored_submission", "responses": 400,
                   "cases": {case: 200 for case in CASES}, "attempts": descriptor(raw),
                   "submission": descriptor((output / "submission.npz").read_bytes()),
                   "case_roster_sha256": descriptor(encoded(ids))["sha256"],
                   "private_target_reads": 0, "scoring_performed": False,
                   "transport_enforcement_qualified": False}
        write(output / "COMPLETE.json", encoded(receipt))
        return receipt
    except Exception as error:
        write(output / "FAILED.json", encoded({"status": "response_admission_failed",
              "reason": str(error), "attempts": descriptor(raw) if raw is not None else None,
              "private_target_reads": 0, "scoring_performed": False}))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--packet", type=Path, required=True)
    build_parser.add_argument("--asset-root", type=Path, required=True)
    build_parser.add_argument("--output", type=Path, required=True)
    collect_parser = sub.add_parser("collect")
    collect_parser.add_argument("--delivery", type=Path, required=True)
    collect_parser.add_argument("--condition", choices=CONDITIONS, required=True)
    collect_parser.add_argument("--responses", type=Path, required=True)
    collect_parser.add_argument("--output", type=Path, required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    try:
        result = build(**args) if command == "build" else collect(**args)
    except (ValueError, OSError, KeyError, TypeError, UnicodeError) as error:
        print("Delivery refused: " + str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
