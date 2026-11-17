#!/usr/bin/env python3
"""NEURAL-040 prospective matched encoder and independent held-out scorer.

Only precomputed, rights-cleared features are accepted. No models/data are fetched.
This is a construction implementation, not an executed authentic benchmark.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np

TASK = "NEURAL-040"
VERSION = "initial-evaluator-v1"
DATASET_COMMIT = "96750e7017b30cb02f011c11561a3df897695853"
PEOPLE = ("sub-01", "sub-02", "sub-03", "sub-05")
FAMILIES = ("audio", "visual", "language")
ARMS = {"full": FAMILIES, "no_audio": ("visual", "language"),
        "no_visual": ("audio", "language"), "no_language": ("audio", "visual")}
HOLDS = ["authentic_payload_access_schema_and_hashes", "native_parcel_alignment",
         "feature_model_exposure_and_media_rights", "authentic_reference_execution",
         "independent_native_replication", "protected_evaluation_and_admission",
         "frozen_scientific_protocol_and_resource_budget", "four_person_population_limit"]


class ContractError(ValueError):
    """Reject a packet instead of silently changing the scientific estimand."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def identifier(value):
    return isinstance(value, str) and bool(value) and "__" not in value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_protocol(p):
    require(isinstance(p, dict), "protocol must be an object")
    require(p.get("task_id") == TASK and p.get("schema_version") == 1,
            "wrong task/schema")
    require(p.get("data_scope") == "public_development_only", "public development only")
    require(p.get("dataset_commit") == DATASET_COMMIT, "wrong dataset commit")
    require(p.get("estimator") == "equal_film_pearson", "freeze the cross-film Pearson estimator")
    require(p.get("participants") == list(PEOPLE), "require the exact four people in fixed order")
    require(type(p.get("tr_seconds")) in (int, float) and p["tr_seconds"] == 1.49,
            "source TR is 1.49 seconds")
    parcels = p.get("parcel_ids", {})
    require(set(parcels) == set(PEOPLE), "parcel maps must cover all four people")
    for person in PEOPLE:
        labels = parcels[person]
        require(isinstance(labels, list) and len(labels) == 1000 and
                all(identifier(x) for x in labels) and len(set(labels)) == 1000,
                "each person needs 1000 unique native parcel IDs")
    lags = p.get("lags_tr")
    require(isinstance(lags, list) and bool(lags) and all(integer(x) for x in lags)
            and lags == sorted(set(lags)), "lags must be ordered unique nonnegative integer TRs")
    for key in ("guard_tr", "feature_context_left_tr", "feature_context_right_tr"):
        require(integer(p.get(key)), key + " must be explicit nonnegative integer")
    require(p["guard_tr"] >= max(lags) + p["feature_context_left_tr"] and
            p["guard_tr"] >= p["feature_context_right_tr"], "guard does not cover lag/context")
    require(min(lags) >= p["feature_context_right_tr"], "feature lookahead exceeds lag: future input")
    require(integer(p.get("capacity_rank"), 1), "capacity_rank must be a positive integer")
    require(type(p.get("ridge_alpha")) in (int, float) and
            np.isfinite(p["ridge_alpha"]) and p["ridge_alpha"] > 0,
            "ridge_alpha must be finite and positive")
    assets = p.get("feature_assets", {})
    require(set(assets) == set(FAMILIES), "pin all three feature families")
    for family, entry in assets.items():
        require(isinstance(entry, dict) and identifier(entry.get("extractor_revision")),
                "feature extractor revision required")
        pin = entry.get("checkpoint_sha256", "")
        require(isinstance(pin, str) and len(pin) == 64 and
                all(c in "0123456789abcdef" for c in pin), "checkpoint SHA256 required")
        require(identifier(entry.get("context_policy")), "feature context policy required")
    segments = p.get("segments")
    require(isinstance(segments, list) and bool(segments), "segments required")
    ids, films, coverage, n_null, synchronized = set(), {}, set(), None, {}
    for segment in segments:
        require(isinstance(segment, dict), "segment must be an object")
        sid = segment.get("id")
        require(identifier(sid) and sid not in ids, "duplicate or invalid segment ID")
        ids.add(sid)
        require(segment.get("participant_id") in PEOPLE, "unknown participant")
        require(identifier(segment.get("film_id")), "whole-film/episode identity required")
        require(identifier(segment.get("run_id")), "repeat/run identity required")
        split = segment.get("split")
        require(split in ("train", "evaluation"), "only frozen train/evaluation splits")
        coverage.add((segment["participant_id"], split))
        film = segment["film_id"]
        require(films.setdefault(film, split) == split, "whole film/repeats cross split")
        n = segment.get("n_samples")
        require(integer(n, 3) and n - 2 * p["guard_tr"] >= 3, "insufficient guarded samples")
        require(set(segment.get("feature_keys", {})) == set(FAMILIES) and
                all(identifier(v) for v in segment["feature_keys"].values()), "feature keys missing")
        if split == "evaluation":
            shifts = segment.get("null_offsets_tr")
            kept = n - 2 * p["guard_tr"]
            lower = max(1, p["guard_tr"] + 1)
            require(isinstance(shifts, list) and bool(shifts) and
                    all(integer(s, lower) and s <= kept - lower for s in shifts),
                    "null offsets must exceed guard in both circular directions")
            if n_null is None:
                n_null = len(shifts)
            require(len(shifts) == n_null, "paired null replicate count mismatch")
            sync_key = (film, segment["run_id"], n)
            require(synchronized.setdefault(sync_key, shifts) == shifts,
                    "matching stimulus/run null shifts must synchronize across people")
    require(coverage == set(itertools.product(PEOPLE, ("train", "evaluation"))),
            "every person must have training and evaluation segments")
    return p


