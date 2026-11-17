"""Fixed trusted historical-lateral source entry; no native work at import.

Future run_historical consumes private operator operands and trains a real model.
Source construction/engineering checks do not authorize that future operation.
The original97 bodies and generic false/null registration stay unchanged.
"""
from __future__ import annotations

import ast
import builtins
import copy
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import stat
import sys
import threading
import types

ROOT = Path(__file__).resolve().parent
PREDECESSOR = (31911, "b6640ed96bae833cf89dc85835d503e25fa9389e2be3f8029fbd41a79aaa8166")
# Bound to the helper's coherent final source before any author control/freeze.
RUNTIME_SOURCE = (23526, "ae1d9f9af3bdb4271c915086b5ed46ad45508fe64e62593c43e6dd2a47684ba4")
CONFIG = "configs/Visnav/lateral/mconf_predict_all.yaml"
CONFIG_PIN = (1464, "07f6fcb647966c4fbad0a07eb711de2d00f413277083afc6063c5c22cb377e3e")
HISTORICAL = "released_computational_path_10ms"
CELLS = (
    "lateral--speed_regression--neuroformer--100::" + HISTORICAL,
    "lateral--joint_speed_gaze--neuroformer--100::" + HISTORICAL,
)
REVISION = "36ed94084628c253098d448048c980d3dea0050d"
LOCK = threading.Lock()
ONE = 1048576
LIMITS = {"max_total_read_bytes", "max_checkpoint_files", "max_checkpoint_file_bytes",
          "max_checkpoint_total_bytes", "max_scalar_values"}


class Refusal(ValueError):
    pass


class FactoryFailure(RuntimeError):
    """Private failure observation; its cause is the original error, never success."""
    def __init__(self, message, receipt):
        super().__init__(message)
        self.receipt = receipt


def require(value, message):
    if not value:
        raise Refusal(message)


def positive(value, name):
    require(type(value) is int and value > 0, name + " must be a positive integer")
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def parse(body):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(Refusal("nonfinite JSON")))


def relative(value):
    require(type(value) is str and value and "\\" not in value, "relative source name")
    p = PurePosixPath(value)
    require(not p.is_absolute() and str(p) == value and all(x not in ("", ".", "..") for x in value.split("/")),
            "canonical relative source name")
    return p


def directory(value):
    require(type(value) is str, "operator directory string")
    p = Path(value)
    require(p.is_absolute() and ".." not in p.parts and str(p) == value, "canonical absolute operator directory")
    for part in (p, *p.parents):
        require(stat.S_ISDIR(part.lstat().st_mode) and not part.is_symlink(), "ordinary directory ancestry")
    return p


class Reads:
    def __init__(self, cap):
        self.cap = positive(cap, "read reservation")
        self.reserved = 0

    def reserve(self, size):
        require(type(size) is int and size >= 0, "nonnegative byte reservation")
        self.reserved += size
        require(self.reserved <= self.cap, "cumulative read reservation exceeded")


def capture(path, expected, meter, cap=ONE):
    n, digest = expected
    require(type(n) is int and 0 <= n <= cap and type(digest) is str and len(digest) == 64,
            "exact bounded source descriptor")
    meter.reserve(n + 1)  # Preserve failed/EOF-probe reservation, never reset it.
    directory(str(path.parent))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == n,
                "ordinary exact single-link source")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            body = handle.read(n + 1)
        key = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(key(before) == key(os.fstat(fd)) == key(path.lstat()), "source changed during capture")
        require(len(body) == n and hashlib.sha256(body).hexdigest() == digest, "source bytes or digest mismatch")
        return body
    finally:
        os.close(fd)


def source_capture(meter):
    predecessor = parse(capture(ROOT / "NATIVE_FACTORY_PREDECESSOR.json", PREDECESSOR, meter))
    require(predecessor["count"] == len(predecessor["files"]) == 97 and predecessor["total_bytes"] == 1018684,
            "complete unchanged predecessor")
    bodies = {}
    for row in predecessor["files"]:
        name = str(relative(row["path"]))
        require(name not in bodies, "duplicate predecessor member")
        bodies[name] = capture(ROOT / name, (row["bytes"], row["sha256"]), meter)
    require(sum(map(len, bodies.values())) == 1018684, "full predecessor extent")
    runtime = capture(ROOT / "native_factory_runtime.py", RUNTIME_SOURCE, meter)
    return bodies, runtime


