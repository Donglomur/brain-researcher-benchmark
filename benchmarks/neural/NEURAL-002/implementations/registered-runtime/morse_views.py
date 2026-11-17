"""Trusted full-fold serialization. Returned plans/receipts remain host-only.

Candidate code receives only the selected training or query root. It must never
receive FoldPlan, inverse, receipt, original records or this trusted process.
"""
from collections import Counter
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re

from packets import fold
from contract import PEOPLE, CELLS
from morse_codec import (REPRESENTATION, WINDOW_BYTES, ViewError, require,
                        encode_window, decode_window, read_regular, safe_path, sha256)

TOTAL = 9984
TRAINING = 9672
QUERY = 312


@dataclass(frozen=True)
class FoldPlan:
    training: tuple
    query: tuple
    arrays: dict
    inverse: dict
    held_participant: str
    namespace: str


def _id(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
            "expected opaque64hex identifier")
    return value


def _namespace(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is not None,
            "namespace must be a bounded opaque identifier")
    return value


def _json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _strict_json(body):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, "duplicate JSON key")
            out[k] = v
        return out
    def invalid(value):
        raise ViewError("nonfinite JSON constant")
    try:
        return json.loads(body, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, UnicodeError) as exc:
        raise ViewError("invalid serialized manifest") from exc


def _validate_inverse(inverse):
    require(type(inverse) is dict and len(inverse) == TOTAL, "full private inverse required")
    seen, counts, held = set(), Counter(), set()
    for alias, row in inverse.items():
        _id(alias)
        require(type(row) is dict and set(row) == {"canonicalid", "participant", "cell", "label", "role"},
                "private inverse schema")
        cid = _id(row["canonicalid"])
        require(cid not in seen, "duplicate canonical identifier")
        seen.add(cid)
        require(row["participant"] in PEOPLE and row["cell"] in CELLS,
                "private inverse group")
        require(type(row["label"]) is int and 0 <= row["label"] < 26, "private inverse label")
        require(row["role"] in ("training", "query"), "private inverse role")
        counts[row["participant"], row["cell"], row["label"]] += 1
        if row["role"] == "query":
            held.add(row["participant"])
    require(set(counts) == {(p, c, y) for p in PEOPLE for c in CELLS for y in range(26)}
            and set(counts.values()) == {2}, "full private inverse class support")
    require(len(held) == 1, "one held participant per fold")
    held = next(iter(held))
    require(all((row["role"] == "query") == (row["participant"] == held) for row in inverse.values()),
            "private role assignment mismatch")
    return held


def build_fold(records, held_participant, private_secret, namespace):
    """Build metadata using actual core fold; arrays are encoded only at export."""
    require(type(private_secret) is bytes and len(private_secret) >= 32, "host secret minimum32bytes")
    _namespace(namespace)
    require(type(records) is list and len(records) == TOTAL, "complete source records required")
    for row in records:
        require(type(row) is dict and set(row) == {"id", "participant", "cell", "x", "label"},
                "core record schema")
        _id(row["id"])
        require(type(row["label"]) is int and 0 <= row["label"] < 26, "integer class required")
    views, targets = fold(records, held_participant)
    require(len(views["training"]) == TRAINING and len(views["query"]) == QUERY
            and len(targets) == QUERY, "core fold sizes")
    by_id = {r["id"]: r for r in records}
    training, query, arrays, inverse = [], [], {}, {}
    domain = b"morse-fold-v1\0" + namespace.encode("ascii") + b"\0" + held_participant.encode("ascii") + b"\0"
    for role in ("training", "query"):
        for row in views[role]:
            original = by_id[row["id"]]
            alias = hmac.new(private_secret, domain + b"item\0" + row["id"].encode("ascii"), hashlib.sha256).hexdigest()
            require(alias not in inverse, "alias collision")
            arrays[alias] = row["x"]
            inverse[alias] = {"canonicalid": row["id"], "participant": original["participant"],
                              "cell": row["cell"], "label": original["label"], "role": role}
            public = {"id": alias, "cell": row["cell"]}
            if role == "training":
                group = hmac.new(private_secret, domain + b"group\0" + row["participant"].encode("ascii"), hashlib.sha256).hexdigest()
                public.update(group=group, label=row["label"])
                training.append(public)
            else:
                query.append(public)
    plan = FoldPlan(tuple(sorted(training, key=lambda r: r["id"])),
                    tuple(sorted(query, key=lambda r: r["id"])), arrays, inverse,
                    held_participant, namespace)
    _validate_plan(plan)
    return plan


