"""Paired descriptive MindBridge Table 1 CLIP comparison on the original panel.

Scores supplied features only. Equal target arrays do not authenticate their
origin, extraction, selected images, checkpoints or a matched experimental run.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

_SPEC = importlib.util.spec_from_file_location(
    "_mindbridge_table1_clip", Path(__file__).with_name("table1_clip.py"))
metric = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(metric)

MIN_WORKING_BYTES = 160 * 1024**2


def _targets(value):
    metric.need(isinstance(value, np.ndarray)
                and value.shape == (metric.GALLERY_SIZE, metric.CLIP_DIM)
                and value.dtype == np.dtype("float32")
                and np.isfinite(value).all(),
                "each arm requires complete finite float32 target features")
    return value


def _score(row, targets, load_array):
    prediction = load_array(row["selected_features"])
    metric.need(isinstance(prediction, np.ndarray)
                and prediction.shape == targets.shape,
                "complete selected feature gallery required in each arm")
    cosines = load_array(row["selection_cosines"])
    chosen = load_array(row["selected_candidate_indices"])
    metric.need(isinstance(cosines, np.ndarray)
                and len(cosines) == metric.GALLERY_SIZE,
                "each arm must select across its complete gallery")
    metric.source_selected_indices(cosines, chosen)
    return metric.two_way_from_features(targets, prediction)


def compare(reference_rows, candidate_rows, load_reference, load_candidate, *,
            max_working_bytes, include_image_counts=False):
    """Compare two complete declared feature panels, without a win decision.

    Image order must match across arms within each subject. Different subjects
    may use different orders, as in the single-arm evaluator. Source-style
    mean(counts)/981 is computed separately for each arm and subject; the reported
    aggregate difference is candidate macro score minus reference macro score.
    """
    reference = metric.validate_rows(reference_rows)
    candidate = metric.validate_rows(candidate_rows)
    metric.need(type(max_working_bytes) is int
                and max_working_bytes >= MIN_WORKING_BYTES,
                "at least 160 MiB paired numerical workspace required")
    metric.need(type(include_image_counts) is bool, "explicit boolean count-output choice")
    # Refuse a changed comparison panel before loading any arrays.
    for subject in metric.SUBJECTS:
        metric.need(reference[subject]["target_ids"] == candidate[subject]["target_ids"],
                    "candidate and reference must use identical ordered target identities")
    reference_scores, candidate_scores, details = {}, {}, []
    for subject in metric.SUBJECTS:
        old, new = reference[subject], candidate[subject]
        old_targets = _targets(load_reference(old["target_features"]))
        new_targets = _targets(load_candidate(new["target_features"]))
        metric.need(np.array_equal(old_targets, new_targets),
                    "candidate and reference target feature values must match exactly")
        del new_targets
        old_counts, old_score = _score(old, old_targets, load_reference)
        new_counts, new_score = _score(new, old_targets, load_candidate)
        reference_scores[subject] = old_score
        candidate_scores[subject] = new_score
        row = {"subject": subject, "images": metric.GALLERY_SIZE,
               "comparisons_per_image": metric.GALLERY_SIZE - 1,
               "reference_clip_two_way": old_score,
               "candidate_clip_two_way": new_score,
               "delta_clip_two_way": new_score - old_score,
               "reference_successful_comparisons": int(np.sum(old_counts)),
               "candidate_successful_comparisons": int(np.sum(new_counts))}
        if include_image_counts:
            row["image_ids"] = list(old["target_ids"])
            row["reference_success_counts"] = old_counts.tolist()
            row["candidate_success_counts"] = new_counts.tolist()
            row["success_count_deltas"] = (new_counts - old_counts).tolist()
        details.append(row)
        del old_targets, old_counts, new_counts
    reference_mean = metric.subject_mean(reference_scores)
    candidate_mean = metric.subject_mean(candidate_scores)
    delta = candidate_mean - reference_mean
    return {
        "schema": "mindbridge-table1-clip-paired-result/v1",
        "endpoint": "table1.mindbridge.joint-subjects-1257.clip",
        "feature_only": True,
        "subjects": details,
        "reference_clip_two_way": reference_mean,
        "candidate_clip_two_way": candidate_mean,
        "delta_clip_two_way": delta,
        "delta_percentage_points": 100 * delta,
        "delta_aggregation": "candidate subject mean minus reference subject mean",
        "image_counts_included": include_image_counts,
        "targets_equal_within_each_subject_across_arms": True,
        "target_aware_best_of_eight": True,
        "scientific_qualification": False,
        "reproduction": "unknown",
        "improvement": "unknown",
        "limits": [
            "The four subjects share 982 stimuli; image and subject rows are not independent repeats.",
            "Per-image counts share their subject's complete distractor gallery; no confidence interval or superiority test is supplied.",
            "Equal declared identities and target arrays do not authenticate original membership, native extraction, weights, or selected-image binding.",
            "Matched information, generation/compute budgets, frozen submissions and protected evaluation remain external requirements.",
            "This CLIP component does not qualify Table 1's other metrics or the separate Table 2 full48 endpoint.",
        ],
    }


def _read_manifest(path):
    path = Path(path)
    metric.need(path.is_file() and path.stat().st_size <= 2 * 1024**2,
                "bounded Table 1 manifest required")
    with path.open("rb") as stream:
        raw = stream.read(2 * 1024**2 + 1)
    metric.need(len(raw) <= 2 * 1024**2, "bounded Table 1 manifest required")
    packet = json.loads(raw, object_pairs_hook=metric._object,
                        parse_constant=lambda _: (_ for _ in ()).throw(
                            metric.MetricError("nonfinite JSON")))
    metric.need(type(packet) is dict and set(packet) == {"schema", "rows"}
                and packet["schema"] == metric.SCHEMA,
                "exact Table 1 feature manifest required for each arm")
    return packet["rows"], hashlib.sha256(raw).hexdigest(), len(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_manifest")
    parser.add_argument("candidate_manifest")
    parser.add_argument("--max-read-bytes", type=int, required=True,
                        help="shared NPY payload byte limit across both arms")
    parser.add_argument("--max-working-bytes", type=int, required=True)
    parser.add_argument("--include-image-counts", action="store_true",
                        help="include operator-private stimulus IDs and paired count vectors")
    args = parser.parse_args(argv)
    paths = [Path(args.reference_manifest), Path(args.candidate_manifest)]
    packets = [_read_manifest(path) for path in paths]
    readers = [metric.FileArrays(path.parent, args.max_read_bytes) for path in paths]
    consumed = 0

    def load(index, descriptor):
        nonlocal consumed
        reader = readers[index]
        previous = reader.read_bytes
        reader.limit = previous + args.max_read_bytes - consumed
        try:
            return reader(descriptor)
        finally:
            consumed += reader.read_bytes - previous

    result = compare(packets[0][0], packets[1][0],
                     lambda d: load(0, d), lambda d: load(1, d),
                     max_working_bytes=args.max_working_bytes,
                     include_image_counts=args.include_image_counts)
    result["reference_manifest_sha256"] = packets[0][1]
    result["candidate_manifest_sha256"] = packets[1][1]
    result["manifest_read_bytes"] = sum(packet[2] for packet in packets)
    result["payload_read_bytes"] = consumed
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
