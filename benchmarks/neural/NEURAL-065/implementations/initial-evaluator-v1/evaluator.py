"""NEURAL-065: independently implemented V1 typed-character evaluation.

Only standard-library code; no neural data, checkpoints or author code bundled.
See ../../docs/initial-evaluator-v1.md for prospective policy and native holds.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics

TASK_ID = "NEURAL-065"
SOURCE_COMMIT = "5f9889621d0df391c5aab37c996683d308e6e926"
DATA_COMMIT = "88f9096c6ce3a3fb17cc7b8e3131ff7f96da5684"
# Index order is the pinned V1 CHAR_INDEX, including special and number tokens.
CHARACTERS = "sotencia dlrb@zvfmuhpgqwxyjk9"
# Keep explicit index order visible; the string above has 29 unique characters.
assert len(CHARACTERS) == len(set(CHARACTERS)) == 29
MERGES = {"S18": "S1", "S14": "S4", "S10": "S5", "S21": "S5"}
EXCLUDED = {"S13", "S23", "S11122024", "S12122024", "S26112024", "S27112024", "S28112024"}
PHASES = {"train", "calibration", "query"}


class ContractError(ValueError):
    """An artifact is invalid; no partial or silently filtered score is emitted."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def keys(obj, expected, context):
    require(isinstance(obj, dict), f"{context}: expected object")
    require(set(obj) == set(expected.split()), f"{context}: unexpected/missing fields")


def label(value, context):
    require(isinstance(value, str) and value and value.strip() == value,
            f"{context}: expected nonempty identifier")
    return value


def integer(value, context, minimum=0):
    require(type(value) is int and value >= minimum, f"{context}: invalid integer")
    return value


def finite(value, context):
    require(type(value) in (int, float), f"{context}: expected numeric value")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ContractError(f"{context}: number overflow") from exc
    require(math.isfinite(number), f"{context}: nonfinite number")
    return number


def pin(value, context):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
            f"{context}: expected SHA256")
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def decode_classes(classes):
    require(isinstance(classes, list), "classes must be a list")
    require(all(type(c) is int and 0 <= c < 29 for c in classes), "class outside V1 0..28")
    return "".join(CHARACTERS[c] for c in classes)


def canonical_person(subject, modality):
    label(subject, "recording_subject")
    prefix = {"MEG": "Pinet2024Meg/", "EEG": "Pinet2024Eeg/"}.get(modality)
    require(prefix is not None and subject.startswith(prefix), "subject/modality mismatch")
    suffix = subject[len(prefix):]
    if modality == "MEG":
        require(re.fullmatch(r"S[1-9][0-9]*", suffix) is not None, "expected MEG loader subject S<number>")
        require(suffix not in EXCLUDED, "excluded V1 MEG participant/control")
        suffix = MERGES.get(suffix, suffix)
    else:
        require(re.fullmatch(r"[0-9]+", suffix) is not None and int(suffix) > 0, "expected EEG numeric subject")
        require(int(suffix) != 1, "excluded malformed EEG subject 001")
        suffix = str(int(suffix)).zfill(3)
    return prefix + suffix


def template_key(text):
    """Prospective conservative collision key; never used to clean scored output."""
    label(text, "template_text")
    import unicodedata
    text = "".join(c for c in unicodedata.normalize("NFKD", text.lower())
                   if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in text).split())


def edit_distance(reference, hypothesis):
    """Exact unit-cost Levenshtein distance in O(min(n,m)) space."""
    if len(reference) < len(hypothesis):
        reference, hypothesis = hypothesis, reference
    row = list(range(len(hypothesis) + 1))
    for i, a in enumerate(reference, 1):
        new = [i]
        for j, b in enumerate(hypothesis, 1):
            new.append(min(new[-1] + 1, row[j] + 1, row[j - 1] + (a != b)))
        row = new
    return row[-1]


def _events(rows, name):
    require(isinstance(rows, list) and rows, f"{name}: expected nonempty event inventory")
    result = {}
    times = []
    for r in rows:
        keys(r, "id time_s", name)
        eid = label(r["id"], name)
        require(eid not in result, f"{name}: duplicate event")
        result[eid] = finite(r["time_s"], name)
        times.append(result[eid])
    require(all(a < b for a, b in zip(times, times[1:])), f"{name}: unordered/repeated times")
    return result


