"""NEURAL-055 metadata-only plan compiler for the captured installed source.

No source acquisition, candidate import, evidence signing or campaign dispatch.
The caller supplies a trusted, fully captured source context. Only the fixed
metadata modules below are evaluated, in a private import namespace.
"""
import builtins
import hashlib
import json
import math
from pathlib import PurePosixPath
import types

SOURCE_PINS = {
    "n055/common.py": {
        "bytes": 9590,
        "sha256": "8593b6ae72247e72f7dc98015168cd43fd635defc6a004129b078a2cff5ddda9"
    },
    "n055/registry.py": {
        "bytes": 5029,
        "sha256": "eeafc6239e3bdbaa9639f9fba99b0f51601aae2f9d0dce2a0cae89e725f5a3c2"
    },
    "n055/plan.py": {
        "bytes": 3537,
        "sha256": "fe268444290415f47f0c221475ac5ccc15e2cec7fb1d0b7b5ce451acf637d93f"
    },
    "n055/interpretation.py": {
        "bytes": 26819,
        "sha256": "1648bbb6f312056c7de99aca3acbf84f86e3d373e8daa04bd5b68f6ba1c5865a"
    },
    "n055/reporting.py": {
        "bytes": 12899,
        "sha256": "d47c12b6af7f13d416c98cfed88a42274cc09aeb490a808dbc9a5163407ec2af"
    },
    "n055/features.py": {
        "bytes": 19589,
        "sha256": "5e828b2aaa283e98a5dc28f59e89298d0ad4476c25ccccbb2de8b77e15cf2bd6"
    },
    "contracts/ISOLATION_CONTRACT.json": {
        "bytes": 5317,
        "sha256": "4327e061f8f2bde65aaccbb7ca1bfe7832c8c88f23be5cacd57d886f69487d34"
    },
    "contracts/MODE_PERMISSIONS.json": {
        "bytes": 4510,
        "sha256": "43e935217e43926337b740d76ca198116ba2b0864dd80bbd1c6f31aea849dee1"
    },
    "contracts/REPORT_HIERARCHY.json": {
        "bytes": 9765,
        "sha256": "649784fcf8f3a128466ee06704e66ee4648fbd50d6fbbca191c8750a22339ffb"
    },
    "contracts/CONTRASTS.json": {
        "bytes": 7938,
        "sha256": "b5b24650a8288272cd4642bb76bb68ffead79b1c116a5f7c43062874925d2411"
    },
    "contracts/RESOURCE_POLICY_V1.json": {
        "bytes": 5124,
        "sha256": "d87a869636bad14078418685a6e5a2d498c5349c5a0c82f672f7e423cb8b516d"
    },
    "central_entry.py": {
        "bytes": 4431,
        "sha256": "b69df03b5a9ff93329d0ce0df363675c79b8d078929c05f761716c65c34abd96"
    }
}
CAMPAIGN_FIELDS = (
    "system", "submission", "limits", "phase_limits", "native_profile",
    "input_index", "input_qualification", "pre_exposure_review",
    "reference_qualification", "semantic_reviews", "protected_scoring_authority",
    "trust", "protected_panel", "paired_schedule", "interpretation",
    "exposure_declaration", "runtime_environment", "diagnostic_incomplete_scoring",
)
FEATURE_FIELDS = (
    "checkpoint", "image_metadata", "image_index", "image_root", "environment",
    "runtime_qualification", "closure_reserve_seconds", "limits", "trust",
)
DIMENSIONS = {
    "people": 10, "training_images": 16540, "development_concepts": 330,
    "queries": 200, "candidates": 200, "channels": 17, "times": 100,
    "training_repeats": 4, "query_repeats": 80, "image_features": 4096,
}
CONTRACTS = {
    "isolation_contract": "ISOLATION_CONTRACT.json",
    "mode_permissions": "MODE_PERMISSIONS.json",
    "report_hierarchy": "REPORT_HIERARCHY.json",
    "contrasts": "CONTRASTS.json",
}
METADATA_MODULES = frozenset(("common", "registry", "plan", "interpretation",
                              "reporting", "features"))
STDLIB_IMPORTS = frozenset(("hashlib", "json", "math", "os", "stat", "pathlib",
                           "itertools", "time", "io", "platform", "signal"))
PLAN_CAP = 16777216


def _require(ok, reason):
    if not ok:
        raise ValueError(reason)


def _keys(value, names):
    _require(type(value) is dict and set(value) == set(names), "closed " + str(names))


def _plain(value):
    """Reject coercible keys/objects before canonical JSON cloning."""
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        _require(math.isfinite(value), "finite JSON number")
        return
    if type(value) is list:
        for x in value:
            _plain(x)
        return
    if type(value) is dict:
        _require(all(type(k) is str for k in value), "string JSON keys")
        for x in value.values():
            _plain(x)
        return
    raise ValueError("plain JSON operands only")


