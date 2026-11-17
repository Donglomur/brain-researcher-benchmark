"""Source-grounded Deeprecon neural conversion inference and complete-pair evaluation.

All fitting occurs outside this evaluator. Public/native qualification remains held.
See SOURCE_PROVENANCE.json and the task documentation for the exact source scope.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path
import time

import numpy as np

TASK_ID = "PAPER-paper-method-029"
SUBJECTS = tuple(f"sub{i:02d}" for i in range(1, 6))
ROIS = ("VC", "V1", "V2", "V3", "V4", "HVC")
METHODS = ("brain_loss", "content_loss")
SOURCE_COMMIT = "c264167c2b5a0fa71709a58ae5b50a042f6d7a79"


class ContractError(ValueError):
    """Input lacks the declared identities or the complete source population."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def array(value, name, ndim=None):
    value = np.asarray(value)
    require(value.dtype.kind in "fiu" and value.dtype.kind != "b", f"{name}: numeric array required")
    value = value.astype(np.float64)
    require(ndim is None or value.ndim == ndim, f"{name}: wrong rank")
    require(value.size > 0 and np.isfinite(value).all(), f"{name}: empty/nonfinite values")
    return value


def identifiers(value, name, unique=True):
    value = np.asarray(value)
    require(value.ndim == 1 and value.size > 0 and value.dtype.kind in "US", f"{name}: string vector required")
    result = [str(x) for x in value]
    require(all(result), f"{name}: empty identifier")
    require(not unique or len(set(result)) == len(result), f"{name}: duplicate identifier")
    return result


def stimulus_ids(value, name, unique=False):
    value = array(value, name, 1)
    require(not unique or len(np.unique(value)) == len(value), f"{name}: duplicate stimulus")
    return value


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pinned_path(base, record):
    require(isinstance(record, dict) and set(record) == {"path", "sha256"}, "file requires path and sha256")
    path = (base / record["path"]).resolve()
    expected = record["sha256"]
    require(isinstance(expected, str) and len(expected) == 64, "invalid SHA256")
    require(path.is_file() and sha256(path) == expected, f"artifact SHA256 mismatch: {record['path']}")
    return path


def read_npz(base, record):
    path = pinned_path(base, record)
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key].copy() for key in archive.files}


def validate_subject(data, training_ids, expected_labels, repeats):
    x = array(data["x"], "x", 2)
    labels = stimulus_ids(data["labels"], "labels")
    trials = identifiers(data["trial_ids"], "trial_ids")
    voxels = identifiers(data["voxel_ids"], "voxel_ids")
    require(len(labels) == len(trials) == len(x), "trial identity/label count mismatch")
    require(len(voxels) == x.shape[1], "voxel identity count mismatch")
    require(set(labels) == set(expected_labels), "complete held-out stimulus roster required")
    require(all(np.count_nonzero(labels == label) == repeats for label in expected_labels), "incorrect repeat count")
    train = stimulus_ids(training_ids, "training stimulus IDs", unique=True)
    require(set(train).isdisjoint(labels), "train/test stimulus leakage")
    rois = {}
    for roi in ROIS:
        idx = np.asarray(data[f"roi_{roi}"])
        require(idx.ndim == 1 and idx.dtype.kind in "iu" and idx.dtype.kind != "b", "ROI indices must be integer vectors")
        require(len(idx) >= 2 and len(set(idx.tolist())) == len(idx), f"{roi}: at least two unique voxels required")
        require((idx >= 0).all() and (idx < x.shape[1]).all(), "ROI index outside VC")
        require(np.all(idx[:-1] < idx[1:]), "ROI order must preserve ascending BData columns")
        rois[roi] = idx
    require(np.array_equal(rois["VC"], np.arange(x.shape[1])), "VC must contain every selected voxel in order")
    return {"x": x, "labels": labels, "trial_ids": trials, "voxel_ids": voxels, "rois": rois, "train_ids": train}


