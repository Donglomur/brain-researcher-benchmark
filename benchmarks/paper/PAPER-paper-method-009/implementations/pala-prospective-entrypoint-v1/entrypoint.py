"""Bind the corrected Pala volts loader to the existing prospective evaluator.

This is not an original Figure 3 evaluator or an improvement scorer. Source
authentication, unit conversion and analysis retain their separate meanings.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

TASK_ID = "PAPER-paper-method-009"
RECIPE = "prospective-held-trial-natural-cubic-v1"
ENTRYPOINT = "pala-prospective-entrypoint-v1"
SOURCE_MD5 = "dc333d3d03b79460f2ec1d36122206c8"
SOURCE_BYTES = 1310739375
MAX_PLAN_BYTES = 262144
MAX_REPORT_BYTES = 16 * 1024 * 1024
PINS = {
    "implementations/pala-source-adapter-v2/source_adapter.py":
        (6567, "531988a0c9e809a4b092226c014350a5a9a73a8e055050e16a4d52a9ba68f1f9"),
    "implementations/initial-evaluator-v1/evaluator.py":
        (20045, "4d7ec918f40b1607841ccbd0e6da8036b105a9491460983e67f8fe0f06d2cfcb"),
    "implementations/initial-evaluator-v1/third_party/neuron_stat.py":
        (10290, "24d9bff22d4eab46891101faed1e082e6483f326469f395850848b9139cf2a2a"),
    "implementations/initial-evaluator-v1/third_party/__init__.py":
        (66, "ce0c53fdfef05443740b02eb8ee15537ee57ae6ed73a082d244908413f80cb30"),
    "implementations/initial-evaluator-v1/third_party/LICENSE":
        (1066, "6dd08a164db36acb6762968cd2fc7a61e97405341a36da046ca3711dab751760"),
}


class EntryError(ValueError):
    """The selected source route or output cannot be preserved."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EntryError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_):
    raise EntryError("nonfinite JSON number")


def _finite_float(token):
    value = float(token)
    if not math.isfinite(value):
        raise EntryError("JSON number overflows the finite float domain")
    return value


def read_plan(path):
    """Hash the exact parsed bytes; do not reopen a changed plan for its hash."""
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_PLAN_BYTES + 1)
    if len(raw) > MAX_PLAN_BYTES:
        raise EntryError("prospective plan exceeds 256 KiB")
    try:
        plan = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant, parse_float=_finite_float)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise EntryError("plan must be strict UTF-8 JSON") from exc
    if (not isinstance(plan, dict) or plan.get("recipe") != RECIPE or
            not isinstance(plan.get("cells"), dict) or not plan["cells"]):
        raise EntryError("an explicit nonempty prospective cell plan is required")
    # Check every cell now. The historical evaluator checks splits inside its
    # fitting loop, so relying on it can fit an early cell before a later error.
    for cell, split in plan["cells"].items():
        if not isinstance(cell, str) or not cell or not isinstance(split, dict):
            raise EntryError("every cell needs a named split object")
        train = split.get("calibration_trial_ids")
        test = split.get("assessment_trial_ids")
        if any(not isinstance(ids, list) or len(ids) < 2 or
               any(not isinstance(value, str) or not value for value in ids)
               for ids in (train, test)):
            raise EntryError("every split needs at least two named trials per partition")
        if (len(set(train)) != len(train) or len(set(test)) != len(test) or
                set(train) & set(test)):
            raise EntryError("all cell partitions must be duplicate-free and disjoint")
    return plan, hashlib.sha256(raw).hexdigest()


def verify_sources(task_root):
    """Verify the five selected source members before importing either module."""
    root = Path(task_root)
    for relative, (size, sha) in PINS.items():
        try:
            raw = (root / relative).read_bytes()
        except OSError as exc:
            raise EntryError("a selected source member is absent") from exc
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != sha:
            raise EntryError("a selected source member differs from its pin: " + relative)


def _load_components(task_root):
    verify_sources(task_root)
    # The historical evaluator imports this absolute package name. Refuse an
    # already imported unrelated package rather than silently using its code.
    reserved = ("_pala_source_v2", "_pala_prospective_v1")
    if any(name in sys.modules for name in reserved) or any(
            name == "third_party" or name.startswith("third_party.")
            for name in sys.modules):
        raise EntryError("use a fresh interpreter without preloaded component names")
    old_path = list(sys.path)
    sys.path.insert(0, str(Path(task_root) / "implementations/initial-evaluator-v1"))
    loaded = []
    try:
        for name, relative in (
                (reserved[0], "implementations/pala-source-adapter-v2/source_adapter.py"),
                (reserved[1], "implementations/initial-evaluator-v1/evaluator.py")):
            spec = importlib.util.spec_from_file_location(name, Path(task_root) / relative)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            loaded.append(module)
        return tuple(loaded)
    finally:
        sys.path[:] = old_path
        for name in reserved + ("third_party.neuron_stat", "third_party"):
            sys.modules.pop(name, None)


