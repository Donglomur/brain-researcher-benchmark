"""PAPER-paper-method-020: protected BOLD5000-QA construction components.

This module never loads pickled NPY records, trains a model, or authenticates
scientific results.  See the adjacent README and provenance.json for scope.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
from typing import Any


TASK_ID = "PAPER-paper-method-020"
CONTRACT_SHA256 = "263ea4a405bdee13a1003048c883293b224589ebce6e4816e7a3e5e4b8248182"
CODE_REVISION = "8071fb42c3ddac0355f2c0b5977baa32e33f6e14"
DATA_REVISION = "36c60313218c0fbf7c381294b81469f8d085ff46"
INVENTORY_PATHS_SHA256 = "8d6625c56d58c289f7a1fbded9730233eaf3ea203f9dab8cde5dbee6dfa8167a"
TEST_PATHS_SHA256 = "fca1becad9f02f509729c8de8a61becde3fcb0e2ba50712c1ceb7357bc9ddceb"
CONDITIONS = ("neural", "no_neural", "shuffled_neural")
PROTOCOL = "prospective_within_person_all_queries_v1"
HOLDS = (
    "Authentic NPY payload conversion, schema and identity evidence are not verified here.",
    "Native author execution and independently audited empirical reference remain unperformed.",
    "Public test exposure, train-plus-test native domain construction and native test-based checkpoint selection remain recorded.",
    "This within-person source partition does not establish held-out-person generalization.",
    "A neural ablation contrast alone does not establish neural understanding or whole-paper reproduction.",
    "Input, stimulus, code, manuscript and model rights require separate adjudication.",
    "Model/prompt equality declarations require independent runtime verification.",
    "A field allowlist cannot establish that question text is free of answer-bearing cues.",
    "Difficulty, target tolerances, protected assessment and scientific qualification remain open.",
)


class ContractError(ValueError):
    """An input would change the declared population or information boundary."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field} must be nonempty text")
    return value


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ContractError(f"{field} must be a lowercase SHA-256")
    return value


def _path_parts(path: str) -> tuple[str, str]:
    p = PurePosixPath(_text(path, "source path"))
    if len(p.parts) != 3 or p.is_absolute() or ".." in p.parts or p.suffix != ".npy":
        raise ContractError(f"not an official subject/split/record.npy path: {path}")
    subject, split, _ = p.parts
    if split not in {"train", "test"}:
        raise ContractError(f"unexpected source split: {split}")
    return subject, split


@dataclass(frozen=True)
class Inventory:
    paths: tuple[str, ...]
    contract_sha256: str
    engineering_fixture: bool = False

    def __post_init__(self) -> None:
        if type(self.engineering_fixture) is not bool:
            raise ContractError("engineering_fixture must be a boolean")
        if not self.paths or len(self.paths) != len(set(self.paths)):
            raise ContractError("inventory must be nonempty and contain unique paths")
        for path in self.paths:
            _path_parts(path)
        if not self.engineering_fixture and self.contract_sha256 != CONTRACT_SHA256:
            raise ContractError("unexpected canonical task digest")
        if not self.engineering_fixture and _digest(sorted(self.paths)) != INVENTORY_PATHS_SHA256:
            raise ContractError("production inventory does not contain the exact canonical path set")


def load_inventory(contract: str | Path) -> Inventory:
    """Bind the production population to the exact immutable task specification."""
    raw = Path(contract).read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise ContractError("canonical task SHA-256 mismatch")
    task = json.loads(raw)
    names = [item["recorded_fields"].get("name")
             for item in task["input_assets"]["exact_asset_records"]]
    # The saved evidence repeats three inventory entries. Deduplicate paths,
    # never rows/questions inside a neural record.
    paths = tuple(sorted({p for p in names if isinstance(p, str) and p.endswith(".npy")}))
    counts = Counter("/".join(PurePosixPath(p).parts[:2]) for p in paths)
    if counts != {"CSI1/train": 4802, "CSI1/test": 84}:
        raise ContractError("frozen source inventory counts changed")
    return Inventory(paths, CONTRACT_SHA256)


def inventory_summary(inventory: Inventory) -> dict:
    return {"task_id": TASK_ID, "contract_sha256": inventory.contract_sha256,
            "data_revision": DATA_REVISION, "records": len(inventory.paths),
            "counts": dict(sorted(Counter("/".join(PurePosixPath(p).parts[:2])
                                           for p in inventory.paths).items())),
            "engineering_fixture": inventory.engineering_fixture,
            "filename_is_image_identity": False,
            "scientifically_qualified": False}


