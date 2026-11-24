"""Replay the released Figure 3 H/I pooled-cell tests, not paper admission.

Source: Figure3_panelGI.ipynb cell 11 in Zenodo 18726362. The source does not
pin SciPy, so runtime-version provenance is reported rather than claiming exact
historical p-value parity. No biological-unit mapping or new comparison is added.
"""
from __future__ import annotations

import math

import scipy
from scipy.stats import mannwhitneyu

from context_response import reconstruct_responses

SOURCE_PAIRS = (("matched", "unmatched"),
                ("matched", "opto_only"),
                ("unmatched", "opto_only"))
# Make the source call's current SciPy defaults explicit, including orientation.
TEST_OPTIONS = {"use_continuity": True, "alternative": "two-sided", "axis": 0,
                "method": "auto", "nan_policy": "propagate", "keepdims": False}


def reconstruct_statistics(experiments, revision):
    """Retain all 140 response rows and replay the three released source tests.

    Arguments are identical to reconstruct_responses; this function reconstructs
    internally so callers cannot silently supply a reduced response roster.
    These are the source's unpaired pooled-cell tests, even though responses
    share cells. They are not substituted with paired tests or animal-level tests.
    Undefined source arithmetic is retained and invalidates every affected pair,
    without dropping rows or reporting a p-value for a smaller population.
    """
    responses = reconstruct_responses(experiments, revision)
    tests = []
    for first, second in SOURCE_PAIRS:
        values = [[row["responses"][name] for row in responses["rows"]]
                  for name in (first, second)]
        undefined = [sum(value is None for value in group) for group in values]
        result = {"first_condition": first, "second_condition": second,
                  "statistic_definition": "Mann-Whitney U for first_condition",
                  "source_row_counts": [len(group) for group in values],
                  "undefined_response_counts": undefined,
                  "statistic": None, "pvalue": None}
        if any(undefined):
            result["status"] = "undefined_source_response"
        else:
            test = mannwhitneyu(values[0], values[1], **TEST_OPTIONS)
            statistic, pvalue = float(test.statistic), float(test.pvalue)
            if not (math.isfinite(statistic) and math.isfinite(pvalue)):
                result["status"] = "nonfinite_test_result"
            else:
                result.update(status="finite", statistic=statistic, pvalue=pvalue)
        tests.append(result)
    return {
        "schema": "sequence-context-statistics/v1",
        "task_id": responses["task_id"],
        "scope": "released_notebook_Figure3_HI_pooled_cell_statistics",
        "response_reconstruction": responses,
        "source_tests": tests,
        "software": {"scipy_version": scipy.__version__,
                     "function": "scipy.stats.mannwhitneyu",
                     "explicit_options": dict(TEST_OPTIONS),
                     "historical_scipy_version_pinned": False,
                     "exact_historical_pvalue_parity_established": False},
        "interpretation": ("Literal source pooled-cell comparisons; unpaired test "
                           "and source pair order retained. No multiple-testing "
                           "correction, new exclusion, animal-level inference or "
                           "same-result improvement criterion is introduced."),
        "nonfinite_policy": ("All rows retained. A pair with any undefined response "
                             "has no statistic or p-value; no deletion or imputation."),
        "biological_independent_units_verified": False,
        "complete_primary_reproduction_established": False,
        "paper_improvement_established": False,
    }
