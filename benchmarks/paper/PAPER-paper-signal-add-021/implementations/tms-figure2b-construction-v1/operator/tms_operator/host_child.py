"""Fixed trusted Figure2B host child; source construction, never standalone authority.

The parent authenticates this package before invoking it in its owned Linux child.
Only stdlib and the parent's already selected project bootstrap are imported before
host_sources.admit. Harbor and agent/environment implementations are deferred.
Natural exit of this child and absence of every owned host actor are observed by
the outer owner; CHILD_TERMINAL is private evidence, not that observation.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import math
import os
import stat
import sys
import time
from pathlib import Path


def _early_cache_guard():
    """Fixed stdlib-only admission before any selected project import.

    The outer owner has already charged the complete child allocation. This
    finite name/stat observation has a fixed 16KiB read/write envelope charged
    to the child meter immediately when its selected class becomes available.
    No bytecode or other body is read from the cache prefix.
    """
    def need(ok, message):
        if not ok:
            raise RuntimeError(message)
    need(sys.flags.isolated == 1 and sys.flags.dont_write_bytecode == 1
         and sys.dont_write_bytecode is True, "required actual -I -B startup")
    need(sys.argv.count("--cache-prefix") == 1, "one explicit cache-prefix operand")
    position = sys.argv.index("--cache-prefix")
    need(position + 1 < len(sys.argv), "complete cache-prefix operand")
    text = sys.argv[position + 1]
    need(type(text) is str and len(text.encode("utf-8")) <= 4096, "bounded literal cache path")
    path = Path(text)
    need(path.is_absolute() and str(path) == os.path.normpath(text)
         and path.name in ("bytecode-cache-A", "bytecode-cache-B")
         and all(not p.is_symlink() for p in (path, *path.parents)), "fixed no-alias per-arm prefix")
    need(sys.pycache_prefix == text and sys._xoptions == {"pycache_prefix": text},
         "actual interpreter selects only the fixed fresh prefix")
    need(os.geteuid() > 0 and os.getegid() > 0, "unprivileged selected host child")
    parent = path.parent.lstat()
    need(stat.S_ISDIR(parent.st_mode) and parent.st_uid == 0
         and parent.st_gid == os.getegid() and stat.S_IMODE(parent.st_mode) == 0o710,
         "root-owned non-writable selected-group stage")
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and info.st_gid == os.getegid()
         and stat.S_IMODE(info.st_mode) == 0o550, "root-owned readable non-writable cache prefix")
    with os.scandir(path) as entries:
        need(next(entries, None) is None, "fresh empty selected prefix before project imports")
    return {"path": text, "device": info.st_dev, "inode": info.st_ino,
            "uid": info.st_uid, "gid": info.st_gid, "mode": stat.S_IMODE(info.st_mode)}


_EARLY_CACHE = _early_cache_guard()

# The fixed outer owner invokes this authenticated file with -I -B. Establish
# only this installed package's own root before importing project dependencies;
# never accept a caller-selected module path or import arbitrary candidate code.
if __package__ in (None, ""):
    _entry = Path(__file__)
    if not _entry.is_absolute() or str(_entry) != os.path.normpath(str(_entry)):
        raise RuntimeError("absolute ordinary source-owned entry")
    if any(p.is_symlink() for p in (_entry, *_entry.parents)):
        raise RuntimeError("no source-entry aliases")
    _entry_stat = _entry.lstat()
    if (not stat.S_ISREG(_entry_stat.st_mode) or _entry_stat.st_nlink != 1
            or _entry.name != "host_child.py" or _entry.parent.name != "tms_operator"
            or not _entry.parent.is_dir() or not _entry.parent.parent.is_dir()):
        raise RuntimeError("exact installed tms_operator entry layout")
    if "tms_operator" in sys.modules:
        raise RuntimeError("fresh direct-script package namespace")
    sys.path.insert(0, str(_entry.parent.parent))
    __package__ = "tms_operator"

from tms_figure.contract import Budget, keys, pin, read_pinned, require
from . import schema as s


CHILD_KEYS = {
    "schema", "plan", "runtime", "arm", "paths", "capsule",
    "operator_configuration", "task_files", "terminal_policy",
    "accounting_parent", "deadline", "read_bytes", "write_bytes",
    "close_read_bytes", "close_write_bytes", "close_deadline",
    "bytecode_cache",
}
PATH_KEYS = {"operator_root", "view", "task", "private", "work", "output", "logs"}


def _absolute(value):
    require(type(value) is str and value and "\0" not in value,
            "explicit absolute path")
    path = Path(value)
    require(path.is_absolute() and str(path) == os.path.normpath(value),
            "normalized absolute path")
    for parent in (path, *path.parents):
        require(not parent.is_symlink(), "no symbolic path ancestors")
    return path


def _encode(value, budget, cap=None):
    available = budget.write_limit - budget.writes
    cap = available if cap is None else min(available, cap)
    require(cap > 0, "remaining bounded metadata capacity")
    body = s.bounded_json(value, cap)
    budget.charge(write=len(body))
    return body


def _same(left, right, budget):
    return _encode(left, budget) == _encode(right, budget)


def _captured_json(path, cap, budget):
    """Capture a generated private ordinary body; its pin is observation only."""
    path = _absolute(str(path))
    s.integer(cap)
    first = path.lstat()
    require(stat.S_ISREG(first.st_mode) and first.st_nlink == 1
            and 0 < first.st_size <= cap, "bounded ordinary private receipt")
    def identity(st):
        return (st.st_dev, st.st_ino, st.st_mode, st.st_nlink, st.st_size,
                st.st_mtime_ns, st.st_ctime_ns)
    budget.charge(read=first.st_size + 1, write=first.st_size)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        require(identity(first) == identity(opened), "private receipt open identity")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(first.st_size + 1)
        require(identity(opened) == identity(os.fstat(fd)) == identity(path.lstat())
                and len(body) == first.st_size, "unchanged complete private receipt")
    finally:
        os.close(fd)
    value = s.json_body(body)
    require(_encode(value, budget, cap) == body, "canonical private receipt")
    return value, s.body_pin(body)


def _stage_record(root, name, expected, value, budget):
    pin(expected)
    raw = read_pinned(root / name, expected, budget)
    # Retain exact selected bytes: runtime/capsule JSON may be pretty-printed.
    # Authentication is byte-exact; only the subsequent semantic join is canonical.
    budget.charge(read=len(raw), write=len(raw))
    parsed = s.json_body(raw)
    require(_same(parsed, value, budget), "exact staged parsed " + name)


def _task_capture(cfg, budget):
    keys(cfg["task_files"], {"instruction.md", "task.toml"})
    root = _absolute(cfg["paths"]["task"])
    require(root.is_dir(), "staged local task directory")
    # Finite name-only inventory; never recursively walk arbitrary task inputs.
    # The fixed three names and empty environment are parent-staged source.
    budget.charge(read=512, write=512)
    names = set()
    with os.scandir(root) as entries:
        for entry in entries:
            require(entry.name in {"instruction.md", "task.toml", "environment"}
                    and entry.name not in names and len(names) < 3,
                    "exact finite staged task tree")
            names.add(entry.name)
            require(not entry.is_symlink(), "no staged task aliases")
    require(names == {"instruction.md", "task.toml", "environment"},
            "complete exact staged task tree")
    environment = s.directory(root / "environment")
    with os.scandir(environment) as entries:
        require(next(entries, None) is None, "empty staged environment source")
    for name in ("instruction.md", "task.toml"):
        expected = cfg["task_files"][name]
        pin(expected)
        raw = read_pinned(root / name, expected, budget)
        if name == "instruction.md":
            instruction = cfg["capsule"]["instruction"]
            budget.charge(write=4 * len(instruction))
            require(raw == instruction.encode("utf-8"), "exact unmodified instruction body")
    return dict(cfg["task_files"])


def _budget_record(budget):
    return {"read_limit": budget.read_limit, "write_limit": budget.write_limit,
            "reads": budget.reads, "writes": budget.writes,
            "deadline_monotonic": budget.deadline}


def _publish(path, record, budget):
    # Bound complete encoding before allocation; reserve both encoding and disk.
    cap = (budget.write_limit - budget.writes) // 2
    require(cap > 0, "terminal publication reserve")
    body = s.bounded_json(record, cap)
    budget.charge(write=2 * len(body))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(body)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)
    budget.charge()
    return s.body_pin(body)


def _tool_join(receipt, journal, cfg, budget):
    """Join real adapter result bodies to the real bounded transport journal."""
    require(journal["schema"] == "figure_terminal_journal_v1"
            and journal["arm_fatal"] is False
            and journal["container_closed_observed"] is True,
            "nonfatal terminal transport with actual closure")
    rows = [x for x in journal["events"] if x["kind"] == "terminal_completed"]
    require(not any(x["kind"] == "terminal_failed" for x in journal["events"]),
            "no failed terminal transport")
    tools = [(r["number"], j, t) for r in receipt["calls"]
             for j, t in enumerate(r["tools"])]
    require(len(rows) == len(tools) == receipt["terminal_calls"],
            "every actual tool result and transport event")
    root = _absolute(cfg["paths"]["logs"]) / "host-private"
    for sequence, ((number, index, tool), observed) in enumerate(zip(tools, rows), 1):
        expected = tool["result"]
        raw = read_pinned(root / (str(number) + ".tool-" + str(index) + ".json"),
                          expected, budget)
        budget.charge(read=len(raw), write=len(raw))
        value = s.json_body(raw)
        keys(value, {"schema", "sequence", "command_sha256", "return_code",
                     "stdout", "stderr", "stdout_b64", "stderr_b64",
                     "raw_output_bytes", "read_reserved_bytes", "elapsed_seconds"})
        require(value["schema"] == "figure_terminal_completed_v1"
                and value["sequence"] == observed["sequence"] == sequence,
                "one sequential terminal call identity")
        command = tool["arguments"]["command"]
        budget.charge(write=4 * len(command))
        command_sha = hashlib.sha256(command.encode("utf-8")).hexdigest()
        require(value["command_sha256"] == observed["command_sha256"] == command_sha,
                "actual requested container command")
        total_raw = 0
        for stream in ("stdout", "stderr"):
            encoded = value[stream + "_b64"]
            require(type(encoded) is str, "raw stream base64 text")
            budget.charge(read=len(encoded), write=len(encoded))
            decoded = base64.b64decode(encoded, validate=True)
            total_raw += len(decoded)
            require(s.body_pin(decoded) == observed[stream]
                    and value[stream] == decoded.decode("utf-8", "replace"),
                    "actual raw and decoded terminal stream")
        for key in ("return_code", "raw_output_bytes", "read_reserved_bytes"):
            require(type(value[key]) is int and value[key] == observed[key],
                    "actual terminal outcome and transfer joins")
        require(total_raw == value["raw_output_bytes"]
                and total_raw <= tool["arguments"]["max_output_bytes"],
                "complete matched raw-output extent")
        s.positive(value["elapsed_seconds"])
    # A nonzero candidate shell command is recorded; it does not independently
    # invalidate an otherwise completed agent investigation.


def _initial(cfg, expected, budget, args):
    keys(cfg, CHILD_KEYS)
    require(cfg["schema"] == "tms_figure2b_host_child_v1", "fixed child schema")
    require(cfg["arm"] in ("A", "B"), "fixed arm")
    keys(cfg["paths"], PATH_KEYS)
    parent = cfg["accounting_parent"]
    keys(parent, {"path", "bytes", "sha256"})
    _absolute(parent["path"])
    pin({k: parent[k] for k in ("bytes", "sha256")})
    require(cfg["deadline"] == args.deadline
            and cfg["read_bytes"] == args.read_bytes
            and cfg["write_bytes"] == args.write_bytes,
            "exact original CLI resource operands")
    for key in ("close_read_bytes", "close_write_bytes"):
        s.integer(cfg[key])
    s.positive(cfg["close_deadline"])
    require(cfg["close_deadline"] >= cfg["deadline"], "finite cleanup horizon")
    require(s.body_pin(_encode(cfg, budget, expected["bytes"])) == expected,
            "exact canonical child configuration")
    runtime, plan = cfg["runtime"], cfg["plan"]
    keys(cfg["bytecode_cache"], {"path", "device", "inode", "uid", "gid", "mode"})
    budget.charge(read=16384, write=16384)
    require(cfg["bytecode_cache"] == _EARLY_CACHE == _early_cache_guard()
            and cfg["bytecode_cache"]["path"] == str(Path(runtime["stage_root"]) /
                                                       ("bytecode-cache-" + cfg["arm"]))
            and cfg["bytecode_cache"]["gid"] == runtime["host_gid"],
            "same original cache identity bound to selected stage, arm and host group")
    require(cfg["close_read_bytes"] == runtime["child_receipt_read_bytes"]
            and cfg["close_write_bytes"] == runtime["child_receipt_write_bytes"],
            "selected terminal receipt reservations")
    require(_same(cfg["paths"], runtime["arm_paths"][cfg["arm"]], budget),
            "selected arm paths")
    # Reserve once before source admission, construction or execution. No refund;
    # this separate budget can only read/validate/publish closure, never call a model.
    budget.charge(read=cfg["close_read_bytes"], write=cfg["close_write_bytes"])
    now = time.monotonic()
    closure = Budget(cfg["close_read_bytes"], cfg["close_write_bytes"],
                     cfg["close_deadline"] - now)
    closure.deadline = cfg["close_deadline"]
    logs = s.directory(_absolute(cfg["paths"]["logs"]))
    journal = s.directory(logs / "host-private")
    s.directory(logs / "trials")
    require(not (journal / "CHILD_TERMINAL.json").exists(), "fresh terminal receipt")
    return closure, journal


async def run(cfg, expected, budget, closure, journal):
    """One fixed child composition; returns zero only after evidence publication."""
    plan, runtime, arm = cfg["plan"], cfg["runtime"], cfg["arm"]
    record = {
        "schema": "tms_figure2b_child_terminal_v1", "binding": None,
        "configuration": expected, "source_admission": None,
        "bytecode_cache": dict(_EARLY_CACHE),
        "task_files": None, "capture_summary": None, "agent_result": None,
        "container_activation": None, "container_absence": None,
        "terminal_journal": None, "investigation_failure": None, "errors": [], "status": "failed",
        "accounting": None, "host_process_absence_observed": False,
        "private_grading_performed": False, "native_qualification_created": False,
    }
    trial = environment = terminal = None
    phase = "source-admission"
    old_sys_path = list(sys.path)
    configured = False
    try:
        from . import host_sources
        record["source_admission"] = host_sources.admit(plan, runtime, budget)
        # No Harbor module or implementation is imported before actual source admission.
        require(not any(k == "harbor" or k.startswith("harbor.") for k in sys.modules),
                "fresh source-admitted Harbor import namespace")
        harbor_root = s.directory(_absolute(runtime["harbor_root"]))
        sys.path.insert(0, str(harbor_root.parent))
        from harbor.models.trial.config import TrialConfig
        from harbor.trial.hooks import TrialEvent
        from .capture_trial import create_capture_trial, config_bytes, terminal_summary
        from . import terminal as terminal_module
        from . import responses
        terminal = terminal_module
        s.execution_plan(plan)
        s.capsule(cfg["capsule"])
        stage = s.directory(_absolute(runtime["stage_root"]))
        plan_pin = s.body_pin(_encode(plan, budget))
        _stage_record(stage, "EXECUTION_PLAN.json", plan_pin, plan, budget)
        _stage_record(stage, "RUNTIME.json", plan["runtime"], runtime, budget)
        _stage_record(stage, "CAPSULE.json", plan["capsule"], cfg["capsule"], budget)
        binding = {"execution_plan_sha256": plan_pin["sha256"],
                   "arm": arm, "trial_id": plan["trials"][arm]}
        record["binding"] = binding
        policy = cfg["terminal_policy"]
        require(policy["compose_project"] == binding["trial_id"] + "__env"
                and policy["lifecycle_deadline_monotonic"] == cfg["deadline"]
                and policy["cleanup_deadline_monotonic"] == cfg["close_deadline"],
                "owned deterministic project and original two deadlines")
        operator = cfg["operator_configuration"]
        keys(operator, {"path", "bytes", "sha256"})
        agent_configuration = s.load(_absolute(operator["path"]),
            {k: operator[k] for k in ("bytes", "sha256")}, budget,
            cap=operator["bytes"])
        expected_agent = {"schema": "tms_figure2b_agent_configuration_v1",
                          "binding": binding, "capsule": cfg["capsule"],
                          "limits": plan["limits"], "credential": runtime["credential"],
                          "journal": str(journal)}
        require(_same(agent_configuration, expected_agent, budget),
                "exact fixed agent configuration and private journal")
        record["task_files"] = _task_capture(cfg, budget)
        phase = "capture-trial-construction"
        config = TrialConfig(
            task={"path": cfg["paths"]["task"]},
            trial_name=binding["trial_id"], trials_dir=Path(cfg["paths"]["logs"]) / "trials",
            timeout_multiplier=1.0, agent_timeout_multiplier=1.0,
            agent_setup_timeout_multiplier=1.0, environment_build_timeout_multiplier=1.0,
            agent={"name": None, "import_path": "tms_operator.agent:FigureAgent",
                   "model_name": cfg["capsule"]["model"],
                   "override_timeout_sec": plan["limits"]["seconds"],
                   "override_setup_timeout_sec": plan["limits"]["seconds"],
                   "max_timeout_sec": plan["limits"]["seconds"],
                   "kwargs": {"operator_configuration": operator}},
            environment={"type": None, "import_path": "tms_operator.terminal:FigureDockerEnvironment",
                         "force_build": False, "delete": True, "kwargs": {}},
            verifier={"disable": True}, artifacts=[], extra_instruction_paths=[],
        )
        trial = await create_capture_trial(config, task_root=cfg["paths"]["task"],
                                           admitted_config=config_bytes(config))
        require(trial.task.instruction == cfg["capsule"]["instruction"],
                "Harbor instruction transformations forbidden")
        environment = trial.agent_environment
        environment._tms_budget = budget
        environment._tms_receipt_budget = closure  # Already precharged before actor activation.
        terminal.configure_environment_transport(environment, policy, budget)
        configured = True
        activations = []

        async def activate(event):
            require(not activations and event.event is TrialEvent.AGENT_START
                    and event.config is trial.config and event.result is trial.result,
                    "one actual fixed agent-start hook")
            _task_capture(cfg, budget)
            row = await terminal.inspect_container(environment)
            observation = host_sources.admit_container(row, policy)
            # The actual complete row and admitted projection remain private.
            _encode(row, budget, policy["metadata_output_cap"])
            terminal.bind_terminal_environment(environment, row["Id"])
            activations.append({"inspection": row, "admitted_projection": observation})
            record["container_activation"] = activations[0]

        trial.add_hook(TrialEvent.AGENT_START, activate)
        phase = "actual-agent-investigation"
        result = await trial.run()
        if hasattr(environment,"_tms_investigation_failure"):
            raise environment._tms_investigation_failure
        phase = "agent-terminal-admission"
        require(len(activations) == 1, "actual inspected activation occurred")
        record["capture_summary"] = terminal_summary(trial, result)
        require(record["capture_summary"]["trial_name"] == binding["trial_id"],
                "actual returned trial-name identity")
        receipt, receipt_pin = _captured_json(journal / "AGENT_RESULT.json",
                                              cfg["close_read_bytes"], closure)
        responses.admit_result(receipt, cfg["capsule"], plan["limits"], binding,
                               journal, closure)
        require(record["capture_summary"]["agent_result_raw"]["n_input_tokens"]
                == receipt["observed_input_tokens"]
                and record["capture_summary"]["agent_result_raw"]["n_output_tokens"]
                == receipt["observed_output_tokens"], "actual AgentContext usage join")
        record["agent_result"] = {"path": str(journal / "AGENT_RESULT.json"),
                                   "pin": receipt_pin, "receipt": receipt}
        _task_capture(cfg, closure)
    except BaseException as error:
        record["errors"].append({"phase": phase, "type": type(error).__name__})
    finally:
        # Strong original carrier survives Harbor's exception-to-result conversion.
        # This fixed metadata projection makes unavailable durable evidence explicit;
        # it is never interpreted as successful provider/process closure.
        carrier=getattr(environment,"_tms_investigation_failure",None) if environment is not None else None
        if carrier is not None:
            try:
                require(type(carrier) is responses.InvestigationFailure,"fixed investigation failure carrier")
                record["investigation_failure"]=carrier.metadata()
                record["errors"].append({"phase":"original-agent-failure","type":type(carrier.first).__name__})
            except BaseException as projection_error:
                record["errors"].append({"phase":"failure-projection-unavailable","type":type(projection_error).__name__})
        # Independent source-defined stop is attempted even if Harbor swallowed
        # a stop exception. It cannot create a passing host-absence observation.
        if configured:
            try:
                await environment.stop(delete=True)
            except BaseException as error:
                record["errors"].append({"phase": "fixed-container-stop",
                                           "type": type(error).__name__})
                try:
                    await terminal.abort_terminal_container(environment, "child_finally")
                except BaseException as second:
                    record["errors"].append({"phase": "fixed-container-abort",
                                               "type": type(second).__name__})
            try:
                record["container_absence"] = await terminal.observe_container_absence(environment)
            except BaseException as error:
                record["errors"].append({"phase": "independent-container-absence",
                                           "type": type(error).__name__})
            try:
                record["terminal_journal"] = terminal.terminal_journal(environment, closure)
            except BaseException as error:
                record["errors"].append({"phase": "terminal-journal-capture",
                                           "type": type(error).__name__})
        sys.path[:] = old_sys_path
    if not record["errors"]:
        try:
            require(record["container_absence"] is not None
                    and record["terminal_journal"] is not None
                    and record["agent_result"] is not None,
                    "complete actual terminal evidence")
            _tool_join(record["agent_result"]["receipt"], record["terminal_journal"], cfg, closure)
            record["status"] = "completed"
        except BaseException as error:
            record["errors"].append({"phase": "complete-terminal-join", "type": type(error).__name__})
    record["accounting"] = {"actor": _budget_record(budget),
                             "closure_before_publication": _budget_record(closure),
                             "accounting_parent": cfg["accounting_parent"],
                             "includes_all_Harbor_internal_IO": False,
                             "native_log_growth_boundary": "separately admitted tmpfs"}
    try:
        _publish(journal / "CHILD_TERMINAL.json", record, closure)
    except BaseException:
        # Missing/truncated/late terminal metadata is a closed failure for parent.
        return 1
    return 0 if record["status"] == "completed" and not record["errors"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--configuration", required=True)
    parser.add_argument("--bytes", required=True, type=int)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--read-bytes", required=True, type=int)
    parser.add_argument("--write-bytes", required=True, type=int)
    parser.add_argument("--deadline", required=True, type=float)
    parser.add_argument("--cache-prefix", required=True)
    args = parser.parse_args(argv)
    try:
        require(math.isfinite(args.deadline), "finite original deadline")
        # This exact Budget exists before the configuration body is opened.
        budget = Budget(args.read_bytes, args.write_bytes, args.deadline - time.monotonic())
        budget.deadline = args.deadline
        budget.charge(read=16384, write=16384)  # Fixed already parent-reserved early guard envelope.
        require(args.cache_prefix == _EARLY_CACHE["path"], "parsed explicit startup prefix")
        expected = {"bytes": args.bytes, "sha256": args.sha256}
        pin(expected)
        cfg = s.load(_absolute(args.configuration), expected, budget, cap=args.bytes)
        closure, journal = _initial(cfg, expected, budget, args)
        return asyncio.run(run(cfg, expected, budget, closure, journal))
    except BaseException:
        # Pre-configuration failures cannot safely choose an output path. The
        # outer owned process observer retains natural nonzero/missing receipt.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
