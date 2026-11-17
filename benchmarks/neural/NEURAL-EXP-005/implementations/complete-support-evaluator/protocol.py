"""Normalized, assessor-owned Helsinki support and causal input contract.

This module does not read EDFs, authenticate annotations, train models or enforce
process isolation. Those qualifications remain external admission requirements.
"""

from copy import deepcopy
import hashlib
import hmac
import json
import math

PROTOCOL = "helsinki_full_timestamp_quality_flags_v1"
SOURCE_VERSION = "zenodo:4940267-v4"
DESCRIPTION_SCHEMA = "helsinki-complete-support-description-v1"
REFERENCE_SCHEMA = "helsinki-complete-support-reference-v1"
MONTAGE = (
    "Fp2-F4", "F4-C4", "C4-P4", "P4-O2", "Fp1-F3", "F3-C3",
    "C3-P3", "P3-O1", "Fp2-F8", "F8-T4", "T4-T6", "T6-O2",
    "Fp1-F7", "F7-T3", "T3-T5", "T5-O1", "Fz-Cz", "Cz-Pz",
)
STRATA = ("no_flagged_context", "earlier_context_flagged", "final_second_flagged")
_DESCRIPTOR_FIELDS = {
    "schema", "assessment_id", "protocol_id", "source_version", "fold_seed",
    "representation_sha256", "detector_sha256", "source_admission_sha256",
    "montage", "development_by_fold", "recordings",
}
_RECORD_FIELDS = {
    "recording_id", "eeg_sha256", "sample_rate", "sample_count",
    "sample_zero_annotation_second", "units", "labels", "quality_flags",
}


class ContractError(ValueError):
    """Invalid or incomplete support; no full primary score may be reported."""


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _fields(value, expected, name):
    if not isinstance(value, dict) or set(value) != expected:
        raise ContractError(f"{name}: exact fields required: {sorted(expected)}")


def _text(value, name):
    if not isinstance(value, str) or not value or len(value) > 256:
        raise ContractError(f"{name}: nonempty string of at most 256 characters required")


def _sha(value, name):
    if (not isinstance(value, str) or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)):
        raise ContractError(f"{name}: lowercase SHA256 required")


def _positive_int(value, name):
    if type(value) is not int or value <= 0:
        raise ContractError(f"{name}: positive integer required")


def _finite(value, name):
    if type(value) not in (int, float):
        raise ContractError(f"{name}: finite number required; booleans are not numbers")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ContractError(f"{name}: finite number required")


def fold_map(record_ids, seed):
    """Versioned prospective choice: hash order, then five round-robin folds.

    Seed and admitted infant-to-recording mapping must be frozen before outcomes.
    This does not assert that any authentic fold assignment has been admitted.
    """
    _text(seed, "fold_seed")
    ids = list(record_ids)
    for rid in ids:
        _text(rid, "recording_id")
    if len(ids) != 79 or len(set(ids)) != 79:
        raise ContractError("exactly 79 unique admitted infant recordings required")
    ordered = sorted(ids, key=lambda rid: (digest([seed, rid]), rid))
    return {rid: index % 5 for index, rid in enumerate(ordered)}