def matrix(value, rows, columns=None, name="array"):
    a = np.asarray(value)
    require(a.dtype.kind in "fiu" and a.ndim == 2 and a.shape[0] == rows and
            a.shape[1] > 0 and (columns is None or a.shape[1] == columns),
            name + " has wrong numeric shape")
    a = a.astype(np.float64)
    require(np.isfinite(a).all(), name + " contains nonfinite values")
    return a


def selected_segments(p, person=None, split=None):
    return [s for s in p["segments"] if
            (person is None or s["participant_id"] == person) and
            (split is None or s["split"] == split)]


def kept_rows(p, s):
    return np.arange(p["guard_tr"], s["n_samples"] - p["guard_tr"])


def lagged_features(p, segment, features, families):
    rows = kept_rows(p, segment)
    return np.concatenate([features[segment["feature_keys"][f]][rows - lag]
                           for f in families for lag in p["lags_tr"]], axis=1)


def validate_targets(p, targets, split):
    segments = selected_segments(p, split=split)
    require(set(targets) == {s["id"] for s in segments},
            split + " targets contain missing, extra, or wrong-split segment IDs")
    return {s["id"]: matrix(targets[s["id"]], s["n_samples"], 1000,
                            s["id"]) for s in segments}


def validate_target_metadata(p, metadata, split):
    require(isinstance(metadata, dict) and metadata.get("protocol_sha256") == digest(p),
            split + " target protocol mismatch")
    require(metadata.get("parcel_ids") == p["parcel_ids"], split + " target parcel order mismatch")
    require(metadata.get("split") == split, "target metadata split mismatch")


def encode(p, features, training_targets, training_target_metadata):
    """Fit only on train rows; held-out neural targets cannot enter this API."""
    validate_protocol(p)
    validate_target_metadata(p, training_target_metadata, "train")
    required = {v for s in p["segments"] for v in s["feature_keys"].values()}
    require(set(features) == required, "feature packet has missing or extra keys")
    clean, widths = {}, {}
    for s in p["segments"]:
        for family, key in s["feature_keys"].items():
            a = matrix(features[key], s["n_samples"], name=key)
            require(widths.setdefault(family, a.shape[1]) == a.shape[1],
                    "feature width changes between segments")
            clean[key] = a
    targets = validate_targets(p, training_targets, "train")
    predictions, fits = {}, []
    k, alpha = p["capacity_rank"], p["ridge_alpha"]
    for person in PEOPLE:
        train = selected_segments(p, person, "train")
        evaluation = selected_segments(p, person, "evaluation")
        y = np.concatenate([targets[s["id"]][kept_rows(p, s)] for s in train])
        y_mean = y.mean(axis=0)
        for arm, families in ARMS.items():
            x = np.concatenate([lagged_features(p, s, clean, families) for s in train])
            mean, scale = x.mean(axis=0), x.std(axis=0)
            scale[scale == 0] = 1.0
            z = (x - mean) / scale
            _, singular, vt = np.linalg.svd(z, full_matrices=False)
            rank = int(np.sum(singular > singular[0] * max(z.shape) * np.finfo(float).eps))
            require(rank >= k, "training feature rank below frozen matched capacity")
            projection = vt[:k].T * (np.sqrt(len(x)) / singular[:k])
            whitened = z @ projection
            require(np.allclose(whitened.T @ whitened, len(x) * np.eye(k),
                                atol=1e-7, rtol=1e-7), "whitening numerical failure")
            weights = whitened.T @ (y - y_mean) / (len(x) + alpha)
            for s in evaluation:
                design = (lagged_features(p, s, clean, families) - mean) / scale
                predictions[arm + "__" + s["id"]] = design @ projection @ weights + y_mean
            fits.append({"participant_id": person, "arm": arm, "training_rows": len(x),
                         "input_columns": x.shape[1], "training_rank": rank,
                         "matched_rank": k, "ridge_alpha": alpha,
                         "readout_effective_df_including_intercept": 1 + k * len(x) / (len(x) + alpha),
                         "training_segment_ids": [s["id"] for s in train]})
    metadata = {"task_id": TASK, "implementation": VERSION, "protocol_sha256": digest(p),
                "parcel_ids": p["parcel_ids"], "fits": fits,
                "recipe": "train_only_standardize_pca_whiten_ridge_fixed_rank_alpha",
                "data_scope": "public_development_only", "scientific_qualification": False}
    return predictions, metadata


