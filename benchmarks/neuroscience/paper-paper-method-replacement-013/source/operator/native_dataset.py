"""Source-faithful VisNav preparation; no model, fitting, or scoring entry point.

Importing this module imports only the standard library. ``prepare`` is a future
operator call that consumes real arrays; it is NOT authorized by source controls.
Native 10 ms rounded-rate tokens must not be relabelled as the 5 ms bridge.
"""
from __future__ import annotations

import ast
import collections
import copy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
from types import SimpleNamespace

REVISION = "36ed94084628c253098d448048c980d3dea0050d"
INDEX_SHA = "97b45d5a535b0037d63a771e094d147d11212d3c6b2d7911edc2ceeecced5dae"
SOURCE_CAPTURE_BYTES = 387254  # Public index plus all26 exact distributed source bodies.
FILES = {
    "spikes": "spikerates_dt_0.01.npy",
    "speed": "behavior_speed_dt_0.05.npy",
    "stimulus": "stimulus.npy",
    "phi": "phi_dt_0.05.npy",
    "th": "th_dt_0.05.npy",
}
CONFIGS = tuple("configs/Visnav/lateral/" + n + ".yaml" for n in (
    "mconf_predict_all", "mconf_predict_all_input_contrastive_visual",
    "mconf_pretrain", "mconf_pretrain_all_input_contrastive"))
SOURCE_SELECTION = {
    "neuroformer/datasets.py": ("split_data_by_interval", "visnav_callback", "load_visnav"),
    "neuroformer/data_utils.py": ("create_nested_defaultdict", "get_frame_idx", "round_n",
        "pad_tensor", "get_var", "Tokenizer", "NFDataloader"),
    "neuroformer/utils.py": ("dict_to_object", "object_to_dict", "create_modalities_dict"),
}


class Refusal(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Refusal(message)


def integer(x, name, minimum=1):
    require(type(x) is int and x >= minimum, name + " must be an integer >= " + str(minimum))
    return x


def sha(b):
    return hashlib.sha256(b).hexdigest()


def relative(s):
    require(isinstance(s, str) and s and "\\" not in s, "invalid relative path")
    p = PurePosixPath(s)
    require(not p.is_absolute() and str(p) == s and all(x not in ("", ".", "..") for x in p.parts),
            "path must be canonical and relative")
    return p.parts


def capture(root, descriptor, limit):
    """Bounded regular-file capture through no-follow parent directory FDs.

    The operator selects the root. Every component below it and the root itself
    must be a directory/ordinary single-link file, never an alias. Returned
    immutable bytes are what later parsing consumes; paths are not reopened.
    """
    require(set(descriptor) >= {"path", "bytes", "sha256"}, "incomplete descriptor")
    n = integer(descriptor["bytes"], "bytes", 0)
    require(n <= integer(limit, "capture limit"), "capture exceeds caller bound")
    require(isinstance(descriptor["sha256"], str) and len(descriptor["sha256"]) == 64,
            "invalid digest")
    parts = relative(descriptor["path"])
    flags = os.O_RDONLY | os.O_NOFOLLOW
    parent = os.open(root, flags | os.O_DIRECTORY)
    fd = None
    try:
        for part in parts[:-1]:
            nxt = os.open(part, flags | os.O_DIRECTORY, dir_fd=parent)
            os.close(parent)
            parent = nxt
        fd = os.open(parts[-1], flags, dir_fd=parent)
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == n,
                "not the exact ordinary single-link file")
        chunks = []
        remaining = n
        while remaining:
            block = os.read(fd, min(1024 * 1024, remaining))
            require(bool(block), "short read")
            chunks.append(block)
            remaining -= len(block)
        require(os.read(fd, 1) == b"", "file grew")
        after = os.fstat(fd)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                "file changed during capture")
        body = b"".join(chunks)
        require(sha(body) == descriptor["sha256"], "digest mismatch")
        return body
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)


