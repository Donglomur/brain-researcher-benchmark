"""Actual accepted protected consumers; no local dictionary manufactures authority."""
from .common import require


def grade_original_output(store,authority,manifest,job,result_directory,meter):
    # This is the existing full source/access/output/observer/two-bank join. A
    # Programme result cannot stand in for any of these source-owned arguments.
    from k4bench.protected import grade_I
    return grade_I(store,authority,manifest,job,result_directory,meter)


def summarize_improvement(candidate,reference_results,case_ids,gates_by_reference):
    from k4bench.grading import evaluate_fixed_references
    # Exact accepted descriptive finite-suite rule, all four fixed references.
    # The caller must supply outputs from grade_original_output; this function
    # is arithmetic/report composition, not an authenticity/issuer boundary.
    return evaluate_fixed_references(candidate,reference_results,case_ids,gates_by_reference)


def summarize_reproduction(catalog,obligation_reports,profile):
    from k4bench.grading import reproduction
    return reproduction(catalog,obligation_reports,profile)