def _index(rows: list[dict], field: str, label: str) -> dict[str, dict]:
    if not isinstance(rows, list):
        raise ContractError(f"{label} must be a list")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ContractError(f"{label} contains a non-object")
        key = _text(row.get(field), f"{label}.{field}")
        if key in result:
            raise ContractError(f"duplicate {label} key: {key}")
        result[key] = row
    return result


def _complete(actual: set, expected: set, label: str) -> None:
    if actual != expected:
        missing, extra = sorted(expected - actual), sorted(actual - expected)
        raise ContractError(f"{label} population mismatch: missing={missing[:5]} ({len(missing)}), "
                            f"extra={extra[:5]} ({len(extra)})")


def _image_groups(rows: dict[str, dict]) -> dict[str, str]:
    """Connected stimulus components under either canonical ID or content hash."""
    parent = {}

    def find(item: str) -> str:
        parent.setdefault(item, item)
        root = item
        while parent[root] != root:
            root = parent[root]
        while parent[item] != item:
            next_item = parent[item]
            parent[item] = root
            item = next_item
        return root

    for row in rows.values():
        left, right = find("id:" + row["image_id"]), find("sha:" + row["image_sha256"])
        parent[max(left, right)] = min(left, right)
    return {path: find("id:" + row["image_id"]) for path, row in rows.items()}


def audit_identities(inventory: Inventory, identities: list[dict]) -> dict:
    """Audit metadata only; no questions, answers or neural values are inspected.

    image_id must identify the source stimulus, not the enumerated NPY filename.
    image_sha256 is an independently supplied stimulus content hash. Both are
    used so aliases and duplicated bytes cannot evade overlap detection.
    """
    rows = _index(identities, "path", "identity")
    _complete(set(rows), set(inventory.paths), "identity")
    by_id, by_hash, by_person = defaultdict(set), defaultdict(set), defaultdict(set)
    person_for_subject = defaultdict(set)
    for path, row in rows.items():
        subject, split = _path_parts(path)
        if row.get("subject") != subject:
            raise ContractError(f"subject disagrees with source directory: {path}")
        person = _text(row.get("person_id"), "person_id")
        image = _text(row.get("image_id"), "image_id")
        image_hash = _sha(row.get("image_sha256"), "image_sha256")
        _text(row.get("identity_evidence"), "identity_evidence")
        by_id[image].add(split)
        by_hash[image_hash].add(split)
        by_person[person].add(split)
        person_for_subject[subject].add(person)
    if any(len(people) != 1 for people in person_for_subject.values()):
        raise ContractError("one source subject is mapped to multiple persons")
    id_overlap = sorted(k for k, splits in by_id.items() if len(splits) > 1)
    hash_overlap = sorted(k for k, splits in by_hash.items() if len(splits) > 1)
    person_overlap = sorted(k for k, splits in by_person.items() if len(splits) > 1)
    groups = _image_groups(rows)
    group_splits = defaultdict(set)
    for path, group in groups.items():
        group_splits[group].add(_path_parts(path)[1])
    group_overlap = sorted(k for k, splits in group_splits.items() if len(splits) > 1)
    return {**inventory_summary(inventory), "identity_rows": len(rows),
            "cross_split_image_ids": id_overlap,
            "cross_split_image_hashes": hash_overlap,
            "cross_split_person_ids": person_overlap,
            "cross_split_image_groups": group_overlap,
            "image_disjoint_as_declared": not group_overlap,
            "person_disjoint_as_declared": not person_overlap,
            "identity_evidence_independently_verified": False,
            "scope": "label-blind audit of supplied identities; filenames are enumeration indices",
            "preserved_holds": list(HOLDS)}


def _matrix(value: Any) -> list[list[float]]:
    if not isinstance(value, list) or len(value) != 5:
        raise ContractError("brain_region must have native BOLD5000 shape [5,1024]")
    for row in value:
        if not isinstance(row, list) or len(row) != 1024:
            raise ContractError("brain_region must have native BOLD5000 shape [5,1024]")
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in row):
            raise ContractError("brain_region must contain finite numeric values")
    return deepcopy(value)


