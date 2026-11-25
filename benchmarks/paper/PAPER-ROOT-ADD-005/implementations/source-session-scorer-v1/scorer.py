"""Paired source-session Pearson maps for PAPER-ROOT-ADD-005.

Trusted operator scoring only. No fitting, permutation inference, noise-ceiling
conversion, voxel aggregation, empirical admission, or paper-win decision.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

TASK_ID = "PAPER-ROOT-ADD-005"
PARTICIPANTS = ("01", "02", "03")
N_FOLDS = 12
POLICY = "source-ordered-session-mean-pearson-v1"


def strings(value: Any, name: str, *, unique: bool = False) -> np.ndarray:
    raw = np.asarray(value)
    if raw.ndim != 1 or not len(raw) or raw.dtype.kind not in "US":
        raise ValueError(f"{name} must be a nonempty string vector")
    out = raw.astype(str)
    if any(not x or x != x.strip() for x in out):
        raise ValueError(f"{name} contains blank or padded identities")
    if unique and len(set(out)) != len(out):
        raise ValueError(f"{name} contains duplicate identities")
    return out


def matrix(value: Any, name: str, shape: tuple[int, int]) -> np.ndarray:
    raw = np.asarray(value)
    if raw.dtype.kind not in "fiu" or raw.shape != shape:
        raise ValueError(f"{name} must be a numeric matrix with shape {shape}")
    out = raw.astype(np.float64, copy=False)
    if not np.isfinite(out).all():
        raise ValueError(f"{name} contains nonfinite values")
    return out


def reindex(actual: Any, expected: np.ndarray, name: str) -> np.ndarray:
    """Exact identity bijection: repeated stimuli never become repeated trial IDs."""
    actual = strings(actual, name, unique=True)
    if set(actual) != set(expected):
        raise ValueError(f"{name} differs from the full operator roster")
    index = {key: i for i, key in enumerate(actual)}
    return np.array([index[key] for key in expected], dtype=np.int64)


def source_folds(session_ids: Any) -> list[np.ndarray]:
    """Require the original unshuffled 12-fold KFold to hold out whole sessions.

    Do not sort rows to repair a mismatch: original response order is scientific
    evidence. KFold gives one extra row to each of its first N % 12 folds.
    """
    sessions = strings(session_ids, "session_ids")
    if len(set(sessions)) != N_FOLDS or len(sessions) < 2 * N_FOLDS:
        raise ValueError("Exactly 12 sessions with at least two rows per fold are required")
    folds = list(np.array_split(np.arange(len(sessions)), N_FOLDS))
    labels = []
    for indices in folds:
        labels_here = np.unique(sessions[indices])
        if len(labels_here) != 1:
            raise ValueError("Original contiguous KFold boundary splits or mixes sessions")
        labels.append(labels_here[0])
    if len(set(labels)) != N_FOLDS:
        raise ValueError("A session appears in more than one original KFold")
    return folds


def pearson_columns(observed: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    """Signed Pearson correlations, NaN for zero-variance columns.

    Remove a finite anchor before scaling, preserving representable variation
    near a common offset without overflowing products. This is the source Pearson estimator;
    floating-point execution is independent of the author's implementation.
    """
    observed = np.asarray(observed, dtype=np.float64)
    predicted = np.asarray(predicted, dtype=np.float64)
    if observed.shape != predicted.shape or observed.ndim != 2 or len(observed) < 2:
        raise ValueError("Pearson inputs must be aligned row-by-voxel matrices")
    if not np.isfinite(observed).all() or not np.isfinite(predicted).all():
        raise ValueError("Pearson inputs must be finite")

    def centered_unit(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        # Raw-value scaling before centering can distort almost-constant
        # columns. Anchor subtraction preserves their representable variation.
        with np.errstate(over="ignore", invalid="ignore"):
            shifted = x - x[:1]
        overflow = ~np.isfinite(shifted).all(axis=0)
        if np.any(overflow):
            # Half-scale only wide-span columns; avoid underflow in unrelated
            # subnormal columns sharing the same matrix.
            shifted[:, overflow] = x[:, overflow] * 0.5 - x[:1, overflow] * 0.5
        amplitude = np.max(np.abs(shifted), axis=0)
        scaled = shifted / np.where(amplitude == 0, 1.0, amplitude)
        centered = scaled - scaled.mean(axis=0)
        norm = np.sqrt(np.sum(centered * centered, axis=0))
        defined = np.any(x != x[:1], axis=0)
        if np.any(defined & (norm == 0)):
            raise ValueError("Pearson precision loss in a nonconstant column")
        return centered / np.where(norm == 0, 1.0, norm), defined

    y, y_defined = centered_unit(observed)
    p, p_defined = centered_unit(predicted)
    result = np.sum(y * p, axis=0)
    result[~(y_defined & p_defined)] = np.nan
    return result


def json_values(values: np.ndarray) -> list:
    if values.ndim == 1:
        return [float(x) if np.isfinite(x) else None for x in values]
    return [json_values(row) for row in values]


def score_maps(observed: np.ndarray, author: np.ndarray, candidate: np.ndarray,
               session_ids: Any) -> dict[str, Any]:
    """Score the identical trials and voxels; retain source equal-fold weighting."""
    folds = source_folds(session_ids)
    if observed.ndim != 2 or observed.shape != author.shape or observed.shape != candidate.shape:
        raise ValueError("All three arrays must have identical row-by-voxel shapes")
    if len(observed) != sum(map(len, folds)) or observed.shape[1] == 0:
        raise ValueError("Response shape disagrees with sessions or contains no voxels")
    author_r = np.stack([pearson_columns(observed[i], author[i]) for i in folds])
    candidate_r = np.stack([pearson_columns(observed[i], candidate[i]) for i in folds])
    author_mean = author_r.mean(axis=0)
    candidate_mean = candidate_r.mean(axis=0)
    return {
        "author_fold_pearson_r": json_values(author_r),
        "candidate_fold_pearson_r": json_values(candidate_r),
        "author_mean_fold_pearson_r": json_values(author_mean),
        "candidate_mean_fold_pearson_r": json_values(candidate_mean),
        "paired_mean_fold_delta_r": json_values(candidate_mean - author_mean),
        "author_defined_folds_per_voxel": np.isfinite(author_r).sum(axis=0).tolist(),
        "candidate_defined_folds_per_voxel": np.isfinite(candidate_r).sum(axis=0).tolist(),
    }


def validate_roster(roster: dict[str, Any]) -> dict[str, dict[str, np.ndarray]]:
    if roster.get("task_id") != TASK_ID or roster.get("schema_version") != POLICY:
        raise ValueError("Wrong task or roster schema")
    records = roster.get("participants", {})
    if set(records) != set(PARTICIPANTS):
        raise ValueError("The operator roster must contain exactly participants 01, 02, 03")
    result = {}
    for sub in PARTICIPANTS:
        entry = records[sub]
        if set(entry) != {"trial_ids", "stimulus_ids", "session_ids", "voxel_ids"}:
            raise ValueError(f"Unexpected or missing roster fields for participant {sub}")
        result[sub] = {
            key: strings(entry[key], f"sub-{sub}.{key}", unique=key in {"trial_ids", "voxel_ids"})
            for key in entry
        }
        nrows = len(result[sub]["trial_ids"])
        if any(len(result[sub][key]) != nrows for key in ("stimulus_ids", "session_ids")):
            raise ValueError(f"Stimulus/session roster lengths disagree for participant {sub}")
        source_folds(result[sub]["session_ids"])
    return result


def bind_archive(bundle: dict[str, Any], roster: dict[str, dict[str, np.ndarray]],
                 *, reference: bool) -> dict[str, np.ndarray]:
    common = {"trial_id", "voxel_id"}
    fields = common | ({"stimulus_id", "session_id", "response"} if reference
                       else {"heldout_session_id", "prediction"})
    expected_keys = {f"sub_{sub}_{field}" for sub in PARTICIPANTS for field in fields}
    if set(bundle) != expected_keys:
        raise ValueError("Archive keys must cover exactly all three participants and specified fields")
    output = {}
    for sub in PARTICIPANTS:
        prefix = f"sub_{sub}_"
        record = roster[sub]
        rows = reindex(bundle[prefix + "trial_id"], record["trial_ids"], prefix + "trial_id")
        columns = reindex(bundle[prefix + "voxel_id"], record["voxel_ids"], prefix + "voxel_id")
        metadata = {"stimulus_id": "stimulus_ids", "session_id": "session_ids"} if reference else {
            "heldout_session_id": "session_ids"}
        for actual, expected in metadata.items():
            labels = strings(bundle[prefix + actual], prefix + actual)
            if len(labels) != len(rows) or not np.array_equal(labels[rows], record[expected]):
                raise ValueError(f"Trial-aligned {actual} disagrees with source roster for {sub}")
        key = prefix + ("response" if reference else "prediction")
        values = matrix(bundle[key], key, (len(rows), len(columns)))
        output[sub] = values[np.ix_(rows, columns)]
    return output


def evaluate(roster: dict[str, Any], reference: dict[str, Any],
             author: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    bound = validate_roster(roster)
    # Complete all identity/finite-value validation before calculating any scores.
    y = bind_archive(reference, bound, reference=True)
    a = bind_archive(author, bound, reference=False)
    c = bind_archive(candidate, bound, reference=False)
    participants = {}
    for sub in PARTICIPANTS:
        record = bound[sub]
        folds = source_folds(record["session_ids"])
        participants[sub] = {
            "voxel_ids": record["voxel_ids"].tolist(),
            "trial_count": len(record["trial_ids"]),
            "unique_stimulus_count": len(set(record["stimulus_ids"])),
            "voxel_count": len(record["voxel_ids"]),
            "folds": [{"heldout_session_id": str(record["session_ids"][i[0]]),
                       "start_row": int(i[0]), "stop_row_exclusive": int(i[-1]) + 1,
                       "trial_count": len(i)} for i in folds],
            **score_maps(y[sub], a[sub], c[sub], record["session_ids"]),
        }
    return {
        "task_id": TASK_ID, "policy": POLICY, "participants": participants,
        "aggregation": "arithmetic mean of 12 signed within-fold Pearson correlations per voxel",
        "qualification": "source-metric software component; authentic source panel and author execution unqualified",
        "paper_win": None,
        "limits": [
            "An operator-supplied roster establishes internal identity completeness, not authentic cohort/mask provenance.",
            "Heldout-session labels cannot establish prediction training history or protected candidate access.",
            "No noise-ceiling conversion, scalar voxel/participant aggregation, uncertainty, permutation p values, or paper-win rule is implemented.",
            "No source-author inference or candidate experiment is performed by this scorer.",
        ],
    }


def load_npz(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as archive:
        if len(set(archive.files)) != len(archive.files):
            raise ValueError("Duplicate NPZ entries are not permitted")
        return {key: archive[key] for key in archive.files}


def digest_stream(stream) -> str:
    """Hash the same retained file description used by the decoder."""
    sha = hashlib.sha256()
    stream.seek(0)
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        sha.update(block)
    stream.seek(0)
    return sha.hexdigest()


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return digest_stream(stream)


def file_identity(stream) -> tuple[int, ...]:
    stat = os.fstat(stream.fileno())
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def parse_roster(text: str) -> dict[str, Any]:
    def unique_object(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f"Duplicate JSON key: {key}")
            out[key] = value
        return out

    roster = json.loads(text, object_pairs_hook=unique_object)
    if not isinstance(roster, dict):
        raise ValueError("Roster must be a JSON object")
    return roster


def load_roster(path: Path) -> dict[str, Any]:
    return parse_roster(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("roster", "reference", "author", "candidate", "output"):
        parser.add_argument("--" + key, required=True, type=Path)
    args = parser.parse_args()
    inputs = {key: getattr(args, key) for key in ("roster", "reference", "author", "candidate")}
    if args.output.resolve() in {path.resolve() for path in inputs.values()}:
        raise ValueError("Output must not overwrite an input")
    # Retain each opened input through both hashes and decoding. Reopening a
    # pathname would permit replacement bytes to be scored between equal hashes.
    with ExitStack() as stack:
        streams = {key: stack.enter_context(path.open("rb")) for key, path in inputs.items()}
        identities = {key: file_identity(stream) for key, stream in streams.items()}
        hashes = {key: digest_stream(stream) for key, stream in streams.items()}
        roster = parse_roster(streams["roster"].read().decode("utf-8"))
        arrays = {key: load_npz(streams[key]) for key in ("reference", "author", "candidate")}
        if (hashes != {key: digest_stream(stream) for key, stream in streams.items()}
                or identities != {key: file_identity(stream) for key, stream in streams.items()}):
            raise ValueError("An input changed while it was being loaded")
    result = evaluate(roster, **arrays)
    result["input_sha256"] = hashes
    # Exclusive create preserves previous operator evidence on accidental reruns.
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
