"""Training-only fUS reference selection; no native input or participant runner.

One invocation receives one outer fold's private training projection. It must
never receive a held-session intake, packet, label or assessment. Authentication
of the projection and fresh operator isolation are external prerequisites.
"""
import builtins
import hashlib
import json
import os
from pathlib import Path
import stat
import types
from fractions import Fraction


class SelectionError(ValueError):
    pass


DEPENDENCIES = {
    "roster": ("direction-scorer/roster.py", 2755,
        "0f1ac943d56edc5305be4ba74f5d27c8cfa626e555092b7a51a1f6f2641dd4c9"),
    "scorer": ("direction-scorer/scorer.py", 14874,
        "11d1b2a330d5c32c6c2ea93c5c54de5d58c9d4d31008ccafd235afa3a732ad50"),
    "reference": ("rendered-references-v1/reference.py", 11970,
        "ed37e6dda9d55e791f8bd751d787ea0d6c314a5c463d631f8266e01e5c73985a"),
    # Filled from the separately authored, frozen admission source before use.
    "admission": ("outer-training-selection-v1/admission.py", 10586, "66495eafec42da3dec4db0cb951e3419464237899261c1bf22b5b37405f57268"),
}
CONFIGURATIONS = (
    ("uniform", None), ("squared_distance", None), ("cosine", None),
    ("linear_ridge", 0.001), ("linear_ridge", 0.01),
    ("linear_ridge", 0.1), ("linear_ridge", 1),
    ("linear_ridge", 10), ("linear_ridge", 100),
)
MAX_FREEZE_BYTES = 1048576


def require(ok, message):
    if not ok:
        raise SelectionError(message)


def wire_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, ensure_ascii=True).encode("ascii")


def digest(body):
    return hashlib.sha256(body).hexdigest()


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def parse(body):
    try:
        return json.loads(body, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              SelectionError("nonfinite JSON")))
    except (ValueError, UnicodeError) as error:
        raise SelectionError("invalid JSON") from error


def _dependencies(root=None):
    """Execute bounded pinned bytes, never ambient roster imports or pyc."""
    root = Path(root) if root is not None else Path(__file__).resolve().parent.parent
    sources = {}
    for name, (relative, extent, sha) in DEPENDENCIES.items():
        path = root / relative
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            require(stat.S_ISREG(os.fstat(fd).st_mode), "ordinary dependency required")
            with os.fdopen(fd, "rb", closefd=False) as handle:
                body = handle.read(extent + 1)
            require(len(body) == extent and digest(body) == sha, "dependency identity: " + name)
            sources[name] = (path, body)
        finally:
            os.close(fd)
    modules = {}
    ordinary_import = builtins.__import__

    def private_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name in DEPENDENCIES:
            require(name in modules, "dependency order")
            return modules[name]
        return ordinary_import(name, globals, locals, fromlist, level)

    for name in DEPENDENCIES:
        path, body = sources[name]
        module = types.ModuleType("_fus_training_selection_" + name)
        module.__file__ = str(path)
        module.__dict__["__builtins__"] = {**vars(builtins), "__import__": private_import}
        exec(compile(body, str(path), "exec"), module.__dict__)
        modules[name] = module
    return modules


