"""Operator-only source-native behavior truth issuance and delayed scoring.

No imports of numerical libraries, observations, or targets occur at import time.
This component retains original target extraction and the existing metric ABI;
it does not supply an original run mapping or authorize an authentic-data run.
"""
from __future__ import annotations

import ast
import contextlib
import copy
import hashlib
import json
import math
from pathlib import Path
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "registered-runtime"
FACTORY = (25741, "102aca8fc446d78ef3945a264c7864e4d4c74ccfd1acaca4e5d9901a870c094d")
DATA_UTILS_SHA = "71ec03aa43aa911c53d680d9f7a8e0f9fd677f50f97ab983acccfcd63ffa15e4"
REVISION = "36ed94084628c253098d448048c980d3dea0050d"
MODES = ("speed", "phi", "th")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


@contextlib.contextmanager
def sources():
    """Reuse the predecessor's exact, bounded, private-namespace source loader."""
    path = ROOT / "native_factory_v2.py"
    with path.open("rb") as stream:
        body = stream.read(FACTORY[0] + 1)
    require((len(body), digest(body)) == FACTORY, "native factory source pin changed")
    factory = ModuleType("_behavior_truth_factory_v1")
    factory.__file__ = str(path)
    exec(compile(body, str(path), "exec"), factory.__dict__)
    captured, helper = factory.source_capture(factory.Reads(2 * 1024 * 1024))
    with factory.Sources(captured, helper) as loaded:
        yield loaded


def _descriptor(value, native, maximum):
    require(type(value) is dict and set(value) >= {"path", "bytes", "sha256"}, "input descriptor")
    native.relative(value["path"])
    native.integer(value["bytes"], "input bytes")
    require(value["bytes"] <= maximum, "input exceeds explicit file capacity")
    h = value["sha256"]
    require(type(h) is str and len(h) == 64 and set(h) <= set("0123456789abcdef"), "input digest")


