"""Operator-only projection of prepared NEURAL-001 arrays to opaque packets.

No raw-source loading, preprocessing, fitting, normalization, targets, or provider
calls. Call only after authorized native preparation establishes source identity,
the 3 ms alignment and complete retained support. This is not a sandbox.
"""
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import zipfile

import numpy as np

PEOPLE = tuple(f"sub-{i:02d}" for i in range(1, 25))
RUNS = tuple(f"task-audiobook{book}_run-0{run}" for book in (1, 2) for run in (1, 2))
MAX_TRAIN_ROWS = 250000
MAX_QUERY_ROWS = 61440
DOMAIN = "NEURAL-001/opaque-delivery-v1"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _array(value, dtype, shape, label):
    require(type(value) is np.ndarray and value.dtype.str == dtype and
            value.shape == shape and value.flags.c_contiguous, f"Exact {label} dtype/shape/order")
    require(np.isfinite(value).all(), f"Finite {label}")


def _offsets(value, rows, count=None):
    require(type(value) is np.ndarray and value.dtype.str == "<i8" and value.ndim == 1 and
            (count is None or len(value) == count + 1) and len(value) >= 3 and
            value[0] == 0 and value[-1] == rows and np.all(np.diff(value) >= 4),
            "Complete interval support; no cropping or artificial padding")


def _channels(value):
    require(type(value) in (tuple, list) and len(value) == 306 and len(set(value)) == 306 and
            all(type(x) is str and re.fullmatch(r"MEG[0-9]{3}[123]", x) for x in value),
            "Original ordered 306 MEG labels only")
    kinds = ["mag" if x.endswith("1") else "grad" for x in value]
    require(kinds.count("mag") == 102 and kinds.count("grad") == 204,
            "102 magnetometers and 204 gradiometers")
    return kinds


def _digest(secret, person, kind, identity):
    message = json.dumps([DOMAIN, person, kind, identity], separators=(",", ":")).encode("ascii")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _alias(secret, person, kind, identity):
    # All aliases are 31 characters, within the predecessor's <U32 contract.
    return kind[0] + _digest(secret, person, kind, identity)[:30]


def reorder_intervals(values, offsets, source_indices):
    """Lossless whole-interval permutation; usable separately for protected targets.

    Indices are zero-based and must be a full permutation. Targets must already
    have the same source-order support. Never infer trimming from target values.
    """
    require(type(values) is np.ndarray and values.ndim in (1, 2), "One vector or samples-by-channel array")
    _offsets(offsets, len(values))
    count = len(offsets) - 1
    require(type(source_indices) in (tuple, list) and len(source_indices) == count and
            all(type(i) is int for i in source_indices) and set(source_indices) == set(range(count)),
            "Every source interval exactly once")
    lengths = [int(offsets[i + 1] - offsets[i]) for i in source_indices]
    output = np.concatenate([values[offsets[i]:offsets[i + 1]] for i in source_indices], axis=0)
    return output, np.asarray([0] + list(np.cumsum(lengths)), dtype="<i8")


@dataclass(frozen=True)
class Projection:
    """Trusted operator object: includes a private mapping, never give to actors."""
    person_alias: str
    training: dict
    queries: dict
    record: dict
    private_mapping: dict