def project_record(record: dict, *, supervised: bool = False) -> dict:
    """Explicit model allowlist; images/config/scene graphs never pass through.

    Trusted conversion to JSON must happen outside this module. The native NPY
    loader uses allow_pickle=True and is deliberately not invoked by this tool.
    """
    if not isinstance(record, dict):
        raise ContractError("record must be an object")
    queries = record.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ContractError("every declared record must have a nonempty queries list")
    for query in queries:
        _text(query, "query")
    projected = {"queries": list(queries), "brain_region": _matrix(record.get("brain_region"))}
    if supervised:
        answers = record.get("answers")
        if not isinstance(answers, list) or len(answers) != len(queries):
            raise ContractError("answers and queries must have identical lengths")
        for answer in answers:
            if type(answer) not in (str, int, bool) or (isinstance(answer, str) and not answer):
                raise ContractError("answers must be nonempty strings, integers, or booleans")
        projected["answers"] = list(answers)
    return projected


def _donors(paths: list[str], identities: dict[str, dict], seed: str) -> dict[str, str]:
    """Deterministic label-blind perfect matching to different source stimuli.

    Matching permutes image groups within subject/split and record-count strata,
    preserving the exact neural-record marginal distribution. All queries and
    repeated records of a target image receive the same donor image. An unequal
    group size that cannot be matched is rejected, never resampled or dropped.
    """
    image_groups = _image_groups(identities)
    groups = defaultdict(list)
    for path in paths:
        groups[(*_path_parts(path), image_groups[path])].append(path)
    strata = defaultdict(list)
    for key, members in groups.items():
        strata[(*key[:2], len(members))].append(key)
    mapping = {}
    for stratum, members in sorted(strata.items()):
        order = sorted(members, key=lambda p: _digest([seed, "target", p]))
        candidates = {}
        for target in order:
            candidates[target] = sorted(
                [donor for donor in members if donor != target],
                key=lambda p: _digest([seed, target, p]))
        # Iterative augmenting paths avoid recursion limits in a full inventory.
        assigned = {}
        for target in order:
            queue, seen_targets, seen_donors = [target], {target}, set()
            parent = {}
            free = None
            for current in queue:
                for donor in candidates[current]:
                    if donor in seen_donors:
                        continue
                    seen_donors.add(donor)
                    parent[donor] = current
                    if donor not in assigned:
                        free = donor
                        break
                    previous = assigned[donor]
                    if previous not in seen_targets:
                        seen_targets.add(previous)
                        queue.append(previous)
                if free is not None:
                    break
            if free is None:
                raise ContractError(f"no image-disjoint neural permutation exists in {stratum}")
            reverse = {v: k for k, v in assigned.items()}
            while free is not None:
                current = parent[free]
                previous = reverse.get(current)
                assigned[free] = current
                free = previous
        for donor, target in assigned.items():
            mapping.update(zip(sorted(groups[target]), sorted(groups[donor])))
    return mapping


def arm_packet(operator_bundle: dict, condition: str) -> dict:
    """Extract the only packet allowed in one isolated inference environment.

    The combined bundle must remain operator-only: exposing all three arms to
    a decoder would disclose the true neural signal to the ablation controls.
    """
    if condition not in CONDITIONS:
        raise ContractError("unknown condition")
    return {"task_id": TASK_ID, "protocol": PROTOCOL, "condition": condition,
            "engineering_fixture": operator_bundle["engineering_fixture"],
            "training": deepcopy(operator_bundle["training"]),
            "evaluation": deepcopy(operator_bundle["conditions"][condition])}


