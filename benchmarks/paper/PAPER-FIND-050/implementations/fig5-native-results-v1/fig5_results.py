"""Read the complete source Figure 5 accuracy triplet without running simulations.

Only the literal notebook layout is supported. Shape/filename agreement and
caller-provided hashes do not prove published-result or paper-method provenance.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import math
from pathlib import Path
import re
import struct
import zipfile

REVISION = "2c15edf4e770165fc3962dcc3920c8bcaf555bed"
FAMILIES = ("symmetric", "nonsymmetric", "echo_state")
PANELS = (("F5d", "acc_multi", 1500, 2000),
          ("F5e", "acc_zero", 1500, 2000),
          ("F5f", "acc_zero_aligned", 4500, 600))
MODES = (("fixed_lag", "acc"), ("time_independent", "acc_shuff"))
MAX_ARCHIVE_BYTES = 131072
MAX_MEMBER_BYTES = 25000


class ResultError(ValueError):
    """Input does not have the complete, explicitly selected native layout."""


def require(condition, message):
    if not condition:
        raise ResultError(message)


def delay_steps(tisi):
    """Exact positive truncation of linspace(60, tisi, 51)[:-1]."""
    require(tisi in (1500, 4500), "unknown source interval")
    return [(60 * 50 + (tisi - 60) * j) // 50 for j in range(50)]


def filenames(role):
    require(role in ("notebook_producer", "notebook_renderer"), "unknown artifact role")
    suffix = "" if role == "notebook_producer" else "2"
    return [stem + suffix + ".npz" for _, stem, _, _ in PANELS]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def read_selection(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(16385)
    require(len(raw) <= 16384, "oversized selection")
    try:
        return json.loads(raw, object_pairs_hook=_unique_object,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              ResultError("nonfinite selection number")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ResultError("invalid selection JSON") from exc


def _npy(raw, *, shape, kind):
    """Bounded numeric NPY 1/2/3 reader; never accepts or loads pickle."""
    require(raw[:6] == b"\x93NUMPY", "invalid NPY magic")
    version = raw[6:8]
    require(version in (b"\x01\x00", b"\x02\x00", b"\x03\x00"), "unsupported NPY version")
    prefix = 10 if version == b"\x01\x00" else 12
    require(len(raw) >= prefix, "truncated NPY header")
    header_size = int.from_bytes(raw[8:prefix], "little")
    require(0 < header_size <= 4096 and prefix + header_size <= len(raw), "invalid NPY header length")
    try:
        encoding = "utf-8" if version == b"\x03\x00" else "latin1"
        header = ast.literal_eval(raw[prefix:prefix + header_size].decode(encoding).strip())
    except (ValueError, SyntaxError, UnicodeError, RecursionError) as exc:
        raise ResultError("invalid literal NPY header") from exc
    require(type(header) is dict and set(header) == {"descr", "fortran_order", "shape"}, "unsupported NPY header")
    require(type(header["shape"]) is tuple and all(type(n) is int for n in header["shape"])
            and header["shape"] == shape, "wrong native array shape")
    require(type(header["fortran_order"]) is bool, "invalid NPY order")
    require(header["fortran_order"] is False, "native source requires C-order arrays")
    dtypes = {"float": {"<f8": "<d", ">f8": ">d"},
              "integer": {"<i4": "<i", ">i4": ">i"}}
    require(type(header["descr"]) is str and header["descr"] in dtypes[kind], "wrong native dtype; objects/pickle forbidden")
    fmt = dtypes[kind][header["descr"]]
    body = raw[prefix + header_size:]
    require(len(body) == math.prod(shape) * struct.calcsize(fmt), "truncated or trailing NPY payload")
    return [value[0] for value in struct.iter_unpack(fmt, body)]


def _archive(raw, interval):
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            require(len(members) == 3 and {m.filename for m in members} ==
                    {"acc.npy", "acc_shuff.npy", "wm_isi.npy"}, "native archive must have exactly three unique arrays")
            require(all(0 < m.file_size <= MAX_MEMBER_BYTES and not (m.flag_bits & 1)
                        and m.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                        for m in members), "unsupported or oversized NPZ member")
            steps = _npy(archive.read("wm_isi.npy"), shape=(50,), kind="integer")
            require(steps == delay_steps(interval), "wrong source delay grid or units")
            values = {name: _npy(archive.read(name + ".npy"), shape=(20, 50, 3), kind="float")
                      for _, name in MODES}
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError) as exc:
        raise ResultError("invalid native NPZ") from exc
    for values_for_mode in values.values():
        require(all(math.isnan(x) or (math.isfinite(x) and 0 <= x <= 1)
                    for x in values_for_mode), "accuracy outside [0,1] or infinite")
    return steps, values


def summarize(input_root, selection):
    """Return complete curves and the source mean/std(0), with failed cells intact.

    Replicate indices are within each family/panel. They are not evidence of
    shared network/noise seeds across independently drawn source families.
    """
    require(type(selection) is dict and set(selection) == {"schema", "artifact_role", "files"}, "selection fields")
    require(selection["schema"] == "fig5-archive-selection/v1", "selection schema")
    role = selection["artifact_role"]
    names = filenames(role)
    records = selection["files"]
    require(type(records) is list and len(records) == 3, "all three panel archives required")
    pins = {}
    for record in records:
        require(type(record) is dict and set(record) == {"name", "bytes", "sha256"}, "file pin fields")
        name = record["name"]
        require(type(name) is str and name in names and name not in pins, "wrong or duplicate panel archive")
        require(type(record["bytes"]) is int and 0 < record["bytes"] <= MAX_ARCHIVE_BYTES, "archive byte bound")
        require(type(record["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", record["sha256"]), "invalid archive digest")
        pins[name] = record

    curves, summaries, failures, panels = [], [], [], []
    input_root = Path(input_root)
    for (panel, _, interval, examples), name in zip(PANELS, names):
        # Hash exactly the bounded bytes that are decoded, never a later reread.
        with (input_root / name).open("rb") as stream:
            raw = stream.read(MAX_ARCHIVE_BYTES + 1)
        require(len(raw) == pins[name]["bytes"] and
                hashlib.sha256(raw).hexdigest() == pins[name]["sha256"], "archive pin mismatch: " + name)
        steps, arrays = _archive(raw, interval)
        panels.append({"panel": panel, "source_archive": name, "delay_steps": steps,
                       "delay_seconds": [step / 500 for step in steps],
                       "notebook_examples": examples, "notebook_examples_per_fold": examples // 2,
                       "rendered_example_count_verified": False})
        for mode, field in MODES:
            values = arrays[field]
            for family_index, family in enumerate(FAMILIES):
                for replicate in range(20):
                    row = [values[(replicate * 50 + lag) * 3 + family_index] for lag in range(50)]
                    failed_lags = [lag for lag, value in enumerate(row) if math.isnan(value)]
                    curves.append({"panel": panel, "mode": mode, "family": family,
                                   "replicate_index": replicate,
                                   "accuracy": [None if math.isnan(x) else x for x in row]})
                    if failed_lags:
                        failures.append({"panel": panel, "mode": mode, "family": family,
                                         "replicate_index": replicate, "delay_indices": failed_lags,
                                         "cause": "not recoverable from NaN result cells"})
                mean, sd, counts = [], [], []
                for lag in range(50):
                    observations = [values[(rep * 50 + lag) * 3 + family_index] for rep in range(20)]
                    finite_count = sum(math.isfinite(x) for x in observations)
                    counts.append(finite_count)
                    if finite_count != 20:
                        mean.append(None)
                        sd.append(None)
                    else:
                        center = math.fsum(observations) / 20
                        mean.append(center)
                        sd.append(math.sqrt(math.fsum((x - center) ** 2 for x in observations) / 20))
                summaries.append({"panel": panel, "mode": mode, "family": family,
                                  "mean_accuracy": mean, "population_sd": sd,
                                  "finite_replicates": counts, "planned_replicates": 20})

    return {"schema": "fig5-native-accuracy-report/v1", "task_id": "PAPER-FIND-050",
            "source_revision": REVISION, "artifact_role": role,
            "input_pins": [pins[name] for name in names],
            "layout": {"panels": 3, "families": 3, "modes": 2, "replicates": 20,
                       "delays_per_curve": 50, "replicate_curves": 360, "accuracy_cells": 18000},
            "panels": panels, "curves": curves, "summaries": summaries,
            "failed_curve_cells": failures,
            "missing_accuracy_cells": sum(len(row["delay_indices"]) for row in failures),
            "numerical_completeness": "required_unscorable" if failures else "complete_native_layout",
            "aggregation": "Per lag mean and population standard deviation over all 20 replicates; any NaN propagates. No across-lag scalar.",
            "qualification": "source-format component only; historical baseline and paper equivalence unresolved",
            "limits": ["Producer acc_*.npz and renderer acc_*2.npz have unresolved lineage; neither role authenticates the published curve.",
                       "Literal aligned caller has 600 examples (300/fold), distinct from paper-described 2000 (1000/fold).",
                       "Literal echo-state gain is 1.35; paper-described gain is 1.4.",
                       "Literal binary centroid decoder, randomized folds, and cumulative in-place time shuffle remain source/prose discrepancies.",
                       "Original RNG states and swallowed exception details are absent from these result archives.",
                       "Replicate index is not a seed identity; paired inference and a paper win are not established."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = summarize(args.input_root, read_selection(args.selection))
    except (ResultError, OSError) as exc:
        parser.exit(2, "Figure 5 results refused: " + str(exc) + "\n")
    print(json.dumps(report, allow_nan=False, separators=(",", ":")))
    return 1 if report["missing_accuracy_cells"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
