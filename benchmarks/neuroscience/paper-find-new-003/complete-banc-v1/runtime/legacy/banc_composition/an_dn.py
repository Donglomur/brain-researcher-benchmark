"""Pure consumers of declared full BANC rows; never loads or fits a graph.

Literal released R operations are exposed separately from native tie/rounding
qualification. Input declarations are not proof of authentic bytes or joins.
"""
from collections import defaultdict, deque
from dataclasses import dataclass
import math
import re

REVISION = "2e78ce38e946ab80e120a42f504a019b3a567fef"
MAX_EXACT_COUNT = 2**53 - 1  # portable declared domain, NOT an Arrow/R dtype
TRANSMITTERS = ("all", "glutamate", "gaba", "acetylcholine")
AD_CLASSES = ("ascending", "descending")
WEIRD = ("DNxl080", "DNge079", "DNg73", "DNg65")


class SourceDomainError(ValueError):
    """A supplied value lies outside this source component's declared domain."""


def need(ok, message):
    if not ok:
        raise SourceDomainError(message)


@dataclass(frozen=True)
class InputBinding:
    producer_revision: str
    metadata_sha256: str
    edge_sha256: str
    materialization: int
    synapse_source: str
    label_provenance: str
    endpoint_join_policy: str


def validate_binding(b):
    need(type(b) is InputBinding, "exact InputBinding required")
    need(b.producer_revision == REVISION, "released source revision")
    need(type(b.materialization) is int and b.materialization == 888 and
         b.synapse_source == "v2", "declared materialization 888 / synapse v2")
    need(b.label_provenance == "declared_canonical_enriched_metadata" and
         b.endpoint_join_policy == "source_first_id_after_proofread_filter",
         "fixed source annotation/join declaration")
    for value in (b.metadata_sha256, b.edge_sha256):
        need(type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None,
             "declared lowercase SHA256")
    return b


def label(value, nullable=True):
    need((nullable and value is None) or type(value) is str,
         "labels are unchanged strings or explicit missing annotations")


def checked_sum(values):
    value = sum(x for x in values if x is not None)
    need(value <= MAX_EXACT_COUNT, "aggregate exceeds portable exact-count domain")
    return value


@dataclass(frozen=True)
class MetadataRow:
    root_id: str
    super_class: str | None
    cell_type: str | None


@dataclass(frozen=True)
class ANEdge:
    pre: str
    post: str
    count: int | None
    pre_cluster: str | None
    post_cluster: str | None
    pre_cell_type: str | None
    post_cell_type: str | None
    pre_super_class: str | None
    post_super_class: str | None
    pre_super_cluster: str | None
    post_super_cluster: str | None
    pre_neurotransmitter: str | None
    post_region: str | None = None


def validate_edges(edges):
    need(type(edges) is tuple, "complete ordered edge tuple required")
    for e in edges:
        need(type(e) is ANEdge, "exact ANEdge rows required")
        label(e.pre, False); label(e.post, False)
        for name in ANEdge.__dataclass_fields__:
            if name not in ("pre", "post", "count"):
                label(getattr(e, name))
        need(e.count is None or (type(e.count) is int and
             0 <= e.count <= MAX_EXACT_COUNT), "nonnegative portable exact counts or missing")


def eligible_an_dn(metadata, binding):
    """Literal panels_an_dn_connectivity.R 51–56 membership, stable dedup.

    R grepl(pattern, NA) is FALSE; missing cell_type is not silently removed.
    """
    validate_binding(binding)
    need(type(metadata) is tuple, "complete ordered metadata tuple required")
    ids = []; seen = set()
    for m in metadata:
        need(type(m) is MetadataRow, "exact metadata projection")
        label(m.root_id, False); label(m.super_class); label(m.cell_type)
        if (m.super_class in AD_CLASSES and m.cell_type not in WEIRD and
                (m.cell_type is None or re.search(r"^SA|^SN|^AN_4|^AN_5", m.cell_type) is None)):
            if m.root_id not in seen:
                seen.add(m.root_id); ids.append(m.root_id)
    return tuple(ids)


@dataclass(frozen=True)
class DirectRow:
    pre_cluster: str
    post_cluster: str
    count: int
    norm: float | None