def validate_source_receipt(recording):
    """Check the corrected loader's declared boundary, not biological identity."""
    receipt = recording.receipt
    if not isinstance(receipt, dict):
        raise EntryError("source loader did not return its recording receipt")
    expected = {
        "source_md5": SOURCE_MD5, "source_bytes": SOURCE_BYTES,
        "source_voltage_unit": "V", "output_voltage_unit": "mV",
        "voltage_multiplier": 1000.0, "source_row_order_preserved": True,
        "cohort_selection_applied": False,
    }
    if any(type(receipt.get(k)) is not type(v) or receipt[k] != v
           for k, v in expected.items()):
        raise EntryError("corrected source unit/identity boundary is absent")
    if (not isinstance(receipt.get("source_sha256"), str) or
            not re.fullmatch(r"[0-9a-f]{64}", receipt["source_sha256"]) or
            type(receipt.get("source_rows")) is not int or
            receipt["source_rows"] <= 0 or
            receipt["source_rows"] != len(recording.trials)):
        raise EntryError("source hash or full row receipt is invalid")
    return dict(receipt)


def preflight_all_cells(trials, plan, evaluator):
    """Validate the complete source-aware split before any cell can be fitted.

    The pinned population audit validates/counts source spikes but does not fit.
    The unchanged evaluate function repeats its own audit and checks afterward;
    this added source scan is real work, not a claimed measured runtime bound.
    """
    eligible, _ = evaluator.audit_population(trials)
    if not eligible or set(plan["cells"]) != set(eligible):
        raise EntryError("the plan must include every eligible cell exactly")
    for cell, records in eligible.items():
        split = plan["cells"][cell]
        planned = set(split["calibration_trial_ids"]) | set(split["assessment_trial_ids"])
        if planned != {trial.trial_id for trial in records}:
            raise EntryError("all cell partitions must cover their complete eligible source trials")


def _publish_exclusive(path, raw):
    """Publish a complete report without overwriting a concurrent output."""
    if len(raw) > MAX_REPORT_BYTES:
        raise EntryError("report exceeds the declared 16 MiB serialization bound")
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".pala-report-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)  # Existing files/symlinks fail; no os.replace.
    finally:
        os.unlink(temporary)


def run(mat_path, plan_path, output_path, *, task_root=None):
    """Run unchanged prospective analysis with the corrected authenticated load.

    task_root is only a relocatable source-package locator, never a source-pin
    bypass. Scientific cohort/recipe validation remains in the pinned evaluator.
    """
    output = Path(output_path)
    if os.path.lexists(output) or not output.parent.is_dir():
        raise EntryError("output must be a new file in an existing directory")
    plan, plan_sha = read_plan(plan_path)
    root = Path(task_root) if task_root is not None else Path(__file__).resolve().parents[2]
    adapter, evaluator = _load_components(root)
    # Crucially, evaluator.load_pala is never called: it does not convert volts.
    recording = adapter.load_pala(mat_path)
    receipt = validate_source_receipt(recording)
    preflight_all_cells(recording.trials, plan, evaluator)
    report = evaluator.evaluate(recording.trials, plan)
    if (not isinstance(report, dict) or report.get("task_id") != TASK_ID or
            report.get("recipe") != RECIPE or
            report.get("classification") != "prospective_engineering_bridge" or
            report.get("scientific_qualified") is not False or
            report.get("exact_figure_reproduction") is not False):
        raise EntryError("evaluator did not preserve its explicit prospective scope")
    report = dict(report)
    report["entrypoint"] = ENTRYPOINT
    report["source_receipt"] = receipt
    report["input_receipt"] = {
        "mat_sha256": receipt["source_sha256"], "mat_md5": receipt["source_md5"],
        "plan_sha256": plan_sha,
        "dsrp_sha256": PINS["implementations/initial-evaluator-v1/third_party/neuron_stat.py"][1],
    }
    # No local filesystem paths, substituted published percentage, win flag or
    # changed biological metric is introduced by this orchestration component.
    try:
        raw = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EntryError("evaluator report is not finite JSON; no report published") from exc
    _publish_exclusive(output, raw)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mat", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    run(args.mat, args.plan, args.output)


if __name__ == "__main__":
    main()
