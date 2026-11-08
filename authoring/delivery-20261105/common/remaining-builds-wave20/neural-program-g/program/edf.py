"""Streaming EDF custody for full Sleep Cassette preparation, not a source reader call.

Derived from the benchmark-authored sleep source-v2 header/TAL specification.
Modified2026-11-07 for standard-library parsing and bounded channel streaming.
No payload, network or scientific dependency is loaded on import.
"""
from datetime import datetime
from decimal import Decimal
import math
import re
from .common import CHANNELS, need


def header(handle, file_bytes):
    first = handle.read(256); need(len(first) == 256, 'Complete EDF fixed header')
    def text(body):
        need(all(32 <= b < 127 for b in body), 'Printable EDF fixed field')
        return body.decode('ascii').strip()
    need(text(first[:8]) == '0', 'EDF version0')
    count = int(text(first[252:256])); extent = int(text(first[184:192]))
    need(1 <= count <= 64 and extent == 256 * (1 + count), 'Bounded full EDF channel header')
    rest = handle.read(extent - 256); need(len(rest) == extent - 256, 'Complete channel header')
    rows, offset = {}, 0
    for name, width in [('labels', 16), ('transducer', 80), ('units', 8), ('physical_min', 8), ('physical_max', 8),
                        ('digital_min', 8), ('digital_max', 8), ('prefilter', 80), ('samples', 8), ('signal_reserved', 32)]:
        rows[name] = [text(rest[offset + j * width:offset + (j + 1) * width]) for j in range(count)]
        offset += width * count
    day, month, year = map(int, text(first[168:176]).split('.'))
    year += 1900 if year >= 85 else 2000
    hour, minute, second = map(int, text(first[176:184]).split('.'))
    start = datetime(year, month, day, hour, minute, second)
    records, seconds = int(text(first[236:244])), Decimal(text(first[244:252]))
    need(records > 0 and seconds.is_finite() and seconds >= 0, 'Finite declared EDF record extent')
    need(len(set(rows['labels'])) == count, 'No duplicate channel names')
    for name in ('digital_min', 'digital_max', 'samples'):
        rows[name] = [int(x) for x in rows[name]]
    for name in ('physical_min', 'physical_max'):
        rows[name] = [float(x) for x in rows[name]]
    need(all(x > 0 for x in rows['samples']), 'Positive samples per record')
    need(all(-32768 <= a < b <= 32767 for a, b in zip(rows['digital_min'], rows['digital_max'])), 'Digital int16 calibration')
    need(all(math.isfinite(a) and math.isfinite(b) and a < b for a, b in zip(rows['physical_min'], rows['physical_max'])), 'Physical calibration')
    stride = 2 * sum(rows['samples'])
    need(file_bytes == extent + records * stride, 'Exact original EDF file length')
    rows.update(header_bytes=extent, record_bytes=stride, records=records, record_seconds=str(seconds),
                start=start.isoformat(), clock_seconds=hour * 3600 + minute * 60 + second, reserved=text(first[192:236]))
    return rows


def psg_geometry(h):
    need(not h['reserved'].startswith('EDF+D'), 'Continuous EDF required; no gap interpolation')
    seconds = Decimal(h['record_seconds']); need(seconds > 0, 'Positive PSG record duration')
    indexes = []
    for channel in CHANNELS:
        need(channel in h['labels'], 'Every required channel present')
        j = h['labels'].index(channel)
        need(Decimal(h['samples'][j]) == 100 * seconds and h['units'][j] == 'uV', 'Exact100Hz microvolt source channel')
        indexes.append(j)
    total_samples = h['records'] * h['samples'][indexes[0]]
    need(all(h['records'] * h['samples'][j] == total_samples for j in indexes), 'Aligned channel lengths')
    epochs, tail = divmod(total_samples, 3000)
    need(epochs >= 2, 'Complete original shift-supported recording; never crop or substitute')
    return indexes, epochs, tail


def annotations(handle, h, max_bytes):
    need(h['labels'] == ['EDF Annotations'], 'Annotation-only companion EDF')
    size = h['records'] * h['record_bytes']; need(size <= max_bytes, 'Prospective annotation body cap')
    body = handle.read(size + 1); need(len(body) == size, 'Complete exact annotation records')
    result = []
    for block in body.split(b'\0'):
        if not block:
            continue
        need(block.endswith(b'\x14'), 'Terminated annotation list')
        fields = block[:-1].split(b'\x14'); timing = fields[0].split(b'\x15')
        need(len(timing) in (1, 2) and re.fullmatch(rb'[+-]\d+(?:\.\d+)?', timing[0]), 'Exact annotation onset text')
        need(len(timing[0]) <= 64, 'Bounded annotation numeric text')
        texts = [x.decode('utf-8') for x in fields[1:] if x]
        if not texts:
            continue
        need(len(timing) == 2 and len(timing[1]) <= 64 and re.fullmatch(rb'\d+(?:\.\d+)?', timing[1]), 'Exact positive duration text')
        need(Decimal(timing[1].decode()) > 0, 'Positive stage duration')
        for text in texts:
            result.append({'onset': timing[0].decode(), 'duration': timing[1].decode(), 'text': text})
    return result


def channel_chunks(handle, h, indexes, samples_wanted, chunk_records=64):
    """Yield calibrated float64 volts per selected channel, never labels/crops."""
    import numpy as np
    need(type(chunk_records) is int and chunk_records > 0, 'Bounded record chunk count')
    need(h['record_bytes'] * chunk_records <= 8 * 1024 * 1024, 'Bounded original-record working chunk')
    source_width = sum(h['samples']); offsets = [sum(h['samples'][:j]) for j in indexes]
    position = 0
    for first in range(0, h['records'], chunk_records):
        count = min(chunk_records, h['records'] - first)
        raw = handle.read(count * h['record_bytes']); need(len(raw) == count * h['record_bytes'], 'Complete original signal chunk')
        data = np.frombuffer(raw, dtype='<i2').reshape(count, source_width)
        n = min(count * h['samples'][indexes[0]], samples_wanted - position)
        if n <= 0:
            break
        output = []
        for j, offset in zip(indexes, offsets):
            digital = data[:, offset:offset + h['samples'][j]].reshape(-1)[:n].astype(np.float64)
            slope = (h['physical_max'][j] - h['physical_min'][j]) / (h['digital_max'][j] - h['digital_min'][j])
            intercept = h['physical_min'][j] - h['digital_min'][j] * slope
            values = (digital * slope + intercept) * 1e-6
            need(np.isfinite(values).all(), 'Finite calibrated complete signal')
            output.append(values)
        yield position, output
        position += n
    need(position == samples_wanted, 'Every complete-clock signal sample retained')
