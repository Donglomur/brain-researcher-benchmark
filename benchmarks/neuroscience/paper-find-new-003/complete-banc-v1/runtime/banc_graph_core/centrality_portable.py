"""Complete directed unweighted source-target betweenness, without native I/O.

The literal producer and consumer-documented count>=5 graphs are distinct
branches. No historical branch is selected by default. Multiplicity is retained;
community selection/peeling is never reused for this population.
"""
from collections import deque
from dataclasses import dataclass
import math
import re

REVISION = "65adfc22458b6084830c71f40e8c71c26414609e"
PRODUCER_SHA = "be4f37c1586136e0fcdb6bef6ab99431b10939a23b91a054143f193bb8b1aa8a"
BRANCHES = ("literal_producer_all_rows", "consumer_documented_count_ge5")
NON_NEURONS = re.compile("glia|trachea|not_a_neuron|merge|orpha|tadpole", re.IGNORECASE)
AFFERENT = frozenset(("sensory", "sensory_ascending", "sensory_descending"))
EFFERENT = frozenset(("motor", "visceral_circulatory", "ascending_visceral_circulatory"))


class CentralityError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise CentralityError(message)


@dataclass(frozen=True, slots=True)
class MetadataRow:
    root_id: str
    super_class: str | None
    proofread: str | None
    roughly_proofread: str | None
    cell_type: object


@dataclass(frozen=True, slots=True)
class EdgeRow:
    pre: str
    post: str
    count: object


@dataclass(frozen=True, slots=True)
class InputBinding:
    metadata_sha256: str
    edges_sha256: str
    id_cast_profile: str
    materialization: int = 888
    synapse_source: str = "v2"
    producer_revision: str = REVISION
    producer_sha256: str = PRODUCER_SHA


@dataclass(frozen=True, slots=True)
class CompleteInputs:
    metadata: tuple[MetadataRow, ...]
    edges: tuple[EdgeRow, ...]
    binding: InputBinding


@dataclass(frozen=True, slots=True)
class PreparedGraph:
    branch: str
    node_ids: tuple[str, ...]
    adjacency: tuple[tuple[int, ...], ...]
    retained_edge_rows: tuple[int, ...]
    metadata_decisions: tuple[str, ...]
    edge_decisions: tuple[str, ...]
    first_metadata: tuple[MetadataRow, ...]
    afferent_indices: tuple[int, ...]
    efferent_indices: tuple[int, ...]
    binding: InputBinding


@dataclass(frozen=True, slots=True)
class CentralityRow:
    vertex_id: int
    root_id: str
    super_class: str | None
    cell_type: object
    afferent_to_efferent: float
    all_to_all: float


@dataclass(frozen=True, slots=True)
class CentralityResult:
    graph: PreparedGraph
    rows: tuple[CentralityRow, ...]
    method_id: str
    managed_work_items: int
    arithmetic_profile: str
    historical_producer_identified: bool = False
    scientific_qualification: bool = False


class WorkBudget:
    """Caller-selected complete-operation bound; never returns a partial result."""
    def __init__(self, *, max_source_sweeps, max_work_items):
        require(type(max_source_sweeps) is int and max_source_sweeps >= 0
                and type(max_work_items) is int and max_work_items >= 0,
                "explicit_nonnegative_work_budget")
        self.max_source_sweeps = max_source_sweeps
        self.max_work_items = max_work_items
        self.used = 0

    def charge(self, count):
        require(self.used + count <= self.max_work_items, "complete_work_budget_exhausted_no_partial_output")
        self.used += count


def _nullable_text(value):
    require(value is None or type(value) is str, "nullable_string_metadata_domain")


