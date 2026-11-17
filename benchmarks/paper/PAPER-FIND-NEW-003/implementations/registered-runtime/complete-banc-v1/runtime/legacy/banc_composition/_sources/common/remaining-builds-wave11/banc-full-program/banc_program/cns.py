"""Pure, complete fixed-label CNS adjacency consumers; no loaders or fits.

Source: BANC-project 2e78ce38e946ab80e120a42f504a019b3a567fef,
panels_cns_network_analyses.R:433-615,752-802. Joined annotation values and
their completeness/provenance are caller declarations, not authenticated here.
Fresh community labels must not silently replace the fixed consumer input.
"""
from dataclasses import dataclass
import re

REVISION = "2e78ce38e946ab80e120a42f504a019b3a567fef"
MAX_EXACT_TOTAL = (1 << 53) - 1
BRANCHES = ("unsigned_cns_all", "unsigned_cns_neck", "signed_cns_all",
            "signed_supercluster_neck")


class CNSContractError(ValueError):
    pass


def _require(value, message):
    if not value:
        raise CNSContractError(message)


@dataclass(frozen=True, slots=True)
class FixedAnnotationBinding:
    producer_revision: str
    metadata_sha256: str
    edge_sha256: str
    materialization: int
    synapse_source: str
    label_provenance: str
    endpoint_join_policy: str


@dataclass(frozen=True, slots=True)
class AnnotatedEdge:
    pre: str
    post: str
    count: int | None
    pre_super_class: str | None
    post_super_class: str | None
    pre_cns_network: str | None
    post_cns_network: str | None
    pre_super_cluster: str | None
    post_super_cluster: str | None
    pre_neurotransmitter: str | None


@dataclass(frozen=True, slots=True)
class EdgeDecision:
    row_index: int
    reason: str


@dataclass(frozen=True, slots=True)
class CollapsedRow:
    pre: str
    count: int
    home: str
    away: str
    transmitter: str | None


@dataclass(frozen=True, slots=True)
class Cell:
    away: str
    home: str
    value: int | float


@dataclass(frozen=True, slots=True)
class CNSResult:
    branch: str
    declared_binding: FixedAnnotationBinding
    input_rows: int
    decisions: tuple[EdgeDecision, ...]
    collapsed_rows: tuple[CollapsedRow, ...]
    source_label_order: tuple[str, ...]
    axes: tuple[str, ...]
    cells: tuple[Cell, ...]
    matrix: tuple[tuple[int | float | None, ...], ...]
    partners: bool
    diagonal: bool
    swing: bool
    axes_semantics: str = "destination_rows_source_columns"
    native_order_or_numeric_parity_qualified: bool = False
    scientific_qualification: bool = False


def _text(value, *, nullable=True):
    _require(value is None and nullable or type(value) is str,
             "plain_string_or_missing_annotation_required")


def _add(total, count):
    result = total + count
    _require(result <= MAX_EXACT_TOTAL, "integer_total_exceeds_declared_exact_domain")
    return result


def _inputs(edges, binding, branch, source_label_order):
    _require(type(edges) is tuple and type(binding) is FixedAnnotationBinding,
             "complete_immutable_joined_edges_and_binding_required")
    _require(binding.producer_revision == REVISION
             and type(binding.materialization) is int and binding.materialization == 888
             and binding.synapse_source == "v2"
             and binding.label_provenance == "declared_canonical_enriched_metadata"
             and binding.endpoint_join_policy == "source_first_id_after_proofread_filter",
             "explicit_fixed_annotation_consumer_binding")
    for digest in (binding.metadata_sha256, binding.edge_sha256):
        _require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest),
                 "declared_source_sha256_required")
    _require(branch in BRANCHES, "explicit_supported_source_branch")
    _require(type(source_label_order) is tuple and all(type(x) is str for x in source_label_order)
             and len(set(source_label_order)) == len(source_label_order),
             "explicit_duplicate_free_source_label_order")
    for row in edges:
        _require(type(row) is AnnotatedEdge, "annotated_edge_type")
        _text(row.pre, nullable=False); _text(row.post, nullable=False)
        for value in (row.pre_super_class, row.post_super_class, row.pre_cns_network,
                      row.post_cns_network, row.pre_super_cluster, row.post_super_cluster,
                      row.pre_neurotransmitter):
            _text(value)
        _require(row.count is None or type(row.count) is int
                 and 0 <= row.count <= MAX_EXACT_TOTAL, "nonnegative_exact_integer_count_or_missing")


