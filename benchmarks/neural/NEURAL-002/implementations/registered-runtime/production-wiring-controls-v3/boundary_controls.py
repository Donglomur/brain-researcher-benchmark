"""Actual V3 refusal/import-order/read-reservation paths; invented metadata only."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import types

from control_support import require, patched, refuses


def run(sources, meter, root, log):
    root = Path(root)
    # Exact file captures and byte/hash/canonical buffers, including failures.
    meter.charge(read=4 * 410043, write=4 * 410043 + 65536,
                 label="two actual entry refusal captures, two-copy buffers and bounded stderr")
    path, body = sources.entry
    entry = types.ModuleType("morse_control_entry")
    entry.__file__ = path
    meter.charge(read=len(body), write=len(body), label="direct captured production entry compile")
    exec(compile(body, path, "exec"), entry.__dict__)
    base = [path, "inspect", "--legacy-root", str(sources.legacy), "--manifest-bytes", "6283",
            "--manifest-sha256", "987410573a680c23a6e21157b96bc829c1480a5da8c0d8eb7620eee895e16daa",
            "--read-bytes", "410042", "--write-bytes", "65536", "--seconds", "10"]
    with patched(sys, argv=base):
        refuses(entry.main, "prospective source deadline/read grant")
    require(not any(n in sys.modules for n in sources.bodies), "undergrant imported no task module")
    log.passed("entry_prospective_source_cap", cap=410042, exact_success_requirement=410043)

    bad = list(base)
    bad[bad.index("--legacy-root") + 1] = "/" + str(sources.legacy)
    with patched(sys, argv=bad):
        refuses(entry.main, "canonical absolute legacy source root")
    require(not any(n in sys.modules for n in sources.bodies), "alias refusal before task import")
    log.passed("entry_double_slash_refused_before_capture")

    evidence_a, evidence_b = root / "evidence-a", root / "evidence-b"
    evidence_a.mkdir(mode=0o700); evidence_b.mkdir(mode=0o700)
    args = list(base); args[1] = "run"; args[args.index("--read-bytes") + 1] = "410043"
    for name, value in (("evidence-root", evidence_a), ("config-root", evidence_b),
                         ("authorization-path", "MUST_NOT_OPEN.json"), ("config-path", "MUST_NOT_OPEN.json"),
                         ("authorization-sha256", "0" * 64), ("config-sha256", "0" * 64),
                         ("authorization-bytes", 1), ("config-bytes", 1)):
        args += ["--" + name, str(value)]
    meter.charge(read=126902, write=126902,
                 label="nine actual entry pre-admission task compiles before config refusal")
    meta_before = list(sys.meta_path)
    try:
        with patched(sys, argv=args):
            refuses(entry.main, "one canonical ordinary private configuration/evidence root required")
        require("numpy" not in sys.modules and "provider" not in sys.modules,
                "actual entry refusal imported no numerical/data module")
        require(not (evidence_a / "MUST_NOT_OPEN.json").exists(), "no fabricated evidence file")
    finally:
        sys.meta_path[:] = meta_before
        for name in sources.bodies:
            sys.modules.pop(name, None)
    log.passed("actual_entry_configuration_separation", protected_evidence_reads=0,
               note="nonexistent pinned files would fail if reached")

    policy = sources.load("production_policy")
    op = sources.load("production_operation")
    require("numpy" not in sys.modules, "pre-admission operation import remains NumPy-free")
    log.passed("isolated_preadmission_module_closure", numerical_imports=0)
    for label, value in (("double-slash", "/" + str(root)),
                         ("dotdot", str(root) + "/../" + root.name),
                         ("trailing-slash", str(root) + "/")):
        refuses(lambda value=value: policy.ordinary_directory(value), "canonical absolute directory")
        log.passed("ordinary_root_alias_" + label)
    alias = root / "alias"
    alias.symlink_to(evidence_a, target_is_directory=True)
    refuses(lambda: policy.ordinary_directory(str(alias)), "ordinary directory ancestry")
    require(policy.ordinary_directory(str(evidence_a)) == evidence_a, "ordinary positive root")
    refuses(lambda: policy.separated([str(root), str(evidence_a)]), "overlapping custody roots")
    log.passed("symlink_and_nested_custody_refusals")

    # Actual prepare_dependencies refuses preloaded NumPy after real ordinary
    # fixture-directory identity admission. No NumPy package is imported.
    dependency = root / "dependency"; dependency.mkdir(mode=0o700)
    st = dependency.stat()
    native = policy.SelectedNativeAdmission.__new__(policy.SelectedNativeAdmission)
    native.profile = {"host_dependency_paths": [{"path": str(dependency), "device": st.st_dev,
        "inode": st.st_ino, "uid": st.st_uid, "mode": 0o700}], "numpy_version": "invented"}
    native.budget = meter
    fake_sys = types.SimpleNamespace(modules={"numpy": object()}, path=[])
    with patched(policy, sys=fake_sys):
        refuses(native.prepare_dependencies, "native NumPy was imported before selected admission")
    require(not fake_sys.path, "preloaded refusal does not extend dependency path")
    log.passed("actual_dependency_preadmission_refuses_loaded_numpy")

    contract = sources.load("contract")
    meter.charge(read=262144, write=524288,
                 label="64 invented intake rows, four serial cases, exact copies and error records")
    rows = []
    for person in contract.PEOPLE:
        for task in contract.TASKS:
            rows.append({"source_commit": contract.SOURCE_COMMIT, "participant": person, "task": task,
                         "files": {role: {"path": person + "/" + task + "/" + role,
                                          "bytes": size, "sha256": "0" * 64}
                                   for role, size in (("header", 7), ("markers", 11), ("events", 13), ("signal", 17))}})
    manifest = {"schema": "morse-pinned-cohort-v1", "source_commit": contract.SOURCE_COMMIT, "recordings": rows}
    # Independent closed-form maximum:63 successful recordings, then the three
    # twice-read metadata roles before the last signal authentication failure.
    success_record = 2 * ((7 + 1) + (11 + 1) + (13 + 1)) + (17 + 1)
    expected = 63 * success_record + 2 * ((7 + 1) + (11 + 1) + (13 + 1)) + 8 * 2**30 + 1
    window = 62 * 301 * 4
    require(expected > 64 * success_record + 2 * 9984 * window, "chosen first-failure maximum dominates")
    calls, closed = [], []
    first = RuntimeError("invented last-recording authentication failure")
    close_error = OSError("invented independent provider close failure")
    mode = {"failure": False, "bad_ledger": False}

    class Recording:
        def __init__(self, data_root, row):
            self.number = len(calls)
            calls.append((row["participant"], row["task"]))
            if mode["failure"] and self.number == 63:
                raise first
            self.rows, self.certificate = (), {"engineering_inert": True}

        def close(self):
            closed.append(self.number)
            if mode["failure"] and self.number == 0:
                raise close_error

    def prepare(recordings, providers, certificates, nonce, premarker=False):
        require(len(recordings) == len(providers) == len(certificates) == 64, "complete constructor join")
        return ["INERT_PREPARED_WINDOW_LEAF"], [{"id": "inert", "changed": bool(premarker and mode["bad_ledger"])}]

    sources.shim("provider", Recording=Recording)
    sources.shim("packets", prepare=prepare)
    intent = {"intake_manifest": {"path": "invented.json", "bytes": 1, "sha256": "0" * 64},
              "data_root": "/INERT-NOT-OPENED"}
    with patched(op, document=lambda *a: manifest):
        refuses(lambda: op._intake(intent, "inert", 2**20, b"x" * 32,
                                   {"intake_read_bytes": expected - 1}, meter, window),
                "native intake reservation omits")
        require(not calls and not closed, "insufficient bound opens no provider")
        log.passed("intake_under_bound_before_provider", exact_required=expected, providers_opened=0)
        result = op._intake(intent, "inert", 2**20, b"x" * 32,
                            {"intake_read_bytes": expected}, meter, window)
        require(result[3] == expected and len(calls) == len(closed) == 64, "exact bound and all closes")
        log.passed("intake_exact_bound_all64", native_bytes_read=0, providers_are_inert=True)
        calls.clear(); closed.clear(); mode["failure"] = True
        exc = refuses(lambda: op._intake(intent, "inert", 2**20, b"x" * 32,
                                         {"intake_read_bytes": expected}, meter, window))
        require(type(exc) is op.ProductionFailure and exc.first is first
                and exc.secondary == (close_error,) and len(calls) == 64 and closed == list(range(63)),
                "first provider error and independent close errors retained")
        log.passed("intake_last_failure_and_close_error", attempts=64, independent_closes=63)
        calls.clear(); closed.clear(); mode.update(failure=False, bad_ledger=True)
        exc = refuses(lambda: op._intake(intent, "inert", 2**20, b"x" * 32,
                                         {"intake_read_bytes": expected}, meter, window))
        require(type(exc) is op.ProductionFailure and "trial identity differs" in str(exc.first)
                and len(closed) == 64, "paired-window identity mismatch fails after closure")
        log.passed("intake_primary_premarker_identity_refusal")
    return {"scope": "actual source refusal and64-provider orchestration; no signal bytes",
            "substitutions": ["provider.Recording", "packets.prepare", "_intake document reader",
                              "native sys.modules registry for preloaded-NumPy refusal"],
            "expected_first_failure_read_bound": expected}
