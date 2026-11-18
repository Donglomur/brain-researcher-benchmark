"""Operator-only, calibrated classic-EDF windows for NEURAL-009.

This is a record-level preparation component, not a participant sandbox or a
complete-cohort admission. No filtering, resampling, fitting or scoring occurs.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
import math
import os
from pathlib import Path
import re
import struct
import types

ROOT = Path(__file__).resolve().parent
ADMISSION_SHA256 = "1c5096ab1a1f75f39cd6de9e8fa71772c7bed9ce35ef3197ac69aacad30720d9"
ADMISSION_BYTES = 21865
UNIT_TO_UV = {"V": Fraction(1000000), "mV": Fraction(1000),
              "uV": Fraction(1), "nV": Fraction(1, 1000)}


class Refused(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise Refused(message)


def integer(value, name, minimum=1):
    need(type(value) is int and minimum <= value <= 2**53 - 1,
         name + ": invalid bounded integer")
    return value


def digest_text(value, name):
    need(type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None,
         name + ": invalid SHA256")


def load_admission(path=None):
    """Execute only the independently pinned existing standard-library helper."""
    path = Path(path) if path is not None else ROOT.parent / "source-admission-v1" / "admission.py"
    need(path.is_file() and not path.is_symlink(), "Missing ordinary admission source")
    with path.open("rb") as handle:
        body = handle.read(ADMISSION_BYTES + 1)
    need(len(body) == ADMISSION_BYTES and hashlib.sha256(body).hexdigest() == ADMISSION_SHA256,
         "Admission source identity differs")
    module = types.ModuleType("_neural009_pinned_source_admission")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def rational(raw, name):
    """Bounded exact decimal calibration; scientific notation is permitted."""
    try:
        value = raw.decode("ascii").strip()
        need(re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?", value)
             is not None, name + ": not an EDF decimal")
        decimal = Decimal(value)
        need(decimal.is_finite() and (decimal == 0 or -24 <= decimal.adjusted() <= 24),
             name + ": outside supported calibration range")
        return Fraction(decimal)
    except (UnicodeError, InvalidOperation, ValueError, OverflowError) as exc:
        raise Refused(name + ": invalid calibration") from exc


def _field(header, channels, offset, width, index):
    start = 256 + offset * channels + width * index
    return header[start:start + width]


def calibration(header, index):
    """Return exact gain/offset in microvolts, retaining negative amplifier gain."""
    channels = int(header[252:256])
    try:
        unit = _field(header, channels, 96, 8, index).decode("ascii").strip()
        need(unit in UNIT_TO_UV, "Uncalibrated or unsupported physical unit")
        pmin = rational(_field(header, channels, 104, 8, index), "Physical minimum")
        pmax = rational(_field(header, channels, 112, 8, index), "Physical maximum")
        digital = []
        for offset in (120, 128):
            text = _field(header, channels, offset, 8, index).decode("ascii").strip()
            need(re.fullmatch(r"[+-]?\d+", text) is not None, "Invalid digital bound")
            digital.append(int(text))
    except (UnicodeError, ValueError) as exc:
        raise Refused("Malformed calibration") from exc
    dmin, dmax = digital
    need(-32768 <= dmin < dmax <= 32767, "Digital bounds outside signed16 range")
    need(pmin != pmax, "Zero amplifier gain")
    gain = (pmax - pmin) * UNIT_TO_UV[unit] / (dmax - dmin)
    offset = pmin * UNIT_TO_UV[unit] - dmin * gain
    return gain, offset, dmin, dmax


class RecordWindow:
    """Own one authenticated operator file and return causal selected-EEG slices.

    `row` is the operator's already admitted record row. All annotation fields
    remain outside this object's output. The caller must authenticate the complete
    admission and its source-review commitments before using this component.
    """

    def __init__(self, path, row, *, max_edf_bytes, max_window_samples,
                 max_output_values, admission_source=None):
        self._stream = None
        self._closed = False
        self._admission = load_admission(admission_source)
        integer(max_edf_bytes, "EDF byte budget")
        self.max_window_samples = integer(max_window_samples, "Window sample budget")
        self.max_output_values = integer(max_output_values, "Output value budget")
        need(type(row) is dict, "Admitted record row must be an object")
        for field in ("edf_sha256", "edf_header_sha256"):
            digest_text(row.get(field), field)
        try:
            stream, before = self._admission.ordinary_open(path, max_edf_bytes)
            self._stream = stream
            self._snapshot = before
            fixed = stream.read(256)
            need(len(fixed) == 256, "Truncated fixed EDF header")
            channels = self._admission.ascii_int(fixed[252:256], "Signal count")
            need(channels <= 256, "Too many EDF channels")
            header_size = self._admission.ascii_int(fixed[184:192], "Header bytes")
            need(header_size == 256 + 256 * channels, "Inconsistent EDF header geometry")
            header = fixed + stream.read(header_size - 256)
            geometry = self._admission.parse_edf_header(header, before.st_size)
            # EDF+C needs a separate TAL-clock qualification. Do not silently
            # flatten it, even though the admission geometry helper permits it.
            need(header[192:236].strip() == b"", "Only reviewed classic EDF clock is supported")
            need(geometry["header_sha256"] == row["edf_header_sha256"], "Admitted header differs")
            reviewed = row.get("channels")
            selected = row.get("predictor_channels")
            need(type(reviewed) is list and len(reviewed) == channels,
                 "Missing complete reviewed channel list")
            need(all(type(item) is dict and set(item) == {"label", "role"} and
                     item["role"] in ("eeg", "annotation", "other") for item in reviewed),
                 "Invalid reviewed channel roles")
            need([item["label"] for item in reviewed] == geometry["labels"], "Reviewed channel order differs")
            need(type(selected) is list and selected and
                 all(type(i) is int and 0 <= i < channels for i in selected) and
                 len(set(selected)) == len(selected), "Invalid selected channel indices")
            need(all(reviewed[i]["role"] == "eeg" and
                     reviewed[i]["label"] not in ("EDF Annotations", "-")
                     for i in selected), "Annotation, dummy or non-EEG channel selected")
            rates = [Fraction(geometry["samples_per_record"][i], 1) / geometry["record_duration"]
                     for i in selected]
            need(len(set(rates)) == 1 and rates[0].denominator == 1, "Selected channels lack one integer rate")
            self.sample_rate_hz = integer(row.get("native_sample_rate_hz"), "Admitted native rate")
            self.sample_count = integer(row.get("native_sample_count"), "Admitted native count")
            self.observed_ticks = integer(row.get("observed_ticks"), "Admitted ticks")
            need(self.sample_rate_hz == rates[0] and self.sample_count ==
                 geometry["samples_per_record"][selected[0]] * geometry["data_records"] and
                 self.observed_ticks == geometry["observed_ticks"], "Admitted native support differs")
            self._selected = tuple(selected)
            self._labels = tuple(reviewed[i]["label"] for i in selected)
            self._calibration = tuple(calibration(header, i) for i in selected)
            self._samples_per_record = geometry["samples_per_record"][selected[0]]
            self._header_size = header_size
            self._record_bytes = 2 * sum(geometry["samples_per_record"])
            self._channel_offsets = tuple(2 * sum(geometry["samples_per_record"][:i]) for i in selected)
            hashed = hashlib.sha256(header)
            consumed = len(header)
            while consumed < before.st_size:
                chunk = stream.read(min(65536, before.st_size - consumed))
                need(chunk, "Truncated EDF body")
                hashed.update(chunk)
                consumed += len(chunk)
            need(not stream.read(1), "EDF grew during authentication")
            self._admission.stable(before, os.fstat(stream.fileno()))
            need(hashed.hexdigest() == row["edf_sha256"], "Complete admitted EDF hash differs")
        except BaseException:
            self.close()
            raise

    def close(self):
        if self._stream is not None:
            self._stream.close()
        self._closed = True

    def __enter__(self):
        need(not self._closed, "Closed record")
        return self

    def __exit__(self, *unused):
        self.close()

    def window(self, start_sample, stop_sample, *, available_through_tick):
        """Return [start,stop); sample j has recording-relative time j/Fs.

        An endpoint tick t permits only j/Fs <= t/10. This is exact rational
        availability, not a claim about hardware or processing latency.
        """
        need(not self._closed, "Closed record")
        integer(start_sample, "Start sample", minimum=0)
        integer(stop_sample, "Stop sample")
        integer(available_through_tick, "Available endpoint tick")
        need(start_sample < stop_sample <= self.sample_count, "Window outside recording")
        need(available_through_tick <= self.observed_ticks, "Endpoint outside recording")
        limit = min(self.sample_count, available_through_tick * self.sample_rate_hz // 10 + 1)
        need(stop_sample <= limit, "Window contains future EEG")
        span = stop_sample - start_sample
        need(span <= self.max_window_samples and span * len(self._selected) <= self.max_output_values,
             "Window exceeds declared output budget")
        self._admission.stable(self._snapshot, os.fstat(self._stream.fileno()))
        channels = []
        for channel, label, channel_offset, parameters in zip(
                self._selected, self._labels, self._channel_offsets, self._calibration):
            gain, offset, digital_min, digital_max = parameters
            values = []
            cursor = start_sample
            while cursor < stop_sample:
                record, within = divmod(cursor, self._samples_per_record)
                count = min(stop_sample - cursor, self._samples_per_record - within)
                self._stream.seek(self._header_size + record * self._record_bytes + channel_offset + 2 * within)
                raw = self._stream.read(2 * count)
                need(len(raw) == 2 * count, "Truncated selected EEG samples")
                for (digital,) in struct.iter_unpack("<h", raw):
                    need(digital_min <= digital <= digital_max, "Sample outside declared digital extrema")
                    value = float(offset + digital * gain)
                    need(math.isfinite(value), "Nonfinite calibrated EEG")
                    values.append(value)
                cursor += count
            channels.append({"channel_index": channel, "label": label, "unit": "uV", "samples": values})
        self._admission.stable(self._snapshot, os.fstat(self._stream.fileno()))
        return {"schema": "neural009_calibrated_causal_window_v1", "sample_start": start_sample,
                "sample_stop": stop_sample, "sample_rate_hz": self.sample_rate_hz,
                "available_through_tick": available_through_tick, "channels": channels}