@dataclass(frozen=True)
class DirectMatrix:
    transmitter: str
    rows: tuple[DirectRow, ...]
    labels: tuple[str, ...]
    values: tuple[tuple[float, ...], ...]
    represented: tuple[tuple[bool, ...], ...]
    native_pivot_input_nonempty: bool


@dataclass(frozen=True)
class DirectResult:
    binding: InputBinding
    input_rows: int
    eligible_ids: tuple[str, ...]
    panels: tuple[DirectMatrix, ...]
    authentic_qualified: bool = False
    native_qualified: bool = False


def an_dn_direct(edges, metadata, binding):
    """All four R 64–137 matrices; no threshold, sampling or NT resumming.

    Rows are presynaptic clusters, columns postsynaptic clusters. Full-graph
    denominator and pair sums precede BOTH membership and NT row filtering.
    """
    validate_edges(edges)
    eligible = eligible_an_dn(metadata, binding)
    ids = set(eligible)
    totals = defaultdict(list); pairs = defaultdict(list)
    for e in edges:
        totals[e.post_cluster].append(e.count)
        pairs[e.pre_cluster, e.post_cluster].append(e.count)
    totals = {k: checked_sum(v) for k, v in totals.items()}
    pairs = {k: checked_sum(v) for k, v in pairs.items()}
    panel_rows = []
    for nt in TRANSMITTERS:
        rows = []; seen = set()
        for e in edges:
            if (e.pre_cluster is None or e.post_cluster is None or e.pre not in ids or
                    e.post not in ids or (nt != "all" and e.pre_neurotransmitter != nt)):
                continue
            count, total = pairs[e.pre_cluster, e.post_cluster], totals[e.post_cluster]
            row = DirectRow(e.pre_cluster, e.post_cluster, count,
                            count / total if total else None)
            if row not in seen:
                seen.add(row); rows.append(row)
        panel_rows.append(tuple(rows))
    need(bool(panel_rows[0]), "empty native all-cluster pivot is unqualified")
    # base::union preserves first appearance; distinct() preserves row order.
    labels = tuple(dict.fromkeys([r.pre_cluster for r in panel_rows[0]] +
                                [r.post_cluster for r in panel_rows[0]]))
    panels = []
    for nt, rows in zip(TRANSMITTERS, panel_rows):
        by_pair = {(r.pre_cluster, r.post_cluster): r.norm for r in rows}
        matrix = tuple(tuple(by_pair.get((a, b)) or 0.0 for b in labels) for a in labels)
        represented = tuple(tuple((a, b) in by_pair for b in labels) for a in labels)
        # An empty NT input is exposed without claiming its native acast call succeeds.
        panels.append(DirectMatrix(nt, rows, labels, matrix, represented, bool(rows)))
    return DirectResult(binding, len(edges), eligible, tuple(panels))


@dataclass(frozen=True)
class SuperclusterDirectRow:
    seed: str
    target: str
    level: str
    count: int
    norm: float | None


def an_dn_supercluster_direct(edges, metadata, binding):
    """R 298–310 row-preserving supercluster direct intermediate.

    Unlike cluster matrices, the post total uses sum WITHOUT na.rm; any missing
    count poisons that entire denominator. The source does NOT distinct rows.
    """
    validate_edges(edges)
    ids = set(eligible_an_dn(metadata, binding))
    totals = defaultdict(list); pairs = defaultdict(list)
    for e in edges:
        totals[e.post_super_cluster].append(e.count)
        pairs[e.pre_super_cluster, e.post_super_cluster].append(e.count)
    totals = {k: None if None in v else checked_sum(v) for k, v in totals.items()}
    pairs = {k: checked_sum(v) for k, v in pairs.items()}
    rows = []
    for e in edges:
        if (e.pre_super_cluster is not None and e.post_super_cluster is not None and
                e.pre in ids and e.post in ids):
            count = pairs[e.pre_super_cluster, e.post_super_cluster]
            total = totals[e.post_super_cluster]
            rows.append(SuperclusterDirectRow(e.pre_super_cluster, e.post_super_cluster,
                                             "direct", count, count / total if total else None))
    return tuple(rows)


@dataclass(frozen=True)
class ChainEdge:
    pre: str
    post: str
    count: int
    pre_super_class: str
    post_super_class: str
    pre_super_cluster: str
    post_super_cluster: str


@dataclass(frozen=True)
class ChainVertex:
    cell_type: str
    super_class: str
    super_cluster: str


