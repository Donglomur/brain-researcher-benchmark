"""Local custody for the three original EXP003 inputs; never launches a producer or R.

This owner-only preparation reuses the pinned existing custody reader/writer.
No network, workbook parser, R import, estimator or runtime admission is implemented.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat

TASK = "PAPER-EXP-20261113-003"
REVISION = "90e8f324f78701bc3b1a8af3b79685ca91084d05"
CUSTODY_RELATIVE = "trusted-owner/engine/runtime/custody.py"
CONSUMERS = {
    "trusted-owner/engine/runtime/custody.py": {
        "bytes": 2321,
        "sha256": "03f29157b2fdee1ee0d2ff02ac32f32c2620cef1b4bb9cc7b52a3b72d70a44b9"
    },
    "nider-primary-producer-v2/replay_primary_dl.py": {
        "bytes": 11933,
        "sha256": "d66ca0a2e177ad0843aaca7fbc7e1a766d158f6f40c7393ccbc4153b6a1f6d16"
    },
    "nider-primary-companions-v1/replay_companions.py": {
        "bytes": 11624,
        "sha256": "89db9a3c1bcb82c5b05dc3b79059ecb5bd098f0f66c35bfeeb1d4242c236726a"
    },
    "nider-primary-companions-v1/companion_contract.py": {
        "bytes": 16563,
        "sha256": "57e738ebd79ecd07620a20dccccf7873c5cbf57aace29342cd842592099977a8"
    },
    "nider-primary-producer-v2/collector.R": {
        "bytes": 7756,
        "sha256": "8eb78f3eedfecb91dff89cedbea1d7db1df665b5065fa115787ae8d3d4599b58"
    },
    "nider-primary-producer-v2/source_selection.R": {
        "bytes": 1173,
        "sha256": "21de9624646177b1974957a4609a2b3ee606fa2159d4b5dbef244e26e449adac"
    },
    "nider-full120-reconstruction-profile-v1/participant/FIELD_SCHEMA.json": {
        "bytes": 11108,
        "sha256": "b6e220d597f2848c83f78c25cd981980888856431701441f426c329e555b9e22"
    },
    "nider-full120-reconstruction-profile-v1/participant/OUTPUT_INTERFACE.json": {
        "bytes": 2256,
        "sha256": "79b3a6be47c1240ba0f19389da5b03251e86502e91d30b38b1ed25281161f07c"
    },
    "nider-full120-reconstruction-profile-v1/comparator/extended_score.py": {
        "bytes": 11093,
        "sha256": "1c24ec4f2fc5d722541e9231268af21218672ee9453f309110acecffaf5833bf"
    },
    "nider-full120-reconstruction-profile-v1/comparator/reporting_core.py": {
        "bytes": 11862,
        "sha256": "8f87075849eece5320354fb05e5f1fa37eb3f541a0b9d8e924c79f9073e35963"
    },
    "nider-primary-companions-v1/replay_companions.R": {
        "bytes": 7894,
        "sha256": "4100fcd10ef4e9927864251dc4a8e927999a21aa73c9636090cd4daa2fb714fb"
    },
    "nider-primary-companions-v1/native_artifacts.R": {
        "bytes": 16327,
        "sha256": "ee80ec9c7d42bebae3fecd798cd92d55ed3536889a5dd9c7cebe9d261cbf4c5b"
    }
}
ASSETS = {
    "workbook": {"name": "studyInformation_publication.xlsx",
        "repository_path": "data/studyInformation/studyInformation_publication.xlsx",
        "bytes": 63870, "sha256": "ef13337351bac9f9fd10d693a81f768633a87a62c8742ad3279528b7f7667498"},
    "script": {"name": "s3_RmetaAnalysis.R", "repository_path": "scripts/s3_RmetaAnalysis.R",
        "bytes": 18666, "sha256": "caa4ac8a0ee84821c19df5fc26c4a7527ef164c6f48f19e2deed3d0a888cd334"},
    "lock": {"name": "renv.lock", "repository_path": "renv.lock",
        "bytes": 60147, "sha256": "c39c34f524eabcf2b72df5900fee43df504b49652ae956ed9c5d5a93a45c1064"},
}
NATIVE_COMPONENT = {
    "native_verifier.R": {"bytes": 7025,
        "sha256": "870325f0ec76ca51be42efc689d66beb83f7f6245f7451c41b34ef8b78cad1e5"},
    "receipt_bridge.py": {"bytes": 7128,
        "sha256": "ef6a3ac6364fc8c2d46470e6897f1ba1b322075706e0174113bb228acc1560e8"},
}
IDS = ("quest_self", "amy_quest", "amy_self")
PAYLOADS = ("full120.json", "row_lineage.json", "table1/habit_associations.rds",
    "table1/habit_associations.csv", "runtime.json") + tuple(
    "dl/" + x + ".rds" for x in IDS) + (
    "results/figures/forestplot_questSelf_nat.png",
    "results/figures/forestplot_amyQuest_nat.png",
    "results/figures/forestplot_meta_amySelf_nat.png") + tuple(
    "bayes/" + x + suffix for x in IDS for suffix in (".input.rds", ".rds", ".txt", ".json")) + tuple(
    "dl/" + x + ".json" for x in IDS)
NATIVE_INPUTS = ("full120.json", "row_lineage.json") + tuple(
    name for x in IDS for name in ("dl/" + x + ".rds", "dl/" + x + ".json",
        "bayes/" + x + ".input.rds", "bayes/" + x + ".rds", "bayes/" + x + ".json"))
NO_EXECUTION = {"producer_executed": False, "native_verifier_executed": False,
    "runtime_admitted": False, "scientific_agreement_assessed": False, "readiness_promoted": False}
MAX_METADATA = 65536
MAX_EXECUTABLE = 8388608


def need(ok, code):
    if not ok:
        raise ValueError(code)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def identity(raw, path):
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load_custody(implementation_root):
    """The only bootstrap read: authenticate small trusted code before compilation."""
    need(type(implementation_root) is str and "\x00" not in implementation_root,
         "bootstrap_path_string")
    root = Path(implementation_root)
    need(root.is_absolute() and str(root) == implementation_root
         and not implementation_root.startswith("//") and ".." not in root.parts,
         "bootstrap_canonical_path_required")
    path = root / CUSTODY_RELATIVE
    need(not any(item.is_symlink() for item in (path, *path.parents)),
         "bootstrap_symlink_path")
    expected = CONSUMERS[CUSTODY_RELATIVE]
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
             and info.st_size == expected["bytes"], "bootstrap_regular_unique_source")
        raw = stream.read(expected["bytes"] + 1)
    need(len(raw) == expected["bytes"] and hashlib.sha256(raw).hexdigest() == expected["sha256"],
         "custody_source_identity")
    spec = importlib.util.spec_from_loader("_exp003_existing_custody", loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    canonical(module, implementation_root)
    module.read_pin({"path": str(path), **expected}, maximum=expected["bytes"])
    return module


def canonical(custody, value):
    need(type(value) is str and "\x00" not in value, "path_string")
    path = custody.plain(value)
    need(str(path) == value and not value.startswith("//"), "canonical_path_required")
    return path


def private_parent(custody, path):
    parent = canonical(custody, str(path.parent))
    info = parent.stat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
         and info.st_mode & 0o077 == 0, "owner_private_parent_required")


def fresh(custody, value):
    path = canonical(custody, value)
    need(not path.exists() and not path.is_symlink(), "new_path_required")
    private_parent(custody, path)
    return path


def outside_sources(path, *roots):
    need(all(not path.is_relative_to(root) and not root.is_relative_to(path) for root in roots),
         "output_outside_source_trees")


def read_document(custody, path, sha256):
    path = canonical(custody, str(path))
    size = path.lstat().st_size
    need(0 < size <= MAX_METADATA, "metadata_extent")
    raw = custody.read_pin({"path": str(path), "bytes": size, "sha256": sha256},
                          maximum=MAX_METADATA)
    return custody.decode(raw), identity(raw, path)


def consumer_pins(custody, implementation_root):
    root = canonical(custody, str(implementation_root))
    need(root.is_dir(), "implementation_root")
    output = {}
    for relative, expected in CONSUMERS.items():
        path = root / relative
        custody.read_pin({"path": str(path), **expected}, maximum=131072)
        output[relative] = {"path": str(path), **expected}
    return output


def self_pin(custody):
    path = canonical(custody, str(Path(__file__).absolute()))
    size = path.lstat().st_size
    need(0 < size <= 65536, "preparer_source_extent")
    # Reading self is metadata identity, not an execution attestation.
    with path.open("rb") as stream:
        raw = stream.read(65537)
    pin = identity(raw, path)
    custody.read_pin(pin, maximum=65536)
    return pin


def stage(locations, implementation_root, output):
    c = load_custody(implementation_root)
    need(type(locations) is dict and set(locations) == {"schema", "inputs"}
         and locations["schema"] == "nider_original_input_locations_v1"
         and type(locations["inputs"]) is dict and set(locations["inputs"]) == set(ASSETS),
         "exact_three_original_locations")
    root = fresh(c, str(output))
    outside_sources(root, Path(implementation_root), Path(__file__).absolute().parent)
    consumers = consumer_pins(c, implementation_root)
    preparer = self_pin(c)
    sources = {}
    material = {}
    for key, spec in ASSETS.items():
        path = canonical(c, locations["inputs"][key])
        need(not path.is_relative_to(root), "input_inside_new_stage")
        entry = {"path": str(path), "bytes": spec["bytes"], "sha256": spec["sha256"]}
        material[key] = c.read_pin(entry, maximum=spec["bytes"])
        sources[key] = entry
    need(len({row["path"] for row in sources.values()}) == 3, "distinct_original_paths")
    # All source and consumer identities pass before any output is created.
    root.mkdir(mode=0o700)
    try:
        c.write_new(root / "INCOMPLETE.json", encoded({"complete": False}))
        (root / "inputs").mkdir(mode=0o700)
        copied = {}
        for key, spec in ASSETS.items():
            target = root / "inputs" / spec["name"]
            copied[key] = c.write_new(target, material[key])
            target.chmod(0o400)
            c.read_pin(copied[key], maximum=spec["bytes"])
        document = {"schema": "nider_original_input_custody_v1", "task": TASK,
            "original_revision": REVISION, "root": str(root), "implementation_root": str(implementation_root),
            "source_inputs": sources, "staged_inputs": copied, "consumers": consumers,
            "preparer_source": preparer, "original_expected_identities_verified": True,
            "origin_scope": "Local owner-supplied files; no network acquisition observed.",
            "native_authorization": "Custody is not runtime admission or permission to run original fits.",
            "complete": True, **NO_EXECUTION}
        # Completion marker last. Preserve partial private files if publication fails.
        pin = c.write_new(root / "CUSTODY.json", encoded(document))
        # No reusable custody until publication AND final completion transition succeed.
        (root / "INCOMPLETE.json").unlink()
        return {"custody": pin, "original_expected_identities_verified": True, **NO_EXECUTION}
    except BaseException as error:
        failure = {"schema": "nider_original_input_custody_failure_v1",
                   "complete": False, "error_type": type(error).__name__, **NO_EXECUTION}
        try:
            c.write_new(root / "FAILURE.json", encoded(failure))
        except (OSError, ValueError):
            pass
        raise


def recheck_stage(custody, custody_path, custody_sha256, implementation_root):
    record, receipt_pin = read_document(custody, custody_path, custody_sha256)
    root = canonical(custody, str(Path(custody_path).parent))
    need(not any((root / name).exists() or (root / name).is_symlink()
                 for name in ("INCOMPLETE.json", "FAILURE.json")), "incomplete_or_failed_stage")
    need(Path(custody_path).name == "CUSTODY.json" and record.get("schema") == "nider_original_input_custody_v1"
         and record.get("task") == TASK and record.get("original_revision") == REVISION
         and record.get("root") == str(root) and record.get("complete") is True
         and record.get("original_expected_identities_verified") is True
         and record.get("implementation_root") == str(implementation_root), "custody_identity")
    need(all(record.get(key) is False for key in NO_EXECUTION), "custody_cannot_admit_execution")
    current = consumer_pins(custody, implementation_root)
    need(record["consumers"] == current, "consumer_binding_changed")
    current_self = self_pin(custody)
    need(record["preparer_source"]["bytes"] == current_self["bytes"]
         and record["preparer_source"]["sha256"] == current_self["sha256"], "preparer_changed")
    need(set(record["staged_inputs"]) == set(ASSETS) and set(record["source_inputs"]) == set(ASSETS),
         "custody_original_membership")
    for key, spec in ASSETS.items():
        expected = {"path": str(root / "inputs" / spec["name"]),
                    "bytes": spec["bytes"], "sha256": spec["sha256"]}
        need(record["staged_inputs"][key] == expected, "staged_pin_changed")
        need(record["source_inputs"][key]["bytes"] == spec["bytes"]
             and record["source_inputs"][key]["sha256"] == spec["sha256"], "source_pin_changed")
        custody.read_pin(expected, maximum=spec["bytes"])
    return record, receipt_pin


def executable_identity(custody, value):
    custody.read_pin(value, maximum=MAX_EXECUTABLE)
    path = canonical(custody, value["path"])
    need(path.stat().st_mode & 0o111 != 0, "executable_mode_required")
    return value


def limits(request):
    need(request["arm"] in ("A", "B") and type(request["owner_runtime_identity"]) is str
         and 1 <= len(request["owner_runtime_identity"]) <= 256
         and bool(request["owner_runtime_identity"].strip())
         and "\x00" not in request["owner_runtime_identity"], "owner_runtime_identity")
    need(type(request["artifact_byte_limit"]) is int and 1 <= request["artifact_byte_limit"] <= 134217728,
         "artifact_limit_proposal")
    key = "producer_timeout_seconds" if request["operation"] == "producer" else "verification_wall_seconds"
    ceiling = 1800 if request["operation"] == "producer" else 180
    need(type(request[key]) is int and 1 <= request[key] <= ceiling, "time_limit_proposal")
    return {"artifact_byte_limit": request["artifact_byte_limit"], key: request[key],
            "bounds_require_external_owner_admission": True, "hard_resource_enforcement": False}


def expected_view(custody, value):
    root = canonical(custody, value)
    need(root.is_dir(), "existing_payload_view_required")
    expected = set(PAYLOADS)
    folders = {str(parent) for name in expected for parent in Path(name).parents if str(parent) != "."}
    found = set()
    pending = [(root, "")]
    # Fixed small directory grammar; do not traverse unrelated trees.
    while pending:
        directory, relative = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                name = str(Path(relative) / entry.name)
                need(name in expected or name in folders, "exact26_payload_view")
                need(not entry.is_symlink(), "payload_view_symlink")
                if name in folders:
                    need(entry.is_dir(follow_symlinks=False), "payload_view_directory")
                    pending.append((Path(entry.path), name))
                else:
                    need(entry.is_file(follow_symlinks=False), "payload_view_regular_file")
                    found.add(name)
    need(found == expected, "exact26_payload_view")
    return root


def bind(request, implementation_root, output):
    c = load_custody(implementation_root)
    need(type(request) is dict and request.get("schema") == "nider_original_command_binding_request_v1"
         and request.get("operation") in ("producer", "qualification"), "binding_request")
    common = {"schema", "operation", "custody", "python", "rscript", "owner_runtime_identity",
              "arm", "artifact_byte_limit"}
    extra = {"bundle_output", "producer_timeout_seconds"} if request["operation"] == "producer" else {
        "payload_view", "native_component_root", "native_receipt", "verification_wall_seconds"}
    need(set(request) == common | extra, "binding_request_keys")
    need(type(request["custody"]) is dict and set(request["custody"]) == {"path", "bytes", "sha256"},
         "custody_pin_shape")
    c.read_pin(request["custody"], maximum=MAX_METADATA)
    stage_record, receipt = recheck_stage(c, request["custody"]["path"],
                                         request["custody"]["sha256"], implementation_root)
    need(receipt == request["custody"], "custody_extent_changed")
    bound_limits = limits(request)
    runtime = {key: executable_identity(c, request[key]) for key in ("python", "rscript")}
    need(runtime["python"]["path"] != runtime["rscript"]["path"], "distinct_executables_required")
    out = fresh(c, str(output))
    outside_sources(out, Path(implementation_root), Path(__file__).absolute().parent)
    stage_root = Path(stage_record["root"])
    need(not out.is_relative_to(stage_root), "binding_outside_staged_inputs")
    root = Path(implementation_root)
    python = runtime["python"]["path"]
    rscript = runtime["rscript"]["path"]
    payload_limit = str(request["artifact_byte_limit"])
    private_native_sources = None
    if request["operation"] == "producer":
        target = fresh(c, request["bundle_output"])
        outside_sources(target, Path(implementation_root), Path(__file__).absolute().parent)
        need(target != out and not target.is_relative_to(stage_root)
             and not out.is_relative_to(target), "distinct_producer_output")
        argv = [python, "-I", "-B", str(root / "nider-primary-companions-v1/replay_companions.py"),
            "--original-workbook", stage_record["staged_inputs"]["workbook"]["path"],
            "--official-script", stage_record["staged_inputs"]["script"]["path"],
            "--renv-lock", stage_record["staged_inputs"]["lock"]["path"],
            "--rscript", rscript, "--runtime-identity", request["owner_runtime_identity"],
            "--arm", request["arm"], "--output-directory", str(target),
            "--timeout-seconds", str(request["producer_timeout_seconds"]),
            "--artifact-byte-limit", payload_limit]
        commands = [{"role": "new_original57_expression_producer", "argv": argv,
                     "cwd": str(target.parent), "requires_native_fit_authorization": True}]
        preconditions = ["Root must admit original native production and locked runtime separately.",
                         "Output directory must still be absent at dispatch; no automatic retry."]
    else:
        view = expected_view(c, request["payload_view"])
        native_root = canonical(c, request["native_component_root"])
        outside_sources(out, native_root)
        private_native_sources = {}
        for name, expected in NATIVE_COMPONENT.items():
            pin = {"path": str(native_root / name), **expected}
            c.read_pin(pin, maximum=65536)
            private_native_sources[name] = pin
        native_receipt = fresh(c, request["native_receipt"])
        outside_sources(native_receipt, root, native_root, Path(__file__).absolute().parent)
        need(not native_receipt.is_relative_to(view) and not out.is_relative_to(view)
             and native_receipt != out, "qualification_outputs_outside_view")
        need(not native_receipt.is_relative_to(stage_root), "receipt_outside_stage")
        checker = str(root / "nider-primary-companions-v1/companion_contract.py")
        inline = ("import json,runpy,sys; from pathlib import Path; m=runpy.run_path(sys.argv[1]); "
                  "b=m['load_predecessor'](); r=m['check_bundle'](Path(sys.argv[2]),sys.argv[3],"
                  "int(sys.argv[4]),b); print(json.dumps({'artifact_count':len(r[0]),"
                  "'workbook_sha256':r[1]['workbook_sha256'],'arm':r[1]['arm']}))")
        commands = [
            {"role": "existing26_payload_closure", "argv": [python, "-I", "-B", "-c", inline,
                checker, str(view), request["arm"], payload_limit], "cwd": str(out.parent)},
            {"role": "existing17_native_consistency", "argv": [rscript, "--vanilla",
                str(native_root / "native_verifier.R"), str(view),
                str(root / "nider-primary-companions-v1/native_artifacts.R"),
                str(root / "nider-primary-producer-v2/collector.R"), str(native_receipt), payload_limit],
             "cwd": str(out.parent)},
            {"role": "existing_receipt_bridge", "argv": [python, "-I", "-B",
                str(native_root / "receipt_bridge.py"), "--bundle", str(view),
                "--receipt", str(native_receipt), "--artifact-byte-limit", payload_limit],
             "cwd": str(out.parent)}]
        preconditions = [
            "The exact26 file-name view check is metadata only: no scientific payload or provenance was read.",
            "Root must authenticate the original owner bundle/publication and supply external read-only handling.",
            "Hard links share inodes: do not chmod/write view or source; before/after identity checks are not a barrier.",
            "Private accepted native source must be explicitly selected; exact hash is not publication/adoption.",
            "Run closure then native verifier then bridge under one admitted verification envelope; no new fit."]
    result = {"schema": "nider_original_command_binding_v1", "task": TASK,
        "operation": request["operation"], "custody": receipt, "consumers": stage_record["consumers"],
        "preparer_source": self_pin(c), "native_component": private_native_sources,
        "native_component_status": "reviewed_private_requires_root_selection" if private_native_sources else None,
        "executable_file_identities": runtime, "owner_runtime_identity": request["owner_runtime_identity"],
        "runtime_versions_observed": False, "bounds": bound_limits, "commands": commands,
        "preconditions": preconditions,
        "environment": {key: "1" for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "RCPP_PARALLEL_NUM_THREADS")},
        "custody_rechecked_before_binding": True, "execution_selected": False,
        "source_and_command_recheck_required_at_dispatch": True,
        "unresolved": ["R4.3.2 and installed locked packages/runtime admission",
            "Original source/publication equivalence and input rights",
            "BMA fit-to-adjacent-input causality and amy_self questionnaire-n authenticity",
            "Scientific reproduction and same-task improvement"], **NO_EXECUTION}
    pin = c.write_new(out, encoded(result))
    return {"command_binding": pin, "operation": request["operation"],
            "executable_identity_only_not_runtime_admission": True, **NO_EXECUTION}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("stage", "bind"))
    parser.add_argument("--implementation-root", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    c = load_custody(args.implementation_root)
    request, _ = read_document(c, args.request, args.request_sha256)
    function = stage if args.operation == "stage" else bind
    print(json.dumps(function(request, args.implementation_root, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
