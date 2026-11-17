"""Trusted Helsinki EDF admission, lazy calibrated samples and private coverage.

This is an owner-side data path. Its source handles and labels must never enter
the participant process. No downloader, learner or model client is supplied.
"""
from __future__ import annotations

import argparse
from collections import OrderedDict
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct
import sys

from source_loader import SourceError, load_sources

FS = 256
MAX_WINDOW_SAMPLES = FS * 30
COORDINATE = "author_exported_record_sample_grid_v1"
RECORD_IDS = tuple("eeg" + str(i) for i in range(1, 80))
HERE = Path(__file__).resolve().parent


def require(condition, reason):
    if not condition:
        raise SourceError(reason)


def canonical(document):
    try:
        return json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise SourceError("document is not finite canonical JSON") from exc


def digest(document):
    return hashlib.sha256(canonical(document)).hexdigest()


def bounded_json(path, limit=1024 * 1024):
    require(type(limit) is int and 0 < limit <= 32 * 1024 * 1024, "invalid JSON read limit")
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    path = Path(path)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit,
                "JSON must be a bounded ordinary non-aliased file")
        raw = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) and
                len(raw) == before.st_size <= limit, "JSON changed or exceeds byte limit")
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(SourceError("nonfinite JSON")))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise SourceError("invalid bounded JSON") from exc


def read_calibrated_record(asset, header, record, montage):
    """Read one stored second, calibrating electrodes before subtraction.

    The caller owns source admission. This low-level operation does not claim
    that a generated Asset/header is a complete admitted Helsinki corpus.
    """
    require(type(record) is int and 0 <= record < header.records, "record outside source support")
    mapping = dict(header.electrode_indices)
    require(set(mapping) == {e for pair in montage for e in pair}, "montage electrode support differs")
    asset.check_unchanged()
    asset.handle.seek(header.bytes + record * header.record_bytes)
    raw = asset.handle.read(header.record_bytes)
    require(len(raw) == header.record_bytes, "short required EDF record")
    electrodes = {}
    for electrode, index in mapping.items():
        channel = header.channels[index]
        require(channel.samples == FS and channel.unit == "uV", "unadmitted channel rate or units")
        values = struct.unpack_from("<256h", raw, channel.byte_offset)
        electrodes[electrode] = tuple(channel.physical(value) for value in values)
    samples = tuple(tuple(electrodes[a][index] - electrodes[b][index] for a, b in montage)
                    for index in range(FS))
    require(all(math.isfinite(value) for row in samples for value in row), "nonfinite calibrated bipolar value")
    asset.check_unchanged()
    return samples


def flags_for_record(samples):
    """Exact retained input-quality rule; not a validated pause detector."""
    require(type(samples) in (list, tuple) and len(samples) == FS and
            all(type(row) in (list, tuple) and len(row) == 18 for row in samples),
            "one complete 256-sample by 18-channel record required")
    try:
        valid = all(type(v) in (int, float) and math.isfinite(v) for row in samples for v in row)
    except OverflowError:
        valid = False
    require(valid, "quality rule requires finite numeric samples")
    zero = all(v == 0.0 for row in samples for v in row)
    flat = any(all(row[channel] == samples[0][channel] for row in samples) for channel in range(18))
    return zero, flat


