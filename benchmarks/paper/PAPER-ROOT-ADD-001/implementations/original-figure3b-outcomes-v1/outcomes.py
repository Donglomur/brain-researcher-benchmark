"""Two continuous Figure 3b views of one authenticated recovered prediction set.

The caller owns RECOVERY byte authentication and its condition/store/protocol
binding. This module revalidates canonical receipt/packet identities and invokes
the pinned original compare; it never opens original reference/data bodies.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import stat
import types

ENDPOINT_BYTES = 8811
ENDPOINT_SHA256 = "bbf81e3f3f8a82edfbeb8005de6b52d335e21d674e3798238a5f8a14555c3afa"
REFERENCE_SOURCE_SHA256 = "d822f284c2d781f920841705a63fec38d3267ee5c62e5dd5635272cf087e49c9"
SOURCE_SUPPORT_SHA256 = "3d2d46bbc6534b282f97d29c51b1961c8d284cf7a9894839fb851550b7549e37"
CONDITIONS = ("paper_data", "paper_data_author_code")
ORIGINAL_SCOPE = "original_figure3b_improvement"
MAX_RECOVERY_BYTES = 262144
MAX_OUTCOME_BYTES = 262144
MAX_NODES = 10000
MAX_STRING_BYTES = 131072
_ENDPOINTS = {}
_SOURCE_READ_BYTES = 0


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def digest(value):
    need(type(value) is str and len(value) == 64
         and all(c in "0123456789abcdef" for c in value), "Exact lowercase SHA256")
    return value


def _bounded_snapshot(value):
    """Admit a finite primitive tree before JSON allocation; own a detached copy."""
    nodes = strings = 0
    active = set()

    def walk(item, depth):
        nonlocal nodes, strings
        nodes += 1
        need(nodes <= MAX_NODES and depth <= 16, "Bounded recovery tree")
        kind = type(item)
        if item is None or kind is bool:
            return
        if kind is int:
            need(abs(item) <= 2**63-1, "Bounded recovery integer")
            return
        if kind is float:
            need(math.isfinite(item), "Finite recovery number or explicit null")
            return
        if kind is str:
            need(len(item) <= 4096, "Bounded recovery string before encoding")
            try:
                count = len(item.encode("utf-8"))
            except UnicodeError as error:
                raise ValueError("Valid recovery UTF8 string") from error
            strings += count
            need(strings <= MAX_STRING_BYTES, "Cumulative recovery string bound")
            return
        need(kind in (dict, list), "Primitive JSON recovery containers only")
        need(id(item) not in active and len(item) <= 128, "Bounded acyclic recovery container")
        active.add(id(item))
        try:
            if kind is dict:
                for key, child in item.items():
                    need(type(key) is str and len(key) <= 128, "Bounded primitive recovery key")
                    walk(key, depth+1)
                    walk(child, depth+1)
            else:
                for child in item:
                    walk(child, depth+1)
        finally:
            active.remove(id(item))

    walk(value, 0)
    raw = encoded(value)
    need(len(raw) <= MAX_RECOVERY_BYTES, "Complete recovery byte bound")
    return json.loads(raw), raw


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _load_endpoint(source_root=None):
    """Load only exact reviewed compare bytes, once per explicit source root."""
    global _SOURCE_READ_BYTES
    root = Path(source_root) if source_root is not None else Path(__file__).absolute().parent.parent
    root = root.absolute()
    need(".." not in root.parts, "Canonical implementations source root")
    path = root / "original-figure3b-improvement-v1" / "improvement.py"
    key = str(path)
    if key in _ENDPOINTS:
        return _ENDPOINTS[key]
    need(not any(p.is_symlink() for p in (path, *path.parents)), "No endpoint source symlink")
    before_path = path.lstat()
    need(stat.S_ISREG(before_path.st_mode) and before_path.st_nlink == 1
         and before_path.st_size == ENDPOINT_BYTES, "Exact ordinary endpoint extent")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        need(_stamp(before) == _stamp(before_path), "Stable endpoint before read")
        raw = stream.read(ENDPOINT_BYTES+1)
        _SOURCE_READ_BYTES += len(raw)
        need(len(raw) == ENDPOINT_BYTES and hashlib.sha256(raw).hexdigest() == ENDPOINT_SHA256
             and _stamp(before) == _stamp(os.fstat(stream.fileno())) == _stamp(path.lstat()),
             "Pinned stable endpoint source")
    module = types.ModuleType("_language_dual_outcome_endpoint_" + ENDPOINT_SHA256[:12])
    module.__file__, module.__package__ = str(path), ""
    exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
    need(module.PROVIDED_REFERENCE_SHA256 == REFERENCE_SOURCE_SHA256,
         "Provided-reference source identity in retained comparison")
    _ENDPOINTS[key] = module
    return module


def source_read_metrics():
    return {"endpoint_source_bytes": _SOURCE_READ_BYTES,
            "cached_endpoint_sources": len(_ENDPOINTS),
            "runtime_standard_library_module_reads_metered": False}


def _complete_recovery(value, collection_sha256):
    need(type(value) is dict and set(value) == {
        "schema", "scope", "collection_sha256", "authorities", "packed", "result",
        "original_result_arrays", "protected_execution_qualified", "scientific_qualification"},
        "Exact selected recovery envelope")
    need(value["schema"] == "language-selected-figure3b-recovery/v1"
         and value["scope"] == ORIGINAL_SCOPE
         and value["collection_sha256"] == collection_sha256
         and value["original_result_arrays"] is None
         and value["protected_execution_qualified"] is False
         and value["scientific_qualification"] is False,
         "Unchanged complete selected recovery scope and lineage")
    authority = value["authorities"]
    need(type(authority) is dict and set(authority) == {
        "jobs", "requests", "read_bytes_charged", "exact_authority_recovered", "scientific_qualification"},
        "Exact maintained authority recovery")
    packed = value["packed"]
    need(type(packed) is dict and set(packed) == {
        "jobs", "requests", "read_bytes", "all_numeric_predictions_recovered",
        "protected_execution_qualified", "provider_journal_independently_verified",
        "scientific_qualification", "compact_request_identity_join_verified", "scope"},
        "Exact maintained packed recovery")
    for row, counter in ((authority, "read_bytes_charged"), (packed, "read_bytes")):
        need(type(row["jobs"]) is int and row["jobs"] == 42
             and type(row["requests"]) is int and row["requests"] == 5685
             and type(row[counter]) is int and 0 <= row[counter] <= 2**63-1
             and row["scientific_qualification"] is False,
             "All42 source jobs and5685 software callbacks recovered")
    need(authority["exact_authority_recovered"] is True
         and packed["all_numeric_predictions_recovered"] is True
         and packed["compact_request_identity_join_verified"] is True
         and packed["scope"] == ORIGINAL_SCOPE
         and packed["protected_execution_qualified"] is False
         and packed["provider_journal_independently_verified"] is False,
         "Complete attributed recovery without protection promotion")
    result = value["result"]
    need(type(result) is dict and set(result) == {
        "candidate_scores", "paired_difference", "reference_packet_sha256",
        "reference_status", "full_224_array_reproduction_executed"},
        "Exact selected recovered result")
    need(result["reference_status"] ==
         "provided-author-values only; same-stack baseline computation not qualified"
         and result["full_224_array_reproduction_executed"] is False,
         "Provided reference is not fresh baseline reexecution")
    return result


def compose_recovered(recovery, *, condition, collection_sha256, recovery_sha256, source_root=None):
    """Compose two views; require the caller's actual authenticated recovery pin.

    Condition/store attribution is the entrypoint's protocol responsibility:
    maintained RECOVERY contains no condition/store fields. A matching digest
    alone does not independently prove physical execution or reference custody.
    """
    need(type(condition) is str and condition in CONDITIONS, "Exact paper access condition")
    digest(collection_sha256)
    digest(recovery_sha256)
    value, raw = _bounded_snapshot(recovery)
    need(hashlib.sha256(raw).hexdigest() == recovery_sha256, "Exact canonical authenticated recovery pin")
    result = _complete_recovery(value, collection_sha256)
    endpoint = _load_endpoint(source_root)
    candidate = result["candidate_scores"]
    candidate_values = endpoint._packet(candidate, "candidate")
    need(candidate["source_support_sha256"] == SOURCE_SUPPORT_SHA256
         and candidate["prediction_run_sha256"] == collection_sha256
         and candidate["execution_qualified"] is False,
         "Original567 support, exact collection and unpromoted candidate lineage")
    saved = result["paired_difference"]
    need(type(saved) is dict and type(saved.get("sessions")) is list
         and len(saved["sessions"]) == 14, "All14 paired sessions, no caller scalar")
    author_values = []
    for session, expected in zip(saved["sessions"], endpoint.SESSIONS):
        need(type(session) is dict and session.get("session") == expected
             and type(session.get("author_lag_correlations")) is list
             and len(session["author_lag_correlations"]) == 3,
             "Complete canonical source sessions and three author lag values")
        author_values.extend(session["author_lag_correlations"])
    reference = {
        "schema": "language-original-figure3b-scores/v1", "role": "provided_author_reference",
        "selection_sha256": candidate["selection_sha256"],
        "source_support_sha256": SOURCE_SUPPORT_SHA256,
        "prediction_run_sha256": REFERENCE_SOURCE_SHA256,
        "scores": [{"context": context, "pearson_r": number}
                   for context, number in zip(endpoint.contexts(), author_values)],
        "execution_qualified": False}
    reference_values = endpoint._packet(reference, "provided_author_reference")
    reference_pin = hashlib.sha256(endpoint.encoded(reference)).hexdigest()
    digest(result["reference_packet_sha256"])
    need(reference_pin == result["reference_packet_sha256"]
         and saved.get("reference_packet_sha256") == reference_pin,
         "Exact reconstructed provided-reference packet identity; no numeric-type guess")
    comparison = endpoint.compare(candidate, reference)
    need(endpoint.encoded(comparison) == endpoint.encoded(saved),
         "All saved comparison values/identities must match the pinned original compare")
    cells = []
    for context, candidate_r, reference_r in zip(endpoint.contexts(), candidate_values, reference_values):
        difference = candidate_r-reference_r if candidate_r is not None and reference_r is not None else None
        cells.append({"context": context, "candidate_pearson_r": candidate_r,
                      "provided_author_pearson_r": reference_r, "signed_difference": difference,
                      "absolute_difference": None if difference is None else abs(difference)})
    sessions = [{"session": row["session"], "person": row["person"],
                 "candidate_lag_mean": row["candidate_mean"], "provided_author_lag_mean": row["author_mean"],
                 "signed_difference": row["paired_delta"]} for row in comparison["sessions"]]
    report = {
        "schema": "language-original-figure3b-dual-outcomes/v1",
        "mode": "original_figure3b_reproduction_and_improvement", "condition": condition,
        "selection": comparison["selection"],
        "lineage": {"collection_sha256": collection_sha256, "recovery_sha256": recovery_sha256,
                    "candidate_packet_sha256": comparison["candidate_packet_sha256"],
                    "reference_packet_sha256": reference_pin,
                    "provided_reference_source_sha256": REFERENCE_SOURCE_SHA256,
                    "source_support_sha256": SOURCE_SUPPORT_SHA256,
                    "selection_sha256": candidate["selection_sha256"],
                    "reference_packet_reexecution": False,
                    "upstream_physical_execution_independently_verified_here": False,
                    "condition_and_store_binding_owned_by_authenticated_entrypoint": True},
        "reproduction": {
            "schema": "language-original-figure3b-continuous-reproduction/v1",
            "cells": cells, "source_lag_cells": 42,
            "defined_cell_pairs": sum(row["signed_difference"] is not None for row in cells),
            "sessions": sessions, "defined_session_pairs": comparison["defined_session_pairs"],
            "candidate_equal_session_mean": comparison["candidate_equal_session_mean"],
            "provided_author_equal_session_mean": comparison["author_equal_session_mean"],
            "equal_session_signed_difference": comparison["equal_session_paired_mean_delta"],
            "aggregation": comparison["selection"]["aggregation"],
            "binary_reproduction": None, "tolerance": None,
            "reference_kind": "provided_author_results_not_fresh_author_reexecution"},
        "improvement": comparison,
        "shared_frozen_candidate_predictions": True, "additional_model_calls": 0,
        "new_resampling": False, "full_224_array_reproduction_executed": False,
        "representation_scope": {
            "released_FR_unit_columns": 567, "same_support_required": True,
            "self_FR_579_biological_crosswalk_resolved": False,
            "self_FR_579_crosswalk_is_gate_for_this_same_support_comparison": False},
        "execution_qualification_independently_verified": False, "scientific_qualification": False,
        "limits": [
            "The same42 cells over14sessions/eight people feed both continuous views.",
            "Equal-session improvement is the unchanged original compare; no new primary error scalar, tolerance, binary success or superiority margin is invented.",
            "Undefined cells and sessions remain present and propagate; no favorable dropping.",
            "Provided author values are attributed through authenticated upstream recovery; this helper does not reread or independently authenticate the original reference body.",
            "Exact reference-packet reconstruction is required; lossy numeric-type ambiguity refuses rather than guessing a matching historical packet.",
            "The maintained selection/store contracts and full224-array historical task remain unchanged.",
            "No full-paper reproduction, current SOTA, protected execution, original dataset readiness or historical environment equivalence follows from this envelope."]}
    need(len(encoded(report)) <= MAX_OUTCOME_BYTES, "Complete dual-outcome report byte bound")
    return report