@dataclass(frozen=True)
class ChainGraph:
    binding: InputBinding
    input_rows: int
    cell_type_order: tuple[str, ...]
    edges: tuple[ChainEdge, ...]
    vertices: tuple[ChainVertex, ...]


def ordered_labels(order, represented, description):
    need(type(order) is tuple and all(type(x) is str for x in order) and
         len(order) == len(set(order)) and set(represented) <= set(order), description)


def prepare_chains(edges, binding, *, cell_type_order):
    """R 371–410: pair sum >=10, then first-annotation filters.

    cell_type_order is the caller-declared native dplyr group order. No Python
    locale/tie assumption replaces it; the full input tuple is always visited.
    """
    validate_binding(binding); validate_edges(edges)
    groups = defaultdict(list)
    for e in edges:
        groups[e.pre_cell_type, e.post_cell_type].append(e)
    represented = {v for pair in groups for v in pair if v is not None}
    ordered_labels(cell_type_order, represented, "complete native cell-type group order")
    need(all("->" not in x for x in represented), "native pasted-path delimiter collision domain held")
    rank = {x: i for i, x in enumerate(cell_type_order)}
    rank[None] = len(rank)
    retained = []
    for pair in sorted(groups, key=lambda p: (rank[p[0]], rank[p[1]])):
        rows = groups[pair]; first = rows[0]
        count = checked_sum(e.count for e in rows)
        if (count < 10 or None in pair or pair[0] == pair[1] or
                first.pre_super_cluster is None or first.post_super_cluster is None or
                first.pre_super_class not in AD_CLASSES or first.post_super_class not in AD_CLASSES):
            continue
        retained.append(ChainEdge(pair[0], pair[1], count,
                                  first.pre_super_class, first.post_super_class,
                                  first.pre_super_cluster, first.post_super_cluster))
    vertices = {}
    for side in ("pre", "post"):
        for edge in retained:
            name = getattr(edge, side)
            vertices.setdefault(name, ChainVertex(name, getattr(edge, side + "_super_class"),
                                getattr(edge, side + "_super_cluster") or "unknown"))
    need(bool(retained), "empty native chain graph/path-table domain held")
    return ChainGraph(binding, len(edges), cell_type_order, tuple(retained), tuple(vertices.values()))


@dataclass(frozen=True)
class ChainSummary:
    path_id: int
    nodes: tuple[str, ...]
    path_len: int
    n_clusters: int
    combo: str
    cluster_mix: str


@dataclass(frozen=True)
class ChainResult:
    graph: ChainGraph
    selection: str
    summaries: tuple[ChainSummary, ...]
    three_plus_counts: tuple[tuple[str, str, int, int], ...]
    authentic_qualified: bool = False
    native_tie_qualified: bool = False


