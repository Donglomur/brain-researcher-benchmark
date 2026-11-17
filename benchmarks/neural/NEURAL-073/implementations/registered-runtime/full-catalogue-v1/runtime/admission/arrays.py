"""Finite canonical numeric admission and complete duplicate-screen primitives.

Only explicit operands are read. No NIfTI/header decoder, authentic-data loader,
filesystem discovery, fitted model, provider or permission issuer is present.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import hashlib
import math
from numbers import Real
import struct
from typing import Mapping, Sequence

from .catalogue import (AdmissionError, Catalogue, SOURCE_DOMAIN, INVENTED_DOMAIN,
                        canonical_json, digest, require_sha)

_OBS_SEAL = object()
_SCREEN_SEAL = object()
_ASSESSMENT_SEAL = object()


@dataclass
class WorkCounter:
    """Logical numeric work, not measured disk I/O, RSS, elapsed time or FLOPs."""
    record_scans: int = 0
    value_inspections: int = 0
    canonical_bytes_processed: int = 0
    snapshot_bytes_materialized: int = 0
    equality_comparisons: int = 0
    equality_value_bytes_compared: int = 0
    pair_universe: int = 0
    support_equal_pairs: int = 0
    support_different_pairs: int = 0
    exact_cross_person_pairs: int = 0
    distance_pairs: int = 0
    distance_coordinates: int = 0
    permutation_records: int = 0
    permutation_positions: int = 0
    permutation_index_bytes: int = 0
    cache_lookup_input_bytes: int = 0
    cache_hit_records: int = 0
    cache_hit_value_bytes: int = 0
    cache_admitted_value_bytes: int = 0
    cache_evicted_value_bytes: int = 0

    def as_dict(self):
        return dict(vars(self))


@dataclass(frozen=True)
class Geometry:
    """C-order (last axis fastest) common grid, never an assumed template."""
    shape: tuple[int, int, int]
    affine: tuple[float, ...]
    orientation: tuple[str, str, str]

    def __post_init__(self):
        object.__setattr__(self, "shape", tuple(self.shape))
        object.__setattr__(self, "affine", tuple(_real(v) for v in self.affine))
        object.__setattr__(self, "orientation", tuple(self.orientation))

    def validate(self, *, full: bool):
        if len(self.shape) != 3 or any(type(n) is not int or n <= 0 for n in self.shape):
            raise AdmissionError("exact positive three-dimensional shape required")
        if len(self.affine) != 16 or any(not isinstance(v, Real) or isinstance(v, bool) or not math.isfinite(v) for v in self.affine):
            raise AdmissionError("finite 4x4 numeric affine required")
        if tuple(self.affine[12:]) != (0, 0, 0, 1):
            raise AdmissionError("affine must have homogeneous final row")
        a = self.affine
        determinant = (a[0]*(a[5]*a[10]-a[6]*a[9])
                       - a[1]*(a[4]*a[10]-a[6]*a[8])
                       + a[2]*(a[4]*a[9]-a[5]*a[8]))
        if not math.isfinite(determinant) or determinant == 0:
            raise AdmissionError("singular or numerically invalid affine")
        pairs = {"L": 0, "R": 0, "P": 1, "A": 1, "I": 2, "S": 2}
        if len(self.orientation) != 3 or any(not isinstance(c, str) or c not in pairs for c in self.orientation) or len({pairs[c] for c in self.orientation}) != 3:
            raise AdmissionError("explicit valid orientation axes required")
        if full and (min(self.shape) < 4 or self.voxels < 256):
            raise AdmissionError("full profile requires axes>=4 and D>=256")

    @property
    def voxels(self):
        return math.prod(self.shape)

    @property
    def fingerprint(self):
        return digest(["float64-little-endian-C-order", self.shape, self.affine, self.orientation])

    def public_descriptor(self):
        return {"shape": list(self.shape), "affine": list(self.affine),
                "orientation": list(self.orientation), "dtype": "<f8", "order": "C"}


@dataclass(frozen=True)
class OriginalReceipt:
    """Private receipt for original bytes, distinct from decoded observations.

    Digests are identity bindings, not proof of conversion fidelity/rights.
    Those require the owner's independently verified external admission gates.
    """
    record_id: str
    domain: str
    original_sha256: str
    original_bytes: int
    source_version: str
    source_locator_digest: str
    rights_evidence_digest: str
    decoder_contract_digest: str
    conversion_evidence_digest: str

    def validate(self):
        if self.domain not in (SOURCE_DOMAIN, INVENTED_DOMAIN):
            raise AdmissionError("unrecognized data domain")
        if (not isinstance(self.record_id, str) or not self.record_id or type(self.original_bytes) is not int
            or self.original_bytes <= 0 or not isinstance(self.source_version, str) or not self.source_version):
            raise AdmissionError("incomplete original-body receipt")
        for name in ("original_sha256", "source_locator_digest", "rights_evidence_digest",
                     "decoder_contract_digest", "conversion_evidence_digest"):
            require_sha(getattr(self, name))
        if self.domain == INVENTED_DOMAIN and not self.record_id.startswith("invented:"):
            raise AdmissionError("invented receipt ID domain mismatch")

    @property
    def fingerprint(self):
        self.validate()
        return digest(vars(self))


@dataclass(frozen=True)
class Observation:
    record_id: str
    domain: str
    receipt_digest: str
    geometry: Geometry
    decoded_sha256: str
    decoded_bytes: int
    support_bits: bytes = field(repr=False)
    norm: float
    _seal: object = field(repr=False, compare=False)

    def private_descriptor(self):
        return {"record_id": self.record_id, "domain": self.domain,
                "original_receipt_digest": self.receipt_digest,
                "geometry_digest": self.geometry.fingerprint,
                "decoded_sha256": self.decoded_sha256,
                "decoded_bytes": self.decoded_bytes,
                "support_sha256": hashlib.sha256(self.support_bits).hexdigest(),
                "norm": self.norm}


def _real(value):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise AdmissionError("numeric values must be real scalars, not strings/bools")
    result = float(value)
    if not math.isfinite(result):
        raise AdmissionError("nonfinite decoded value")
    return result


def canonical_f64(values: Sequence[Real], work: WorkCounter | None = None) -> bytes:
    """Canonical <f8 bytes, preserving signed-zero bit patterns; no headers."""
    out = bytearray(8 * len(values))
    for j in range(len(values)):
        struct.pack_into("<d", out, 8*j, _real(values[j]))
    if work is not None:
        work.value_inspections += len(values)
        work.canonical_bytes_processed += len(out)
        work.snapshot_bytes_materialized += len(out)
    return bytes(out)


def decode_canonical_f64(raw: bytes, geometry: Geometry, *, full: bool) -> tuple[float, ...]:
    """Safe header-free codec; full byte length and finite values mandatory."""
    geometry.validate(full=full)
    if not isinstance(raw, bytes) or len(raw) != 8*geometry.voxels:
        raise AdmissionError("canonical float64 byte length mismatch")
    result = tuple(v[0] for v in struct.iter_unpack("<d", raw))
    if any(not math.isfinite(v) for v in result):
        raise AdmissionError("nonfinite canonical export")
    return result


def inspect_array(record_id: str, values: Sequence[Real], geometry: Geometry,
                  receipt: OriginalReceipt, work: WorkCounter | None = None) -> Observation:
    """Observe explicitly supplied decoded values; does not decode original bytes.

    Authentic invocation is an externally gated future action. Current tests use
    only INVENTED_DOMAIN. This routine cannot establish decoder fidelity.
    """
    receipt.validate()
    if record_id != receipt.record_id:
        raise AdmissionError("original/decoded record join mismatch")
    geometry.validate(full=receipt.domain == SOURCE_DOMAIN)
    if len(values) != geometry.voxels:
        raise AdmissionError("full grid values required; no masking/cropping")
    sha = hashlib.sha256()
    support = bytearray((len(values)+7)//8)
    norm = 0.0
    for j in range(len(values)):
        x = _real(values[j])
        sha.update(struct.pack("<d", x))
        if x != 0:
            support[j//8] |= 1 << (j % 8)
        norm = math.hypot(norm, x)
    if not math.isfinite(norm):
        raise AdmissionError("decoded norm overflow blocks numeric qualification")
    if work is not None:
        work.record_scans += 1
        work.value_inspections += len(values)
        work.canonical_bytes_processed += 8*len(values)
    return Observation(record_id, receipt.domain, receipt.fingerprint, geometry,
                       sha.hexdigest(), len(values)*8, bytes(support), norm, _OBS_SEAL)


def _snapshot(observation: Observation, values: Sequence[Real], work: WorkCounter):
    if observation._seal is not _OBS_SEAL:
        raise AdmissionError("unissued observation")
    raw = canonical_f64(values, work)
    if len(raw) != observation.decoded_bytes or hashlib.sha256(raw).hexdigest() != observation.decoded_sha256:
        raise AdmissionError("decoded values changed since observation")
    return raw


def _cross_pairs(ids, record_map):
    n = len(ids)
    persons = Counter(record_map[k].person for k in ids)
    return (n*n-sum(c*c for c in persons.values()))//2


@dataclass(frozen=True)
class DuplicateFlag:
    reason: str
    record_ids: tuple[str, ...]
    decoded_digests: tuple[str, ...]
    normalized_l2: float

    @property
    def flag_id(self):
        return digest([self.reason, self.record_ids, self.decoded_digests, self.normalized_l2])


@dataclass(frozen=True)
class ScreenReport:
    domain: str
    catalogue_digest: str
    observations_digest: str
    exact_groups: tuple[tuple[str, ...], ...]
    flags: tuple[DuplicateFlag, ...]
    counts: tuple[tuple[str, int], ...]
    _seal: object = field(repr=False, compare=False)

    @property
    def fingerprint(self):
        if self._seal is not _SCREEN_SEAL:
            raise AdmissionError("unissued screening report")
        return digest([self.domain, self.catalogue_digest, self.observations_digest,
                       self.exact_groups, [[f.flag_id, f.reason, f.record_ids, f.decoded_digests,
                                            f.normalized_l2] for f in self.flags], self.counts])


def observations_digest(observations: Mapping[str, Observation]):
    return digest([observations[k].private_descriptor() for k in sorted(observations)])


def screen_duplicates(catalogue: Catalogue, observations: Mapping[str, Observation],
                      values_by_id: Mapping[str, Sequence[Real]],
                      work: WorkCounter | None = None) -> ScreenReport:
    """Cover every cross-person pair under the exact/equal-support definition.

    A controlled lazy Mapping is allowed. Reads/revalidations and comparisons
    are counted; caller owns actual I/O capacity and mapping immutability.
    """
    catalogue.require_valid()
    work = WorkCounter() if work is None else work
    record_map = catalogue.by_id
    expected = set(record_map)
    if set(observations) != expected or set(values_by_id) != expected:
        raise AdmissionError("complete exact record set required for screening")
    geometry = None
    supports, digest_groups = defaultdict(list), defaultdict(list)
    for record_id in sorted(expected):
        o = observations[record_id]
        if o._seal is not _OBS_SEAL or o.domain != catalogue.domain or o.record_id != record_id:
            raise AdmissionError("observation domain/record mismatch")
        if geometry is None:
            geometry = o.geometry
        elif o.geometry != geometry:
            raise AdmissionError("heterogeneous native grids require explicit design revision")
        # Revalidates every input even if it has no same-support peer.
        _snapshot(o, values_by_id[record_id], work)
        supports[o.support_bits].append(record_id)
        digest_groups[o.decoded_sha256].append(record_id)
    all_pairs = _cross_pairs(tuple(expected), record_map)
    equal_pairs = sum(_cross_pairs(group, record_map) for group in supports.values())
    work.pair_universe += all_pairs
    work.support_equal_pairs += equal_pairs
    work.support_different_pairs += all_pairs-equal_pairs
    if catalogue.domain == SOURCE_DOMAIN and all_pairs != 41901550:
        raise AdmissionError("full source cross-person pair universe mismatch")
    exact_groups, flags, exact_membership = [], [], {}
    exact_cross = 0
    # Hash is only an index. Verify actual canonical bytes for every equality.
    for bucket in digest_groups.values():
        verified = []
        for rid in bucket:
            data = _snapshot(observations[rid], values_by_id[rid], work)
            found = False
            for representative, group in verified:
                other = _snapshot(observations[representative], values_by_id[representative], work)
                work.equality_comparisons += 1
                work.equality_value_bytes_compared += len(data)+len(other)
                if data == other:
                    group.append(rid)
                    found = True
                    break
            if not found:
                verified.append((rid, [rid]))
        for representative, group in verified:
            group = tuple(sorted(group))
            if len(group) < 2:
                continue
            group_index = len(exact_groups)
            exact_groups.append(group)
            exact_membership.update((rid, group_index) for rid in group)
            cross = _cross_pairs(group, record_map)
            exact_cross += cross
            if cross:
                flags.append(DuplicateFlag("exact_content", group,
                             tuple(observations[k].decoded_sha256 for k in group), 0.0))
    work.exact_cross_person_pairs += exact_cross
    distances = 0
    for group in supports.values():
        for j, left in enumerate(group):
            for right in group[j+1:]:
                if record_map[left].person == record_map[right].person:
                    continue
                if left in exact_membership and exact_membership.get(right) == exact_membership[left]:
                    continue
                x = _snapshot(observations[left], values_by_id[left], work)
                y = _snapshot(observations[right], values_by_id[right], work)
                denominator = max(observations[left].norm, observations[right].norm, 1e-12)
                distance = 0.0
                for (a,), (b,) in zip(struct.iter_unpack("<d", x), struct.iter_unpack("<d", y)):
                    # Scaling before subtraction avoids finite-input overflow.
                    distance = math.hypot(distance, a/denominator-b/denominator)
                if not math.isfinite(distance):
                    raise AdmissionError("nonfinite normalized distance")
                distances += 1
                work.distance_pairs += 1
                work.distance_coordinates += len(x)//8
                if distance <= 1e-6:
                    pair = tuple(sorted((left, right)))
                    flags.append(DuplicateFlag("near_content", pair,
                                 tuple(observations[k].decoded_sha256 for k in pair), distance))
    if distances + exact_cross != equal_pairs:
        raise AdmissionError("incomplete equal-support cross-person coverage")
    counts = (("cross_person_pair_universe", all_pairs),
              ("support_equal_pairs", equal_pairs),
              ("support_different_pairs", all_pairs-equal_pairs),
              ("exact_cross_person_pairs", exact_cross),
              ("distance_pairs", distances),
              ("flagged_groups", len(flags)))
    return ScreenReport(catalogue.domain, catalogue.fingerprint,
                        observations_digest(observations), tuple(exact_groups),
                        tuple(sorted(flags, key=lambda f: f.flag_id)), counts, _SCREEN_SEAL)


@dataclass(frozen=True)
class IdentityConflict:
    """Private known identity conflict from a separately qualified source audit."""
    record_ids: tuple[str, ...]
    source_evidence_digest: str

    def __post_init__(self):
        if any(not isinstance(rid, str) or not rid for rid in self.record_ids):
            raise AdmissionError("identity conflict needs explicit private record IDs")
        object.__setattr__(self, "record_ids", tuple(sorted(self.record_ids)))
        if len(self.record_ids) < 2 or len(set(self.record_ids)) != len(self.record_ids):
            raise AdmissionError("identity conflict needs distinct record group")
        require_sha(self.source_evidence_digest)

    @property
    def flag_id(self):
        return digest(["cross_person_identity_conflict", self.record_ids, self.source_evidence_digest])


@dataclass(frozen=True)
class Adjudication:
    flag_id: str
    disposition: str
    evidence_digest: str
    decision_receipt_digest: str


@dataclass(frozen=True)
class CorpusAssessment:
    """Concrete data checks; never self-authorizes authentic execution/export."""
    domain: str
    catalogue_digest: str
    observations_digest: str
    original_receipts_digest: str
    geometry: Geometry
    screening_digest: str
    adjudications_digest: str
    identity_conflicts_digest: str
    private_ids: tuple[str, ...]
    numeric_checks_passed: bool
    issues: tuple[str, ...]
    external_gates: tuple[str, ...]
    _seal: object = field(repr=False, compare=False)

    @property
    def fingerprint(self):
        self.require_issued()
        return digest([self.domain, self.catalogue_digest, self.observations_digest,
                       self.original_receipts_digest, self.geometry.fingerprint,
                       self.screening_digest, self.adjudications_digest, self.identity_conflicts_digest, self.private_ids,
                       self.numeric_checks_passed, self.issues, self.external_gates])

    def require_issued(self):
        if self._seal is not _ASSESSMENT_SEAL:
            raise AdmissionError("unissued corpus assessment")


def assess_corpus(catalogue: Catalogue, observations: Mapping[str, Observation],
                  original_receipts: Mapping[str, OriginalReceipt], screen: ScreenReport,
                  adjudications: Sequence[Adjudication], *,
                  identity_conflicts: Sequence[IdentityConflict] = ()) -> CorpusAssessment:
    catalogue.require_valid()
    ids = set(catalogue.by_id)
    if set(observations) != ids or set(original_receipts) != ids:
        raise AdmissionError("full receipt/observation set required")
    if screen._seal is not _SCREEN_SEAL or screen.domain != catalogue.domain or screen.catalogue_digest != catalogue.fingerprint:
        raise AdmissionError("screening catalogue binding mismatch")
    obs_digest = observations_digest(observations)
    if obs_digest != screen.observations_digest:
        raise AdmissionError("screening observation binding mismatch")
    geometry = None
    for rid in sorted(ids):
        o, receipt = observations[rid], original_receipts[rid]
        receipt.validate()
        if o._seal is not _OBS_SEAL or o.domain != catalogue.domain or receipt.domain != catalogue.domain or o.record_id != rid or receipt.record_id != rid or o.receipt_digest != receipt.fingerprint:
            raise AdmissionError("original/decoded identity or domain mismatch")
        o.geometry.validate(full=catalogue.domain == SOURCE_DOMAIN)
        if geometry is None:
            geometry = o.geometry
        elif o.geometry != geometry:
            raise AdmissionError("common-grid requirement failed")
    expected_flags = {f.flag_id for f in screen.flags}
    identity_by_flag = {}
    record_map = catalogue.by_id
    for conflict in identity_conflicts:
        if not isinstance(conflict, IdentityConflict) or conflict.flag_id in identity_by_flag:
            raise AdmissionError("duplicate/invalid source identity-conflict group")
        if not set(conflict.record_ids) <= ids or len({record_map[k].person for k in conflict.record_ids}) < 2:
            raise AdmissionError("identity conflict must bind known cross-person source group")
        identity_by_flag[conflict.flag_id] = conflict
    expected_flags.update(identity_by_flag)
    decisions = {}
    issues = []
    for decision in adjudications:
        if not isinstance(decision, Adjudication) or decision.flag_id in decisions or decision.flag_id not in expected_flags:
            raise AdmissionError("adjudication must bind one exact flagged group")
        require_sha(decision.evidence_digest)
        require_sha(decision.decision_receipt_digest)
        if decision.disposition not in ("independent_measurements_confirmed", "cross_person_reuse_confirmed", "unresolved"):
            raise AdmissionError("invalid adjudication disposition")
        decisions[decision.flag_id] = decision
        if decision.disposition != "independent_measurements_confirmed":
            issues.append("unresolved_or_confirmed_cross_person_leakage:"+decision.flag_id)
    for flag in sorted(expected_flags-set(decisions)):
        issues.append("missing_adjudication:"+flag)
    # These bindings require owner-side verification; hashes alone are not proof.
    external = ("original_body_authentication_and_source_authority",
                "qualified_original_to_decoded_converter_and_fidelity",
                "rights_and_redistribution_authority",
                "cross_person_identity_and_adjudication_evidence_authority",
                "process_and_provider_isolation",
                "full_capacity_and_execution_selection")
    return CorpusAssessment(catalogue.domain, catalogue.fingerprint, obs_digest,
        digest([original_receipts[k].fingerprint for k in sorted(ids)]), geometry,
        screen.fingerprint, digest([vars(decisions[k]) for k in sorted(decisions)]),
        digest([[k, identity_by_flag[k].record_ids, identity_by_flag[k].source_evidence_digest]
                for k in sorted(identity_by_flag)]), tuple(sorted(ids)), not issues, tuple(issues), external, _ASSESSMENT_SEAL)
