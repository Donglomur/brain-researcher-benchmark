"""Opaque, allowlisted exports requiring a verified owner-core capability.

Trusted objects are never candidate objects. Only iter_public_files() output may
cross an independently isolated candidate process boundary. No filesystem I/O.
"""
from __future__ import annotations

from array import array
from collections import OrderedDict
from dataclasses import dataclass, field
import hashlib
import hmac
import math
import re
from typing import Mapping, Sequence

from .catalogue import (AdmissionError, Catalogue, SOURCE_DOMAIN, INVENTED_DOMAIN,
                        canonical_json, digest, require_sha, outer_folds)
from .arrays import (CorpusAssessment, Observation, WorkCounter, _snapshot,
                     observations_digest, _real)
from ..core.custody import VerifiedAuthority

_PLAN_SEAL = object()
_FAMILIES = ("ridge", "linear_ovr_svm", "rbf_ovr_svm", "extra_trees", "centroid")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _key(value):
    if type(value) is not bytes or len(value) < 32:
        raise AdmissionError("explicit secret key of at least256 bits required")
    return value


@dataclass(frozen=True)
class ContextSpec:
    outer_person: str
    arm: str
    condition: str
    repetition: int
    nonce: str

    def validate(self):
        if not isinstance(self.outer_person, str) or not self.outer_person or self.arm not in ("F", "I") or self.condition not in ("original", "spatial_scrambled", "C_only"):
            raise AdmissionError("invalid context role/condition")
        if type(self.repetition) is not int or self.repetition not in range(3):
            raise AdmissionError("exact three-repetition schedule required")
        if not isinstance(self.nonce, str) or not _HEX64.fullmatch(self.nonce):
            raise AdmissionError("context nonce must be a committed opaque256-bit token")

    @property
    def fingerprint(self):
        self.validate()
        return digest(["n073-export-context-v1", self.outer_person, self.arm,
                       self.condition, self.repetition, self.nonce])


@dataclass(frozen=True)
class ExportPlan:
    """PRIVATE: never serialize this object to a candidate."""
    domain: str
    assessment_digest: str
    catalogue_digest: str
    context: ContextSpec
    training_map: tuple[tuple[str, str, int, str], ...]
    query_map: tuple[tuple[str, str, int], ...]
    label_order: tuple[str, ...]
    descriptors_digest: str
    scramble_bank_commitment: str | None
    _seal: object = field(repr=False, compare=False)

    @property
    def case_allowlist_digest(self):
        return digest({"training": [row[0] for row in self.training_map],
                       "query": [row[0] for row in self.query_map]})

    @property
    def authority_domain(self):
        return "authentic" if self.domain == SOURCE_DOMAIN else "invented"

    @property
    def bindings(self):
        result = {"assessment_digest": self.assessment_digest,
                  "context_digest": self.context.fingerprint,
                  "case_allowlist_digest": self.case_allowlist_digest,
                  "descriptors_digest": self.descriptors_digest}
        if self.scramble_bank_commitment is not None:
            result["scramble_bank_commitment"] = self.scramble_bank_commitment
        return result

    def private_evaluation_key(self):
        self.require_issued()
        return {case_id: {"record_id": rid, "label": label}
                for case_id, rid, label in self.query_map}

    def require_issued(self):
        if self._seal is not _PLAN_SEAL:
            raise AdmissionError("unissued export plan")


