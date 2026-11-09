"""BANC Python-branch graph preparation, stopping before numerical affinity.

Source: bancpipeline 65adfc22458b6084830c71f40e8c71c26414609e,
banc/clustering/banc-spectral-clustering.py:198-290. This pure interface
performs no I/O, native import, graph fit, partition naming or assessment.
Its source-only controls do not authenticate supplied bindings or paper parity.
"""
from dataclasses import dataclass
import re


REVISION = "65adfc22458b6084830c71f40e8c71c26414609e"
PRODUCER_SHA256 = "890c3725fa5a4b204d550bf091f2b12d79a2465edc31c65da1b6936b54ed8d6a"
_MAX_COUNT = (1 << 63) - 1
_BAD_CLASS = re.compile("glia|trachea|not_a_neuron|merge|debris", re.IGNORECASE)
_BAD_STATUS = re.compile("GLIA|TRACHEA|NOT_A_NEURON|DEBRIS|MERGE|DELETE")
_NECK = re.compile("ascending|descending")
_EXCLUDED_REGION_CLASS = re.compile("sensory|motor|efferent|afferent|visceral")


class ContractError(ValueError):
    """Input is outside the explicitly supported source domain."""


@dataclass(frozen=True, slots=True)
class DeclaredInputBinding:
    """Caller declarations only; input hashes are not verified by this helper."""
    branch: str
    producer_revision: str
    producer_sha256: str
    materialization: int
    synapse_source: str
    metadata_sha256: str
    edges_sha256: str


@dataclass(frozen=True, slots=True)
class MetadataRow:
    root_id: str | None
    super_class: str | None
    status: str | None
    proofread: str | None
    roughly_proofread: str | None
    region: str | None


@dataclass(frozen=True, slots=True)
class EdgeRow:
    pre: str | None
    post: str | None
    count: int | None


@dataclass(frozen=True, slots=True)
class MetadataDecision:
    row_index: int
    reason: str
    clustering_set: str | None


@dataclass(frozen=True, slots=True)
class EdgeDecision:
    row_index: int
    reason: str


@dataclass(frozen=True, slots=True)
class PeelRound:
    intersection_size: int
    edge_rows_before: int
    edge_rows_after: int


@dataclass(frozen=True, slots=True)
class PairWeight:
    pre: str
    post: str
    weight: int


@dataclass(frozen=True, slots=True)
class PreparedGraph:
    declared_binding: DeclaredInputBinding
    min_connection_strength: int
    selected_ids: tuple[str, ...]
    neuron_ids: tuple[str, ...]
    metadata_decisions: tuple[MetadataDecision, ...]
    edge_decisions: tuple[EdgeDecision, ...]
    retained_edge_row_indices: tuple[int, ...]
    peel_rounds: tuple[PeelRound, ...]
    pair_weights: tuple[PairWeight, ...]


def _nullable_text(value: object) -> None:
    # Do not coerce actual Arrow/pandas values here. In particular Python True
    # would become "True", not the literal "TRUE" in the upstream comparison.
    if value is not None and type(value) is not str:
        raise ContractError("Metadata/endpoint values must be plain strings or None")
    if isinstance(value, str) and any(c in value for c in ("\x00", "\r", "\n")):
        raise ContractError("NUL, CR and LF are outside the supported string domain")


def _binding(binding: DeclaredInputBinding) -> None:
    if type(binding) is not DeclaredInputBinding:
        raise ContractError("An explicit DeclaredInputBinding is required")
    if (binding.branch != "python" or binding.producer_revision != REVISION
            or binding.producer_sha256 != PRODUCER_SHA256):
        raise ContractError("Only the exact pinned Python producer branch is supported")
    if (type(binding.materialization) is not int or binding.materialization != 888
            or binding.synapse_source != "v2"):
        raise ContractError("The original task requires materialization 888 / synapse v2")
    for digest in (binding.metadata_sha256, binding.edges_sha256):
        if type(digest) is not str or re.fullmatch("[0-9a-f]{64}", digest) is None:
            raise ContractError("Opaque source object declarations require lowercase SHA256")