def source_snapshot(root):
    """Authenticate all 26 original text bodies, without importing the project."""
    index = capture(root / "operator", {"path": "CODE_INDEX.json", "bytes": 9550,
                    "sha256": INDEX_SHA}, 9550)
    obj = json.loads(index)
    require(obj["commit"] == REVISION and len(obj["files"]) == 26, "unexpected source roster")
    result = {}
    for row in obj["files"]:
        body = capture(root / "public" / "official_code", row.get("public_distribution", row), 1024 * 1024)
        if "public_distribution" in row:
            d = row["public_distribution"]; prefix = d["notice_prefix"].encode("utf-8")
            require(d["path"] == row["path"] and d["notice_only"] is True, "notice-only distribution")
            require(prefix and all(not line.strip() or line.lstrip().startswith(b"#") for line in prefix.splitlines()), "comment-only prefix")
            require(body.startswith(prefix), "exact public notice prefix")
            body = body[len(prefix):]
            require(len(body) == row["bytes"] and sha(body) == row["sha256"], "exact recovered original source")
        require(hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()
                == row["git_blob_sha"], "git blob mismatch")
        body.decode("utf-8")
        require(b"\0" not in body, "source is not text")
        require(row["path"] not in result, "duplicate source path")
        result[row["path"]] = body
    return result


def compile_selected(bodies, runtime, arrays, cohort, seed):
    """Compile exact AST definitions, omitting original top-level side effects.

    Local RandomState isolates the original MT19937 draw from unrelated callers.
    This is source-amended dependency binding, not a run of the original script.
    Duplicate definitions use Python's effective last binding (round_n).
    """
    prefix = "./data/VisNav_VR_Expt/" + {"medial": "Medial", "lateral": "Lateral"}[cohort] + "VRDataset//NF_1.5/"
    paths = {prefix + FILES[k]: arrays[k] for k in FILES}
    loads = []

    class BoundNumpy:
        random = runtime.np.random.RandomState(seed)

        def __getattr__(self, name):
            return getattr(runtime.np, name)

        @staticmethod
        def load(path, *args, **kwargs):
            require(not args and not kwargs and path in paths, "unexpected native file request")
            require(path not in loads, "duplicate native file request")
            loads.append(path)
            return paths[path]

    def no_download():
        raise Refusal("downloads are disabled")

    namespace = {"np": BoundNumpy(), "torch": runtime.torch, "pd": runtime.pd,
        "Dataset": runtime.Dataset, "collections": collections, "copy": copy,
        "math": math, "SimpleNamespace": SimpleNamespace,
        "os": SimpleNamespace(path=SimpleNamespace(exists=lambda p: p == "./data")),
        "download_data": no_download}
    selected = []
    for path, names in SOURCE_SELECTION.items():
        tree = ast.parse(bodies[path].decode("utf-8"), filename=path)
        effective = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        for name in names:
            node = effective[name]
            selected.append({"path": path, "name": name, "line": node.lineno, "end_line": node.end_lineno})
            exec(compile(ast.Module(body=[node], type_ignores=[]), path, "exec"), namespace)
    return namespace, loads, selected


