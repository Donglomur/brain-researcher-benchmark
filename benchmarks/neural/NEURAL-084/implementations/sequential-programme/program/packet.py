"""NEURAL084 complete54 public packet custody; opaque array bytes only.

The controller injects authenticated `c` (reviewed common API). External input
review admits numerical schema/finite values/full-source joins. This module
never opens pool/gold/key bodies, interprets NPY, or fits/scores a method.
"""
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

INDEX_CAP = 131072
FOLD_CAP = 262144
JSON_CAP = 5000000
ARRAY_CAP = 400000000  # exact stage_fold.save transport ceiling
PRED_CAP = 262144
NATIVE_CAP = 262144
TREE_CAP = 1073741824
CHUNK = 65536
PEOPLE = tuple(range(1, 55))
SESSIONS = (1, 2)
PHASES = ("train", "test")
CLASSES = (1, 2, 3, 4)
QUERY_COUNT = 400
TRAINING_COUNT = 21200
CLASS_CELL_COUNT = 25
FILES = ("fold.json", "training.npy", "training.json", "queries.npy")
CAPS = {"fold.json": FOLD_CAP, "training.json": JSON_CAP,
        "training.npy": ARRAY_CAP, "queries.npy": ARRAY_CAP}
DOCS = ()


def decode(raw):
    """Exact public io_utils.decode numeric/UTF8 policy, without file reads."""
    c.need(type(raw) is bytes, "strict JSON bytes")

    def pairs(rows):
        result = {}
        for key, value in rows:
            c.need(key not in result, "Duplicate JSON field")
            result[key] = value
        return result

    def finite(value):
        number = float(value)
        c.need(math.isfinite(number), "Finite JSON number")
        return number

    def integer(value):
        c.need(len(value) <= 18, "Bounded integer")
        return int(value)

    def invalid(value):
        raise ValueError("Nonstandard JSON constant")

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                          parse_float=finite, parse_int=integer, parse_constant=invalid)
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("Malformed bounded JSON") from error


def _exact(value, fields, message):
    c.need(type(value) is dict and set(value) == set(fields), message)


def _pin(value, cap):
    c.exact_pin(value)
    c.need(value["bytes"] <= cap, "bounded selected packet pin")
    return dict(value)


def _descriptor(value, name):
    _exact(value, ("path", "bytes", "sha256"), "exact named public descriptor")
    c.need(value["path"] == name, "literal four-member public path")
    return _pin(c.only_pin(value), CAPS[name])


def _generation(value):
    c.need(type(value) is str, "string generation")
    try:
        c.need(0 < len(value.encode("utf-8")) <= 256, "bounded nonempty generation")
    except UnicodeError as error:
        raise ValueError("UTF8 generation") from error


def _ids(ids, count):
    c.need(type(ids) is list and len(ids) == count, "complete ordered opaque IDs")
    previous = None
    for identity in ids:
        c.need(type(identity) is str and re.fullmatch("[0-9a-f]{64}", identity), "opaque64hex ID")
        c.need(previous is None or previous < identity, "strictly sorted unique IDs")
        previous = identity
    return ids


def _fold_contract(fold, person, generation):
    _exact(fold, ("schema", "generation", "fold", "ids", "classes", "training",
                  "queries", "training_metadata"), "exact public fold fields")
    c.need(fold["schema"] == "neural084_fold_v1", "source fold schema")
    _generation(fold["generation"])
    c.need(fold["generation"] == generation and fold["fold"] == "fold%03d" % person,
           "exact generation and held-person fold")
    c.need(type(fold["classes"]) is list and fold["classes"] == list(CLASSES)
           and all(type(value) is int for value in fold["classes"]), "exact four source classes")
    _ids(fold["ids"], QUERY_COUNT)
    return {
        "training.npy": _descriptor(fold["training"], "training.npy"),
        "queries.npy": _descriptor(fold["queries"], "queries.npy"),
        "training.json": _descriptor(fold["training_metadata"], "training.json"),
    }


