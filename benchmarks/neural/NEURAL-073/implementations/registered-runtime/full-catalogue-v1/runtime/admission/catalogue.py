"""Authenticated catalogue metadata and whole-person split construction.

No I/O or discovery: callers explicitly supply frozen metadata bytes. Candidate
processes must never receive these private objects or their serialization.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import json
from typing import Mapping, Sequence

SOURCE_DOMAIN = "n073-full-declared-catalogue-v1"
INVENTED_DOMAIN = "n073-invented-control-v1"
PIN_DOCUMENT = (3260, "2ba089e7057097298df3cecf63fb6b63b024754bd03fc641079d829e6c38dba1")
SUPPORT_DOCUMENT = (57956, "51339ee2c7bce1c4dd293b695a3ce68fd123b6f65e1f4ffde7dcb8bfc105169b")
_SEAL = object()


class AdmissionError(ValueError):
    """An admission requirement failed; never silently drop a record."""


def canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def require_sha(value: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise AdmissionError("expected lowercase SHA-256")
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AdmissionError("duplicate JSON key")
        result[key] = value
    return result


def strict_json(raw: bytes):
    if not isinstance(raw, bytes):
        raise AdmissionError("metadata must be explicit immutable bytes")
    def bad_constant(value):
        raise AdmissionError("nonfinite JSON token")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=bad_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AdmissionError("invalid UTF-8 JSON") from exc


def _authenticate(raw: bytes, expected: tuple[int, str]) -> None:
    if not isinstance(raw, bytes) or len(raw) != expected[0] or hashlib.sha256(raw).hexdigest() != expected[1]:
        raise AdmissionError("frozen metadata pin mismatch")


@dataclass(frozen=True)
class Record:
    record_id: str
    person: str
    label: int
    protocol: str
    construction: str
    session: str
    source_name: str
    advertised_bytes: int

    def private_identity(self):
        return [self.record_id, self.person, self.label, self.protocol,
                self.construction, self.session, self.source_name, self.advertised_bytes]


class Catalogue:
    """Factory-issued immutable private metadata; no mutable alias or replace()."""
    __slots__ = ("domain", "records", "label_order", "people", "source_binding", "_seal", "_fingerprint")

    def __init__(self, domain, records, label_order, people, source_binding, seal):
        if seal is not _SEAL or domain not in (SOURCE_DOMAIN, INVENTED_DOMAIN):
            raise AdmissionError("catalogue must be issued by its metadata factory")
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "records", tuple(records))
        object.__setattr__(self, "label_order", tuple(label_order))
        object.__setattr__(self, "people", tuple(people))
        object.__setattr__(self, "source_binding", source_binding)
        object.__setattr__(self, "_seal", seal)
        object.__setattr__(self, "_fingerprint", digest([domain, source_binding, self.label_order,
                         [r.private_identity() for r in self.records]]))

    def __setattr__(self, name, value):
        raise AdmissionError("issued catalogue is immutable")

    def require_valid(self):
        if self._seal is not _SEAL:
            raise AdmissionError("catalogue was not constructed by the authenticated parser")

    @property
    def fingerprint(self):
        self.require_valid()
        return self._fingerprint

    @property
    def by_id(self):
        self.require_valid()
        return {r.record_id: r for r in self.records}

    @property
    def cell_counts(self):
        return Counter((r.person, r.label) for r in self.records)


def _validate_rows(records, labels, *, invented=False):
    if not records or not labels or any(not isinstance(v, str) or not v for v in labels) or len(set(labels)) != len(labels):
        raise AdmissionError("empty or duplicated ontology")
    ids = set()
    for r in records:
        if not isinstance(r, Record) or any(not isinstance(getattr(r, name), str) for name in ("record_id", "person", "protocol", "construction", "session", "source_name")):
            raise AdmissionError("record text fields must be immutable strings")
        if r.record_id in ids or not r.record_id:
            raise AdmissionError("duplicate/invalid private record ID")
        ids.add(r.record_id)
        if type(r.label) is not int or not 0 <= r.label < len(labels) or r.protocol != labels[r.label]:
            raise AdmissionError("record ontology mismatch")
        if not r.person or not r.construction or not isinstance(r.session, str):
            raise AdmissionError("missing record provenance metadata")
        if type(r.advertised_bytes) is not int or r.advertised_bytes < 0:
            raise AdmissionError("invalid advertised size")
        if invented and (not r.record_id.startswith("invented:") or not r.person.startswith("invented-person:")):
            raise AdmissionError("invented fixture identity domain required")


def catalogue_from_pages(page_bytes: Mapping[str, bytes], pin_document: bytes,
                         support_document: bytes) -> Catalogue:
    """Authenticate all twelve exact held pages and complete 9532/13/25 support.

    This establishes metadata identity only; it never admits a neural array.
    """
    _authenticate(pin_document, PIN_DOCUMENT)
    _authenticate(support_document, SUPPORT_DOCUMENT)
    pins, support = strict_json(pin_document), strict_json(support_document)
    entries = pins["pages"]
    if len(entries) != 12 or set(page_bytes) != {p["path"] for p in entries}:
        raise AdmissionError("exact twelve-page set required")
    labels = tuple(support["label_order"])
    records = []
    for p in entries:
        raw = page_bytes[p["path"]]
        _authenticate(raw, (p["bytes"], p["sha256"]))
        document = strict_json(raw)
        for row in document["rows"]:
            if type(row["id"]) is not int or row["id"] <= 0:
                raise AdmissionError("invalid source image ID")
            if row["task"] not in labels:
                raise AdmissionError("unknown declared label")
            records.append(Record(str(row["id"]), row["subject"],
                                  labels.index(row["task"]), row["task"],
                                  row["construction"], row["session"], row["name"],
                                  row["advertised_bytes"]))
    _validate_rows(records, labels)
    people = tuple(sorted({r.person for r in records}))
    counts = Counter((r.person, r.protocol) for r in records)
    expected = {(c["person"], c["protocol"]): c["n_records"] for c in support["cells"]}
    if len(records) != 9532 or len(people) != 13 or len(labels) != 25 or len(counts) != 300:
        raise AdmissionError("full 9532/13/25/300 scope required")
    if counts != expected or people != tuple(support["people"]):
        raise AdmissionError("available person/protocol support mismatch")
    if dict(Counter(r.person for r in records)) != support["person_rows"]:
        raise AdmissionError("person record support mismatch")
    if dict(Counter(r.construction for r in records)) != support["construction_counts"]:
        raise AdmissionError("construction support mismatch")
    if sum(r.advertised_bytes for r in records) != support["advertised_compressed_bytes"]:
        raise AdmissionError("advertised size sum mismatch")
    binding = digest([PIN_DOCUMENT, SUPPORT_DOCUMENT, entries])
    result = Catalogue(SOURCE_DOMAIN, tuple(sorted(records, key=lambda r: int(r.record_id))),
                       labels, people, binding, _SEAL)
    # Full fold eligibility is enforced now rather than assumed from global counts.
    tuple(outer_folds(result))
    return result


def invented_catalogue(records: Sequence[Record], labels: Sequence[str]) -> Catalogue:
    """Explicitly marked tiny controls; cannot acquire SOURCE_DOMAIN."""
    records, labels = tuple(records), tuple(labels)
    _validate_rows(records, labels, invented=True)
    people = tuple(sorted({r.person for r in records}))
    if len(people) < 3:
        raise AdmissionError("invented split controls need at least three people")
    return Catalogue(INVENTED_DOMAIN, records, labels, people,
                     digest(["invented-only", [r.private_identity() for r in records]]), _SEAL)


@dataclass(frozen=True)
class InnerFold:
    validation_person: str
    fit_ids: tuple[str, ...]
    validation_ids: tuple[str, ...]


@dataclass(frozen=True)
class OuterFold:
    outer_person: str
    training_ids: tuple[str, ...]
    query_ids: tuple[str, ...]
    inner: tuple[InnerFold, ...]


def outer_folds(catalogue: Catalogue):
    catalogue.require_valid()
    expected_labels = set(range(len(catalogue.label_order)))
    for held in catalogue.people:
        train = tuple(r for r in catalogue.records if r.person != held)
        query = tuple(r.record_id for r in catalogue.records if r.person == held)
        if {r.label for r in train} != expected_labels or not query:
            raise AdmissionError("outer training lacks fixed ontology support")
        inner = []
        for validation in catalogue.people:
            if validation == held:
                continue
            fit = tuple(r for r in train if r.person != validation)
            valid_ids = tuple(r.record_id for r in train if r.person == validation)
            if {r.label for r in fit} != expected_labels or not valid_ids:
                raise AdmissionError("inner training lacks fixed ontology support")
            inner.append(InnerFold(validation, tuple(r.record_id for r in fit), valid_ids))
        if catalogue.domain == SOURCE_DOMAIN and (len(inner) != 12 or len(catalogue.people) != 13):
            raise AdmissionError("full 13 outer/12 inner support required")
        yield OuterFold(held, tuple(r.record_id for r in train), query, tuple(inner))


def weights(catalogue: Catalogue, people: Sequence[str] | None = None):
    """Exact person/protocol/record fractions for complete selected people."""
    catalogue.require_valid()
    selected = tuple(catalogue.people if people is None else people)
    if not selected or len(selected) != len(set(selected)) or not set(selected) <= set(catalogue.people):
        raise AdmissionError("invalid complete-person roster")
    counts = catalogue.cell_counts
    m = Counter(person for person, label in counts)
    return {r.record_id: Fraction(1, len(selected) * m[r.person] * counts[(r.person, r.label)])
            for r in catalogue.records if r.person in selected}