def prepare(inputs, *, branch):
    require(type(inputs) is CompleteInputs and type(inputs.metadata) is tuple
            and type(inputs.edges) is tuple and type(inputs.binding) is InputBinding,
            "complete_immutable_input_tables_required")
    require(branch in BRANCHES, "explicit_centrality_source_discrepancy_branch_required")
    b = inputs.binding
    require(b.materialization == 888 and type(b.materialization) is int and b.synapse_source == "v2"
            and b.producer_revision == REVISION and b.producer_sha256 == PRODUCER_SHA,
            "exact_original_version_and_producer_binding")
    require(b.id_cast_profile == "already_plain_string_ids_no_missing_scalars",
            "explicit_original_ID_cast_domain_required")
    for digest in (b.metadata_sha256, b.edges_sha256):
        require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest), "declared_complete_source_hash")
    decisions = []; first = {}; afferents = set(); efferents = set()
    for row in inputs.metadata:
        require(type(row) is MetadataRow and type(row.root_id) is str, "plain_string_ID_no_inferred_cast")
        for value in (row.super_class, row.proofread, row.roughly_proofread): _nullable_text(value)
        if row.proofread != "TRUE" and row.roughly_proofread != "TRUE":
            decisions.append("not_literal_TRUE"); continue
        if row.super_class is None or NON_NEURONS.search(row.super_class):
            decisions.append("excluded_non_neuron_or_missing_class"); continue
        decisions.append("retained")
        first.setdefault(row.root_id, row)
        if row.super_class in AFFERENT: afferents.add(row.root_id)
        if row.super_class in EFFERENT: efferents.add(row.root_id)
    selected = set(first); retained = []; edge_decisions = []
    for i, row in enumerate(inputs.edges):
        require(type(row) is EdgeRow and type(row.pre) is str and type(row.post) is str,
                "plain_string_edge_ID_no_inferred_cast")
        if branch == "consumer_documented_count_ge5":
            require(row.count is None or (type(row.count) is int and row.count >= 0),
                    "documented_threshold_nullable_nonnegative_integer_count_domain")
            if row.count is None or row.count < 5:
                edge_decisions.append("below_documented_row_threshold"); continue
        # Literal producer never examines count, aggregates, removes loops or peels.
        if row.pre not in selected or row.post not in selected:
            edge_decisions.append("outside_neuron_population"); continue
        retained.append(i); edge_decisions.append("retained")
    ids = tuple(sorted({identity for i in retained for identity in (inputs.edges[i].pre, inputs.edges[i].post)}))
    index = {identity: i for i, identity in enumerate(ids)}
    adjacency = [[] for _ in ids]
    for i in retained:
        row = inputs.edges[i]
        adjacency[index[row.pre]].append(index[row.post])
    return PreparedGraph(branch, ids, tuple(tuple(row) for row in adjacency), tuple(retained),
                         tuple(decisions), tuple(edge_decisions), tuple(first[i] for i in ids),
                         tuple(index[i] for i in ids if i in afferents),
                         tuple(index[i] for i in ids if i in efferents), b)


def _brandes(adjacency, sources, targets, budget):
    """Directed edge-distinct shortest paths; endpoint contributions excluded.

    Targets=None means every node; an empty target set means no pairs. Integer
    path multiplicities stay exact; dependency arithmetic uses Python binary64.
    No native igraph bit-order/runtime equivalence is claimed.
    """
    n = len(adjacency); total = [0.0] * n
    target_set = None if targets is None else frozenset(targets)
    for source in sources:
        budget.charge(n + 1)
        predecessors = [[] for _ in range(n)]
        paths = [0] * n; distance = [-1] * n
        paths[source] = 1; distance[source] = 0
        queue = deque((source,)); stack = []
        while queue:
            vertex = queue.popleft(); stack.append(vertex)
            for neighbor in adjacency[vertex]:
                budget.charge(1)
                if distance[neighbor] < 0:
                    distance[neighbor] = distance[vertex] + 1; queue.append(neighbor)
                if distance[neighbor] == distance[vertex] + 1:
                    paths[neighbor] += paths[vertex]
                    predecessors[neighbor].append(vertex)
        dependency = [0.0] * n
        while stack:
            vertex = stack.pop()
            target = 1.0 if target_set is None or vertex in target_set else 0.0
            for predecessor in predecessors[vertex]:
                budget.charge(1)
                dependency[predecessor] += (paths[predecessor] / paths[vertex]) * (target + dependency[vertex])
            if vertex != source:
                total[vertex] += dependency[vertex]
        require(all(math.isfinite(v) and v >= 0 for v in total), "finite_betweenness_arithmetic_required")
    return tuple(total)


def _output(graph, restricted, unrestricted, method_id, used, arithmetic):
    require(len(restricted) == len(unrestricted) == len(graph.node_ids), "complete_two_mode_output")
    rows = []
    for i, identity in enumerate(graph.node_ids):
        for value in (restricted[i], unrestricted[i]):
            require(not isinstance(value, bool) and math.isfinite(value) and value >= 0,
                    "finite_nonnegative_centrality_output")
        meta = graph.first_metadata[i]
        rows.append(CentralityRow(i, identity, meta.super_class, meta.cell_type, restricted[i], unrestricted[i]))
    return CentralityResult(graph, tuple(rows), method_id, used, arithmetic)


def run_reference(inputs, *, branch, budget):
    graph = prepare(inputs, branch=branch)
    require(type(budget) is WorkBudget, "explicit_complete_work_budget_required")
    sweeps = len(graph.node_ids) + len(graph.afferent_indices)
    require(sweeps <= budget.max_source_sweeps, "all_required_sources_fit_no_sampling")
    restricted = _brandes(graph.adjacency, graph.afferent_indices, graph.efferent_indices, budget)
    unrestricted = _brandes(graph.adjacency, range(len(graph.node_ids)), None, budget)
    return _output(graph, restricted, unrestricted, "portable_directed_brandes", budget.used,
                   "exact_integer_path_counts_with_Python_binary64_dependencies_not_native_bit_parity")


def run_candidate(inputs, *, branch, method_id, method):
    """Method sees all inputs/support/cohorts and may use any complete algorithm."""
    require(type(method_id) is str and bool(method_id.strip()) and method_id != "portable_directed_brandes",
            "distinct_candidate_method_id")
    graph = prepare(inputs, branch=branch)
    restricted, unrestricted = method(inputs, graph)
    return _output(graph, restricted, unrestricted, method_id, 0, "candidate_declared_algorithm")