def _validate_plan(plan):
    require(type(plan) is FoldPlan, "trusted FoldPlan required")
    _namespace(plan.namespace)
    require(_validate_inverse(plan.inverse) == plan.held_participant, "held participant differs")
    require(len(plan.training) == TRAINING and len(plan.query) == QUERY, "fold row counts")
    require(type(plan.arrays) is dict and set(plan.arrays) == set(plan.inverse), "array/inverse coverage")
    seen, person_groups, group_people = set(), {}, {}
    for role, rows in (("training", plan.training), ("query", plan.query)):
        require(type(rows) is tuple and [r["id"] for r in rows] == sorted(r["id"] for r in rows),
                "deterministic alias row order")
        for row in rows:
            expected = {"id", "group", "cell", "label"} if role == "training" else {"id", "cell"}
            require(type(row) is dict and set(row) == expected, "public metadata field boundary")
            alias = _id(row["id"])
            require(alias in plan.inverse and alias not in seen, "metadata alias mismatch")
            seen.add(alias)
            private = plan.inverse[alias]
            require(private["role"] == role and private["cell"] == row["cell"], "public/private role/cell mismatch")
            if role == "training":
                require(type(row["label"]) is int and row["label"] == private["label"], "training label mismatch")
                group = _id(row["group"])
                person = private["participant"]
                require(person_groups.setdefault(person, group) == group and
                        group_people.setdefault(group, person) == person, "training group bijection")
    require(seen == set(plan.inverse) and len(person_groups) == 31, "full public metadata coverage")


def _manifests(plan):
    return {role: _json({"role": role, "representation": REPRESENTATION, "rows": list(rows)})
            for role, rows in (("training", plan.training), ("query", plan.query))}


def planned_export_bytes(plan):
    _validate_plan(plan)
    return TOTAL * WINDOW_BYTES + sum(map(len, _manifests(plan).values()))


def _sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(body)
            stream.flush()
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_projection(root, role, rows, arrays, manifest_body):
    """Real I/O helper; small direct controls do not claim a full-fold export."""
    directory = root / role
    directory.mkdir(mode=0o700)
    (directory / "windows").mkdir(mode=0o700)
    files = []
    for row in rows:
        alias = _id(row["id"])
        body = encode_window(arrays[alias])  # Exactly one snapshot per array.
        relative = role + "/windows/" + alias + ".f32"
        _write(root / relative, body)
        files.append({"role": role, "alias": alias, "path": relative,
                      "bytes": len(body), "sha256": sha256(body)})
    _sync(directory / "windows")
    relative = role + "/manifest.json"
    _write(root / relative, manifest_body)  # Published last inside this root.
    _sync(directory)
    _sync(root)
    return files, {"path": relative, "bytes": len(manifest_body), "sha256": sha256(manifest_body)}


def export_fold(plan, destination, *, max_total_bytes):
    """Write one full fold only under an explicit capacity selection.

    No private inverse or host receipt is written beneath destination. Any
    failure preserves partial files and propagates; root must inspect before
    cleanup/retry. The caller separately budgets host receipts and overhead.
    """
    _validate_plan(plan)
    manifests = _manifests(plan)
    needed = TOTAL * WINDOW_BYTES + sum(map(len, manifests.values()))
    require(type(max_total_bytes) is int and max_total_bytes >= needed,
            "full-fold export capacity must be explicitly reserved")
    root = safe_path(destination)
    require(not root.exists(), "export destination must be absent")
    root.mkdir(mode=0o700)
    _sync(root.parent)
    files = []
    pins = {}
    for role, rows in (("training", plan.training), ("query", plan.query)):
        group, pins[role] = _write_projection(root, role, rows, plan.arrays, manifests[role])
        files.extend(group)
    require(len(files) == TOTAL, "full export tensor count")
    canonical = {plan.inverse[r["alias"]]["canonicalid"]: r["sha256"] for r in files}
    require(len(canonical) == TOTAL, "canonical serialized identity count")
    return {"representation": REPRESENTATION, "held_participant": plan.held_participant,
            "namespace": plan.namespace, "root": str(root),
            "training_root": str(root / "training"), "query_root": str(root / "query"),
            "training_manifest": pins["training"], "query_manifest": pins["query"],
            "files": files, "canonical_window_pins": canonical, "total_bytes": needed}


