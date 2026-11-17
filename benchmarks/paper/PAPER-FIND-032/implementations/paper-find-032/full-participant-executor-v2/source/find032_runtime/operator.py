"""Actual complete paired-programme operator; invoked by captured source entry."""
import os
import sys
import time
from pathlib import Path
from find032.core import Budget, Custody, encode_json
from find032.participant_executor import launch as launch_original, assess_closed
from .staging import strict, path, need

ORIGINALS = []


def run(raw, source_selection, original_endpoint, bootstrap_accounting):
    value = strict(raw)
    need(type(value) is dict and set(value) == {"schema", "launch", "assessment", "budgets",
         "numerical_search_roots", "report_bytes"} and value["schema"] == "FIND032_COMPLETE_OPERATOR_V1",
         "closed explicit whole-study operator request")
    launch, assessment = value["launch"], value["assessment"]
    need(type(launch) is dict and set(launch) == {"python", "python_pin", "controller_config", "config_pin",
         "host_selection", "observation_root", "origin", "normal_end", "cleanup_end", "final_end",
         "docker", "docker_pin", "socket"}, "fixed original native owner request")
    need(type(assessment) is dict and set(assessment) == {"reference_root", "reference_result_pin",
         "absolute_tolerance", "group_absolute_tolerance"}, "explicit genuine reference and supplied diagnostics")
    need(launch["origin"] <= time.monotonic() < launch["normal_end"] < launch["cleanup_end"] <
         launch["final_end"] < original_endpoint, "single original full native and scientific timeline")
    limits = value["budgets"]
    need(type(limits) is dict and set(limits) == {"launch", "assessment"}, "complete explicit caller accounting")
    for row in limits.values():
        need(type(row) is dict and set(row) == {"read_bytes", "write_bytes", "files"} and
             all(type(n) is int and n > 0 for n in row.values()), "positive caller-selected logical limits")
    # -S deliberately suppresses site initialisation. Only explicitly supplied
    # existing runtime search roots are added; no .pth processing or installation.
    # Their actual NumPy/native identities and enclosing CPU/RSS/storage envelope
    # remain externally selected and qualified, not inferred by this admission.
    roots = value["numerical_search_roots"]
    need(type(roots) is list and 1 <= len(roots) <= 8 and len(set(roots)) == len(roots),
         "finite explicit existing scientific runtime roots")
    custody = Custody()
    launch_budget = Budget(**limits["launch"], deadline=original_endpoint, custody=custody)
    assessment_budget = Budget(**limits["assessment"], deadline=original_endpoint, custody=custody)
    cap = value["report_bytes"]
    need(type(cap) is int and 0 < cap <= 4194304, "preselected complete diagnostic report ceiling")
    report_token = assessment_budget.reserve("write", cap)
    original = None
    try:
        original = launch_original(**launch, source_selection=source_selection,
                                   budget=launch_budget, custody=custody)
        ORIGINALS.append(original)
        original.require_closed()
        need(type(assessment["reference_root"]) is str and assessment["reference_root"].startswith("/") and
             os.path.normpath(assessment["reference_root"]) == assessment["reference_root"],
             "exact protected reference root spelling")
        protected = [Path(original.config[key]) for key in ("input_root", "source_root", "program_root", "workspace")]
        protected += [Path(launch["observation_root"]), Path(assessment["reference_root"]),
                      Path(__file__).absolute().parent.parent]
        admitted_roots = []
        for name in roots:
            selected = path(name)
            need(selected.is_dir() and all(not selected.is_relative_to(p) and not p.is_relative_to(selected)
                                          for p in protected),
                 "scientific library roots disjoint from all participant, reference and source custody")
            admitted_roots.append(str(selected))
        sys.path.extend(admitted_roots)
        diagnostic = assess_closed(original, **assessment, budget=assessment_budget, custody=custody)
        result = encode_json({"diagnostic": diagnostic, "bootstrap": bootstrap_accounting,
                              "launch_budget": launch_budget.report(), "assessment_before_report": assessment_budget.report(),
                              "scientific_and_native_qualification": False})
        need(len(result) <= cap, "complete diagnostic report fits originally selected ceiling")
        done = 0
        while done < len(result):
            assessment_budget.checkpoint()
            n = os.write(1, memoryview(result)[done:done + 65536])
            need(0 < n <= min(65536, len(result) - done), "original report stream progress")
            done += n
        assessment_budget.observed(report_token, done)
        assessment_budget.checkpoint()
    except BaseException as error:
        ORIGINALS.append((error, original))
        if custody.first is None:
            custody.catch("complete original operator", error)
        custody.raise_first()
    return 0