def audit_alignment(row, modality):
    keys(row, "recording_subject session_id biological_session_id log_events neural_events pairs excluded_log_events "
              "excluded_neural_events log_to_neural_offset_s max_residual_s evidence_sha256", "alignment")
    canonical_person(row["recording_subject"], modality)
    label(row["session_id"], "session_id")
    label(row["biological_session_id"], "biological_session_id")
    pin(row["evidence_sha256"], "alignment evidence")
    logs = _events(row["log_events"], "log_events")
    neural = _events(row["neural_events"], "neural_events")
    offset = finite(row["log_to_neural_offset_s"], "clock offset")
    tolerance = finite(row["max_residual_s"], "residual tolerance")
    require(tolerance >= 0, "negative residual tolerance")
    require(isinstance(row["pairs"], list) and row["pairs"], "no aligned pairs")
    used_l, used_n, residuals, last = set(), set(), [], None
    for p in row["pairs"]:
        keys(p, "log_id neural_id", "pair")
        l, n = p["log_id"], p["neural_id"]
        require(isinstance(l, str) and isinstance(n, str), "pair IDs must be strings")
        require(l in logs and n in neural, "unknown pair endpoint")
        require(l not in used_l and n not in used_n, "non one-to-one alignment")
        require(last is None or (logs[l] > last[0] and neural[n] > last[1]), "nonmonotone alignment")
        last = (logs[l], neural[n])
        residual = abs(neural[n] - (logs[l] + offset))
        require(residual <= tolerance + 1e-12, "alignment residual exceeds frozen tolerance")
        used_l.add(l); used_n.add(n); residuals.append(residual)
    losses = {}
    for name, source, paired in (("excluded_log_events", logs, used_l),
                                 ("excluded_neural_events", neural, used_n)):
        require(isinstance(row[name], list), f"{name}: expected list")
        omitted = set()
        for e in row[name]:
            keys(e, "id reason", name)
            label(e["reason"], "exclusion reason")
            require(isinstance(e["id"], str) and e["id"] in source, "unknown excluded event")
            require(e["id"] not in omitted and e["id"] not in paired, "duplicate/paired exclusion")
            omitted.add(e["id"])
        require(paired | omitted == set(source), "unaccounted alignment loss")
        losses[name] = len(omitted)
    return {"matched_log_ids": used_l, "log_times": logs, "matched_pairs": len(used_l),
            "biological_session_id": row["biological_session_id"],
            "max_observed_residual_s": max(residuals), **losses}