def prepare_assessment(inventory: Inventory, identities: list[dict], records: list[dict],
                       *, shuffle_seed: str, id_salt: str) -> tuple[dict, dict]:
    """Build a safe supervised-training packet and three matched test packets.

    All canonical records and all their questions are mandatory. Source test
    questions are never silently removed because of unknown concepts. Combined
    inputs and answers are BOTH operator-only. Use arm_packet to release one
    condition into each isolated environment; never release the combined set.
    """
    _text(shuffle_seed, "shuffle_seed")
    if len(_text(id_salt, "id_salt")) < 16:
        raise ContractError("id_salt requires at least 16 characters")
    audit = audit_identities(inventory, identities)
    if not audit["image_disjoint_as_declared"]:
        raise ContractError("source image overlap blocks prospective protected assessment; audit without dropping records")
    identity = _index(identities, "path", "identity")
    image_groups = _image_groups(identity)
    raw = _index(records, "path", "record")
    _complete(set(raw), set(inventory.paths), "record")
    clean = {p: project_record(raw[p], supervised=True) for p in inventory.paths}
    test_paths = [p for p in inventory.paths if _path_parts(p)[1] == "test"]
    if not test_paths:
        raise ContractError("no test population")
    donors = _donors(test_paths, identity, shuffle_seed)
    public = {"task_id": TASK_ID, "protocol": PROTOCOL,
              "engineering_fixture": inventory.engineering_fixture,
              "training": [], "conditions": {c: [] for c in CONDITIONS}}
    protected = {"task_id": TASK_ID, "protocol": PROTOCOL,
                 "contract_sha256": inventory.contract_sha256,
                 "engineering_fixture": inventory.engineering_fixture,
                 "audit": audit, "targets": [], "donor_bindings": donors,
                 "source_records": [{"path": p, "query_count": len(clean[p]["queries"])}
                                    for p in inventory.paths],
                 "shuffle_seed": shuffle_seed, "preserved_holds": list(HOLDS)}
    for path in inventory.paths:
        row, split = clean[path], _path_parts(path)[1]
        record_id = _digest([id_salt, path])
        if split == "train":
            public["training"].append({"id": record_id, **row})
            continue
        question_ids = []
        for index, (query, answer) in enumerate(zip(row["queries"], row["answers"])):
            qid = _digest([id_salt, path, index])
            question_ids.append(qid)
            protected["targets"].append({"id": qid, "path": path,
                                          "person_id": identity[path]["person_id"],
                                          "image_id": identity[path]["image_id"],
                                          "image_sha256": identity[path]["image_sha256"],
                                          "image_group": image_groups[path],
                                          "query_index": index, "answer": answer})
        for condition in CONDITIONS:
            matrix = row["brain_region"] if condition == "neural" else (
                [[0.0] * 1024 for _ in range(5)] if condition == "no_neural"
                else clean[donors[path]]["brain_region"])
            # One tensor per image record, never duplicated for every question.
            # Target identities, source image and answer fields are absent.
            public["conditions"][condition].append({"id": record_id,
                                                     "question_ids": question_ids,
                                                     "queries": list(row["queries"]),
                                                     "brain_region": deepcopy(matrix)})
    protected["arm_packet_sha256"] = {c: _digest(arm_packet(public, c)) for c in CONDITIONS}
    protected["assessment_sha256"] = _digest(protected)
    return public, protected


def decode_execution(execution: dict | None, vocabulary: list[str]) -> str | None:
    """Decode source QALoss outputs: >0 bool, ties-to-even integer, argmax vocab."""
    if execution is None:
        return None
    if not isinstance(execution, dict):
        raise ContractError("execution must be null or an object")
    kind = execution.get("kind")
    value = execution.get("value")
    if kind in {"bool", "int64"}:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ContractError("scalar execution must be finite")
        return ("yes" if value > 0 else "no") if kind == "bool" else str(round(value))
    if kind == "Object":
        return None  # QALoss never marks Object-valued answers correct.
    if kind != "vocab":
        raise ContractError(f"unsupported execution kind: {kind}")
    if not isinstance(value, list) or len(value) != len(vocabulary) or not value:
        raise ContractError("vocabulary score vector has the wrong length")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
        raise ContractError("vocabulary scores must be finite")
    return vocabulary[max(range(len(value)), key=value.__getitem__)]


def _correct(execution: dict | None, answer: Any, vocabulary: list[str]) -> tuple[int, int]:
    decoded = decode_execution(execution, vocabulary)
    if execution is None:
        return 0, 0
    kind = execution["kind"]
    if kind == "bool":
        target = answer == "yes" if answer in ("yes", "no") else answer
        return int(type(target) is bool and (decoded == "yes") == target), 1
    if kind == "int64":
        return int(type(answer) is int and decoded == str(answer)), 1
    if kind == "Object":
        return 0, 1
    return int(isinstance(answer, str) and decoded == answer), 1


def _mean(values: list[int | float]) -> float | None:
    return sum(values) / len(values) if values else None


