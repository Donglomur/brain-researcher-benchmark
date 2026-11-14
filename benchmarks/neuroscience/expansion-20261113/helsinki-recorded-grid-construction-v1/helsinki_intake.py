"""Owner-only Helsinki recorded-grid v2 intake. No downloader or import-time I/O.

The host must keep this module, Corpus, annotations and EDFs outside participant
processes. Python attribute privacy is not a sandbox. See IMPLEMENTATION_STATUS.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import stat
import struct
from dataclasses import dataclass
from pathlib import Path

INFANTS = tuple(range(1, 80))
FS = 256
RELEASE_SHA256 = "84ad5381159c34a592a8177b2d2b2b03d6dc3a352a1e8e566201f5cd40f8aa8a"
from helsinki_profile import (PROTOCOL_ID, COORDINATE_ID, Refusal, source_profiles,
                              profile_identity, complete_support, validate_lineage)
FLAG_RULE = "zero-bipolar-and-any-flatline-per-second-v1"
ANNOTATIONS = ("annotations_2017_A_fixed.csv", "annotations_2017_B.csv",
               "annotations_2017_C.csv")
MONTAGE = (("Fp2", "F4"), ("F4", "C4"), ("C4", "P4"), ("P4", "O2"),
           ("Fp1", "F3"), ("F3", "C3"), ("C3", "P3"), ("P3", "O1"),
           ("Fp2", "F8"), ("F8", "T4"), ("T4", "T6"), ("T6", "O2"),
           ("Fp1", "F7"), ("F7", "T3"), ("T3", "T5"), ("T5", "O1"),
           ("Fz", "Cz"), ("Cz", "Pz"))
ELECTRODES = frozenset(v for pair in MONTAGE for v in pair)


def require(condition, reason):
    if not condition:
        raise Refusal(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def finite(value):
    require(type(value) in (int, float) and math.isfinite(value), "nonfinite_number")
    return float(value)


def _ascii(raw):
    try:
        return raw.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise Refusal("non_ascii_edf_header") from exc


def _integer(raw):
    s = _ascii(raw)
    require(s and s.isdecimal(), "invalid_nonnegative_edf_integer")
    return int(s)


@dataclass(frozen=True)
class Channel:
    label: str
    unit: str
    minimum: float
    maximum: float
    digital_minimum: int
    digital_maximum: int
    samples: int
    byte_offset: int

    def physical(self, value):
        require(self.digital_minimum <= value <= self.digital_maximum,
                "sample_outside_declared_digital_range")
        return (self.minimum + (value - self.digital_minimum) *
                (self.maximum - self.minimum) /
                (self.digital_maximum - self.digital_minimum))


@dataclass(frozen=True)
class Header:
    bytes: int
    records: int
    record_bytes: int
    channels: tuple[Channel, ...]
    electrode_indices: tuple[tuple[str, int], ...]
    sha256: str

    @property
    def duration_seconds(self):
        # Count exported one-second records; this is not a clinical-clock claim.
        return self.records


@dataclass(frozen=True)
class QualityFlags:
    zero_bipolar: tuple[bool, ...]
    any_flatline: tuple[bool, ...]

    def validate(self):
        require(type(self.zero_bipolar) is tuple and type(self.any_flatline) is tuple,
                "quality_flag_containers_must_be_immutable_tuples")
        require(len(self.zero_bipolar) == len(self.any_flatline) == 30 and
                all(type(v) is bool for v in self.zero_bipolar + self.any_flatline),
                "invalid_quality_flag_shape_or_type")
        require(all(not z or f for z, f in zip(self.zero_bipolar, self.any_flatline)),
                "zero_bipolar_must_also_be_flatline")
        return self

    def public(self):
        self.validate()
        return {"rule": FLAG_RULE, "zero_bipolar_seconds": self.zero_bipolar,
                "any_flatline_seconds": self.any_flatline,
                "interpretation": "input_quality_flags_not_verified_missingness"}

    def features(self):
        self.validate()
        return (any(self.zero_bipolar), self.zero_bipolar[-1],
                any(self.any_flatline), self.any_flatline[-1])

    def stratum(self):
        self.validate()
        if self.zero_bipolar[-1] or self.any_flatline[-1]:
            return "final_second_flagged"
        if any(self.zero_bipolar) or any(self.any_flatline):
            return "earlier_context_flagged_final_unflagged"
        return "no_flagged_context"


def derive_quality_flags(signal):
    require(len(signal) == 18 and all(len(ch) == 30 * FS for ch in signal),
            "wrong_waveform_shape")
    require(all(type(v) in (int, float) and math.isfinite(v) for ch in signal for v in ch),
            "invalid_waveform_value")
    zero, flat = [], []
    for second in range(30):
        segments = [ch[second * FS:(second + 1) * FS] for ch in signal]
        zero.append(all(all(v == 0.0 for v in ch) for ch in segments))
        flat.append(any(min(ch) == max(ch) for ch in segments))
    return QualityFlags(tuple(zero), tuple(flat)).validate()


def read_header(handle, expected_size):
    handle.seek(0)
    fixed = handle.read(256)
    require(len(fixed) == 256 and _ascii(fixed[:8]) == "0", "unsupported_edf_version")
    require(_ascii(fixed[192:236]) == "", "edf_plus_or_discontinuous_not_admitted")
    count = _integer(fixed[252:256])
    size = _integer(fixed[184:192])
    records = _integer(fixed[236:244])
    require(19 <= count <= 64 and size == 256 * (count + 1), "header_size_or_channels")
    require(records >= 30 and float(_ascii(fixed[244:252])) == 1.0,
            "requires_one_second_records_and_30_second_support")
    body = handle.read(size - 256)
    require(len(body) == size - 256, "short_edf_header")
    fields, position = {}, 0
    widths = (("label", 16), ("transducer", 80), ("unit", 8), ("min", 8),
              ("max", 8), ("dmin", 8), ("dmax", 8), ("filter", 80),
              ("samples", 8), ("reserved", 32))
    for key, width in widths:
        fields[key] = tuple(_ascii(body[position + j * width:position + (j + 1) * width])
                            for j in range(count))
        position += count * width
    channels, offset, mapping = [], 0, {}
    require(len(set(fields["label"])) == count, "duplicate_channel_label")
    for i in range(count):
        try:
            lo, hi = float(fields["min"][i]), float(fields["max"][i])
            dlo, dhi = int(fields["dmin"][i]), int(fields["dmax"][i])
            n = int(fields["samples"][i])
        except ValueError as exc:
            raise Refusal("invalid_channel_number") from exc
        require(math.isfinite(lo) and math.isfinite(hi) and lo < hi and
                -32768 <= dlo < dhi <= 32767 and 0 < n <= 16384,
                "invalid_channel_calibration_or_rate")
        ch = Channel(fields["label"][i], fields["unit"][i], lo, hi, dlo, dhi, n, offset)
        channels.append(ch)
        offset += 2 * n
        for electrode in ELECTRODES:
            if ch.label == "EEG " + electrode + "-Ref":
                require(ch.unit == "uV" and ch.samples == FS, "eeg_units_or_sampling")
                require(electrode not in mapping, "duplicate_electrode")
                mapping[electrode] = i
    require(set(mapping) == ELECTRODES, "missing_or_unreviewed_eeg_label_alias")
    require(size + records * offset == expected_size, "edf_duration_file_size_mismatch")
    return Header(size, records, offset, tuple(channels), tuple(sorted(mapping.items())),
                  hashlib.sha256(fixed + body).hexdigest())


def decode_fixed_record_header(handle, expected_size, marker=""):
    """Syntax/calibration decoder only; this does not admit a production source."""
    handle.seek(0)
    fixed = handle.read(256)
    require(len(fixed) == 256 and _ascii(fixed[:8]) == "0", "unsupported_edf_version")
    require(marker in ("", "EDF+C") and _ascii(fixed[192:236]) == marker,
            "unadmitted_recorded_grid_marker")
    count = _integer(fixed[252:256])
    size = _integer(fixed[184:192])
    records = _integer(fixed[236:244])
    require(19 <= count <= 64 and size == 256 * (count + 1), "header_size_or_channels")
    require(records >= 30 and float(_ascii(fixed[244:252])) == 1.0,
            "requires_one_second_records_and_30_second_support")
    body = handle.read(size - 256)
    require(len(body) == size - 256, "short_edf_header")
    fields, position = {}, 0
    widths = (("label", 16), ("transducer", 80), ("unit", 8), ("min", 8),
              ("max", 8), ("dmin", 8), ("dmax", 8), ("filter", 80),
              ("samples", 8), ("reserved", 32))
    for key, width in widths:
        fields[key] = tuple(_ascii(body[position + j * width:position + (j + 1) * width])
                            for j in range(count))
        position += count * width
    channels, offset, mapping = [], 0, {}
    require(len(set(fields["label"])) == count, "duplicate_channel_label")
    for i in range(count):
        try:
            lo, hi = float(fields["min"][i]), float(fields["max"][i])
            dlo, dhi = int(fields["dmin"][i]), int(fields["dmax"][i])
            n = int(fields["samples"][i])
        except ValueError as exc:
            raise Refusal("invalid_channel_number") from exc
        require(math.isfinite(lo) and math.isfinite(hi) and lo < hi and
                -32768 <= dlo < dhi <= 32767 and 0 < n <= 16384,
                "invalid_channel_calibration_or_rate")
        ch = Channel(fields["label"][i], fields["unit"][i], lo, hi, dlo, dhi, n, offset)
        channels.append(ch)
        offset += 2 * n
        for electrode in ELECTRODES:
            if ch.label in ("EEG " + electrode + "-Ref", "EEG " + electrode + "-REF"):
                require(ch.unit == "uV" and ch.samples == FS, "eeg_units_or_sampling")
                require(electrode not in mapping, "duplicate_electrode")
                mapping[electrode] = i
    require(not any("annotation" in ch.label.lower() for ch in channels), "unexpected_annotations_channel")
    require(set(mapping) == ELECTRODES, "missing_or_unreviewed_eeg_label_alias")
    require(size + records * offset == expected_size, "edf_duration_file_size_mismatch")
    return Header(size, records, offset, tuple(channels), tuple(sorted(mapping.items())),
                  hashlib.sha256(fixed + body).hexdigest())


def inspect_profile_header(raw, source_name, published_size, published_md5):
    """Exact partial header observation; NEVER a complete Corpus/custody receipt."""
    profiles = source_profiles()
    matches = [r for r in profiles["headers"].values() if r["asset_name"] == source_name]
    require(len(matches) == 1, "unknown_profile_edf_source")
    expected = matches[0]
    require(published_size == expected["published_bytes"] and
            published_md5 == expected["published_md5"] and
            len(raw) == expected["observed_header_bytes"] and
            hashlib.sha256(raw).hexdigest() == expected["observed_header_sha256"],
            "profile_source_or_header_identity_mismatch")
    marker = expected["reserved_marker"]
    if marker:
        exception = profiles["exceptions"].get(expected["study_id"])
        require(exception is not None and marker == "EDF+C" and
                exception["asset_name"] == source_name and
                exception["published_file_bytes"] == published_size and
                exception["published_file_md5"] == published_md5 and
                exception["observed_header_sha256"] == expected["observed_header_sha256"],
                "unlisted_legacy_export_exception")
    header = decode_fixed_record_header(io.BytesIO(raw), published_size, marker)
    require(header.records == expected["declared_records"] and
            len(header.channels) == expected["declared_channels"] == 21 and
            len(header.electrode_indices) == expected["declared_required_EEG"] == 19,
            "profile_record_grid_changed")
    return header


def read_helsinki_recorded_grid_header(asset):
    """Production route requires a complete authenticated Asset descriptor."""
    require(type(asset) is Asset, "complete_authenticated_asset_required")
    asset.check_unchanged()
    profiles = source_profiles()
    require(asset.name in profiles["manifest"] and asset.name.endswith(".edf"), "unknown_edf_asset")
    row = profiles["manifest"][asset.name]
    require(asset.md5 == row["md5"], "official_complete_asset_checksum_mismatch")
    require(asset.size == row["bytes"], "complete_edf_size_mismatch")
    asset.handle.seek(0)
    raw = asset.handle.read(5632)
    header = inspect_profile_header(raw, asset.name, asset.size, row["md5"])
    asset.check_unchanged()
    return header


def parse_recorded_grid_csv(handle, durations, expected_records):
    """Grammar/support parser only; production source identity is checked outside."""
    require(set(durations) == set(INFANTS) and
            all(type(t) is int and t >= 30 for t in durations.values()) and
            type(expected_records) is int and expected_records >= max(durations.values()),
            "invalid_recorded_grid_duration_census")
    wrapper = io.TextIOWrapper(handle, encoding="ascii", newline="")
    columns = {i: [] for i in INFANTS}
    observed_records = 0
    try:
        rows = csv.reader(wrapper)
        require(next(rows, None) == [str(i) for i in INFANTS], "mandatory_infant_header_mismatch")
        for second, row in enumerate(rows):
            require(second < expected_records and len(row) == 79,
                    "recorded_grid_csv_row_count_or_width")
            observed_records += 1
            for infant, cell in zip(INFANTS, row):
                if second < durations[infant]:
                    require(cell in ("0", "1"), "missing_nonbinary_recorded_grid_annotation")
                    columns[infant].append(int(cell))
                else:
                    require(cell == "", "nonempty_recorded_grid_padding")
    except (UnicodeError, csv.Error) as exc:
        raise Refusal("recorded_grid_csv_encoding_or_syntax") from exc
    finally:
        wrapper.detach()
    require(observed_records == expected_records and
            all(len(columns[i]) == durations[i] for i in INFANTS), "recorded_grid_csv_support_incomplete")
    return {i: tuple(columns[i]) for i in INFANTS}


def load_recorded_grid_annotations(asset, durations):
    require(type(asset) is Asset, "complete_authenticated_annotation_asset_required")
    profiles = source_profiles()
    require(asset.name in profiles["annotations"], "unknown_recorded_grid_expert_source")
    row = profiles["annotations"][asset.name]
    require(asset.size == row["bytes"] and asset.sha256 == row["actual_sha256"],
            "recorded_grid_expert_source_pin_mismatch")
    require(durations == {i: r["declared_records"] for i, r in profiles["headers"].items()},
            "recorded_grid_expert_duration_profile_mismatch")
    asset.check_unchanged()
    asset.handle.seek(0)
    result = parse_recorded_grid_csv(asset.handle, durations, profiles["csv"]["data_records"])
    asset.check_unchanged()
    return result


class Asset:
    """Authenticated open descriptor; host must additionally mount files read-only."""
    def __init__(self, root, row):
        path = Path(root) / row["name"]
        require(path.parent.resolve() == Path(root).resolve(), "asset_path_escape")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        self.handle = os.fdopen(fd, "rb")
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_size == row["bytes"],
                    "asset_type_or_length")
            md5 = hashlib.md5(usedforsecurity=False)
            sha = hashlib.sha256()
            for chunk in iter(lambda: self.handle.read(1024 * 1024), b""):
                md5.update(chunk)
                sha.update(chunk)
            self.md5 = md5.hexdigest()
            require(self.md5 == row["md5"], "published_asset_checksum_mismatch")
            self.identity = (before.st_dev, before.st_ino, before.st_size,
                             before.st_mtime_ns, before.st_ctime_ns)
            self.check_unchanged()
            self.sha256 = sha.hexdigest()
            self.name = row["name"]
            self.size = row["bytes"]
            self.handle.seek(0)
        except BaseException:
            self.handle.close()
            raise

    def check_unchanged(self):
        s = os.fstat(self.handle.fileno())
        require((s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns) == self.identity,
                "source_mutated_after_authentication")

    def close(self):
        self.handle.close()


def load_annotations(asset, durations):
    """Owner-only: exact 79 CSV columns, row0 is second0, no header guessing.

    Only empty/NaN padding is accepted outside a recording. Exact current padding
    convention remains an acquisition gate; finite padded labels are a refusal.
    """
    asset.check_unchanged()
    asset.handle.seek(0)
    wrapper = io.TextIOWrapper(asset.handle, encoding="ascii", newline="")
    columns = {i: [] for i in INFANTS}
    try:
        rows = csv.reader(wrapper)
        for second, row in enumerate(rows):
            require(len(row) == 79, "annotation_column_count_or_blank_row")
            require(second < 24 * 60 * 60, "unexpected_annotation_duration")
            for infant, cell in zip(INFANTS, row):
                cell = cell.strip()
                if second < durations[infant]:
                    require(cell in ("0", "1"), "missing_nonbinary_or_shifted_annotation")
                    columns[infant].append(int(cell))
                else:
                    require(cell in ("", "NaN", "nan"), "annotation_extends_beyond_recording")
    finally:
        wrapper.detach()
    for infant in INFANTS:
        require(len(columns[infant]) == durations[infant], "annotation_duration_mismatch")
    asset.check_unchanged()
    return {i: tuple(columns[i]) for i in INFANTS}


def read_recorded_window(asset, header, second):
    """Calibrated fixed-record slicing only; no production source admission."""
    require(type(asset) is Asset and type(header) is Header, "window_descriptor_or_header_type")
    require(type(second) is int and 29 <= second < header.records, "case_outside_recorded_support")
    asset.check_unchanged()
    mapping = dict(header.electrode_indices)
    reference = {e: [] for e in ELECTRODES}
    for record in range(second - 29, second + 1):
        asset.handle.seek(header.bytes + record * header.record_bytes)
        data = asset.handle.read(header.record_bytes)
        require(len(data) == header.record_bytes, "short_required_record")
        for e, index in mapping.items():
            ch = header.channels[index]
            values = struct.unpack_from("<" + str(FS) + "h", data, ch.byte_offset)
            reference[e].extend(ch.physical(v) for v in values)
    asset.check_unchanged()
    return tuple(tuple(x - y for x, y in zip(reference[a], reference[b]))
                 for a, b in MONTAGE)


class Corpus:
    """Trusted owner object. Never serialize this into a participant container."""
    def __init__(self, root, manifest_path):
        raw = Path(manifest_path).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == RELEASE_SHA256,
                "manifest_pin_mismatch")
        manifest = json.loads(raw)
        require(manifest["record_id"] == 4940267 and manifest["version"] == "v4",
                "wrong_release")
        rows = manifest["files"]
        names = {r["name"] for r in rows}
        require(len(rows) == len(names) == 82 and
                names == {f"eeg{i}.edf" for i in INFANTS} | set(ANNOTATIONS),
                "incomplete_or_extra_asset_census")
        self.assets, self.headers, self.annotations = {}, {}, {}
        self._intake_complete = False
        source_profiles()
        self.manifest_sha256 = RELEASE_SHA256
        try:
            for row in rows:
                self.assets[row["name"]] = Asset(root, row)
            for i in INFANTS:
                a = self.assets[f"eeg{i}.edf"]
                self.headers[i] = read_helsinki_recorded_grid_header(a)
            durations = self.durations
            streams = [load_recorded_grid_annotations(self.assets[n], durations) for n in ANNOTATIONS]
            self.annotations = {i: tuple(zip(*(s[i] for s in streams))) for i in INFANTS}
            self._intake_complete = True
            validate_lineage(self.lineage())
        except BaseException:
            self.close()
            raise

    @property
    def durations(self):
        return {i: self.headers[i].duration_seconds for i in INFANTS}

    @property
    def declared_recorded_seconds(self):
        return self.durations

    def seconds(self, infant):
        require(type(infant) is int and infant in INFANTS, "unknown_infant")
        return range(29, self.headers[infant].duration_seconds)

    def votes(self, infant, second):
        require(second in self.seconds(infant), "annotation_outside_primary_support")
        return self.annotations[infant][second]

    def waveform(self, infant, second):
        require(type(second) is int and second in self.seconds(infant), "case_outside_support")
        return read_recorded_window(self.assets[f"eeg{infant}.edf"], self.headers[infant], second)

    def case_data(self, infant, second):
        signal = self.waveform(infant, second)
        return signal, derive_quality_flags(signal)

    def lineage(self):
        require(self._intake_complete, "complete_recorded_grid_intake_required")
        for asset in self.assets.values():
            asset.check_unchanged()
        return validate_lineage({"manifest_sha256": self.manifest_sha256,
                "assets": {n: a.sha256 for n, a in sorted(self.assets.items())},
                "headers": {str(i): self.headers[i].sha256 for i in INFANTS},
                "durations": {str(i): self.durations[i] for i in INFANTS},
                "profile": profile_identity(), "support": complete_support()})

    def close(self):
        self._intake_complete = False
        for a in self.assets.values():
            a.close()
