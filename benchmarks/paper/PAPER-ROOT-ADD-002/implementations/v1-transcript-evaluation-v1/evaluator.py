#!/usr/bin/env python3
"""Evaluate a frozen V1 presented-sentence panel; no model or recording reads.

This implements the pinned author's export endpoint, not the online typed-target
metric. The caller must supply the independent panel digest from a trusted freeze.
Neither a matching digest nor passing generated controls qualifies neuroscience.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import statistics
import sys


CONTRACT_SHA256 = "36eafec00f096a5ef22c4e271e61429901369989e72248543643f28913c9e0b6"
CONTRACT_BYTES = 95797
TASK_ID = "PAPER-ROOT-ADD-002"
METRIC_ROUTE = "pinned-v1-presented-sentence-export"
PANEL_SCHEMA = "typing-v1-panel-v1"
SUBMISSION_SCHEMA = "typing-v1-predictions-v1"
SPLITS = ("train", "validation", "calibration", "test")
REPRESENTATIONS = ("transcript", "per-keystroke-classes")
HEX = re.compile(r"[0-9a-f]{64}\Z")


class CandidateError(ValueError):
    """Malformed or incomplete candidate output; not an operator failure."""


class PanelError(ValueError):
    """Missing, inconsistent or unauthenticated operator assessment."""


class ResourceLimit(ValueError):
    """The declared engineering budget cannot cover this input."""


class Limits:
    """Caller-chosen source-evaluation bounds, not measured native model costs."""

    def __init__(self, *, max_json_bytes, max_edit_cells, max_codepoints):
        for name, value in locals().copy().items():
            if name != "self":
                if type(value) is not int or value <= 0:
                    raise ResourceLimit(f"{name} must be a positive integer")
                if name == "max_json_bytes" and value >= sys.maxsize:
                    raise ResourceLimit("JSON byte budget exceeds supported read size")
                setattr(self, name, value)


class EditBudget:
    def __init__(self, maximum):
        if type(maximum) is not int or maximum <= 0:
            raise ResourceLimit("edit-cell budget must be a positive integer")
        self.maximum, self.used = maximum, 0

    def reserve(self, count):
        if count > self.maximum - self.used:
            raise ResourceLimit("declared edit-cell budget exceeded")
        self.used += count


def _need(condition, message, error=PanelError):
    if not condition:
        raise error(message)


def _keys(value, names, label, error=PanelError):
    _need(type(value) is dict and set(value) == set(names),
          f"invalid {label} fields", error)


def _text(value, label, *, nonempty=False, error=PanelError):
    _need(type(value) is str, f"{label} must be text", error)
    _need(not nonempty or bool(value), f"{label} must be nonempty", error)
    _need(not any(0xD800 <= ord(c) <= 0xDFFF for c in value),
          f"{label} contains an unpaired Unicode surrogate", error)
    return value


def _identifier(value, label, error=PanelError):
    _text(value, label, nonempty=True, error=error)
    _need(len(value) <= 512 and not any(ord(c) < 32 or ord(c) == 127 for c in value),
          f"invalid {label}", error)
    return value


def _sha(value, label, error=PanelError):
    _need(type(value) is str and HEX.fullmatch(value) is not None,
          f"invalid {label}", error)
    return value


def _unique_ids(values, label, error=PanelError):
    _need(type(values) is list, f"{label} must be an array", error)
    for value in values:
        _identifier(value, label, error)
    _need(len(set(values)) == len(values), f"duplicate {label}", error)
    return values


def decode_json(raw, *, label, limits, error):
    _need(type(raw) is bytes, f"{label} input must be bytes", error)
    if len(raw) > limits.max_json_bytes:
        raise ResourceLimit(f"{label} exceeds declared JSON byte budget")

    def pairs(rows):
        out = {}
        for key, value in rows:
            if key in out:
                raise error(f"duplicate JSON key in {label}")
            out[key] = value
        return out

    def constant(_):
        raise error(f"nonfinite JSON constant in {label}")

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, (CandidateError, PanelError)):
            raise
        raise error(f"invalid JSON {label}") from None


def source_contract():
    raw = read_bounded(Path(__file__).with_name("source_contract.json"), CONTRACT_BYTES)
    _need(hashlib.sha256(raw).hexdigest() == CONTRACT_SHA256,
          "bundled source contract identity mismatch")
    return json.loads(raw)


def edit_distance(left, right, budget):
    """Unit-cost Levenshtein; rolling row, exact integer operations."""
    budget.reserve((len(left) + 1) * (len(right) + 1))
    if len(right) > len(left):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for i, x in enumerate(left, 1):
        current = [i]
        for j, y in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def sentence_metrics(reference, prediction, budget):
    """Literal codepoint CER and Python-whitespace token WER; null if undefined."""
    _text(reference, "reference")
    _text(prediction, "prediction", error=CandidateError)
    words, predicted_words = reference.split(), prediction.split()
    chars = edit_distance(reference, prediction, budget)
    word_edits = edit_distance(words, predicted_words, budget)
    return {"character_edits": chars, "reference_characters": len(reference),
            "word_edits": word_edits, "reference_words": len(words),
            "cer": chars / len(reference) if reference else None,
            "wer": word_edits / len(words) if words else None}


def validate_submission(value, contract, limits):
    """Perform public candidate validation before the private panel is opened."""
    _keys(value, ("schema", "task_id", "metric_route", "representation", "predictions"),
          "submission", CandidateError)
    _need(value["schema"] == SUBMISSION_SCHEMA and value["task_id"] == TASK_ID
          and value["metric_route"] == METRIC_ROUTE,
          "wrong candidate schema, task or endpoint", CandidateError)
    kind = value["representation"]
    _need(kind in REPRESENTATIONS, "unsupported candidate representation", CandidateError)
    rows = value["predictions"]
    _need(type(rows) is list, "predictions must be an array", CandidateError)
    vocabulary = contract["vocabulary"]
    ids, count, result = set(), 0, {}
    for row in rows:
        payload = "text" if kind == "transcript" else "class_ids"
        _keys(row, ("case_id", "keystroke_ids", payload), "prediction", CandidateError)
        key = _identifier(row["case_id"], "candidate case ID", CandidateError)
        _need(key not in ids, "duplicate candidate case ID", CandidateError)
        ids.add(key)
        strokes = _unique_ids(row["keystroke_ids"], "candidate keystroke IDs", CandidateError)
        if kind == "transcript":
            text = _text(row["text"], "candidate transcript", error=CandidateError)
            _need(all(c in vocabulary for c in text),
                  "candidate transcript is outside the frozen 29-class vocabulary", CandidateError)
        else:
            classes = row["class_ids"]
            _need(type(classes) is list and all(type(i) is int and 0 <= i < 29 for i in classes),
                  "invalid candidate class IDs", CandidateError)
            _need(len(classes) == len(strokes),
                  "class count does not match ordered input keystroke count", CandidateError)
            text = "".join(vocabulary[i] for i in classes)
        count += len(text)
        if count > limits.max_codepoints:
            raise ResourceLimit("candidate transcripts exceed declared codepoint budget")
        result[key] = {"text": text, "keystroke_ids": strokes}
    return kind, result, count


def validate_panel(value, contract, limits):
    _keys(value, ("schema", "task_id", "metric_route", "source", "modality", "condition",
                  "provenance", "aliases", "recordings", "cases"), "panel")
    _need(value["schema"] == PANEL_SCHEMA and value["task_id"] == TASK_ID
          and value["metric_route"] == METRIC_ROUTE, "wrong panel endpoint")
    _keys(value["source"], ("code_commit", "data_revision"), "source identity")
    _need(value["source"] == {key: contract[key] for key in ("code_commit", "data_revision")},
          "panel source revision mismatch")
    modality = value["modality"]
    _need(modality in ("MEG", "EEG"), "panel must declare one modality")
    condition = value["condition"]
    _keys(condition, ("id", "access_condition", "split_kind", "disjoint_units",
                      "calibration_sentence_limit_per_person", "representation"), "condition")
    _identifier(condition["id"], "condition ID")
    _need(condition["access_condition"] in ("paper_and_data", "paper_data_official_code"),
          "unknown access condition")
    _need(condition["representation"] in REPRESENTATIONS, "unsupported panel representation")
    units = _unique_ids(condition["disjoint_units"], "split units")
    _need(bool(units) and set(units) <= {"person", "person_session", "sentence_cluster"}
          and "sentence_cluster" in units, "sentence-cluster disjointness is required")
    _need(condition["split_kind"] in ("pinned-source-sentence-clusters", "prospective-declared"),
          "unrecognized split kind")
    if condition["split_kind"] == "pinned-source-sentence-clusters":
        _need(units == ["sentence_cluster"],
              "source sentence split must not be relabeled as a person/session holdout")
        _need(condition["representation"] == "per-keystroke-classes",
              "source condition requires original per-keystroke class outputs")
    calibration_limit = condition["calibration_sentence_limit_per_person"]
    _need(type(calibration_limit) is int and calibration_limit >= 0,
          "invalid declared calibration budget")
    if condition["split_kind"] == "pinned-source-sentence-clusters":
        _need(calibration_limit == 0, "source condition does not authorize added calibration")
    provenance = value["provenance"]
    _keys(provenance, ("panel_id", "eligibility_manifest_sha256", "preprocessing_manifest_sha256",
                       "grouping_manifest_sha256", "training_or_checkpoint_manifest_sha256"), "provenance")
    _identifier(provenance["panel_id"], "panel ID")
    for key in set(provenance) - {"panel_id"}:
        _sha(provenance[key], key)
    alias_rows = value["aliases"]
    _need(type(alias_rows) is list and bool(alias_rows), "aliases must be a nonempty array")
    aliases = {}
    for row in alias_rows:
        _keys(row, ("participant_id", "person_id"), "alias")
        participant = _identifier(row["participant_id"], "participant ID")
        person = _identifier(row["person_id"], "person ID")
        _need(participant not in aliases, "duplicate participant alias")
        if modality == "MEG":
            _need(participant not in contract["excluded_meg_participants"],
                  "panel includes source-excluded MEG participant")
            _need(person == contract["meg_aliases"].get(participant, participant),
                  "MEG identity contradicts pinned known aliases")
        else:
            _need(participant not in contract["excluded_eeg_participants"],
                  "panel includes source-excluded EEG participant")
        aliases[participant] = person
    source_assets = {r["path"]: r for r in contract["source_records"]}
    recording_rows = value["recordings"]
    _need(type(recording_rows) is list and bool(recording_rows),
          "recordings must be a nonempty array")
    recordings = {}
    for row in recording_rows:
        _keys(row, ("path", "bytes", "sha256"), "recording identity")
        path = _text(row["path"], "source recording", nonempty=True)
        _need(path in source_assets and path not in recordings,
              "unregistered or duplicate recording identity")
        source = source_assets[path]
        _need(path.startswith(modality + "/") and type(row["bytes"]) is int
              and row["bytes"] == source["bytes"], "recording metadata mismatch")
        _sha(row["sha256"], "recording SHA256")
        recordings[path] = row
    cases = value["cases"]
    _need(type(cases) is list and bool(cases), "cases must be a nonempty array")
    seen, used_aliases, used_recordings, stroke_keys = set(), set(), set(), set()
    source_trial_keys = set()
    uid_metadata, exact_text_clusters, split_groups = {}, {}, {}
    calibration_counts = Counter()
    count = 0
    for row in cases:
        _keys(row, ("case_id", "participant_id", "session_id", "sentence_uid",
                    "sentence_cluster_id", "trial_id", "split", "source_path",
                    "reference_text", "keystroke_ids"), "panel case")
        key = _identifier(row["case_id"], "panel case ID")
        _need(key not in seen, "duplicate panel case ID")
        seen.add(key)
        participant = _identifier(row["participant_id"], "case participant")
        _need(participant in aliases, "case participant has no alias entry")
        used_aliases.add(participant)
        person = aliases[participant]
        session = _identifier(row["session_id"], "session ID")
        uid = _identifier(row["sentence_uid"], "source sentence UID")
        _need(uid not in contract["excluded_sentence_uids"],
              "source-excluded corrupted sentence UID")
        cluster = _identifier(row["sentence_cluster_id"], "sentence cluster ID")
        trial = row["trial_id"]
        _need(type(trial) is int and trial >= 2, "practice or invalid trial in admitted panel")
        split = row["split"]
        _need(split in SPLITS, "unknown case split")
        path = row["source_path"]
        _need(type(path) is str and path in recordings, "case recording was not admitted")
        identity = contract["recording_identities"][path]
        _need(identity["primary_case_eligible"], "case anchor is not a source-eligible primary recording")
        _need(participant == identity["participant_id"] and session == identity["session_id"],
              "case participant/session contradicts pinned recording metadata")
        suffix = (f"_{identity['study']}_subject-{participant}"
                  f"_session-{session}_task-{identity['task']}")
        equivalent_uids = (str(trial) + suffix, str(trial) + ".0" + suffix)
        _need(uid in equivalent_uids,
              "sentence UID contradicts recording/trial identity")
        _need(not set(equivalent_uids).intersection(contract["excluded_sentence_uids"]),
              "source-excluded corrupted sentence UID")
        trial_identity = (identity["study"], participant, session, identity["task"], trial)
        _need(trial_identity not in source_trial_keys,
              "duplicate source trial under different sentence UID spellings")
        source_trial_keys.add(trial_identity)
        used_recordings.add(path)
        text = _text(row["reference_text"], "presented reference text")
        count += len(text)
        if count > limits.max_codepoints:
            raise ResourceLimit("reference text exceeds declared codepoint budget")
        strokes = _unique_ids(row["keystroke_ids"], "reference keystroke IDs")
        _need(bool(strokes) and strokes == [f"{uid}_button_{i}" for i in range(1, len(strokes) + 1)],
              "reference keystrokes must preserve the source ordered sentence sequence")
        for stroke in strokes:
            identity = (path, stroke)
            _need(identity not in stroke_keys, "duplicate physical keystroke identity in panel")
            stroke_keys.add(identity)
        _need(uid not in uid_metadata, "duplicate source sentence UID in panel")
        uid_metadata[uid] = (participant, session, text, cluster)
        _need(text not in exact_text_clusters or exact_text_clusters[text] == cluster,
              "identical presented text assigned to different sentence clusters")
        exact_text_clusters[text] = cluster
        # Session ordinals restart under each recording-participant alias. S1/1
        # and S18/1 are distinct source acquisitions of the same person.
        values = {"person": person, "person_session": (person, participant, session),
                  "sentence_cluster": cluster}
        # Calibration is model-accessible data, not held-out assessment. It may
        # share training groups, but never validation or test groups.
        partition = "train" if split == "calibration" else split
        for unit in units:
            group = (unit, values[unit])
            _need(group not in split_groups or split_groups[group] == partition,
                  f"declared {unit} split overlaps")
            split_groups[group] = partition
        if split == "calibration":
            calibration_counts[person] += 1
    _need(used_aliases == set(aliases), "alias roster includes unrepresented participants")
    _need(used_recordings == set(recordings), "recording roster includes unrepresented recordings")
    _need(all(n <= calibration_limit for n in calibration_counts.values()),
          "declared calibration sentence budget exceeded")
    test = [row for row in cases if row["split"] == "test"]
    _need(bool(test), "panel has no declared assessment cases")
    return aliases, test


def summarize(rows):
    """Complete-panel headline and explicitly conditional source-parity summary."""
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["person_id"]].append(row)
    people = []
    for person in sorted(grouped):
        subset = grouped[person]
        entry = {"person_id": person, "cases": len(subset)}
        for metric in ("cer", "wer"):
            values = [r[metric] for r in subset if r[metric] is not None]
            entry[metric] = math.fsum(values) / len(values) if values else None
            entry[metric + "_defined_cases"] = len(values)
            entry[metric + "_undefined_cases"] = len(subset) - len(values)
        people.append(entry)
    result = {"people": people, "person_count": len(people)}
    for metric in ("cer", "wer"):
        values = [p[metric] for p in people if p[metric] is not None]
        result[metric] = math.fsum(values) / len(values) if values else None
        result[metric + "_defined_people"] = len(values)
        result[metric + "_undefined_people"] = len(people) - len(values)
    values = [p["cer"] for p in people if p["cer"] is not None]
    # Author pandas.std skips NaNs, but its sqrt(n_subj) includes every grouped
    # participant. Keep that behavior explicit rather than hiding zero support.
    result["source_cer_sem"] = (statistics.stdev(values) / math.sqrt(len(people))
                                if len(values) >= 2 else None)
    support = {metric: all(row[metric] is not None for row in rows) for metric in ("cer", "wer")}
    return {"cer": result["cer"] if support["cer"] else None,
            "wer": result["wer"] if support["wer"] else None,
            "cer_sem": result["source_cer_sem"] if support["cer"] else None,
            "person_count": len(people),
            "complete_metric_support": all(support.values()),
            "complete_support_by_metric": support,
            "source_conditional_defined_support": result}


def evaluate_validated(panel_raw, expected_panel_sha256, candidate, contract, limits):
    _need(type(panel_raw) is bytes, "panel input must be bytes")
    _sha(expected_panel_sha256, "independently frozen panel digest")
    _need(hashlib.sha256(panel_raw).hexdigest() == expected_panel_sha256,
          "frozen panel digest mismatch")
    panel = decode_json(panel_raw, label="panel", limits=limits, error=PanelError)
    aliases, test = validate_panel(panel, contract, limits)
    representation, predictions, _ = candidate
    _need(representation == panel["condition"]["representation"],
          "candidate representation differs from frozen condition", CandidateError)
    expected = {row["case_id"] for row in test}
    _need(set(predictions) == expected,
          "candidate case coverage differs from complete declared assessment", CandidateError)
    budget = EditBudget(limits.max_edit_cells)
    scored = []
    for row in test:
        pred = predictions[row["case_id"]]
        _need(pred["keystroke_ids"] == row["keystroke_ids"],
              "candidate ordered keystroke coverage differs from frozen assessment", CandidateError)
        item = {"case_id": row["case_id"], "person_id": aliases[row["participant_id"]],
                **sentence_metrics(row["reference_text"], pred["text"], budget)}
        scored.append(item)
    return {"schema": "typing-v1-result-v1", "task_id": TASK_ID,
            "metric_route": METRIC_ROUTE, "panel_sha256": expected_panel_sha256,
            "panel_id": panel["provenance"]["panel_id"], "modality": panel["modality"],
            "condition": panel["condition"], "source_contract_sha256": CONTRACT_SHA256,
            "declared_population": {"all_split_cases": len(panel["cases"]),
                                    "assessment_cases": len(test), "assessment_people": len({r["person_id"] for r in scored}),
                                    "recordings_with_cases": len(panel["recordings"]),
                                    "complete_submitted_case_and_keystroke_coverage": True},
            "cases": scored, "summary": summarize(scored),
            "engineering_work": {"reserved_edit_cells": budget.used,
                                  "max_edit_cells": budget.maximum},
            "verification": {"authentic_population_verified": False,
                             "source_payloads_verified": False,
                             "biological_session_equivalence_verified": False,
                             "sentence_cluster_derivation_verified": False,
                             "lawful_input_use_verified": False,
                             "neural_only_derivation_verified": False,
                             "original_reference_competence_verified": False,
                             "protected_execution_qualified": False,
                             "paper_reproduction_established": False,
                             "scientifically_qualified": False}}


def evaluate_bytes(panel_raw, expected_panel_sha256, predictions_raw, limits):
    contract = source_contract()
    raw = decode_json(predictions_raw, label="candidate", limits=limits, error=CandidateError)
    candidate = validate_submission(raw, contract, limits)
    return evaluate_validated(panel_raw, expected_panel_sha256, candidate, contract, limits)


def read_bounded(path, limit):
    if type(limit) is not int or not 0 < limit < sys.maxsize:
        raise ResourceLimit("invalid or unsupported JSON read budget")
    # A FIFO or device must not turn a bounded JSON read into a blocking stream.
    # Parent-directory ownership is still an operator responsibility.
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise PanelError("input must be a regular file")
        with os.fdopen(fd, "rb") as stream:
            fd = None
            chunks, remaining = [], limit + 1
            while remaining:
                chunk = stream.read(min(65536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
    finally:
        if fd is not None:
            os.close(fd)
    if len(raw) > limit:
        raise ResourceLimit("input exceeds declared JSON byte budget")
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", required=True)
    parser.add_argument("--panel-sha256", required=True,
                        help="Digest obtained independently from the trusted assessment freeze")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--output", required=True, help="New JSON result file; never overwrite")
    parser.add_argument("--max-json-bytes", type=int, required=True)
    parser.add_argument("--max-edit-cells", type=int, required=True)
    parser.add_argument("--max-codepoints", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        limits = Limits(max_json_bytes=args.max_json_bytes, max_edit_cells=args.max_edit_cells,
                        max_codepoints=args.max_codepoints)
        contract = source_contract()
        candidate_raw = read_bounded(args.predictions, limits.max_json_bytes)
        candidate = validate_submission(
            decode_json(candidate_raw, label="candidate", limits=limits, error=CandidateError),
            contract, limits)
        # Public malformed candidates stop above, before the panel path is opened.
        panel_raw = read_bounded(args.panel, limits.max_json_bytes)
        result = evaluate_validated(panel_raw, args.panel_sha256, candidate, contract, limits)
        body = (json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")
        with open(args.output, "xb") as stream:
            stream.write(body)
        print(json.dumps({"status": "scored_declared_panel", "scientifically_qualified": False}))
        return 0
    except CandidateError as exc:
        print(json.dumps({"status": "invalid_candidate", "reason": str(exc)}))
        return 2
    except (PanelError, ResourceLimit, OSError) as exc:
        # Never interpolate private file paths, target text or OS error strings.
        reason = str(exc) if isinstance(exc, (PanelError, ResourceLimit)) else "operator file access failed"
        print(json.dumps({"status": "not_run", "reason": reason}))
        return 3


if __name__ == "__main__":
    sys.exit(main())