def _training_rows(rows, held, query_ids):
    """Streaming semantic helper; the public JSON entry enforces a full list.

    Keeping only a previous ID and cell counter avoids retaining a duplicate
    21,200-ID set. Strict increasing order establishes training uniqueness.
    """
    query_ids = set(query_ids)
    counts = Counter()
    previous = None
    total = 0
    for row in rows:
        total += 1
        c.need(total <= TRAINING_COUNT, "bounded complete training row count")
        _exact(row, ("id", "label", "person", "session", "phase"), "exact public training row fields")
        identity = row["id"]
        c.need(type(identity) is str and re.fullmatch("[0-9a-f]{64}", identity), "opaque training ID")
        c.need(previous is None or previous < identity, "strict sorted unique training IDs")
        c.need(identity not in query_ids, "training/query identity disjointness")
        previous = identity
        person, session, phase, label = row["person"], row["session"], row["phase"], row["label"]
        c.need(type(person) is int and person in PEOPLE and person != held, "all training people exclude held person")
        c.need(type(session) is int and session in SESSIONS and type(phase) is str and phase in PHASES,
               "exact source session and acquisition phase")
        c.need(type(label) is int and label in CLASSES, "exact source training class")
        counts[(person, session, phase, label)] += 1
        c.need(counts[(person, session, phase, label)] <= CLASS_CELL_COUNT, "bounded class support per source cell")
    expected = {(person, session, phase, label) for person in PEOPLE if person != held
                for session in SESSIONS for phase in PHASES for label in CLASSES}
    c.need(total == TRAINING_COUNT and set(counts) == expected
           and set(counts.values()) == {CLASS_CELL_COUNT}, "full53people two-session two-phase25-per-class training")
    return dict(rows=total, people=len(PEOPLE) - 1, class_cells=len(expected), trials_per_class_cell=CLASS_CELL_COUNT)


def training_contract(training, held, query_ids):
    _exact(training, ("schema", "rows"), "exact source training metadata")
    c.need(training["schema"] == "neural084_training_v1" and type(training["rows"]) is list
           and len(training["rows"]) == TRAINING_COUNT, "complete21200 public training rows")
    return _training_rows(iter(training["rows"]), held, query_ids)


def _root(value):
    c.need(type(value) is str and len(value.encode("utf-8")) <= 4096
           and Path(value).is_absolute() and Path(value).as_posix() == value, "canonical absolute public root")
    return c.path(value)


def _snapshot(root, expected, *, current, cap=TREE_CAP):
    root = c.path(root)
    before = root.lstat()
    c.need(stat.S_ISDIR(before.st_mode), "ordinary packet directory")
    allowed = (0o555,) if current else (0o700, 0o555)
    c.need(stat.S_IMODE(before.st_mode) in allowed, "source stage/sealed or readonly current directory")
    files, dirs, _ = c.inventory(root, cap, 8)
    c.need(set(files) == set(FILES) == set(expected) and dirs == [root], "exact four-file packet tree")
    for name, (_, stamp) in files.items():
        _pin(expected[name], CAPS[name])
        c.need(stamp[4] == expected[name]["bytes"] and stat.S_IMODE(stamp[2]) == 0o444,
               "readonly exact packet member extent")
    c.need(c.stamp(before) == c.stamp(root.lstat()), "stable packet directory inventory")
    return {"root": c.stamp(before), "files": {name: files[name][1] for name in FILES}}


def _read_meta(root, name, expected, budget):
    budget.tick()
    source = c.path(root / name)
    before = source.lstat()
    c.need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
           and stat.S_IMODE(before.st_mode) == 0o444, "readonly ordinary public JSON")
    raw = c.capture(source, CAPS[name], expected, budget.tick, budget.read)
    after = source.lstat()
    c.need(c.stamp(before) == c.stamp(after), "stable public metadata custody")
    parsed = decode(raw)
    budget.tick()
    return parsed, c.stamp(after)


def _close_all(*descriptors):
    """Attempt every close; keep the active operation error and cleanup notes."""
    primary = sys.exc_info()[1]
    failures = []
    for descriptor in descriptors:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except BaseException as error:
                failures.append(error)
    if failures and primary is not None:
        for error in failures:
            primary.add_note("Descriptor cleanup also failed: " + type(error).__name__ + ": " + str(error))
    elif len(failures) == 1:
        raise failures[0]
    elif failures:
        raise BaseExceptionGroup("Independent descriptor cleanup failures", failures)