def consume_chains(graph, selected_paths, *, cluster_order, selection,
                   max_pair_checks, max_paths):
    """Validate one selected unweighted shortest path for EVERY reachable pair.

    A native igraph adapter or candidate supplies paths. This component neither
    invents a tie rule nor restricts the complete graph to a smaller surrogate.
    """
    need(type(graph) is ChainGraph and type(selected_paths) is tuple, "prepared graph and path tuple")
    validate_binding(graph.binding)
    need(type(max_pair_checks) is int and max_pair_checks >= 0 and
         type(max_paths) is int and max_paths >= 0, "explicit nonnegative work/path capacities")
    need(len(selected_paths) <= max_paths, "selected path capacity exceeded; no truncation")
    need(selection in ("igraph_one_shortest_path_per_reachable_pair",
                       "candidate_one_shortest_path_per_reachable_pair"), "explicit path-selection branch")
    attrs = {v.cell_type: v.super_cluster for v in graph.vertices}
    ordered_labels(cluster_order, attrs.values(), "complete native cluster sort order")
    rank = {x: i for i, x in enumerate(cluster_order)}
    adjacency = {v: set() for v in attrs}
    for e in graph.edges:
        adjacency[e.pre].add(e.post)
    expected = {}; work = 0
    for source in attrs:
        distances = {source: 0}; queue = deque([source])
        while queue:
            cur = queue.popleft()
            for nxt in adjacency[cur]:
                work += 1
                need(work <= max_pair_checks, "all-source BFS work capacity exceeded; no truncation")
                if nxt not in distances:
                    distances[nxt] = distances[cur] + 1; queue.append(nxt)
        for target in attrs:
            work += 1
            need(work <= max_pair_checks, "all-pair validation work capacity exceeded; no truncation")
            if target in distances and distances[target] > 0:
                need(len(expected) < max_paths, "full reachable-pair capacity exceeded; no truncation")
                expected[source, target] = distances[target]
    seen = set(); summaries = []; counts = defaultdict(int)
    for path in selected_paths:
        need(type(path) is tuple and len(path) >= 2 and all(type(x) is str and x in attrs for x in path),
             "full selected path vertex sequence")
        pair = (path[0], path[-1])
        need(pair not in seen and pair in expected and len(path) - 1 == expected[pair] and
             len(set(path)) == len(path) and all(b in adjacency[a] for a, b in zip(path, path[1:])),
             "exactly one simple shortest path per reachable ordered pair")
        seen.add(pair)
        clusters = sorted({attrs[x] for x in path}, key=rank.__getitem__)
        combo = " + ".join(clusters)
        mix = "unitary super cluster" if len(clusters) == 1 else "mixed super cluster"
        summary = ChainSummary(len(summaries) + 1, path, len(path) - 1, len(clusters), combo, mix)
        summaries.append(summary)
        if len(clusters) >= 3:
            counts[mix, combo.replace("_", " "), len(path) - 1] += 1
    need(seen == set(expected), "all reachable ordered pairs required; no sampling")
    need([(p[0], p[-1]) for p in selected_paths] == list(expected),
         "source vertex-order sources and target-order paths required")
    return ChainResult(graph, selection, tuple(summaries), tuple((*k, v) for k, v in counts.items()))


@dataclass(frozen=True)
class ChainDisplay:
    all_three_plus_counts: tuple[tuple[str, str, int, int], ...]
    combo_totals: tuple[tuple[str, int], ...]
    top25_combos: tuple[str, ...]
    top25_counts: tuple[tuple[str, str, int, int], ...]


def chain_display(result, *, combo_order):
    """R 476–509: complete >=3-cluster counts and explicit top25 display.

    Caller supplies native clean-combo grouping order to preserve tied totals.
    No path is removed from the underlying ChainResult.
    """
    need(type(result) is ChainResult, "complete chain result")
    counts = result.three_plus_counts
    represented = {row[1] for row in counts}
    ordered_labels(combo_order, represented, "complete native clean-combo group order")
    rank = {x: i for i, x in enumerate(combo_order)}
    counts = tuple(sorted(counts, key=lambda r: (rank[r[1]], -r[2])))
    totals = {combo: sum(r[3] for r in counts if r[1] == combo) for combo in combo_order if combo in represented}
    top25 = tuple(sorted(totals, key=lambda c: (-totals[c], rank[c]))[:25])
    return ChainDisplay(counts, tuple(totals.items()), top25, tuple(r for r in counts if r[1] in top25))


@dataclass(frozen=True)
class EffectorUpstream:
    input_rows: int
    selected_indices: tuple[int, ...]
    grouped_counts: tuple[tuple[str, str, str, int], ...]
    minor_presynaptic_classes: tuple[str, ...]
    presynaptic_plot_order: tuple[str, ...]
    target_counts: tuple[tuple[str, str, int, int], ...]


