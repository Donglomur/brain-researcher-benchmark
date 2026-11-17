"""Source-style stimulus decoding scores; no fitting, fold generation, or selection.

All reference records and original fold assignments are supplied by the operator.
Validation establishes consistency, never that those records came from the paper.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import math
from itertools import combinations, product
from pathlib import Path
from statistics import fmean, pstdev


ROI_PAIRS = (
    ("Category_Selective", "IPS"),
    ("Category_Selective", "Prefrontal_Cortex"),
    ("Category_Selective", "V1_V2"),
    ("IPS", "Category_Selective"),
    ("Prefrontal_Cortex", "Category_Selective"),
    ("V1_V2", "Category_Selective"),
)
RELEVANCE = ("Relevant-non-target", "Irrelevant")
PERIODS = ("on", "off")
CLASSES = ("face", "false", "letter", "object")
CLASS_PAIRS = tuple(combinations(CLASSES, 2))
BLOCKS = tuple((a, b, r, p) for (a, b), r, p in product(ROI_PAIRS, RELEVANCE, PERIODS))
ROSTER_SHA256 = "6e0970cb1a1a9aab53a35c43c3bcf84af527131631418bfd00594528e43bf70a"
AUTHOR_COLUMNS = (
    "SPI", "classifier", "meta_ROI_from", "meta_ROI_to", "relevance_type",
    "stimulus_presentation", "stimulus_combo", "accuracy", "accuracy_SD", "AUC", "AUC_SD",
)


class ScoreError(ValueError):
    """Input does not meet the explicitly supplied comparison support."""


def _require(condition, message):
    if not condition:
        raise ScoreError(message)


def _name(value):
    _require(isinstance(value, str) and bool(value.strip()), "empty or non-string identifier")
    return value


def _number(value, name):
    _require(type(value) in (int, float), f"{name} must be a finite number")
    _require(0 <= value <= 1 and math.isfinite(value), f"{name} must be in [0,1]")
    return float(value)


def published_participants():
    """Read the already-pinned public identifier list, never any private targets."""
    path = Path(__file__).parent.parent / "nested-connectivity-v1" / "published_participants.txt"
    raw = path.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == ROSTER_SHA256, "published roster identity changed")
    participants = tuple(raw.decode("utf-8").splitlines())
    _require(len(participants) == len(set(participants)) == 94, "published roster is not 94 unique IDs")
    return participants


def class_pair(value):
    """Canonical comparison identity; probability orientation is lexical class order."""
    _require(isinstance(value, (list, tuple)) and len(value) == 2, "binary class pair required")
    _require(all(isinstance(x, str) and x in CLASSES for x in value), "unknown stimulus class")
    pair = tuple(sorted(value))
    _require(pair in CLASS_PAIRS, "two distinct stimulus classes required")
    return pair


def expected_cells(measure_ids, eligibility):
    """Compile complete source support from an externally established QC ledger.

    A block is (ROI_from, ROI_to, relevance, on/off). Every one of the 246
    measures needs an explicit status in each of 24 blocks: None means included;
    a nonempty reason string means excluded. A measure passing block QC generates
    all six stimulus-pair cells, matching the placement of QC in author code.
    """
    _require(isinstance(measure_ids, (list, tuple)), "measure_ids must be ordered")
    _require(all(isinstance(x, str) and x.strip() for x in measure_ids), "invalid measure ID")
    _require(len(measure_ids) == len(set(measure_ids)) == 246, "exact 246-measure domain required")
    _require(isinstance(eligibility, dict) and set(eligibility) == set(BLOCKS), "all 24 source blocks required")
    cells, seen = [], set()
    for block in BLOCKS:
        status = eligibility[block]
        _require(isinstance(status, dict) and set(status) == set(measure_ids), "complete per-block QC statuses required")
        included = []
        for measure in measure_ids:
            reason = status[measure]
            _require(reason is None or (isinstance(reason, str) and reason.strip()), "invalid QC exclusion reason")
            if reason is None:
                included.append(measure)
                seen.add(measure)
                cells.extend((measure, *block, *pair) for pair in CLASS_PAIRS)
        _require(included, "an empty block does not cover the original endpoint family")
    _require(seen == set(measure_ids), "a retained measure has no eligible source block")
    return tuple(cells)


def _validate_cells(cells):
    _require(isinstance(cells, tuple) and cells, "compiled expected cells required")
    seen, blocks, measures = set(), {}, set()
    for key in cells:
        _require(isinstance(key, tuple) and len(key) == 7, "invalid source cell key")
        _require(all(isinstance(x, str) for x in key), "cell key fields must be strings")
        _require(key not in seen, "duplicate expected cell")
        seen.add(key)
        measure, block, pair = key[0], key[1:5], key[-2:]
        _name(measure)
        _require(block in BLOCKS and pair in CLASS_PAIRS, "unknown source endpoint")
        blocks.setdefault(block, {}).setdefault(measure, set()).add(pair)
        measures.add(measure)
    _require(len(measures) == 246 and set(blocks) == set(BLOCKS), "complete 246-measure, 24-block support required")
    _require(all(pairs == set(CLASS_PAIRS) for block in blocks.values() for pairs in block.values()), "QC-selected measure must retain all six stimulus pairs")
    return seen


def score_cell(observations, probabilities, pair):
    """Score one complete cell on supplied original out-of-fold observations.

    observations: sequence of {id, participant, label, fold}, with folds 0..9.
    probabilities: mapping id -> P(lexically second class). Exactly .5 selects
    the first class, as in the binary sklearn logistic decision at zero.
    The participant ledger is operator-owned; targets must not be delivered to
    candidate execution. This is an offline scorer, not a process sandbox.
    """
    pair = class_pair(pair)
    _require(isinstance(observations, (list, tuple)) and observations, "observations must be nonempty")
    _require(isinstance(probabilities, dict), "probabilities must be keyed by observation ID")
    roster = set(published_participants())
    observed, participant_folds = set(), {}
    counts, correct = [0] * 10, [0] * 10
    participant_counts, participant_correct = {}, {}
    for row in observations:
        _require(isinstance(row, dict) and set(row) == {"id", "participant", "label", "fold"}, "invalid observation fields")
        identifier, participant = _name(row["id"]), _name(row["participant"])
        _require(identifier not in observed, "duplicate observation ID")
        observed.add(identifier)
        _require(participant in roster, "unknown participant")
        fold, label = row["fold"], row["label"]
        _require(type(fold) is int and 0 <= fold < 10, "original fold must be an integer in 0..9")
        _require(label in pair, "target is not in the cell class pair")
        _require(participant_folds.get(participant, fold) == fold, "participant crosses held-out folds")
        participant_folds[participant] = fold
        _require(identifier in probabilities, "missing prediction")
        probability = _number(probabilities[identifier], "probability")
        hit = int(pair[int(probability > 0.5)] == label)
        counts[fold] += 1
        correct[fold] += hit
        participant_counts[participant] = participant_counts.get(participant, 0) + 1
        participant_correct[participant] = participant_correct.get(participant, 0) + hit
    _require(observed == set(probabilities), "unexpected prediction")
    _require(set(participant_folds) == roster, "all 94 published participants required")
    _require(all(counts), "all ten original folds must have held-out observations")
    scores = [hits / total for hits, total in zip(correct, counts)]
    return {
        "accuracy": fmean(scores),
        "accuracy_SD": pstdev(scores),
        "fold_accuracy": scores,
        "fold_observations": counts,
        "fold_correct": correct,
        "pooled_accuracy_descriptive": sum(correct) / sum(counts),
        "participant_accuracy_descriptive": {
            p: participant_correct[p] / participant_counts[p] for p in sorted(roster)
        },
        "observations": sum(counts),
        "participants": 94,
    }


def score_complete_matrix(cells, cell_inputs):
    """Consume all cell inputs before returning any matrix.

    cells must be the exact expected_cells result. cell_inputs is an iterable of
    (cell_key, observations, probabilities). No cross-cell averaging, selection,
    inferential uncertainty, or paper-win decision is introduced here.
    """
    expected = _validate_cells(cells)
    results = {}
    for key, observations, probabilities in cell_inputs:
        _require(key in expected, "unexpected source cell")
        _require(key not in results, "duplicate source cell")
        results[key] = score_cell(observations, probabilities, key[-2:])
    _require(set(results) == expected, "incomplete source result matrix")
    return {key: results[key] for key in cells}


def read_author_matrix(stream, cells):
    """Read the exact author stimulus CSV family, preserving every declared cell.

    This imports public author summaries; it cannot reconstruct their predictions
    or prove original fold identities. Reversed stimulus tuple order is an alias,
    whereas directed ROI order remains scientifically distinct.
    """
    expected = _validate_cells(cells)
    reader = csv.DictReader(stream)
    _require(reader.fieldnames is not None and len(reader.fieldnames) == len(set(reader.fieldnames)), "duplicate or absent CSV columns")
    _require(set(reader.fieldnames) == set(AUTHOR_COLUMNS), "not the source stimulus-accuracy CSV schema")
    results = {}
    for row in reader:
        _require(None not in row and all(v is not None for v in row.values()), "ragged CSV row")
        _require(row["classifier"] == "Logistic_Regression", "not the published logistic comparator")
        try:
            _require(len(row["stimulus_combo"]) <= 100, "oversized stimulus tuple")
            pair = class_pair(ast.literal_eval(row["stimulus_combo"]))
        except (ValueError, SyntaxError, TypeError, RecursionError) as exc:
            raise ScoreError("invalid source stimulus tuple") from exc
        key = (row["SPI"], row["meta_ROI_from"], row["meta_ROI_to"], row["relevance_type"], row["stimulus_presentation"], *pair)
        _require(key in expected, "unexpected source cell")
        _require(key not in results, "duplicate source cell, including reversed class aliases")
        metrics = {}
        for name in ("accuracy", "accuracy_SD", "AUC", "AUC_SD"):
            try:
                value = float(row[name])
            except ValueError as exc:
                raise ScoreError(f"invalid {name}") from exc
            metrics[name] = _number(value, name)
        _require(metrics["accuracy_SD"] <= 0.5 and metrics["AUC_SD"] <= 0.5, "impossible population SD for scores in [0,1]")
        results[key] = metrics
    _require(set(results) == expected, "incomplete source result matrix")
    return {key: results[key] for key in cells}


def compare_matrices(candidate, reference):
    """Report per-cell matched differences only; no hidden global win scalar."""
    _require(isinstance(candidate, dict) and isinstance(reference, dict), "keyed matrices required")
    _require(candidate and candidate.keys() == reference.keys(), "paired matrices must have identical support")
    _validate_cells(tuple(reference))
    return {
        key: {
            "candidate_accuracy": _number(candidate[key]["accuracy"], "candidate accuracy"),
            "reference_accuracy": _number(reference[key]["accuracy"], "reference accuracy"),
            "accuracy_difference": candidate[key]["accuracy"] - reference[key]["accuracy"],
        }
        for key in reference
    }
