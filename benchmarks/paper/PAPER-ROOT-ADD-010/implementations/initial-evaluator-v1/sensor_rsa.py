"""Processed-epoch sensor RSA construction component for PAPER-ROOT-ADD-010.

Independent implementation; no author payload, pretrained model or reference result.
This component never awards reproduction or scientific qualification.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.signal import savgol_filter

TASK_ID = "PAPER-ROOT-ADD-010"
SOURCE_REVISION = "133669b577b5ae341cd0842dfb0e7f0af85c0020"
CONTRACT_SHA256 = "40e9ad5a0593399399e449e0b005caa1f9e31f84bca32f91c96f8eb1c7da0edd"
SHAPES = ("square", "rectangle", "isoTrapezoid", "parallelogram", "losange",
          "kite", "rightKite", "rustedHinge", "hinge", "trapezoid", "random")
SUBJECTS = tuple(f"sub-{i:02d}" for i in range(1, 21))
# Raw POGS FIF inventory in the immutable task.json, not a guessed complete grid.
RUNS = {s: tuple(f"{i:02d}" for i in range(1, 8 if s in ("sub-10", "sub-11") else 9))
        for s in SUBJECTS}
TIMES = np.arange(-25, 276, dtype=float) / 250.0
PAIRS = np.triu_indices(len(SHAPES), 1)
HOLDS = (
    "Version-of-Record .3 versus reviewed-preprint v2 figure/latency/model reconciliation",
    "Authentic raw BIDS preprocessing and modified native pipeline execution",
    "Historical shape/oddball decoding implementation and endpoint reconstruction",
    "Historical rsatoolbox dependency pin, numerical agreement and independent reference",
    "Exact model-RDM payload validation, unspecified noise ceiling and native permutation parity",
    "Protected assessment packet, public-result exposure policy and target tolerances",
    "Stimulus/model/third-party rights and complete payload qualification",
    "Scientific replication, meaningful difficulty and measured native resources",
)


def _finite(value, name):
    out = np.asarray(value, dtype=float)
    if not np.isfinite(out).all():
        raise ValueError(f"{name} must contain only finite numbers")
    return out


def _strings(value, n, name):
    out = np.asarray(value)
    if out.shape != (n,) or out.dtype.kind not in "US":
        raise ValueError(f"{name} must be a length-{n} string array")
    if any(not str(x) for x in out):
        raise ValueError(f"{name} contains an empty label")
    return out.astype(str)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def crossnobis(data, shapes, runs, *, shape_order=SHAPES, smooth=False):
    """Return [time, pair] leave-one-run-out distances and trial counts.

    Training means pool all trials outside the held run, rather than weighting
    run means equally. Fold distances are averaged equally, divided by channels.
    Identity precision matches the source call's omitted noise argument. Negative
    estimates are retained. Missing run/shape cells fail instead of dropping pairs.
    """
    x = _finite(data, "data")
    if x.ndim != 3 or min(x.shape) == 0:
        raise ValueError("data must have nonempty [trial, channel, time] axes")
    n, channels, _ = x.shape
    labels = _strings(shapes, n, "shapes")
    groups = _strings(runs, n, "runs")
    order = tuple(shape_order)
    if len(order) < 2 or len(set(order)) != len(order) or set(labels) != set(order):
        raise ValueError("shape labels must exactly cover the distinct declared order")
    folds = sorted(set(groups))
    if len(folds) < 2:
        raise ValueError("at least two independent runs are required")
    if type(smooth) is not bool:
        raise ValueError("smooth must be a boolean")
    if smooth:
        if x.shape[2] < 25:
            raise ValueError("source smoothing requires at least 25 time samples")
        x = savgol_filter(x, window_length=25, polyorder=2, axis=2, mode="interp")
    counts = np.array([[np.count_nonzero((groups == run) & (labels == shape))
                        for shape in order] for run in folds], dtype=int)
    if np.any(counts == 0):
        raise ValueError("every observed run must contain every declared shape")
    i, j = np.triu_indices(len(order), 1)
    distances = []
    for run in folds:
        test = np.stack([x[(groups == run) & (labels == shape)].mean(0) for shape in order])
        train = np.stack([x[(groups != run) & (labels == shape)].mean(0) for shape in order])
        a, b = train[i] - train[j], test[i] - test[j]
        distances.append(np.einsum("pct,pct->tp", a, b) / channels)
    result = np.mean(distances, axis=0)
    if not np.isfinite(result).all():
        raise ValueError("crossnobis overflow; inspect input scaling")
    return result, {run: dict(zip(order, row.tolist())) for run, row in zip(folds, counts)}


def corr_cov(empirical, models, *, n_shapes=len(SHAPES)):
    """Whitened Pearson RDM correlation with identity pattern covariance.

    After removing each pair-vector's mean, use V = (C C.T)**2, where rows
    of C are shape contrasts. This accounts for covariance of shared-shape
    distances. It is not sensor whitening or an ordinary Pearson correlation.
    Degenerate vectors fail explicitly rather than reporting a misleading zero.
    """
    a, b = _finite(empirical, "empirical RDMs"), _finite(models, "model RDMs")
    size = n_shapes * (n_shapes - 1) // 2
    if a.ndim != 2 or b.ndim != 2 or a.shape[1] != size or b.shape[1] != size:
        raise ValueError("RDM arrays must be [observation, n_shapes choose 2]")
    i, j = np.triu_indices(n_shapes, 1)
    contrasts = np.zeros((size, n_shapes))
    contrasts[np.arange(size), i], contrasts[np.arange(size), j] = 1, -1
    covariance = (contrasts @ contrasts.T) ** 2
    # Scale before centering as well: a finite row's sum may overflow otherwise.
    a_scale, b_scale = np.max(np.abs(a), axis=1), np.max(np.abs(b), axis=1)
    if np.any(a_scale == 0) or np.any(b_scale == 0):
        raise ValueError("constant RDM has undefined correlation")
    a, b = a / a_scale[:, None], b / b_scale[:, None]
    a = a - a.mean(axis=1, keepdims=True)
    b = b - b.mean(axis=1, keepdims=True)
    # Normalize before solving to keep small centered differences numerically safe.
    anorm, bnorm = np.max(np.abs(a), axis=1), np.max(np.abs(b), axis=1)
    if np.any(anorm == 0) or np.any(bnorm == 0):
        raise ValueError("constant RDM has undefined correlation")
    a, b = a / anorm[:, None], b / bnorm[:, None]
    wa, wb = np.linalg.solve(covariance, a.T).T, np.linalg.solve(covariance, b.T).T
    denom = np.sqrt(np.sum(a * wa, axis=1)[:, None] * np.sum(b * wb, axis=1)[None, :])
    result = (a @ wb.T) / denom
    if not np.isfinite(result).all():
        raise ValueError("undefined whitened correlation")
    return np.clip(result, -1, 1)


def cluster_inference(correlations, *, seed=None):
    """Optional native source-call adapter; not exercised on authentic data here.

    Calls each model separately, tail=1 and 8192 permutations over samples25:226
    (0 through .8 seconds inclusive). The author call leaves seed unspecified;
    specifying one is a prospective reproducibility choice, recorded in output.
    Historical MNE version/defaults and exact p-value agreement remain held.
    """
    x = _finite(correlations, "subject correlations")
    if x.shape != (20, 301, 2):
        raise ValueError("correlations must have axes [20 subjects, 301 times, 2 models]")
    if np.any(np.abs(x) > 1):
        raise ValueError("correlations must lie in [-1, 1]")
    if seed is not None and (type(seed) is not int or not 0 <= seed < 2**32):
        raise ValueError("seed must be None or a nonnegative 32-bit integer")
    if np.any(x[:, 25:226].std(axis=0, ddof=1) == 0):
        raise ValueError("zero subject variance gives undefined t statistics")
    import mne
    results = []
    for model in range(2):
        kwargs = {"n_permutations": 8192, "verbose": False, "tail": 1}
        if seed is not None:
            kwargs["seed"] = seed
        statistics, clusters, pvalues, null = mne.stats.permutation_cluster_1samp_test(x[:, 25:226, model], **kwargs)
        _finite(statistics, "native t statistics")
        _finite(pvalues, "native cluster pvalues")
        _finite(null, "native null statistics")
        cluster_rows = []
        for cluster, pvalue in zip(clusters, pvalues):
            # MNE 1D default returns a tuple containing integer indices or a slice.
            indices = np.arange(201)[cluster[0] if isinstance(cluster, tuple) else cluster]
            cluster_rows.append({"sample_indices": (np.atleast_1d(indices) + 25).tolist(),
                                 "pvalue": float(pvalue)})
        results.append({"model": ("symbolic", "visual_cnn")[model],
                        "t_statistics": np.asarray(statistics).tolist(), "clusters": cluster_rows,
                        "null_max_cluster_statistics": np.asarray(null).tolist()})
    return {"mne_version": mne.__version__, "seed": seed,
            "seed_policy": "source unspecified" if seed is None else "prospective reproducibility choice",
            "n_permutations_requested": 8192, "tail": 1, "results": results,
            "authentic_reference_agreement": "not_established"}


def read_models(path):
    """Read explicitly ordered symbolic and visual RDMs; never guess CSV order."""
    obj = json.loads(Path(path).read_text())
    if obj.get("shape_order") != list(SHAPES):
        raise ValueError("model shape_order must equal the exact sensor-RSA order")
    if set(obj.get("models", {})) != {"symbolic", "visual_cnn"}:
        raise ValueError("models must contain exactly symbolic and visual_cnn")
    out = []
    for name in ("symbolic", "visual_cnn"):
        item = obj["models"][name]
        if not isinstance(item.get("source"), str) or not item["source"].strip():
            raise ValueError(f"{name} needs a source declaration")
        m = _finite(item["matrix"], name)
        if m.shape != (11, 11) or not np.allclose(m, m.T, atol=1e-12, rtol=0):
            raise ValueError(f"{name} must be a symmetric 11 by 11 matrix")
        if not np.allclose(np.diag(m), 0, atol=1e-12, rtol=0):
            raise ValueError(f"{name} diagonal must be zero")
        out.append(m[PAIRS])
    result = np.stack(out)
    corr_cov(result, result)  # Reject degenerate models before reading epochs.
    return result, obj


def import_models(symbolic_csv, visual_csv, destination):
    """Explicitly align labeled author CSVs without changing their values."""
    result = {"shape_order": list(SHAPES), "models": {}}
    for name, path in (("symbolic", symbolic_csv), ("visual_cnn", visual_csv)):
        with Path(path).open(newline="") as stream:
            rows = list(csv.reader(stream))
        if len(rows) != 12 or any(len(row) != 12 for row in rows):
            raise ValueError("model CSV must have one header and 11 labeled rows/columns")
        columns, labels = rows[0][1:], [row[0] for row in rows[1:]]
        if set(columns) != set(SHAPES) or set(labels) != set(SHAPES):
            raise ValueError("CSV shape labels must match the exact 11 shapes")
        matrix = [[float(rows[1 + labels.index(s)][1 + columns.index(t)]) for t in SHAPES]
                  for s in SHAPES]
        result["models"][name] = {"source": str(Path(path).resolve()),
                                  "sha256": digest(path), "matrix": matrix}
    # Validate in-memory through the same strict matrix rules before writing.
    for item in result["models"].values():
        m = _finite(item["matrix"], "model")
        if not np.allclose(m, m.T, atol=1e-12, rtol=0) or not np.allclose(np.diag(m), 0, atol=1e-12, rtol=0):
            raise ValueError("model CSV must be symmetric with zero diagonal")
    corr_cov(np.stack([np.asarray(v["matrix"])[PAIRS] for v in result["models"].values()]),
             np.stack([np.asarray(v["matrix"])[PAIRS] for v in result["models"].values()]))
    with Path(destination).open("x") as stream:
        json.dump(result, stream, allow_nan=False, indent=2)
    return {"path": str(Path(destination).resolve()), "sha256": digest(destination)}


def load_subject(path, subject):
    """Validate a post-clean converted-reference NPZ, with no pickle loading."""
    if subject not in SUBJECTS:
        raise ValueError("unknown subject")
    with np.load(path, allow_pickle=False) as f:
        required = {"data", "shapes", "runs", "times", "channel_names", "subject", "representation"}
        if set(f.files) != required:
            raise ValueError(f"NPZ fields must be exactly {sorted(required)}")
        if str(f["subject"].item()) != subject:
            raise ValueError("NPZ subject differs from manifest")
        if str(f["representation"].item()) != "reference_mne_virtual_magnetometers":
            raise ValueError("NPZ must declare source-converted reference magnetometers")
        data = _finite(f["data"], "data")
        if data.ndim != 3:
            raise ValueError("data must be trial by channel by time")
        names = _strings(f["channel_names"], data.shape[1], "channel_names")
        if len(set(names)) != len(names):
            raise ValueError("duplicate channel names")
        times = _finite(f["times"], "times")
        if times.shape != TIMES.shape or not np.allclose(times, TIMES, rtol=0, atol=1e-10):
            raise ValueError("times must be -0.1 through 1.1 seconds inclusive at 250 Hz")
        if data.shape[2] != len(times):
            raise ValueError("data and time lengths differ")
        runs = _strings(f["runs"], data.shape[0], "runs")
        if set(runs) != set(RUNS[subject]):
            raise ValueError("run roster differs from immutable raw POGS inventory")
        shapes = _strings(f["shapes"], data.shape[0], "shapes")
    return data, shapes, runs, names


def evaluate(manifest_path):
    """Compute both time courses for all 20 sensor subjects, with equal subject weight."""
    manifest_path = Path(manifest_path).resolve()
    packet = json.loads(manifest_path.read_text())
    subjects = packet.get("subjects", [])
    if (len(subjects) != len(SUBJECTS) or
            sorted(s.get("subject", "") for s in subjects) != list(SUBJECTS)):
        raise ValueError("the complete distinct 20-subject sensor population is required")
    if packet.get("source_revision") != SOURCE_REVISION:
        raise ValueError("source revision must match the canonical pinned snapshot")
    def checked(item):
        path = (manifest_path.parent / item["path"]).resolve()
        if not isinstance(item.get("sha256"), str) or digest(path) != item["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {path.name}")
        return path
    models_path = checked(packet["models"])
    models, model_record = read_models(models_path)
    values = {"unsmoothed": [], "savgol_25_2": []}
    coverage = []
    channels = None
    for item in sorted(subjects, key=lambda s: s["subject"]):
        path = checked(item)
        data, shapes, runs, names = load_subject(path, item["subject"])
        if channels is None:
            channels = names
        elif not np.array_equal(channels, names):
            raise ValueError("sensor mask/order differs across subjects")
        for mode, smooth in (("unsmoothed", False), ("savgol_25_2", True)):
            rdms, counts = crossnobis(data, shapes, runs, smooth=smooth)
            values[mode].append(rdms)
        coverage.append({"subject": item["subject"], "path": str(path), "sha256": item["sha256"],
                         "reference_trial_counts": counts})
    output = {}
    for mode, rdms in values.items():
        rdms = np.stack(rdms)
        correlations = corr_cov(rdms.reshape(-1, len(PAIRS[0])), models).reshape(20, len(TIMES), 2)
        output[mode] = {"subject_rdms": rdms.tolist(), "mean_rdm": rdms.mean(0).tolist(),
                        "subject_model_corr_cov": correlations.tolist(),
                        "mean_model_corr_cov": correlations.mean(0).tolist(),
                        "sem_model_corr_cov": (correlations.std(0, ddof=0) / np.sqrt(20)).tolist()}
    return {"task_id": TASK_ID, "implementation": "initial-evaluator-v1",
            "scope": "complete processed-reference sensor RSA numerical component",
            "scientifically_qualified": False, "full_contract_complete": False,
            "authentic_reference_agreement": "not_established", "holds": list(HOLDS),
            "source_revision": SOURCE_REVISION, "contract_sha256": CONTRACT_SHA256,
            "manifest_sha256": digest(manifest_path), "models_sha256": digest(models_path),
            "model_declarations_unverified": model_record,
            "times_seconds": TIMES.tolist(), "subjects": list(SUBJECTS),
            "shape_order": list(SHAPES), "pair_order": [[SHAPES[i], SHAPES[j]] for i, j in zip(*PAIRS)],
            "models": ["symbolic", "visual_cnn"], "channel_names": channels.tolist(),
            "sem_convention": "source population standard deviation (ddof=0) / sqrt(20)",
            "coverage": coverage, "results": output}


def export_epochs(source, subject, destination):
    """Native adapter only: caller supplies already-cleaned +metadata epochs.

    This does not execute raw-BIDS preprocessing or reproduce the archived decoder.
    A run is never inferred from trial order. MNE conversion is intentionally the
    same requested representation as the author sensor-RSA entrypoint.
    """
    if subject not in SUBJECTS:
        raise ValueError("unknown subject")
    import mne
    epochs = mne.read_epochs(source, preload=True)["reference"].as_type("mag").pick_types(meg="mag")
    if epochs.metadata is None or not {"base_shape", "run"}.issubset(epochs.metadata.columns):
        raise ValueError("clean epochs require base_shape and run metadata")
    raw_runs = epochs.metadata["run"].to_numpy()
    def run_label(value):
        s = str(value)
        if s.isdecimal() and 1 <= int(s) <= 8:
            return f"{int(s):02d}"
        raise ValueError("run metadata must be integer labels 1..8")
    with Path(destination).open("xb") as stream:
        np.savez_compressed(stream, data=epochs.get_data(),
                            shapes=epochs.metadata["base_shape"].to_numpy(dtype=str),
                            runs=np.array([run_label(x) for x in raw_runs]), times=epochs.times,
                            channel_names=np.array(epochs.ch_names), subject=np.array(subject),
                            representation=np.array("reference_mne_virtual_magnetometers"))
    return {"source_path": str(Path(source).resolve()), "source_sha256": digest(source),
            "subject": subject, "path": str(Path(destination).resolve()), "sha256": digest(destination),
            "mne_version": mne.__version__, "native_preprocessing_verified": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    ev = sub.add_parser("evaluate")
    ev.add_argument("manifest")
    ev.add_argument("output")
    ex = sub.add_parser("export-epochs")
    ex.add_argument("source")
    ex.add_argument("subject", choices=SUBJECTS)
    ex.add_argument("destination")
    im = sub.add_parser("import-models")
    im.add_argument("symbolic_csv")
    im.add_argument("visual_csv")
    im.add_argument("destination")
    args = p.parse_args()
    if args.command == "evaluate":
        report = evaluate(args.manifest)
        with Path(args.output).open("x") as stream:
            json.dump(report, stream, allow_nan=False)
    elif args.command == "export-epochs":
        print(json.dumps(export_epochs(args.source, args.subject, args.destination)))
    else:
        print(json.dumps(import_models(args.symbolic_csv, args.visual_csv, args.destination)))


if __name__ == "__main__":
    main()