def _prepare(edges, branch):
    signed = branch.startswith("signed")
    supercluster = branch == "signed_supercluster_neck"
    threshold = 3 if signed else 5
    kept, decisions, totals = [], [], {}
    for index, row in enumerate(edges):
        home = row.pre_super_cluster if supercluster else row.pre_cns_network
        away = row.post_super_cluster if supercluster else row.post_cns_network
        if branch == "unsigned_cns_neck" and row.pre_super_class not in ("ascending", "descending"):
            reason = "presynaptic_not_AN_DN"
        elif home is None or away is None:
            reason = "missing_fixed_label"
        elif row.count is None or row.count < threshold:
            reason = "below_individual_threshold_or_missing_count"
        elif supercluster and (row.pre_super_class not in ("ascending", "descending")
                               or row.post_super_class not in ("ascending", "descending")):
            reason = "both_endpoints_not_AN_DN"
        else:
            reason = "retained_before_source_distinct"
            nt = row.pre_neurotransmitter if signed else None
            key = (row.pre, nt, away) if signed else (row.pre, away)
            totals[key] = _add(totals.get(key, 0), row.count)
            kept.append((row.pre, home, away, nt, key))
        decisions.append(EdgeDecision(index, reason))
    # Source mutates each qualifying row with its group sum, then distincts
    # precisely these fields. Home/annotation multiplicity is not deduplicated
    # earlier or silently treated as a unique-neuron data-quality repair.
    seen, collapsed = set(), []
    for pre, home, away, nt, key in kept:
        row = CollapsedRow(pre, totals[key], home, away, nt)
        if row not in seen:
            seen.add(row); collapsed.append(row)
    return tuple(decisions), tuple(collapsed)


def compute_cns(edges: tuple[AnnotatedEdge, ...], binding: FixedAnnotationBinding, *,
                branch: str, source_label_order: tuple[str, ...], partners: bool = True,
                diagonal: bool = False, swing: bool = False) -> CNSResult:
    """Apply a complete literal fixed-label branch to all supplied joined rows.

    A source order is mandatory: Python lexical order is not substituted for
    native R/dplyr grouping/collation. It must cover every represented label;
    unused entries are allowed. Matrix axes follow away-order then source
    column first appearance, as source grouping/pivot/union do. Plot-specific
    cns.network.order filtering and Ward.D2 sorting are not performed here.

    Counts and every aggregate fit 2**53-1. Swing uses Python binary64 division
    then multiplication by100; native R bit/locale parity remains unqualified.
    Missing diagonal is None, distinct from structural-zero cells. Empty
    collapsed support and weighted swing with a missing global sign column
    are refused, not replaced with a fabricated empty/zero result.
    """
    _inputs(edges, binding, branch, source_label_order)
    _require(type(partners) is bool and type(diagonal) is bool and type(swing) is bool,
             "literal_boolean_options")
    signed = branch.startswith("signed")
    _require(not swing or signed, "swing_requires_signed_source_branch")
    decisions, collapsed = _prepare(edges, branch)
    _require(bool(collapsed), "empty_source_pivot_domain_unqualified")
    ordinal = {label: i for i, label in enumerate(source_label_order)}
    _require(all(row.home in ordinal and row.away in ordinal for row in collapsed),
             "source_order_covers_complete_represented_labels")
    sums, pos, neg, global_signs = {}, {}, {}, set()
    for row in collapsed:
        key = (row.away, row.home)
        amount = 1 if partners else row.count
        sign = (1 if row.transmitter == "acetylcholine" else
                -1 if row.transmitter in ("gaba", "glutamate") else 0)
        if signed and swing:
            if not sign:
                continue
            global_signs.add(sign)
            target = pos if sign == 1 else neg
            target[key] = _add(target.get(key, 0), amount)
        elif signed:
            # Unknown/missing NT contributes zero but retains this pair/axis.
            totals = pos if sign >= 0 else neg
            totals[key] = _add(totals.get(key, 0), amount if sign else 0)
        else:
            sums[key] = _add(sums.get(key, 0), amount)
    if signed and swing:
        _require(bool(global_signs), "empty_recognized_signed_pivot_domain_unqualified")
        if not partners:
            _require(global_signs == {-1, 1}, "weighted_swing_requires_both_global_native_pivot_sign_columns")
        homes = {}
        for key in pos.keys() | neg.keys():
            homes[key[1]] = _add(homes.get(key[1], 0), _add(pos.get(key, 0), neg.get(key, 0)))
        for key in pos.keys() | neg.keys():
            sums[key] = ((pos.get(key, 0) - neg.get(key, 0)) / homes[key[1]]) * 100
    elif signed:
        sums = {key: pos.get(key, 0) - neg.get(key, 0) for key in pos.keys() | neg.keys()}
    ordered = tuple(sorted(sums, key=lambda key: (ordinal[key[0]], ordinal[key[1]])))
    away_order = tuple(dict.fromkeys(key[0] for key in ordered))
    home_order = tuple(dict.fromkeys(key[1] for key in ordered))
    axes = away_order + tuple(name for name in home_order if name not in away_order)
    matrix = tuple(tuple(None if not diagonal and away == home else sums.get((away, home), 0)
                         for home in axes) for away in axes)
    cells = tuple(Cell(away, home, sums[(away, home)]) for away, home in ordered)
    return CNSResult(branch, binding, len(edges), decisions, collapsed, source_label_order,
                     axes, cells, matrix, partners, diagonal, swing)