def admit_request(request):
    require(type(request) is dict and set(request) == {"schema", "cohort", "seed", "config",
        "config_status", "recording_id", "assets", "limits", "provenance"}, "request keys")
    require(request["schema"] == "neuroformer_native_recording_v1", "wrong native schema")
    require(request["cohort"] in ("medial", "lateral"), "unknown cohort")
    seed = integer(request["seed"], "seed", 0)
    require(seed < 2**32, "seed outside RandomState domain")
    require(request["config"] in CONFIGS, "configuration not among four captured lateral releases")
    expected = "released_lateral_config" if request["cohort"] == "lateral" else "lateral_config_on_medial_unqualified"
    require(request["config_status"] == expected, "medial requires explicit cross-locus configuration status")
    require(isinstance(request["recording_id"], str) and request["recording_id"].strip(), "missing recording identity")
    limits = request["limits"]
    require(type(limits) is dict and set(limits) == {"max_file_bytes", "max_total_input_bytes",
        "max_intervals", "max_repetitions_per_window", "max_scan_values"}, "explicit caller limits required")
    for k, value in limits.items():
        integer(value, k)
    assets = request["assets"]
    require(type(assets) is dict and set(assets) == set(FILES), "all five original inputs are required")
    paths = []
    total = 0
    for name, desc in assets.items():
        require(type(desc) is dict and set(desc) == {"path", "bytes", "sha256", "dtype", "shape"}, "asset keys")
        paths.append(relative(desc["path"]))
        n = integer(desc["bytes"], name + " bytes")
        require(n <= limits["max_file_bytes"], "file allocation exceeds caller bound")
        total += n
        shape = desc["shape"]
        require(type(shape) is list and shape and all(type(x) is int and x > 0 for x in shape), "invalid shape")
        require(desc["dtype"] in ("<f4", "<f8", "|u1"), "unsupported original numerical dtype")
        require(isinstance(desc["sha256"], str) and len(desc["sha256"]) == 64 and
                all(x in "0123456789abcdef" for x in desc["sha256"]), "invalid asset hash")
    require(len(set(paths)) == 5, "duplicate asset path")
    neurons = {"medial": 1905, "lateral": 2022}[request["cohort"]]
    spikes = assets["spikes"]
    require(len(spikes["shape"]) == 2 and spikes["shape"][0] == neurons and
            spikes["dtype"] in ("<f4", "<f8"), "full cohort neuron-by-10-ms rate matrix required")
    ticks = spikes["shape"][1]
    require(ticks % 5 == 0, "unaligned recording tail requires separate scientific qualification")
    samples = ticks // 5
    require(samples <= limits["max_intervals"], "interval capacity exceeded")
    for name in ("speed", "phi", "th"):
        require(assets[name]["shape"] in ([samples], [samples, 1]) and assets[name]["dtype"] in ("<f4", "<f8"),
                "native scalar behavioral stream must retain its full 50-ms clock and original scalar layout")
    video = assets["stimulus"]
    require(video["shape"] == [samples, 1, 64, 112], "source-documented full video shape required")
    require(sum(math.prod(d["shape"]) for d in assets.values()) <= limits["max_scan_values"],
            "full finite-value scan exceeds caller bound")
    provenance = request["provenance"]
    require(type(provenance) is dict and set(provenance) == {"acquisition", "clock_alignment", "physical_units", "run_mapping"},
            "provenance descriptors required; descriptive assertions do not prove them")
    for row in provenance.values():
        require(type(row) is dict and set(row) == {"path", "bytes", "sha256"}, "provenance descriptor keys")
        relative(row["path"])
        size = integer(row["bytes"], "provenance bytes")
        require(size <= min(1024 * 1024, limits["max_file_bytes"]), "provenance capacity exceeded")
        require(isinstance(row["sha256"], str) and len(row["sha256"]) == 64 and
                all(x in "0123456789abcdef" for x in row["sha256"]), "invalid provenance hash")
        total += size
    total += SOURCE_CAPTURE_BYTES
    require(total <= limits["max_total_input_bytes"], "aggregate source/provenance/array input exceeds caller bound")
    return total


def decode_npy(body, desc, np):
    require(body[:6] == b"\x93NUMPY" and body[6:8] in (b"\x01\x00", b"\x02\x00"), "NPY v1/v2 required")
    width = 2 if body[6] == 1 else 4
    require(len(body) >= 8 + width, "short NPY header")
    n = int.from_bytes(body[8:8 + width], "little")
    require(0 < n <= 16384 and 8 + width + n <= len(body), "invalid NPY header size")
    node = ast.parse(body[8 + width:8 + width + n].decode("latin1").strip(), mode="eval")
    require(isinstance(node.body, ast.Dict) and len(node.body.keys) == 3, "NPY header keys")
    header = ast.literal_eval(node)
    require(set(header) == {"descr", "fortran_order", "shape"} and header["fortran_order"] is False,
            "only C-order numeric arrays admitted")
    require(header["descr"] == desc["dtype"] and header["shape"] == tuple(desc["shape"]), "NPY metadata mismatch")
    sizes = {"<f4": 4, "<f8": 8, "|u1": 1}
    offset = 8 + width + n
    require(len(body) == offset + math.prod(desc["shape"]) * sizes[desc["dtype"]], "NPY length mismatch")
    result = np.ndarray(tuple(desc["shape"]), dtype=desc["dtype"], buffer=body, offset=offset, order="C")
    require(not result.flags.writeable, "captured immutable bytes must yield read-only arrays")
    return result


def native_runtime():
    # Deliberately unreachable from --help/import and engineering controls.
    import numpy as np
    import torch
    import pandas as pd
    import yaml
    from torch.utils.data import Dataset
    return SimpleNamespace(np=np, torch=torch, pd=pd, Dataset=Dataset, parse_config=yaml.safe_load)