def validate_packet(packet):
    keys(packet, "schema_version task_id source_commit data_commit modality target_definition protocol alignments sentences", "packet")
    require(type(packet["schema_version"]) is int and packet["schema_version"] == 1, "schema version")
    require(packet["task_id"] == TASK_ID, "task mismatch")
    require(packet["source_commit"] == SOURCE_COMMIT and packet["data_commit"] == DATA_COMMIT,
            "source must be pinned V1")
    require(packet["target_definition"] == "pinned_v1_typed_button_classes", "target definition must be explicit typed V1 buttons")
    modality = packet["modality"]
    require(isinstance(modality, str) and modality in {"MEG", "EEG"}, "one modality per packet; cross-modal person map unresolved")
    p = packet["protocol"]
    keys(p, "protocol_sha256 selection_sha256 calibration_sentences_per_person "
            "calibration_keystrokes_per_person bootstrap_seed bootstrap_replicates "
            "max_sentence_characters fixed_lm_id", "protocol")
    pin(p["protocol_sha256"], "protocol pin"); pin(p["selection_sha256"], "selection pin")
    ns = integer(p["calibration_sentences_per_person"], "calibration sentences")
    nc = integer(p["calibration_keystrokes_per_person"], "calibration characters")
    require((ns == 0) == (nc == 0), "inconsistent zero calibration")
    integer(p["bootstrap_seed"], "bootstrap seed")
    nr = integer(p["bootstrap_replicates"], "bootstrap replicates", 1)
    require(nr <= 100000, "bootstrap resource bound")
    limit = integer(p["max_sentence_characters"], "character bound", 1)
    require(limit <= 10000, "character resource bound")
    require(p["fixed_lm_id"] is None or isinstance(p["fixed_lm_id"], str) and p["fixed_lm_id"], "LM identifier")
    require(isinstance(packet["alignments"], list) and packet["alignments"], "missing alignments")
    alignment = {}
    for a in packet["alignments"]:
        audit = audit_alignment(a, modality)
        k = (a["recording_subject"], a["session_id"])
        require(k not in alignment, "duplicate alignment session")
        alignment[k] = audit
    require(isinstance(packet["sentences"], list) and packet["sentences"], "empty selected population")
    ids, sessions, templates, template_texts, persons = set(), {}, {}, {}, defaultdict(set)
    biological_sessions, text_template_id, used_events, outputs = {}, {}, set(), []
    neural_assets = set()
    for s in packet["sentences"]:
        keys(s, "query_id recording_subject session_id template_id template_text phase "
                "target_classes log_event_ids neural_asset_sha256", "sentence")
        qid = s["query_id"]
        require(isinstance(qid, str) and re.fullmatch(r"[0-9a-f]{32}", qid) is not None,
                "query IDs must be opaque 32-hex identifiers")
        require(qid not in ids, "duplicate sentence/query ID"); ids.add(qid)
        person = canonical_person(s["recording_subject"], modality)
        phase = s["phase"]
        require(isinstance(phase, str) and phase in PHASES, "unknown phase")
        label(s["session_id"], "session"); label(s["template_id"], "template")
        sk = (s["recording_subject"], s["session_id"])
        require(sk in alignment, "sentence has no alignment")
        require(sessions.setdefault(sk, phase) == phase, "session crosses partition")
        visit = (person, alignment[sk]["biological_session_id"])
        require(biological_sessions.setdefault(visit, phase) == phase, "biological session crosses partition")
        tid, text = s["template_id"], template_key(s["template_text"])
        require(text, "empty normalized template")
        require(text_template_id.setdefault(text, tid) == tid, "same template text has multiple IDs")
        require(templates.setdefault(tid, phase) == phase, "sentence template crosses partition")
        require(template_texts.setdefault(text, phase) == phase, "template text crosses partition")
        persons[person].add(phase)
        target = decode_classes(s["target_classes"])
        require(0 < len(target) <= limit, "empty/oversized selected reference sentence")
        events = s["log_event_ids"]
        require(isinstance(events, list) and len(events) == len(target), "keystroke/target length mismatch")
        times = []
        for eid in events:
            require(isinstance(eid, str) and eid in alignment[sk]["matched_log_ids"], "unmatched target keystroke")
            require((sk, eid) not in used_events, "target keystroke reused across sentences")
            used_events.add((sk, eid)); times.append(alignment[sk]["log_times"][eid])
        require(all(a < b for a, b in zip(times, times[1:])), "sentence keystrokes unordered")
        pin(s["neural_asset_sha256"], "neural asset")
        require(s["neural_asset_sha256"] not in neural_assets, "duplicate per-sentence neural asset")
        neural_assets.add(s["neural_asset_sha256"])
        outputs.append({**s, "person_id": person, "target_text": target})
    require(set(sessions) == set(alignment), "alignment session absent from selected inventory")
    train = {person for person, phases in persons.items() if "train" in phases}
    query = {person for person, phases in persons.items() if "query" in phases}
    cal = {person for person, phases in persons.items() if "calibration" in phases}
    require(train and query, "training and query people required")
    require(not train & (query | cal), "resolved person leaks from training to target")
    require(cal <= query, "calibration person has no query")
    for person in query:
        rows = [s for s in outputs if s["person_id"] == person and s["phase"] == "calibration"]
        require(len(rows) == ns and sum(len(s["target_text"]) for s in rows) == nc,
                "unequal target-person calibration budget")
    return outputs, alignment


def query_manifest(packet):
    """Explicit allowlist: never expose targets, templates, keycodes, source paths or logs."""
    rows, _ = validate_packet(packet)
    return {"schema_version": 1, "task_id": TASK_ID, "packet_sha256": digest(packet),
            "queries": [{"query_id": s["query_id"], "neural_asset_sha256": s["neural_asset_sha256"]}
                        for s in rows if s["phase"] == "query"]}


def _prediction_map(submission, packet, query_ids, arm):
    keys(submission, "schema_version task_id packet_sha256 arm lm_id predictions", "submission")
    require(type(submission["schema_version"]) is int and submission["schema_version"] == 1, "submission schema")
    require(submission["task_id"] == TASK_ID and submission["packet_sha256"] == digest(packet), "submission binding mismatch")
    require(submission["arm"] == arm, "wrong arm")
    lm = submission["lm_id"]
    if arm == "neural_only":
        require(lm is None, "neural-only arm cannot use LM")
    else:
        require(lm == packet["protocol"]["fixed_lm_id"], "unmatched LM access")
        if arm == "fixed_lm":
            require(lm is not None, "fixed LM must be specified prospectively")
    require(isinstance(submission["predictions"], list), "predictions must be a list")
    result = {}
    for r in submission["predictions"]:
        keys(r, "query_id text", "prediction")
        qid, text = r["query_id"], r["text"]
        require(isinstance(qid, str) and qid in query_ids and qid not in result, "extra/duplicate prediction ID")
        require(isinstance(text, str) and all(c in CHARACTERS for c in text), "prediction outside V1 alphabet")
        require(len(text) <= packet["protocol"]["max_sentence_characters"], "oversized prediction")
        result[qid] = text
    require(set(result) == query_ids, "missing predictions; partial scores forbidden")
    return result