def pearson_columns(target, prediction):
    """Raw Pearson r per parcel; no clipping negatives or replacing constants."""
    x = target - target.mean(axis=0)
    y = prediction - prediction.mean(axis=0)
    # Scale before squaring, avoiding overflow for valid finite inputs.
    xs, ys = np.max(np.abs(x), axis=0), np.max(np.abs(y), axis=0)
    require(np.all(xs > 0) and np.all(ys > 0), "constant target or prediction parcel")
    x, y = x / xs, y / ys
    r = np.sum(x * y, axis=0) / np.sqrt(np.sum(x * x, axis=0) * np.sum(y * y, axis=0))
    require(np.isfinite(r).all(), "nonfinite correlation")
    return np.clip(r, -1.0, 1.0)


def exact_person_bootstrap(values):
    """All 4**4 ordered resamples; descriptive four-person empirical interval."""
    values = np.asarray(values)
    means = [float(np.mean(values[list(i)])) for i in itertools.product(range(4), repeat=4)]
    return np.quantile(means, [0.025, 0.975], method="linear").tolist()


def score(p, predictions, private_targets, prediction_metadata, private_target_metadata, claims=None):
    validate_protocol(p)
    validate_target_metadata(p, private_target_metadata, "evaluation")
    require(isinstance(prediction_metadata, dict), "prediction metadata must be an object")
    require(prediction_metadata.get("protocol_sha256") == digest(p), "prediction protocol mismatch")
    require(prediction_metadata.get("parcel_ids") == p["parcel_ids"], "prediction parcel order mismatch")
    targets = validate_targets(p, private_targets, "evaluation")
    evaluation = selected_segments(p, split="evaluation")
    expected = {arm + "__" + s["id"] for arm in ARMS for s in evaluation}
    require(set(predictions) == expected, "missing or extra prediction arm/segment IDs")
    pred = {arm + "__" + s["id"]:
            matrix(predictions[arm + "__" + s["id"]], len(kept_rows(p, s)), 1000,
                   arm + "__" + s["id"]) for arm in ARMS for s in evaluation}
    people, null_deltas = {}, {f: [] for f in FAMILIES}
    for person in PEOPLE:
        segments = selected_segments(p, person, "evaluation")
        film_ids = sorted({s["film_id"] for s in segments})
        def correlations_by_film(rep=None):
            by_film = {}
            for film in film_ids:
                movie_segments = [s for s in segments if s["film_id"] == film]
                y = np.concatenate([targets[s["id"]][kept_rows(p, s)] for s in movie_segments])
                by_film[film] = {arm: pearson_columns(y, np.concatenate([
                    pred[arm + "__" + s["id"]] if rep is None else
                    np.roll(pred[arm + "__" + s["id"]], s["null_offsets_tr"][rep], axis=0)
                    for s in movie_segments])) for arm in ARMS}
            return by_film
        by_film = correlations_by_film()
        correlations = {arm: np.mean([by_film[f][arm] for f in film_ids], axis=0) for arm in ARMS}
        deltas = {f: correlations["full"] - correlations["no_" + f] for f in FAMILIES}
        people[person] = {"n_evaluation_rows": sum(len(kept_rows(p, s)) for s in segments),
                          "film_ids": film_ids, "parcel_ids": p["parcel_ids"][person],
                          "film_r_by_arm": {f: {a: r.tolist() for a, r in by_film[f].items()}
                                            for f in film_ids},
                          "r_by_arm": {a: v.tolist() for a, v in correlations.items()},
                          "mean_r_by_arm": {a: float(v.mean()) for a, v in correlations.items()},
                          "delta_by_family": {f: v.tolist() for f, v in deltas.items()},
                          "mean_delta_by_family": {f: float(v.mean()) for f, v in deltas.items()}}
        per_person_null = {f: [] for f in FAMILIES}
        for rep in range(len(segments[0]["null_offsets_tr"])):
            # Identical shift for every arm within each segment preserves pairing.
            shifted = correlations_by_film(rep)
            null_r = {arm: np.mean([shifted[f][arm] for f in film_ids], axis=0) for arm in ARMS}
            for family in FAMILIES:
                per_person_null[family].append(float(np.mean(null_r["full"] - null_r["no_" + family])))
        for family in FAMILIES:
            null_deltas[family].append(per_person_null[family])
    contrasts = {}
    for family in FAMILIES:
        values = [people[person]["mean_delta_by_family"][family] for person in PEOPLE]
        estimate = float(np.mean(values))
        null = np.mean(null_deltas[family], axis=0)
        contrasts[family] = {"mean_delta_r": estimate, "person_deltas": dict(zip(PEOPLE, values)),
                             "person_bootstrap_percentile_95": exact_person_bootstrap(values),
                             "paired_circular_shift_null_deltas": null.tolist(),
                             "two_sided_shift_tail_fraction": float(np.mean(np.abs(null) >= abs(estimate)))}
    verified_claims = []
    if claims is not None:
        require(isinstance(claims, list), "claims must be a list")
        seen = set()
        for claim in claims:
            require(isinstance(claim, dict) and set(claim) == {"family", "mean_delta_r"},
                    "only numerical group mean_delta_r claims are supported")
            family = claim["family"]
            require(family in FAMILIES and family not in seen, "unknown or duplicate claim family")
            seen.add(family)
            number = claim["mean_delta_r"]
            require(type(number) in (int, float) and np.isfinite(number), "claim must be finite numeric")
            actual = contrasts[family]["mean_delta_r"]
            verified_claims.append({"family": family, "reported": number, "recomputed": actual,
                                    "verified": bool(abs(actual - number) <= 1e-8)})
    return {"task_id": TASK, "implementation": VERSION, "protocol_sha256": digest(p),
            "data_scope": "public_development_only", "scientific_qualification": False,
            "native_reference_reproduced": False, "n_people": 4, "n_parcels_per_person": 1000,
            "estimator": "guarded_samples_Pearson_within_film_then_equal_film_parcel_person_means",
            "contrasts": contrasts, "people": people, "claims": verified_claims,
            "holds": HOLDS, "uncertainty_scope": "descriptive empirical resampling of four people",
            "null_scope": "frozen within-segment circular shifts; no exchangeability or multiplicity qualification",
            "fitting_lineage": "metadata is not independent proof of externally supplied prediction lineage"}


