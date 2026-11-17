"""Captured Neuroformer module identity and checkpoint-byte consumption.

Import is standard-library-only. Native dependencies are loaded solely by the
explicit native_runtime call. This trusted-operator component is not a sandbox
or scientific qualification and does not run the upstream entrypoint scripts.
"""
from __future__ import annotations

import ast
import builtins
import collections
import hashlib
import importlib
from importlib.machinery import ModuleSpec
import io
import json
import os
from pathlib import Path, PurePosixPath
import pickle
import re
import sys
import threading
from types import MappingProxyType, ModuleType, SimpleNamespace

SOURCE_PINS = {'LICENSE': {'bytes': 1066, 'sha256': '6e0003990cc525a4abe56f5b7803c5c3eeb8d7842e7ccd7ddd5dbc4d4777e9a3'}, 'README.md': {'bytes': 9869, 'sha256': '61af2ba081b718267d553e2553783cc7a449191963c0743d16b24a08853ff555'}, 'configs/V1AL/mconf.yaml': {'bytes': 1049, 'sha256': 'cf6c0f6cd8b5a36352c695a63c306b04c6e4005582f3638b1fc54b8d65b098ab'}, 'configs/Visnav/lateral/mconf_predict_all.yaml': {'bytes': 1464, 'sha256': '07f6fcb647966c4fbad0a07eb711de2d00f413277083afc6063c5c22cb377e3e'}, 'configs/Visnav/lateral/mconf_predict_all_input_contrastive_visual.yaml': {'bytes': 1459, 'sha256': 'c295bd47e398919cb263316cbaaec3430e6eaf46a2eb88b1f31a73d57a94ded7'}, 'configs/Visnav/lateral/mconf_pretrain.yaml': {'bytes': 1554, 'sha256': '762cf54719b71080aa5468ac8bd0494dbf21d73755001fd94cd2f1f8c75495ed'}, 'configs/Visnav/lateral/mconf_pretrain_all_input_contrastive.yaml': {'bytes': 1455, 'sha256': 'df88b773d669d01de31e038f5941b8b38ad0344208053a970f4e2f345154be46'}, 'launch.sh': {'bytes': 1277, 'sha256': '33320ab7b433d59ec5625ce4c49986972857b5e274b2ecc318805a5720571df2'}, 'neuroformer/__init__.py': {'bytes': 0, 'sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}, 'neuroformer/analysis.py': {'bytes': 16758, 'sha256': '20f9988c5c01893a9d34e7a68fe0213b9934495509ade3292a8a1a9f3d9901ca'}, 'neuroformer/attention_vis.py': {'bytes': 47361, 'sha256': '3f3b573900dc4e8d100126925c0627875171448040c09c5b595f1aefdc37ef51'}, 'neuroformer/data_utils.py': {'bytes': 53196, 'sha256': '71ec03aa43aa911c53d680d9f7a8e0f9fd677f50f97ab983acccfcd63ffa15e4'}, 'neuroformer/datasets.py': {'bytes': 4853, 'sha256': '9301d689076ce2ab608c0c41765616edee5f33014f2ede676fced7a5aa904e89'}, 'neuroformer/default_args.py': {'bytes': 3890, 'sha256': 'e6e595bcdf99f4aba3db2ad5d126d5b129251af4638dc8a06887c166318b1190'}, 'neuroformer/gather_atts.py': {'bytes': 8524, 'sha256': '84b9265aa94cc35923f990ca74adcb3311383c4743167e7415ebe14a1b4ff5e7'}, 'neuroformer/hparam_sweep.py': {'bytes': 2503, 'sha256': '8466ac9261ae6bd9d05e130f7922105e2bb05dc038f5ba783db55df542cba099'}, 'neuroformer/model_neuroformer.py': {'bytes': 58004, 'sha256': '919dbeed014d1a600743d415cccfb594caf74f7edf47cfa5b3747ba0456bb3cd'}, 'neuroformer/modules.py': {'bytes': 16575, 'sha256': 'd8d584380a5d985046bc6ab440f273500cbb65e4d8d904fa468de83c15148371'}, 'neuroformer/simulation.py': {'bytes': 20772, 'sha256': 'cb7b0a2445c468e13ab197a69205b08cc4b15907ef36bb3fe593a8dced75033d'}, 'neuroformer/trainer.py': {'bytes': 17599, 'sha256': '24c99e1e8b45ec8a243216469ee6fecd20e5a94ecedd7bb24f37eb5af649b3f3'}, 'neuroformer/utils.py': {'bytes': 35779, 'sha256': '31c53331fb3bf86c54cd7ace5224f5fd8b61f910d58d76bc06e20707eeffd7a3'}, 'neuroformer/visualize.py': {'bytes': 46238, 'sha256': 'ea0d5b0987460934304b3e2f6977ae5a34458478ac670dca63583e69e50739bd'}, 'neuroformer_inference.py': {'bytes': 9175, 'sha256': '2a2047d472c0ebe56233ab8ebaafee9951472ccaa64c67debcd9f792673bc26c'}, 'neuroformer_train.py': {'bytes': 8531, 'sha256': '9dbb86497df842ce99e61a0241bfacb848ac864e99eb1caecda765bb3364dea9'}, 'requirements.txt': {'bytes': 5766, 'sha256': '5b4bac66f65012fbd1dbea47cfb71e97b08c4c0c4b3ad2cdec03d82723579da7'}, 'setup_env.sh': {'bytes': 431, 'sha256': '366cc8e65273bfd7d68bda56a05940756a433b4e5a2d971c5c2b06f33b9a03e7'}}
OPERATOR_PINS = {"native_dataset.py": {"bytes": 22893, "sha256": "dc5275f37f1fec542e33cb8de63a4ad9c792f9710a5df694ee765870bf15881e"}}
MODULE_SCHEMA = "neuroformer-captured-modules-v1"
CHECKPOINT_HARD_LIMITS = {"max_files": 64, "max_file_bytes": 1073741824, "max_total_bytes": 2147483648}
_LEASE_LOCK = threading.RLock()
_REQUIRED = frozenset(("mconf.yaml", "tokenizer.pkl", "model.pt"))
_EPOCH = re.compile(r"_epoch_[A-Za-z0-9_.-]{1,80}\.pt\Z")
_LOCAL = {"utils": "utils", "modules": "modules", "model_neuroformer": "model_neuroformer",
          "trainer": "trainer", "simulation": "simulation"}


class Refusal(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Refusal(message)


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def _authenticate(bodies, expected, label):
    require(type(bodies) is dict and set(bodies) == set(expected), "exact " + label + " body map required")
    result = {}
    for name, descriptor in expected.items():
        body = bodies[name]
        require(type(body) is bytes and pin(body) == descriptor, "wrong captured " + label + " body: " + name)
        body.decode("utf-8")
        require(b"\0" not in body, "non-source body")
        result[name] = body
    return MappingProxyType(result)


def _effective(body, path, name):
    matches = [n for n in ast.parse(body, filename=path).body
               if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name]
    require(bool(matches), "missing captured definition: " + name)
    return matches[-1]


def _exec_definition(body, path, name, namespace):
    node = _effective(body, path, name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<captured:" + path + ">", "exec"), namespace)
    return namespace[name]


class CapturedModules:
    """Exclusive lifetime for authenticated digest-derived Python module names.

    A fresh consumer must enter a new equivalent context before unpickling. The
    original Tokenizer class is defined in the registered preparation module at
    definition time; its __module__ is never relabeled after construction.
    """
    def __init__(self, bodies, operator_bodies):
        self.bodies = _authenticate(bodies, SOURCE_PINS, "original source")
        self.operator_bodies = _authenticate(operator_bodies, OPERATOR_PINS, "operator")
        identity = {"schema": MODULE_SCHEMA, "original": SOURCE_PINS, "operator": OPERATOR_PINS}
        self.digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.name = "_neuroformer_captured_" + self.digest
        self._owned = {}
        self._active = False
        self._prepared = False
        self._runtime = None
        self._loading = set()
        self._failed = set()
        self._tokenizer_class = None

    def _register(self, suffix, *, package=False):
        name = self.name + ("." + suffix if suffix else "")
        require(name not in sys.modules, "captured module collision: " + name)
        module = ModuleType(name)
        module.__package__ = self.name if suffix else self.name
        module.__spec__ = ModuleSpec(name, loader=None, is_package=package)
        if package:
            module.__path__ = []
        module.__file__ = "<captured:" + name + ">"
        sys.modules[name] = module
        self._owned[name] = module
        if suffix:
            setattr(self._owned[self.name], suffix, module)
        return module

    def _assert_active(self):
        require(self._active, "captured module context is not active")
        require(all(sys.modules.get(name) is module for name, module in self._owned.items()),
                "captured module ownership changed")
        require(all(name == self.name or getattr(self._owned[self.name], name.rsplit(".", 1)[1], None) is module
                    for name, module in self._owned.items()), "captured package binding changed")
        if self._tokenizer_class is not None:
            require(self.preparation.Tokenizer is self._tokenizer_class, "captured Tokenizer class binding changed")

    def __enter__(self):
        with _LEASE_LOCK:
            require(not self._active and not self._owned, "context objects cannot be reused")
            require(not any(k == self.name or k.startswith(self.name + ".") for k in tuple(sys.modules)),
                    "captured namespace already occupied")
            self._register("", package=True)
            self.preparation = self._register("preparation")
            self._active = True
            try:
                self._tokenizer_class = _exec_definition(self.bodies["neuroformer/data_utils.py"],
                    "neuroformer/data_utils.py", "Tokenizer", self.preparation.__dict__)
                require(self._tokenizer_class.__module__ == self.preparation.__name__, "Tokenizer definition module mismatch")
            except BaseException:
                self.__exit__(*sys.exc_info())
                raise
        return self

    def __exit__(self, exc_type, exc, tb):
        changed = []
        with _LEASE_LOCK:
            for name, module in reversed(tuple(self._owned.items())):
                if sys.modules.get(name) is module:
                    del sys.modules[name]
                else:
                    changed.append(name)
            self._active = False
        if changed:
            raise Refusal("foreign replacements retained; captured namespace ownership changed: " + repr(changed)) from exc
        return False

    def _bind_preparation(self, bindings):
        self._assert_active()
        self.preparation.__dict__.update(bindings)
        return self.preparation.__dict__

    def compile_preparation(self, bodies, runtime, arrays, cohort, seed):
        """Original compile_selected ABI, with one namespace-only adaptation.

        Call once per lifetime, before retaining live datasets. Repeated calls
        would rebind globals of their classes and are refused. Only the exact
        original Tokenizer definition is reused rather than redefined.
        """
        self._assert_active()
        _authenticate(bodies, SOURCE_PINS, "original source")
        require(not self._prepared, "one preparation binding per captured lifetime")
        self._prepared = True
        module = self._register("native_dataset")
        body = self.operator_bodies["native_dataset.py"]
        exec(compile(body, "<captured:native_dataset.py>", "exec"), module.__dict__)
        node = _effective(body, "native_dataset.py", "compile_selected")
        changes = {"namespace": 0, "exec": 0}

        class NamespaceBinding(ast.NodeTransformer):
            def visit_Assign(self, item):
                if any(isinstance(t, ast.Name) and t.id == "namespace" for t in item.targets):
                    changes["namespace"] += 1
                    item.value = ast.Call(func=ast.Name(id="_registered_preparation", ctx=ast.Load()), args=[item.value], keywords=[])
                return self.generic_visit(item)

            def visit_Expr(self, item):
                if isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Name) and item.value.func.id == "exec":
                    changes["exec"] += 1
                    return ast.copy_location(ast.If(test=ast.Compare(left=ast.Name(id="name", ctx=ast.Load()),
                        ops=[ast.NotEq()], comparators=[ast.Constant(value="Tokenizer")]), body=[item], orelse=[]), item)
                return self.generic_visit(item)

        amended = ast.fix_missing_locations(NamespaceBinding().visit(node))
        require(changes == {"namespace": 1, "exec": 1}, "unexpected preparation compiler shape")
        module.__dict__["_registered_preparation"] = self._bind_preparation
        exec(compile(ast.Module(body=[amended], type_ignores=[]), "<captured:preparation-namespace-amendment>", "exec"), module.__dict__)
        namespace, loads, selected = module.compile_selected(dict(self.bodies), runtime, arrays, cohort, seed)
        require(namespace is self.preparation.__dict__ and namespace["Tokenizer"] is self._tokenizer_class,
                "preparation replaced genuine registered Tokenizer")
        return namespace, loads, selected

    def _private_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        self._assert_active()
        require(level == 0, "unexpected relative captured import")
        short = name.removeprefix("neuroformer.")
        if short in _LOCAL and (name == short or name == "neuroformer." + short):
            module = self._native_module(short)
            return module if fromlist or name == short else self._owned[self.name]
        require(not (name == "neuroformer" or name.startswith("neuroformer.") or name in ("data_utils", "datasets")),
                "unselected project import")
        return builtins.__import__(name, globals, locals, fromlist, level)

    def _native_module(self, short):
        self._assert_active()
        require(short in _LOCAL, "unselected native module")
        name = self.name + "." + short
        if name in self._owned:
            require(short not in self._loading and short not in self._failed, "captured module is incomplete after cycle/failure")
            return self._owned[name]
        module = self._register(short)
        namespace_builtins = dict(vars(builtins))
        namespace_builtins["__import__"] = self._private_import
        module.__dict__["__builtins__"] = namespace_builtins
        self._loading.add(short)
        try:
            # Full authenticated module bodies preserve Python's effective last
            # definition. These are library modules, never train/inference scripts.
            exec(compile(self.bodies["neuroformer/" + short + ".py"],
                         "<captured:neuroformer/" + short + ".py>", "exec"), module.__dict__)
        except BaseException:
            self._failed.add(short)
            raise
        finally:
            self._loading.remove(short)
        return module

    def native_runtime(self):
        """Lazy fixed native assembly; not invoked by source/serialization controls."""
        self._assert_active()
        require(not any(k in os.environ for k in ("RANK", "WORLD_SIZE", "LOCAL_RANK")),
                "ambient distributed execution is not admitted")
        if self._runtime is not None:
            return self._runtime
        np = importlib.import_module("numpy")
        torch = importlib.import_module("torch")
        pd = importlib.import_module("pandas")
        yaml = importlib.import_module("yaml")
        data = importlib.import_module("torch.utils.data")
        functional = importlib.import_module("torch.nn.functional")
        utils = self._native_module("utils")
        model = self._native_module("model_neuroformer")
        trainer = self._native_module("trainer")
        simulation = self._native_module("simulation")

        def uncaptured_checkpoint(*args, **kwargs):
            raise Refusal("bind an authenticated own-output checkpoint before loading")

        self._runtime = SimpleNamespace(Neuroformer=model.Neuroformer, TrainerConfig=trainer.TrainerConfig,
            Trainer=trainer.Trainer, decode_modality=simulation.decode_modality,
            generate_spikes=simulation.generate_spikes, set_seed=utils.set_seed, all_device=utils.all_device,
            object_to_dict=utils.object_to_dict, dict_to_object=utils.dict_to_object,
            load_config=utils.load_config, parse_config=yaml.safe_load, yaml=yaml,
            np=np, torch=torch, pd=pd, DataLoader=data.DataLoader, Dataset=data.Dataset,
            F=functional,
            load_model_and_tokenizer=uncaptured_checkpoint, captured_source_digest=self.digest)
        return self._runtime

    def receipt(self):
        self._assert_active()
        return {"schema": MODULE_SCHEMA, "source_digest": self.digest, "namespace": self.name,
                "original_files": len(self.bodies), "operator_files": len(self.operator_bodies),
                "registered_modules": sorted(self._owned), "preparation_bound": self._prepared,
                "native_runtime_loaded": self._runtime is not None,
                "tokenizer_module": self._tokenizer_class.__module__,
                "scientifically_qualified": False}


class CapturedCheckpoint:
    """Authenticate a complete own-output map before pickle/config/Torch parsing.

    Caller owns source lineage and stable filesystem capture. This component
    accepts only immutable bytes, never opens checkpoint paths, and never treats
    supplied hashes as independently issued scientific provenance.
    """
    def __init__(self, bodies, descriptors, *, directory, limits):
        require(type(limits) is dict and set(limits) == set(CHECKPOINT_HARD_LIMITS), "explicit exact checkpoint limits required")
        require(all(type(limits[k]) is int and 0 < limits[k] <= v for k, v in CHECKPOINT_HARD_LIMITS.items()), "invalid checkpoint limits")
        require(type(bodies) is dict and type(descriptors) is dict and set(bodies) == set(descriptors), "checkpoint map/descriptor mismatch")
        require(_REQUIRED <= set(bodies) and 3 <= len(bodies) <= limits["max_files"], "complete current checkpoint trio required")
        require(all(name in _REQUIRED or name == "tconf.yaml" or _EPOCH.fullmatch(name) for name in bodies), "unexpected checkpoint artifact")
        require(type(directory) is str and Path(directory).is_absolute() and ".." not in Path(directory).parts and str(Path(directory)) == directory,
                "canonical absolute owned checkpoint directory required")
        total = 0
        captured = {}
        rows = {}
        for name in sorted(bodies):
            body = bodies[name]
            expected = descriptors[name]
            require(type(body) is bytes and type(expected) is dict and set(expected) == {"bytes", "sha256"}, "immutable checkpoint bytes and exact pins required")
            require(type(expected["bytes"]) is int and 0 <= expected["bytes"] <= limits["max_file_bytes"], "checkpoint member bound")
            require(type(expected["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", expected["sha256"]) and pin(body) == expected,
                    "checkpoint pin mismatch before deserialization")
            total += len(body)
            require(total <= limits["max_total_bytes"], "checkpoint total bound")
            captured[name] = body
            rows[name] = MappingProxyType(dict(expected))
        self.bodies = MappingProxyType(captured)
        self.descriptors = MappingProxyType(rows)
        self.directory = directory
        self.total_bytes = total
        self._events = []
        self._attempted = False
        self._loaded = False
        self._later_attempted = False
        self._base_torch = None

    def _name(self, path):
        require(isinstance(path, (str, Path)), "checkpoint path operand required")
        text = str(path)
        for name in _REQUIRED:
            if text == self.directory + "/" + name:
                return name
        raise Refusal("only the exact current checkpoint trio is consumable")

    def _record(self, operation, name, **details):
        self._events.append({"index": len(self._events), "operation": operation, "artifact": name,
                            **dict(self.descriptors[name]), **details})

    def _open(self, path, mode="r", *args, **kwargs):
        require(not args and not kwargs, "unexpected source checkpoint open arguments")
        name = self._name(path)
        require((name, mode) in (("mconf.yaml", "r"), ("tokenizer.pkl", "rb")), "unexpected source checkpoint open")
        self._record("source_open", name, mode=mode)
        return io.StringIO(self.bodies[name].decode("utf-8")) if mode == "r" else io.BytesIO(self.bodies[name])

    def _torch_proxy(self, base_torch, *, first):
        owner = self

        class CapturedTorch:
            def __getattr__(self, name):
                return getattr(base_torch, name)

            def load(self, path, *args, **kwargs):
                name = owner._name(path)
                require(name == "model.pt" and not args, "only current model checkpoint load admitted")
                if first:
                    require(not kwargs and owner._attempted and not owner._loaded, "original first load has no map_location")
                else:
                    require(owner._loaded and not owner._later_attempted and set(kwargs) == {"map_location"} and str(kwargs["map_location"]) == "cpu",
                            "later historical reload must retain explicit CPU map_location")
                    owner._later_attempted = True
                owner._record("torch_load", name, phase="original_loader" if first else "later_cpu_reload",
                              keyword_names=sorted(kwargs), map_location=None if first else str(kwargs["map_location"]))
                return base_torch.load(io.BytesIO(owner.bodies[name]), **kwargs)
        return CapturedTorch()

    def load_original(self, captured, runtime):
        """Exact original load_model_and_tokenizer body; native leaves are fixed upstream."""
        captured._assert_active()
        require(runtime is captured._runtime and not self._attempted, "one original load from the fixed captured runtime required")
        self._attempted = True
        self._base_torch = runtime.torch
        config_namespace = {"open": self._open, "yaml": runtime.yaml, "dict_to_object": runtime.dict_to_object}
        load_config = _exec_definition(captured.bodies["neuroformer/utils.py"], "neuroformer/utils.py", "load_config", config_namespace)
        class BoundPickle:
            @staticmethod
            def load(stream):
                value = pickle.load(stream)
                require(type(value) is captured._tokenizer_class,
                        "checkpoint must restore the exact registered source Tokenizer before model construction")
                return value
        namespace = {"load_config": load_config, "pickle": BoundPickle, "Neuroformer": runtime.Neuroformer,
                     "torch": self._torch_proxy(runtime.torch, first=True), "open": self._open}
        loader = _exec_definition(captured.bodies["neuroformer/model_neuroformer.py"],
                                  "neuroformer/model_neuroformer.py", "load_model_and_tokenizer", namespace)
        value = loader(self.directory)
        require(type(value) is tuple and len(value) == 3 and type(value[1]) is captured._tokenizer_class,
                "loader did not restore exact registered source Tokenizer")
        self._loaded = True
        return value

    def torch_for_runtime(self, base_torch):
        require(self._loaded and base_torch is self._base_torch, "same native Torch binding after original load required")
        return self._torch_proxy(base_torch, first=False)

    def receipt(self):
        return {"schema": "neuroformer-captured-own-checkpoint-v1", "directory": self.directory,
                "artifacts": [{"path": name, **dict(self.descriptors[name]),
                    "role": "current_trio" if name in _REQUIRED else "distinct_unconsumed_variant"} for name in sorted(self.bodies)],
                "total_bytes": self.total_bytes, "original_loader_attempted": self._attempted,
                "original_loader_completed": self._loaded, "later_cpu_reload_attempted": self._later_attempted,
                "events": [dict(e) for e in self._events],
                "filesystem_reopened": False, "scientifically_qualified": False}
