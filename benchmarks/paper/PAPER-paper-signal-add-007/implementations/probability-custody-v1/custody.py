"""Lossless ICNet probability custody; generated controls are not native qualification.

Trusted operator API. No model loader, isolation boundary or scientific admission.
The unchanged original converter defines derived normalization and PCG64 sampling.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import types

import numpy as np

PINS = {
    "original-inputs-v1/source.py": "9533cb8fc55f0185a80522081af258122f4788fb973fee7011551efd43b3284c",
    "original-inputs-v1/predictions.py": "84b0215d549c282f0d8a7683b49214c5b146d1ebab0d3d8395ea2571cb468b94",
    "original-inputs-v1/grade.py": "63aed8d64d3670567234873cc5d11233a587f5edab344151228e84066b426778",
    "source-equations-v1/scorer.py": "c2643973762868391ea1d32b9c7ed54f546740f615db65bb2c920bc4ca9a493a",
}
SCHEMA = "icnet-probability-custody/v1"
SAMPLING = "NumPy-PCG64-original-column-row-major-inverse-CDF"
ROW_LIMIT = 512
META_ALLOWANCE = 1024 * 1024


def _dependencies():
    """Load exact sibling bytes without trusting ambient source/predictions imports."""
    root = Path(__file__).resolve().parent.parent
    bodies = {}
    for rel, expected in PINS.items():
        body = (root / rel).read_bytes()
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError("original dependency differs: " + rel)
        bodies[rel] = body
    saved = {name: sys.modules.get(name) for name in ("source", "predictions")}
    modules = []
    try:
        for name in ("source", "predictions", "grade"):
            rel = "original-inputs-v1/" + name + ".py"
            module = types.ModuleType("icnet_custody_" + name)
            module.__file__ = str(root / rel)
            exec(compile(bodies[rel], module.__file__, "exec"), module.__dict__)
            modules.append(module)
            if name in saved:
                sys.modules[name] = module
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
    return tuple(modules)


s, p, g = _dependencies()
require = s.require


def storage_plan():
    """Worst-case f64 probabilities, both derived types, one-bin chunks and receipts."""
    streams = len(p.ANIMALS) * len(p.SOUNDS) * 2
    elements = streams * p.TIME_BINS * p.UNITS
    blocks = streams * p.TIME_BINS
    payload = elements * (5 * 8 + 8 + 1)
    overhead = (blocks + streams * 5) * 4096 + blocks * ROW_LIMIT + META_ALLOWANCE
    return {"streams": streams, "probability_max_bytes": elements * 5 * 8,
            "derived_payload_bytes": elements * 9, "overhead_allowance_bytes": overhead,
            "required_bytes": payload + overhead}


def _pin(path, root):
    return {"path": str(Path(path).relative_to(root)), "sha256": s.sha256_file(path)}


def _identity(case, trial):
    return {"animal": case["animal"], "sound": case["sound"], "trial": trial,
            "measurement_time_seconds": case["measurement_times_seconds"][trial - 1]}


def _ordered(panel):
    return sorted(panel["cases"], key=lambda c: (p.SOUNDS.index(c["sound"]), c["animal"]))


def _binding(value):
    require(type(value) is dict and set(value) == {"model_sha256", "model_source_sha256"}
            and all(s.is_sha(x) for x in value.values()), "explicit model and model-source identities required")


def capture(public_path, destination, predictor, *, predictor_sha256, model_binding,
            seed, storage_budget_bytes):
    """Call the predictor once per original stream, archive before yielding to v1.

    Budget admission precedes every predictor call. This does not prevent a caller
    from having loaded a model beforehand. Errors keep STARTED, partial raw blocks,
    count files and FAILURE; only successful replay writes COMPLETED.
    """
    destination = Path(destination)
    require(not destination.exists(), "custody destination must be new")
    destination.mkdir(mode=0o700)
    streams = []
    try:
        s.write_json(destination / "STARTED.json", {"schema": SCHEMA, "complete": False})
        _binding(model_binding)
        require(callable(predictor) and s.is_sha(predictor_sha256), "reviewed predictor required")
        require(type(seed) is int and 0 <= seed < 2**63, "explicit valid sampling seed required")
        panel, public_pin = s.read_json_with_pin(public_path)
        p.validate_public(panel)
        plan = storage_plan()
        require(type(storage_budget_bytes) is int and storage_budget_bytes >= plan["required_bytes"],
                "storage budget cannot hold complete probability/count custody")
        require(shutil.disk_usage(destination).free >= plan["required_bytes"],
                "insufficient available storage for complete custody")
        s.write_json(destination / "PREFLIGHT.json", {**plan, "storage_budget_bytes": storage_budget_bytes,
                     "physical_reservation": False})
        s.write_json(destination / "RUN.json", {"schema": SCHEMA, "public_manifest_sha256": public_pin,
                     "predictor_sha256": predictor_sha256, "model_binding": dict(model_binding),
                     "sampling_seed": seed, "sampling": SAMPLING, "numpy_version": np.__version__,
                     "dependency_sha256": dict(PINS), "complete": False})
        raw_root = destination / "probabilities"
        raw_root.mkdir(mode=0o700)
        expected = [_identity(case, trial) for case in _ordered(panel) for trial in (1, 2)]

        def archived(request):
            index = len(streams)
            identity = {key: request[key] for key in ("animal", "sound", "trial", "measurement_time_seconds")}
            require(index < len(expected) and identity == expected[index], "unexpected or repeated predictor stream")
            receipt_path = raw_root / f"stream-{index:02d}.jsonl"
            s.write_json(raw_root / f"stream-{index:02d}.STARTED.json", {"identity": identity, "complete": False})
            position, columns, count = 0, None, 0
            with receipt_path.open("xb") as receipt:
                for block in predictor(request):
                    require(type(block) is dict and set(block) == {"start_bin", "probabilities", "column_indices"},
                            "invalid predictor block fields")
                    values = block["probabilities"]
                    require(type(values) is np.ndarray and values.dtype in (np.dtype("float32"), np.dtype("float64"))
                            and values.ndim == 3 and 1 <= values.shape[0] <= p.MAX_BLOCK_BINS
                            and values.shape[1:] == (p.UNITS, 5), "invalid raw probability geometry")
                    require(type(block["start_bin"]) is int and block["start_bin"] == position
                            and position + values.shape[0] <= p.TIME_BINS, "raw probability gap/overlap/extent")
                    current = block["column_indices"]
                    require(type(current) is list and len(current) == p.UNITS
                            and all(type(x) is int for x in current) and set(current) == set(range(p.UNITS)),
                            "original columns must be an exact permutation")
                    if columns is None:
                        columns = list(current)
                        s.write_json(raw_root / f"stream-{index:02d}.COLUMNS.json",
                                     {"identity": identity, "column_indices": columns})
                    require(columns == current, "column order changed within stream")
                    # Own the exact pre-normalization bytes consumed by the converter.
                    owned = np.array(values, copy=True, order="C")
                    owned.flags.writeable = False
                    path = raw_root / f"p-{index:02d}-{count:05d}.npy"
                    with path.open("xb") as output:
                        np.lib.format.write_array(output, owned, version=(1, 0), allow_pickle=False)
                    row = {"start_bin": position, "rows": owned.shape[0], "dtype": owned.dtype.str,
                           "array": _pin(path, destination)}
                    encoded = (json.dumps(row, separators=(",", ":")) + "\n").encode()
                    require(len(encoded) <= ROW_LIMIT, "probability receipt exceeds bound")
                    receipt.write(encoded)
                    receipt.flush()
                    yield {"start_bin": position, "probabilities": owned, "column_indices": list(columns)}
                    position += owned.shape[0]
                    count += 1
            require(position == p.TIME_BINS, "incomplete probability stream")
            streams.append({"identity": identity, "column_indices": columns, "blocks": count,
                            "receipt": _pin(receipt_path, destination)})

        predictions = p.run(public_path, destination / "counts", archived,
                            predictor_sha256=predictor_sha256, seed=seed)
        require(len(streams) == 56 and predictions["complete"], "all 56 streams required")
        document = {"schema": SCHEMA, "capture_complete": True, "public_manifest_sha256": public_pin,
                    "predictor_sha256": predictor_sha256, "model_binding": dict(model_binding),
                    "sampling_seed": seed, "sampling": SAMPLING, "numpy_version": np.__version__,
                    "dependency_sha256": dict(PINS), "streams": streams,
                    "predictions": _pin(destination / "counts/predictions.json", destination),
                    "storage": {**plan, "storage_budget_bytes": storage_budget_bytes},
                    "qualification": "operator_custody_not_native_or_scientific_qualification"}
        s.write_json(destination / "capture.json", document)
        result = verify(public_path, destination / "capture.json")
        s.write_json(destination / "COMPLETED.json", result)
        return result
    except BaseException as exc:
        s.write_json(destination / "FAILURE.json", {"schema": SCHEMA, "complete": False,
                     "completed_streams": len(streams), "error_type": type(exc).__name__,
                     "error": str(exc)[:512]})
        raise


def verify(public_path, capture_path):
    """Replay exact v1 conversion from retained raw blocks; no predictor invocation."""
    capture_path = Path(capture_path)
    root = capture_path.parent.resolve(strict=True)
    document, capture_pin = s.read_json_with_pin(capture_path)
    require(type(document) is dict and set(document) == {
        "schema", "capture_complete", "public_manifest_sha256", "predictor_sha256", "model_binding",
        "sampling_seed", "sampling", "numpy_version", "dependency_sha256", "streams", "predictions",
        "storage", "qualification"}, "not a complete probability-custody artifact")
    require(document["schema"] == SCHEMA and document["capture_complete"] is True,
            "not a complete probability capture")
    require(document["dependency_sha256"] == PINS and document["numpy_version"] == np.__version__,
            "converter dependency or NumPy version differs")
    require(document["sampling"] == SAMPLING and type(document["sampling_seed"]) is int
            and 0 <= document["sampling_seed"] < 2**63 and s.is_sha(document["predictor_sha256"]),
            "sampling/predictor identity differs")
    _binding(document["model_binding"])
    require(document["qualification"] == "operator_custody_not_native_or_scientific_qualification",
            "qualification scope differs")
    plan = storage_plan()
    require(type(document["storage"]) is dict
            and set(document["storage"]) == set(plan) | {"storage_budget_bytes"}
            and all(document["storage"][key] == value for key, value in plan.items())
            and type(document["storage"]["storage_budget_bytes"]) is int
            and document["storage"]["storage_budget_bytes"] >= plan["required_bytes"], "invalid storage admission")
    panel, public_pin = s.read_json_with_pin(public_path)
    p.validate_public(panel)
    require(public_pin == document["public_manifest_sha256"], "public panel identity differs")
    prediction_path = p.inside(root, document["predictions"]["path"])
    prediction, prediction_pin = s.read_json_with_pin(prediction_path)
    require(set(document["predictions"]) == {"path", "sha256"}
            and prediction_pin == document["predictions"]["sha256"], "prediction manifest differs")
    require(prediction.get("schema") == "icnet-original-predictions/v1" and prediction.get("complete") is True
            and prediction.get("public_manifest_sha256") == public_pin
            and prediction.get("predictor_sha256") == document["predictor_sha256"]
            and prediction.get("sampling_seed") == document["sampling_seed"]
            and prediction.get("sampling") == SAMPLING, "count provenance differs")
    cases = g._cases(prediction["cases"])
    require(type(document["streams"]) is list and len(document["streams"]) == 56, "complete 56-stream custody required")
    ordinal = 0
    for case in _ordered(panel):
        predicted = cases[(case["animal"], case["sound"])]
        require(predicted["measurement_times_seconds"] == case["measurement_times_seconds"], "trial times differ")
        require(set(predicted["arrays"]) == {"sampled_trial1", "expected_trial1", "sampled_trial2", "expected_trial2"}
                and type(predicted["trials"]) is list and len(predicted["trials"]) == 2, "count outputs incomplete")
        for trial in (1, 2):
            stream = document["streams"][ordinal]
            require(type(stream) is dict and set(stream) == {"identity", "column_indices", "blocks", "receipt"}
                    and stream["identity"] == _identity(case, trial), "missing, repeated or reordered stream")
            require(type(stream["blocks"]) is int and math.ceil(p.TIME_BINS / p.MAX_BLOCK_BINS)
                    <= stream["blocks"] <= p.TIME_BINS, "invalid block count")
            receipt_name = f"probabilities/stream-{ordinal:02d}.jsonl"
            require(set(stream["receipt"]) == {"path", "sha256"} and stream["receipt"]["path"] == receipt_name,
                    "unexpected probability receipt identity")
            receipt_path = p.inside(root, receipt_name)
            require(receipt_path.stat().st_size <= stream["blocks"] * ROW_LIMIT
                    and s.sha256_file(receipt_path) == stream["receipt"]["sha256"], "probability receipt differs")
            require(predicted["trials"][trial - 1] == {"trial": trial, "blocks": stream["blocks"],
                    "column_indices": stream["column_indices"]}, "count/probability column or block identity differs")
            arrays = {kind: p.load_array(prediction_path.parent, predicted["arrays"][f"{kind}_trial{trial}"],
                                        (p.TIME_BINS, p.UNITS), dtype)
                      for kind, dtype in (("sampled", "int8"), ("expected", "float64"))}
            rng = np.random.Generator(np.random.PCG64(p._case_seed(document["sampling_seed"], case["animal"], case["sound"], trial)))
            position = 0
            with s.regular_file(receipt_path) as receipts:
                receipt_identity = s._identity(receipts)
                consumed_digest = hashlib.sha256()
                for block_number in range(stream["blocks"]):
                    line = receipts.readline(ROW_LIMIT + 1)
                    require(line.endswith(b"\n") and len(line) <= ROW_LIMIT, "missing or oversized block receipt")
                    consumed_digest.update(line)
                    row = json.loads(line)
                    require(type(row) is dict and set(row) == {"start_bin", "rows", "dtype", "array"}
                            and type(row["start_bin"]) is int and row["start_bin"] == position
                            and type(row["rows"]) is int and 1 <= row["rows"] <= p.MAX_BLOCK_BINS
                            and position + row["rows"] <= p.TIME_BINS, "invalid probability block order/support")
                    require(row["dtype"] in (np.dtype("float32").str, np.dtype("float64").str), "invalid original probability dtype")
                    require(row["array"]["path"] == f"probabilities/p-{ordinal:02d}-{block_number:05d}.npy",
                            "probability chunk identity differs")
                    probabilities = p.load_array(root, row["array"], (row["rows"], p.UNITS, 5), row["dtype"])
                    draws, means = p.convert_block(probabilities, stream["column_indices"], rng)
                    stop = position + row["rows"]
                    require(np.array_equal(draws, arrays["sampled"][position:stop])
                            and np.array_equal(means, arrays["expected"][position:stop]),
                            "retained probabilities disagree with sampled or expected counts")
                    position = stop
                require(receipts.read(1) == b"", "extra probability receipt")
                require(consumed_digest.hexdigest() == stream["receipt"]["sha256"]
                        and s._identity(receipts) == receipt_identity, "probability receipt changed during replay")
            require(position == p.TIME_BINS, "incomplete probability bins")
            ordinal += 1
            del arrays
    require(s.sha256_file(capture_path) == capture_pin and s.sha256_file(public_path) == public_pin
            and s.sha256_file(prediction_path) == prediction_pin, "manifests changed during verification")
    return {"schema": "icnet-probability-custody-verification/v1", "complete": True,
            "capture_sha256": capture_pin, "public_manifest_sha256": public_pin,
            "prediction_sha256": prediction_pin, "streams": ordinal, "derived_outputs_verified": ordinal * 2,
            "verification": "exact_v1_converter_replay", "scientifically_qualified": False}


def verify_and_grade(public_path, reference_path, capture_path, workspace_root, *, variance_ddof):
    """Require complete custody before invoking the unchanged v1 preparation/scorer."""
    verification = verify(public_path, capture_path)
    document, capture_pin = s.read_json_with_pin(capture_path)
    require(capture_pin == verification["capture_sha256"], "capture changed after verification")
    prediction_path = p.inside(Path(capture_path).parent, document["predictions"]["path"])
    manifest = g.assemble(public_path, reference_path, prediction_path, workspace_root, variance_ddof=variance_ddof)
    require(manifest["preparation"]["public_manifest_sha256"] == verification["public_manifest_sha256"]
            and manifest["preparation"]["prediction_freeze_sha256"] == verification["prediction_sha256"],
            "grading inputs differ from verified custody")
    return {"custody": verification, "source_equation_report": g.grade(manifest, workspace_root),
            "scientifically_qualified": False, "reproduction_evaluated": False, "improvement_evaluated": False}
