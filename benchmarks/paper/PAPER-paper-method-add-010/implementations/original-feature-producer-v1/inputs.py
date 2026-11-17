"""Authenticate the full release and prepare its selected original MEG windows.

The released rows are known-category epoch averages, not individual trials.
Only parsing and keyed ordering happen here; no feature or model is computed.
"""
from __future__ import annotations

from contextlib import contextmanager
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import stat
import zipfile

import numpy as np

HERE = Path(__file__).resolve().parent
TASK = "PAPER-paper-method-add-010"
REGIONS = ("Category_Selective", "IPS", "Prefrontal_Cortex", "V1_V2")
STIMULI = ("False", "face", "letter", "object")
RELEVANCES = ("Irrelevant", "Relevant non-target", "Relevant target")
FIELDS = ("stimulus_type", "relevance_type", "duration", "times") + REGIONS
GRID_MS = tuple(range(-500, 2001))
ON_MS = tuple(range(1000))
SOURCE_MISSING_GROUPS = {"CB027": (("Relevant target", "False"),),
                         "CB042": (("Relevant target", "face"),)}
ARCHIVE = {"bytes": 220609250,
           "sha256": "79308086f1c6eed01d1bee27d75220778a90283f4ef14aa535afb971d2764904",
           "md5": "c7d3a97c229d97ec174582653cd4a8ba"}
ARCHIVE_ENTRIES = 350
SELECTED_EXPANDED_BYTES = 345354727
SOURCE_URL = "https://zenodo.org/api/records/18294156/files/empirical.zip/content"
SHAPE = (4, 4, 1000)  # source stimulus, region, physical time


class InputError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InputError(message)


def roster():
    spec = importlib.util.spec_from_file_location("fc_source_score", HERE.parent / "original-fold-score-v1" / "score.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(module.published_participants())


def source_member(participant):
    return f"empirical/MEG_time_series/sub-{participant}_ses-1_meg_1000ms_all_time_series.csv"


def pin_stream(stream):
    sha, md5, size = hashlib.sha256(), hashlib.md5(), 0
    maximum = os.fstat(stream.fileno()).st_size
    while True:
        body = stream.read(min(1024 * 1024, maximum - size + 1))
        if not body:
            break
        size += len(body)
        require(size <= maximum, "source grew beyond checked file extent")
        sha.update(body)
        md5.update(body)
    return {"bytes": size, "sha256": sha.hexdigest(), "md5": md5.hexdigest()}


@contextmanager
def ordinary_file(path, max_bytes):
    """Keep one checked descriptor through hash and parse; detect mutations."""
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                "single-link ordinary source file required")
        require(0 < before.st_size <= max_bytes, "source file exceeds bound or is empty")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            yield stream
        after = os.fstat(fd)
        require(all(getattr(before, key) == getattr(after, key) for key in
                    ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")),
                "source file changed while reading")
    finally:
        os.close(fd)


def pin_file(path, max_bytes):
    with ordinary_file(path, max_bytes) as stream:
        return pin_stream(stream)


def fresh_directory(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), "symlink output path")
    require(not path.exists(), "fresh output directory required; partial attempts are retained")
    path.mkdir()
    return path