def admit_request(request, loaded):
    """Bind every evaluation row to a full native recording and original cell."""
    native = loaded.modules["native_dataset"]
    composition = loaded.modules["run_composition"]
    require(type(request) is dict and set(request) == {"schema", "recordings", "cells", "limits", "study"},
            "closed behavior truth request")
    require(request["schema"] == "neuroformer_behavior_truth_v1", "truth request schema")
    limits = request["limits"]
    require(type(limits) is dict and set(limits) == {"max_input_bytes", "max_file_bytes", "max_rows", "max_values"},
            "explicit input and output bounds")
    for key, value in limits.items():
        native.integer(value, key)
    _descriptor(request["study"], native, limits["max_file_bytes"])
    require(set(request["study"]) == {"path", "bytes", "sha256"}, "study descriptor keys")
    recordings = request["recordings"]
    require(type(recordings) is dict and recordings, "complete recording roster")
    total = request["study"]["bytes"]
    paths = [request["study"]["path"]]
    for recording, entry in recordings.items():
        require(type(recording) is str and recording and type(entry) is dict and
                set(entry) == {"cohort", "recording_ticks", "assets", "provenance"}, "recording identity and provenance")
        require(entry["cohort"] in ("lateral", "medial"), "original VisNav cohort")
        native.integer(entry["recording_ticks"], "recording ticks")
        require(entry["recording_ticks"] % 5 == 0, "full 10 ms recording / 50 ms behavior clock")
        samples = entry["recording_ticks"] // 5
        require(type(entry["assets"]) is dict and set(entry["assets"]) == set(MODES), "all original behavior streams")
        for mode, desc in entry["assets"].items():
            _descriptor(desc, native, limits["max_file_bytes"])
            require(set(desc) == {"path", "bytes", "sha256", "dtype", "shape"}, "behavior array descriptor keys")
            require(Path(desc["path"]).name == native.FILES[mode], "original behavior filename")
            require(desc["dtype"] in ("<f4", "<f8") and desc["shape"] in ([samples], [samples, 1]),
                    "complete original scalar stream and layout")
            total += desc["bytes"]
            paths.append(desc["path"])
        _descriptor(entry["provenance"], native, limits["max_file_bytes"])
        require(set(entry["provenance"]) == {"path", "bytes", "sha256"}, "provenance descriptor keys")
        total += entry["provenance"]["bytes"]
        paths.append(entry["provenance"]["path"])
    require(len(paths) == len(set(paths)) and total <= limits["max_input_bytes"], "unique bounded complete inputs")
    cases = {row["id"]: row for row in json.loads(loaded.bodies["source/public/PANEL.json"])["cases"]}
    cells = request["cells"]
    require(type(cells) is list and cells, "nonempty selected cell roster")
    specs, seen, used = [], set(), set()
    count = values = 0
    for cell in cells:
        require(type(cell) is dict and set(cell) == {"case_id", "condition", "support"}, "cell keys")
        case = cases.get(cell["case_id"])
        require(case is not None and case["kind"] in ("regression", "joint") and
                case["family"] not in composition.PROSPECTIVE_FAMILIES, "native continuous cell required")
        condition = cell["condition"]
        require(condition in (composition.HISTORICAL, composition.PROTECTED), "no 5 ms or classification substitution")
        support = cell["support"]
        require(type(support) is dict and set(support) == {"train", "selection", "evaluation"}, "all support roles")
        require(all(type(rows) is list for rows in support.values()), "support lists")
        count += sum(len(rows) for rows in support.values())
        require(count <= limits["max_rows"], "full support exceeds row capacity")
        composition.admit_support(support, condition)
        identities = {row["recording"] for rows in support.values() for row in rows}
        require(len(identities) == 1 and identities <= set(recordings), "one bound original recording per cell")
        recording = next(iter(identities))
        entry = recordings[recording]
        require(entry["cohort"] == case["cohort"] and all(row["recording_ticks"] == entry["recording_ticks"]
                for rows in support.values() for row in rows), "cohort and full recording extent")
        modes = list(MODES) if case["kind"] == "joint" else ["speed"]
        cell_id = case["id"] + "::" + condition
        require(cell_id not in seen, "duplicate selected cell")
        seen.add(cell_id)
        used.add(recording)
        values += len(support["evaluation"]) * len(modes)
        specs.append({"cell_id": cell_id, "condition": condition, "modes": modes,
                      "row_ids": [row["id"] for row in support["evaluation"]]})
    require(values <= limits["max_values"] and used == set(recordings), "bounded selected full target roster")
    return specs


def _native_runtime():
    import numpy as np
    import torch
    from scipy.stats import pearsonr
    return SimpleNamespace(np=np, torch=torch, pearsonr=pearsonr)


def _extractor(body, runtime):
    """Compile exact source target methods, omitting dataset/model side effects."""
    require(digest(body) == DATA_UTILS_SHA, "exact original data utilities required")
    tree = ast.parse(body)
    effective = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    methods = {node.name: node for node in effective["NFDataloader"].body if isinstance(node, ast.FunctionDef)}
    # Arrays are the only admitted input. A local sentinel retains the original
    # DataFrame branch test without importing pandas or accepting table inputs.
    class NoDataFrame:
        pass
    namespace = {"np": runtime.np, "torch": runtime.torch, "pd": SimpleNamespace(DataFrame=NoDataFrame)}
    nodes = [effective[name] for name in ("get_frame_idx", "round_n", "pad_tensor", "get_var")]
    nodes += [methods[name] for name in ("calc_intervals", "get_behavior")]
    for node in nodes:
        exec(compile(ast.Module(body=[node], type_ignores=[]), "neuroformer/data_utils.py", "exec"), namespace)
    owner = SimpleNamespace(window=.05, window_prev=.05, dt=.01, stoi={"PAD": 0}, stoi_dt={"PAD": 0})
    # Source pad_tensor ignores its pad_value argument and pads with zeros.
    return namespace, owner


