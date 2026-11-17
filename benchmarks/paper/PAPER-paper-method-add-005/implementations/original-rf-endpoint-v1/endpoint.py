"""AJILE source RF decoding endpoint; trusted operator inputs, no diffusion fitting.

This component evaluates already prepared standardized signals and frozen imputer
outputs. It does not certify original data identity, split lineage or model quality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

SCHEMA = "ajile-source-rf-endpoint-v1"
PARTICIPANTS = tuple(f"EC{i:02d}" for i in range(1, 13))
CHANNELS = dict(zip(PARTICIPANTS, (94, 86, 80, 84, 106, 80, 64, 92, 126, 126, 106, 116)))
DROPOUTS = (0.5, 0.7, 0.9)
REPEATS = tuple(range(5))
IMPUTERS = ("author_ddpm", "deterministic_nn", "candidate")
ARMS = ("fully_observed", "mean_imputation") + IMPUTERS
SOURCE_REVISION = "7e9c3314dc242c36a206d18f13158c049e84cd1d"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def digest_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def valid_digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def array_digest(value):
    value = np.ascontiguousarray(value)
    require(value.dtype.kind != "O", "object arrays are unsupported")
    return digest_json({"dtype": value.dtype.str, "shape": list(value.shape),
                        "bytes_sha256": hashlib.sha256(memoryview(value).cast("B")).hexdigest()})


def float32(value, name):
    """Match AJILE_LFP.__getitem__/get_train_mean_and_std float32 conversion."""
    value = np.asarray(value)
    require(value.dtype.kind in "fiu" and np.isfinite(value).all(), f"{name} must be finite numeric data")
    with np.errstate(over="ignore"):
        value = value.astype(np.float32)
    require(np.isfinite(value).all(), f"{name} overflows source float32")
    return value


def row_ids(value, length, name):
    value = np.asarray(value)
    require(value.shape == (length,) and value.dtype.kind in "US", f"invalid {name}")
    values = value.astype(str).tolist()
    require(len(set(values)) == length and all(v.strip() for v in values), f"{name} must be unique nonempty strings")
    return values


def binary_labels(value, length, name):
    value = np.asarray(value)
    require(value.shape == (length,) and value.dtype.kind in "fiu" and np.isin(value, [0, 1]).all(), f"invalid binary {name}")
    return value.astype(np.int64)


def source_day_indices(days):
    """Source loader order: concatenate earlier days sorted, hold latest day.

    This returns the author code split, not proof that latest day is paper day 7.
    Sorting days before collecting rows is consequential for the seeded RF split.
    """
    days = np.asarray(days)
    require(days.ndim == 1 and days.dtype.kind in "fiu" and np.isfinite(days).all(), "invalid event days")
    require(np.equal(days, np.floor(days)).all(), "event days must be integer labels")
    unique = np.unique(days)
    require(len(unique) >= 2, "need training and test days")
    train = np.concatenate([np.flatnonzero(days == day) for day in unique[:-1]])
    test = np.flatnonzero(days == unique[-1])
    return train, test


def observed_channels(channels, dropout, repeat):
    require(type(channels) is int and channels >= 2, "invalid channel count")
    require(dropout in DROPOUTS and type(repeat) is int and repeat in REPEATS, "unsupported dropout/repeat")
    count = int(np.round((1.0 - dropout) * channels))
    require(0 < count < channels, "mask must retain observed and missing channels")
    # Preserve the source choice order as provenance, though the binary mask is unordered.
    chosen = np.random.default_rng(repeat).choice(channels, size=count, replace=False)
    mask = np.zeros(channels, dtype=bool)
    mask[chosen] = True
    return mask, chosen


def training_partitions(length, repeat):
    require(type(length) is int and length >= 3, "three RF partitions require at least three training events")
    require(type(repeat) is int and repeat in REPEATS, "unsupported repeat")
    permutation = np.random.default_rng(repeat).permutation(length)
    size = length // 3
    # np.setdiff1d sorts the retained rows. Remainder rows are in all three fits.
    return tuple(np.setdiff1d(permutation, permutation[i * size:(i + 1) * size]) for i in range(3))


def decoder_inputs(test_z, mean, scale, imputations, observed):
    """Source merge, float32 inverse transform, then channel-major flattening.

    No quality filtering occurs here: the pinned experiment ignores quality masks.
    Test arrays and this return value are evaluator-only, never candidate packets.
    """
    test_z = float32(test_z, "test_z")
    require(test_z.ndim == 3 and min(test_z.shape) > 0, "expected events/channels/time")
    channels = test_z.shape[1]
    mean, scale = float32(mean, "mean"), float32(scale, "scale")
    require(mean.shape == scale.shape == (channels,) and np.all(scale > 0), "invalid training normalization")
    observed = np.asarray(observed)
    require(observed.shape == (channels,) and observed.dtype == bool and observed.any() and (~observed).any(), "invalid observed mask")
    require(set(imputations) == set(IMPUTERS), "author DDPM, deterministic neural imputer and candidate outputs all required")
    mask = observed[None, :, None].astype(np.float32)
    mean, scale = mean[None, :, None], scale[None, :, None]
    with np.errstate(over="ignore", invalid="ignore"):
        full = test_z * scale + mean
        completed = {"fully_observed": full, "mean_imputation": full * mask + (1.0 - mask) * mean}
        for arm in IMPUTERS:
            prediction = float32(imputations[arm], arm)
            require(prediction.shape == test_z.shape, f"{arm} shape mismatch")
            merged = prediction * (1.0 - mask) + test_z * mask
            completed[arm] = merged * scale + mean
    require(all(np.isfinite(value).all() for value in completed.values()), "inverse normalization overflow")
    return {arm: value.reshape(len(test_z), -1) for arm, value in completed.items()}


def evaluate_case(data, *, participant, dropout, repeat, input_digest, kind):
    """Fit the three source RF decoders and score all frozen arms on all events.

    Called only by a trusted operator under a separately authorized native run.
    Generated software controls may exercise the exact same path on small arrays.
    """
    require(participant in PARTICIPANTS, "unknown participant")
    require(kind in ("generated_control", "authentic_input"), "explicit input kind required")
    require(valid_digest(input_digest), "input content digest required")
    train, test = float32(data["train_z"], "train_z"), float32(data["test_z"], "test_z")
    require(train.ndim == test.ndim == 3 and train.shape[1:] == test.shape[1:] and min(train.shape + test.shape) > 0, "signal shape mismatch")
    if kind == "authentic_input":
        require(train.shape[1:] == (CHANNELS[participant], 1001), "original participant channels and 1001 samples required")
    train_ids = row_ids(data["train_row_ids"], len(train), "train row IDs")
    test_ids = row_ids(data["test_row_ids"], len(test), "test row IDs")
    require(not set(train_ids).intersection(test_ids), "training/test event overlap")
    train_y = binary_labels(data["train_labels"], len(train), "training labels")
    test_y = binary_labels(data["test_labels"], len(test), "test labels")
    # Bind the prepared row order to native indices and source event-day order.
    native_days = np.asarray(data["native_days"])
    native_ids = row_ids(data["native_row_ids"], len(native_days), "native row IDs")
    train_idx, test_idx = source_day_indices(native_days)
    require(train_ids == [native_ids[i] for i in train_idx] and test_ids == [native_ids[i] for i in test_idx], "prepared rows differ from source day-sorted train/latest-day test order")
    source_digest = str(np.asarray(data["source_sha256"]).item())
    require(valid_digest(source_digest), "native source digest required")
    observed, chosen = observed_channels(int(train.shape[1]), dropout, repeat)
    mean, scale = float32(data["train_mean"], "train_mean"), float32(data["train_scale"], "train_scale")
    inputs = decoder_inputs(test, mean, scale, {arm: data[arm] for arm in IMPUTERS}, observed)
    with np.errstate(over="ignore"):
        train_raw = train * scale[None, :, None] + mean[None, :, None]
    require(np.isfinite(train_raw).all(), "training inverse normalization overflow")
    train_flat = train_raw.reshape(len(train), -1)
    from sklearn import __version__ as sklearn_version
    from sklearn.ensemble import RandomForestClassifier
    folds = []
    for fold, indices in enumerate(training_partitions(len(train), repeat)):
        model = RandomForestClassifier(n_estimators=240, max_depth=9, class_weight="balanced", oob_score=True, random_state=fold, n_jobs=1)
        model.fit(train_flat[indices], train_y[indices])
        correct = {arm: int(np.count_nonzero(model.predict(inputs[arm]) == test_y)) for arm in ARMS}
        folds.append({"fold": fold, "rf_seed": fold, "train_events": len(indices), "train_row_order_sha256": digest_json([train_ids[i] for i in indices]), "test_events": len(test), "correct": correct})
    return {
        "schema": SCHEMA, "kind": kind, "participant": participant, "dropout": dropout, "repeat": repeat,
        "source_revision": SOURCE_REVISION, "input_sha256": input_digest, "source_sha256": source_digest,
        "preparation_sha256": digest_json({name: array_digest(value) for name, value in
            (("train_z", train), ("test_z", test), ("train_labels", train_y), ("test_labels", test_y),
             ("train_mean", mean), ("train_scale", scale))}),
        "train_row_order_sha256": digest_json(train_ids), "test_row_order_sha256": digest_json(test_ids),
        "native_day_order_sha256": digest_json(native_days.tolist()), "train_days": np.unique(native_days[train_idx]).tolist(), "test_day": int(native_days[test_idx][0]),
        "channels": int(train.shape[1]), "samples_per_event": int(train.shape[2]), "test_events": len(test),
        "observed_channels_choice_order": chosen.tolist(), "folds": folds,
        "software": {"numpy": np.__version__, "scikit_learn": sklearn_version},
        "qualification": "source_endpoint_component_only; data, model and scientific qualification not established",
    }


def aggregate_panel(records):
    """Require the complete 12 x 3 x 5 x 3 panel; retain all 36 source curves."""
    require(len(records) == 180, "exactly 180 participant/dropout/repeat cases required")
    keys = [(r["participant"], r["dropout"], r["repeat"]) for r in records]
    expected = {(p, d, r) for p in PARTICIPANTS for d in DROPOUTS for r in REPEATS}
    require(len(set(keys)) == 180 and set(keys) == expected, "incomplete or duplicated case panel")
    require(len({r["kind"] for r in records}) == 1, "cannot mix authentic inputs and generated controls")
    kind = records[0]["kind"]
    require(kind in ("authentic_input", "generated_control"), "invalid panel kind")
    require(all(r["software"] == records[0]["software"] for r in records), "software versions differ within panel")
    table = dict(zip(keys, records))
    cells = []
    for participant in PARTICIPANTS:
        reference = table[participant, 0.5, 0]
        for dropout in DROPOUTS:
            accuracy = {arm: [] for arm in ARMS}
            for repeat in REPEATS:
                row = table[participant, dropout, repeat]
                require(row["schema"] == SCHEMA and row["source_revision"] == SOURCE_REVISION, "source/schema mismatch")
                for field in ("source_sha256", "preparation_sha256", "train_row_order_sha256", "test_row_order_sha256", "native_day_order_sha256", "channels", "samples_per_event", "test_events", "train_days", "test_day", "software"):
                    require(row[field] == reference[field], f"participant binding differs: {field}")
                for field in ("source_sha256", "input_sha256", "preparation_sha256", "train_row_order_sha256", "test_row_order_sha256", "native_day_order_sha256"):
                    require(valid_digest(row[field]), f"invalid {field}")
                if kind == "authentic_input":
                    require((row["channels"], row["samples_per_event"]) == (CHANNELS[participant], 1001), "original geometry required")
                _, chosen = observed_channels(row["channels"], dropout, repeat)
                require(row["observed_channels_choice_order"] == chosen.tolist(), "source channel mask changed")
                folds = row["folds"]
                require([f["fold"] for f in folds] == [0, 1, 2], "exact three ordered folds required")
                n = row["test_events"]
                require(type(n) is int and n > 0, "invalid event denominator")
                for fold, result in enumerate(folds):
                    require(result["rf_seed"] == fold and result["test_events"] == n and set(result["correct"]) == set(ARMS), "fold/arm mismatch")
                    require(type(result["train_events"]) is int and result["train_events"] > 0 and valid_digest(result["train_row_order_sha256"]), "invalid training fold identity")
                    paired = table[participant, 0.5, repeat]["folds"][fold]
                    require(result["train_row_order_sha256"] == paired["train_row_order_sha256"] and result["train_events"] == paired["train_events"], "RF training partition differs across dropouts")
                    require(result["correct"]["fully_observed"] == paired["correct"]["fully_observed"], "fully observed paired control changed")
                    for count in result["correct"].values():
                        require(type(count) is int and 0 <= count <= n, "invalid correct count")
                for arm in ARMS:
                    accuracy[arm].append(float(np.mean([f["correct"][arm] / n for f in folds])))
            means = {arm: float(np.mean(values)) for arm, values in accuracy.items()}
            # The author plotting cell uses std(arr[:, 2] - arr[:, 1]), not std(arr[:, 2]).
            paired_sd = {arm: float(np.std(np.array(accuracy[arm]) - accuracy["mean_imputation"], ddof=0)) for arm in IMPUTERS}
            cells.append({"participant": participant, "dropout": dropout, "test_events": reference["test_events"], "fold_mean_accuracy_by_repeat": accuracy, "mean_accuracy": means,
                          "accuracy_sd_over_repeats": {arm: float(np.std(values, ddof=0)) for arm, values in accuracy.items()},
                          "source_figure_errorbar_paired_gain_sd": paired_sd,
                          "candidate_minus_author_ddpm_by_repeat": (np.array(accuracy["candidate"]) - accuracy["author_ddpm"]).tolist()})
    return {"schema": SCHEMA, "kind": kind, "case_count": 180, "fold_count": 540, "participant_dropout_cells": cells,
            "aggregation": "three RF fold accuracies averaged within each replicate; five replicates per participant/dropout; figure errorbar is population SD of paired gain over mean imputation",
            "qualification": "software component only; no paper win, calibrated author result, current SOTA or independent-participant inference asserted"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    case = sub.add_parser("score-case", help="trusted operator only; fits the original fixed RF decoder")
    case.add_argument("input", type=Path)
    case.add_argument("output", type=Path)
    case.add_argument("--participant", choices=PARTICIPANTS, required=True)
    case.add_argument("--dropout", type=float, choices=DROPOUTS, required=True)
    case.add_argument("--repeat", type=int, choices=REPEATS, required=True)
    case.add_argument("--kind", choices=("authentic_input", "generated_control"), required=True)
    panel = sub.add_parser("aggregate")
    panel.add_argument("manifest", type=Path, help="JSON list of {path,sha256} case receipts, relative to manifest")
    panel.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        require(not args.output.exists(), "refusing to overwrite output")
        if args.command == "score-case":
            with np.load(args.input, allow_pickle=False) as source:
                result = evaluate_case(dict(source), participant=args.participant, dropout=args.dropout, repeat=args.repeat, input_digest=digest_file(args.input), kind=args.kind)
        else:
            rows = json.loads(args.manifest.read_text())
            require(isinstance(rows, list) and len(rows) == 180, "180 bound receipt files required")
            records = []
            for item in rows:
                path = args.manifest.parent / item["path"]
                require(digest_file(path) == item["sha256"], "case receipt modified")
                records.append(json.loads(path.read_text()))
            result = aggregate_panel(records)
        # Native event identities and prepared arrays stay in operator-only inputs.
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write("\n")
    except (ValueError, KeyError, OSError, TypeError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
