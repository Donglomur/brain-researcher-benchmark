"""Concrete full-study launch and target-last assessment for the corrected profile.

These are trusted operator APIs. Call through an authenticated source loader and
an independently qualified enclosing host. No native/scientific qualification
is inferred from a file, boolean, successful import, or diagnostic comparison.
"""
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import stat

from .core import Custody, Refusal, read_exact
from .complete_capture import capture_metadata, decode_full, literal_group_differences
from .artifacts import numerical_agreement
from find032_runtime.outer import OuterOutcome, execute
from find032_runtime.staging import strict, validate_config, path, need


@dataclass(eq=False)
class PairedExecution:
    original: OuterOutcome
    config: dict
    config_capture: object
    receipt: dict
    receipt_capture: object
    custody: Custody
    captures: dict = field(default_factory=dict)
    decoded: dict = field(default_factory=dict)
    reference_opened: bool = False
    assessment_attempted: bool = False

    def require_closed(self):
        need(type(self.original) is OuterOutcome and type(self.custody) is Custody,
             "original concrete paired owner")
        self.custody.raise_first()
        self.original.require_closed()
        need(self.receipt.get("status") == "both_complete_captures_pending_original_parent_exit" and
             set(self.receipt.get("arms", {})) == {"A", "B"}, "both actual full-study captures")
        return self


class ParticipantFailure(RuntimeError):
    def __init__(self, custody, original=None, execution=None):
        self.custody, self.original, self.execution = custody, original, execution
        self.first = custody.first
        super().__init__("FIND032 participant path failed; original first failure and owners retained")


def _root(value, custody):
    selected = path(value)
    fd = os.open(selected, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        need(stat.S_ISDIR(os.fstat(fd).st_mode), "ordinary trusted root")
    except BaseException:
        custody.close("failed trusted root", lambda: os.close(fd))
        raise
    return fd


def _selected_absolute(value, expected, budget, custody):
    p = path(value)
    need(type(expected) is dict and set(expected) == {"bytes", "sha256", "mode"} and
         type(expected["bytes"]) is int and 0 < expected["bytes"] <= 1048576 and
         type(expected["mode"]) is int and expected["mode"] in (0o400, 0o444, 0o644),
         "closed bounded trusted configuration pin")
    fd = _root(str(p.parent), custody)
    raw = captured = None
    try:
        st = os.stat(p.name, dir_fd=fd, follow_symlinks=False)
        need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and stat.S_IMODE(st.st_mode) == expected["mode"],
             "ordinary selected configuration mode")
        raw, captured = read_exact(fd, p.name, expected["bytes"], expected["sha256"], budget, custody)
    except BaseException as error:
        if custody.first is None:
            custody.catch("trusted configuration capture", error)
    finally:
        custody.close("trusted configuration parent", lambda: os.close(fd))
    custody.raise_first()
    return raw, captured


