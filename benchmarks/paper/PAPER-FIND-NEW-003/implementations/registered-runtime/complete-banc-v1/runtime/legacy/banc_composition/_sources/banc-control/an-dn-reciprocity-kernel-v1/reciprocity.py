"""Conditional AN/DN direct-reciprocity consumer; no I/O or scientific admission.

Source: BANC-project commit 2e78ce38e946ab80e120a42f504a019b3a567fef,
R/figures/panels_an_dn_connectivity.R:175-233. Stops before display-string
plot selection. Cohort, annotations and source grouping order are supplied,
not authenticated here. See CONTRACT.json for domain and arithmetic limits.
"""
from dataclasses import dataclass
import math


class ContractError(ValueError):
    """The supplied typed input is outside this component's stated domain."""


@dataclass(frozen=True, slots=True)
class AnnotatedEdge:
    pre: str
    post: str
    count: int | None
    pre_cluster: str | None
    post_cluster: str | None
    pre_neurotransmitter: str | None


@dataclass(frozen=True, slots=True)
class SourceGroupOrder:
    cluster_labels: tuple[str, ...]
    neurotransmitter_labels: tuple[str | None, ...]


@dataclass(frozen=True, slots=True)
class ReciprocityInput:
    edges: tuple[AnnotatedEdge, ...]
    eligible_ids: frozenset[str]
    source_order: SourceGroupOrder


@dataclass(frozen=True, slots=True)
class TransmitterFraction:
    pre_cluster: str
    post_cluster: str
    neurotransmitter: str | None
    count: int
    post_cluster_total: int
    norm: float


@dataclass(frozen=True, slots=True)
class PairReciprocity:
    pre_cluster: str
    post_cluster: str
    forward_norm: float
    reverse_norm: float
    directionality: float
    sum_norm: float


@dataclass(frozen=True, slots=True)
class ReciprocityResult:
    transmitter_rows: tuple[TransmitterFraction, ...]
    pairs: tuple[PairReciprocity, ...]
    directed_pairs: tuple[PairReciprocity, ...]
    reciprocal_pairs: tuple[PairReciprocity, ...]


_MAX_EXACT_TOTAL = (1 << 53) - 1
_TOP_N = 60


def _text(value: object, *, nullable: bool, nonempty: bool = False) -> None:
    if value is None and nullable:
        return
    if type(value) is not str or (nonempty and value == ""):
        raise ContractError("Expected a plain string in the declared domain")
    if any(char in value for char in ("\x00", "\r", "\n")):
        raise ContractError("NUL, CR and LF are outside the declared string domain")


def _ordinals(labels: object, *, nullable: bool) -> dict:
    if type(labels) is not tuple:
        raise ContractError("Source group order must use immutable tuples")
    for label in labels:
        _text(label, nullable=nullable)
    if len(set(labels)) != len(labels):
        raise ContractError("Source group order contains duplicate labels")
    return {label: index for index, label in enumerate(labels)}


def compute_reciprocity(data: ReciprocityInput) -> ReciprocityResult:
    """Compute literal source formula/order semantics on explicit typed inputs.

    Missing counts are omitted in sums. Duplicate edges are retained. Every
    edge contributes to its post-cluster denominator before cohort filtering.
    Caller order stands for the unverified plain-character R grouping order.
    Returned NaN/Infinity are intentional typed values, not JSON encodings.
    """
    if type(data) is not ReciprocityInput or type(data.edges) is not tuple:
        raise ContractError("Expected ReciprocityInput with an edge tuple")
    if type(data.eligible_ids) is not frozenset:
        raise ContractError("eligible_ids must be an immutable frozenset")
    for identity in data.eligible_ids:
        _text(identity, nullable=False, nonempty=True)
    if type(data.source_order) is not SourceGroupOrder:
        raise ContractError("Expected SourceGroupOrder")
    clusters = _ordinals(data.source_order.cluster_labels, nullable=False)
    transmitters = _ordinals(data.source_order.neurotransmitter_labels, nullable=True)
    totals: dict[str | None, int] = {}
    numerators: dict[tuple[str, str, str | None], int] = {}
    for edge in data.edges:
        if type(edge) is not AnnotatedEdge:
            raise ContractError("Expected AnnotatedEdge rows")
        _text(edge.pre, nullable=False, nonempty=True)
        _text(edge.post, nullable=False, nonempty=True)
        _text(edge.pre_cluster, nullable=True)
        _text(edge.post_cluster, nullable=True)
        _text(edge.pre_neurotransmitter, nullable=True)
        if edge.count is not None and (type(edge.count) is not int or edge.count < 0):
            raise ContractError("count must be a nonnegative integer or None")
        for label in (edge.pre_cluster, edge.post_cluster):
            if label is not None and label not in clusters:
                raise ContractError("Source group order does not cover an input cluster")
        if edge.pre_neurotransmitter not in transmitters:
            raise ContractError("Source group order does not cover an input transmitter")
        count = 0 if edge.count is None else edge.count
        total = totals.get(edge.post_cluster, 0) + count
        if total > _MAX_EXACT_TOTAL:
            raise ContractError("Post-cluster count total exceeds exact binary64 integer domain")
        totals[edge.post_cluster] = total
        if (edge.pre_cluster is not None and edge.post_cluster is not None
                and edge.pre in data.eligible_ids and edge.post in data.eligible_ids):
            key = (edge.pre_cluster, edge.post_cluster, edge.pre_neurotransmitter)
            numerators[key] = numerators.get(key, 0) + count

    nt_rows = []
    pair_terms: dict[tuple[str, str], list[float]] = {}
    ordered_keys = sorted(numerators, key=lambda key: (
        clusters[key[0]], clusters[key[1]], transmitters[key[2]]))
    for pre, post, nt in ordered_keys:
        # Source192-195: literal suffix after final underscore, not a numeric ID.
        if pre == post or pre.rsplit("_", 1)[-1] == post.rsplit("_", 1)[-1]:
            continue
        count = numerators[(pre, post, nt)]
        total = totals[post]
        norm = count / total if total else math.nan
        nt_rows.append(TransmitterFraction(pre, post, nt, count, total, norm))
        pair_terms.setdefault((pre, post), []).append(norm)

    # Source198-203 divides each transmitter group before summing with na.rm.
    pair_norms = {pair: math.fsum(value for value in values if not math.isnan(value))
                  for pair, values in pair_terms.items()}
    pairs = []
    for pre, post in sorted(pair_norms, key=lambda pair: (clusters[pair[0]], clusters[pair[1]])):
        forward = pair_norms[(pre, post)]
        reverse = pair_norms.get((post, pre), 0.0)
        ratio = forward / reverse if reverse > 0 else math.inf
        pairs.append(PairReciprocity(pre, post, forward, reverse, ratio, forward + reverse))
    # Stable sorting preserves explicit source group order for score ties.
    directed = sorted((pair for pair in pairs if pair.directionality >= 2),
                      key=lambda pair: pair.forward_norm, reverse=True)[:_TOP_N]
    reciprocal = sorted((pair for pair in pairs if 0.5 < pair.directionality < 2),
                        key=lambda pair: pair.sum_norm, reverse=True)[:_TOP_N]
    return ReciprocityResult(tuple(nt_rows), tuple(pairs), tuple(directed), tuple(reciprocal))