def _validate_receipt(receipt, inverse):
    require(type(receipt) is dict and set(receipt) == {"representation", "held_participant", "namespace",
            "root", "training_root", "query_root", "training_manifest", "query_manifest", "files",
            "canonical_window_pins", "total_bytes"}, "host export receipt schema")
    require(receipt["representation"] == REPRESENTATION, "representation changed")
    held = _validate_inverse(inverse)
    require(held == receipt["held_participant"], "receipt held person mismatch")
    _namespace(receipt["namespace"])
    root = safe_path(receipt["root"])
    require(receipt["training_root"] == str(root / "training") and
            receipt["query_root"] == str(root / "query"), "projection root mismatch")
    require(type(receipt["files"]) is list and len(receipt["files"]) == TOTAL, "receipt tensor count")
    by_alias, canonical, total = {}, {}, 0
    for row in receipt["files"]:
        require(type(row) is dict and set(row) == {"role", "alias", "path", "bytes", "sha256"}, "tensor receipt schema")
        alias = _id(row["alias"])
        require(alias in inverse and alias not in by_alias, "receipt alias coverage")
        role = inverse[alias]["role"]
        require(row["role"] == role and row["path"] == role + "/windows/" + alias + ".f32",
                "receipt canonical relative tensor path")
        require(type(row["bytes"]) is int and row["bytes"] == WINDOW_BYTES, "receipt tensor extent")
        _id(row["sha256"])
        by_alias[alias] = row
        canonical[inverse[alias]["canonicalid"]] = row["sha256"]
        total += WINDOW_BYTES
    require(set(by_alias) == set(inverse) and canonical == receipt["canonical_window_pins"],
            "canonical value identities differ")
    for role in ("training", "query"):
        pin = receipt[role + "_manifest"]
        require(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"}, "manifest pin schema")
        require(pin["path"] == role + "/manifest.json" and type(pin["bytes"]) is int and pin["bytes"] > 0,
                "canonical manifest path/extent")
        _id(pin["sha256"])
        total += pin["bytes"]
    require(type(receipt["total_bytes"]) is int and total == receipt["total_bytes"], "receipt total extent")
    return root, by_alias


def reconstruct_reference_records(receipt, private_inverse):
    """Owner-only decode from the exact candidate serialization, never originals."""
    root, tensors = _validate_receipt(receipt, private_inverse)
    seen, output, person_groups, group_people = set(), [], {}, {}
    for role in ("training", "query"):
        pin = receipt[role + "_manifest"]
        body = read_regular(root / pin["path"], pin["bytes"],
                            expected_bytes=pin["bytes"], expected_sha256=pin["sha256"])
        document = _strict_json(body)
        require(type(document) is dict and set(document) == {"role", "representation", "rows"}
                and document["role"] == role and document["representation"] == REPRESENTATION,
                "serialized candidate manifest schema")
        rows = document["rows"]
        require(type(rows) is list and len(rows) == (TRAINING if role == "training" else QUERY),
                "serialized candidate row count")
        aliases = []
        for row in rows:
            expected = {"id", "group", "cell", "label"} if role == "training" else {"id", "cell"}
            require(type(row) is dict and set(row) == expected, "serialized field boundary")
            alias = _id(row["id"])
            require(alias in private_inverse and alias not in seen, "serialized alias coverage")
            seen.add(alias)
            aliases.append(alias)
            private = private_inverse[alias]
            require(private["role"] == role and private["cell"] == row["cell"], "serialized role/cell mismatch")
            if role == "training":
                require(type(row["label"]) is int and row["label"] == private["label"], "serialized training target mismatch")
                group = _id(row["group"])
                person = private["participant"]
                require(person_groups.setdefault(person, group) == group and
                        group_people.setdefault(group, person) == person, "serialized group bijection")
            pin = tensors[alias]
            payload = read_regular(root / pin["path"], WINDOW_BYTES,
                                   expected_bytes=WINDOW_BYTES, expected_sha256=pin["sha256"])
            output.append({"id": private["canonicalid"], "participant": private["participant"],
                           "cell": private["cell"], "label": private["label"], "x": decode_window(payload)})
        require(aliases == sorted(aliases), "serialized alias order changed")
    require(seen == set(private_inverse) and len(person_groups) == 31, "reconstructed full coverage")
    # Actual core boundary validates the reconstructed metadata as well.
    fold(output, receipt["held_participant"])
    return sorted(output, key=lambda r: r["id"])


def compare_canonical_windows(reference_receipt, next_receipt):
    """Compare host receipts already authenticated by export/reconstruction."""
    require(type(reference_receipt) is dict and type(next_receipt) is dict, "host receipts required")
    require(reference_receipt.get("representation") == next_receipt.get("representation") == REPRESENTATION,
            "canonical representation changed across folds")
    a, b = reference_receipt.get("canonical_window_pins"), next_receipt.get("canonical_window_pins")
    require(type(a) is dict and type(b) is dict and len(a) == len(b) == TOTAL,
            "complete canonical identity maps required")
    for cid, digest in a.items():
        _id(cid)
        _id(digest)
    require(a == b, "canonical serialized values changed across folds")
    return True