def _classify(row: MetadataRow, index: int) -> MetadataDecision:
    if type(row) is not MetadataRow:
        raise ContractError("Expected MetadataRow")
    for value in (row.root_id, row.super_class, row.status, row.proofread,
                  row.roughly_proofread, row.region):
        _nullable_text(value)
    if row.root_id is None or row.root_id == "":
        return MetadataDecision(index, "missing_or_empty_root_id", None)
    if (_BAD_CLASS.search(row.super_class or "")
            or _BAD_STATUS.search(row.status or "")):
        return MetadataDecision(index, "excluded_quality_text", None)
    if row.proofread != "TRUE" and row.roughly_proofread != "TRUE":
        return MetadataDecision(index, "proofread_not_literal_TRUE", None)
    if row.super_class in ("visual_centrifugal", "visual_projection"):
        group = "visual"
    elif _NECK.search(row.super_class or ""):
        group = "neck_connective"
    elif (row.region in ("central_brain", "ventral_nerve_cord")
          and not _EXCLUDED_REGION_CLASS.search(row.super_class or "")):
        group = row.region
    else:
        return MetadataDecision(index, "outside_clustering_population", None)
    return MetadataDecision(index, "selected", group)


def prepare_graph(metadata: tuple[MetadataRow, ...], edges: tuple[EdgeRow, ...],
                  binding: DeclaredInputBinding, *,
                  min_connection_strength: int = 1) -> PreparedGraph:
    """Select and aggregate the complete supplied graph without fitting it.

    Source rows are validated before filtering. None means a missing scalar;
    no coercion, unknown flag normalization, ID rewriting or deduplication is
    performed. Metadata duplicate IDs contribute by source set union. Integer
    counts/sums must fit signed int64; native missing/float/overflow behavior is
    outside this domain. Thresholds are applied per row before aggregation.

    The literal iterative in/out-endpoint intersection is retained, including
    disconnected cycles. This does not compute an SCC. Empty graphs are valid
    preparation results, not evidence that downstream spectral fitting works.
    """
    _binding(binding)
    if type(metadata) is not tuple or type(edges) is not tuple:
        raise ContractError("Complete metadata and edge rows must be immutable tuples")
    if (type(min_connection_strength) is not int
            or not 1 <= min_connection_strength <= _MAX_COUNT):
        raise ContractError("Minimum strength must be a positive signed-int64 integer")
    metadata_decisions = tuple(_classify(row, i) for i, row in enumerate(metadata))
    selected = {metadata[d.row_index].root_id for d in metadata_decisions
                if d.reason == "selected"}
    decisions = []
    retained = []
    for index, row in enumerate(edges):
        if type(row) is not EdgeRow:
            raise ContractError("Expected EdgeRow")
        _nullable_text(row.pre)
        _nullable_text(row.post)
        if row.count is not None and (type(row.count) is not int
                                     or not 0 <= row.count <= _MAX_COUNT):
            raise ContractError("Counts must be nonnegative signed-int64 integers or None")
        if row.count is None or row.count < min_connection_strength:
            reason = "below_threshold_or_missing_count"
        elif row.pre == row.post:
            reason = "self_edge"
        elif row.pre not in selected or row.post not in selected:
            reason = "endpoint_outside_population"
        else:
            reason = "retained_before_peeling"
            retained.append(index)
        decisions.append(EdgeDecision(index, reason))

    rounds = []
    previous_size = -1
    while True:
        both = ({edges[i].pre for i in retained}
                & {edges[i].post for i in retained})
        if len(both) == previous_size:
            break
        previous_size = len(both)
        next_retained = [i for i in retained
                         if edges[i].pre in both and edges[i].post in both]
        rounds.append(PeelRound(len(both), len(retained), len(next_retained)))
        retained = next_retained

    retained_set = set(retained)
    decisions = tuple(EdgeDecision(d.row_index, "peeled")
                      if d.reason == "retained_before_peeling" and d.row_index not in retained_set
                      else EdgeDecision(d.row_index, "retained")
                      if d.row_index in retained_set else d for d in decisions)
    summed = {}
    for index in retained:
        row = edges[index]
        key = (row.pre, row.post)
        summed[key] = summed.get(key, 0) + row.count
        if summed[key] > _MAX_COUNT:
            raise ContractError("Aggregated pair weight exceeds signed-int64 domain")
    return PreparedGraph(
        binding, min_connection_strength, tuple(sorted(selected)), tuple(sorted(both)),
        metadata_decisions, decisions, tuple(retained), tuple(rounds),
        tuple(PairWeight(pre, post, summed[(pre, post)]) for pre, post in sorted(summed)),
    )