def _production_binding(protected: dict, targets: dict[str, dict]) -> None:
    """Validate complete declared source coverage; this is not payload attestation."""
    if type(protected.get("engineering_fixture")) is not bool:
        raise ContractError("assessment engineering_fixture must be a boolean")
    if protected["engineering_fixture"]:
        return
    if protected.get("contract_sha256") != CONTRACT_SHA256:
        raise ContractError("production assessment lacks canonical contract binding")
    audit = protected.get("audit")
    if not isinstance(audit, dict) or audit.get("contract_sha256") != CONTRACT_SHA256:
        raise ContractError("production assessment lacks canonical identity audit")
    if (audit.get("engineering_fixture") is not False or audit.get("records") != 4886
            or audit.get("counts") != {"CSI1/train": 4802, "CSI1/test": 84}
            or audit.get("data_revision") != DATA_REVISION
            or audit.get("image_disjoint_as_declared") is not True):
        raise ContractError("production identity audit population/split mismatch")
    records = _index(protected.get("source_records"), "path", "source record")
    if _digest(sorted(records)) != INVENTORY_PATHS_SHA256:
        raise ContractError("production source-record inventory mismatch")
    test_paths = {path for path in records if _path_parts(path)[1] == "test"}
    if _digest(sorted(test_paths)) != TEST_PATHS_SHA256:
        raise ContractError("production test path inventory mismatch")
    for record in records.values():
        if type(record.get("query_count")) is not int or record["query_count"] <= 0:
            raise ContractError("source query count must be a positive integer")
    indices = defaultdict(set)
    for target in targets.values():
        path, index = target.get("path"), target.get("query_index")
        if path not in test_paths or type(index) is not int or index < 0:
            raise ContractError("target is outside the declared source test queries")
        if index in indices[path]:
            raise ContractError("duplicate source path/query-index target")
        indices[path].add(index)
    _complete(set(indices), test_paths, "production target path")
    for path in test_paths:
        if indices[path] != set(range(records[path]["query_count"])):
            raise ContractError("production target query indices are not exhaustive")


def score_assessment(protected: dict, runs: dict, vocabulary: list[str]) -> dict:
    """Score every declared test query and require matched control provenance.

    Equality checks on runtime declarations are necessary, not attestation that
    a model really obeyed them. Authentic execution remains a separate hold.
    """
    if not isinstance(vocabulary, list) or not vocabulary or len(set(vocabulary)) != len(vocabulary):
        raise ContractError("vocabulary must be a nonempty unique list")
    for word in vocabulary:
        _text(word, "vocabulary item")
    if protected.get("protocol") != PROTOCOL or protected.get("task_id") != TASK_ID:
        raise ContractError("unsupported protected assessment")
    body = {k: v for k, v in protected.items() if k != "assessment_sha256"}
    if _digest(body) != protected.get("assessment_sha256"):
        raise ContractError("protected assessment digest mismatch")
    targets = _index(protected.get("targets"), "id", "target")
    if not targets:
        raise ContractError("empty target population")
    _production_binding(protected, targets)
    _complete(set(runs), set(CONDITIONS), "condition")
    required_provenance = {"model_sha256", "language_model_sha256", "prompt_sha256",
                           "domain_sha256", "vocabulary_sha256", "selection_policy",
                           "domain_policy", "runtime_sha256", "inference_seed",
                           "decoding_config_sha256", "training_partition_sha256",
                           "non_neural_resources_sha256"}
    provenance, per_condition, correctness = None, {}, {}
    for condition in CONDITIONS:
        run = runs[condition]
        if not isinstance(run, dict) or run.get("assessment_sha256") != protected["assessment_sha256"]:
            raise ContractError("run is not bound to this assessment")
        if run.get("input_packet_sha256") != protected["arm_packet_sha256"].get(condition):
            raise ContractError("run is not bound to its condition packet")
        current = run.get("provenance")
        if not isinstance(current, dict) or set(current) != required_provenance:
            raise ContractError("incomplete or extra run provenance fields")
        for field in required_provenance:
            if field.endswith("sha256"):
                _sha(current[field], field)
            else:
                _text(current[field], field)
        if current["vocabulary_sha256"] != _digest(vocabulary):
            raise ContractError("vocabulary digest mismatch")
        if current["selection_policy"] != "train_validation_only" or current["domain_policy"] != "train_only":
            raise ContractError("prospective scoring requires train-only domain and train/validation-only selection")
        if provenance is not None and current != provenance:
            raise ContractError("neural controls changed model/prompt/domain/runtime provenance")
        provenance = current
        predictions = _index(run.get("predictions"), "id", "prediction")
        _complete(set(predictions), set(targets), f"{condition} query")
        values, success, image_values, person_values, types = {}, [], defaultdict(list), defaultdict(list), defaultdict(list)
        for qid, target in targets.items():
            prediction = predictions[qid]
            if set(prediction) != {"id", "execution"}:
                raise ContractError("prediction fields must be exactly id and execution")
            correct, executed = _correct(prediction["execution"], target["answer"], vocabulary)
            values[qid] = correct
            success.append(executed)
            # Group by declared stimulus identity across records/persons, not by question.
            image_values[target["image_group"]].append(correct)
            person_values[target["person_id"]].append(correct)
            answer_type = "yes_no" if type(target["answer"]) is bool or target["answer"] in ("yes", "no") else "other"
            types[answer_type].append(correct)
        correctness[condition] = values
        per_condition[condition] = {"queries": len(values), "correct": sum(values.values()),
                                    "qa_accuracy": _mean(list(values.values())),
                                    "execution_success_rate": _mean(success),
                                    "image_macro_accuracy": _mean([_mean(v) for v in image_values.values()]),
                                    "person_macro_accuracy": _mean([_mean(v) for v in person_values.values()]),
                                    "images": len(image_values), "persons": len(person_values),
                                    "person_accuracy": {k: _mean(v) for k, v in sorted(person_values.items())},
                                    "answer_type_accuracy": {k: {"n": len(v), "accuracy": _mean(v)}
                                                             for k, v in sorted(types.items())}}
    deltas = {}
    for control in CONDITIONS[1:]:
        grouped = defaultdict(list)
        people = defaultdict(list)
        differences = []
        for qid, target in targets.items():
            delta = correctness["neural"][qid] - correctness[control][qid]
            differences.append(delta)
            grouped[target["image_group"]].append(delta)
            people[target["person_id"]].append(delta)
        deltas[control] = {"query_paired_accuracy_difference": _mean(differences),
                           "image_macro_paired_difference": _mean([_mean(v) for v in grouped.values()]),
                           "person_macro_paired_difference": _mean([_mean(v) for v in people.values()]),
                           "neural_only_correct": sum(d == 1 for d in differences),
                           "control_only_correct": sum(d == -1 for d in differences)}
    return {"task_id": TASK_ID, "protocol": PROTOCOL,
            "assessment_sha256": protected["assessment_sha256"],
            "engineering_fixture": protected["engineering_fixture"],
            "conditions": per_condition, "neural_minus_control": deltas,
            "metric_status": "source-derived QA decisions; prospective exhaustive denominator and control policy",
            "scientifically_qualified": False, "native_reproduction_established": False,
            "preserved_holds": protected["preserved_holds"]}