class IntervalReader:
    """Bounded cache over an owner-supplied asset/header lookup.

    This class is a numerical/IO primitive, not a source-admission certificate.
    SourceCorpus supplies only exact authenticated source descriptors.
    """
    def __init__(self, lookup, montage, cache_records=31):
        require(type(cache_records) is int and 0 <= cache_records <= 31, "cache bound must be 0..31 records")
        require(tuple("-".join(pair) for pair in montage) == load_sources().current.MONTAGE,
                "exact source montage required")
        self.lookup, self.montage = lookup, tuple(montage)
        self.cache_records, self._cache = cache_records, OrderedDict()
        self._identities = {}

    def __call__(self, recording_id, start, stop):
        require(type(recording_id) is str and recording_id in RECORD_IDS, "unknown recording ID")
        asset, header = self.lookup(recording_id)
        identity = (asset.identity, asset.sha256, header)
        if recording_id in self._identities:
            require(self._identities[recording_id] == identity, "recording descriptor changed after first read")
        else:
            self._identities[recording_id] = identity
        require(type(start) is int and type(stop) is int and 0 <= start < stop <= header.records * FS,
                "invalid half-open sample interval")
        require(stop - start <= MAX_WINDOW_SAMPLES, "read exceeds original 30-record context")
        asset.check_unchanged()
        result = []
        for record in range(start // FS, (stop - 1) // FS + 1):
            key = (recording_id, record)
            samples = self._cache.pop(key, None)
            if samples is None:
                samples = read_calibrated_record(asset, header, record, self.montage)
            if self.cache_records:
                self._cache[key] = samples
                while len(self._cache) > self.cache_records:
                    self._cache.popitem(last=False)
            first, last = max(0, start - record * FS), min(FS, stop - record * FS)
            result.extend(samples[first:last])
        asset.check_unchanged()
        require(len(result) == stop - start, "incomplete interval read")
        return result

    def clear(self):
        self._cache.clear()


class SourceCorpus:
    """Complete pinned 82-file Corpus with one-pass flags and a lazy reader."""
    def __init__(self, source_root):
        self.sources = load_sources()
        self._corpus = self.sources.intake.Corpus(source_root, self.sources.manifest)
        self._closed = False
        self.source_lineage = deepcopy(self._corpus.lineage())
        self.reader = IntervalReader(self._lookup, self.sources.intake.MONTAGE)

    def _lookup(self, recording_id):
        require(not self._closed and type(recording_id) is str and recording_id in RECORD_IDS,
                "closed corpus or invalid recording")
        infant = int(recording_id[3:])
        return self._corpus.assets[recording_id + ".edf"], self._corpus.headers[infant]

    def read_samples(self, recording_id, start, stop):
        return self.reader(recording_id, start, stop)

    def private_census(self):
        """Traverse every source second once; do not materialize overlapping windows."""
        require(not self._closed, "closed corpus")
        records = []
        for infant in range(1, 80):
            rid = "eeg" + str(infant)
            asset, header = self._lookup(rid)
            zero, flat = [], []
            for second in range(header.records):
                z, f = flags_for_record(self.reader(rid, second * FS, (second + 1) * FS))
                zero.append(z)
                flat.append(f)
            labels = [[votes[expert] for votes in self._corpus.annotations[infant]] for expert in range(3)]
            records.append({"recording_id": rid, "source_asset": asset.name,
                            "source_sha256": asset.sha256, "header_sha256": header.sha256,
                            "sample_rate": {"num": FS, "den": 1}, "sample_count": header.records * FS,
                            "record_seconds": header.records, "units": "uV", "labels": labels,
                            "zero_bipolar": zero, "any_flatline": flat,
                            "primary_cases": header.records - 29,
                            "first_primary_record_second": 29,
                            "last_primary_record_second": header.records - 1})
        self.reader.clear()
        require(self._corpus.lineage() == self.source_lineage, "source lineage changed during census")
        result = {"schema": "helsinki-original-source-census-v1", "source_version": "zenodo:4940267-v4",
                  "coordinate_id": COORDINATE, "historical_protocol_id": self.sources.profile.PROTOCOL_ID,
                  "physical_clock_verified": False, "clinical_or_TAL_continuity_verified": False,
                  "flag_rule": self.sources.intake.FLAG_RULE, "quality_detector_validated": False,
                  "source_lineage": self.source_lineage, "source_dependencies": self.sources.dependencies,
                  "records": records, "record_seconds": sum(r["record_seconds"] for r in records),
                  "primary_cases": sum(r["primary_cases"] for r in records),
                  "infants": 79, "experts": 3, "excluded_initial_record_seconds": 79 * 29,
                  "excluded_final_fractional_record_seconds": 0}
        require((result["record_seconds"], result["primary_cases"]) == (402825, 400534),
                "source complete support differs")
        return result

    def close(self):
        if not self._closed:
            self.reader.clear()
            self._corpus.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def current_description(census, policy, coordinate_binding=None):
    """Project private source census only after an explicit coordinate decision.

    The binding is a reviewed source document, not a caller-provided claim that
    clinical clock continuity was proven. Exact binding pins are set in the
    release after root's source review; an absent decision refuses projection.
    """
    from coordinate import load_coordinate_binding
    admitted = load_coordinate_binding()
    if coordinate_binding is not None:
        require(canonical(coordinate_binding) == canonical(admitted), "unreviewed coordinate binding")
    sources = load_sources()
    require(type(policy) is dict and set(policy) == {
        "schema", "assessment_id", "fold_seed", "development_by_fold"} and
        policy["schema"] == "helsinki-source-preparation-policy-v1", "exact preparation policy required")
    require(type(census) is dict and census.get("schema") == "helsinki-original-source-census-v1" and
            census.get("source_version") == "zenodo:4940267-v4" and census.get("coordinate_id") == COORDINATE and
            census.get("historical_protocol_id") == sources.profile.PROTOCOL_ID and
            census.get("source_dependencies") == sources.dependencies and
            census.get("flag_rule") == sources.intake.FLAG_RULE and
            census.get("physical_clock_verified") is False and
            census.get("clinical_or_TAL_continuity_verified") is False and
            census.get("quality_detector_validated") is False,
            "source census identity or scope differs")
    require(set(census) == {
        "schema", "source_version", "coordinate_id", "historical_protocol_id", "physical_clock_verified",
        "clinical_or_TAL_continuity_verified", "flag_rule", "quality_detector_validated", "source_lineage",
        "source_dependencies", "records", "record_seconds", "primary_cases", "infants", "experts",
        "excluded_initial_record_seconds", "excluded_final_fractional_record_seconds"}, "exact source census fields required")
    sources.profile.validate_lineage(census["source_lineage"])
    require(all(type(census[key]) is int for key in (
        "record_seconds", "primary_cases", "infants", "experts", "excluded_initial_record_seconds",
        "excluded_final_fractional_record_seconds")), "source counts must be integers")
    require((census.get("record_seconds"), census.get("primary_cases"), census.get("infants"), census.get("experts"),
             census.get("excluded_initial_record_seconds"), census.get("excluded_final_fractional_record_seconds")) ==
            (402825, 400534, 79, 3, 2291, 0), "complete source counts differ")
    rows = census.get("records")
    require(type(rows) is list and len(rows) == 79 and
            [row.get("recording_id") for row in rows if type(row) is dict] == list(RECORD_IDS),
            "complete ordered original recording roster required")
    descriptions = []
    for infant, row in enumerate(rows, 1):
        rid = "eeg" + str(infant)
        count = sources.profile.source_profiles()["headers"][infant]["declared_records"]
        expected_fields = {"recording_id", "source_asset", "source_sha256", "header_sha256", "sample_rate",
                           "sample_count", "record_seconds", "units", "labels", "zero_bipolar", "any_flatline",
                           "primary_cases", "first_primary_record_second", "last_primary_record_second"}
        require(set(row) == expected_fields and row["source_asset"] == rid + ".edf" and
                row["source_sha256"] == census["source_lineage"]["assets"][rid + ".edf"] and
                row["header_sha256"] == census["source_lineage"]["headers"][str(infant)] and
                row["sample_rate"] == {"num": FS, "den": 1} and
                all(type(row["sample_rate"][key]) is int for key in ("num", "den")) and type(row["sample_count"]) is int and
                row["sample_count"] == count * FS and type(row["record_seconds"]) is int and
                row["record_seconds"] == count and row["units"] == "uV" and
                (row["primary_cases"], row["first_primary_record_second"], row["last_primary_record_second"]) ==
                (count - 29, 29, count - 1), "source recording geometry or identity differs")
        zero, flat = row["zero_bipolar"], row["any_flatline"]
        require(type(zero) is list and type(flat) is list and len(zero) == len(flat) == count and
                all(type(v) is bool for v in zero + flat) and all(not z or f for z, f in zip(zero, flat)),
                "complete frozen original quality flags required")
        descriptions.append({"recording_id": rid, "eeg_sha256": row["source_sha256"],
                             "sample_rate": {"num": FS, "den": 1}, "sample_count": count * FS,
                             "sample_zero_annotation_second": 0, "units": "uV",
                             "labels": deepcopy(row["labels"]),
                             "quality_flags": [z or f for z, f in zip(zero, flat)]})
    representation = {"schema": "helsinki-source-sample-representation-v1", "coordinate_binding": admitted,
                      "montage": list(sources.current.MONTAGE), "units": "uV", "sample_rate": {"num": FS, "den": 1},
                      "transform": "calibrate_each_electrode_then_bipolar_subtraction",
                      "source_dependencies": sources.dependencies}
    detector = {"rule": sources.intake.FLAG_RULE,
                "projection": "per_record_zero_bipolar_OR_any_flatline",
                "intake_source_sha256": sources.dependencies[
                    "docs/provenance/registrations/expansion-20261113/helsinki-recorded-grid-construction-v1/helsinki_intake.py"],
                "validated_missingness_or_pause_detector": False}
    result = {"schema": sources.current.DESCRIPTION_SCHEMA, "assessment_id": policy["assessment_id"],
              "protocol_id": sources.current.PROTOCOL, "source_version": sources.current.SOURCE_VERSION,
              "fold_seed": policy["fold_seed"], "representation_sha256": digest(representation),
              "detector_sha256": digest(detector),
              "source_admission_sha256": digest({"source_census": digest(census), "coordinate_binding": admitted}),
              "montage": list(sources.current.MONTAGE),
              "development_by_fold": deepcopy(policy["development_by_fold"]), "recordings": descriptions}
    # Reuse the current protocol's own exact roster/label/fold/metadata checks.
    # Its split and full-payload commitments are not replaced by historical ones.
    sources.current._validate_description(result)
    return result


def write_private_new(path, document):
    path = Path(path)
    require(path.parent.is_dir() and not path.exists(), "output parent must exist and output must be new")
    body = canonical(document) + b"\n"
    require(len(body) <= 32 * 1024 * 1024, "private JSON output exceeds 32 MiB")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--policy", type=Path, help="optional exact current-protocol preparation policy")
    parser.add_argument("--description-output", type=Path, help="private current-protocol description output")
    args = parser.parse_args(argv)
    try:
        require(not args.output.exists(), "output already exists")
        require((args.policy is None) == (args.description_output is None),
                "policy and description output must be supplied together")
        if args.description_output is not None:
            require(not args.description_output.exists() and
                    args.output.absolute() != args.description_output.absolute(), "description output must be distinct and new")
        policy = bounded_json(args.policy) if args.policy is not None else None
        with SourceCorpus(args.source_root) as corpus:
            census = corpus.private_census()
            description = current_description(census, policy) if policy is not None else None
        write_private_new(args.output, census)
        if description is not None:
            write_private_new(args.description_output, description)
    except (SourceError, OSError, ValueError) as exc:
        print("source admission refused: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"private_output": str(args.output), "infants": census["infants"],
                      "record_seconds": census["record_seconds"], "primary_cases": census["primary_cases"],
                      "coordinate_id": census["coordinate_id"], "scientific_qualification": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