def encode_plan(plan):
    """Return the exact bytes to write; these are current, not future hashes."""
    _plain(plan)
    raw = json.dumps(plan, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    _require(0 < len(raw) <= PLAN_CAP, "original central-entry plan cap")
    return raw


def _copy(value):
    return json.loads(encode_plan(value))


def _pin(raw):
    _require(type(raw) is bytes, "captured bytes")
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _absolute(value):
    _require(type(value) is str and value and "\\" not in value
             and all(ord(c) >= 32 and ord(c) != 127 for c in value),
             "literal absolute POSIX path")
    p = PurePosixPath(value)
    _require(p.is_absolute() and str(p) == value and not value.startswith("//")
             and ".." not in p.parts, "canonical absolute POSIX path")
    return p


class _Metadata:
    """Exact source loader; no sys.path/sys.modules mutation or runtime import."""
    def __init__(self, context):
        _keys(context, ("source_manifest", "identity", "source_bodies"))
        _require(type(context["source_bodies"]) is dict, "captured source mapping")
        self.bodies = context["source_bodies"]
        self.loaded = {}
        self.source = types.SimpleNamespace(identity=context["identity"])
        common = self.module("common")
        common.descriptor(context["source_manifest"])
        d = context["source_manifest"]
        _require(0 < d["bytes"] <= 1048576
                 and d["role"] == "complete_runtime_manifest",
                 "original complete source manifest descriptor")
        _require(type(context["identity"]) is str
                 and context["identity"] == d["sha256"], "source identity join")
        self.manifest = _copy(d)

    def body(self, path):
        _require(path in SOURCE_PINS and path in self.bodies,
                 "selected captured metadata dependency: " + path)
        raw = self.bodies[path]
        _require(_pin(raw) == SOURCE_PINS[path],
                 "exact installed metadata dependency: " + path)
        return raw

    def module(self, name):
        _require(name in METADATA_MODULES, "closed metadata module")
        if name in self.loaded:
            return self.loaded[name]
        body = self.body("n055/" + name + ".py")
        module = types.ModuleType("_n055_plan_metadata." + name)
        module.__file__ = "<captured:n055/" + name + ".py>"
        module.__package__ = "_n055_plan_metadata"

        def importing(operand, globals=None, locals=None, fromlist=(), level=0):
            if level == 1:
                _require(operand in METADATA_MODULES, "closed relative metadata import")
                return self.module(operand)
            _require(level == 0 and operand in STDLIB_IMPORTS,
                     "stdlib-only metadata import: " + operand)
            return builtins.__import__(operand, globals, locals, fromlist, 0)

        scope = dict(vars(builtins))
        scope["__import__"] = importing
        module.__dict__["__builtins__"] = scope
        self.loaded[name] = module
        try:
            exec(compile(body, module.__file__, "exec"), module.__dict__)
        except BaseException:
            del self.loaded[name]
            raise
        return module


def _limits(value, common):
    for key in ("wall_seconds", "cpu_seconds"):
        common.finite(value[key], True)
    for key in ("read_bytes", "write_bytes", "live_bytes", "files",
                "model_calls", "stream_bytes"):
        common.integer(value[key], 1)


def _descriptor(value, common, maximum=None):
    common.descriptor(value)
    common.integer(value["bytes"], 1, maximum)


def build_campaign_plan(spec, source_context):
    """Compile the complete 960-cell plan, preserving explicit external inputs.

    Neither evidence contents nor candidate programs are opened. Source-derived
    policy identities may be omitted from profile/environment, but conflicting
    explicitly supplied identities are refused. Actual runtime qualification,
    signatures and scientific evidence remain the original operator's inputs.
    """
    _keys(spec, CAMPAIGN_FIELDS)
    value = _copy(spec)
    metadata = _Metadata(source_context)
    common = metadata.module("common")
    registry = metadata.module("registry")
    _limits(value["limits"], common)
    _keys(value["submission"], ("F", "I", "common_policy"))
    for name, descriptor in value["submission"].items():
        _descriptor(descriptor, common, 131072 if name in ("F", "I") else 1048576)
    for name in ("input_index", "input_qualification", "pre_exposure_review",
                 "protected_scoring_authority", "trust"):
        _descriptor(value[name], common)
    _require(type(value["diagnostic_incomplete_scoring"]) is bool,
             "explicit diagnostic boolean")
    system = value["system"]
    _require(type(system) is str and bool(system)
             and system not in ("R0", "R1", "R2", "R3"), "candidate system identity")
    resource_raw = metadata.body("contracts/RESOURCE_POLICY_V1.json")
    resource = {"version": common.parse(resource_raw)["schema"], **_pin(resource_raw)}
    for name in ("native_profile", "runtime_environment"):
        _require(type(value[name]) is dict, "explicit " + name)
        if "resource_policy" in value[name]:
            _require(value[name]["resource_policy"] == resource,
                     "conflicting supplied resource identity")
        value[name]["resource_policy"] = _copy(resource)
    plan = {name: value[name] for name in CAMPAIGN_FIELDS
            if name != "diagnostic_incomplete_scoring"}
    plan.update(schema="neural055-complete-campaign-plan-v2",
                task_id="NEURAL-055", protocol_version=registry.VERSION,
                source_manifest=metadata.manifest, cells=registry.campaign(system),
                dimensions=_copy(DIMENSIONS), resource_policy=resource)
    contracts = {filename: metadata.body("contracts/" + filename)
                 for filename in CONTRACTS.values()}
    for field, filename in CONTRACTS.items():
        plan[field] = _pin(contracts[filename])
    plan["policy"] = {
        "no_other_cell_state": True, "no_query_fit": True,
        "target_access": "after_all960_safe_original_dispositions",
        "diagnostic_incomplete_scoring": value["diagnostic_incomplete_scoring"],
        "physical_and_attributable_costs": "separate_not_summed",
        "broker_contract": "neural055-trusted-host-broker-contract-v4",
        "resource_policy": _copy(resource),
    }
    metadata.module("plan").admit(plan, metadata.source, contracts)
    encode_plan(plan)
    return plan


def build_feature_plan(spec, source_context):
    """Compile actual fixed AlexNet feature plan, without opening payloads.

    The original validate_plan performs image-root symlink metadata checks.
    This function intentionally preserves those checks; it is not a scientific
    producer or a promise that the named checkpoint/images/evidence exist.
    """
    _keys(spec, FEATURE_FIELDS)
    plan = _copy(spec)
    metadata = _Metadata(source_context)
    common = metadata.module("common")
    _limits(plan["limits"], common)
    _descriptor(plan["trust"], common)
    _descriptor(plan["runtime_qualification"], common)
    for name in ("checkpoint", "image_metadata", "image_index"):
        _descriptor(plan[name], common)
    _absolute(plan["image_root"])
    plan.update(schema="neural055-image-feature-preparation-plan-v1",
                task_id="NEURAL-055", source_manifest=metadata.manifest)
    metadata.module("features").validate_plan(plan, metadata.source)
    encode_plan(plan)
    return plan


def central_entry_argv(mode, plan, *, python, source_root, operator_root,
                       output, plan_path):
    """Describe an actual entry invocation; do not read/write a plan or launch.

    The caller must write encode_plan(plan) unchanged at plan_path. The original
    entry reauthenticates the complete source and plan before any run. This is
    command construction, not source authentication or execution authority.
    """
    _require(mode in ("inspect", "prepare", "prepare-features", "run"),
             "original central command")
    expected = ("neural055-image-feature-preparation-plan-v1"
                if mode == "prepare-features" else "neural055-complete-campaign-plan-v2")
    _require(type(plan) is dict and plan.get("schema") == expected
             and plan.get("task_id") == "NEURAL-055", "plan/command schema join")
    paths = {name: _absolute(value) for name, value in (
        ("python", python), ("source_root", source_root),
        ("operator_root", operator_root), ("output", output), ("plan_path", plan_path))}
    descriptor = plan["source_manifest"]
    _keys(descriptor, ("path", "bytes", "sha256", "mode", "role"))
    rel = PurePosixPath(descriptor["path"])
    _require(type(descriptor["path"]) is str and not rel.is_absolute()
             and str(rel) == descriptor["path"] and ".." not in rel.parts
             and str(rel) != "." and "\\" not in str(rel)
             and all(ord(c) >= 32 and ord(c) != 127 for c in str(rel)),
             "manifest within explicit source root")
    _require(type(descriptor["bytes"]) is int and 0 < descriptor["bytes"] <= 1048576
             and type(descriptor["sha256"]) is str and len(descriptor["sha256"]) == 64
             and all(c in "0123456789abcdef" for c in descriptor["sha256"])
             and descriptor["role"] == "complete_runtime_manifest",
             "exact source descriptor arguments")
    entry = paths["source_root"] / "central_entry.py"
    manifest = paths["source_root"] / rel
    _require(paths["plan_path"] not in (entry, manifest), "plan distinct from source entry/manifest")
    _require(paths["output"] not in (paths["source_root"], paths["operator_root"],
                                    paths["plan_path"]), "distinct output operand")
    raw = encode_plan(plan)
    identity = _pin(raw)
    argv = [str(paths["python"]), "-I", "-B", str(entry), mode,
            "--source-root", str(paths["source_root"]), "--source-manifest", str(manifest),
            "--manifest-bytes", str(descriptor["bytes"]), "--manifest-sha256", descriptor["sha256"],
            "--plan", str(paths["plan_path"]), "--plan-bytes", str(identity["bytes"]),
            "--plan-sha256", identity["sha256"], "--operator-root", str(paths["operator_root"]),
            "--output", str(paths["output"])]
    return {"argv": argv, "plan_pin": identity, "plan_path": str(paths["plan_path"])}