def rational(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def grouped_score(rows):
    """Exact arithmetic over existing scorer confusion/support, not new losses."""
    scores = {animal: [] for animal in ("L", "P")}
    for row in rows:
        require(len(row["class_support"]) == 8 and all(n > 0 for n in row["class_support"]),
                "complete query class support required")
        score = sum((Fraction(row["confusion"][i][i], row["class_support"][i])
                     for i in range(8)), Fraction()) / 8
        scores[row["animal"]].append(score)
    require(all(scores.values()), "both animals required")
    return sum((sum(values, Fraction()) / len(values) for values in scores.values()), Fraction()) / 2


def _packet(wire, descriptor, episode, reference, max_packet_bytes, max_map_pixels):
    require(type(wire) is bytes and len(wire) == descriptor["bytes"] and
            digest(wire) == descriptor["sha256"], "packet identity/extent mismatch")
    # Source parser checks complete PNGs, geometry, all masks and probability inputs.
    reference.decode_packet(wire, max_packet_bytes=max_packet_bytes, max_map_pixels=max_map_pixels)
    packet = parse(wire)
    require(packet["query_id"] == descriptor["query_id"] and
            packet["fold_key"] == episode["fold_key"], "episode/query identity mismatch")
    require([(m["map_id"], m["direction_degrees"]) for m in packet["calibration"]] ==
            [(t["query_id"], 45 * t["direction"]) for t in episode["calibration"]],
            "earliest calibration identities mismatch")
    require(all(m["scale"] == episode["scale"] and
                type(m["scale"]) is type(episode["scale"]) and
                m["native_hz"] == episode["native_hz"]
                for m in packet["calibration"] + [packet["query"]]), "nested scale/rate mismatch")
    return digest(wire_json({"calibration": packet["calibration"], "context": packet["context"]}))


def select_fold(manifest_wire, *, expected_manifest_sha256, load_packet,
                max_manifest_bytes, max_packet_bytes, max_total_packet_bytes,
                max_map_pixels, dependency_root=None):
    """Return private canonical freeze bytes only after complete training scoring.

    Missing inputs, mismatched packet bodies or unresolved admission abort the
    entire selection. Predictor exceptions/invalid rows are scored as incorrect,
    using the existing scorer, and never remove a query. The callback receives
    only an admitted training record and opaque query ID. No held callback exists.
    This is a trusted-owner source interface, not an adversarial process sandbox.
    """
    for bound in (max_manifest_bytes, max_packet_bytes, max_total_packet_bytes, max_map_pixels):
        require(type(bound) is int and bound > 0, "positive integer bounds")
    require(type(manifest_wire) is bytes and len(manifest_wire) <= max_manifest_bytes and
            digest(manifest_wire) == expected_manifest_sha256, "manifest extent/identity")
    require(callable(load_packet), "training packet callback required")
    modules = _dependencies(dependency_root)
    manifest = parse(manifest_wire)
    episodes = modules["admission"].admit(manifest, modules["roster"].ROSTER)
    total = sum(p["bytes"] for e in episodes for p in e["packets"])
    require(total <= max_total_packet_bytes and
            all(p["bytes"] <= max_packet_bytes for e in episodes for p in e["packets"]),
            "complete training packet extent exceeds bounds")
    scorer, reference = modules["scorer"], modules["reference"]
    candidate_sessions = [[] for _ in CONFIGURATIONS]
    failure_counts = [0] * len(CONFIGURATIONS)
    for episode in episodes:
        predictions = [[] for _ in CONFIGURATIONS]
        calibration_pin = None
        for descriptor in episode["packets"]:
            body = load_packet(episode["record_id"], descriptor["query_id"])
            current_pin = _packet(body, descriptor, episode, reference, max_packet_bytes, max_map_pixels)
            require(calibration_pin is None or calibration_pin == current_pin,
                    "calibration/context changed between queries")
            calibration_pin = current_pin
            for index, (method, ridge_lambda) in enumerate(CONFIGURATIONS):
                try:
                    row = reference.predict(body, method=method, ridge_lambda=ridge_lambda,
                                            max_packet_bytes=max_packet_bytes, max_map_pixels=max_map_pixels)
                except Exception:
                    failure_counts[index] += 1
                    continue  # existing prediction_index counts this fixed query as missing
                predictions[index].append(row)
        expected = {t["query_id"] for t in episode["queries"]}
        for index, rows in enumerate(predictions):
            values, issues, invalidate = scorer.prediction_index(rows, expected)
            score = scorer.session_score(episode["queries"], values, invalidate)
            candidate_sessions[index].append({"record_id": episode["record_id"],
                "animal": episode["animal"], "class_support": score["class_support"],
                "confusion": score["confusion"], "invalid_by_class": score["invalid_by_class"],
                "prediction_issues": issues, "whole_episode_invalid": invalidate})
    scores = [grouped_score(rows) for rows in candidate_sessions]
    # max keeps first element on exact ties: distance first, ascending lambda.
    template_index = max((1, 2), key=lambda index: scores[index])
    ridge_index = max(range(3, 9), key=lambda index: scores[index])
    result = {
        "schema": "fus_outer_training_selection_freeze_v1",
        "status": "complete_training_selection",
        "held_record_id": manifest["held_record_id"],
        "manifest_sha256": expected_manifest_sha256,
        "zero_reconciliation_sha256": manifest["zero_record"]["reconciliation_sha256"],
        "training_records": [e["record_id"] for e in episodes],
        "training_queries": sum(len(e["queries"]) for e in episodes),
        "training_packet_bytes": total,
        "dependencies": {key: {"bytes": val[1], "sha256": val[2]} for key, val in DEPENDENCIES.items()},
        "choices": {"uniform": {"method": "uniform", "ridge_lambda": None},
            "template": {"method": CONFIGURATIONS[template_index][0], "ridge_lambda": None},
            "ridge": {"method": "linear_ridge", "ridge_lambda": CONFIGURATIONS[ridge_index][1]}},
        "candidates": [{"method": method, "ridge_lambda": lam,
                        "equal_animal_session_balanced_accuracy": rational(scores[i]),
                        "predictor_exceptions": failure_counts[i], "sessions": candidate_sessions[i]}
                       for i, (method, lam) in enumerate(CONFIGURATIONS)],
        "selection_objective": "equal animal means of equal session eight-class balanced accuracy",
        "tie_order": "squared_distance before cosine; ridge lambda ascending",
        "native_source_authenticated": False, "protected_isolation_established": False,
        "scientifically_qualified": False,
    }
    frozen = wire_json(result)
    require(len(frozen) <= MAX_FREEZE_BYTES, "complete freeze exceeds fixed byte ceiling")
    return frozen


def publish_freeze(wire, path, *, expected_sha256):
    """Exclusive private file, fsynced file and parent; return only after success.

    Caller must keep its output directory protected and must not release held
    packets until return. On any failure, any retained partial file is NOT a
    successful freeze and must not be used. No retry or automatic cleanup.
    """
    require(type(wire) is bytes and len(wire) <= MAX_FREEZE_BYTES and digest(wire) == expected_sha256,
            "freeze identity/extent")
    value = parse(wire)
    require(type(value) is dict and value.get("schema") == "fus_outer_training_selection_freeze_v1"
            and value.get("status") == "complete_training_selection", "selection receipt required")
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o400)
    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(wire)
            handle.flush()
            os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return {"held_record_id": value["held_record_id"], "freeze_sha256": expected_sha256}


def verify_coverage(descriptors, *, dependency_root=None):
    """All48 descriptor roster only; no claim of process or scientific coverage."""
    modules = _dependencies(dependency_root)
    expected = [row[0] for row in modules["roster"].ROSTER if row[3] > 0]
    require(type(descriptors) is list and len(descriptors) == 48, "all48 descriptors required")
    for item, record_id in zip(descriptors, expected):
        require(type(item) is dict and set(item) == {"held_record_id", "freeze_sha256"} and
                item["held_record_id"] == record_id and modules["scorer"].pin(item["freeze_sha256"]),
                "canonical complete fold descriptors")
    return {"schema": "fus_selection_coverage_roster_v1", "positive_folds": 48,
            "zero_record": "L-S45-R1", "descriptor_sha256": digest(wire_json(descriptors)),
            "freeze_bodies_authenticated": False, "fresh_process_isolation_established": False,
            "scientifically_qualified": False}