def _validate_description(document):
    _fields(document, _DESCRIPTOR_FIELDS, "description")
    if document["schema"] != DESCRIPTION_SCHEMA:
        raise ContractError("wrong description schema")
    if document["protocol_id"] != PROTOCOL or document["source_version"] != SOURCE_VERSION:
        raise ContractError("wrong source version or active protocol")
    _text(document["assessment_id"], "assessment_id")
    for name in ("representation_sha256", "detector_sha256", "source_admission_sha256"):
        _sha(document[name], name)
    if document["montage"] != list(MONTAGE):
        raise ContractError("the pinned ordered 18-bipolar montage is required")
    records = document["recordings"]
    if not isinstance(records, list) or len(records) != 79:
        raise ContractError("all 79 recordings required")
    by_id = {}
    for record in records:
        _fields(record, _RECORD_FIELDS, "recording")
        rid = record["recording_id"]
        _text(rid, "recording_id")
        if rid in by_id:
            raise ContractError("duplicate recording identity")
        _sha(record["eeg_sha256"], "eeg_sha256")
        rate = record["sample_rate"]
        _fields(rate, {"num", "den"}, "sample_rate")
        for name in ("num", "den"):
            _positive_int(rate[name], "sample_rate." + name)
        if math.gcd(rate["num"], rate["den"]) != 1:
            raise ContractError("sample rate must be a reduced rational")
        _positive_int(record["sample_count"], "sample_count")
        origin = record["sample_zero_annotation_second"]
        if type(origin) is not int or origin != 0:
            raise ContractError("sample zero must be authenticated at annotation second zero")
        if record["units"] not in ("uV", "mV", "V", "digital_count"):
            raise ContractError("explicit calibrated or stored units required")
        seconds = record["sample_count"] * rate["den"] // rate["num"]
        if seconds < 30:
            raise ContractError("an infant without primary support holds the full 79-infant score")
        labels = record["labels"]
        if not isinstance(labels, list) or len(labels) != 3:
            raise ContractError("three original aligned expert streams required")
        for stream in labels:
            if (not isinstance(stream, list) or len(stream) != seconds
                    or any(type(x) is not int or x not in (0, 1) for x in stream)):
                raise ContractError("each expert stream must cover every complete second with binary integers")
        flags = record["quality_flags"]
        if (not isinstance(flags, list) or len(flags) != seconds
                or any(type(x) is not bool for x in flags)):
            raise ContractError("original input flags must cover every complete second")
        by_id[rid] = record
    folds = fold_map(by_id, document["fold_seed"])
    development = document["development_by_fold"]
    _fields(development, {str(f) for f in range(5)}, "development_by_fold")
    for fold in range(5):
        dev = development[str(fold)]
        if not isinstance(dev, list) or not dev or any(not isinstance(x, str) for x in dev):
            raise ContractError("every fold needs nonempty development infant IDs")
        if len(set(dev)) != len(dev) or any(rid not in by_id or folds[rid] == fold for rid in dev):
            raise ContractError("development must be unique, admitted, non-held infants")
        if not (set(by_id) - {rid for rid, f in folds.items() if f == fold} - set(dev)):
            raise ContractError("every fold needs fitting infants separate from development and held infants")
    return by_id, folds


def _validate_key(case_key):
    if not isinstance(case_key, bytes) or len(case_key) < 32:
        raise ContractError("use an assessor-private random case key of at least 32 bytes")


class Reference:
    """Snapshot of a fully bound assessor reference; never pass it to candidates."""

    def __init__(self, document, case_key):
        _validate_key(case_key)
        document = deepcopy(document)
        _fields(document, _DESCRIPTOR_FIELDS | {"input_sha256_by_recording", "case_key_commitment"}, "reference")
        if document["schema"] != REFERENCE_SCHEMA:
            raise ContractError("wrong reference schema")
        if document["case_key_commitment"] != hashlib.sha256(case_key).hexdigest():
            raise ContractError("wrong assessor case key")
        description = {key: value for key, value in document.items() if key in _DESCRIPTOR_FIELDS}
        description["schema"] = DESCRIPTION_SCHEMA
        records, folds = _validate_description(description)
        bindings = document["input_sha256_by_recording"]
        _fields(bindings, set(records), "input_sha256_by_recording")
        for rid, record in records.items():
            hashes = bindings[rid]
            if not isinstance(hashes, list) or len(hashes) != _seconds(record) - 29:
                raise ContractError("every primary timestamp needs one frozen input hash")
            for value in hashes:
                _sha(value, "input_sha256")
        self._document, self._records, self._folds = document, records, folds
        self._case_key = case_key
        self.reference_sha256 = digest(document)

    @property
    def document(self):
        return deepcopy(self._document)

    def record_ids(self):
        return tuple(sorted(self._records))

    def record(self, recording_id):
        try:
            return deepcopy(self._records[recording_id])
        except KeyError as exc:
            raise ContractError("unknown assessor recording") from exc

    def partition(self, fold):
        if type(fold) is not int or fold not in range(5):
            raise ContractError("fold must be an integer from 0 through 4")
        held = [rid for rid in self.record_ids() if self._folds[rid] == fold]
        dev = sorted(self._document["development_by_fold"][str(fold)])
        train = sorted(set(self._records) - set(held) - set(dev))
        return {"fit": train, "development": dev, "held": held}

    def case_rows(self):
        """Expected submission order, private to the assessor/coordinator."""
        for rid in self.record_ids():
            for k in range(29, _seconds(self._records[rid])):
                row = _binding(self._document, self._case_key, rid, k, self._folds[rid])
                row["input_sha256"] = self._document["input_sha256_by_recording"][rid][k - 29]
                yield row


