"""Target-free provenance families and crossed person/family coordinates.

Every object in this module is metadata. Descriptors and hashes record supplied
provenance; they are neither authentic-input authority nor evidence validation.
No source file, media, signal, model, or target is opened here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import PurePosixPath
from typing import Iterator

METHOD = "NEURAL080-family-v1"
PERSONS = tuple(f"sub-{i:02d}" for i in range(1, 7))
VIDEO_IDS = tuple(range(1, 1103))
FOLDS = tuple(range(5))


class SplitError(ValueError):
    """Supplied provenance or coordinates do not satisfy the selected design."""


@dataclass(frozen=True)
class EvidenceDescriptor:
    path: str
    bytes: int
    sha256: str


@dataclass(frozen=True, order=True)
class DonorIdentity:
    """Observed shared source-item identity, not an analyst-created category."""
    namespace: str
    identity: str


@dataclass(frozen=True)
class VideoProvenance:
    video_id: int
    donor_identities: tuple[DonorIdentity, ...]
    evidence: tuple[EvidenceDescriptor, ...]


@dataclass(frozen=True)
class DuplicateEdge:
    left_video_id: int
    right_video_id: int
    evidence: tuple[EvidenceDescriptor, ...]


@dataclass(frozen=True)
class ProvenanceGraph:
    provider_identity: str
    source_version: str
    evidence: tuple[EvidenceDescriptor, ...]
    videos: tuple[VideoProvenance, ...]
    duplicate_edges: tuple[DuplicateEdge, ...]


@dataclass(frozen=True)
class FamilyComponent:
    component_sha256: str
    video_ids: tuple[int, ...]
    donor_identities: tuple[DonorIdentity, ...]
    fold: int


@dataclass(frozen=True)
class FamilyPlan:
    method: str
    persons: tuple[str, ...]
    source_graph: ProvenanceGraph
    source_graph_sha256: str
    components: tuple[FamilyComponent, ...]
    video_to_fold: tuple[int, ...]  # entry video_id - 1, all 1,102 identities
    fold_video_ids: tuple[tuple[int, ...], ...]
    assignment_sha256: str


@dataclass(frozen=True)
class InnerCell:
    outer_person: str
    outer_fold: int
    validation_person: str
    validation_fold: int
    fit_persons: tuple[str, ...]
    fit_video_ids: tuple[int, ...]
    validation_video_ids: tuple[int, ...]

    def fit_coordinates(self) -> Iterator[tuple[str, int]]:
        for person in self.fit_persons:
            for video_id in self.fit_video_ids:
                yield person, video_id

    def validation_coordinates(self) -> Iterator[tuple[str, int]]:
        for video_id in self.validation_video_ids:
            yield self.validation_person, video_id


@dataclass(frozen=True)
class OuterCase:
    case_id: str
    query_person: str
    query_fold: int
    training_persons: tuple[str, ...]
    training_video_ids: tuple[int, ...]
    query_video_ids: tuple[int, ...]
    inner_cells: tuple[InnerCell, ...]

    def training_coordinates(self) -> Iterator[tuple[str, int]]:
        for person in self.training_persons:
            for video_id in self.training_video_ids:
                yield person, video_id

    def query_coordinates(self) -> Iterator[tuple[str, int]]:
        for video_id in self.query_video_ids:
            yield self.query_person, video_id


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise SplitError(message)


def _text(value: object, label: str) -> str:
    _need(type(value) is str and bool(value) and value == value.strip(),
          "Nonempty observed " + label + " required")
    _need(not any(ord(char) < 32 or ord(char) == 127 for char in value),
          "Control character in " + label)
    return value


def _descriptor(value: EvidenceDescriptor) -> EvidenceDescriptor:
    _need(type(value) is EvidenceDescriptor, "Typed source evidence required")
    path = _text(value.path, "evidence path")
    parsed = PurePosixPath(path)
    _need(not parsed.is_absolute() and parsed.as_posix() == path and
          "\\" not in path and all(part not in ("", ".", "..") for part in path.split("/")),
          "Canonical relative evidence path required")
    _need(type(value.bytes) is int and 0 < value.bytes < 2**63,
          "Positive observed evidence extent required")
    _need(type(value.sha256) is str and len(value.sha256) == 64 and
          all(char in "0123456789abcdef" for char in value.sha256),
          "Observed evidence SHA-256 required")
    return value


def _evidence(values: tuple[EvidenceDescriptor, ...]) -> tuple[EvidenceDescriptor, ...]:
    _need(type(values) is tuple and bool(values), "Missing source evidence")
    result = tuple(_descriptor(value) for value in values)
    _need(len(set(result)) == len(result), "Duplicate evidence descriptor")
    return tuple(sorted(result, key=lambda value: (value.path, value.bytes, value.sha256)))


def _donors(values: tuple[DonorIdentity, ...]) -> tuple[DonorIdentity, ...]:
    _need(type(values) is tuple and bool(values),
          "Each video requires observed donor/provenance identities")
    for value in values:
        _need(type(value) is DonorIdentity, "Typed observed donor identity required")
        _text(value.namespace, "donor namespace")
        _text(value.identity, "donor identity")
    _need(len(set(values)) == len(values), "Duplicate donor identity for one video")
    return tuple(sorted(values))


def _persons(persons: tuple[str, ...]) -> tuple[str, ...]:
    _need(type(persons) is tuple and len(persons) == 6 and
          all(type(person) is str for person in persons) and set(persons) == set(PERSONS),
          "All six canonical persons exactly once required")
    return PERSONS


def validate_graph(graph: ProvenanceGraph) -> ProvenanceGraph:
    """Validate and canonicalize supplied metadata without attesting its meaning."""
    _need(type(graph) is ProvenanceGraph, "Typed complete provenance graph required")
    _text(graph.provider_identity, "provenance provider identity")
    _text(graph.source_version, "provenance source version")
    evidence = _evidence(graph.evidence)
    _need(type(graph.videos) is tuple and len(graph.videos) == len(VIDEO_IDS),
          "Exactly 1,102 observed video provenance rows required")
    videos = []
    seen = set()
    for row in graph.videos:
        _need(type(row) is VideoProvenance and type(row.video_id) is int and
              row.video_id in VIDEO_IDS and row.video_id not in seen,
              "Unique canonical video identity required")
        seen.add(row.video_id)
        videos.append(VideoProvenance(row.video_id, _donors(row.donor_identities),
                                      _evidence(row.evidence)))
    _need(seen == set(VIDEO_IDS), "Complete 1..1,102 video support required")
    _need(type(graph.duplicate_edges) is tuple and
          len(graph.duplicate_edges) <= len(VIDEO_IDS) * (len(VIDEO_IDS) - 1) // 2,
          "Finite unique duplicate-edge roster required")
    edges = []
    seen_edges = set()
    for edge in graph.duplicate_edges:
        _need(type(edge) is DuplicateEdge and type(edge.left_video_id) is int and
              type(edge.right_video_id) is int and edge.left_video_id in seen and
              edge.right_video_id in seen and edge.left_video_id != edge.right_video_id,
              "Duplicate edges require two distinct selected video identities")
        pair = tuple(sorted((edge.left_video_id, edge.right_video_id)))
        _need(pair not in seen_edges, "Duplicate graph edge; combine its observed evidence")
        seen_edges.add(pair)
        edges.append(DuplicateEdge(*pair, _evidence(edge.evidence)))
    return ProvenanceGraph(graph.provider_identity, graph.source_version, evidence,
                           tuple(sorted(videos, key=lambda row: row.video_id)),
                           tuple(sorted(edges, key=lambda edge: (edge.left_video_id,
                                                               edge.right_video_id))))


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def component_digest(video_ids: tuple[int, ...]) -> str:
    """Selected tie key: prefix, newline, compact JSON of sorted member IDs."""
    _need(type(video_ids) is tuple and bool(video_ids) and
          all(type(video_id) is int and video_id in VIDEO_IDS for video_id in video_ids) and
          tuple(sorted(set(video_ids))) == video_ids,
          "Canonical component member tuple required")
    return hashlib.sha256(METHOD.encode("ascii") + b"\n" +
                          _canonical_bytes(video_ids)).hexdigest()


def _construct(graph: ProvenanceGraph, persons: tuple[str, ...]) -> FamilyPlan:
    parent = {video_id: video_id for video_id in VIDEO_IDS}

    def find(video_id: int) -> int:
        while parent[video_id] != video_id:
            parent[video_id] = parent[parent[video_id]]
            video_id = parent[video_id]
        return video_id

    def union(left: int, right: int) -> None:
        left, right = find(left), find(right)
        if left != right:
            parent[max(left, right)] = min(left, right)

    first = {}
    for row in graph.videos:
        for donor in row.donor_identities:
            if donor in first:
                union(row.video_id, first[donor])
            else:
                first[donor] = row.video_id
    for edge in graph.duplicate_edges:
        union(edge.left_video_id, edge.right_video_id)
    grouped = {}
    for video_id in VIDEO_IDS:
        grouped.setdefault(find(video_id), []).append(video_id)
    members = tuple(tuple(ids) for ids in grouped.values())
    _need(len(members) >= len(FOLDS),
          "At least five actual provenance/duplicate components required; never split a component")
    keyed = tuple((ids, component_digest(ids)) for ids in members)
    _need(len({key for _, key in keyed}) == len(keyed),
          "Component digest collision; explicit source review required")
    ordered = sorted(keyed, key=lambda item: (-len(item[0]), item[1]))
    counts = [0] * len(FOLDS)
    mapping = [-1] * len(VIDEO_IDS)
    components = []
    by_video = {row.video_id: row for row in graph.videos}
    for ids, key in ordered:
        fold = min(FOLDS, key=lambda candidate: (counts[candidate], candidate))
        counts[fold] += len(ids)
        donors = tuple(sorted({donor for video_id in ids
                               for donor in by_video[video_id].donor_identities}))
        components.append(FamilyComponent(key, ids, donors, fold))
        for video_id in ids:
            mapping[video_id - 1] = fold
    fold_ids = tuple(tuple(video_id for video_id in VIDEO_IDS
                           if mapping[video_id - 1] == fold) for fold in FOLDS)
    _need(all(fold_ids) and all(fold in FOLDS for fold in mapping),
          "All five folds require nonempty complete support")
    graph_sha = _digest(asdict(graph))
    assignment = {"method": METHOD, "persons": persons,
                  "source_graph_sha256": graph_sha,
                  "components": [asdict(component) for component in components],
                  "video_to_fold": mapping, "fold_video_ids": fold_ids}
    return FamilyPlan(METHOD, persons, graph, graph_sha, tuple(components),
                      tuple(mapping), fold_ids, _digest(assignment))


def build_family_plan(graph: ProvenanceGraph,
                      persons: tuple[str, ...] = PERSONS) -> FamilyPlan:
    """Construct the selected split from complete supplied provenance only."""
    return _construct(validate_graph(graph), _persons(persons))


def validate_family_plan(plan: FamilyPlan) -> FamilyPlan:
    """Recompute graph closure, balancing, complete support and both digests."""
    _need(type(plan) is FamilyPlan, "Typed family plan required")
    expected = _construct(validate_graph(plan.source_graph), _persons(plan.persons))
    _need(plan == expected, "Plan differs from the complete deterministic source assignment")
    return plan


def _outer_case(plan: FamilyPlan, query_person: str, query_fold: int) -> OuterCase:
    training_persons = tuple(person for person in PERSONS if person != query_person)
    training_ids = tuple(video_id for video_id in VIDEO_IDS
                         if plan.video_to_fold[video_id - 1] != query_fold)
    query_ids = plan.fold_video_ids[query_fold]
    cells = []
    for validation_person in training_persons:
        for validation_fold in FOLDS:
            if validation_fold == query_fold:
                continue
            fit_persons = tuple(person for person in training_persons
                                if person != validation_person)
            fit_ids = tuple(video_id for video_id in training_ids
                            if plan.video_to_fold[video_id - 1] != validation_fold)
            validation_ids = plan.fold_video_ids[validation_fold]
            _need(len(fit_persons) == 4 and fit_ids and validation_ids,
                  "Inner FIT and validation support must be nonempty")
            cells.append(InnerCell(query_person, query_fold, validation_person,
                                   validation_fold, fit_persons, fit_ids, validation_ids))
    _need(len(training_persons) == 5 and training_ids and query_ids and len(cells) == 20,
          "Complete outer and twenty-cell inner support required")
    return OuterCase(f"{query_person}.family-{query_fold}", query_person, query_fold,
                     training_persons, training_ids, query_ids, tuple(cells))


def outer_cases(plan: FamilyPlan) -> tuple[OuterCase, ...]:
    """All 6 x 5 outer cases; each has all 5 x 4 inner validation cells."""
    validate_family_plan(plan)
    return tuple(_outer_case(plan, person, fold) for person in PERSONS for fold in FOLDS)


def validate_outer_case(plan: FamilyPlan, case: OuterCase) -> OuterCase:
    validate_family_plan(plan)
    _need(type(case) is OuterCase and case.query_person in PERSONS and
          type(case.query_fold) is int and case.query_fold in FOLDS,
          "Canonical outer coordinates required")
    _need(case == _outer_case(plan, case.query_person, case.query_fold),
          "Outer case or inner cells changed selected full support")
    return case


def validate_outer_cases(plan: FamilyPlan,
                         cases: tuple[OuterCase, ...]) -> tuple[OuterCase, ...]:
    _need(type(cases) is tuple and len(cases) == 30,
          "Complete thirty-case outer roster required")
    _need(cases == outer_cases(plan), "Missing, repeated, reordered or changed outer case")
    return cases


def assignment_document(plan: FamilyPlan) -> dict:
    """Complete data-only membership/provenance record, with no issuer fields."""
    validate_family_plan(plan)
    return {"schema": "neural080_family_assignment_v1", **asdict(plan)}
