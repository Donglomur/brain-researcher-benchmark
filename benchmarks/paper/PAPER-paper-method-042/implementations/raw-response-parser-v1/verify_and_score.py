#!/usr/bin/env python3
"""Verify captured UMBRAE raw responses before scoring their extracted snapshots.

Trusted operator custody only. External raw/roster commitments are required;
this operation does not attest who generated them or a historical converter exit.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import tempfile
import types
from typing import Any

HERE = Path(__file__).resolve().parent
ROLES = ("candidate", "official_baseline", "neural_free", "shuffled_neural")
SUBJECTS = ("S1", "S2", "S5", "S7")
MAX_INPUT_BYTES = 256 * 1024 * 1024
MAX_SMALL_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
DEPENDENCIES = {
    "grounding": ("../initial-evaluator-v1/grounding.py", 18770,
                  "14c7ba38ca656e7e5e1f8db11d6eb3ecc2e4dd06848aeb07c2e1212ccb1afa1d"),
    "raw": ("raw_response.py", 12269,
            "99bbc9ba86e04028ad8e4029b8a5746ce955dff8cc4bd465e8673ac12a2f7b3c"),
    "vector": ("../endpoint-vector-v2/endpoint_vector.py", 9917,
               "2a32ac480f91b4d643aca0162d24d8ee7a4891da932c7891713df04a107e837b"),
}


class CustodyError(ValueError):
    """A snapshot or its declared conversion relationship was rejected."""


def require(ok: bool, message: str) -> None:
    if not ok:
        raise CustodyError(message)


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _strict_json(body: bytes) -> Any:
    def constant(_):
        raise CustodyError("nonfinite JSON constant")
    def number(value):
        result = float(value)
        require(math.isfinite(result), "nonfinite JSON number")
        return result
    value = json.loads(body.decode("utf-8"), object_pairs_hook=_pairs,
                       parse_constant=constant, parse_float=number)
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            item.encode("utf-8")  # Reject escaped lone surrogates as well.
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return value


def _pin(body: bytes) -> dict:
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def _expected_pin(pin: Any) -> dict:
    require(isinstance(pin, dict) and set(pin) == {"bytes", "sha256"},
            "expected byte/SHA256 commitment required")
    require(type(pin["bytes"]) is int and 0 < pin["bytes"] <= MAX_INPUT_BYTES,
            "commitment byte bound")
    digest = pin["sha256"]
    require(isinstance(digest, str) and len(digest) == 64
            and all(c in "0123456789abcdef" for c in digest), "SHA256 commitment required")
    return dict(pin)


def _identity(info) -> tuple:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _ordinary_path(value) -> tuple[Path, tuple]:
    path = Path(os.path.abspath(value))
    require(path.resolve(strict=True) == path and not path.is_symlink(),
            "canonical non-symlink input path required")
    info = path.stat()
    require(stat.S_ISREG(info.st_mode), "ordinary input file required")
    return path, _identity(info)


def _prepare_paths(paths: dict, output_path=None) -> tuple[dict, Path | None]:
    """Reject role aliases using metadata before opening any input payload."""
    prepared, identities = {}, set()
    for label, value in paths.items():
        path, identity = _ordinary_path(value)
        require(identity[:2] not in identities, "input roles alias the same file")
        identities.add(identity[:2])
        prepared[label] = (path, identity)
    output = None
    if output_path is not None:
        output = Path(os.path.abspath(output_path))
        require(output.parent.resolve(strict=True) == output.parent,
                "canonical output parent required")
        require(not output.exists() and not output.is_symlink(), "output already exists")
        require(output not in {entry[0] for entry in prepared.values()}, "output aliases input")
    return prepared, output


def _capture(path: Path, identity: tuple, limit: int) -> tuple[Any, dict]:
    require(0 < identity[3] <= limit, "input exceeds declared byte bound")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(_identity(before) == identity and stat.S_ISREG(before.st_mode),
                "input changed before capture")
        body = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    require(_identity(after) == identity and _identity(path.lstat()) == identity,
            "input changed during capture")
    require(len(body) == identity[3] and len(body) <= limit, "input capture size mismatch")
    return _strict_json(body), _pin(body)


def _module(name: str, body: bytes, filename: Path, grounding=None):
    """Inject captured grounding in place of only the pinned path-loader prelude.

    Whole-source SHA/size authentication precedes this fixed AST adaptation.
    Function bodies, grammar, constants and arithmetic are compiled unchanged.
    The existing files themselves are never rewritten or imported by pathname.
    """
    tree = ast.parse(body, filename=str(filename))
    if grounding is not None:
        start, stop, spec_name = (19, 23, "_spec") if name == "raw" else (22, 26, "spec")
        removed = [node for node in tree.body if start <= node.lineno <= stop]
        require(len(removed) == 4 and [type(n) for n in removed] ==
                [ast.If, ast.Assign, ast.Assign, ast.Expr], "dependency loader shape changed")
        require(removed[0].lineno == start and removed[-1].end_lineno == stop,
                "dependency loader span changed")
        require([n.id for n in removed[1].targets if isinstance(n, ast.Name)] == [spec_name]
                and [n.id for n in removed[2].targets if isinstance(n, ast.Name)] == ["g"],
                "dependency loader names changed")
        tree.body = [node for node in tree.body if node not in removed]
    module = types.ModuleType("umbrae_custody_" + name)
    module.__file__ = str(filename)
    if grounding is not None:
        module.g = grounding
    exec(compile(tree, str(filename), "exec"), module.__dict__)
    return module


def load_kernels() -> tuple[Any, Any, Any, dict]:
    captured, pins = {}, {}
    for name, (relative, size, digest) in DEPENDENCIES.items():
        path = (HERE / relative).resolve(strict=True)
        with path.open("rb") as stream:
            body = stream.read(size + 1)
        require(_pin(body) == {"bytes": size, "sha256": digest},
                "reviewed dependency bytes changed")
        captured[name] = (body, path)
        pins[name] = {"path_relative_to_parser": relative, **_pin(body)}
    g = _module("grounding", *captured["grounding"])
    raw = _module("raw", *captured["raw"], grounding=g)
    vector = _module("vector", *captured["vector"], grounding=g)
    require(g.ROLES == ROLES and g.SUBJECTS == SUBJECTS, "reviewed population constants differ")
    return g, raw, vector, pins


def verify_and_score(raw_path, roster_path, conversion_path, contract_path,
                     annotations_path, image_order_path, *, expected_raw: dict,
                     expected_roster: dict, draws: int = 1000, seed: int = 0,
                     confidence: float = 0.95, output_path=None) -> dict:
    """Return a score only after authenticating and replaying all sixteen streams.

    The expected commitments come from the caller's independent capture authority,
    never from conversion.json. All scored values are the captured extracted JSON
    objects; neither the legacy file evaluator nor an input reopen is used.
    """
    expected_raw, expected_roster = _expected_pin(expected_raw), _expected_pin(expected_roster)
    conversion_path = Path(conversion_path)
    paths = {"raw_panel": raw_path, "query_roster": roster_path,
             "conversion": conversion_path, "contract": contract_path,
             "annotations": annotations_path, "image_order": image_order_path}
    for role in ROLES:
        for subject in SUBJECTS:
            paths[f"response/{role}/{subject}"] = conversion_path.parent / f"{role}-{subject}.json"
    prepared, output = _prepare_paths(paths, output_path)
    require(sum(identity[3] for _, identity in prepared.values()) <= MAX_TOTAL_BYTES,
            "combined input snapshots exceed declared byte bound")
    g, raw, vector, source_pins = load_kernels()
    values, pins = {}, {}
    for label, (path, identity) in prepared.items():
        limit = MAX_INPUT_BYTES if label == "raw_panel" else MAX_SMALL_BYTES
        values[label], pins[label] = _capture(path, identity, limit)
    require(pins["raw_panel"] == expected_raw and pins["query_roster"] == expected_roster,
            "independent raw/roster commitment mismatch")
    replay = raw.convert_panel(values["raw_panel"], values["query_roster"])
    conversion = values["conversion"]
    require(isinstance(conversion, dict) and conversion.get("complete") is True,
            "completed converter manifest required")
    core_keys = set(replay) - {"responses"}
    required_keys = core_keys | {"input_pins", "extracted_files", "raw_panel_value_sha256", "complete"}
    require(required_keys <= set(conversion) <= required_keys | {"extraction_comparison"},
            "conversion manifest fields differ")
    for key in core_keys:
        require(raw.canonical_sha256(conversion[key]) == raw.canonical_sha256(replay[key]),
                "conversion replay metadata mismatch")
    require(conversion["raw_panel_value_sha256"] == raw.canonical_sha256(values["raw_panel"]),
            "raw value commitment mismatch")
    input_pins = conversion["input_pins"]
    require(isinstance(input_pins, dict) and {"raw_panel", "query_roster"} <= set(input_pins)
            <= {"raw_panel", "query_roster", "comparison_extracted_panel"}, "conversion input pins differ")
    require(input_pins["raw_panel"] == expected_raw and input_pins["query_roster"] == expected_roster,
            "converter did not consume the independently committed raw/roster bytes")
    has_comparison = "extraction_comparison" in conversion
    require(has_comparison == ("comparison_extracted_panel" in input_pins),
            "incomplete optional comparison metadata")
    if has_comparison:
        _expected_pin(input_pins["comparison_extracted_panel"])
        require(isinstance(conversion["extraction_comparison"], dict), "comparison diagnostic must be an object")
    files = conversion["extracted_files"]
    require(isinstance(files, dict) and set(files) == set(ROLES), "exact extracted role roster required")
    extracted = {}
    for role in ROLES:
        require(isinstance(files[role], dict) and set(files[role]) == set(SUBJECTS),
                "exact extracted subject roster required")
        extracted[role] = {}
        for subject in SUBJECTS:
            label = f"response/{role}/{subject}"
            expected_file_pin = {"path": f"{role}-{subject}.json", **pins[label]}
            require(files[role][subject] == expected_file_pin, "extracted file byte pin mismatch")
            # Replay the unchanged converter's exact serialization, including
            # numeric image order and sorted category insertion order. A
            # canonical-value hash alone would erase those ordering differences.
            emitted = (json.dumps(replay["responses"][role][subject],
                                  ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
            require(pins[label] == _pin(emitted), "extracted bytes differ from converter replay")
            extracted[role][subject] = values[label]
    comparison = raw.extraction_comparison(replay, extracted)
    require(comparison["status"] == "equal_extracted_values", "extracted values differ from raw replay")
    contract, annotations, image_order = (values[k] for k in ("contract", "annotations", "image_order"))
    require(isinstance(contract, dict), "scoring contract must be an object")
    require(contract.get("profile") == replay["profile"], "conversion/scoring profile differs")
    targets = g.prepare_reference(annotations, image_order, contract.get("profile"))
    g.validate_design(contract, image_order)
    require(contract["annotations_sha256"] == pins["annotations"]["sha256"]
            and contract["image_order_sha256"] == pins["image_order"]["sha256"], "scoring reference pin mismatch")
    roster = values["query_roster"]
    require(set(roster) == set(image_order) and all(set(roster[i]) == set(annotations[i]) for i in roster),
            "raw query roster differs from scoring population, including empty images")
    contract_parent = prepared["contract"][0].parent
    rows, scores = {}, {}
    for role in ROLES:
        rows[role], scores[role] = {}, {}
        for subject in SUBJECTS:
            selected = Path(os.path.abspath(contract_parent / contract["runs"][role]["responses"][subject]))
            require(selected == prepared[f"response/{role}/{subject}"][0],
                    "scoring contract selects a different extracted file")
            rows[role][subject] = g.score_subject(targets, set(image_order), extracted[role][subject])
            scores[role][subject] = g.summarize(rows[role][subject])
    endpoint = vector.compare_vectors(rows, [str(i) for i in range(len(image_order))],
                                      draws=draws, seed=seed, confidence=confidence)
    result = {
        "schema": "umbrae-raw-vector-custody-score/v1", "task_id": g.TASK,
        "component": "umbrae_verified_raw_response_vector", "profile": contract["profile"],
        "complete": True, "qualification": "not_established", "authentic_reference_run": False,
        "custody": {"status": "verified_raw_to_extracted_to_vector",
                    "streams": len(ROLES) * len(SUBJECTS), "raw_replay": comparison,
                    "completion_authority": "this_successful_verification_operation_only",
                    "historical_converter_exit_observed": False,
                    "generation_attested": False,
                    "optional_comparison_diagnostic_consumed": False},
        "expected_capture_commitments": {"raw_panel": expected_raw, "query_roster": expected_roster},
        "input_pins": pins, "source_pins": source_pins,
        "source_loading": "authenticated_snapshot_AST_with_only_path_loader_replaced_by_captured_grounding",
        "population": {"subjects": list(SUBJECTS), "shared_images": len(image_order),
                       "queries_per_subject": len(targets)},
        "scores": scores, "row_scores": rows, "endpoint_vector": endpoint,
        "exposure_status": "matching declarations only; no execution attestation",
        "holds": g.HOLDS + [
            "The simultaneous bootstrap is a prospective diagnostic, not an accepted scientific decision rule.",
            "Published v2 values are documentary; a run named official_baseline is not execution attestation.",
            "External raw/roster commitments identify accepted capture bytes, not their producer or generation.",
            "This operation does not attest a historical converter exit or an optional extracted-panel comparison.",
            "Historical receipts are not relabeled; no reproduction, improvement or readiness is established.",
        ],
    }
    if output is not None:
        _publish(result, output)
    return result


def _publish(result: dict, output: Path) -> None:
    """Publish complete serialized bytes atomically and without overwriting."""
    body = (json.dumps(result, indent=2, allow_nan=False, ensure_ascii=False) + "\n").encode("utf-8")
    require(len(body) <= MAX_OUTPUT_BYTES, "score output exceeds declared byte bound")
    fd, name = tempfile.mkstemp(prefix="." + output.name + ".", suffix=".pending", dir=output.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            require(stream.write(body) == len(body), "short score output write")
            stream.flush()
            os.fsync(stream.fileno())
        # The final pathname never exposes a partial JSON body. link refuses an
        # existing destination, even if another writer created it after preflight.
        os.link(temporary, output)
    finally:
        try:
            temporary.unlink()
        except OSError:
            # A cleanup failure may leave only the private .pending copy; it
            # cannot turn a failed publication into a complete final result.
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("raw-panel", "query-roster", "conversion", "contract", "annotations", "image-order", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    for name in ("raw", "roster"):
        parser.add_argument("--expected-" + name + "-bytes", type=int, required=True)
        parser.add_argument("--expected-" + name + "-sha256", required=True)
    parser.add_argument("--draws", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--confidence", type=float, default=0.95)
    args = parser.parse_args()
    try:
        verify_and_score(args.raw_panel, args.query_roster, args.conversion, args.contract,
                         args.annotations, args.image_order,
                         expected_raw={"bytes": args.expected_raw_bytes, "sha256": args.expected_raw_sha256},
                         expected_roster={"bytes": args.expected_roster_bytes, "sha256": args.expected_roster_sha256},
                         draws=args.draws, seed=args.seed, confidence=args.confidence, output_path=args.output)
    except (ValueError, TypeError, OSError, KeyError, IndexError, RecursionError) as exc:
        # Do not echo protected response text or query identities to stderr.
        parser.exit(2, "raw-to-vector custody rejected: " + type(exc).__name__ + "\n")


if __name__ == "__main__":
    main()