def _terminal(root_fd, name, cap, budget, custody):
    """Actual post-owner capture; a self-reported terminal pin is never authority."""
    need(type(cap) is int and 0 < cap <= 1048576 and name == "PARTICIPANT_EXECUTION.json",
         "fixed bounded terminal receipt")
    token = budget.reserve("read", cap)
    fd = None
    raw = bytearray()
    primary = None
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root_fd)
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap and
             stat.S_IMODE(before.st_mode) == 0o400, "original terminal ordinary extent/mode")
        while len(raw) < before.st_size:
            budget.checkpoint()
            part = os.read(fd, min(65536, before.st_size - len(raw)))
            need(bool(part), "complete terminal receipt")
            raw.extend(part)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mode", "st_nlink", "st_mtime_ns", "st_ctime_ns")
        need(all(getattr(before, k) == getattr(after, k) for k in fields), "stable actual terminal capture")
        budget.observed(token, len(raw))
    except BaseException as error:
        primary = error
        custody.catch("actual participant terminal capture", error)
    finally:
        if fd is not None:
            custody.close("terminal capture descriptor", lambda: os.close(fd))
    custody.raise_first()
    body = bytes(raw)
    return strict(body), {"name": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def launch(*, budget, custody, python, python_pin, controller_config, config_pin, source_selection,
           host_selection, observation_root, origin, normal_end, cleanup_end, final_end,
           docker, docker_pin, socket):
    """Run the original native owner once; no protected operand enters its child."""
    local = Custody(custody)
    original = completed = None
    fd = None
    try:
        raw, captured = _selected_absolute(controller_config, config_pin, budget, local)
        cfg = validate_config(strict(raw))
        need(cfg["docker"]["binary"] == docker and cfg["docker"]["socket"] == socket,
             "same original normal and recovery Docker operands")
        observation = path(observation_root)
        for key in ("input_root", "source_root", "program_root", "workspace"):
            other = path(cfg[key])
            need(not observation.is_relative_to(other) and not other.is_relative_to(observation),
                 "separate native evidence custody")
        original = execute(python=python, python_pin=python_pin, controller_config=controller_config,
            config_pin=config_pin, source_selection=source_selection, host_selection=host_selection,
            observation_root=observation_root, origin=origin, normal_end=normal_end,
            cleanup_end=cleanup_end, final_end=final_end, docker=docker, docker_pin=docker_pin, socket=socket)
        original.require_closed()
        fd = _root(cfg["workspace"], local)
        receipt, receipt_capture = _terminal(fd, "PARTICIPANT_EXECUTION.json",
                                             cfg["limits"]["receipt_bytes"], budget, local)
        need(type(receipt) is dict and receipt.get("schema") == "FIND032_PARTICIPANT_EXECUTION_V1" and
             receipt.get("profile") == cfg["profile"] and receipt.get("endpoint") == cfg["endpoint"] and
             receipt.get("fixed_seed") == cfg["fixed_seed"] and receipt.get("reference_opened") is False and
             receipt.get("scientific_qualification") is False and receipt.get("native_qualification") is False,
             "original actual source-bound terminal receipt")
        completed = PairedExecution(original, cfg, captured, receipt, receipt_capture, local)
        completed.require_closed()
        for arm in ("A", "B"):
            item = receipt["arms"][arm]
            need(item["view"]["complete_recordings"] == 132 and
                 item["view"]["program"]["sha256"] == cfg["programs"][arm]["sha256"] and
                 item["view"]["program"]["bytes"] == cfg["programs"][arm]["bytes"] and
                 item["outputs"]["capture_root"] == str(Path(cfg["workspace"]) / arm / "captured"),
                 "same full cohort, precommitted programme and original capture root")
    except BaseException as error:
        original = getattr(error, "outcome", original)
        if local.first is None:
            local.catch("actual participant launch", error)
    finally:
        if fd is not None:
            local.close("original participant workspace", lambda: os.close(fd))
    if local.first is not None:
        raise ParticipantFailure(local, original, completed) from local.first.raw
    return completed


def assess_closed(execution, *, reference_root, reference_result_pin, budget, custody,
                  absolute_tolerance, group_absolute_tolerance):
    """Decode both full candidates before the first protected-reference open.

    NumPy/ZIP/scientific host operations require the selected enclosing qualified
    runtime; logical read ceilings do not measure native RSS/CPU. Supplied original
    reference, tolerances and figure scientific validation remain external inputs.
    """
    need(type(execution) is PairedExecution, "same returned original paired execution")
    execution.require_closed()
    need(not execution.assessment_attempted, "single original assessment attempt")
    execution.assessment_attempted = True
    local = Custody(custody)
    cfg, opened = execution.config, []
    result = None
    try:
        need(type(reference_root) is str and reference_root.startswith("/") and
             os.path.normpath(reference_root) == reference_root and "\x00" not in reference_root,
             "exact protected root spelling")
        reference = Path(reference_root)
        for key in ("input_root", "source_root", "program_root", "workspace"):
            other = path(cfg[key])
            need(not reference.is_relative_to(other) and not other.is_relative_to(reference),
                 "protected reference disjoint from every participant/source view")
        for arm in ("A", "B"):
            fd = _root(str(Path(cfg["workspace"]) / arm / "captured"), local)
            opened.append(fd)
            item = execution.receipt["arms"][arm]["outputs"]
            admitted = capture_metadata(fd, item["result_manifest"], budget, local,
                member_bytes=cfg["docker"]["member_bytes"], total_bytes=cfg["docker"]["volume_bytes"],
                file_count=cfg["docker"]["file_count"], fixed_seed=cfg["fixed_seed"])
            need(len(admitted["capture_requests"]) + 35 == item["files"], "complete original capture count")
            execution.decoded[arm] = decode_full(fd, admitted, budget, local,
                member_bytes=cfg["docker"]["member_bytes"], endpoint=cfg["endpoint"])
        execution.require_closed()
        need(set(execution.decoded) == {"A", "B"}, "both full candidate decodes before any reference open")
        # This is deliberately the first operation that opens the protected root.
        execution.reference_opened = True
        ref_fd = _root(str(reference), local)
        opened.append(ref_fd)
        admitted = capture_metadata(ref_fd, reference_result_pin, budget, local,
            member_bytes=cfg["docker"]["member_bytes"], total_bytes=cfg["docker"]["volume_bytes"],
            file_count=cfg["docker"]["file_count"], fixed_seed=cfg["fixed_seed"])
        reference_decoded = decode_full(ref_fd, admitted, budget, local,
            member_bytes=cfg["docker"]["member_bytes"], endpoint=cfg["endpoint"])
        execution.decoded["reference"] = reference_decoded
        result = {"schema": "FIND032_FULL_PAIRED_DIAGNOSTICS_V1", "profile": cfg["profile"],
            "endpoint": cfg["endpoint"], "scope": {"recordings_per_arm": 132, "planned_products_per_arm": 990,
                "comparison_dispositions": 52, "BF10_dispositions": 3, "figures": 6},
            "arms": {}, "qualified_reward": None, "scientific_qualification": False,
            "native_qualification": False, "historical_paper_parity": "unavailable separate route"}
        for arm in ("A", "B"):
            candidate = execution.decoded[arm]
            import numpy as np
            need(all(np.array_equal(a, b) for a, b in zip(candidate["axes"], reference_decoded["axes"])),
                 "same exact candidate and protected reference time axes")
            result["arms"][arm] = {
                "original_product_diagnostic": numerical_agreement(candidate["products"], reference_decoded["products"],
                    absolute_tolerance=absolute_tolerance, endpoint=cfg["endpoint"]),
                "all_group_arrays_and_figure_identity": literal_group_differences(candidate, reference_decoded,
                    absolute_tolerance=group_absolute_tolerance)}
    except BaseException as error:
        if local.first is None:
            local.catch("original target-last full assessment", error)
    finally:
        for fd in reversed(opened):
            local.close("full assessment original root", lambda fd=fd: os.close(fd))
    if local.first is not None:
        raise ParticipantFailure(local, execution.original, execution) from local.first.raw
    return result


def execute_and_assess(*, launch_selection, assessment_selection, launch_budget, assessment_budget, custody):
    """Actual complete caller, retaining the concrete original owner throughout."""
    execution = launch(budget=launch_budget, custody=custody, **launch_selection)
    diagnostic = assess_closed(execution, budget=assessment_budget, custody=custody, **assessment_selection)
    return execution, diagnostic
