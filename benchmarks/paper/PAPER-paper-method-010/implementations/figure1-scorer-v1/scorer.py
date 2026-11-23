"""Figure 1 simulation endpoints; no generation, fitting, or paper-win decision.

Independently implemented from the documented formulas in the pinned Rastermap
paper/metrics.py. NumPy's default argsort is intentional, including tied values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

MODULE_NAMES = ("tuning", "sustained", "sequence 1", "sequence 2", "power-law")
MODULE_COUNTS = (1000, 1000, 1000, 1000, 2000)
METRICS = ("contamination", "correct_triplets")
SOURCE_REVISION = "b37644ea52c4cd81f143a9c2cec90286ffd61c49"


def _vector(value, name):
    a = np.asarray(value)
    if a.ndim == 2 and a.shape[1] == 1:
        a = a[:, 0]
    if a.ndim != 1 or a.dtype.kind not in "fiu" or not np.isfinite(a).all():
        raise ValueError(f"{name} must be a finite real vector or N-by-1 array")
    return a


def _inputs(xi_all, embedding):
    gt = _vector(xi_all, "xi_all")
    emb = _vector(embedding, "embedding")
    if gt.shape != emb.shape or gt.size == 0 or (gt < 0).any():
        raise ValueError("ground truth and embedding must have matching nonempty rows")
    n_modules = int(np.ceil(gt.max()))
    labels = np.floor(gt).astype(int)
    if n_modules < 1 or labels.max() >= n_modules:
        raise ValueError("ground truth must occupy half-open module intervals")
    counts = np.bincount(labels, minlength=n_modules)
    if (counts < 3).any():
        raise ValueError("every module must contain at least three neurons")
    return gt, emb, labels, counts


def triplet_order(xi_all, embedding, rng):
    """Source reversal-invariant sampled order, with 10*n draws per module."""
    gt, emb, labels, counts = _inputs(xi_all, embedding)
    result = np.empty(len(counts), dtype=float)
    for module, count in enumerate(counts):
        member = labels == module
        # Source computes local truth as gt[member]-module before sorting.
        true_order = (gt[member] - module).argsort()
        embedded_order = emb[member].argsort()
        rank = np.empty(count, dtype=np.intp)
        rank[embedded_order] = np.arange(count)
        correct = 0
        for _ in range(int(count) * 10):
            selected_ranks = np.sort(rng.choice(count, size=3, replace=False))
            a, b, c = rank[true_order[selected_ranks]]
            correct += int((a < b < c) or (a > b > c))
        result[module] = correct / (int(count) * 10)
    return result


def embedding_contamination(xi_all, embedding, rng):
    """Source interval semantics; return score and actual qualifying pair count.

    A pair qualifies only when its embedding-rank distance exceeds five. The
    source slice is [lower+1:upper-1], NOT [lower+1:upper]. No replacement draws
    are made for rejected pairs. Zero accepted pairs produces NaN, never zero.
    """
    _, emb, labels, counts = _inputs(xi_all, embedding)
    order = emb.argsort()
    rank = np.empty(len(order), dtype=np.intp)
    rank[order] = np.arange(len(order))
    result = np.empty(len(counts), dtype=float)
    accepted = np.zeros(len(counts), dtype=np.int64)
    for module, count in enumerate(counts):
        members = np.flatnonzero(labels == module)
        in_module = labels == module
        total = 0.0
        for _ in range(int(count) * 10):
            pair = members[rng.choice(count, size=2, replace=False)]
            lower, upper = sorted(rank[pair])
            if upper - lower > 5:
                total += 1 - in_module[order[lower + 1:upper - 1]].mean()
                accepted[module] += 1
        result[module] = total / accepted[module] if accepted[module] else np.nan
    return result, accepted


def source_benchmarks(xi_all, embeddings, rng):
    """Mirror source benchmarks draw order, including its float32 random control.

    Returns [metric, method including random, module] and qualifying pair counts.
    With identical inputs, initial RandomState and NumPy this follows the source
    function's stream. The original post-fitting RNG state remains unrecovered.
    """
    if not isinstance(rng, np.random.RandomState):
        raise ValueError("source sampling requires numpy.random.RandomState")
    embeddings = list(embeddings)
    if not embeddings:
        raise ValueError("at least one embedding is required")
    validated = [_inputs(xi_all, e)[1] for e in embeddings]
    random_control = rng.rand(len(validated[0]), 1).astype("float32")
    all_embeddings = validated + [random_control]
    contamination, counts = zip(*[
        embedding_contamination(xi_all, e, rng) for e in all_embeddings
    ])
    triplets = [triplet_order(xi_all, e, rng) for e in all_embeddings]
    return np.asarray([contamination, triplets]), np.asarray(counts)


def validate_original_population(xi_all):
    gt = _vector(xi_all, "xi_all")
    # Bound the fixed population before _inputs allocates a bincount array
    # from the largest submitted module coordinate.
    if gt.shape != (6000,) or (gt < 0).any() or (gt >= len(MODULE_COUNTS)).any():
        raise ValueError("Figure 1 requires 6000 neurons in module intervals [0,5)")
    _, _, _, counts = _inputs(gt, gt)
    # Generator groups and source metric labels differ at exact boundaries:
    # sustained xi = 1 - tpref/100 can equal 1, hence xi_all == 2 after
    # its module offset. The source metric still uses floor(xi_all), so these
    # rows belong to metric module 2. Other shared endpoints can arise from
    # sequence inversion or floating-point addition. Permit only count shifts
    # supported by exact shared endpoints, never an arbitrary count tolerance.
    if counts[0] != MODULE_COUNTS[0] or (gt == 1).any():
        raise ValueError("Figure 1 requires 1000 tuning rows and no coordinate at 1")
    for boundary, prefix in ((2, 2000), (3, 3000), (4, 4000)):
        if not np.count_nonzero(gt < boundary) <= prefix <= np.count_nonzero(gt <= boundary):
            raise ValueError("Figure 1 nominal group counts must be recoverable at exact module boundaries")
    return gt


def summarize_panel(scores, realization_ids):
    """Percentages and source SEM; keep every metric/method/module separately."""
    ids = list(realization_ids)
    if any(type(x) is not int for x in ids) or ids != list(range(10)):
        raise ValueError("all original realization IDs 0..9 in order are required")
    a = np.asarray(scores)
    if a.ndim != 4 or a.shape[0:2] != (10, 2) or a.shape[3] != 5 or a.shape[2] < 1:
        raise ValueError("scores must have shape [10,2,methods,5]")
    if a.dtype.kind not in "fiu" or not np.isfinite(a).all() or ((a < 0) | (a > 1)).any():
        raise ValueError("scores must be finite fractions in [0,1]")
    return {
        "per_realization_percent": (100 * a).tolist(),
        "mean_percent": (100 * a.mean(axis=0)).tolist(),
        "sem_percent": (100 * a.std(axis=0, ddof=0) / np.sqrt(9)).tolist(),
        "sem_definition": "100 * population_std_across_10_realizations / sqrt(9)",
    }


def _digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _load_artifact(record, keys):
    if not isinstance(record, dict) or set(record) != {"path", "sha256"} or not _digest(record["sha256"]):
        raise ValueError("artifact requires exactly path and lowercase sha256")
    path = Path(record["path"])
    if not path.is_absolute():
        raise ValueError("operator artifact paths must be absolute")
    # Only compact target/embedding packets belong here; never load the activity
    # matrix. Hash and parse the same bytes to avoid a path replacement race.
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("target/embedding packet exceeds 1 MiB")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != record["sha256"]:
        raise ValueError("artifact SHA-256 mismatch")
    import io
    import zipfile
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if sum(x.file_size for x in archive.infolist()) > 1024 * 1024:
            raise ValueError("expanded packet exceeds 1 MiB")
    with np.load(io.BytesIO(payload), allow_pickle=False) as data:
        if set(data.files) != set(keys) or len(data.files) != len(keys):
            raise ValueError("packet has missing, duplicate or unexpected fields")
        arrays = {key: data[key] for key in keys}
    ids = arrays["neuron_id"]
    if ids.shape != (6000,) or ids.dtype.kind not in "iu" or not np.array_equal(ids, np.arange(6000)):
        raise ValueError("neuron_id must be shuffled-activity row indices 0..5999 in order")
    return arrays


def evaluate_request(request):
    """Operator-only paired scoring; never execute or expose targets to candidates.

    Each method receives a fresh, identical per-realization legacy RNG stream.
    This is an explicit reproducible policy, not the unrecovered original RNG
    after fitting all seven methods. It preserves source metric/draw semantics.
    """
    if set(request) != {"schema", "method_names", "realizations"} or request["schema"] != "rastermap-figure1-score/v1":
        raise ValueError("invalid request schema or fields")
    methods = request["method_names"]
    if not isinstance(methods, list) or len(methods) < 2 or not all(isinstance(x, str) for x in methods) or len(set(methods)) != len(methods):
        raise ValueError("provide distinct author and candidate method names")
    if methods[0] != "source_rastermap" or not all(isinstance(x, str) and x and x.isascii() and x.replace("_", "").replace("-", "").isalnum() for x in methods):
        raise ValueError("first method must be source_rastermap; use ASCII method identifiers")
    rows = request["realizations"]
    if (not isinstance(rows, list) or len(rows) != 10 or
            not all(isinstance(r, dict) and type(r.get("id")) is int for r in rows) or
            [r.get("id") for r in rows] != list(range(10))):
        raise ValueError("provide original realizations 0..9 exactly once in order")
    # Authenticate and validate the complete roster before any metric work.
    prepared = []
    for row in rows:
        if set(row) != {"id", "metric_seed", "activity_sha256", "target", "embeddings"}:
            raise ValueError("invalid realization fields")
        seed = row["metric_seed"]
        if type(seed) is not int or not 0 <= seed < 2**32 or not _digest(row["activity_sha256"]):
            raise ValueError("invalid metric seed or activity identity")
        if set(row["embeddings"]) != set(methods):
            raise ValueError("every method must cover every realization")
        gt = validate_original_population(_load_artifact(row["target"], {"xi_all", "neuron_id"})["xi_all"])
        embeddings = [_inputs(gt, _load_artifact(row["embeddings"][name], {"embedding", "neuron_id"})["embedding"])[1] for name in methods]
        prepared.append((gt, embeddings, seed))
    all_scores, all_counts, controls, identities = [], [], [], []
    for row, (gt, embeddings, seed) in zip(rows, prepared):
        method_scores, method_counts, method_controls = [], [], []
        for emb in embeddings:
            score, count = source_benchmarks(gt, [emb], np.random.RandomState(seed))
            method_scores.append(score[:, 0])
            method_counts.append(count[0])
            method_controls.append(score[:, 1])
        all_scores.append(np.stack(method_scores, axis=1))
        all_counts.append(method_counts)
        controls.append(np.stack(method_controls, axis=1))
        identities.append({"id": row["id"], "metric_seed": seed, "activity_sha256": row["activity_sha256"],
                           "target_sha256": row["target"]["sha256"],
                           "metric_module_counts": np.bincount(np.floor(gt).astype(int), minlength=5).tolist(),
                           "embedding_sha256": {name: row["embeddings"][name]["sha256"] for name in methods}})
    scores = np.asarray(all_scores)
    report = summarize_panel(scores, range(10))
    report.update({"schema": "rastermap-figure1-report/v1", "source_revision": SOURCE_REVISION,
                   "numpy_version": np.__version__, "metric_order": list(METRICS),
                   "module_order": list(MODULE_NAMES), "method_order": methods,
                   "realizations": identities, "qualifying_pairs": all_counts,
                   "random_controls": summarize_panel(np.asarray(controls), range(10)),
                   "sampling_policy": "paired-method-independent-RandomState; source-benchmarks-one-method-plus-random",
                   "qualification": "metric_software_component_only",
                   "published_score_reproduced": False, "paper_improvement_established": False})
    # Positive means favorable for both endpoints; do not collapse modules or
    # confuse descriptive paired differences with a superiority decision.
    difference = 100 * (scores[:, :, 1:] - scores[:, :, :1])
    difference[:, 0] *= -1
    report["paired_favorable_difference_percentage_points"] = difference.tolist()
    report["paired_favorable_mean_percentage_points"] = difference.mean(axis=0).tolist()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = evaluate_request(json.loads(args.request.read_text()))
    # Default=str would silently hide undefined scores; fail on them instead.
    encoded = json.dumps(report, indent=2, allow_nan=False, default=lambda x: x.tolist()) + "\n"
    with args.output.open("x") as handle:
        handle.write(encoded)


if __name__ == "__main__":
    main()