def _seconds(record):
    return record["sample_count"] * record["sample_rate"]["den"] // record["sample_rate"]["num"]


def _binding(description, case_key, rid, k, fold):
    identity = [description["assessment_id"], PROTOCOL,
                description["representation_sha256"], rid, k]
    return {
        "case_id": hmac.new(case_key, canonical_bytes(identity), hashlib.sha256).hexdigest(),
        "assessment_id": description["assessment_id"], "protocol_id": PROTOCOL,
        "representation_sha256": description["representation_sha256"], "fold": fold,
    }


def _payload(description, case_key, record, k, fold, read_samples):
    if type(k) is not int or k not in range(29, _seconds(record)):
        raise ContractError("timestamp outside exact primary support")
    rate = record["sample_rate"]
    num, den = rate["num"], rate["den"]
    start = ((k - 29) * num + den - 1) // den
    stop = ((k + 1) * num + den - 1) // den
    values = read_samples(record["recording_id"], start, stop)
    if not isinstance(values, (list, tuple)) or len(values) != stop - start:
        raise ContractError("reader must return exactly the requested causal sample interval")
    samples = []
    for row in values:
        if not isinstance(row, (list, tuple)) or len(row) != 18:
            raise ContractError("every sample needs exactly the ordered 18 bipolar values")
        for value in row:
            _finite(value, "EEG sample")
        samples.append(list(row))
    result = _binding(description, case_key, record["recording_id"], k, fold)
    result.update({
        "schema": "helsinki-causal-packet-v1", "montage": list(MONTAGE),
        "units": record["units"], "duration_seconds": 30,
        "prediction_interval_seconds": [29, 30],
        "sample_clock": {"first_tick": start * den - (k - 29) * num,
                         "step_ticks": den, "ticks_per_second": num},
        "samples": samples,
        "quality_flags": record["quality_flags"][k - 29:k + 1],
        "detector_sha256": description["detector_sha256"],
    })
    return result


def prepare_reference(description, read_samples, case_key):
    """Construction step: freeze all public packet hashes before predictions.

    The caller supplies an authenticated normalized source reader. Hashing proves
    subsequent byte consistency, not EDF authenticity, calibration or alignment.
    The private labels are not used to construct any candidate-visible bytes.
    """
    _validate_key(case_key)
    description = deepcopy(description)
    records, folds = _validate_description(description)
    hashes = {}
    for rid in sorted(records):
        record = records[rid]
        hashes[rid] = [digest(_payload(description, case_key, record, k, folds[rid], read_samples))
                       for k in range(29, _seconds(record))]
    document = deepcopy(description)
    document.update(schema=REFERENCE_SCHEMA, input_sha256_by_recording=hashes,
                    case_key_commitment=hashlib.sha256(case_key).hexdigest())
    return Reference(document, case_key)


def packet(reference, recording_id, k, read_samples):
    """Return one target-free causal packet only if its frozen binding matches."""
    if recording_id not in reference._records:
        raise ContractError("unknown assessor recording")
    body = _payload(reference._document, reference._case_key,
                    reference._records[recording_id], k,
                    reference._folds[recording_id], read_samples)
    actual = digest(body)
    if actual != reference._document["input_sha256_by_recording"][recording_id][k - 29]:
        raise ContractError("packet differs from the frozen original-input binding")
    return dict(body, input_sha256=actual)


def stratum(flags, k):
    if flags[k]:
        return STRATA[2]
    return STRATA[1] if any(flags[k - 29:k]) else STRATA[0]
