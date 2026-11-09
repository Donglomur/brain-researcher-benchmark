"""Complete supplied-graph community composition; no automatic I/O or fitting.

Python reference reuses the checked selector/affinity and composes the literal
producer stages. R remains a separate native source entrypoint. Candidate
methods receive complete inputs and need not use either reference algorithm.
Caller declarations and invented controls are not authentic-data qualification.
"""
from dataclasses import dataclass
import hashlib
import math
import operator
from pathlib import Path
import re
import sys
from types import ModuleType

REVISION = "65adfc22458b6084830c71f40e8c71c26414609e"
GRAPH_SHA = "a1b52f23b8a7ddcb72506090a7780be995c70f23b615a38d2145335610568616"
AFFINITY_SHA = "56c8bf35ebc55fec76baf0cd3acaa0a51dfb70a9f81714e370efe6528ee99918"
COMMON = Path(__file__).resolve().parents[2]
PROFILE = {"materialization": 888, "synapse_source": "v2", "min_connection_strength": 1,
           "cluster_count": 13, "cluster_seed": 10, "embedding_seed": 3}


class ProgramError(ValueError):
    pass


def require(value, message):
    if not value:
        raise ProgramError(message)


def _module(name, path, digest):
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == digest, "reviewed_source_pin_changed")
    if name in sys.modules:
        result = sys.modules[name]
        require(getattr(result, "__reviewed_source_sha256__", None) == digest,
                "conflicting_reviewed_module")
        return result
    result = ModuleType(name); result.__file__ = str(path)
    sys.modules[name] = result
    try:
        exec(compile(raw, str(path), "exec"), result.__dict__)
        result.__reviewed_source_sha256__ = digest
    except BaseException:
        del sys.modules[name]
        raise
    return result


def graph_source():
    return _module("banc_graph_prepare_" + GRAPH_SHA,
                   COMMON / "remaining-builds-wave8/paper_b-work/graph_prepare.py", GRAPH_SHA)


def affinity_source():
    return _module("banc_affinity_prepare_" + AFFINITY_SHA,
                   COMMON / "remaining-builds-wave9/paper_b-work/affinity_prepare.py", AFFINITY_SHA)


@dataclass(frozen=True, slots=True)
class MetadataFields:
    root_id: str | None
    supervoxel_id: object
    position: object
    cns_network: str | None


@dataclass(frozen=True, slots=True)
class PriorLabel:
    root_id: str | None
    cns_network: str | None


@dataclass(frozen=True, slots=True)
class CompleteInputs:
    metadata: tuple
    edges: tuple
    binding: object
    fields: tuple[MetadataFields, ...]
    label_origin: str
    prior_labels: tuple[PriorLabel, ...] | None
    prior_label_sha256: str | None


@dataclass(frozen=True, slots=True)
class MethodRow:
    root_id: str
    spectral_cluster: int
    umap_x: object
    umap_y: object
    cns_network: str


@dataclass(frozen=True, slots=True)
class CommunityRow:
    root_id: str
    supervoxel_id: object
    position: object
    spectral_cluster: int
    umap_x: object
    umap_y: object
    cns_network: str


@dataclass(frozen=True, slots=True)
class NamingTrace:
    cluster_ids: tuple[int, ...]
    old_labels: tuple[str, ...]
    overlap: tuple[tuple[int, ...], ...]
    square_assignment: tuple[int, ...]
    duplicate_policy: str = "last_nonmissing_nonblank_quality_row"


@dataclass(frozen=True, slots=True)
class ProgramResult:
    branch: str
    method_id: str
    graph_trace: object
    rows: tuple[CommunityRow, ...]
    naming_trace: NamingTrace | None
    declared_input_binding: object
    label_origin: str
    prior_label_sha256: str | None
    source_weight_cast_profile: str | None
    numerical_runtime_declaration: object
    historical_producer_identified: bool = False
    scientific_qualification: bool = False


def _nullable_label(value):
    require(value is None or type(value) is str, "nullable_plain_string_label_required")


def validate_inputs(inputs):
    require(type(inputs) is CompleteInputs and type(inputs.metadata) is tuple
            and type(inputs.edges) is tuple and type(inputs.fields) is tuple,
            "complete_immutable_inputs_required")
    require(len(inputs.fields) == len(inputs.metadata), "complete_metadata_field_row_alignment")
    for base, extra in zip(inputs.metadata, inputs.fields):
        require(type(extra) is MetadataFields and extra.root_id == base.root_id,
                "metadata_fields_same_original_row_order")
        _nullable_label(extra.cns_network)
    if inputs.label_origin == "local_quality_metadata":
        require(inputs.prior_labels is None and inputs.prior_label_sha256 is None,
                "local_labels_derived_from_same_complete_metadata")
    else:
        require(inputs.label_origin in ("external_o2_snapshot", "external_gcs_snapshot")
                and type(inputs.prior_labels) is tuple
                and type(inputs.prior_label_sha256) is str
                and re.fullmatch(r"[0-9a-f]{64}", inputs.prior_label_sha256),
                "explicit_complete_external_label_snapshot")
        for row in inputs.prior_labels:
            require(type(row) is PriorLabel, "prior_label_row_type")
            _nullable_label(row.root_id); _nullable_label(row.cns_network)


