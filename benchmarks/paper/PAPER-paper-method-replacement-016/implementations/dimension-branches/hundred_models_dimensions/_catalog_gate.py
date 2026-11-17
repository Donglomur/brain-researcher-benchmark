"""Full99 metadata compiler; no framework import, graph instantiation or weights.

`complete` describes an operator-admitted metadata closure, not empirical or
historical qualification. The operator must authenticate graph/output witnesses
outside this compiler. Merely declaring those claims cannot make them true.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

PROTOCOL_PIN = {"bytes": 144249, "sha256": "59a43129bda8f20c4de74f1022609d09c3d7b8f1db275cc6b7df05057c7e9d1c"}
INVENTORY_PIN = {"bytes": 93437, "sha256": "d202c0b6b0e15f5fd894a2c9456525dd3e698e00945500ae6427b4b9a8a53a9e"}
TASK = "PAPER-paper-method-replacement-016"
PROFILE = "author_5e802ae5_order_with_net2brain_0beb63d3_extraction"
MAX_METADATA_BYTES = 32 * 1024 * 1024
MAX_NAMES = 500000


def need(test, message):
    if not test:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode()


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def strict(raw):
    need(type(raw) is bytes and len(raw) <= MAX_METADATA_BYTES, "bounded metadata bytes")
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, "duplicate metadata key"); out[key] = value
        return out
    def number(text):
        value = float(text); need(math.isfinite(value), "finite metadata number"); return value
    def integer(text):
        need(len(text) <= 100, "bounded metadata integer"); return int(text)
    return json.loads(raw, object_pairs_hook=pairs, parse_float=number, parse_int=integer,
                      parse_constant=lambda _: need(False, "finite metadata constant"))


def descriptor(d):
    need(type(d) is dict and set(d) == {"bytes", "sha256"}
         and type(d["bytes"]) is int and d["bytes"] > 0
         and type(d["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", d["sha256"]), "positive byte/SHA descriptor")
    return d


def capture(path, expected, cap=MAX_METADATA_BYTES):
    descriptor(expected)
    p = Path(path).absolute()
    need(".." not in p.parts and not any(x.is_symlink() for x in (p, *p.parents)), "ordinary metadata path")
    need(expected["bytes"] <= cap, "metadata input bound")
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected["bytes"], "single-link exact metadata extent")
        with os.fdopen(fd, "rb", closefd=False) as stream: raw = stream.read(expected["bytes"] + 1)
        fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
        after, named = os.fstat(fd), p.lstat()
        need(all(getattr(before,k) == getattr(after,k) == getattr(named,k) for k in fields), "stable metadata custody")
    finally:
        os.close(fd)
    need(pin(raw) == expected, "exact metadata bytes")
    return raw


def contract(protocol_raw, inventory_raw):
    need(pin(protocol_raw) == PROTOCOL_PIN and pin(inventory_raw) == INVENTORY_PIN, "fixed full99 protocol/source inventory")
    protocol, inventory = strict(protocol_raw), strict(inventory_raw)
    need(protocol["task_id"] == TASK and protocol["full_model_count"] == 99
         and len(protocol["models"]) == len(inventory["models"]) == 99
         and len(protocol["subjects"]) == 10 and len(protocol["stimuli"]) == 102
         and len(protocol["roi_parts"]) == 17 and protocol["test_repetitions"] == 10,
         "complete published axes")
    need([m["config"] for m in protocol["models"]] == inventory["models"]
         and len({m["id"] for m in protocol["models"]}) == 99, "exact configuration order and identity")
    return protocol


def names(values, *, root=False):
    need(type(values) is list and len(values) <= MAX_NAMES, "bounded complete ordered names")
    need(all(type(x) is str and len(x) <= 512 and (x or root)
             and not any(c in x for c in ("/", "\\", "\0")) for x in values), "safe module or feature names")
    need(len(set(values)) == len(values), "unique source names")
    return list(values)


def normalize(values):
    out = [x.replace(".", "_") for x in values]
    need(len(set(out)) == len(out), "dot-to-underscore namespace collision")
    return out


def source_order(model, graph=None):
    """Exact calc_alignment.py order, including immediate-next parent removal."""
    explicit = model["config"].get("layers")
    skips = names(model["config"].get("rsa_skips", []))
    if explicit:
        raw = names(explicit)
        if graph is not None: need(set(raw) <= set(graph), "explicit source layers missing in admitted graph")
        order = normalize(raw)
    else:
        need(graph is not None, "framework graph metadata required")
        raw = [x for x in names(graph, root=True) if x not in ("", "data_preprocessor") and not re.search(r"\d\.", x)]
        order = normalize(raw)
        remove = {left for left, right in zip(order, order[1:]) if right.startswith(left + "_")}
        order = [x for x in order if x not in remove]
    return [x for x in order if x not in skips]


def extraction_selection(model, graph):
    """Pinned NetSetBase rule; JSON network_layers branch is commented out."""
    graph = names(graph, root=True)
    explicit = model["config"].get("layers")
    if explicit:
        need(set(explicit) <= set(graph), "no silent explicit-layer removal")
        return names(explicit)
    raw = [x for x in graph if x and not re.search(r"\d\.", x)]
    remove = {left for left, right in zip(raw, raw[1:]) if right.startswith(left + ".")}
    return [x for x in raw if x not in remove]


def _bound_model(model, record, protocol, admission):
    expected = {"model_id", "configuration", "profile", "framework_identity", "framework_source_files",
                "checkpoint", "named_modules", "emitted_feature_keys", "stimulus_order", "subjects",
                "emission_receipt", "graph_receipt", "all102_emission_keysets_identical", "evidence_origin"}
    need(type(record) is dict and set(record) == expected, "exact graph/output witness fields")
    need(record["model_id"] == model["id"] and record["configuration"] == pin(encoded(model["config"]))
         and record["profile"] == PROFILE, "model configuration and rule-profile identity")
    need(record["evidence_origin"] in ("operator_admitted_metadata", "invented_control"), "explicit evidence origin")
    need(type(record["framework_identity"]) is str and 0 < len(record["framework_identity"]) <= 512, "explicit framework identity")
    need(type(record["framework_source_files"]) is list and 0 < len(record["framework_source_files"]) <= 1024, "framework source closure")
    for d in record["framework_source_files"]: descriptor(d)
    for key in ("checkpoint", "emission_receipt", "graph_receipt"): descriptor(record[key])
    need(record["stimulus_order"] == pin(encoded(protocol["stimuli"]))
         and record["subjects"] == protocol["subjects"]
         and record["all102_emission_keysets_identical"] is True, "same full102 emission support")
    graph = names(record["named_modules"], root=True)
    need(graph and graph[0] == "", "complete traversal includes root first")
    emitted = names(record["emitted_feature_keys"])
    need(emitted, "nonempty emitted feature witness")
    output_names = normalize(emitted)
    expected_order = source_order(model, graph)
    selected = extraction_selection(model, graph)
    # Cleaners may emit tuple suffixes. A graph alone cannot prove those outputs
    # or assign a source numeric-order position; refuse ungrounded completion.
    eligible = set(output_names) - set(model["config"].get("rsa_skips", []))
    need(eligible == set(expected_order), "emitted unskipped names do not equal complete source layer order")
    need(expected_order, "source layer set must be nonempty")
    return {"layers": expected_order, "checkpoint_sha256": record["checkpoint"]["sha256"],
            "checkpoint": record["checkpoint"], "framework_identity": record["framework_identity"],
            "framework_source_files": record["framework_source_files"],
            "configuration": record["configuration"], "graph_witness": pin(encoded(record)),
            "graph_receipt": record["graph_receipt"], "emission_receipt": record["emission_receipt"],
            "operator_admission": admission, "extraction_selected_module_names": selected,
            "metadata_closure_complete": True, "historical_execution_proven": False,
            "evidence_origin": record["evidence_origin"]}


def compile_catalog(protocol_raw, inventory_raw, bindings_raw=None, admitted_binding_pin=None, *, require_complete=False):
    """Pure full99 compiler. The external admission pin is a caller trust input.

    No caller-supplied layer subset is accepted: it must equal the entire source
    rule plus the closed emission witness. Neither metadata nor a digest proves
    actual execution. The operator owns authentication/admission of the witness.
    """
    protocol = contract(protocol_raw, inventory_raw)
    bindings = {}
    if bindings_raw is not None:
        descriptor(admitted_binding_pin)
        need(pin(bindings_raw) == admitted_binding_pin, "separately admitted complete binding bytes")
        document = strict(bindings_raw)
        need(set(document) == {"schema", "protocol", "profile", "models"}
             and document["schema"] == "hundred_models_graph_metadata_v1"
             and document["protocol"] == PROTOCOL_PIN and document["profile"] == PROFILE
             and type(document["models"]) is list and len(document["models"]) <= 99, "bounded graph metadata schema")
        for record in document["models"]:
            need(type(record) is dict and type(record.get("model_id")) is str
                 and record["model_id"] not in bindings, "one graph witness per model")
            bindings[record["model_id"]] = record
        need(set(bindings) <= {m["id"] for m in protocol["models"]}, "no foreign model witness")
        need(sum(len(x.get("named_modules", [])) + len(x.get("emitted_feature_keys", [])) for x in bindings.values()) <= MAX_NAMES,
             "complete graph-name aggregate resource bound")
    else:
        need(admitted_binding_pin is None, "no unbound admission descriptor")
    output = {}
    gaps = []
    for model in protocol["models"]:
        key = model["id"]
        if key in bindings:
            output[key] = _bound_model(model, bindings[key], protocol, admitted_binding_pin)
        else:
            explicit = model["config"].get("layers")
            missing = ["checkpoint_bytes_identity", "framework_source_identity", "closed_graph_and_emission_witness"]
            if not explicit: missing.append("ordered_framework_module_graph")
            output[key] = {"layers": source_order(model) if explicit else None,
                "source_explicit_layers": explicit, "excluded_layers": model["config"].get("rsa_skips", []),
                "configuration": pin(encoded(model["config"])), "metadata_closure_complete": False,
                "checkpoint_sha256": None, "framework_identity": None, "missing": missing}
            gaps.append({"model_id": key, "missing": missing})
    complete = not gaps
    need(not require_complete or complete, "all99 admitted graph/checkpoint/framework/emission records required")
    return {"schema": "hundred_models_layer_catalog_v1", "task_id": TASK, "protocol": PROTOCOL_PIN,
            "profile": PROFILE, "complete": complete, "models": output,
            "model_order": [m["id"] for m in protocol["models"]],
            "model_count": 99, "explicit_source_layer_lists": 18, "default_framework_graphs": 81,
            "gaps": gaps, "historical_execution_proven": False, "scientific_execution_qualified": False,
            "checkpoint_bodies_read": False, "framework_instantiated": False,
            "admitted_bindings": admitted_binding_pin,
            "trust_boundary": "Caller authenticates admitted witness; compiler checks metadata identity/rules only."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True); parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--bindings", type=Path); parser.add_argument("--bindings-bytes", type=int); parser.add_argument("--bindings-sha256")
    parser.add_argument("--require-complete", action="store_true"); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    p = capture(args.protocol, PROTOCOL_PIN, 200000); inventory = capture(args.inventory, INVENTORY_PIN, 200000)
    expected = None; body = None
    if args.bindings:
        expected = {"bytes": args.bindings_bytes, "sha256": args.bindings_sha256}; body = capture(args.bindings, expected)
    else:
        need(args.bindings_bytes is None and args.bindings_sha256 is None, "no detached witness pin")
    result = compile_catalog(p, inventory, body, expected, require_complete=args.require_complete)
    raw = encoded(result); need(len(raw) <= MAX_METADATA_BYTES, "compiled metadata output bound")
    output = args.output.absolute()
    need(".." not in output.parts and not any(x.is_symlink() for x in (output, *output.parents)), "ordinary fresh catalog output")
    with output.open("xb") as stream: stream.write(raw)
    print(json.dumps({"complete": result["complete"], "unresolved_models": len(result["gaps"]), **pin(raw)}))


if __name__ == "__main__":
    main()
