"""Bind a supplied BANC matrix CSV to its saved same-versus-different report.

This is an inactive artifact-consistency component, not a scientific scorer.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re

INSPECTOR_SHA256 = "95855f4fdb513ccef63979fdfb7d2cb759c27df7dae480ee412f991522b40285"
INSPECTOR_BYTES = 7563
PANEL_SHA256 = "76149a9bea40688bdef0d2867c9c63ce22cc11d16a0b06d50c03cc461b4581df"
SOURCE_COMMIT = "2e78ce38e946ab80e120a42f504a019b3a567fef"
METRIC = "influence_log_minmax"
MAX_REPORT_BYTES = 16384
MAX_BINDING_BYTES = 8192
MAX_CSV_BYTES = 262144
SHA = re.compile(r"[0-9a-f]{64}\Z")
DECIMAL = r"-?[0-9]+\.[0-9]{2}"


class WitnessError(ValueError):
    """Supplied artifacts fail the limited consistency contract."""


def _need(condition, message):
    if not condition:
        raise WitnessError(message)


def _fields(value, names, label):
    _need(type(value) is dict and set(value) == set(names), label + " fields differ")


def _descriptor(value, label):
    _fields(value, ("bytes", "sha256"), label)
    _need(type(value["bytes"]) is int and 0 < value["bytes"] <= 2**63 - 1,
          label + " requires a positive integer byte count")
    _need(type(value["sha256"]) is str and SHA.fullmatch(value["sha256"]),
          label + " requires a SHA256")


def _pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def load_inspector(path=None):
    """Load only the accepted dependency bytes, before executing its module."""
    if path is None:
        path = os.environ.get("BANC_INSPECTOR_PATH") or (
            Path(__file__).resolve().parent.parent /
            "sensory-effector-result-inspection-v1" / "inspect_results.py")
    with Path(path).open("rb") as handle:
        body = handle.read(INSPECTOR_BYTES + 1)
    _need(_pin(body) == {"bytes": INSPECTOR_BYTES, "sha256": INSPECTOR_SHA256},
          "accepted inspector dependency pin differs")
    # Execute the checked bytes, avoiding a second file read after the pin check.
    spec = importlib.util.spec_from_loader("banc_accepted_inspector", loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def parse_binding(body):
    _need(type(body) is bytes and 0 < len(body) <= MAX_BINDING_BYTES,
          "binding size/type differs")
    def pairs(items):
        result = {}
        for key, value in items:
            _need(key not in result, "duplicate binding key")
            result[key] = value
        return result
    try:
        return json.loads(body.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              WitnessError("nonfinite JSON constant")))
    except (ValueError, UnicodeError) as exc:
        raise WitnessError("invalid binding JSON: " + str(exc)) from exc


def parse_report(body):
    """Read the retained R script's complete 23-line saved-result structure.

    Summary numbers, legend, effect text and formatted p remain unverified text.
    Requiring their structure is not a check of their scientific truth.
    """
    _need(type(body) is bytes and 0 < len(body) <= MAX_REPORT_BYTES,
          "report size/type differs")
    try:
        text = body.decode("utf-8")
    except UnicodeError as exc:
        raise WitnessError("report must be UTF-8") from exc
    _need("\r" not in text and all(c == "\n" or c.isprintable() for c in text),
          "report contains unsupported control characters")
    lines = text.removesuffix("\n").split("\n")
    _need(len(lines) == 23, "saved report must have exactly 23 lines")
    fixed = {
        0: "Same vs Different Body Part Analysis", 1: "=" * 70,
        3: "Metric: influence_log_minmax | Body parts: 14",
        4: "Test: Wilcoxon rank-sum (one-sided, on-diagonal > off-diagonal)",
        5: "Note: single test, no multiple comparisons correction needed",
        6: "", 7: "Group summaries", 8: "-" * 70, 11: "",
        12: "Test results", 13: "-" * 70, 17: "", 18: "=" * 70,
        19: "FIGURE LEGEND (copy-paste ready)", 20: "=" * 70, 22: "=" * 70,
    }
    for index, expected in fixed.items():
        _need(lines[index] == expected, f"saved report identity/structure at line {index + 1}")
    _need(re.fullmatch(r"Date: [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}", lines[2]),
          "source date field differs")
    summary = rf"median={DECIMAL}, IQR={DECIMAL}, range=\[{DECIMAL}, {DECIMAL}\]"
    _need(re.fullmatch(r"On-diagonal \(same body part\):      n=14, " + summary, lines[9]),
          "same group count/summary structure differs")
    _need(re.fullmatch(r"Off-diagonal \(different body part\): n=182, " + summary, lines[10]),
          "different group count/summary structure differs")
    match = re.fullmatch(r"W = ([0-9]+)\.([05])", lines[14])
    _need(match is not None and len(match[1]) <= 4,
          "W must be a bounded nonnegative half-integer with one decimal")
    twice_w = 2 * int(match[1]) + (match[2] == "5")
    _need(0 <= twice_w <= 2 * 14 * 182, "W outside 14-by-182 rank-statistic support")
    _need(lines[15].startswith("p = ") and 0 < len(lines[15][4:]) <= 80,
          "missing or oversized formatted p report")
    _need(re.fullmatch(r"Rank-biserial r = -?[0-9]+\.[0-9]{3} \((negligible|small|medium|large) effect\)", lines[16]),
          "effect report structure differs")
    _need(lines[21].startswith("A one-sided Wilcoxon rank-sum test ") and len(lines[21]) <= 2048,
          "legend structure differs")
    return {"reported_twice_W": twice_w, "reported_W": twice_w / 2,
            "reported_p_text": lines[15][4:], "date_text": lines[2][6:],
            "unverified_group_summary_text": lines[9:11],
            "unverified_effect_text": lines[16], "unverified_legend_text": lines[21]}


def witness(csv_body, report_body, binding_body, *, inspector_path=None):
    """Check artifact identities, complete source support and serialized-input U.

    U = count(same > different) + count(ties)/2. The retained source explicitly
    identifies its W with U. This check neither computes p nor emulates R's
    rounding, tie warnings, inferential defaults or native floating arithmetic.
    """
    _need(type(csv_body) is bytes and 0 < len(csv_body) <= MAX_CSV_BYTES,
          "CSV size/type differs")
    _need(type(report_body) is bytes and 0 < len(report_body) <= MAX_REPORT_BYTES,
          "report size/type differs")
    binding = parse_binding(binding_body)
    _fields(binding, ("schema", "metric", "source_commit", "source_panel_sha256",
                     "inspector_sha256", "input", "producer_receipt", "csv", "report"),
            "binding")
    _need(binding["schema"] == "banc-figure2e-artifact-binding/v1", "binding schema differs")
    _need(binding["metric"] == METRIC, "Figure2e source metric declaration differs")
    _need(binding["source_commit"] == SOURCE_COMMIT and binding["source_panel_sha256"] == PANEL_SHA256,
          "retained source identity differs")
    _need(binding["inspector_sha256"] == INSPECTOR_SHA256, "inspector declaration differs")
    for name in ("input", "producer_receipt"):
        _descriptor(binding[name], name)
    for name, body, suffix in (("csv", csv_body, "body_part_similarity_data.csv"),
                              ("report", report_body, "same_vs_different_body_part_test.txt")):
        _fields(binding[name], ("name", "bytes", "sha256"), name)
        _descriptor({k: binding[name][k] for k in ("bytes", "sha256")}, name)
        _need(binding[name]["name"] == METRIC + "_" + suffix, name + " output name differs")
        _need({k: binding[name][k] for k in ("bytes", "sha256")} == _pin(body),
              name + " artifact pin differs")
    report = parse_report(report_body)
    inspector = load_inspector(inspector_path)
    try:
        operands = inspector.inspect_csv(csv_body, metric=METRIC)
    except ValueError as exc:
        raise WitnessError("accepted inspector refused operands: " + str(exc)) from exc
    same = operands["same_body_part_values"]
    different = operands["different_body_part_values"]
    twice_u = sum(2 if a > b else int(a == b) for a in same for b in different)
    _need(twice_u == report["reported_twice_W"],
          "reported W differs from serialized-operand pairwise U")
    return {
        "schema": "banc-figure2e-artifact-witness/v1",
        "binding_sha256": hashlib.sha256(binding_body).hexdigest(),
        "binding_declarations": binding,
        "artifact_pins_verified": {"csv": _pin(csv_body), "report": _pin(report_body)},
        "metric": METRIC, "matrix_axes": operands["matrix_axes"],
        "body_parts": operands["body_parts"], "support_counts": operands["support_counts"],
        "same_body_part_values": same, "different_body_part_values": different,
        "biological_specimens": 1, "matrix_entries_are_independent_animals": False,
        "serialized_operand_pairwise_U": twice_u / 2, "W_matches_serialized_operand_U": True,
        "reported_result": report,
        "qualification": "supplied_artifact_consistency_only",
        "producer_and_input_lineage_authenticated": False,
        "p_value_computed_or_verified": False, "R_runtime_parity_verified": False,
        "source_release_equivalence_verified": False, "primary_endpoint_adopted": False,
        "source_pipeline_reproduced": False, "scientific_reproduction": None,
        "scientific_improvement": None, "readiness_promoted": False,
    }


def _read(path, cap):
    with path.open("rb") as handle:
        body = handle.read(cap + 1)
    _need(0 < len(body) <= cap, "empty or oversized input")
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("binding", type=Path)
    args = parser.parse_args()
    try:
        result = witness(_read(args.csv, MAX_CSV_BYTES), _read(args.report, MAX_REPORT_BYTES),
                         _read(args.binding, MAX_BINDING_BYTES))
    except (OSError, WitnessError) as exc:
        parser.exit(2, "BANC result witness refused: " + str(exc) + "\n")
    print(json.dumps(result, sort_keys=True, allow_nan=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