def _quality_indices(graph):
    # Outside-population rows remain in upstream quality-filtered metadata.
    return tuple(d.row_index for d in graph.metadata_decisions
                 if d.reason in ("selected", "outside_clustering_population"))


def metadata_and_prior(inputs, graph):
    first = {}
    eligible = _quality_indices(graph)
    for index in eligible:
        row = inputs.fields[index]
        first.setdefault(row.root_id, row)
    source = (tuple(PriorLabel(inputs.fields[i].root_id, inputs.fields[i].cns_network)
                    for i in eligible) if inputs.label_origin == "local_quality_metadata"
              else inputs.prior_labels)
    last = {}
    for row in source:
        if row.cns_network is not None and row.cns_network != "":
            last[row.root_id] = row.cns_network
    return first, last


def _cluster(value):
    require(not isinstance(value, bool), "integer_cluster_not_boolean")
    try:
        result = operator.index(value)
    except TypeError as error:
        raise ProgramError("integer_cluster_required") from error
    require(1 <= result <= PROFILE["cluster_count"], "cluster_in_original_1_to_13_domain")
    return result


def _matrix(matrix, rows, columns, name):
    require(len(matrix) == rows and all(len(row) == columns for row in matrix), name + "_complete_shape")
    for row in matrix:
        for value in row:
            require(not isinstance(value, bool) and math.isfinite(value), name + "_finite_numeric")


def python_names(neuron_ids, labels, prior_map, maximum_overlap, *, max_assignment_cells):
    """Literal Python overlap/square padding; assignment tie behavior stays in backend."""
    require(len(neuron_ids) == len(labels), "complete_naming_support")
    require(type(max_assignment_cells) is int and max_assignment_cells >= 0,
            "explicit_nonnegative_assignment_capacity")
    clusters = tuple(sorted(set(labels)))
    old = tuple(sorted({prior_map[i] for i in neuron_ids
                        if i in prior_map and prior_map[i] is not None and prior_map[i] != ""}))
    if old:
        n = max(len(clusters), len(old))
        require(n * n <= max_assignment_cells,
                "whole_square_assignment_capacity_no_label_truncation")
    counts = {cl: {name: 0 for name in old} for cl in clusters}
    for identity, cl in zip(neuron_ids, labels):
        name = prior_map.get(identity)
        if name in counts[cl]: counts[cl][name] += 1
    overlap = tuple(tuple(counts[cl][name] for name in old) for cl in clusters)
    named = {cl: str(cl) for cl in clusters}
    assigned = ()
    if old:
        square = tuple(tuple(overlap[i][j] if i < len(clusters) and j < len(old) else 0
                             for j in range(n)) for i in range(n))
        assigned = tuple(maximum_overlap(square))
        require(len(assigned) == n and all(type(j) is int for j in assigned)
                and set(assigned) == set(range(n)), "complete_square_assignment_permutation")
        for i, cl in enumerate(clusters):
            j = assigned[i]
            if j < len(old) and overlap[i][j] > 0:
                named[cl] = old[j]
    return tuple(named[cl] for cl in labels), NamingTrace(clusters, old, overlap, assigned)


def _rows(method_rows, ids, first):
    require(type(method_rows) is tuple and len(method_rows) == len(ids), "complete_output_tuple")
    out = []
    for identity, row in zip(ids, method_rows):
        require(type(row) is MethodRow and row.root_id == identity, "exact_ordered_full_output_support")
        cl = _cluster(row.spectral_cluster)
        require(type(row.cns_network) is str and row.cns_network != "", "nonempty_output_name")
        require(not isinstance(row.umap_x, bool) and not isinstance(row.umap_y, bool)
                and math.isfinite(row.umap_x) and math.isfinite(row.umap_y), "finite_complete_coordinates")
        require(identity in first, "complete_metadata_join")
        fields = first[identity]
        # Opaque metadata scalars are preserved: no invented supervoxel/position dtype.
        out.append(CommunityRow(identity, fields.supervoxel_id, fields.position, cl,
                                row.umap_x, row.umap_y, row.cns_network))
    return tuple(out)