def norm_vectors(model, source_voxels, target_voxels):
    result = {}
    for name, size in (("x_mean", source_voxels), ("x_norm", source_voxels), ("y_mean", target_voxels), ("y_norm", target_voxels)):
        value = array(model[name], name)
        require(value.shape in ((size,), (1, size)), f"{name}: wrong voxel dimension")
        result[name] = value.reshape(-1)
        if name.endswith("norm"):
            require((result[name] > 0).all(), f"{name}: nonpositive training scale")
    return result


def predict(model, x, method, source_voxel_ids, target_voxel_ids):
    """Return target-normalized trial predictions using the pinned authors' topology.

    Exported normalization is used unchanged. No test-derived fitting/normalization.
    Content weights follow PyTorch Linear (out,in), InstanceNorm1d eps=1e-5,
    no affine/running statistics, LeakyReLU slope=.2, three Linear layers.
    """
    require(method in METHODS, "unknown conversion method")
    require(identifiers(model["source_voxel_ids"], "model source voxels") == list(source_voxel_ids), "source model voxel identity/order mismatch")
    require(identifiers(model["target_voxel_ids"], "model target voxels") == list(target_voxel_ids), "target model voxel identity/order mismatch")
    norms = norm_vectors(model, len(source_voxel_ids), len(target_voxel_ids))
    z = (array(x, "source test", 2) - norms["x_mean"]) / norms["x_norm"]
    require(z.shape[1] == len(source_voxel_ids), "source dimension mismatch")
    if method == "brain_loss":
        matrix = array(model["M"], "brain-loss M", 2)
        require(matrix.shape == (z.shape[1] + 1, len(target_voxel_ids)), "brain-loss matrix dimensions")
        z = np.column_stack([z, np.ones(len(z))]) @ matrix
    else:
        hidden = z.shape[1] // 2
        require(hidden >= 2, "InstanceNorm requires at least two hidden positions")
        sizes = ((z.shape[1], hidden), (hidden, hidden), (hidden, len(target_voxel_ids)))
        for layer, (n_in, n_out) in enumerate(sizes):
            w = array(model[f"W{layer}"], f"W{layer}", 2)
            b = array(model[f"b{layer}"], f"b{layer}", 1)
            require(w.shape == (n_out, n_in) and b.shape == (n_out,), "content-loss layer dimensions")
            z = z @ w.T + b
            if layer < 2:
                centered = z - z.mean(axis=1, keepdims=True)
                z = centered / np.sqrt(np.mean(centered ** 2, axis=1, keepdims=True) + 1e-5)
                z = np.where(z >= 0, z, .2 * z)
    require(np.isfinite(z).all(), "nonfinite model prediction")
    return z, norms


def cross_repeat_correlation(left, right):
    """Arithmetic mean of every pair of row Pearson correlations.

    Undefined constant rows stay undefined; they are never silently replaced by zero.
    """
    left, right = array(left, "left", 2), array(right, "right", 2)
    require(left.shape[1] == right.shape[1] and left.shape[1] >= 2, "Pearson coordinate mismatch")
    lc, rc = left - left.mean(axis=1, keepdims=True), right - right.mean(axis=1, keepdims=True)
    ln, rn = np.linalg.norm(lc, axis=1), np.linalg.norm(rc, axis=1)
    if np.any(ln == 0) or np.any(rn == 0):
        return None
    correlations = (lc / ln[:, None]) @ (rc / rn[:, None]).T
    return float(np.clip(correlations, -1, 1).mean())


def score_pair(prediction, source, target, norms, labels, source_id, target_id, method):
    """Source-faithful all-repeat pattern and profile rows, preserving feature IDs."""
    require(prediction.shape == (len(source["x"]), len(target["voxel_ids"])), "prediction dimensions")
    truth = (target["x"] - norms["y_mean"]) / norms["y_norm"]
    predicted_groups = np.stack([prediction[source["labels"] == label] for label in labels])
    truth_groups = np.stack([truth[target["labels"] == label] for label in labels])
    # Shape image x repeat x target-VC voxel, within-image BData row order retained.
    rows = []
    for roi, indices in target["rois"].items():
        for image_number, label in enumerate(labels):
            value = cross_repeat_correlation(truth_groups[image_number][:, indices], predicted_groups[image_number][:, indices])
            rows.append({"source": source_id, "target": target_id, "method": method, "roi": roi, "axis": "pattern", "feature": float(label), "raw_r": value})
        for local_index, global_index in enumerate(indices):
            value = cross_repeat_correlation(truth_groups[:, :, global_index].T, predicted_groups[:, :, global_index].T)
            rows.append({"source": source_id, "target": target_id, "method": method, "roi": roi, "axis": "profile", "feature": local_index, "voxel_id": target["voxel_ids"][global_index], "raw_r": value})
    return rows