def _issue(request, loaded, array_root, runtime):
    native = loaded.modules["native_dataset"]
    ns, owner = _extractor(loaded.bodies["source/public/official_code/neuroformer/data_utils.py"], runtime)
    arrays, receipts = {}, {}
    native.capture(array_root, request["study"], request["limits"]["max_file_bytes"])
    for recording, entry in request["recordings"].items():
        native.capture(array_root, entry["provenance"], request["limits"]["max_file_bytes"])
        arrays[recording] = {}
        for mode, desc in entry["assets"].items():
            body = native.capture(array_root, desc, request["limits"]["max_file_bytes"])
            array = native.decode_npy(body, desc, runtime.np)
            require(all(math.isfinite(float(value)) for value in array.flat), "nonfinite original behavior stream")
            arrays[recording][mode] = array
        receipts[recording] = {"cohort": entry["cohort"], "recording_ticks": entry["recording_ticks"],
            "asset_hashes": {key: desc["sha256"] for key, desc in entry["assets"].items()},
            "provenance_sha256": entry["provenance"]["sha256"]}
    specs = admit_request(request, loaded)
    packets, extraction = [], []
    for cell, spec in zip(request["cells"], specs):
        values = {mode: [] for mode in spec["modes"]}
        empty_source_slices = []
        for row in cell["support"]["evaluation"]:
            previous, current = ns["calc_intervals"](owner, row["end_tick"] * .01)
            for mode in spec["modes"]:
                value, times = ns["get_behavior"](owner, arrays[row["recording"]][mode], current,
                    variable_name=mode, trial=0, dt=.05, tokenizer=None)
                # Literal y['modalities']['behavior'][mode]['value'] construction.
                selected = value[:, -1]
                require(tuple(selected.shape) in ((1,), (1, 1)), "source target is not one scalar; no flattening substitution")
                scalar = float(selected.detach().cpu().reshape(-1).tolist()[0])
                require(math.isfinite(scalar), "nonfinite source float32 target")
                times[-1]  # Original __getitem__ also requires the final time.
                values[mode].append(scalar)
                if ns["get_frame_idx"](current[0], .05) == ns["get_frame_idx"](current[1], .05):
                    empty_source_slices.append({"row_id": row["id"], "mode": mode})
        packets.append({"cell_id": spec["cell_id"], "row_ids": spec["row_ids"], "values": values})
        extraction.append({"cell_id": spec["cell_id"], "rows": len(spec["row_ids"]),
                           "empty_source_slices_retained": empty_source_slices})
    return packets, {"recordings": receipts, "extraction": extraction}


def grade(packets, request, array_root, *, runtime=None):
    """Freeze all scalar predictions, then issue truth and call unchanged metrics.

    The caller is a trusted evaluator. ``runtime`` is an engineering-control
    injection point, not a candidate interface. Paths and target arrays must
    remain outside candidate mounts. No claim of physical isolation is made.
    """
    request = copy.deepcopy(request)
    array_root = Path(array_root)
    with sources() as loaded:
        specs = admit_request(request, loaded)
        active, receipt = [], []

        def targets():
            numerical = _native_runtime() if runtime is None else runtime
            active.append(numerical)
            truth, evidence = _issue(request, loaded, array_root, numerical)
            receipt.append(evidence)
            return truth

        report = loaded.modules["run_metrics"].grade_behavior(
            packets, specs, targets, lambda x, y: active[0].pearsonr(x, y))
        report["truth_issuance"] = {"schema": "neuroformer_behavior_truth_receipt_v1",
            "source_revision": REVISION, "data_utils_sha256": DATA_UTILS_SHA,
            "request_sha256": digest(canonical(request)), "study_sha256": request["study"]["sha256"],
            "source_clock_seconds": .05, "neural_tick_seconds": .01,
            "target_precision": "source torch.float32", "target_values_returned": False,
            "provenance_scientifically_qualified": False, "physical_isolation_qualified": False,
            **receipt[0]}
        return report