def _score(rows, predictions):
    people, items = defaultdict(list), []
    for s in rows:
        text = predictions[s["query_id"]]
        errors = edit_distance(s["target_text"], text)
        cer = errors / len(s["target_text"])
        people[s["person_id"]].append(cer)
        # Do not echo reference/prediction text into evaluation reports.
        items.append({"query_id": s["query_id"], "edits": errors, "reference_characters": len(s["target_text"]), "cer": cer})
    by_person = {k: statistics.fmean(v) for k, v in sorted(people.items())}
    return {"person_macro_cer": statistics.fmean(by_person.values()), "person_sentence_mean_cer": by_person,
            "sentence_count": len(rows), "person_count": len(by_person), "sentences": items,
            "diagnostics": {"constant_output": len(set(predictions.values())) == 1,
                            "empty_outputs": sum(v == "" for v in predictions.values())}}


def _quantile(values, fraction):
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def paired_uncertainty(candidate, comparator, seed, replicates):
    require(set(candidate) == set(comparator), "paired people mismatch")
    delta = [candidate[k] - comparator[k] for k in sorted(candidate)]
    result = {"estimand": "neural_only_minus_language_only_person_macro_cer",
              "difference": statistics.fmean(delta), "independent_people": len(delta),
              "per_person_difference": {k: candidate[k] - comparator[k] for k in sorted(candidate)}}
    if len(delta) == 1:
        return {**result, "interval_95": None, "method": "single_person_descriptive_only"}
    rng = random.Random(seed)
    draws = [statistics.fmean(delta[rng.randrange(len(delta))] for _ in delta) for _ in range(replicates)]
    return {**result, "interval_95": [_quantile(draws, .025), _quantile(draws, .975)],
            "method": "paired_person_cluster_percentile_bootstrap", "replicates": replicates, "seed": seed}


def evaluate(packet, neural, language_only, fixed_lm=None):
    rows, alignments = validate_packet(packet)
    query = [r for r in rows if r["phase"] == "query"]
    ids = {r["query_id"] for r in query}
    arms = {"neural_only": neural, "language_only": language_only}
    if fixed_lm is not None:
        arms["fixed_lm"] = fixed_lm
    scores = {arm: _score(query, _prediction_map(data, packet, ids, arm)) for arm, data in arms.items()}
    p = packet["protocol"]
    return {"schema_version": 1, "task_id": TASK_ID, "packet_sha256": digest(packet),
            "modality": packet["modality"], "target_definition": packet["target_definition"], "primary_metric": "neural_only.person_macro_cer",
            "scores": scores,
            "paired_comparison": paired_uncertainty(scores["neural_only"]["person_sentence_mean_cer"],
                scores["language_only"]["person_sentence_mean_cer"], p["bootstrap_seed"], p["bootstrap_replicates"]),
            "alignment_accounting": [{"recording_subject": k[0], "session_id": k[1],
                **{name: value for name, value in a.items() if name not in {"matched_log_ids", "log_times"}}}
                for k, a in alignments.items()],
            "scientific_qualification": "unknown", "data_scope": "public_development_only",
            "native_reference_executed": False,
            "remaining_holds": ["Authentic selected payloads and complete inventory require independent verification.",
                "Raw DTW alignment, biological visit mapping, decoder/checkpoint compatibility and signal-derived reference remain unexecuted.",
                "Typed-button targets differ from paper intended-key targets; native batch-metric parity is unverified.",
                "Declared model/LM exposure, fitting, resources and target privacy require operator audit.",
                "Protected evaluation, independent native replication and scientific admission remain unresolved."]}


def read_json(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, "duplicate JSON object key")
            out[key] = value
        return out
    def bad_constant(value):
        raise ContractError(f"nonfinite JSON constant: {value}")
    return json.loads(Path(path).read_text(), object_pairs_hook=unique, parse_constant=bad_constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    q = sub.add_parser("queries"); q.add_argument("packet")
    s = sub.add_parser("evaluate")
    s.add_argument("packet"); s.add_argument("neural"); s.add_argument("language_only")
    s.add_argument("--fixed-lm")
    args = parser.parse_args()
    try:
        packet = read_json(args.packet)
        out = query_manifest(packet) if args.command == "queries" else evaluate(
            packet, read_json(args.neural), read_json(args.language_only),
            read_json(args.fixed_lm) if args.fixed_lm else None)
        print(json.dumps(out, indent=2, sort_keys=True, allow_nan=False))
    except (ContractError, OSError, json.JSONDecodeError) as e:
        parser.exit(2, f"invalid evaluation artifact: {e}\n")


if __name__ == "__main__":
    main()