def load_ceiling_tables(base, definitions):
    """Read exact pinned author CSV interfaces; fail on unmatched/duplicate joins."""
    result = {}
    require(len(definitions) == 2 and {x["axis"] for x in definitions} == {"pattern", "profile"}, "both ceiling axes required")
    for definition in definitions:
        axis = definition["axis"]
        feature_column = "Image index" if axis == "pattern" else "Vox_idx"
        tables = []
        for kind, column in (("ceiling_file", "Correlation"), ("threshold_file", "Threshold 1")):
            with pinned_path(base, definition[kind]).open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            table = {}
            for row in rows:
                subject = row["Subject"].replace("-", "")
                require(subject in SUBJECTS and row["ROI"] in ROIS, "unknown ceiling subject/ROI")
                value = float(row[feature_column])
                if axis == "profile":
                    require(value.is_integer() and value >= 0, "invalid ROI-local voxel index")
                    value = int(value)
                key = (subject, row["ROI"], axis, value)
                require(key not in table, "duplicate ceiling/threshold key")
                number = float(row[column])
                require(np.isfinite(number) and -1 <= number <= 1, "invalid ceiling/threshold correlation")
                table[key] = number
            tables.append(table)
        require(set(tables[0]) == set(tables[1]), "ceiling/threshold coverage mismatch")
        for key, ceiling in tables[0].items():
            result[key] = (ceiling, tables[1][key])
    return result


def apply_ceilings(rows, ceilings):
    expected = {(r["target"], r["roi"], r["axis"], r["feature"]) for r in rows}
    require(set(ceilings) == expected, "complete exact target/ROI/feature ceiling coverage required")
    for row in rows:
        ceiling, threshold = ceilings[(row["target"], row["roi"], row["axis"], row["feature"])]
        row.update(ceiling=ceiling, threshold=threshold, eligible=ceiling > threshold)
        row["normalized_r"] = None
        if row["eligible"]:
            require(ceiling > 0, "eligible ceiling must be positive; do not impute invalid division")
            if row["raw_r"] is not None:
                row["normalized_r"] = float(np.clip(row["raw_r"] / ceiling, -1, 1))


def source_pair_bootstrap(values, iterations=1000):
    """Exact plot_figure sampling mechanism; descriptive source replication only.

    This samples accepted nonself source-target pairs, not five independent subjects.
    Each group resets RandomState(42), matching the published figure script.
    """
    rng = np.random.RandomState(42)
    samples = []
    for _ in range(iterations):
        sample = []
        while len(sample) < 20:
            source, target = rng.choice(SUBJECTS, 1)[0], rng.choice(SUBJECTS, 1)[0]
            if source != target:
                sample.append(values[(source, target)])
        samples.append(np.mean(sample))
    return {"bootstrap_mean": float(np.mean(samples)), "percentile_2_5": float(np.percentile(samples, 2.5)), "percentile_97_5": float(np.percentile(samples, 97.5)), "replicates": iterations, "seed": 42, "unit": "accepted_nonself_pair_draw_not_independent_subject"}


