"""Bind the fixed MorseEEG inventory to content pins without opening EEG.

Trusted operator utility; no network, fitting, decoding, or execution admission.
Git-annex pointer bodies identify payloads; they are never treated as payloads.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

SOURCE_COMMIT = "d2e09f610d267b8b3679997f8bc4e52fe6ca402a"
INVENTORY_SHA256 = "3ec6ba3dcf60c49ee381126958a617a87eadfcbabce09a5cf8bd3eb12ab0af8e"
INVENTORY = Path(__file__).resolve().parents[1] / "registered-runtime" / "SOURCES.json"
PEOPLE = tuple(f"sub-{n:02d}" for n in range(1, 33))
TASKS = ("dotcount", "firstlast")
ANNEX_ROLES = {"header": ("header", ".vhdr", 2**20),
               "markers": ("markers", ".vmrk", 2**20),
               "eeg": ("signal", ".eeg", 8 * 2**30)}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs)


def inventory_rows():
    """Read only the unchanged, hash-pinned public source inventory."""
    body = INVENTORY.read_bytes()
    _require(hashlib.sha256(body).hexdigest() == INVENTORY_SHA256,
             "source inventory differs from reviewed version")
    document = _json(body)
    _require(document["source_commit"] == SOURCE_COMMIT and
             document["cohort_metadata"]["commit"] == SOURCE_COMMIT,
             "wrong source revision")
    return document["cohort_metadata"]["files"]


def authenticate_git_blob(descriptor, body):
    """Verify raw Git blob bytes, including Git's object-type/length framing."""
    _require(type(body) is bytes and type(descriptor) is dict,
             "descriptor and immutable bytes required")
    size, oid = descriptor.get("bytes"), descriptor.get("git_object")
    _require(type(size) is int and 0 < size <= 2**20 and len(body) == size,
             "Git blob extent differs")
    _require(type(oid) is str and re.fullmatch(r"[0-9a-f]{40}", oid),
             "Git SHA-1 object ID required")
    actual = hashlib.sha1(b"blob " + str(len(body)).encode("ascii") + b"\0" + body).hexdigest()
    _require(actual == oid, "Git blob identity differs")
    return body


def resolve_pointer(descriptor, body, *, extension, maximum):
    """Derive a provider pin from an authenticated SHA256E annex symlink."""
    _require(descriptor.get("git_mode") == "120000", "annex symlink mode required")
    authenticate_git_blob(descriptor, body)
    _require(len(body) <= 1024, "annex pointer bound")
    try:
        pointer = body.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("non-ASCII annex pointer") from exc
    # The task's sources live at sub-XX/eeg/: exactly two parents reach .git.
    # Validate syntax only: never resolve or dereference the symlink on disk.
    match = re.fullmatch(
        r"\.\./\.\./\.git/annex/objects/[A-Za-z0-9]+/[A-Za-z0-9]+/"
        r"(SHA256E-s([1-9][0-9]*)--([0-9a-f]{64})(\.[A-Za-z0-9]+))/\1",
        pointer,
    )
    _require(match is not None, "unsupported or malformed annex pointer")
    _require(match.group(4) == extension, "annex extension differs from source role")
    size = int(match.group(2))
    _require(size <= maximum, "payload exceeds existing provider role bound")
    return {"path": descriptor["path"], "bytes": size, "sha256": match.group(3)}


def _validated_rows(rows):
    _require(type(rows) is list and len(rows) == 64, "all64 recordings required")
    expected = {(p, t) for p in PEOPLE for t in TASKS}
    seen = set()
    for row in rows:
        key = (row.get("subject"), row.get("task"))
        _require(key in expected and key not in seen, "duplicate/unknown recording")
        seen.add(key)
        prefix = f"{key[0]}/eeg/{key[0]}_task-{key[1]}"
        for role, (_, extension, _) in ANNEX_ROLES.items():
            _require(row[role]["path"] == prefix + "_eeg" + extension,
                     "annex role/recording path differs")
        _require(row["events"]["path"] == prefix + "_events.tsv" and
                 row["events"]["git_mode"] == "100644", "event identity differs")
    _require(seen == expected, "incomplete32-person/two-task cohort")
    return sorted(rows, key=lambda r: (r["subject"], r["task"]))


def _compile_metadata(rows, pointer_bodies):
    rows = _validated_rows(rows)
    expected = {row[role]["path"] for row in rows for role in ANNEX_ROLES}
    _require(type(pointer_bodies) is dict and set(pointer_bodies) == expected,
             "exact192 annex pointer bodies required")
    result = []
    for row in rows:
        files = {}
        for role, (provider_role, extension, maximum) in ANNEX_ROLES.items():
            descriptor = row[role]
            files[provider_role] = resolve_pointer(
                descriptor, pointer_bodies[descriptor["path"]],
                extension=extension, maximum=maximum)
        result.append({"source_commit": SOURCE_COMMIT,
                       "participant": row["subject"], "task": row["task"],
                       "annex_payload_pins": files,
                       "events_git_blob": dict(row["events"])})
    return result


def compile_metadata(pointer_bodies):
    """Return all192 content pins plus64 unresolved event Git identities.

    This output is metadata, not a provider selection or evidence that a single
    annex payload is present. It contains no event rows or stimulus labels.
    """
    return _compile_metadata(inventory_rows(), pointer_bodies)


def compile_provider_selections(pointer_bodies, event_bodies):
    """Produce the existing provider's exact64 four-file selections.

    Event bodies must be supplied by an independently authorized operator; this
    function hashes them without parsing or exposing any trial/target value.
    Every selected signal/header/marker body still needs provider authentication.
    """
    metadata = compile_metadata(pointer_bodies)
    expected = {row["events_git_blob"]["path"] for row in metadata}
    _require(type(event_bodies) is dict and set(event_bodies) == expected,
             "exact64 event bodies required")
    selections = []
    for row in metadata:
        descriptor = row["events_git_blob"]
        body = authenticate_git_blob(descriptor, event_bodies[descriptor["path"]])
        files = {role: dict(pin) for role, pin in row["annex_payload_pins"].items()}
        files["events"] = {"path": descriptor["path"], "bytes": len(body),
                           "sha256": hashlib.sha256(body).hexdigest()}
        selections.append({"source_commit": SOURCE_COMMIT,
                           "participant": row["participant"], "task": row["task"],
                           "files": files})
    return selections