def run_python_reference(inputs, *, source_weight_cast_profile, backend, max_assignment_cells):
    """Future full reference invocation. Tests substitute inert numerical backends.

    All supplied rows enter the exact reviewed affinity stage. There is no
    graph sample, alternate SCC, seed change, inferred cast, or reduced k.
    """
    validate_inputs(inputs)
    require(type(max_assignment_cells) is int and max_assignment_cells >= 0,
            "explicit_nonnegative_assignment_capacity")
    prepared = affinity_source().prepare_partition_input(
        inputs.metadata, inputs.edges, inputs.binding,
        source_weight_cast_profile=source_weight_cast_profile, min_connection_strength=1)
    graph = prepared.graph; ids = graph.neuron_ids
    require(len(ids) > 13, "original_eigsh_requires_n_greater_than_k_no_smaller_problem")
    labels, embedding = backend.spectral(prepared.affinity, clusters=13, cluster_seed=10)
    require(len(labels) == len(ids), "complete_cluster_support")
    labels = tuple(_cluster(label) for label in labels)
    _matrix(embedding, len(ids), 13, "spectral_embedding")
    coordinates = backend.umap(embedding, neighbors=100, embedding_seed=3)
    _matrix(coordinates, len(ids), 2, "umap")
    first, old = metadata_and_prior(inputs, graph)
    names, trace = python_names(ids, labels, old, backend.maximum_overlap,
                                max_assignment_cells=max_assignment_cells)
    proposed = tuple(MethodRow(identity, labels[i], coordinates[i][0], coordinates[i][1], names[i])
                     for i, identity in enumerate(ids))
    return ProgramResult("python", "source_reference", graph, _rows(proposed, ids, first), trace,
                         inputs.binding, inputs.label_origin, inputs.prior_label_sha256,
                         source_weight_cast_profile, backend.runtime_declaration)


def run_candidate(inputs, *, method_id, method, runtime_declaration):
    """Same full population/output problem; candidate internals remain unrestricted.

    The callback receives COMPLETE original rows, metadata fields and explicit
    prior-label source, plus the complete required coordinate order. It need
    not build the reference affinity, spectral features, k-means or UMAP.
    """
    validate_inputs(inputs)
    require(type(method_id) is str and bool(method_id.strip()) and method_id != "source_reference",
            "distinct_candidate_method_identity")
    graph = graph_source().prepare_graph(inputs.metadata, inputs.edges, inputs.binding,
                                         min_connection_strength=1)
    ids = graph.neuron_ids
    require(len(ids) > 13, "original_complete_problem_support_required")
    proposed = method(inputs, ids)
    first, _ = metadata_and_prior(inputs, graph)
    return ProgramResult("candidate", method_id, graph, _rows(proposed, ids, first), None,
                         inputs.binding, inputs.label_origin, inputs.prior_label_sha256,
                         None, runtime_declaration)


class NativePythonBackend:
    """Explicit future native implementation; constructing it imports libraries.

    No instance is created by this source build or its tests. Exact installed
    versions must match a caller-supplied declaration, which is not evidence
    of the historical runtime. No eigensolver RNG/start vector is added.
    """
    def __init__(self, runtime_declaration):
        import numpy as np
        import scipy
        import sklearn
        import umap
        from scipy.sparse.csgraph import laplacian
        from scipy.sparse.linalg import eigsh
        from scipy.optimize import linear_sum_assignment
        from sklearn.preprocessing import normalize
        from sklearn.cluster import KMeans
        observed = {"numpy": np.__version__, "scipy": scipy.__version__,
                    "sklearn": sklearn.__version__, "umap": umap.__version__}
        require(type(runtime_declaration) is dict and runtime_declaration == observed,
                "explicit_exact_native_runtime_declaration")
        require(observed["numpy"] == "2.2.6" and observed["scipy"] == "1.15.3",
                "reviewed_affinity_numerical_profile")
        self.runtime_declaration = dict(observed)
        self.np, self.umap_module = np, umap
        self.laplacian, self.eigsh, self.normalize = laplacian, eigsh, normalize
        self.KMeans, self.linear_sum_assignment = KMeans, linear_sum_assignment

    def spectral(self, affinity, *, clusters, cluster_seed):
        lap = self.laplacian(affinity, normed=True)
        _, eigvec = self.eigsh(lap, k=clusters, which="SM")
        embedding = self.normalize(eigvec)
        model = self.KMeans(n_clusters=clusters, random_state=cluster_seed, n_init=10)
        return model.fit_predict(embedding) + 1, embedding

    def umap(self, embedding, *, neighbors, embedding_seed):
        model = self.umap_module.UMAP(n_neighbors=neighbors, metric="cosine", min_dist=0,
                                     n_components=2, random_state=embedding_seed, n_jobs=1)
        return model.fit_transform(embedding)

    def maximum_overlap(self, square):
        matrix = self.np.asarray(square, dtype=self.np.int64)
        rows, columns = self.linear_sum_assignment(matrix, maximize=True)
        require(tuple(rows) == tuple(range(len(square))), "native_square_assignment_row_order")
        return tuple(int(j) for j in columns)