def aggregate(rows, normalized=False, bootstrap=False):
    key = "normalized_r" if normalized else "raw_r"
    grouped = {}
    for row in rows:
        group = (row["source"], row["target"], row["roi"], row["axis"], row["method"])
        grouped.setdefault(group, []).append(row)
    pair_rows = []
    for group, members in grouped.items():
        eligible = [r for r in members if not normalized or r["eligible"]]
        defined = [r[key] for r in eligible if r[key] is not None]
        complete = bool(eligible) and len(defined) == len(eligible)
        pair_rows.append(dict(zip(("source", "target", "roi", "axis", "method"), group), mean_r=float(np.mean(defined)) if complete else None, eligible_count=len(eligible), total_count=len(members), undefined_count=len(eligible) - len(defined)))
    summaries = []
    for roi, axis in itertools.product(ROIS, ("pattern", "profile")):
        method_values = {}
        for method in METHODS:
            selected = [r for r in pair_rows if (r["roi"], r["axis"], r["method"]) == (roi, axis, method)]
            require(len(selected) == 20, "incomplete pair aggregate")
            values = {(r["source"], r["target"]): r["mean_r"] for r in selected}
            method_values[method] = values
            valid = all(x is not None for x in values.values())
            summary = {"roi": roi, "axis": axis, "method": method, "observed_pair_mean": float(np.mean(list(values.values()))) if valid else None, "complete_pairs": sum(x is not None for x in values.values()), "expected_pairs": 20}
            if bootstrap and valid:
                summary["source_bootstrap"] = source_pair_bootstrap(values)
            summaries.append(summary)
        differences = {pair: method_values["content_loss"][pair] - method_values["brain_loss"][pair] for pair in method_values["content_loss"] if method_values["content_loss"][pair] is not None and method_values["brain_loss"][pair] is not None}
        summary = {"roi": roi, "axis": axis, "method": "content_minus_brain", "observed_pair_mean": float(np.mean(list(differences.values()))) if len(differences) == 20 else None, "complete_pairs": len(differences), "expected_pairs": 20}
        if len(differences) == 20:
            summary["leave_one_subject_out_means"] = {subject: float(np.mean([value for (src, trg), value in differences.items() if subject not in (src, trg)])) for subject in SUBJECTS}
            summary["leave_one_subject_out_status"] = "prospective_descriptive_sensitivity_not_improvement_inference"
        summaries.append(summary)
    return {"pair_rows": pair_rows, "summaries": summaries}


def evaluate(manifest_path, *, bootstrap=False):
    started = time.perf_counter()
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text())
    require(manifest.get("schema_version") == 1 and manifest.get("task_id") == TASK_ID, "wrong manifest identity")
    require(manifest.get("source_commit") == SOURCE_COMMIT, "wrong official source revision")
    require(manifest.get("population") in ("public_deeprecon", "generated_engineering_control"), "declare population")
    labels = stimulus_ids(manifest["stimulus_ids"], "frozen stimulus roster", unique=True)
    labels = np.sort(labels)
    repeats = manifest["repeat_count"]
    require(type(repeats) is int and repeats >= 2 and len(labels) >= 2, "invalid image/repeat count")
    if manifest["population"] == "public_deeprecon":
        require(repeats == 24 and len(labels) == 50, "source NaturalImageTest requires 50 images x 24 trials")
    require(manifest.get("training_regime") == "shared_stimulus_fig2", "nonshared-category experiments are outside this Fig2 evaluator")
    records = manifest["subjects"]
    require(len(records) == 5 and {r["id"] for r in records} == set(SUBJECTS), "exact five-subject roster required")
    subjects = {r["id"]: validate_subject(read_npz(manifest_path.parent, r["file"]), r["training_stimulus_ids"], labels, repeats) for r in records}
    training_sets = [set(subjects[subject]["train_ids"]) for subject in SUBJECTS]
    require(all(values == training_sets[0] for values in training_sets), "shared Fig2 training stimulus roster must match across subjects")
    if manifest["population"] == "public_deeprecon":
        require(len(training_sets[0]) == 1200 and all(r.get("training_repeat_count") == 5 for r in records), "source training requires declared 1200 images x 5 trials; native receipt still held")
        require(np.all(labels == np.floor(labels)), "public image indices must be integer-valued")
    model_records = manifest["models"]
    expected = set(itertools.product(itertools.permutations(SUBJECTS, 2), METHODS))
    actual = [((r["source"], r["target"]), r["method"]) for r in model_records]
    require(len(actual) == len(expected) and set(actual) == expected, "exact 20 directed pairs x two methods required")
    rows = []
    for record in model_records:
        source_id, target_id, method = record["source"], record["target"], record["method"]
        source, target = subjects[source_id], subjects[target_id]
        model = read_npz(manifest_path.parent, record["file"])
        for side, subject in (("source", source), ("target", target)):
            used = stimulus_ids(record[f"{side}_fit_stimulus_ids"], f"{side} fit stimuli", unique=True)
            require(set(used) == set(subject["train_ids"]), "model fit-stimulus roster mismatch; decoder training included")
        prediction, norms = predict(model, source["x"], method, source["voxel_ids"], target["voxel_ids"])
        rows.extend(score_pair(prediction, source, target, norms, labels, source_id, target_id, method))
    result = {"task_id": TASK_ID, "source_commit": SOURCE_COMMIT, "population": manifest["population"], "scientific_qualification": "unknown", "manifest_sha256": sha256(manifest_path), "source_pairs": 20, "methods": list(METHODS), "rois": list(ROIS), "images": len(labels), "repeats": repeats, "raw": aggregate(rows), "normalized": None, "rows": rows}
    if manifest.get("noise_ceilings") is not None:
        ceilings = load_ceiling_tables(manifest_path.parent, manifest["noise_ceilings"])
        apply_ceilings(rows, ceilings)
        result["normalized"] = aggregate(rows, normalized=True, bootstrap=bootstrap)
        result["normalized_stage"] = "computed_from_supplied_pinned_tables_authentic_identity_unqualified"
    else:
        result["normalized_stage"] = "held_missing_source_noise_ceiling_and_threshold_tables"
    result["holds"] = ["No authentic data/model/native execution or reference output/tolerance qualification.", "Normalization/feature/decoder asset lineage and rights need independent verification; hashes establish local file identity only.", "Prepared-array model exports require native parity checks, including PyTorch float32 and BData selection.",
                     "Training identity/cardinality declarations do not verify actual full-6000 fitting population or repetition lineage.", "Published inputs are exposed development; protected improvement panel and budgets remain unfrozen.", "Source pair bootstrap is not independent-subject improvement inference.", "No expected positive content-minus-brain neural-correlation advantage is asserted."]
    result["resources"] = {"wall_seconds": time.perf_counter() - started, "kind": "local_evaluator_observation_not_native_campaign_envelope"}
    return result