def _stream_file(source, expected, budget, destination=None):
    """Authenticate/copy bytes in <=64KiB chunks, never interpreting NPY.

    One full size+1 read reservation, and one full-size write reservation if
    copying. Failures retain both charges and any created partial destination.
    """
    budget.tick()
    source = c.path(source)
    expected = c.exact_pin(expected)
    if destination is not None:
        destination = c.path(destination)
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    out = None
    try:
        initial = os.fstat(fd)
        c.need(stat.S_ISREG(initial.st_mode) and initial.st_nlink == 1
               and initial.st_size == expected["bytes"] and stat.S_IMODE(initial.st_mode) == 0o444,
               "exact readonly ordinary selected source")
        budget.read(initial.st_size + 1)
        if destination is not None:
            budget.write(initial.st_size)
            budget.tick()
            out = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        digest = hashlib.sha256()
        count = 0
        while True:
            budget.tick()
            block = os.read(fd, min(CHUNK, initial.st_size + 1 - count))
            budget.tick()
            if not block:
                break
            c.need(count + len(block) <= initial.st_size, "source did not grow")
            count += len(block)
            digest.update(block)
            if out is not None:
                view = memoryview(block)
                while view:
                    budget.tick()
                    written = os.write(out, view)
                    budget.tick()
                    c.need(written > 0, "complete streaming write progress")
                    view = view[written:]
        c.need(count == initial.st_size and digest.hexdigest() == expected["sha256"], "complete selected byte identity")
        c.need(c.stamp(initial) == c.stamp(os.fstat(fd)) == c.stamp(source.lstat()), "stable complete source stream")
        if out is not None:
            budget.tick()
            os.fchmod(out, 0o444)
            os.fsync(out)
            budget.tick()
            written_stat = os.fstat(out)
            c.need(stat.S_ISREG(written_stat.st_mode) and written_stat.st_nlink == 1
                   and written_stat.st_size == expected["bytes"]
                   and c.stamp(written_stat) == c.stamp(destination.lstat()), "same complete published destination")
    finally:
        _close_all(out, fd)
    if destination is not None:
        c.sync_dir(destination.parent, budget.tick)
    budget.tick()
    return c.stamp(initial)


def inspect_fold(entry, generation, budget):
    _exact(entry, ("person", "public_root", "fold.json"), "exact operator fold descriptor")
    person = entry["person"]
    c.need(type(person) is int and person in PEOPLE, "designated held person1..54")
    root = _root(entry["public_root"])
    root_stamp = c.stamp(root.lstat())
    fold_pin = _pin(entry["fold.json"], FOLD_CAP)
    fold, fold_stamp = _read_meta(root, "fold.json", fold_pin, budget)
    files = _fold_contract(fold, person, generation)
    files["fold.json"] = fold_pin
    # Check complete public-only inventory BEFORE opening any nonmetadata body.
    initial = _snapshot(root, files, current=False)
    c.need(initial["root"] == root_stamp and initial["files"]["fold.json"] == fold_stamp,
           "same initial source directory/fold metadata")
    training, training_stamp = _read_meta(root, "training.json", files["training.json"], budget)
    training_summary = training_contract(training, person, fold["ids"])
    del training
    stamps = {"fold.json": fold_stamp, "training.json": training_stamp}
    for name in ("training.npy", "queries.npy"):
        stamps[name] = _stream_file(root / name, files[name], budget)
    final = _snapshot(root, files, current=False)
    c.need(final == initial and final["files"] == stamps, "whole original packet stayed unchanged during admission")
    budget.tick()
    return dict(person=person, root=root, fold=fold, files=files, stamps=final,
                training_summary=training_summary, total_bytes=sum(pin["bytes"] for pin in files.values()))


def inspect_index(raw, budget):
    c.need(type(raw) is bytes and 0 < len(raw) <= INDEX_CAP, "bounded complete input index")
    index = decode(raw)
    _exact(index, ("schema", "generation", "folds"), "acyclic public input index fields")
    c.need(index["schema"] == "neural084-full54-input-index-v1", "complete54 index schema")
    _generation(index["generation"])
    entries = index["folds"]
    c.need(type(entries) is list and len(entries) == len(PEOPLE)
           and all(type(entry) is dict for entry in entries)
           and [entry.get("person") for entry in entries] == list(PEOPLE)
           and all(type(entry.get("person")) is int for entry in entries), "all54 held people in original order")
    roots = [_root(entry.get("public_root")) for entry in entries]
    c.need(len(set(roots)) == len(PEOPLE), "distinct original public roots")
    for ordinal, root in enumerate(roots):
        for other in roots[ordinal + 1:]:
            c.need(not root.is_relative_to(other) and not other.is_relative_to(root), "nonoverlapping public roots")
    rows = []
    query_ids = set()
    for entry in entries:
        budget.tick()
        row = inspect_fold(entry, index["generation"], budget)
        c.need(not query_ids.intersection(row["fold"]["ids"]), "disjoint held-person query identities across54folds")
        query_ids.update(row["fold"]["ids"])
        rows.append(row)
    c.need(len(query_ids) == len(PEOPLE) * QUERY_COUNT, "complete21600 query identity support")
    plan = dict(contexts=54, query_count=21600, training_per_context=21200,
                files=216, public_bytes=sum(row["total_bytes"] for row in rows),
                max_fold_bytes=max(row["total_bytes"] for row in rows))
    budget.tick()
    return index, rows, plan


