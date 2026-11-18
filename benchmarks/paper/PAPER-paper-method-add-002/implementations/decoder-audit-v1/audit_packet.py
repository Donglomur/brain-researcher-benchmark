"""Optional original-linear-readout evidence bound to an unchanged score packet.

This verifies supplied-input arithmetic and source support, not honest fitting,
historical provenance, isolated execution, or a scientific reproduction/improvement.
Other candidate algorithms may continue using the original prediction interface.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat

import numpy as np

HERE = Path(__file__).resolve().parent
BRIDGE_SHA256 = "c5a56e942273fb90805fc939910612a4f0cbe922ddb28dd5b5a36254c0938396"
AUDITED_PRODUCER_SHA256 = "df9534b38bc0caeae4811960b4487f30c64e4350f2b1d98b76a41d6eb1a7184c"


def _load(name, path, expected):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("dependency identity differs: " + name)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


b = _load("slice_audit_original_bridge", HERE.parent / "submission-bridge-v1/bridge.py", BRIDGE_SHA256)
a = _load("slice_audited_producer", HERE / "audited_producer.py", AUDITED_PRODUCER_SHA256)
SCHEMA = "slicetca-original-linear-readout-audit-v1"
FEATURES = 182
MAX_MANIFEST_BYTES = 16 * 1024**2
MAX_PACKET_BYTES = 512 * 1024**2
MAX_DECODED_BYTES = 512 * 1024**2
TOLERANCE = {"rtol": 1e-10, "atol": 1e-10}
SINGLE_FIELDS = ("weight", "bias", "displacement", "train_indices")
HALF_FIELDS = ("weight", "bias", "displacement", "neural_train_mean", "neural_test_mean",
               "movement_train_mean", "group_counts")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def _close(actual, expected, name):
    actual = b.real(actual, name, np.asarray(expected).shape)
    need(np.allclose(actual, expected, **TOLERANCE), "arithmetic differs: " + name)


def _same(actual, expected, name):
    need(np.array_equal(np.asarray(actual), np.asarray(expected)), "exact values differ: " + name)


def _shape_keys(counts):
    need(set(counts) == set(b.e.CONDITIONS), "both condition-average groups required")
    shapes = {}
    for model in b.MODELS:
        for reach, (lo, hi) in b.e.CONDITIONS.items():
            width = (hi - lo) // 5
            prefix = f"single/{model}/{reach}/"
            shapes.update({prefix + "weight": (20, 5, 2, FEATURES),
                           prefix + "bias": (20, 5, 2),
                           prefix + "displacement": (20, 5, 79, width, 2),
                           prefix + "train_indices": (20, 5, hi - lo - width)})
    for reach, (lo, hi) in b.e.CONDITIONS.items():
        count = counts[reach]
        need(type(count) is int and 1 <= count <= hi - lo, "invalid condition group count")
        prefix = f"averaged/{reach}/"
        for field, shape in {
            "weight": (20, 2, 2, FEATURES), "bias": (20, 2, 2),
            "displacement": (20, 2, 79, count, 2),
            "neural_train_mean": (20, 2, 80, count, FEATURES),
            "neural_test_mean": (20, 2, 80, count, FEATURES),
            "movement_train_mean": (20, 2, 80, count, 2),
            "group_counts": (20, 2, 2, count),
        }.items():
            shapes[prefix + field] = shape
    return shapes


def collect(family, core):
    """Join retained evidence to every original packet prediction, without fitting."""
    need(set(family["single_trial_decoding"]) == set(b.MODELS), "all eight original routes required")
    arrays, records = {}, {"single": {}, "averaged": {}}
    recipe = core.plan["recipe"]
    for model in b.MODELS:
        result = family["single_trial_decoding"][model]
        need(result["recipe"] == recipe and set(result["conditions"]) == set(b.e.CONDITIONS),
             "single-trial recipe/conditions differ")
        records["single"][model] = {}
        for reach in b.e.CONDITIONS:
            row = result["conditions"][reach]
            audit = row["decoder_audit"]
            need(audit["recipe"] == recipe and audit["bias_penalized"] == bool(b.e.RECIPES[recipe])
                 and audit["feature_count"] == FEATURES, "decoder identity differs")
            _same(row["prediction"], core.get(f"decoding/{model}/{reach}/prediction"), "core prediction")
            _same(row["test_indices"], core.get(f"decoding/{model}/{reach}/test_indices"), "core test identities")
            for field in SINGLE_FIELDS:
                arrays[f"single/{model}/{reach}/{field}"] = audit[field]
            records["single"][model][reach] = audit["fit_records"]
    average = family["raw_condition_average_control"]
    need(average["recipe"] == recipe and set(average["conditions"]) == set(b.e.CONDITIONS),
         "condition-average recipe/conditions differ")
    for reach in b.e.CONDITIONS:
        rows = average["conditions"][reach]["rows"]
        need(len(rows) == 20 and all(len(pair) == 2 for pair in rows), "all repeated halves required")
        core_values = {field: core.get(f"averaged/{reach}/{field}")
                       for field in ("prediction", "train_indices", "test_indices", "labels")}
        for field in HALF_FIELDS:
            arrays[f"averaged/{reach}/{field}"] = np.stack([
                np.stack([row["decoder"][field] if field in ("weight", "bias") else row[field]
                          for row in pair]) for pair in rows])
        records["averaged"][reach] = [[row["fit_record"] for row in pair] for pair in rows]
        for repeat, pair in enumerate(rows):
            for half, row in enumerate(pair):
                decoder = row["decoder"]
                need(decoder["recipe"] == recipe and decoder["bias_penalized"] == bool(b.e.RECIPES[recipe])
                     and decoder["feature_count"] == FEATURES, "half decoder identity differs")
                for field in ("prediction", "train_indices", "test_indices"):
                    _same(row[field], core_values[field][repeat, half], "half " + field)
                _same(row["condition_labels"], core_values["labels"], "condition labels")
    shapes = _shape_keys(core.manifest["angle_counts"])
    need(set(arrays) == set(shapes), "complete audit array census required")
    for key, shape in shapes.items():
        value = b.real(arrays[key], key, shape)
        need(value.dtype.itemsize in (4, 8), "only explicit 32/64-bit numeric storage")
    need(sum(np.asarray(value).nbytes for value in arrays.values()) <= MAX_DECODED_BYTES,
         "aggregate decoded audit exceeds declared profile")
    # Canonicalization also rejects nonfinite/non-JSON receipt fields. A deep
    # copy prevents caller mutations during later serialization.
    return arrays, json.loads(b.canonical(records))


class _LimitedOutput:
    def __init__(self, stream, budget):
        self.stream, self.budget = stream, budget

    def write(self, data):
        need(len(data) <= self.budget[0], "audit output budget exceeded")
        self.budget[0] -= len(data)  # Precharge before an interrupted write.
        return self.stream.write(data)

    def flush(self):
        return self.stream.flush()


def _manifest(path, expected_sha256):
    """Return parsed data and the extent of the same authenticated byte buffer."""
    need(b.hexhash(expected_sha256), "manifest SHA256 required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        st = os.fstat(stream.fileno())
        need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and 0 < st.st_size <= MAX_MANIFEST_BYTES,
             "ordinary bounded manifest required")
        body = stream.read(st.st_size + 1)
    need(len(body) == st.st_size and hashlib.sha256(body).hexdigest() == expected_sha256,
         "manifest identity differs")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, "duplicate manifest key")
            result[key] = value
        return result
    def invalid(_):
        raise ValueError("nonfinite JSON is forbidden")
    value = json.loads(body, object_pairs_hook=unique, parse_constant=invalid)
    need(isinstance(value, dict), "manifest must be an object")
    return value, len(body)


def write_packet(family, destination, core, representation_pins, *, maximum_bytes=MAX_PACKET_BYTES):
    """Write optional private audit evidence; failures preserve partial outputs.

    Representation pins describe caller-selected arrays, not independently
    authenticated decomposition fitting or permission to inspect a dataset.
    """
    need(type(maximum_bytes) is int and 0 < maximum_bytes <= MAX_PACKET_BYTES, "bounded output budget required")
    need(set(representation_pins) == set(b.MODELS), "explicit identity for all eight representations required")
    for pin in representation_pins.values():
        need(set(pin) == {"shape", "dtype", "bytes", "sha256"} and pin["shape"] == [150, 511, FEATURES]
             and pin["dtype"] == "<f8" and pin["bytes"] == 150 * 511 * FEATURES * 8
             and b.hexhash(pin["sha256"]), "representation must bind exact float64 source layout")
    arrays, records = collect(family, core)
    root = Path(destination)
    need(not root.exists(), "fresh private audit directory required")
    root.mkdir(mode=0o700, parents=True)
    os.chmod(root, 0o700)
    budget, files = [maximum_bytes], {}
    for index, (key, value) in enumerate(sorted(arrays.items())):
        value = b.real(value, key)
        path = root / f"{index:04d}.npy.gz"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as raw:
            os.fchmod(raw.fileno(), 0o600)
            with gzip.GzipFile(filename="", fileobj=_LimitedOutput(raw, budget), mode="wb", compresslevel=1, mtime=0) as zipped:
                np.save(zipped, value, allow_pickle=False)
            raw.flush()
            os.fsync(raw.fileno())
        files[key] = {"file": path.name, "bytes": path.stat().st_size, "sha256": b.p.file_hash(path),
                      "shape": list(value.shape), "dtype": value.dtype.str}
    manifest = {"schema": SCHEMA, "core_manifest_sha256": core.manifest_sha256,
                "plan_sha256": b.digest(core.plan), "bridge_sha256": BRIDGE_SHA256,
                "audited_producer_sha256": AUDITED_PRODUCER_SHA256,
                "representation_pins": representation_pins, "fit_records": records,
                "files": files, "fit_execution_authenticated": False,
                "scientific_admission": False}
    body = b.canonical(manifest)
    need(len(body) <= MAX_MANIFEST_BYTES and len(body) <= budget[0], "manifest exceeds output budget")
    fd = os.open(root / "MANIFEST.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        budget[0] -= len(body)
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    return {"manifest_sha256": hashlib.sha256(body).hexdigest(), "arrays": len(files),
            "charged_output_bytes": maximum_bytes - budget[0], "fit_execution_authenticated": False}


class AuditPacket:
    def __init__(self, directory, manifest_sha256, core):
        self.root, self.core = Path(directory), core
        m, manifest_bytes = _manifest(self.root / "MANIFEST.json", manifest_sha256)
        need(set(m) == {"schema", "core_manifest_sha256", "plan_sha256", "bridge_sha256",
                       "audited_producer_sha256", "representation_pins", "fit_records", "files",
                       "fit_execution_authenticated", "scientific_admission"}, "exact audit manifest fields required")
        need(m["schema"] == SCHEMA and m["core_manifest_sha256"] == core.manifest_sha256
             and m["plan_sha256"] == b.digest(core.plan) and m["bridge_sha256"] == BRIDGE_SHA256
             and m["audited_producer_sha256"] == AUDITED_PRODUCER_SHA256
             and m["fit_execution_authenticated"] is False and m["scientific_admission"] is False,
             "audit identity/scope differs")
        self.shapes = _shape_keys(core.manifest["angle_counts"])
        need(set(m["files"]) == set(self.shapes), "missing or extra audit arrays")
        need(set(m["representation_pins"]) == set(b.MODELS), "all representation identities required")
        names, total, decoded_total = [], manifest_bytes, 0
        for key, row in m["files"].items():
            need(set(row) == {"file", "bytes", "sha256", "shape", "dtype"}, "exact array declaration required")
            need(row["shape"] == list(self.shapes[key]) and isinstance(row["file"], str)
                 and re.fullmatch(r"[0-9]{4}\.npy\.gz", row["file"]), "array shape/name differs")
            dtype = np.dtype(row["dtype"])
            need(dtype.kind in "fiu" and dtype.itemsize in (4, 8), "numeric32/64 arrays required")
            maximum = int(np.prod(self.shapes[key])) * dtype.itemsize + 1024**2
            decoded_total += int(np.prod(self.shapes[key])) * dtype.itemsize
            need(decoded_total <= MAX_DECODED_BYTES, "aggregate decoded audit exceeds declared profile")
            need(type(row["bytes"]) is int and 0 < row["bytes"] <= maximum and b.hexhash(row["sha256"]), "array extent/hash differs")
            st = (self.root / row["file"]).lstat()
            need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size == row["bytes"], "ordinary single-link exact array required")
            total += row["bytes"]
            names.append(row["file"])
        need(total <= MAX_PACKET_BYTES and len(names) == len(set(names))
             and {x.name for x in self.root.iterdir()} == set(names) | {"MANIFEST.json"}, "packet extent/census differs")
        self.manifest, self.manifest_sha256 = m, manifest_sha256

    def get(self, key):
        row, shape = self.manifest["files"][key], self.shapes[key]
        fd = os.open(self.root / row["file"], os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            st = os.fstat(stream.fileno())
            need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size == row["bytes"], "array extent changed")
            payload = stream.read(row["bytes"] + 1)
        need(len(payload) == row["bytes"] and hashlib.sha256(payload).hexdigest() == row["sha256"], "array content changed")
        with gzip.GzipFile(fileobj=io.BytesIO(payload), mode="rb") as zipped:
            version = np.lib.format.read_magic(zipped)
            need(version in ((1, 0), (2, 0)), "NPY1/2 required")
            reader = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
            actual, fortran, dtype = reader(zipped, max_header_size=4096)
            need(actual == shape and dtype.str == row["dtype"] and not dtype.hasobject, "array header differs")
            size = int(np.prod(shape)) * dtype.itemsize
            body = zipped.read(size + 1)
            need(len(body) == size and not zipped.read(1), "decoded array extent differs")
        return b.real(np.frombuffer(body, dtype=dtype).reshape(shape, order="F" if fortran else "C"), key, shape)


def verify_original_linear_readout(packet, bank, representations):
    """Verify all original route arithmetic against explicitly supplied inputs.

    Each representation is a full source-layout float64 array [150,511,182].
    Their identities are compared to the frozen audit declarations. This does
    not authenticate their fitted provenance or recompute any fit/optimization.
    """
    core = packet.core
    need(bank["manifest_sha256"] == core.plan["bank_manifest_sha256"], "operator bank differs")
    need(set(representations) == set(b.MODELS), "all eight explicit representations required")
    movement = b.real(bank["movement"], "operator movement", (150, 511, 2)).astype(np.float64, copy=False)
    y, recipe = movement[65:-5], core.plan["recipe"]
    counts = {"single_fits": 0, "half_fits": 0, "single_test_occurrences": 0}
    need(set(packet.manifest["fit_records"]) == {"single", "averaged"}, "fit record categories differ")
    fit_records = packet.manifest["fit_records"]
    need(set(fit_records["single"]) == set(b.MODELS) and set(fit_records["averaged"]) == set(b.e.CONDITIONS), "complete fit roster required")
    for model in b.MODELS:
        full = b.real(representations[model], "representation", (150, 511, FEATURES)).astype(np.float64, copy=False)
        need(a.array_digest(full) == packet.manifest["representation_pins"][model], "representation identity differs")
        if model == "raw":
            _same(full, np.asarray(bank["neural"]).transpose(2, 0, 1), "raw representation")
        x = full[55:-15]
        need(set(fit_records["single"][model]) == set(b.e.CONDITIONS), "both fit conditions required")
        for reach in b.e.CONDITIONS:
            prefix, schedule = f"single/{model}/{reach}/", b.e.source_schedule(reach)
            weights, biases, deltas, trains = (packet.get(prefix + key) for key in SINGLE_FIELDS)
            b.same_indices(trains, schedule["train"], "audit training support")
            tests = core.get(f"decoding/{model}/{reach}/test_indices")
            b.same_indices(tests, schedule["test"], "core test support")
            predictions = core.get(f"decoding/{model}/{reach}/prediction")
            records = fit_records["single"][model][reach]
            need(len(records) == 20 and all(len(row) == 5 for row in records), "all100 fit records required")
            for repeat in range(20):
                for fold in range(5):
                    train, test = trains[repeat, fold], tests[repeat, fold]
                    fitted = {"weight": weights[repeat, fold], "bias": biases[repeat, fold],
                              "recipe": recipe, "bias_penalized": bool(b.e.RECIPES[recipe])}
                    expected_record = a.make_fit_record(fitted, x[:, train], y[:, train], train, test)
                    need(records[repeat][fold] == expected_record, "fit input/output record differs")
                    expected_delta = x[:-1, test] @ fitted["weight"].T + fitted["bias"]
                    _close(deltas[repeat, fold], expected_delta, "single displacement")
                    expected_position = b.e.integrate_displacements(expected_delta, y[0, test])
                    _same(predictions[repeat, fold, 0], y[0, test], "true initial position")
                    _close(predictions[repeat, fold], expected_position, "single position")
                    counts["single_fits"] += 1
                    counts["single_test_occurrences"] += len(test)
    raw = np.asarray(bank["neural"], dtype=np.float64).transpose(2, 0, 1)[55:-15]
    angles = b.real(bank["target_angle"], "operator angles", (511,))
    for reach, (lo, hi) in b.e.CONDITIONS.items():
        prefix, schedule = f"averaged/{reach}/", b.average_schedule()[reach]
        labels = np.unique(angles[lo:hi])
        need(core.manifest["angle_counts"][reach] == len(labels), "operator angle count differs")
        _same(core.get(prefix + "labels"), labels, "averaged labels")
        values = {key: packet.get(prefix + key) for key in HALF_FIELDS}
        trains, tests = (core.get(prefix + key) for key in ("train_indices", "test_indices"))
        b.same_indices(trains, schedule["train"], "averaged training support")
        b.same_indices(tests, schedule["test"], "averaged test support")
        predictions = core.get(prefix + "prediction")
        records = fit_records["averaged"][reach]
        need(len(records) == 20 and all(len(row) == 2 for row in records), "all40 half fit records required")
        for repeat in range(20):
            for half in range(2):
                train, test = trains[repeat, half], tests[repeat, half]
                groups = np.array([[np.count_nonzero(angles[ids] == label) for label in labels] for ids in (train, test)])
                need(np.all(groups > 0), "missing angle group")
                _same(values["group_counts"][repeat, half], groups, "group counts")
                means = {}
                for side, indices in (("train", train), ("test", test)):
                    for kind, original in (("neural", raw), ("movement", y)):
                        name = kind + "_" + side + "_mean"
                        means[name] = np.stack([original[:, indices[angles[indices] == label]].mean(axis=1) for label in labels], axis=1)
                        # Held-out movement means belong only to the evaluator;
                        # candidate evidence is never required to supply them.
                        if name in values:
                            _close(values[name][repeat, half], means[name], name)
                fitted = {"weight": values["weight"][repeat, half], "bias": values["bias"][repeat, half],
                          "recipe": recipe, "bias_penalized": bool(b.e.RECIPES[recipe])}
                expected_record = a.make_fit_record(fitted, means["neural_train_mean"], means["movement_train_mean"], train, test)
                need(records[repeat][half] == expected_record, "averaged fit record differs")
                delta = means["neural_test_mean"][:-1] @ fitted["weight"].T + fitted["bias"]
                _close(values["displacement"][repeat, half], delta, "averaged displacement")
                initial = means["movement_test_mean"][0]
                _same(predictions[repeat, half, 0], initial, "averaged true initial position")
                _close(predictions[repeat, half], b.e.integrate_displacements(delta, initial), "averaged position")
                counts["half_fits"] += 1
    return {"schema": "slicetca-linear-readout-arithmetic-verification-v1", "status": "consistent_with_supplied_inputs",
            "audit_manifest_sha256": packet.manifest_sha256, "core_manifest_sha256": core.manifest_sha256,
            "counts": counts, "arithmetic_tolerance": TOLERANCE, "fitting_reexecuted": False,
            "fit_execution_authenticated": False, "representation_fitting_authenticated": False,
            "scientific_admission": False,
            "scope": "Complete original linear readout supports, means, coefficients-to-deltas-to-positions only; not optimizer optimality, trusted execution, historical findings or a paper win."}