def project_person(person, training, queries, *, secret):
    """Project one complete native-prepared person, without opening any targets.

    training: meg[N,306], envelope[N], offsets[E+1], source_run_ids[E],
    source_epoch_numbers[E] (original positive numbers, retained after native
    rejection), channel_labels[306], fs_hz=64. Query source_trial_indices must be
    exactly 1..120 in source event order; do not pass a filtered/reordered table.
    """
    require(person in PEOPLE, "Canonical operator-side participant")
    require(type(secret) is bytes and len(secret) >= 32, "Private alias key of at least 32 bytes")
    require(type(training) is dict and set(training) == {"meg", "envelope", "offsets", "source_run_ids",
            "source_epoch_numbers", "channel_labels", "fs_hz"}, "Exact native training adapter fields")
    require(type(queries) is dict and set(queries) == {"meg", "offsets", "source_trial_indices",
            "channel_labels", "fs_hz"}, "Exact native query adapter fields; no target or event metadata")
    require(type(training["fs_hz"]) is int and type(queries["fs_hz"]) is int and
            training["fs_hz"] == queries["fs_hz"] == 64, "Prepared 64 Hz observations")
    labels = training["channel_labels"]
    kinds = _channels(labels)
    require(list(queries["channel_labels"]) == list(labels), "Identical original channel order")
    for source, cap in ((training, MAX_TRAIN_ROWS), (queries, MAX_QUERY_ROWS)):
        meg = source["meg"]
        require(type(meg) is np.ndarray and meg.ndim == 2 and 4 <= len(meg) <= cap,
                "Complete rows within provisional cap; exceeding cap is not crop authority")
        _array(meg, "<f8", (len(meg), 306), "MEG")
        _offsets(source["offsets"], len(meg), 120 if source is queries else None)
    _array(training["envelope"], "<f8", (len(training["meg"]),), "training envelope")
    runs, numbers = training["source_run_ids"], training["source_epoch_numbers"]
    count = len(training["offsets"]) - 1
    require(type(runs) in (tuple, list) and type(numbers) in (tuple, list) and len(runs) == len(numbers) == count,
            "Native retained epoch/run mapping")
    expected_runs = RUNS[:2] if person == "sub-01" else RUNS
    require(set(runs) == set(expected_runs), "All original released runs required (2 for sub-01, 4 otherwise)")
    require(all(type(i) is int and i > 0 for i in numbers) and len(set(zip(runs, numbers))) == count,
            "Unique original epoch identity within each run")
    expected_keys = sorted(zip(runs, numbers), key=lambda pair: (RUNS.index(pair[0]), pair[1]))
    require(list(zip(runs, numbers)) == expected_keys, "Preserve native training run and retained epoch order")
    trials = queries["source_trial_indices"]
    require(type(trials) in (tuple, list) and all(type(i) is int for i in trials) and
            list(trials) == list(range(1, 121)), "All 120 source trials in original event order")

    run_aliases = {run: _alias(secret, person, "run", run) for run in expected_runs}
    epoch_aliases = [_alias(secret, person, "epoch", [run, number]) for run, number in zip(runs, numbers)]
    query_aliases = [_alias(secret, person, "query", i) for i in range(1, 121)]
    person_alias = _alias(secret, person, "person", person)
    aliases = [person_alias] + list(run_aliases.values()) + epoch_aliases + query_aliases
    require(len(set(aliases)) == len(aliases), "Alias collision; use a new private key")
    order = sorted(range(120), key=lambda i: _digest(secret, person, "presentation", i + 1))
    # Both the labels and ordering depend on source identity and the secret only,
    # never on MEG, targets, sentence identity, SNR, intelligibility, or duration.
    meg, offsets = reorder_intervals(queries["meg"], queries["offsets"], order)
    ordered_query_ids = [query_aliases[i] for i in order]
    public_training = {
        "meg": training["meg"].copy(), "envelope": training["envelope"].copy(),
        "offsets": training["offsets"].copy(), "interval_ids": np.asarray(epoch_aliases, dtype="<U32"),
        "run_ids": np.asarray([run_aliases[run] for run in runs], dtype="<U32"),
        "channel_labels": np.asarray(labels, dtype="<U16"),
    }
    public_queries = {"meg": meg, "offsets": offsets,
                      "interval_ids": np.asarray(ordered_query_ids, dtype="<U32"),
                      "channel_labels": np.asarray(labels, dtype="<U16")}
    record = {
        "subject": {"id": person, "query_ids": ordered_query_ids, "query_offsets": offsets.tolist(),
                    "query_samples": len(meg)},
        "training": {"samples": len(training["meg"]), "epoch_ids": epoch_aliases,
                     "epoch_runs": [run_aliases[run] for run in runs],
                     "epoch_lengths": np.diff(training["offsets"]).tolist(),
                     "run_ids": [run_aliases[run] for run in expected_runs],
                     "channel_labels": list(labels), "channel_kinds": kinds},
        "queries": {"channel_labels": list(labels)},
    }
    private = {
        "schema": DOMAIN, "canonical_person": person, "person_alias": person_alias,
        "source_query_offsets": queries["offsets"].tolist(), "projected_query_offsets": offsets.tolist(),
        "projected_to_source_zero_based": order,
        "queries": [{"opaque_id": query_aliases[i], "source_trial_one_based": i + 1} for i in order],
        "epochs": [{"opaque_id": alias, "source_run": run, "source_epoch_one_based": number,
                    "opaque_run_id": run_aliases[run]} for alias, run, number in zip(epoch_aliases, runs, numbers)],
    }
    return Projection(person_alias, public_training, public_queries, record, private)


def _write_npz(path, arrays):
    # Stable headers, member order and timestamps yield reproducible identities.
    with path.open("xb") as output:
        os.chmod(path, 0o600)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, array in arrays.items():
                info = zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o100600 << 16
                with archive.open(info, "w", force_zip64=True) as member:
                    np.lib.format.write_array(member, np.ascontiguousarray(array), version=(1, 0), allow_pickle=False)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": path.parent.name + "/" + path.name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def write_projection(projection, packet_root, custody_root):
    """Write new operator files beneath two distinct, non-nested external roots.

    Neither root is a candidate mount. PacketStore later serializes individual
    allowed views. All24 records must be validated together before delivery. The
    private map and secret must never enter public Git or participant transport.
    """
    require(type(projection) is Projection, "A prepared projection")
    roots = [Path(root).resolve(strict=True) for root in (packet_root, custody_root)]
    require(all(root.is_dir() for root in roots) and roots[0] != roots[1] and
            roots[0] not in roots[1].parents and roots[1] not in roots[0].parents,
            "Separate existing packet/custody roots")
    destinations = [root / projection.person_alias for root in roots]
    require(not any(path.exists() or path.is_symlink() for path in destinations), "Never overwrite an existing projection")
    made = []
    try:
        for path in destinations:
            path.mkdir(mode=0o700)
            made.append(path)
        record = json.loads(json.dumps(projection.record))
        record["training"]["pin"] = _write_npz(destinations[0] / "training.npz", projection.training)
        record["queries"]["pin"] = _write_npz(destinations[0] / "queries.npz", projection.queries)
        private = dict(projection.private_mapping, prepared_file_pins={
            name: record[name]["pin"] for name in ("training", "queries")})
        private_path = destinations[1] / "identity.json"
        with private_path.open("x", encoding="utf-8") as stream:
            os.chmod(private_path, 0o600)
            json.dump(private, stream, indent=2, sort_keys=True)
            stream.write("\n")
        return record
    except BaseException:
        for path in reversed(made):
            shutil.rmtree(path)
        raise