def effector_upstream(edges, binding, *, source_class_order, post_class_order, region_order):
    """R 558–639: original upstream-count and 1%-collapse branches.

    Full selected counts precede the <1% whole-table class collapse. Target
    neuron counts derive from original filtered rows, not collapsed classes.
    """
    validate_binding(binding); validate_edges(edges)
    chosen = tuple((i, e) for i, e in enumerate(edges) if e.pre_super_class is not None and
                   e.post_region in ("central_brain", "ventral_nerve_cord") and
                   e.pre_super_class not in ("glia", "trachea", "not_a_neuron") and
                   e.post_super_class in ("motor", "visceral_circulatory", "ascending_visceral_circulatory"))
    ordered_labels(source_class_order, (e.pre_super_class for _, e in chosen), "full source class grouping order")
    ordered_labels(post_class_order, (e.post_super_class for _, e in chosen), "full post class grouping order")
    ordered_labels(region_order, (e.post_region for _, e in chosen), "full region grouping order")
    groups = defaultdict(list); pre_totals = defaultdict(list); neuron_sets = defaultdict(set)
    for _, e in chosen:
        groups[e.pre_super_class, e.post_super_class, e.post_region].append(e.count)
        neuron_sets[e.post_super_class, e.post_region].add(e.post)
    totals = {k: checked_sum(v) for k, v in groups.items()}
    for (pre, _, _), count in totals.items(): pre_totals[pre].append(count)
    pre_totals = {k: checked_sum(v) for k, v in pre_totals.items()}
    grand = checked_sum(pre_totals.values())
    minor = tuple(p for p in source_class_order if p in pre_totals and grand and pre_totals[p] / grand < .01)
    collapsed = defaultdict(list)
    for (pre, post, region), count in totals.items():
        collapsed["other" if pre in minor else pre, post, region].append(count)
    collapsed = {k: checked_sum(v) for k, v in collapsed.items()}
    # Native dplyr group order, including synthetic "other", is explicit.
    ordered_labels(source_class_order, (k[0] for k in collapsed), "source class order must include generated other")
    sr = {x: i for i, x in enumerate(source_class_order)}
    pr = {x: i for i, x in enumerate(post_class_order)}; rr = {x: i for i, x in enumerate(region_order)}
    keys = sorted(collapsed, key=lambda k: (sr[k[0]], pr[k[1]], rr[k[2]]))
    counts = tuple((*k, collapsed[k]) for k in keys)
    by_pre = defaultdict(list); by_target = defaultdict(list)
    for (pre, post, region), count in collapsed.items():
        by_pre[pre].append(count); by_target[post, region].append(count)
    order = sorted(by_pre, key=lambda p: (-checked_sum(by_pre[p]), sr[p]))
    order = tuple([x for x in order if x != "other"] + (["other"] if "other" in order else []))
    target_keys = sorted(by_target, key=lambda k: (pr[k[0]], rr[k[1]]))
    labels = tuple((*k, checked_sum(by_target[k]), len(neuron_sets[k])) for k in target_keys)
    return EffectorUpstream(len(edges), tuple(i for i, _ in chosen), counts, minor, order, labels)


@dataclass(frozen=True)
class InfluenceRow:
    id: str
    seed: str
    target: str
    influence_original: float | int | None
    influence_norm_original: float | int | None
    level: str | None = None


@dataclass(frozen=True)
class ClusterAnnotation:
    root_id: str
    cluster: str | None


def map_an_dn_influence(rows, metadata, binding):
    """R 718–733 literal id→pre_cluster, stripped seed→post_cluster joins.

    The naming/orientation is kept even where biological intuition suggests the
    reverse. distinct(root_id,cluster) preserves conflicting-label multiplicity.
    """
    validate_binding(binding)
    need(type(rows) is tuple and type(metadata) is tuple, "complete ordered input tuples")
    lookup = defaultdict(list); seen = set()
    for m in metadata:
        need(type(m) is ClusterAnnotation, "exact root_id/cluster projection")
        label(m.root_id, False); label(m.cluster)
        if m.cluster is not None and (m.root_id, m.cluster) not in seen:
            seen.add((m.root_id, m.cluster)); lookup[m.root_id].append(m.cluster)
    out = []
    for row in rows:
        need(type(row) is InfluenceRow, "exact influence projection")
        label(row.id, False); label(row.seed, False)
        stripped = row.seed.rsplit("_", 1)[-1]
        for pre in lookup[row.id]:
            for post in lookup[stripped]:
                out.append(InfluenceRow(row.id, pre, post, row.influence_original, row.influence_norm_original, row.level))
    return tuple(out)


@dataclass(frozen=True)
class NormalizedInfluence:
    first_row: InfluenceRow
    input_indices: tuple[int, ...]
    no_seeds: float
    no_targets: int
    influence_quantile: float | None
    metrics: tuple[tuple[str, float], ...]
    unrounded_metrics: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class InfluenceResult:
    binding: InputBinding
    input_rows: int
    rows: tuple[NormalizedInfluence, ...]
    rounding: str
    authentic_qualified: bool = False
    native_float_qualified: bool = False


def portable_signif4(value):
    """Declared binary64 formatting; native R signif tie parity remains held."""
    return float(format(value, ".4g"))


