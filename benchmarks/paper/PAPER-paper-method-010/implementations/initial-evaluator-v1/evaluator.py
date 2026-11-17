"""Prospective, source-grounded Rastermap artifact evaluation; no native fitting.

Only NumPy and the Python standard library are required. The canonical task and
the primary paper do not freeze an empirical grading target. These measurements
therefore never produce a reproduction pass or scientific qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

TASK_ID = "PAPER-paper-method-010"
CONTRACT_SHA256 = "8764f79a3610f0323b82f342d2bfde9a98b5551241604d44af8684c1a97932bd"
SOURCE_REVISION = "b37644ea52c4cd81f143a9c2cec90286ffd61c49"
POPULATIONS = {"hippocampus": 137, "mouse": 34086}
HOLDS = [
    "No authentic empirical data or native Rastermap/reference run validated by this package.",
    "Prospective endpoints and split are not published numeric targets or tolerance qualification.",
    "Both hippocampal and mouse recordings, source preprocessing reconciliation and exact acquired data pins remain required.",
    "Candidate isolation, protected reference separation, equal realized resources and provenance require independent verification.",
    "OSF data reuse/redistribution and other paper/stimulus rights remain unresolved; public access is not permission.",
    "Neuron perturbations are robustness checks, not independent biological replication.",
    "Baseline competence, native dependencies, empirical resource measurement and full scientific review remain open.",
    "Native Rastermap may exclude zero-variance neurons; full-population finite embeddings require explicit scientific reconciliation, never fabricated coordinates.",
    "Native itrain alone does not isolate all preprocessing/time-lag operations; fitting must use a truly training-only matrix or a verified adapter.",
]


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def _matrix(value: Any, name: str, allow_nan: bool = False) -> np.ndarray:
    a = np.asarray(value, dtype=np.float64)
    if a.ndim != 2 or min(a.shape) == 0:
        raise ValueError(f"{name} must be a nonempty 2D numeric array")
    if np.isinf(a).any() or (not allow_nan and not np.isfinite(a).all()):
        raise ValueError(f"{name} contains invalid nonfinite values")
    return a


def _ids(values: Any, name: str) -> list[str]:
    if not isinstance(values, (list, tuple, np.ndarray)):
        raise ValueError(f"{name} must be an array of unique nonempty strings")
    ids = list(values)
    if any(not isinstance(x, (str, np.str_)) or not str(x) for x in ids):
        raise ValueError(f"{name} must contain nonempty strings")
    ids = [str(x) for x in ids]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{name} contains duplicate IDs")
    return ids


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def index_sha256(indices: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(indices, dtype="<i8").tobytes()).hexdigest()


def temporal_split(n_time: int, purge_samples: int) -> dict[str, np.ndarray]:
    """Prospective 60/20/20 chronological split; purge both sides of boundaries.

    Validation may be used for tuning; final fitting remains train-only. Samples
    in the embargo are reported, not silently counted as evaluated observations.
    """
    n_time = _integer(n_time, "n_time", 10)
    gap = _integer(purge_samples, "purge_samples")
    a, b = (3 * n_time) // 5, (4 * n_time) // 5
    split = {"train": np.arange(0, a - gap),
             "validation": np.arange(a + gap, b - gap),
             "test": np.arange(b + gap, n_time)}
    if any(len(x) < 3 for x in split.values()):
        raise ValueError("each split needs at least three samples after the purge")
    used = np.concatenate(list(split.values()))
    if len(np.unique(used)) != len(used) or used.min() < 0 or used.max() >= n_time:
        raise ValueError("invalid temporal split")
    split["embargo"] = np.setdiff1d(np.arange(n_time), used)
    return split


def train_standardize(activity: Any, train: np.ndarray) -> tuple[np.ndarray, dict]:
    """Retain every neuron; fit mean/scale on training samples only (ddof=0)."""
    x = _matrix(activity, "activity")
    train = np.asarray(train)
    if train.ndim != 1 or not np.issubdtype(train.dtype, np.integer) or len(train) < 2:
        raise ValueError("training indices must be an integer vector of length >= 2")
    if len(np.unique(train)) != len(train) or train.min() < 0 or train.max() >= x.shape[1]:
        raise ValueError("invalid training indices")
    mean = x[:, train].mean(axis=1, keepdims=True)
    scale = x[:, train].std(axis=1, keepdims=True)
    constant = scale[:, 0] == 0
    scale[constant] = 1.0
    transformed = (x - mean) / scale
    if not np.isfinite(transformed).all():
        raise ValueError("standardization overflow")
    return transformed, {"mean": mean[:, 0].tolist(), "scale": scale[:, 0].tolist(),
                         "training_constant_neuron_count": int(constant.sum())}


def knn_indices(features: Any, k: int, row_block: int = 64) -> np.ndarray:
    """Exact nonself squared-Euclidean neighbors, full population, bounded rows.

    Input row order is the canonical sorted neuron-ID order. Equal distances are
    resolved by that order. This differs explicitly from upstream's random
    maximum-2000-neuron subset. Memory for distances is O(row_block * N).
    """
    x = _matrix(features, "features")
    k = _integer(k, "k", 1)
    block = _integer(row_block, "row_block", 1)
    n = len(x)
    if k >= n:
        raise ValueError("k must be smaller than the number of neurons")
    # Translation must not change neighborhoods. Center before the Gram formula;
    # use direct differences for scalar embeddings (no catastrophic cancellation).
    x = x - x.mean(axis=0, keepdims=True)
    norms = np.einsum("ij,ij->i", x, x)
    result = np.empty((n, k), dtype=np.int64)
    for start in range(0, n, block):
        stop = min(n, start + block)
        if x.shape[1] == 1:
            d = (x[start:stop, 0, None] - x[None, :, 0]) ** 2
        else:
            d = norms[start:stop, None] + norms[None, :] - 2 * (x[start:stop] @ x.T)
        if not np.isfinite(d).all():
            raise ValueError("distance computation overflow")
        np.maximum(d, 0, out=d)
        d[np.arange(stop - start), np.arange(start, stop)] = np.inf
        result[start:stop] = np.argsort(d, axis=1, kind="stable")[:, :k]
    return result


def neighborhood_retention(neural_neighbors: Any, embedding_neighbors: Any) -> float:
    a, b = np.asarray(neural_neighbors), np.asarray(embedding_neighbors)
    if a.ndim != 2 or a.shape != b.shape or min(a.shape) == 0:
        raise ValueError("neighbor arrays must have the same nonempty 2D shape")
    return float(sum(len(set(u) & set(v)) for u, v in zip(a, b)) / a.size)


def _embedding(artifact: dict, neuron_ids: list[str]) -> np.ndarray:
    ids = _ids(artifact.get("neuron_ids"), "artifact neuron_ids")
    if set(ids) != set(neuron_ids):
        raise ValueError("embedding must contain every source neuron exactly once")
    values = np.asarray(artifact.get("embedding"), dtype=np.float64)
    if values.shape not in [(len(ids),), (len(ids), 1)] or not np.isfinite(values).all():
        raise ValueError("embedding must contain one finite coordinate per neuron")
    mapping = dict(zip(ids, values.reshape(-1)))
    return np.array([mapping[x] for x in neuron_ids])


def _superneurons(activity: np.ndarray, embedding: np.ndarray, group_size: int) -> np.ndarray:
    size = _integer(group_size, "group_size", 1)
    # Resolve the arbitrary axis reversal before assigning a shorter last group.
    # Rows are in canonical neuron-ID order; the first distinct pair orients the
    # coordinate, so reversing it yields exactly the same partition (also at ties).
    distinct = np.flatnonzero(embedding != embedding[0])
    if len(distinct) and embedding[distinct[0]] < embedding[0]:
        embedding = -embedding
    order = np.argsort(embedding, kind="stable")
    # Retain the remainder group; upstream plotting bin1d drops it.
    return np.stack([activity[order[i:i + size]].mean(axis=0)
                     for i in range(0, len(order), size)], axis=1)


def behavior_prediction(activity: Any, behavior: Any, embedding: Any,
                        split: dict[str, np.ndarray], group_size: int,
                        alpha: float = 1.0) -> dict:
    """Prospective linear behavior->superneuron prediction; never native NN VE.

    Fit input centering/scaling, target intercept and ridge weights on training
    only. NaN behavior rows are excluded with explicit splitwise accounting.
    Test R² is centered on the test target mean. Constants yield null, not zero.
    """
    x = _matrix(activity, "activity")
    b = _matrix(behavior, "behavior", allow_nan=True)
    if b.shape[0] != x.shape[1]:
        raise ValueError("behavior must be aligned to the neural time axis")
    z = np.asarray(embedding, dtype=float).reshape(-1)
    if len(z) != len(x) or not np.isfinite(z).all():
        raise ValueError("one finite embedding coordinate is required per neuron")
    if isinstance(alpha, bool) or not math.isfinite(alpha) or alpha <= 0:
        raise ValueError("ridge alpha must be finite and positive")
    y = _superneurons(x, z, group_size)
    finite = np.isfinite(b).all(axis=1)
    indices = {name: np.asarray(split[name])[finite[split[name]]]
               for name in ["train", "validation", "test"]}
    if any(len(v) < 3 for v in indices.values()):
        raise ValueError("behavior has fewer than three evaluable rows in a split")
    tr, te = indices["train"], indices["test"]
    mean, scale = b[tr].mean(axis=0), b[tr].std(axis=0)
    scale[scale == 0] = 1.0
    train_x, test_x = (b[tr] - mean) / scale, (b[te] - mean) / scale
    intercept = y[tr].mean(axis=0)
    weights = np.linalg.solve(train_x.T @ train_x + alpha * np.eye(b.shape[1]),
                              train_x.T @ (y[tr] - intercept))
    pred = test_x @ weights + intercept
    residual = np.sum((y[te] - pred) ** 2, axis=0)
    denominator = np.sum((y[te] - y[te].mean(axis=0)) ** 2, axis=0)
    if not np.isfinite(residual).all() or not np.isfinite(denominator).all():
        raise ValueError("behavior regression overflow")
    valid = denominator > 0
    scores = [float(1 - r / d) if d > 0 else None for r, d in zip(residual, denominator)]
    return {"direction": "behavior_to_sorted_superneurons", "metric": "centered_test_r2",
            "per_group_r2": scores,
            "macro_r2": float(np.mean(np.asarray(scores, dtype=float)[valid])) if valid.any() else None,
            "group_sizes": [min(group_size, len(x) - i) for i in range(0, len(x), group_size)],
            "undefined_constant_test_groups": int((~valid).sum()),
            "ridge_alpha": float(alpha),
            "behavior_row_accounting": {name: {"included": len(v), "excluded_nonfinite": len(split[name]) - len(v)}
                                        for name, v in indices.items()}}


def order_stability(reference: dict, perturbation: dict) -> dict:
    """Absolute tie-aware Kendall tau-b on shared neurons; O(N log N).

    Reversal is equivalent. Missing neurons are permitted only for this explicit
    robustness endpoint. It is not an independent-recording confidence interval.
    """
    ref_ids = _ids(reference.get("neuron_ids"), "reference neuron_ids")
    sub_ids = _ids(perturbation.get("neuron_ids"), "perturbation neuron_ids")
    if len(sub_ids) < 3 or not set(sub_ids).issubset(ref_ids):
        raise ValueError("perturbation must have >=3 known source neurons")
    common = sorted(sub_ids)
    ref_map = dict(zip(ref_ids, _embedding(reference, ref_ids)))
    r = np.array([ref_map[x] for x in common])
    p = _embedding(perturbation, common)
    ref_order = np.argsort(r, kind="stable")
    _, ranks, counts_y = np.unique(p, return_inverse=True, return_counts=True)
    _, counts_x = np.unique(r, return_counts=True)
    _, counts_xy = np.unique(np.column_stack((r, p)), axis=0, return_counts=True)
    seq = ranks[ref_order]
    tree = np.zeros(len(counts_y) + 1, dtype=np.int64)
    inversions = 0
    seen = 0
    for count in counts_x:
        group = seq[seen:seen + count]
        # Query a tied-reference group before updating: x ties are neither
        # concordant nor discordant. The prefix query includes y ties.
        for rank in group:
            i, prior_le = int(rank) + 1, 0
            while i:
                prior_le += int(tree[i]); i -= i & -i
            inversions += seen - prior_le
        for rank in group:
            i = int(rank) + 1
            while i < len(tree):
                tree[i] += 1; i += i & -i
        seen += int(count)
    pairs = len(seq) * (len(seq) - 1) // 2
    ties_x = sum(int(c) * (int(c) - 1) // 2 for c in counts_x)
    ties_y = sum(int(c) * (int(c) - 1) // 2 for c in counts_y)
    ties_xy = sum(int(c) * (int(c) - 1) // 2 for c in counts_xy)
    comparable = pairs - ties_x - ties_y + ties_xy
    denominator = math.sqrt((pairs - ties_x) * (pairs - ties_y))
    score = abs((comparable - 2 * inversions) / denominator) if denominator else None
    return {"absolute_kendall_tau_b": score, "comparable_pairs": comparable,
            "reference_tied_pairs": ties_x, "perturbation_tied_pairs": ties_y,
            "shared_neurons": len(seq), "reference_neurons": len(ref_ids),
            "scope": "neuron/time perturbation robustness; not biological replication"}


def _stability_panel(artifact: dict, train: np.ndarray) -> list[dict]:
    panel = artifact.get("perturbations")
    if not isinstance(panel, list) or len(panel) < 2:
        raise ValueError("each method requires repeat-seed and subsampling/missing-time robustness artifacts")
    kinds = {p.get("kind") for p in panel}
    if "repeat_seed" not in kinds or not kinds.intersection({"neuron_subsample", "missing_time"}):
        raise ValueError("stability panel must include a repeat seed and a population/time perturbation")
    results = []
    for p in panel:
        kind = p.get("kind")
        if kind not in {"repeat_seed", "neuron_subsample", "missing_time"}:
            raise ValueError("unknown perturbation kind")
        for field in ["input_sha256", "access_condition", "maximum_fit_lag", "tuning_budget"]:
            if p.get(field) != artifact.get(field):
                raise ValueError(f"perturbation differs in {field}")
        if artifact["access_condition"] == "paper_data_official_code" and p.get("official_code_revision") != SOURCE_REVISION:
            raise ValueError("perturbation must pin the approved official-code snapshot")
        seed = _integer(p.get("seed"), "perturbation seed")
        if kind == "repeat_seed" and seed == artifact["seed"]:
            raise ValueError("repeat-seed control must use a different declared seed")
        fit = np.asarray(p.get("fit_time_indices"))
        if fit.ndim != 1 or not np.issubdtype(fit.dtype, np.integer) or len(fit) < 3:
            raise ValueError("perturbation needs at least three explicit integer fitting time indices")
        if len(np.unique(fit)) != len(fit) or not set(fit).issubset(train):
            raise ValueError("perturbation fitting times must be unique training-only samples")
        if p.get("train_index_sha256") != index_sha256(fit):
            raise ValueError("perturbation fitting-time digest mismatch")
        if kind == "missing_time":
            if len(fit) >= len(train):
                raise ValueError("missing-time control must withhold training time samples")
        elif not np.array_equal(fit, train):
            raise ValueError("non-temporal perturbations must retain the frozen fitting time samples")
        p_ids = _ids(p.get("neuron_ids"), "perturbation neuron_ids")
        if kind == "neuron_subsample":
            if len(p_ids) >= len(artifact["neuron_ids"]):
                raise ValueError("neuron subsampling must remove some training neurons")
        elif set(p_ids) != set(artifact["neuron_ids"]):
            raise ValueError("repeat-seed/missing-time control must retain all source neurons")
        results.append({"kind": kind, **order_stability(artifact, p)})
    return results


def load_source_npz(path: str | Path, role: str, expected_sha256: str) -> dict:
    """Read only source arrays (never pickle) and bridge native clocks explicitly.

    Mouse interpolation is prospective and split-local: it cannot use camera
    observations across a temporal boundary. Exact schema/clock receipt is
    returned; data rights and acquired asset identity still need qualification.
    """
    if role not in POPULATIONS:
        raise ValueError("role must be hippocampus or mouse")
    digest = file_sha256(path)
    if digest != expected_sha256:
        raise ValueError("source file SHA256 does not match operator-declared pin")
    with np.load(path, allow_pickle=False) as data:
        x = _matrix(data["spks"], "spks")
        n_time = x.shape[1]
        result = {"activity": x, "neuron_ids": [f"row:{i:06d}" for i in range(len(x))],
                  "input_sha256": digest, "role": role}
        if role == "hippocampus":
            loc = np.asarray(data["loc_signed"], dtype=float)
            if loc.shape != (n_time,) or np.isinf(loc).any():
                raise ValueError("loc_signed must match neural time, allowing source NaNs")
            result.update(behavior=loc[:, None], timestamps=np.arange(n_time) * 0.2,
                          behavior_names=["loc_signed"],
                          adapter="source signed-position vector; prospective linear position-to-neural endpoint")
        else:
            neural = np.asarray(data["tneural"], dtype=float).reshape(-1)
            camera = np.asarray(data["tcam"], dtype=float).reshape(-1)
            behavior = _matrix(data["beh"], "beh", allow_nan=True)
            run = np.asarray(data["run"], dtype=float).reshape(-1)
            if len(neural) != n_time or len(run) != n_time or len(camera) != len(behavior):
                raise ValueError("mouse spks/run/tneural and beh/tcam clocks disagree")
            for name, times in [("tneural", neural), ("tcam", camera)]:
                if not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
                    raise ValueError(f"{name} must be finite and strictly increasing")
            if np.isinf(run).any():
                raise ValueError("run contains infinity")
            result.update(timestamps=neural, camera_times=camera, camera_behavior=behavior,
                          running=run, adapter="prospective split-local linear camera-to-neural interpolation")
    return result


def _aligned_behavior(record: dict, split: dict) -> np.ndarray:
    if "behavior" in record:
        return _matrix(record["behavior"], "behavior", allow_nan=True)
    camera, neural = np.asarray(record["camera_times"]), np.asarray(record["timestamps"])
    beh = _matrix(record["camera_behavior"], "camera_behavior", allow_nan=True)
    aligned = np.full((len(neural), beh.shape[1] + 1), np.nan)
    aligned[:, -1] = record["running"]
    for name in ["train", "validation", "test"]:
        idx = split[name]
        keep = (camera >= neural[idx[0]]) & (camera <= neural[idx[-1]])
        if keep.sum() < 2:
            continue
        for column in range(beh.shape[1]):
            # np.interp propagates missing endpoint values; no gap-filling across NaNs.
            aligned[idx, column] = np.interp(neural[idx], camera[keep], beh[keep, column],
                                             left=np.nan, right=np.nan)
    return aligned


def evaluate_recording(record: dict, artifacts: list[dict], *, purge_samples: int,
                       maximum_fit_lag: int = 0, neighbor_k: int = 10,
                       engineering: bool = False, row_block: int = 64) -> dict:
    role = record.get("role")
    if role not in POPULATIONS:
        raise ValueError("unknown recording role")
    x = _matrix(record.get("activity"), "activity")
    ids = _ids(record.get("neuron_ids"), "recording neuron_ids")
    if len(ids) != len(x) or (not engineering and len(x) != POPULATIONS[role]):
        raise ValueError("source population is incomplete or has unexpected size")
    times = np.asarray(record.get("timestamps"), dtype=float)
    if times.shape != (x.shape[1],) or not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        raise ValueError("timestamps must match the neural time axis and increase strictly")
    lag = _integer(maximum_fit_lag, "maximum_fit_lag")
    if _integer(purge_samples, "purge_samples") < lag:
        raise ValueError("purge must cover the maximum declared fitting temporal support")
    split = temporal_split(x.shape[1], purge_samples)
    if not isinstance(artifacts, list) or len(artifacts) < 2:
        raise ValueError("candidate and at least one declared baseline are required")
    if sum(a.get("role") == "candidate" for a in artifacts) != 1 or any(a.get("role") not in ["candidate", "baseline"] for a in artifacts):
        raise ValueError("exactly one candidate and at least one baseline are required")
    names = [a.get("name") for a in artifacts]
    if any(not isinstance(n, str) or not n for n in names) or len(set(names)) != len(names):
        raise ValueError("method names must be nonempty and unique")
    input_pin = record.get("input_sha256")
    if not isinstance(input_pin, str) or len(input_pin) != 64 or any(c not in "0123456789abcdef" for c in input_pin):
        raise ValueError("an exact source/input SHA256 receipt is required")
    expected_train = index_sha256(split["train"])
    conditions = []
    for a in artifacts:
        if a.get("input_sha256") != input_pin or a.get("train_index_sha256") != expected_train:
            raise ValueError("method input/training provenance differs from frozen protocol")
        condition = a.get("access_condition")
        if condition not in ["paper_and_data", "paper_data_official_code"]:
            raise ValueError("unknown access condition")
        budget = _integer(a.get("tuning_budget"), "tuning_budget", 1)
        _integer(a.get("seed"), "seed")
        if a.get("maximum_fit_lag") != lag:
            raise ValueError("method temporal support differs from frozen protocol")
        if condition == "paper_data_official_code" and a.get("official_code_revision") != SOURCE_REVISION:
            raise ValueError("official-code condition must pin the approved snapshot")
        conditions.append((condition, budget))
    if len(set(conditions)) != 1:
        raise ValueError("compared methods must have equal declared access and tuning budgets")
    panel_signatures = []
    for a in artifacts:
        panel = a.get("perturbations", [])
        panel_signatures.append(sorted((p.get("kind", ""), p.get("seed", -1),
                                        p.get("train_index_sha256", ""),
                                        tuple(sorted(_ids(p.get("neuron_ids"), "perturbation neuron_ids"))))
                                       for p in panel))
    if any(signature != panel_signatures[0] for signature in panel_signatures[1:]):
        raise ValueError("methods must use the same declared robustness seeds, neuron supports and fitting times")
    # Canonical source IDs make all tie-breaking invariant to incoming row order.
    order = np.argsort(np.array(ids), kind="stable")
    ids = [ids[i] for i in order]
    normalized, scaling = train_standardize(x[order], split["train"])
    neighbors = knn_indices(normalized[:, split["test"]], neighbor_k, row_block)
    behavior = _aligned_behavior(record, split)
    group_size = 50 if role == "mouse" else 5
    results = []
    for a in artifacts:
        z = _embedding(a, ids)
        retained = neighborhood_retention(neighbors, knn_indices(z[:, None], neighbor_k, row_block))
        results.append({"name": a["name"], "role": a["role"], "neighbor_retention": retained,
                        "tied_coordinate_count": len(z) - len(np.unique(z)),
                        "behavior": behavior_prediction(normalized, behavior, z, split, group_size),
                        "stability": _stability_panel(a, split["train"])})
    candidate = next(r for r in results if r["role"] == "candidate")
    comparisons = [{"baseline": r["name"],
                    "neighbor_retention_difference": candidate["neighbor_retention"] - r["neighbor_retention"],
                    "behavior_macro_r2_difference": (candidate["behavior"]["macro_r2"] - r["behavior"]["macro_r2"])
                    if candidate["behavior"]["macro_r2"] is not None and r["behavior"]["macro_r2"] is not None else None}
                   for r in results if r["role"] == "baseline"]
    return {"task_id": TASK_ID, "role": role, "mode": "generated_engineering_control" if engineering else "prospective_empirical_artifact_evaluation",
            "scientifically_qualified": False, "reproduction_pass": None,
            "population": {"supplied": len(x), "source_expected": POPULATIONS[role], "scored": len(x)},
            "input_sha256": input_pin, "train_index_sha256": expected_train,
            "split": {k: {"count": len(v), "indices_sha256": index_sha256(v)} for k, v in split.items()},
            "policy": {"neighbor_k": neighbor_k, "distance": "squared_euclidean_on_train_standardized_heldout_activity",
                       "purge_samples": purge_samples, "maximum_fit_lag": lag, "group_size": group_size,
                       "access_condition": conditions[0][0], "declared_tuning_budget": conditions[0][1],
                       "baseline_competence_verified": False, "realized_budget_verified": False},
            "preprocessing": scaling, "methods": results, "comparisons": comparisons, "holds": HOLDS}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path, help="operator JSON request containing both source roles")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    entries = request.get("recordings", [])
    if sorted(e.get("role", "") for e in entries) != sorted(POPULATIONS):
        raise ValueError("CLI requires exactly one hippocampus and one mouse recording")
    results = []
    for entry in entries:
        record = load_source_npz(entry["source_npz"], entry["role"], entry["expected_sha256"])
        artifacts = [json.loads(Path(path).read_text()) for path in entry["embedding_artifacts"]]
        result = evaluate_recording(record, artifacts, purge_samples=request["purge_samples"],
                                    maximum_fit_lag=request["maximum_fit_lag"])
        result["embedding_artifact_receipts"] = [
            {"name": artifact["name"], "sha256": file_sha256(path)}
            for path, artifact in zip(entry["embedding_artifacts"], artifacts)]
        results.append(result)
    output = {"schema_version": 1, "task_id": TASK_ID, "contract_sha256": CONTRACT_SHA256,
              "scientifically_qualified": False, "full_contract_complete": False,
              "recordings": results, "holds": HOLDS}
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