def prepare_context(catalogue: Catalogue, assessment: CorpusAssessment,
                    context: ContextSpec, export_key: bytes,
                    original_descriptors: Mapping[str, OriginalDescriptor],
                    *, scramble_bank_commitment: str | None = None) -> ExportPlan:
    """Plan opaque IDs before signing; this does not release data/labels."""
    catalogue.require_valid()
    assessment.require_issued()
    context.validate()
    _key(export_key)
    if not assessment.numeric_checks_passed or assessment.issues:
        raise AdmissionError("unresolved data/duplicate findings block export planning")
    if assessment.domain != catalogue.domain or assessment.catalogue_digest != catalogue.fingerprint:
        raise AdmissionError("assessment/catalogue mismatch")
    if set(assessment.private_ids) != set(catalogue.by_id):
        raise AdmissionError("incomplete assessment record set")
    if set(original_descriptors) != set(assessment.private_ids):
        raise AdmissionError("complete original-descriptor mapping required")
    descriptor_binding = descriptors_digest(original_descriptors)
    if context.condition == "spatial_scrambled":
        require_sha(scramble_bank_commitment)
    elif scramble_bank_commitment is not None:
        raise AdmissionError("non-scrambled context cannot bind a scramble bank")
    folds = {f.outer_person: f for f in outer_folds(catalogue)}
    if context.outer_person not in folds:
        raise AdmissionError("unknown outer person")
    fold, records = folds[context.outer_person], catalogue.by_id
    def opaque(kind, value):
        return hmac.new(export_key, canonical_json(["n073-opaque-v1", kind,
                       context.fingerprint, value]), hashlib.sha256).hexdigest()
    case_ids = {rid: opaque("case", rid) for rid in records}
    if len(set(case_ids.values())) != len(records):
        raise AdmissionError("opaque case-ID collision")
    groups = {p: opaque("group", p) for p in catalogue.people if p != context.outer_person}
    if len(set(groups.values())) != len(groups):
        raise AdmissionError("opaque group-ID collision")
    def order(ids, kind):
        pairs = [(opaque(kind, rid), rid) for rid in ids]
        if len({key for key, rid in pairs}) != len(pairs):
            raise AdmissionError("opaque order collision")
        return [rid for key, rid in sorted(pairs)]
    train = tuple((case_ids[rid], rid, records[rid].label, groups[records[rid].person])
                  for rid in order(fold.training_ids, "training-order"))
    query = tuple((case_ids[rid], rid, records[rid].label)
                  for rid in order(fold.query_ids, "query-order"))
    return ExportPlan(catalogue.domain, assessment.fingerprint, catalogue.fingerprint,
                      context, train, query, catalogue.label_order, descriptor_binding,
                      scramble_bank_commitment, _PLAN_SEAL)


@dataclass(frozen=True)
class OriginalDescriptor:
    """Trusted linkage to a descriptor actually computed by transforms.c_descriptor.

    This binding alone does not prove its numeric producer; the owner must call
    the pinned qualified transform on the original array. No C computation is
    replaced by this record or by a claimed metadata value.
    """
    record_id: str
    original_decoded_sha256: str
    producer_contract_digest: str
    values: tuple[float, ...]

    def __post_init__(self):
        object.__setattr__(self, "values", tuple(_real(v) for v in self.values))
        require_sha(self.original_decoded_sha256)
        require_sha(self.producer_contract_digest)
        if not self.record_id or len(self.values) != 105:
            raise AdmissionError("exact original C105 descriptor required")

    def validate(self, observation: Observation):
        if self.record_id != observation.record_id or self.original_decoded_sha256 != observation.decoded_sha256:
            raise AdmissionError("C must bind to the original decoded array")
        require_sha(self.producer_contract_digest)
        if len(self.values) != 105:
            raise AdmissionError("exact C105 descriptor required")
        tuple(_real(v) for v in self.values)


def descriptors_digest(descriptors: Mapping[str, OriginalDescriptor]):
    rows = []
    for rid in sorted(descriptors):
        value = descriptors[rid]
        if not isinstance(value, OriginalDescriptor) or value.record_id != rid:
            raise AdmissionError("descriptor ID/type mismatch")
        rows.append([rid, value.original_decoded_sha256, value.producer_contract_digest, value.values])
    return digest(rows)