def _load(path: str) -> Any:
    def reject(value: str) -> None:
        raise ContractError(f"nonfinite JSON constant: {value}")
    def unique(pairs: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ContractError(f"duplicate JSON object key: {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), parse_constant=reject, object_pairs_hook=unique)


def _save(path: str, value: Any) -> None:
    # Exclusive creation avoids accidental replacement of protected material.
    with Path(path).open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2, ensure_ascii=False, allow_nan=False)
        output.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("contract")
    audit = sub.add_parser("audit-identities")
    audit.add_argument("contract")
    audit.add_argument("identities")
    prepare = sub.add_parser("prepare")
    for name in ("contract", "identities", "records", "operator_output_directory"):
        prepare.add_argument(name)
    prepare.add_argument("--shuffle-seed", required=True)
    prepare.add_argument("--id-salt", required=True)
    score = sub.add_parser("score")
    for name in ("protected", "runs", "vocabulary"):
        score.add_argument(name)
    args = parser.parse_args()
    try:
        if args.command == "inventory":
            result = inventory_summary(load_inventory(args.contract))
        elif args.command == "audit-identities":
            result = audit_identities(load_inventory(args.contract), _load(args.identities))
        elif args.command == "prepare":
            output = Path(args.operator_output_directory)
            if output.exists():
                raise ContractError("operator output directory already exists")
            public, protected = prepare_assessment(load_inventory(args.contract), _load(args.identities),
                                                   _load(args.records), shuffle_seed=args.shuffle_seed,
                                                   id_salt=args.id_salt)
            output.mkdir(mode=0o700)
            _save(str(output / "protected.json"), protected)
            for condition in CONDITIONS:
                _save(str(output / f"{condition}.json"), arm_packet(public, condition))
            result = {"assessment_sha256": protected["assessment_sha256"],
                      "test_queries": len(protected["targets"]), "scientifically_qualified": False}
        else:
            result = score_assessment(_load(args.protected), _load(args.runs), _load(args.vocabulary))
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ContractError, OSError, json.JSONDecodeError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