def _finite_and_expansion(arrays, config, limits, np):
    """Bound expansion BEFORE original repetition allocates token lists.

    All inputs are scanned. Per-bin masses use Python integers, so no int64
    overflow silently admits huge rates. Five-bin moving sums cover arbitrary
    source current/history windows; bounded runtime scratch is one source column.
    Negative rates retain original empty-list repetition; no physical spike claim.
    """
    for array in arrays.values():
        for scalar in array.flat:
            require(math.isfinite(float(scalar)), "nonfinite original observation")
    width = max(round(config.window.curr / config.resolution.dt),
                round(config.window.prev / config.resolution.dt))
    cap = limits["max_repetitions_per_window"]
    ring = collections.deque()
    moving = 0
    maximum = 0
    negative = 0
    spikes = arrays["spikes"]
    for t in range(spikes.shape[1]):
        mass = 0
        for value in spikes[:, t]:
            negative += int(value < 0)
            mass += max(0, round(float(value)))
            require(mass <= cap, "native single-bin repetition capacity exceeded")
        ring.append(mass)
        moving += mass
        if len(ring) > width:
            moving -= ring.popleft()
        require(moving <= cap, "native window repetition capacity exceeded")
        maximum = max(maximum, moving)
    return {"max_rounded_repetitions": maximum, "negative_rate_values": negative,
            "rate_operation": "Python round then ID repetition; no dt multiplication"}


class PreparedNative:
    """Owns full support and lazily calls the original source dataset methods.

    ``item`` returns original (x,y), including source boundary failures. No
    generated-history override is exposed; original get_interval ignores it.
    Outputs are sensitive observations/targets and must remain operator-private.
    """
    def __init__(self, datasets, intervals, tokenizer, evidence):
        self.datasets = datasets
        self.intervals = intervals
        self.tokenizer = tokenizer
        self.evidence = evidence

    def item(self, split, index):
        require(split in ("train", "test", "finetune"), "unknown split")
        integer(index, "item index", 0)
        require(index < len(self.datasets[split]), "item outside support")
        return self.datasets[split][index]

    def tokens(self, split, index):
        require(split in ("train", "test", "finetune"), "unknown split")
        integer(index, "token index", 0)
        d = self.datasets[split]
        require(index < len(d), "token index outside support")
        previous, current = d.calc_intervals(d.t[index])
        return {"previous_interval": previous, "current_interval": current,
                "previous": d.get_interval(previous, 0, d.id_prev_block_size),
                "current": d.get_interval(current, 0, d.id_block_size)}