def read_json(path, max_bytes, *, with_pin=False):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def nonfinite(value):
        raise InputError("nonfinite JSON value: " + value)
    with ordinary_file(path, max_bytes) as stream:
        identity = pin_stream(stream) if with_pin else None
        stream.seek(0)
        value = json.load(stream, object_pairs_hook=unique, parse_constant=nonfinite)
    return (value, identity) if with_pin else value


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def decode_csv(stream, participant):
    """Check every released coordinate and retain the original 0..999ms window.

    Source times are seconds. The full census is -500..2000ms inclusive; the
    source `<1000ms` ON mask keeps exactly 1000 samples, including time zero.
    Known absent *target* conditions do not license missing irrelevant rows.
    """
    require(participant in roster(), "unknown published participant")
    reader = csv.DictReader(stream)
    require(tuple(reader.fieldnames or ()) == FIELDS, "exact source CSV header required")
    seen = np.zeros((3, 4, len(GRID_MS)), dtype=bool)
    expected = np.ones_like(seen)
    for relevance, stimulus in SOURCE_MISSING_GROUPS.get(participant, ()):
        expected[RELEVANCES.index(relevance), STIMULI.index(stimulus), :] = False
    selected = np.empty(SHAPE, dtype="<f8")
    category_order = []
    row_count = 0
    for row in reader:
        require(set(row) == set(FIELDS) and all(v is not None for v in row.values()),
                "extra or missing CSV field")
        require(row["duration"] == "1000ms", "source duration must be 1000ms")
        try:
            ri = RELEVANCES.index(row["relevance_type"])
            si = STIMULI.index(row["stimulus_type"])
            seconds = float(row["times"])
            require(math.isfinite(seconds), "nonfinite time")
            ms = round(seconds * 1000)
            require(abs(seconds * 1000 - ms) <= 1e-6, "source time is off millisecond grid")
            require(-500 <= ms <= 2000, "source time is outside released grid")
            values = [float(row[region]) for region in REGIONS]
        except (KeyError, OverflowError, TypeError, ValueError) as exc:
            raise InputError("invalid source coordinate or signal: " + str(exc)) from exc
        require(all(math.isfinite(x) for x in values), "nonfinite source signal")
        ti = ms + 500
        require(not seen[ri, si, ti], "duplicate condition/time coordinate")
        require(expected[ri, si, ti], "unexpected row in census-absent target condition")
        seen[ri, si, ti] = True
        row_count += 1
        if row["stimulus_type"] not in category_order:
            category_order.append(row["stimulus_type"])
        if ri == 0 and 0 <= ms < 1000:
            selected[si, :, ms] = values
    require(np.array_equal(seen, expected), "incomplete full source condition/time support")
    require(set(category_order) == set(STIMULI), "missing source category")
    return selected, {"participant": participant, "source_rows": row_count,
                      "category_first_occurrence": category_order,
                      "known_absent_target_groups": SOURCE_MISSING_GROUPS.get(participant, ())}


@contextmanager
def authenticated_archive(path):
    """Authenticate the complete ZIP before interpreting any CSV body."""
    with ordinary_file(path, ARCHIVE["bytes"]) as stream:
        require(pin_stream(stream) == ARCHIVE, "complete release archive identity mismatch")
        stream.seek(0)
        with zipfile.ZipFile(stream) as zipped:
            infos = zipped.infolist()
            require(len(infos) == ARCHIVE_ENTRIES and len({i.filename for i in infos}) == len(infos),
                    "original archive entry count/uniqueness mismatch")
            selected = {source_member(p) for p in roster()}
            selected_infos = [i for i in infos if i.filename in selected]
            require(len(selected_infos) == 94, "all94 original CSV members required")
            require(sum(i.file_size for i in selected_infos) == SELECTED_EXPANDED_BYTES,
                    "original CSV expansion mismatch")
            for info in selected_infos:
                require(not info.is_dir() and not (info.flag_bits & 1) and
                        0 < info.file_size <= 5_000_000 and info.compress_type == zipfile.ZIP_DEFLATED,
                        "unsupported source member size/type/compression")
            yield zipped


def prepare(archive_path, output):
    """Prepare all94 participants, with no DTW, fitting or scientific scores."""
    records = []
    with authenticated_archive(archive_path) as zipped:
        output = fresh_directory(output)
        for participant in roster():
            member = source_member(participant)
            with zipped.open(member) as stream:
                values, details = decode_csv(io.TextIOWrapper(stream, encoding="utf-8-sig", newline=""), participant)
            path = output / f"{participant}.npy"
            with path.open("xb") as stream:
                np.save(stream, values, allow_pickle=False)
            records.append({**details, "source_member": member, "file": path.name,
                            "shape": list(SHAPE), "dtype": "<f8", "pin": pin_file(path, 130000)})
    binding = {"schema": "meg_original_selected_windows_v1", "task_id": TASK,
               "archive": ARCHIVE, "source_url": SOURCE_URL,
               "participants": list(roster()), "regions": list(REGIONS), "stimuli": list(STIMULI),
               "relevance": "Irrelevant", "data_type": "Raw", "duration": "1000ms",
               "physical_time_ms": list(ON_MS), "files": records,
               "observation_unit": "known-category epoch-averaged regional time series",
               "row_order": "published roster then each CSV's first stimulus occurrence; newly declared, not historical glob order",
               "operation": "full CSV coordinate validation, float64 parsing, exact original ON masking and keyed ordering only",
               "historical_folds_authenticated": False, "feature_computations": 0, "model_fits": 0}
    write_json(output / "INPUT_BINDING.json", binding)
    return {"participants": 94, "category_windows": 376, "samples_per_region_window": 1000,
            "prepared_bytes": sum(r["pin"]["bytes"] for r in records),
            "binding": pin_file(output / "INPUT_BINDING.json", 262144),
            "feature_computations": 0, "model_fits": 0}


