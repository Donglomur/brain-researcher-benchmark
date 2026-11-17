"""Audit NEURONA's two source scoring paths from complete operator-held traces.

No native records, models, source parser, or scientific workload are loaded here.
The source parser's ordered function names are inputs, never guessed from text.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


_legacy_path = Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "evaluator.py"
_spec = importlib.util.spec_from_file_location("neurona_initial_evaluator_v1", _legacy_path)
legacy = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = legacy
_spec.loader.exec_module(legacy)
ContractError = legacy.ContractError
BUILTINS = ["equal", "greater_than", "less_than"]
SCHEMA = "neurona-source-trace/v2"
# Source data/bold5000_pred_cls.json at legacy.CODE_REVISION, including repeated under.
VOCAB_TYPES = {
    "Movement": ["climb", "play", "eat", "fly", "grow", "hold", "ride", "sit",
                 "use", "walk", "work", "resting", "wear"],
    "Position": ["under", "_in", "surround", "in_front_of", "beside", "on",
                 "under", "attached_to", "next_to"],
    "Thing": ["has", "_is"], "YesNo": ["yes", "no"],
}
PAPER_ANCHORS = {"Overall": 0.7041, "Action": 0.6207, "Position": 0.5079, "T/F": 0.7407}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ContractError(message)


def functions(value):
    require(isinstance(value, list) and value[:3] == BUILTINS,
            "ordered source domain must begin with the three native built-ins")
    require(all(isinstance(x, str) and x for x in value), "invalid domain function")
    require(len(value) == len(set(value)), "duplicate domain function")
    return value[3:]


def inspect_manifest(manifest):
    require(isinstance(manifest, dict), "manifest must be an object")
    require(manifest.get("schema") == SCHEMA, "unsupported manifest schema")
    require(type(manifest.get("engineering_fixture")) is bool, "explicit fixture marker required")
    require(manifest.get("source_code_revision") == legacy.CODE_REVISION, "source revision mismatch")
    require(manifest.get("data_revision") == legacy.DATA_REVISION, "data revision mismatch")
    functions(manifest.get("train_domain_functions"))
    legacy._sha(manifest.get("training_manifest_sha256"), "training_manifest_sha256")
    rows, paths, ids = [], set(), set()
    records = manifest.get("records")
    require(isinstance(records, list) and records, "nonempty test records required")
    for record in records:
        require(isinstance(record, dict), "record must be an object")
        path = record.get("path")
        require(legacy._path_parts(path) == ("CSI1", "test"), "only original CSI1 test records supported")
        require(path not in paths, "duplicate record path")
        paths.add(path)
        legacy._sha(record.get("source_sha256"), "record source_sha256")
        queries = record.get("queries")
        require(isinstance(queries, list) and queries, "every record needs all ordered queries")
        for index, query in enumerate(queries):
            require(isinstance(query, dict), "query must be an object")
            qid = legacy._text(query.get("id"), "query id")
            require(qid not in ids, "duplicate query id")
            ids.add(qid)
            legacy._sha(query.get("query_sha256"), "query_sha256")
            require(isinstance(query.get("answer"), str) and query["answer"],
                    "BOLD5000 source trace requires nonempty string answers")
            concepts = functions(query.get("domain_functions"))
            rows.append({"id": qid, "path": path, "query_index": index,
                         "answer": query["answer"], "concepts": concepts})
    if not manifest["engineering_fixture"]:
        require(digest(sorted(paths)) == legacy.TEST_PATHS_SHA256,
                "production manifest must contain exactly the original 84 test paths")
    return rows


def _trace(trace, rows, value_field):
    require(isinstance(trace, list), "complete trace must be a list")
    indexed = {}
    for item in trace:
        require(isinstance(item, dict) and set(item) == {"id", "outcome", value_field},
                "trace fields must be id, outcome and " + value_field)
        require(isinstance(item["id"], str) and item["id"] not in indexed, "duplicate/invalid trace id")
        require(item["outcome"] in {"returned", "raised", "not_called"}, "invalid trace outcome")
        if item["outcome"] != "returned":
            require(item[value_field] is None, "unexecuted or raised trace cannot contain a result")
        indexed[item["id"]] = item
    require(set(indexed) == {row["id"] for row in rows}, "trace must cover every declared query exactly once")
    return indexed


def _metric(correctness):
    return {"correct": sum(correctness.values()), "queries": len(correctness),
            "accuracy": sum(correctness.values()) / len(correctness) if correctness else None,
            "included_ids": sorted(correctness)}


def score(manifest, run, vocabulary):
    """Score completed source calls, preserving skipped, null and raised outcomes.

    This is the source ``train_hop=all`` / CSI1 condition. The posthoc functions
    receive training concepts. Zero-shot/hop-restricted settings are distinct.
    """
    rows = inspect_manifest(manifest)
    require(isinstance(run, dict), "run must be an object")
    require(run.get("manifest_sha256") == digest(manifest), "run manifest binding mismatch")
    require(run.get("train_hop") == "all", "only Table 1 all-hop source mode supported")
    require(run.get("neural_condition") in legacy.CONDITIONS, "unknown neural condition")
    require(run.get("access_condition") in {"paper_data", "paper_data_author_code"}, "unknown access condition")
    legacy._sha(run.get("checkpoint_sha256"), "checkpoint_sha256")
    legacy._text(run.get("selection_policy"), "selection_policy")
    require(isinstance(vocabulary, list) and vocabulary and
            all(isinstance(x, str) and x for x in vocabulary) and
            len(set(vocabulary)) == len(vocabulary), "invalid ordered vocabulary")
    require(run.get("vocabulary_sha256") == digest(vocabulary), "vocabulary binding mismatch")
    train_trace = _trace(run.get("training_monitor"), rows, "execution")
    plot_trace = _trace(run.get("posthoc"), rows, "pred_answer")
    known = set(manifest["train_domain_functions"])
    vocab2type = {word: category for category, words in VOCAB_TYPES.items() for word in words}
    train_values, plot_values, ledger = {}, {}, []
    buckets = {name: {} for name in ("T/F", *VOCAB_TYPES, "unknown", "Vocabulary")}
    aborted = False
    for row in rows:
        qid, answer = row["id"], row["answer"]
        unseen = sorted(set(row["concepts"]) - known)
        native = train_trace[qid]
        native_reason = "unseen_concept" if unseen else "included"
        native_correct = None
        if aborted:
            native_reason = "after_source_abort"
            require(native["outcome"] == "not_called", "training source cannot continue after an exception")
        elif unseen:
            require(native["outcome"] == "not_called", "training source must skip unseen concepts")
        else:
            require(native["outcome"] != "not_called", "missing eligible training-monitor execution")
            if native["outcome"] == "raised":
                aborted = True
                native_reason = "source_abort"
            else:
                if isinstance(native["execution"], dict) and native["execution"].get("kind") == "vocab":
                    require(answer in vocabulary, "source QALoss cannot return with an absent vocabulary target")
                native_correct = legacy._correct(native["execution"], answer, vocabulary)[0]
                train_values[qid] = native_correct
        plot = plot_trace[qid]
        # The TF function applies the hop gate before the unseen-concept gate.
        plot_reason = ("tf_hop_outside_1_3" if answer in {"yes", "no"} and
                       len(row["concepts"]) not in {1, 2, 3} else
                       "unseen_concept" if unseen else "included")
        plot_correct, category = None, "T/F" if answer in {"yes", "no"} else vocab2type.get(answer, "unknown")
        if plot_reason != "included":
            require(plot["outcome"] == "not_called", "posthoc source must skip ineligible queries")
        else:
            require(plot["outcome"] != "not_called", "missing eligible posthoc execution")
            if plot["outcome"] == "raised":
                plot_reason = "caught_exception"
            else:
                predicted = plot["pred_answer"]
                require(isinstance(predicted, str), "returned posthoc pred_answers[0] must be a string")
                # Native TF confusion matrix folds every non-yes token into no.
                plot_correct = int((predicted == "yes") == (answer == "yes")) if category == "T/F" else int(predicted == answer)
                plot_values[qid] = plot_correct
                buckets[category][qid] = plot_correct
                if category != "T/F":
                    buckets["Vocabulary"][qid] = plot_correct
        ledger.append({"id": qid, "path": row["path"], "query_index": row["query_index"],
                       "concept_count": len(row["concepts"]), "unseen_concepts": unseen,
                       "category": category, "training_reason": native_reason,
                       "training_correct": native_correct, "posthoc_reason": plot_reason,
                       "posthoc_correct": plot_correct})
    training = _metric(train_values)
    training.update(completed=not aborted, partial_accuracy=training["accuracy"] if aborted else None)
    if aborted:
        training["accuracy"] = None
    plotting = {"Overall": _metric(plot_values), **{k: _metric(v) for k, v in buckets.items()}}
    plotting["Action"] = plotting["Movement"].copy()
    return {"schema": "neurona-source-score/v2", "manifest_sha256": digest(manifest),
            "engineering_fixture": manifest["engineering_fixture"],
            "source_code_revision": legacy.CODE_REVISION, "data_revision": legacy.DATA_REVISION,
            "checkpoint_sha256": run["checkpoint_sha256"], "selection_policy": run["selection_policy"],
            "access_condition": run["access_condition"], "neural_condition": run["neural_condition"],
            "declared_records": len(manifest["records"]), "declared_queries": len(rows),
            "paper_reports_2095_queries": len(rows) == 2095,
            "training_monitor": training, "posthoc": plotting, "ledger": ledger,
            "exclusions": {field: dict(Counter(x[field] for x in ledger))
                           for field in ("training_reason", "posthoc_reason")},
            "paper_anchors": PAPER_ANCHORS, "table1_parity_authenticated": False,
            "qualification": "source_scoring_component_only"}


def compare(manifest, reference_run, candidate_run, vocabulary):
    """Keep reproduction distances distinct from same-query improvement deltas.

    A changed posthoc execution denominator is reported, never treated as a win.
    No tolerance, minimum effect, uncertainty, or current-SOTA rule is invented.
    """
    reference = score(manifest, reference_run, vocabulary)
    candidate = score(manifest, candidate_run, vocabulary)
    require(reference["neural_condition"] == candidate["neural_condition"], "comparison changed neural condition")
    comparisons = {}
    for metric, anchor in PAPER_ANCHORS.items():
        left, right = reference["posthoc"][metric], candidate["posthoc"][metric]
        comparable = bool(left["queries"]) and left["included_ids"] == right["included_ids"]
        comparisons[metric] = {
            "reference_queries": left["queries"], "candidate_queries": right["queries"],
            "same_included_queries": comparable,
            "reference_only_ids": sorted(set(left["included_ids"]) - set(right["included_ids"])),
            "candidate_only_ids": sorted(set(right["included_ids"]) - set(left["included_ids"])),
            "candidate_minus_reference": right["accuracy"] - left["accuracy"] if comparable else None,
            "reference_minus_published": left["accuracy"] - anchor if left["queries"] else None,
            "candidate_minus_published": right["accuracy"] - anchor if right["queries"] else None,
        }
    return {"reference": reference, "candidate": candidate, "posthoc_comparison": comparisons,
            "reproduction_established": False, "improvement_established": False,
            "reason": "Publication cohort/checkpoint/denominator identity and decision rules remain unqualified."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("run", type=Path)
    parser.add_argument("vocabulary", type=Path)
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args()
    # The predecessor reader rejects duplicate JSON keys and nonfinite literals.
    manifest, run, vocabulary = (legacy._load(str(p)) for p in (args.manifest, args.run, args.vocabulary))
    result = (compare(manifest, legacy._load(str(args.reference)), run, vocabulary) if args.reference
              else score(manifest, run, vocabulary))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