def prepare_bdata(input_path, expected_sha256, output_path):
    """Trusted, hash-bound native adapter. Requires an already-installed bdpy."""
    require(sha256(input_path) == expected_sha256, "native H5 SHA256 mismatch")
    try:
        import bdpy
    except ImportError as error:
        raise ContractError("bdpy unavailable; native adapter remains unverified; no installation performed") from error
    data = bdpy.BData(str(input_path))
    x, base_mask = data.select("ROI_VC", return_index=True)
    global_columns = np.flatnonzero(base_mask)
    mapping = {int(value): i for i, value in enumerate(global_columns)}
    output = {"x": x, "labels": data.select("image_index").reshape(-1), "trial_ids": np.array([f"row:{i}" for i in range(len(x))]), "voxel_ids": np.array([f"bdata-column:{i}" for i in global_columns]), "native_sha256": np.array(expected_sha256)}
    for roi in ROIS:
        native_key = "ROI_hV4" if roi == "V4" else f"ROI_{roi}"
        _, selected = data.select(native_key, return_index=True)
        columns = np.flatnonzero(selected)
        require(all(int(value) in mapping for value in columns), "native ROI has voxel outside VC")
        output[f"roi_{roi}"] = np.array([mapping[int(value)] for value in columns], dtype=np.int64)
    np.savez(output_path, **output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    score = sub.add_parser("evaluate")
    score.add_argument("manifest")
    score.add_argument("--output", required=True)
    score.add_argument("--source-bootstrap", action="store_true", help="replicate source pair bootstrap, not independent-subject inference")
    native = sub.add_parser("prepare-bdata")
    native.add_argument("input")
    native.add_argument("--sha256", required=True)
    native.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "evaluate":
        result = evaluate(args.manifest, bootstrap=args.source_bootstrap)
        Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    else:
        prepare_bdata(args.input, args.sha256, args.output)


if __name__ == "__main__":
    main()