def load_json(path):
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result
    with open(path) as stream:
        return json.load(stream, object_pairs_hook=reject_duplicates,
                         parse_constant=lambda x: (_ for _ in ()).throw(ContractError("nonfinite JSON")))


def load_npz(path):
    with np.load(path, allow_pickle=False) as z:
        require(len(z.files) == len(set(z.files)), "duplicate NPZ keys")
        return {k: z[k] for k in z.files}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fit = commands.add_parser("encode")
    fit.add_argument("--protocol", required=True)
    fit.add_argument("--features", required=True)
    fit.add_argument("--training-targets", required=True)
    fit.add_argument("--training-target-metadata", required=True)
    fit.add_argument("--output-dir", required=True)
    evaluate = commands.add_parser("score")
    for option in ("protocol", "predictions", "prediction-metadata", "private-targets",
                   "private-target-metadata", "output"):
        evaluate.add_argument("--" + option, required=True)
    evaluate.add_argument("--claims")
    args = parser.parse_args()
    p = load_json(args.protocol)
    if args.command == "encode":
        target_metadata = load_json(args.training_target_metadata)
        require(target_metadata.get("npz_sha256") == sha256(args.training_targets), "training target hash mismatch")
        predictions, metadata = encode(p, load_npz(args.features), load_npz(args.training_targets), target_metadata)
        directory = Path(args.output_dir)
        directory.mkdir(parents=True, exist_ok=False)
        output = directory / "predictions.npz"
        np.savez(output, **predictions)
        metadata["artifact_sha256"] = {"protocol_file": sha256(args.protocol),
                                      "features": sha256(args.features),
                                      "training_targets": sha256(args.training_targets),
                                      "predictions": sha256(output)}
        write_json(directory / "prediction-metadata.json", metadata)
    else:
        metadata = load_json(args.prediction_metadata)
        target_metadata = load_json(args.private_target_metadata)
        require(target_metadata.get("npz_sha256") == sha256(args.private_targets), "private target hash mismatch")
        require(metadata.get("artifact_sha256", {}).get("predictions") == sha256(args.predictions),
                "prediction NPZ hash mismatch")
        result = score(p, load_npz(args.predictions), load_npz(args.private_targets), metadata,
                       target_metadata, None if args.claims is None else load_json(args.claims))
        result["artifact_sha256"] = {"protocol_file": sha256(args.protocol),
                                     "predictions": sha256(args.predictions),
                                     "private_targets": sha256(args.private_targets)}
        write_json(args.output, result)


if __name__ == "__main__":
    main()