def prepared_binding(directory, *, with_pin=False):
    directory = Path(directory)
    require(not directory.is_symlink(), "symlink prepared directory")
    binding, identity = read_json(directory / "INPUT_BINDING.json", 262144, with_pin=True)
    require(binding.get("schema") == "meg_original_selected_windows_v1" and binding.get("task_id") == TASK,
            "wrong prepared input schema/task")
    require(binding.get("archive") == ARCHIVE and binding.get("participants") == list(roster()),
            "complete original archive/participant binding required")
    require(binding.get("regions") == list(REGIONS) and binding.get("stimuli") == list(STIMULI)
            and binding.get("physical_time_ms") == list(ON_MS) and binding.get("relevance") == "Irrelevant"
            and binding.get("data_type") == "Raw" and binding.get("duration") == "1000ms",
            "source window, modality, category or ROI mapping mismatch")
    records = binding.get("files")
    require(isinstance(records, list) and len(records) == 94, "all94 prepared records required")
    require([r.get("participant") for r in records] == list(roster()), "prepared roster order mismatch")
    for r in records:
        p = r["participant"]
        require(r.get("file") == f"{p}.npy" and r.get("source_member") == source_member(p),
                "prepared/source participant identity mismatch")
        require(r.get("shape") == list(SHAPE) and r.get("dtype") == "<f8", "prepared shape/dtype mismatch")
        order = r.get("category_first_occurrence")
        require(isinstance(order, list) and len(order) == 4 and set(order) == set(STIMULI), "category order mismatch")
        require(r.get("source_rows") == (12 - len(SOURCE_MISSING_GROUPS.get(p, ()))) * 2501,
                "full source row census mismatch")
        expected_missing = [list(x) for x in SOURCE_MISSING_GROUPS.get(p, ())]
        require(r.get("known_absent_target_groups") == expected_missing, "absent target groups changed")
    return (binding, identity) if with_pin else binding


def load_prepared(directory, record):
    """Check exact per-person bytes before allocating the small source array."""
    inputs_name = record["file"]
    require(isinstance(inputs_name, str) and Path(inputs_name).name == inputs_name
            and inputs_name.endswith(".npy"), "local prepared NPY filename required")
    with ordinary_file(Path(directory) / record["file"], 130000) as stream:
        require(pin_stream(stream) == record["pin"], "prepared array identity mismatch")
        stream.seek(0)
        version = np.lib.format.read_magic(stream)
        require(version in ((1, 0), (2, 0)), "unsupported prepared NPY version")
        reader = (np.lib.format.read_array_header_1_0 if version == (1, 0)
                  else np.lib.format.read_array_header_2_0)
        shape, fortran, dtype = reader(stream, max_header_size=10000)
        require(shape == SHAPE and dtype.str == "<f8" and not fortran,
                "prepared NPY header shape/dtype/order mismatch")
        require(os.fstat(stream.fileno()).st_size == stream.tell() + math.prod(SHAPE) * 8,
                "prepared NPY payload extent mismatch")
        stream.seek(0)
        array = np.load(stream, allow_pickle=False)
        require(array.shape == SHAPE and array.dtype.str == "<f8", "prepared array shape/dtype mismatch")
        require(bool(np.isfinite(array).all()), "nonfinite prepared array")
        require(stream.read(1) == b"", "trailing prepared-array bytes")
        return array