def _owned_current(current, budget):
    current = c.path(current)
    c.need(current != budget.root and current.is_relative_to(budget.root), "current view inside owned execution root")
    return current


def view(current, row, docs, budget):
    current = _owned_current(current, budget)
    c.need(type(docs) is dict and not docs, "exact four-file view; no extra documents")
    c.need(not current.exists() and current.parent.is_dir(), "fresh current packet path")
    c.need(not current.is_relative_to(row["root"]) and not row["root"].is_relative_to(current),
           "owned view separate from original source")
    unchanged(row, budget)
    budget.capacity(16384)
    current.mkdir(mode=0o700)
    expected = {name: dict(row["files"][name]) for name in FILES}
    for name in FILES:
        _stream_file(row["root"] / name, expected[name], budget, current / name)
    budget.tick()
    os.chmod(current, 0o555)
    c.sync_dir(current, budget.tick)
    c.sync_dir(current.parent, budget.tick)
    budget.tick()
    return expected


def verify_view(current, expected, budget):
    current = _owned_current(current, budget)
    budget.tick()
    initial = _snapshot(current, expected, current=True, cap=budget.limits["retained"])
    for name in FILES:
        observed = _stream_file(current / name, expected[name], budget)
        c.need(observed == initial["files"][name], "same member during view verification")
    final = _snapshot(current, expected, current=True, cap=budget.limits["retained"])
    c.need(final == initial, "same complete current view during verification")
    budget.tick()
    return final


def retire(current, expected, stamps, budget):
    """Retire only the final hash-verified snapshot, with no extra body pass."""
    current = _owned_current(current, budget)
    budget.tick()
    # Observe the WHOLE owned allocation before deletion can free any capacity.
    # Retiring a view never hides an oversized candidate/output tree or refunds
    # its previous logical read/write reservations.
    budget.capacity()
    c.need(_snapshot(current, expected, current=True, cap=budget.limits["retained"]) == stamps,
           "same final trusted view before retirement")
    fd = os.open(current, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        c.need(c.stamp(os.fstat(fd)) == stamps["root"], "same owned retirement directory")
        budget.tick()
        os.fchmod(fd, 0o700)
        for name in FILES:
            budget.tick()
            observed = os.stat(name, dir_fd=fd, follow_symlinks=False)
            c.need(c.stamp(observed) == stamps["files"][name], "same trusted retirement member")
            os.unlink(name, dir_fd=fd)
            budget.tick()
        os.fsync(fd)
        budget.tick()
        c.need(c.stamp(os.fstat(fd)) == c.stamp(current.lstat()), "same empty owned directory before removal")
        os.rmdir(current)
        budget.tick()
    finally:
        _close_all(fd)
    c.sync_dir(current.parent, budget.tick)


def unchanged(row, budget):
    budget.tick()
    c.need(_snapshot(row["root"], row["files"], current=False) == row["stamps"],
           "original whole public packet unchanged")
    budget.tick()


def prediction(raw, fold):
    c.need(type(raw) is bytes and 0 < len(raw) <= PRED_CAP, "bounded complete262144-byte prediction")
    value = decode(raw)
    c.need(type(fold) is dict, "supplied public fold object")
    _ids(fold.get("ids"), QUERY_COUNT)
    _exact(value, ("schema", "generation", "fold", "predictions"), "exact public prediction fields")
    c.need(value["schema"] == "neural084_scores_v1"
           and value["generation"] == fold["generation"] and value["fold"] == fold["fold"],
           "exact supplied prediction schema/generation/fold")
    predictions = value["predictions"]
    c.need(type(predictions) is list and len(predictions) == QUERY_COUNT, "all400 ordered predictions")
    for expected_id, row in zip(fold["ids"], predictions):
        _exact(row, ("id", "scores"), "exact prediction row fields")
        c.need(row["id"] == expected_id, "exact ordered query prediction identity")
        scores = row["scores"]
        c.need(type(scores) is list and len(scores) == len(CLASSES)
               and all(type(score) in (int, float) and math.isfinite(score) for score in scores),
               "four raw finite nonboolean scores")
    return value