def construct(request, bodies, arrays, runtime):
    """Actual native conversion, with explicit injectable numerical leaves.

    This lower-level interface expects hash-admitted immutable arrays. ``prepare``
    provides that admission. Tests call this interface with named inert leaves;
    such calls cannot qualify any dataset or scientific result.
    """
    request = copy.deepcopy(request)
    admit_request(request)
    require(set(arrays) == set(FILES), "exact admitted array set required")
    for name, a in arrays.items():
        require(tuple(a.shape) == tuple(request["assets"][name]["shape"]), "runtime shape mismatch")
        require(str(a.dtype) in ({"<f4": "float32", "<f8": "float64", "|u1": "uint8"}[request["assets"][name]["dtype"]],
                                request["assets"][name]["dtype"]), "runtime dtype mismatch")
        require(not a.flags.writeable, "mutable arrays are not admitted")
    ns, loads, selected = compile_selected(bodies, runtime, arrays, request["cohort"], request["seed"])
    config = ns["dict_to_object"](runtime.parse_config(bodies[request["config"]].decode("utf-8")))
    require(config.resolution.dt == .01 and config.window.curr == .05 and config.window.prev == .05
            and config.window.frame == .15, "unexpected native clock configuration")
    for modality in vars(config.modalities).values() if hasattr(config, "modalities") and config.modalities else ():
        for variable in vars(modality.variables).values():
            require(variable.objective == "regression", "no invented class quantizer")
    expansion = _finite_and_expansion(arrays, config, request["limits"], runtime.np)
    data, intervals, train, test, finetune, callback = ns["load_visnav"](request["cohort"], config, selection=None)
    require(len(loads) == 5, "original loader did not request all five inputs")
    require(len(intervals) <= request["limits"]["max_intervals"], "actual interval capacity exceeded")
    round_n = ns["round_n"]
    token_types = {"ID": {"tokens": list(runtime.np.arange(data["spikes"].shape[0]))},
                   "dt": {"tokens": [round_n(x, config.resolution.dt) for x in
                     runtime.np.arange(0, max(config.window.curr, config.window.prev) + config.resolution.dt,
                                       config.resolution.dt)], "resolution": config.resolution.dt}}
    tokenizer = ns["Tokenizer"](token_types)
    spike_dict = {"ID": data["spikes"], "Frames": data["stimulus"], "Interval": intervals,
        "dt": config.resolution.dt, "id_block_size": config.block_size.id,
        "prev_id_block_size": config.block_size.prev_id, "frame_block_size": config.block_size.frame,
        "window": config.window.curr, "window_prev": config.window.prev, "frame_window": config.window.frame}
    def owned_frame_callback(frame_array, frame_index, n_frames, **kwargs):
        # Source-amended ownership boundary: PyTorch does not enforce NumPy's
        # read-only flag. Copy only the exact source-selected frame window, then
        # run the original callback with equivalent relative coordinates.
        # This avoids exposing writable tensors backed by immutable capture bytes.
        first = max(0, frame_index - n_frames)
        owned = frame_array[first:first + n_frames].copy()
        return callback(owned, len(owned), n_frames, **kwargs)

    frames = {"feats": data["stimulus"], "callback": owned_frame_callback,
              "window": config.window.frame, "dt": config.resolution.dt}
    modalities = ns["create_modalities_dict"](data, config.modalities) if getattr(config, "modalities", None) else None
    support = {"all": intervals, "train": train, "test": test, "finetune": finetune}
    datasets = {name: ns["NFDataloader"](spike_dict, tokenizer, config, dataset=request["cohort"],
                 frames=frames, intervals=values, modalities=modalities)
                for name, values in support.items() if name != "all"}
    evidence = {"schema": "neuroformer_native_preparation_evidence_v1", "original_revision": REVISION,
        "source_complete": False, "scientifically_qualified": False, "paper_parity": False,
        "config_status": request["config_status"], "recording_id": request["recording_id"],
        "seed": request["seed"], "rng": "local NumPy RandomState; no earlier random draws",
        "selected_definitions": selected, "native_files_requested": loads,
        "support_counts": {name: len(v) for name, v in support.items()}, "expansion": expansion,
        "native_time_grid_seconds": .01, "prospective_5ms_bridge_produced": False,
        "historical_test_used_during_training": True, "models_trained": False,
        "negative_boundary_intervals_retained": True, "generated_history_supported": False,
        "source_frame_clock_seconds": .05, "frame_covariate_endpoint": "neural endpoint + 0.05 seconds",
        "video_ownership_boundary": "source-amended exact-window copy before original callback",
        "behavior_source_shapes": {k: request["assets"][k]["shape"] for k in ("speed", "phi", "th")},
        "provenance_verified_scientifically": False}
    return PreparedNative(datasets, support, tokenizer, evidence)


def prepare(request, array_root, source_root=None, *, runtime=None):
    """Authenticate the original source, provenance bodies and all original arrays.

    Explicit caller byte/count/expansion caps are admission bounds, NOT a measured
    RSS or authorization. Immutable captured bytes remain backing array storage.
    Physical clocks/units/run mapping require a separate scientific review.
    """
    request = copy.deepcopy(request)
    total = admit_request(request)
    root = Path(source_root) if source_root is not None else Path(__file__).resolve().parents[1]
    bodies = source_snapshot(root)
    provenance = {}
    for name, descriptor in request["provenance"].items():
        provenance[name] = capture(Path(array_root), descriptor, 1024 * 1024)
    runtime = native_runtime() if runtime is None else runtime
    arrays = {}
    for name, descriptor in request["assets"].items():
        body = capture(Path(array_root), descriptor, request["limits"]["max_file_bytes"])
        arrays[name] = decode_npy(body, descriptor, runtime.np)
    prepared = construct(request, bodies, arrays, runtime)
    prepared.evidence["input_bytes"] = total
    prepared.evidence["provenance_hashes"] = {k: sha(v) for k, v in provenance.items()}
    prepared.evidence["acquisition_identity_authentication"] = "declared immutable file hashes; physical provenance unqualified"
    return prepared
