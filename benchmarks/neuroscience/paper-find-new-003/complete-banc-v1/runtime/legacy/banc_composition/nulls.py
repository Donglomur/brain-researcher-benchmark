"""Literal observed-matrix binomial summaries, not randomized graph nulls.

Source CNS1160–1259. Independence and p=.5 are source assumptions; these are
neither scientifically validated here nor replaced with rewiring ensembles.
"""
from fractions import Fraction
from dataclasses import dataclass
from math import comb, isfinite
from statistics import median

SOURCE_TESTED_NETWORKS = ("central complex related", "right olfactory", "left olfactory")


@dataclass(frozen=True)
class BinomialSummary:
    pooled_median: float
    named_network_rows: tuple
    combined_zero_probability: Fraction | None
    all_networks_above: tuple[bool, ...]
    exact_greater_probability: Fraction
    native_confidence_interval: None = None
    assumed_entry_independence_qualified: bool = False
    scientific_qualification: bool = False


def source_binomial_summary(matrix, *, column_names, tested_networks, max_trials):
    """Explicit complete matrix; missing values are None/NaN, no sample/cap cut.

    max_trials is a refusal-only resource bound on ALL columns. Matrix and
    named-network ordering are explicit; probabilities remain exact fractions.
    Native binom.test confidence interval and bitwise numerical parity are held.
    """
    def need(ok, message):
        if not ok: raise ValueError(message)
    need(type(matrix) is tuple and type(column_names) is tuple and len(set(column_names)) == len(column_names)
         and all(type(x) is str for x in column_names), "full_ordered_matrix_labels")
    need(type(tested_networks) is tuple and tested_networks == SOURCE_TESTED_NETWORKS,
         "exact_source_named_networks")
    need(type(max_trials) is int and max_trials >= len(column_names) > 0, "complete_binomial_work_bound")
    for row in matrix:
        need(type(row) is tuple and len(row) == len(column_names), "full_matrix_shape")
        for v in row:
            need(v is None or type(v) in (int, float) and (isfinite(v) or v != v), "finite_or_missing_matrix_domain")
    valid = lambda v: v is not None and v == v
    values = [v for row in matrix for v in row if valid(v)]
    need(bool(values), "source_native_all_missing_boundary")
    midpoint = median(values)
    need(isfinite(midpoint), "finite_portable_median_domain")
    columns = tuple(tuple(row[i] for row in matrix if valid(row[i])) for i in range(len(column_names)))
    named = []
    for name in tested_networks:
        if name not in column_names: continue
        column = columns[column_names.index(name)]
        if not column: continue
        n = len(column); above = sum(v > midpoint for v in column)
        need(n <= max_trials, "complete_named_column_trial_bound")
        # Literal .5^N is computed even if above>0; no alternative p-value.
        named.append((name, n, above, Fraction(1, 2**n)))
    combined = None
    if named and all(row[2] == 0 for row in named):
        combined = Fraction(1)
        for row in named: combined *= row[3]
    above = tuple(any(v > midpoint for v in column) for column in columns)
    n = len(columns); k = sum(above)
    greater = Fraction(sum(comb(n, j) for j in range(k, n+1)), 2**n)
    return BinomialSummary(midpoint, tuple(named), combined, above, greater)


def randomized_graph_ensemble(*args, **kwargs):
    raise RuntimeError("no_exact_randomized_graph_producer_located_in_inspected_source_no_substitute")