class ScrambleBank:
    """Evaluator-secret per-map/per-outer bijections, shared across F/I/reps.

    Different outer token -> different stream. Arm/repetition is intentionally
    absent from the permutation key. No inverse/index/key enters public files.
    """
    __slots__ = ("outer_person", "outer_token", "_key", "_cache_limit_bytes",
                 "_cache", "_cache_bytes", "_cache_peak", "_cache_hits", "_generated")

    def __init__(self, *, outer_person: str, outer_token: str, key: bytes, cache_limit_bytes: int = 0):
        if not isinstance(outer_person, str) or not outer_person or not isinstance(outer_token, str) or not _HEX64.fullmatch(outer_token):
            raise AdmissionError("opaque outer-bank token required")
        object.__setattr__(self, "outer_person", outer_person)
        object.__setattr__(self, "outer_token", outer_token)
        object.__setattr__(self, "_key", bytes(_key(key)))
        if type(cache_limit_bytes) is not int or cache_limit_bytes < 0:
            raise AdmissionError("nonnegative explicit retained-payload cache cap required")
        object.__setattr__(self, "_cache_limit_bytes", cache_limit_bytes)
        object.__setattr__(self, "_cache", OrderedDict())
        object.__setattr__(self, "_cache_bytes", 0)
        object.__setattr__(self, "_cache_peak", 0)
        object.__setattr__(self, "_cache_hits", 0)
        object.__setattr__(self, "_generated", 0)

    def __setattr__(self, name, value):
        raise AdmissionError("committed scramble bank is immutable")

    @property
    def commitment(self):
        return hashlib.sha256(canonical_json(["n073-scramble-commit-v1", self.outer_token,
                               hashlib.sha256(self._key).hexdigest()])).hexdigest()

    def _indices(self, n: int, record_id: str):
        seed = canonical_json(["n073-spatial-bijection-v1", self.outer_token, record_id, n])
        counter = 0
        def randbelow(bound):
            nonlocal counter
            cutoff = (1 << 64)-((1 << 64) % bound)
            for unused in range(128):
                word = int.from_bytes(hmac.new(self._key, seed+b"|"+str(counter).encode("ascii"),
                                               hashlib.sha256).digest()[:8], "big")
                counter += 1
                if word < cutoff:
                    return word % bound
            raise AdmissionError("bounded unbiased RNG rejection exhausted")
        code, width = ("I", 4) if n < (1 << 32) else ("Q", 8)
        indices = array(code, range(n))
        if indices.itemsize != width:
            raise AdmissionError("qualified compact index width unavailable")
        for j in range(n-1, 0, -1):
            k = randbelow(j+1)
            indices[j], indices[k] = indices[k], indices[j]
        return indices

    @property
    def cache_info(self):
        return {"retained_payload_limit_bytes": self._cache_limit_bytes,
                "retained_payload_bytes": self._cache_bytes,
                "peak_retained_payload_bytes": self._cache_peak,
                "retained_entries": len(self._cache), "hit_records": self._cache_hits,
                "generated_records": self._generated,
                "scope": "one immutable bank; payload cap excludes Python index/object overhead and active permutation workspace"}

    def clear_cache(self, work: WorkCounter | None = None):
        if work is not None:
            work.cache_evicted_value_bytes += self._cache_bytes
        self._cache.clear()
        object.__setattr__(self, "_cache_bytes", 0)

    def transform_bytes(self, record_id: str, original: bytes, work: WorkCounter):
        if not isinstance(record_id, str) or not record_id:
            raise AdmissionError("explicit record ID required")
        if type(original) is not bytes or not original or len(original) % 8:
            raise AdmissionError("nonempty canonical full float64 bytes required")
        # Authenticate exact source content and immutable bank identity on every
        # invocation, including hits. No caller can restore/populate cache data.
        cache_key = (record_id, hashlib.sha256(original).hexdigest(), self.commitment)
        work.cache_lookup_input_bytes += len(original)
        if cache_key in self._cache:
            output = self._cache.pop(cache_key)
            self._cache[cache_key] = output
            object.__setattr__(self, "_cache_hits", self._cache_hits+1)
            work.cache_hit_records += 1
            work.cache_hit_value_bytes += len(output)
            return output
        n = len(original)//8
        indices = self._indices(n, record_id)
        output = bytearray(len(original))
        for j, source in enumerate(indices):
            output[8*j:8*j+8] = original[8*source:8*source+8]
        work.permutation_records += 1
        work.permutation_positions += n
        work.permutation_index_bytes += n*(4 if n < (1 << 32) else 8)
        work.snapshot_bytes_materialized += len(output)
        object.__setattr__(self, "_generated", self._generated+1)
        result = bytes(output)
        # Capacity is tested before retaining a value. Too-large records remain
        # uncached; no partial/cropped value enters this bank.
        if self._cache_limit_bytes and len(result) <= self._cache_limit_bytes:
            while self._cache_bytes+len(result) > self._cache_limit_bytes:
                unused_key, evicted = self._cache.popitem(last=False)
                object.__setattr__(self, "_cache_bytes", self._cache_bytes-len(evicted))
                work.cache_evicted_value_bytes += len(evicted)
            self._cache[cache_key] = result
            object.__setattr__(self, "_cache_bytes", self._cache_bytes+len(result))
            object.__setattr__(self, "_cache_peak", max(self._cache_peak, self._cache_bytes))
            work.cache_admitted_value_bytes += len(result)
        return result


def eligible_tool_names(condition: str):
    if condition not in ("original", "spatial_scrambled", "C_only"):
        raise AdmissionError("unknown condition")
    views = ("C",) if condition == "C_only" else ("N", "C", "NC")
    return tuple(view+":"+family for view in views for family in _FAMILIES)


@dataclass(frozen=True)
class PublicArtifact:
    relative_name: str
    body: bytes
    media_type: str