class Sources:
    """Private source namespaces: fixed imports, no ambient task module names."""
    def __init__(self, bodies, runtime_body):
        self.bodies, self.runtime_body = bodies, runtime_body
        digest = hashlib.sha256(canonical({k: hashlib.sha256(v).hexdigest() for k, v in sorted(bodies.items())}) + runtime_body).hexdigest()
        self.prefix = "_neuroformer_factory_operator_" + digest
        self.owned = {}
        self.modules = {}

    def register(self, suffix, body, path, imports):
        name = self.prefix + "." + suffix
        require(name not in sys.modules, "captured source namespace collision")
        module = types.ModuleType(name)
        module.__file__ = str(path)
        module.__package__ = self.prefix
        safe = dict(vars(builtins))
        ordinary = {"__future__", "ast", "copy", "hashlib", "json", "math", "struct", "pathlib",
                    "types", "os", "stat", "collections", "numbers"}
        def importer(target, globals=None, locals=None, fromlist=(), level=0):
            require(level == 0, "unexpected relative operator import")
            if target in imports:
                return imports[target]
            require(target.split(".")[0] in ordinary, "unexpected operator dependency: " + target)
            return builtins.__import__(target, globals, locals, fromlist, level)
        safe["__import__"] = importer
        module.__dict__["__builtins__"] = safe
        sys.modules[name] = module
        self.owned[name] = module
        try:
            exec(compile(body, str(path), "exec"), module.__dict__)
        except BaseException:
            self.close()
            raise
        return module

    def __enter__(self):
        require(not any(n == self.prefix or n.startswith(self.prefix + ".") for n in sys.modules),
                "captured operator package already owned")
        parent = types.ModuleType(self.prefix)
        parent.__path__ = []
        sys.modules[self.prefix] = parent
        self.owned[self.prefix] = parent
        for name in ("native_dataset", "run_composition", "run_metrics", "protected_rollout"):
            path = "source/operator/" + name + ".py"
            self.modules[name] = self.register(name, self.bodies[path], ROOT / path, self.modules)
        # Helper source is independently pinned; its only import-time effects are
        # definitions/stdlib bindings. It has its own source-registry ownership.
        name = self.prefix + ".runtime"
        require(name not in sys.modules, "runtime namespace collision")
        module = types.ModuleType(name);module.__file__ = str(ROOT / "native_factory_runtime.py")
        module.__package__ = self.prefix
        sys.modules[name] = module;self.owned[name] = module
        try:
            exec(compile(self.runtime_body, module.__file__, "exec"), module.__dict__)
        except BaseException:
            self.close();raise
        self.runtime_module = module
        return self

    def close(self):
        changed = []
        for name, module in reversed(list(self.owned.items())):
            if sys.modules.get(name) is module:
                del sys.modules[name]
            else:
                changed.append(name)
        self.owned.clear()
        require(not changed, "captured namespace ownership changed: " + repr(changed))

    def __exit__(self, exc_type, exc, tb):
        try:
            self.close()
        except BaseException as cleanup:
            if exc is not None:
                exc.add_note("Secondary namespace release failure: " + repr(cleanup))
            else:
                raise