def normalize_influence(rows, binding, *, rounding="portable_binary64_signif4"):
    """R calculate_influence_norms default const=-24, quantile=FALSE (p=0).

    Inputs are already fully annotated target/seed rows from the declared
    influence producer. Zero/positive ratios causing nonfinite normalizations
    are refused, not silently repaired. No influence graph solve occurs here.
    """
    validate_binding(binding)
    need(type(rows) is tuple and bool(rows), "complete nonempty influence rows")
    need(rounding == "portable_binary64_signif4", "explicit supported rounding profile")
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        need(type(row) is InfluenceRow, "exact influence row projection")
        for value in (row.id, row.seed, row.target): label(value, False)
        label(row.level)
        for value in (row.influence_original, row.influence_norm_original):
            need(value is None or (type(value) in (int, float) and math.isfinite(value) and value >= 0),
                 "finite nonnegative declared influence or missing")
        groups[row.target, row.seed].append(i)
    firsts = {key: rows[indices[0]] for key, indices in groups.items()}
    target_ids = defaultdict(set)
    for row in firsts.values(): target_ids[row.target].add(row.id)
    raw = {}; ratios = {}; quantiles = defaultdict(list)
    floor = math.exp(-24)
    for key, indices in groups.items():
        first = firsts[key]; a = first.influence_original; b = first.influence_norm_original
        ratio = 1.0 if a is None or b is None or (a == 0 and b == 0) else (a / b if b else math.inf)
        need(ratio > 0, "zero no_seeds yields native nonfinite normalization; domain held")
        ratios[key] = ratio
        total = sum(rows[i].influence_original or 0 for i in indices)
        need(math.isfinite(total), "native nonfinite aggregate domain held")
        n = len(target_ids[first.target])
        inf = max(total, floor); norm = max(total / (ratio * n), floor)
        raw[key] = {"influence": inf, "influence_norm": norm,
                    "influence_log": math.log(inf / n) + 24,
                    "influence_norm_log": math.log(norm) + 24}
        if a is not None: quantiles[first.seed].append(a)
    for suffix, field in (("", 0), ("_seed", 1)):
        by = defaultdict(list)
        for key in raw: by[key[field]].append(key)
        for keys in by.values():
            for metric in ("influence_log", "influence_norm_log"):
                vals = [raw[k][metric] for k in keys]; lo, hi = min(vals), max(vals)
                for key in keys:
                    raw[key][metric + "_minmax" + suffix] = 0.0 if hi == lo else (raw[key][metric] - lo) / (hi - lo)
    output = []
    for key, indices in groups.items():
        values = raw[key]
        need(all(math.isfinite(v) for v in values.values()), "native nonfinite result domain held")
        q = quantiles[firsts[key].seed]
        output.append(NormalizedInfluence(firsts[key], tuple(indices), ratios[key],
                      len(target_ids[firsts[key].target]), portable_signif4(min(q)) if q else None,
                      tuple((k, portable_signif4(v)) for k, v in values.items()), tuple(values.items())))
    return InfluenceResult(binding, len(rows), tuple(output), rounding)


@dataclass(frozen=True)
class InfluenceMatrix:
    metric: str
    seed_order: tuple[str, ...]
    target_order: tuple[str, ...]
    values: tuple[tuple[float | None, ...], ...]
    supported: tuple[tuple[bool, ...], ...]
    source_zero_filled: tuple[tuple[float, ...], ...]


def influence_matrix(result, *, seed_order, target_order, metric="influence_log_minmax"):
    """Full caller-declared target×seed axes, with support distinct from R fill.

    Every represented label must be included; no hidden plot-specific narrowing.
    Source R fill is returned separately; an absent pair remains unsupported.
    """
    need(type(result) is InfluenceResult, "normalized influence result")
    ordered_labels(seed_order, (r.first_row.seed for r in result.rows), "complete seed order")
    ordered_labels(target_order, (r.first_row.target for r in result.rows), "complete target order")
    cells = {}
    for r in result.rows:
        metrics = dict(r.metrics); need(metric in metrics, "source-defined metric")
        cells[r.first_row.target, r.first_row.seed] = metrics[metric]
    values = tuple(tuple(cells.get((t, s)) for s in seed_order) for t in target_order)
    support = tuple(tuple((t, s) in cells for s in seed_order) for t in target_order)
    source_fill = tuple(tuple(v if v is not None else 0.0 for v in row) for row in values)
    return InfluenceMatrix(metric, seed_order, target_order, values, support, source_fill)
