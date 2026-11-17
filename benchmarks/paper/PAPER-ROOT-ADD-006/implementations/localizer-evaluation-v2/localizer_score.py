"""Original localizer accuracy arithmetic; no decoder fitting or qualification.

All predictions are scored. This module never selects a timepoint, penalty,
participant subset, or fold assignment from performance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

TASK_ID = "PAPER-ROOT-ADD-006"
SOURCE_REVISION = "1c9b3c92c77d4f5a4e4ccfa36d5a695814a2f612"
COHORT = tuple(f"sub-S{i:03d}" for i in range(1, 22))
EXCLUDED = ("sub-S006", "sub-S019")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _integer_vector(values, name):
    a = np.asarray(values)
    if a.ndim != 1 or a.dtype.kind not in "iu" or a.dtype.kind == "b":
        raise ValueError(f"{name}: integer vector required")
    return a


def _time_axis(values, name):
    a = _integer_vector(values, name)
    if not len(a) or any(int(t) % 10 for t in a) or any(int(r) <= int(l) for l, r in zip(a, a[1:])):
        raise ValueError(f"{name}: increasing exact 10-ms grid values required")
    return a


def validate_trials(trial_ids, image_class, fold_id, fold_count):
    """Validate supplied identities; never invent/recover source folds."""
    if not isinstance(trial_ids, list) or len(trial_ids) != 420:
        raise ValueError("all 420 localizer trial identities required")
    if any(not isinstance(t, str) or not t for t in trial_ids) or len(set(trial_ids)) != 420:
        raise ValueError("unique nonempty trial identities required")
    y = _integer_vector(image_class, "image_class")
    f = _integer_vector(fold_id, "fold_id")
    if y.shape != (420,) or f.shape != (420,):
        raise ValueError("labels/folds must align to all 420 trials")
    if type(fold_count) is not int or fold_count not in (5, 7):
        raise ValueError("declare deposited five-fold or paper seven-fold protocol")
    if set(y.tolist()) != set(range(1, 8)) or any(np.sum(y == c) != 60 for c in range(1, 8)):
        raise ValueError("all seven image classes require exactly 60 trials")
    if set(f.tolist()) != set(range(1, fold_count + 1)):
        raise ValueError("complete declared fold coverage required")
    for c in range(1, 8):
        counts = [int(np.sum((y == c) & (f == k))) for k in range(1, fold_count + 1)]
        if min(counts) == 0 or (fold_count == 5 and counts != [12] * 5):
            raise ValueError("class/fold support differs from declared protocol")
    return y, f


def score_participant(logits, image_class, train_ms, test_ms):
    """Score each cell over 180 outcome trials; return all cells and controls.

    The source stores seven channels but trains three outcome classifiers.
    Outcome accuracy uses only channels 1:3 and labels 1:3. Using logits
    avoids introducing sigmoid saturation ties; MATLAB max selects first ties.
    """
    tr, te = _time_axis(train_ms, "train_ms"), _time_axis(test_ms, "test_ms")
    y = _integer_vector(image_class, "image_class")
    if y.shape != (420,) or any(np.sum(y == c) != 60 for c in range(1, 8)):
        raise ValueError("complete seven-class localizer labels required")
    a = np.asanyarray(logits)
    if a.dtype.kind not in "fiu" or a.shape not in [(420, len(tr), len(te), 3), (420, len(tr), len(te), 7)]:
        raise ValueError("logits require trial x train x test x 3-or-7 channels")
    accuracy = np.empty((len(tr), len(te)))
    by_class = np.empty((3, len(tr), len(te)))
    ties = np.zeros((len(tr), len(te)), dtype=np.int64)
    outcomes = y <= 3
    # One training-time slice at a time also works on read-only NPY memmaps.
    for i in range(len(tr)):
        slab = a[:, i, :, :]
        if not np.isfinite(slab).all():
            raise ValueError("nonfinite prediction in supplied full panel")
        out = slab[outcomes, :, :3]
        predicted = np.argmax(out, axis=-1) + 1
        correct = predicted == y[outcomes, None]
        accuracy[i] = correct.mean(axis=0)
        ties[i] = ((out == out.max(axis=-1, keepdims=True)).sum(axis=-1) > 1).sum(axis=0)
        for c in range(1, 4):
            by_class[c - 1, i] = correct[y[outcomes] == c].mean(axis=0)
    common = [(i, int(np.flatnonzero(te == t)[0])) for i, t in enumerate(tr) if np.any(te == t)]
    return {"accuracy": accuracy, "by_class_accuracy": by_class, "tied_outcome_trials": ties,
            "diagonal_ms": [int(tr[i]) for i, _ in common],
            "diagonal": np.array([accuracy[i, j] for i, j in common])}


def summarize_cohort(participant_ids, maps):
    """Keep the deposited 21-person analysis and paper 19-person figure distinct."""
    if tuple(participant_ids) != COHORT:
        raise ValueError("complete ordered 21-participant source cohort required")
    a = np.asarray(maps)
    if a.dtype.kind not in "fiu" or a.ndim != 3 or a.shape[0] != 21 or not all(a.shape):
        raise ValueError("21 complete participant maps required")
    if not np.isfinite(a).all() or np.any((a < 0) | (a > 1)):
        raise ValueError("accuracy must be finite proportions")
    result = {}
    for name, ids in [("deposited_analysis_21", COHORT),
                      ("paper_figure_19", tuple(p for p in COHORT if p not in EXCLUDED))]:
        chosen = a[[COHORT.index(p) for p in ids]]
        result[name] = {"participant_ids": list(ids), "n_participants": len(ids),
                        "mean_accuracy": chosen.mean(axis=0).tolist(),
                        "participant_sem": (chosen.std(axis=0, ddof=1) / np.sqrt(len(ids))).tolist()}
    return result


def _local_array(base, record):
    name = record["path"]
    if not isinstance(name, str) or Path(name).is_absolute():
        raise ValueError("prediction path must be relative")
    path = (base / name).resolve(strict=True)
    if not path.is_relative_to(base.resolve()):
        raise ValueError("prediction path escapes manifest directory")
    if digest(path) != record["sha256"]:
        raise ValueError("prediction SHA256 mismatch")
    return np.load(path, mmap_mode="r", allow_pickle=False)


def evaluate(manifest_path):
    """Score a primitive operator packet; authentic joins remain unqualified."""
    manifest_path = Path(manifest_path)
    m = json.loads(manifest_path.read_text())
    if m.get("schema") != "localizer-score/v2" or m.get("source_revision") != SOURCE_REVISION:
        raise ValueError("schema/source revision mismatch")
    if m.get("input_kind") not in ("generated_control", "unqualified_operator_export"):
        raise ValueError("this scorer cannot authenticate native input")
    tr, te = _time_axis(m["train_ms"], "train_ms"), _time_axis(m["test_ms"], "test_ms")
    rows = m["participants"]
    if tuple(p["participant_id"] for p in rows) != COHORT:
        raise ValueError("complete ordered 21-participant source cohort required")
    paired = all("candidate_logits" in p for p in rows)
    if any("candidate_logits" in p for p in rows) != paired:
        raise ValueError("candidate predictions must cover all participants")
    author, candidate, details = [], [], []
    for row in rows:
        y, f = validate_trials(row["trial_ids"], row["image_class"], row["fold_id"], m["fold_count"])
        scores = {}
        for arm in (["author", "candidate"] if paired else ["author"]):
            prediction = row[f"{arm}_logits"]
            # Each independently exported prediction must attest to exactly the
            # same row/fold order, rather than inheriting a convenient ordering.
            order = {key: row[key] for key in ("participant_id", "trial_ids", "image_class", "fold_id")}
            order.update(train_ms=m["train_ms"], test_ms=m["test_ms"], fold_count=m["fold_count"])
            order_hash = hashlib.sha256(json.dumps(order, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            if prediction.get("trial_order_sha256") != order_hash:
                raise ValueError("prediction trial/fold order binding mismatch")
            scores[arm] = score_participant(_local_array(manifest_path.parent, prediction), y, tr, te)
        author.append(scores["author"]["accuracy"])
        if paired:
            candidate.append(scores["candidate"]["accuracy"])
        details.append({"participant_id": row["participant_id"], "outcome_trials": 180,
                        "class_fold_counts": [[int(np.sum((y == c) & (f == k)))
                                               for k in range(1, m["fold_count"] + 1)]
                                              for c in range(1, 8)],
                        "arms": {arm: {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in score.items()}
                                 for arm, score in scores.items()}})
    result = {"task_id": TASK_ID, "scope": "localizer_accuracy_arithmetic_only",
              "source_revision": SOURCE_REVISION, "input_manifest_sha256": digest(manifest_path),
              "input_kind": m["input_kind"], "declared_fold_count": m["fold_count"],
              "train_ms": tr.tolist(), "test_ms": te.tolist(), "participant_results": details,
              "author": summarize_cohort(COHORT, author), "reproduction_qualified": False,
              "improvement_qualified": False, "independent_final_holdout": False}
    if paired:
        result["candidate"] = summarize_cohort(COHORT, candidate)
        delta = np.asarray(candidate) - np.asarray(author)
        keep = [i for i, p in enumerate(COHORT) if p not in EXCLUDED]
        result["paired_candidate_minus_author"] = {
            "participant_ids": [COHORT[i] for i in keep], "participant_differences": delta[keep].tolist(),
            "mean_difference": delta[keep].mean(axis=0).tolist(),
            "participant_sem": (delta[keep].std(axis=0, ddof=1) / np.sqrt(19)).tolist(),
            "interpretation": "descriptive paired cells; no selection, confidence interval, multiplicity correction or win threshold"}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.manifest)
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