class CandidateExport:
    """Trusted-host materializer, not a candidate-visible object.

    The owner provides actual eligible model tools separately and enforces the
    signed tool/isolation gates; these names are only the required inventory.
    """
    def __init__(self, *, plan: ExportPlan, assessment: CorpusAssessment,
                 observations: Mapping[str, Observation],
                 original_descriptors: Mapping[str, OriginalDescriptor],
                 values_by_id: Mapping[str, Sequence[float]] | None,
                 authority: VerifiedAuthority, scramble_bank: ScrambleBank | None = None,
                 work: WorkCounter | None = None):
        plan.require_issued()
        assessment.require_issued()
        if not isinstance(authority, VerifiedAuthority):
            raise AdmissionError("verified owner-core export authority required")
        authority.require(role="export", domain=plan.authority_domain, bindings=plan.bindings)
        if assessment.fingerprint != plan.assessment_digest or not assessment.numeric_checks_passed:
            raise AdmissionError("wrong/unqualified numeric assessment")
        if observations_digest(observations) != assessment.observations_digest:
            raise AdmissionError("observation set changed after assessment")
        all_ids = {r[1] for r in plan.training_map}|{r[1] for r in plan.query_map}
        if set(observations) != all_ids or set(original_descriptors) != all_ids:
            raise AdmissionError("complete observations/original C required")
        if descriptors_digest(original_descriptors) != plan.descriptors_digest:
            raise AdmissionError("descriptor values/source bindings changed after signing")
        for rid in sorted(all_ids):
            original_descriptors[rid].validate(observations[rid])
        condition = plan.context.condition
        if condition == "C_only":
            if values_by_id is not None or scramble_bank is not None:
                raise AdmissionError("C-only export must not hold a neural mapping/bank")
        else:
            if values_by_id is None or set(values_by_id) != all_ids:
                raise AdmissionError("full original numeric mapping required")
            if condition == "spatial_scrambled":
                if (not isinstance(scramble_bank, ScrambleBank) or scramble_bank.outer_person != plan.context.outer_person
                    or scramble_bank.commitment != plan.scramble_bank_commitment):
                    raise AdmissionError("correct private outer scramble bank required")
            elif scramble_bank is not None:
                raise AdmissionError("unexpected scramble bank in original condition")
        self._plan, self._assessment, self._observations = plan, assessment, observations
        # Copy only private metadata maps; immutable descriptor/observation values
        # prevent caller alias mutation. Neural values are revalidated on each read.
        self._observations = dict(observations)
        self._descriptors, self._values, self._bank = dict(original_descriptors), values_by_id, scramble_bank
        self.work = WorkCounter() if work is None else work
        self._used = False

    def iter_public_files(self):
        """One-pass allowlisted byte artifacts; no private manifest serialization."""
        if self._used:
            raise AdmissionError("export materialization is single-use; regeneration must be charged explicitly")
        self._used = True
        plan = self._plan
        neural = plan.context.condition != "C_only"
        interface = {"schema": "n073-candidate-export-v1", "execution_domain": plan.authority_domain,
                     "arm": plan.context.arm, "condition": plan.context.condition,
                     "label_order": list(plan.label_order),
                     "query_is_one_held_person": True,
                     "allowed_cardinality_side_information": True,
                     "training_rows": len(plan.training_map), "query_rows": len(plan.query_map),
                     "required_tools": list(eligible_tool_names(plan.context.condition))}
        yield PublicArtifact("interface.json", canonical_json(interface)+b"\n", "application/json")
        if neural:
            yield PublicArtifact("geometry.json", canonical_json(self._assessment.geometry.public_descriptor())+b"\n", "application/json")
        for role, entries in (("training", plan.training_map), ("query", plan.query_map)):
            lines = []
            for entry in entries:
                case_id, rid = entry[0], entry[1]
                c = self._descriptors[rid]
                c.validate(self._observations[rid])
                row = {"case_id": case_id, "C": [float(v) for v in c.values]}
                if role == "training":
                    row["label_index"], row["person_group"] = entry[2], entry[3]
                if neural:
                    raw = _snapshot(self._observations[rid], self._values[rid], self.work)
                    if self._bank is not None:
                        raw = self._bank.transform_bytes(rid, raw, self.work)
                    filename = "arrays/"+case_id+".f64"
                    row["array_file"] = filename
                    yield PublicArtifact(filename, raw, "application/octet-stream")
                lines.append(canonical_json(row)+b"\n")
            yield PublicArtifact(role+".jsonl", b"".join(lines), "application/x-ndjson")