def validate_request(request):
    require(type(request) is dict and set(request) == {"schema", "cell_id", "array_root", "native_request", "job", "limits"},
            "closed historical factory request")
    request = parse(canonical(request))
    require(request["schema"] == "neuroformer_historical_lateral_factory_v1" and request["cell_id"] in CELLS,
            "only two selected historical lateral cells")
    require(type(request["limits"]) is dict and set(request["limits"]) == LIMITS, "complete factory bounds")
    for k, v in request["limits"].items(): positive(v, k)
    require(3 <= request["limits"]["max_checkpoint_files"] <= 64 and
            request["limits"]["max_checkpoint_file_bytes"] <= 1073741824 and
            request["limits"]["max_checkpoint_total_bytes"] <= 2147483648,
            "checkpoint hard guards before any operation")
    n, j = request["native_request"], request["job"]
    require(type(n) is dict and type(j) is dict, "native recording/job records")
    require(set(j) == {"run_id", "seed", "config_identity", "run_provenance", "support", "output_directory",
                       "original_interval_count", "limits", "historical_true_past"}, "closed original job")
    require(type(j["run_id"]) is str and bool(j["run_id"]), "explicit run identity")
    require(type(j["output_directory"]) is str and Path(j["output_directory"]).is_absolute(), "absolute output")
    positive(j["original_interval_count"], "full native interval count")
    require(type(j["limits"]) is dict and set(j["limits"]) ==
            {"max_support_rows", "max_prediction_rows", "max_native_intervals"}, "original caller limits")
    for k, v in j["limits"].items(): positive(v, k)
    require(type(j["support"]) is dict and set(j["support"]) == {"train", "selection", "evaluation"} and
            all(type(v) is list and v for v in j["support"].values()), "full original support roles")
    require(sum(map(len, j["support"].values())) <= j["limits"]["max_support_rows"] and
            len(j["support"]["evaluation"]) <= j["limits"]["max_prediction_rows"] and
            j["original_interval_count"] <= j["limits"]["max_native_intervals"], "early original caller capacity")
    modes = 3 if "--joint_speed_gaze--" in request["cell_id"] else 1
    require(len(j["support"]["evaluation"]) * modes <= request["limits"]["max_scalar_values"],
            "full scalar admission before native work")
    for key in ("config_identity", "run_provenance"):
        d = j[key]
        require(type(d) is dict and set(d) == {"path", "bytes", "sha256"}, "exact job descriptor")
        relative(d["path"]); positive(d["bytes"], "descriptor extent")
        require(type(d["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", d["sha256"]), "descriptor digest")
    require(n.get("cohort") == "lateral" and n.get("config") == CONFIG and n.get("config_status") == "released_lateral_config",
            "exact selected lateral predictive recipe")
    require(type(j.get("seed")) is int and 0 <= j["seed"] < 2**32 and n.get("seed") == j["seed"], "same explicit source seed")
    require(j.get("config_identity") == {"path": CONFIG, "bytes": CONFIG_PIN[0], "sha256": CONFIG_PIN[1]}, "exact source configuration identity")
    require(j.get("run_provenance") == n.get("provenance", {}).get("run_mapping"), "one bound run mapping")
    require(type(j.get("historical_true_past")) is bool, "explicit historical history flag")
    return request


class Output:
    """Fresh trusted-operator output ownership; not hostile-process containment."""
    def __init__(self, value):
        self.path = Path(value)
        require(self.path.is_absolute() and str(self.path) == value and self.path.name not in ("", ".", ".."), "absolute fresh output")
        parent = directory(str(self.path.parent))
        self.parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.fd = None
        try:
            os.mkdir(self.path.name, 0o700, dir_fd=self.parent_fd)
            self.fd = os.open(self.path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.parent_fd)
            self.stamp = (os.fstat(self.fd).st_dev, os.fstat(self.fd).st_ino)
            self.check()
        except BaseException:
            self.close();raise

    def check(self):
        require(self.fd is not None, "output not owned")
        now = os.stat(self.path.name, dir_fd=self.parent_fd, follow_symlinks=False)
        require(stat.S_ISDIR(now.st_mode) and (now.st_dev, now.st_ino) == self.stamp and
                (self.path.lstat().st_dev, self.path.lstat().st_ino) == self.stamp, "output namespace changed")

    def close(self):
        if self.fd is not None: os.close(self.fd);self.fd = None
        if self.parent_fd is not None: os.close(self.parent_fd);self.parent_fd = None


class Providers:
    def __init__(self, prepared, request, configuration_body):
        self.prepared, self.request = prepared, request
        self.configuration_body = configuration_body
        self.trace = []

    def configuration(self, identity, run):
        require(identity == self.request["job"]["config_identity"] and run == self.request["job"]["run_provenance"], "captured configuration/run join")
        require(hashlib.sha256(self.configuration_body).hexdigest() == identity["sha256"], "consumed config hash")
        self.trace.append("configuration")
        return {"cohort": "lateral", "config_status": "released_lateral_config",
                "config": self.prepared.datasets["train"].config, "tokenizer": self.prepared.tokenizer}

    def select(self, role, rows, split):
        require(rows == self.request["job"]["support"][role], "complete selected provider support")
        self.trace.append(role)
        return self.prepared.datasets[split]

    def training(self, rows): return self.select("train", rows, "train")
    def selection(self, rows): return self.select("selection", rows, "test")

    def historical_finetune(self, rows):
        expected = self.request["job"]["support"]["train"][:int(len(self.prepared.datasets["train"]) * .01)]
        require(rows == expected, "literal historical finetune prefix")
        self.trace.append("historical_finetune")
        return self.prepared.datasets["finetune"]

    def protected_queries(self, rows):
        raise Refusal("protected query policy is not selected by this historical factory")


def _runtime(captured):
    """Fixed production binding; engineering controls replace this leaf explicitly."""
    return captured.native_runtime()


def _checkpoint(output, limits, meter, runtime_module):
    output.check()
    names = sorted(os.listdir(output.fd))
    require(0 < len(names) <= limits["max_checkpoint_files"], "complete checkpoint file count")
    require({"mconf.yaml", "tokenizer.pkl", "model.pt"} <= set(names), "selected current checkpoint trio")
    require(all(n in {"mconf.yaml", "tokenizer.pkl", "model.pt", "tconf.yaml"} or
                re.fullmatch(r"_epoch_[A-Za-z0-9_.-]{1,80}\.pt", n) for n in names), "unexpected checkpoint member before body read")
    bodies, descriptors = {}, {}
    total = 0
    for name in names:
        require("/" not in name and "\\" not in name, "checkpoint basename")
        s = os.stat(name, dir_fd=output.fd, follow_symlinks=False)
        require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, "ordinary checkpoint artifact")
        total += s.st_size
        require(0 < s.st_size <= limits["max_checkpoint_file_bytes"] and total <= limits["max_checkpoint_total_bytes"], "checkpoint byte admission")
        meter.reserve(s.st_size + 1)
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=output.fd)
        try:
            before = os.fstat(fd)
            with os.fdopen(fd, "rb", closefd=False) as f: b = f.read(s.st_size + 1)
            key = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
            require(key(s) == key(before) == key(os.fstat(fd)) == key(os.stat(name, dir_fd=output.fd, follow_symlinks=False)), "checkpoint changed during capture")
            require(len(b) == s.st_size, "checkpoint extent changed")
        finally: os.close(fd)
        bodies[name] = b
        descriptors[name] = {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
    output.check()
    return runtime_module.CapturedCheckpoint(bodies, descriptors, directory=str(output.path), limits={
        "max_files": limits["max_checkpoint_files"], "max_file_bytes": limits["max_checkpoint_file_bytes"],
        "max_total_bytes": limits["max_checkpoint_total_bytes"]})


def _execute(request, sources, meter, observation):
    native = sources.modules["native_dataset"]
    composition = sources.modules["run_composition"]
    metrics = sources.modules["run_metrics"]
    original_capture = native.capture
    def metered_capture(root, descriptor, limit):
        meter.reserve(descriptor["bytes"] + 1)
        return original_capture(root, descriptor, limit)
    native.capture = metered_capture
    array_root = directory(request["array_root"])
    n, job, limits = request["native_request"], request["job"], request["limits"]
    native.admit_request(n)
    composition.admit_support(job["support"], HISTORICAL)
    require(all(row["recording"] == n["recording_id"] for rows in job["support"].values() for row in rows), "one exact selected recording")
    run_body = native.capture(array_root, job["run_provenance"], ONE)
    run = parse(run_body)
    expected_run = {"schema": "neuroformer_operator_selected_historical_run_v1", "identity_scope": "operator_selected_source_run_not_authenticated_author_run",
                    "run_id": job["run_id"], "seed": job["seed"], "cohort": "lateral", "source_revision": REVISION,
                    "config_identity": job["config_identity"], "condition": HISTORICAL,
                    "historical_true_past": job["historical_true_past"],
                    "support_sha256": hashlib.sha256(canonical(job["support"])).hexdigest()}
    require(run == expected_run, "closed actual run binding; no invented author identity")
    bodies = native.source_snapshot(ROOT / "source")
    require((len(bodies[CONFIG]), hashlib.sha256(bodies[CONFIG]).hexdigest()) == CONFIG_PIN, "captured predictive configuration")
    output = None
    checkpoint = None
    with sources.runtime_module.CapturedModules(bodies, {"native_dataset.py": sources.bodies["source/operator/native_dataset.py"]}) as captured:
        native.compile_selected = captured.compile_preparation
        output = Output(job["output_directory"])
        observation["output_directory"] = str(output.path)
        observation["output_policy"] = "fresh operator-owned; original files retained on success/failure; no cleanup or containment claim"
        runtime = None
        base_torch = None
        try:
            require(not any(k in os.environ for k in ("RANK", "WORLD_SIZE", "LOCAL_RANK")),
                    "ambient distributed rank contradicts selected single-process caller")
            runtime = _runtime(captured)
            base_torch = runtime.torch
            prepared = native.prepare(n, array_root, source_root=ROOT / "source", runtime=runtime)
            recipe = parse(canonical(runtime.object_to_dict(prepared.datasets["train"].config)))
            require(recipe.pop("epoch", None) == 0, "fixed source recipe initial epoch")
            recipe["id_vocab_size"] = int(prepared.tokenizer.ID_vocab_size)
            def load_owned(path):
                nonlocal checkpoint
                require(path == str(output.path) and checkpoint is None, "single owned historical checkpoint selection")
                checkpoint = _checkpoint(output, limits, meter, sources.runtime_module)
                runtime.torch = base_torch
                config, tokenizer, model = checkpoint.load_original(captured, runtime)
                require(type(tokenizer) is type(prepared.tokenizer) and vars(tokenizer) == vars(prepared.tokenizer), "genuine source tokenizer identity/state roundtrip")
                selected = parse(canonical(runtime.object_to_dict(config)))
                epoch = selected.pop("epoch", None)
                max_epochs = composition.training_constants(bodies)["MAX_EPOCHS"]
                require(type(epoch) is int and 1 <= epoch <= max_epochs, "actual saved training epoch within literal source run")
                require(selected == recipe, "selected checkpoint configuration equals fixed recipe plus tokenizer geometry")
                observation["selected_checkpoint_epoch"] = epoch
                require(model.config is config and model.tokenizer is tokenizer, "actual loaded model/config/tokenizer join")
                runtime.torch = checkpoint.torch_for_runtime(base_torch)
                return config, tokenizer, model
            runtime.load_model_and_tokenizer = load_owned
            providers = Providers(prepared, request, bodies[CONFIG])
            matrix = parse(sources.bodies["source/operator/RUN_MATRIX.json"])
            calls = composition.ReleasedCalls(bodies, runtime)
            result = composition.dispatch_native(matrix, request["cell_id"], calls, job, providers)
            require(checkpoint is not None, "actual owned checkpoint was not consumed")
            output.check()
            expected = {"cell_id": request["cell_id"], "condition": HISTORICAL, "support": job["support"]["evaluation"],
                        "modes": ["speed", "phi", "th"] if "--joint_speed_gaze--" in request["cell_id"] else ["speed"]}
            packet = metrics.assemble_behavior_packet(result, expected, max_values=limits["max_scalar_values"])
            observation.update({"provider_calls": providers.trace, "preparation": prepared.evidence,
                                "checkpoint": checkpoint.receipt(), "read_reserved_bytes": meter.reserved})
            return {"schema": "neuroformer_historical_lateral_factory_result_v1", "cell_id": request["cell_id"],
                    "condition": HISTORICAL, "behavior_packet": packet, "private_original_inference": result["historical_inference"],
                    "source_observation": observation, "all_outputs_operator_private": True,
                    "source_complete": False, "runnable": False, "scientifically_qualified": False,
                    "generic_execution_admitted": False, "historical_test_exposure_preserved": True,
                    "all46_slots85_cells7_families29_holds_retained": True}
        finally:
            if runtime is not None and base_torch is not None: runtime.torch = base_torch
            if checkpoint is not None: observation["checkpoint"] = checkpoint.receipt()
            if output is not None: output.close()


def run_historical(request):
    """Future private source operation. No caller source/runtime/provider injection."""
    request = validate_request(request)
    meter = Reads(request["limits"]["max_total_read_bytes"])
    observation = {"status": "incomplete", "native_or_scientific_qualification": False}
    require(LOCK.acquire(blocking=False), "trusted serial non-reentrant factory")
    try:
        bodies, helper = source_capture(meter)
        with Sources(bodies, helper) as sources:
            result = _execute(request, sources, meter, observation)
        observation["status"] = "source_operation_returned_no_qualification"
        observation["read_reserved_bytes"] = meter.reserved
        return result
    except Exception as error:
        observation.update({"status": "failed", "read_reserved_bytes": meter.reserved,
                            "error_type": type(error).__name__, "error": str(error)})
        raise FactoryFailure("Historical source factory failed; original cause and owned outputs retained", observation) from error
    finally:
        LOCK.release()
