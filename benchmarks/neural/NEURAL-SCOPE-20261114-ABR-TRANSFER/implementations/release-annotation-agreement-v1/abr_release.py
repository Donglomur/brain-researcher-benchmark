"""Complete ABR release-code assay construction. No provider/sandbox admission.

Operator library. NativeTarget reads the fixed retained preparation only when
explicitly constructed. Nothing imports original data or opens protected labels
on import. Pair is an operator collector, not an OS security boundary.
"""
from __future__ import annotations
import array
import contextlib
from decimal import Decimal, InvalidOperation, localcontext
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys
import types
import zlib

MODE = 'abr-release-annotation-code-agreement-zero-support-v1'
COMPLETE_PIN = (22643, '507b7e77a2a4d09f5056e6191efe34db7092ca4eab70a4880e425ae7eade1972')
PROTOCOL_PIN = (13916, 'd356876a7f9b2888749a2e787ec292dc92b6d9c1fdc2e82bdc29252354e7fa44')
COMMON_DOCUMENTATION_PIN = (3489, '455d5777bd6e49162055cbccfff079689517d8934bebc1a6adf4e49ee0c7b754')
RASTER_PATH = 'benchmarks/neural/NEURAL-077/implementations/visual-viewer-v1/raster.py'
RASTER_PIN = (8179, 'b8cc040978a38104a9adc7747748411e4abe61aa9df9c5a6cdd3c00902dd2a18')
TARGET_KEYS = ('observations/target/cases.jsonl.gz', 'observations/target/index.jsonl.gz',
               'observations/target/waveforms.f64le.gz', 'private/annotation-projection.jsonl.gz')
BACKGROUND_COUNTS = {'C57BL/6NTacCdh23+': 54, 'C57BL/6N': 50}
TONES = (3000, 6000, 12000, 18000, 24000, 30000, 36000, 42000)
HOLDS = {'candidate_delivery_admitted': False, 'authentic_scoring_admitted': False,
         'scientifically_qualified': False, 'new_benchmark_count': 0}
MAX_FINAL = 4096


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def decode(raw, *, decimal=False):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def constant(_):
        raise ValueError('nonfinite JSON constant')
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant,
                          parse_float=Decimal if decimal else float)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('malformed JSON') from exc


def number(x):
    need(type(x) in (int, float, Decimal), 'numeric value required')
    try:
        need(math.isfinite(float(x)), 'finite IEEE754-range number required')
    except (OverflowError, ValueError) as exc:
        raise ValueError('finite IEEE754-range number required') from exc
    return x


def prediction_number(value):
    number(value)  # Explicit finite-binary64 magnitude rule, before exact Decimal comparison.
    return Decimal(str(value))


def opaque(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{32}', value), 'opaque ID required')
    return value


def stim(value):
    need(type(value) is dict, 'stimulus object')
    if value == {'kind': 'click'}:
        return 'click'
    need(set(value) == {'kind', 'frequency_hz'} and value['kind'] == 'tone', 'stimulus schema')
    f = number(value['frequency_hz'])
    need(f in TONES, 'unknown target tone')
    return 'tone:' + str(int(f))


@contextlib.contextmanager
def pinned_open(path, pin):
    """Hash one stable, regular, single-link descriptor and retain it for use."""
    path = Path(path)
    # Reject symlink components, including an otherwise innocuous parent alias.
    for part in (path, *path.parents):
        need(not part.is_symlink(), 'symlink in operator path')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'regular single-link input required')
        need(before.st_size == pin[0], 'input size differs')
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
        need(digest.hexdigest() == pin[1], 'input digest differs')
        after = os.fstat(stream.fileno())
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'input changed')
        stream.seek(0)
        yield stream
        final = os.fstat(stream.fileno())
        need((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) ==
             (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns, final.st_ctime_ns), 'input changed during use')


def read_pin(path, pin):
    with pinned_open(path, pin) as stream:
        return stream.read()


def load_raster(repository):
    raw = read_pin(Path(repository) / RASTER_PATH, RASTER_PIN)
    module = types.ModuleType('abr_pinned_raster')
    exec(compile(raw, RASTER_PATH, 'exec'), module.__dict__)
    return module


def jsonl(stream, cap):
    total = 0
    for line in stream:
        total += len(line)
        need(total <= cap and len(line) <= 65536 and line.endswith(b'\n'), 'JSONL expansion/line cap')
        yield decode(line)


class Roster:
    """Structural complete-roster validation; never authenticates source identity."""
    def __init__(self, cases, traces, *, samples=1953, trace_count=16226):
        need(len(cases) == 936 and len(traces) == trace_count, 'complete case/trace denominator')
        self.cases, self.traces = {}, {}
        offset = 0
        for row in traces:
            need(set(row) == {'trace_id', 'sample_offset', 'sample_count', 'stimulus', 'level_db', 'axis', 'case_id'}, 'trace fields differ')
            tid = opaque(row['trace_id']); cid = opaque(row['case_id'])
            need(tid not in self.traces and type(row['sample_offset']) is int and row['sample_offset'] == offset, 'trace duplicate/gap/order')
            need(type(row['sample_count']) is int and row['sample_count'] == samples, 'native sample count')
            number(row['level_db']); stim(row['stimulus'])
            axis = row['axis']
            need(type(axis) is dict and set(axis) == {'kind', 'sample_period_ms', 'first_sample_ms', 'unit', 'reason'}, 'axis fields differ')
            need(axis['kind'] == 'sample_index' and all(axis[k] is None for k in ('sample_period_ms', 'first_sample_ms', 'unit')),
                 'invented physical calibration')
            need(axis['reason'] == 'release CSV contains no physical axis or voltage calibration', 'axis provenance differs')
            self.traces[tid] = json.loads(json.dumps(row))
            offset += samples
        seen = set()
        for row in cases:
            need(set(row) == {'case_id', 'stimulus', 'trace_ids', 'repeated_levels_preserved'}, 'case fields differ')
            cid = opaque(row['case_id']); stim(row['stimulus'])
            need(cid not in self.cases and type(row['trace_ids']) is list and 1 <= len(row['trace_ids']) <= 256, 'case duplicate/empty/oversize')
            levels = []
            for tid in row['trace_ids']:
                need(tid in self.traces and tid not in seen, 'missing/duplicate trace join')
                t = self.traces[tid]
                need(t['case_id'] == cid and stim(t['stimulus']) == stim(row['stimulus']), 'case trace mismatch')
                seen.add(tid); levels.append(t['level_db'])
            need(type(row['repeated_levels_preserved']) is bool and row['repeated_levels_preserved'] == (len(levels) != len(set(levels))), 'repeat metadata differs')
            self.cases[cid] = json.loads(json.dumps(row))
        need(seen == set(self.traces), 'unclaimed traces')
        self.ids = tuple(self.cases)  # Preserve the complete observed order; do not invent a product.
        self.samples, self.trace_count, self.total_samples = samples, trace_count, offset
        self.identity = sha(canonical({'cases': cases, 'traces': traces}))
        self._identity = self.identity
        self._observed_ids = self.ids
        self._case_pins = {cid: sha(canonical({'case': row, 'traces': [self.traces[t] for t in row['trace_ids']]})) for cid, row in self.cases.items()}

    def verify_case(self, cid):
        need(self.ids == self._observed_ids and cid in self.cases, 'observed roster order changed')
        row = self.cases[cid]
        try:
            current = sha(canonical({'case': row, 'traces': [self.traces[t] for t in row['trace_ids']]}))
        except (KeyError, TypeError) as exc:
            raise ValueError('case join changed') from exc
        need(current == self._case_pins[cid], 'case/trace metadata changed')

    def verify(self):
        need(tuple(self.cases) == self.ids and len(self.cases) == 936 and len(self.traces) == self.trace_count, 'roster state changed')
        current = sha(canonical({'cases': list(self.cases.values()), 'traces': list(self.traces.values())}))
        need(self.identity == self._identity == current, 'roster contents changed')

    def packet(self, cid, reader):
        need(cid in self.cases, 'unknown case')
        case = self.cases[cid]
        result = {'case_id': cid, 'stimulus': case['stimulus'], 'axis': 'sample_index',
                  'amplitude_unit': 'native_raw_value', 'labelled_support_count': 0, 'traces': []}
        for tid in case['trace_ids']:
            meta = self.traces[tid]
            values = list(reader(meta))
            need(len(values) == self.samples, 'reader truncated native trace')
            for x in values:
                number(x)
            result['traces'].append({'trace_id': tid, 'release_level_code': meta['level_db'],
                                     'sample_indices': [0, self.samples - 1], 'samples': values})
        return result


class NativeTarget:
    """Fixed operator bundle adapter; does not grant candidate access or score admission.

    Native input pins cannot be replaced with a generated-fixture flag. Index and
    case bodies are read only when an operator explicitly constructs this object.
    Waveform decompression uses a retained read-only gzip descriptor; per-case
    random access may be expensive and has no authentic runtime qualification.
    """
    def __init__(self, root):
        self.root = Path(root)
        self.complete = decode(read_pin(self.root / 'COMPLETE.json', COMPLETE_PIN))
        c = self.complete
        need(c['target_animals'] == 104 and c['target_cases'] == 936 and c['candidate_delivery_admitted'] is False, 'completion identity')
        self.pins = {k: (c['files'][k]['bytes'], c['files'][k]['sha256']) for k in TARGET_KEYS}
        rows = []
        for name, cap in ((TARGET_KEYS[0], 2 * 1024**2), (TARGET_KEYS[1], 12 * 1024**2)):
            with pinned_open(self.root / name, self.pins[name]) as stream:
                with gzip.GzipFile(fileobj=stream) as gz:
                    rows.append(list(jsonl(gz, cap)))
        self.roster = Roster(*rows)
        self._stack = contextlib.ExitStack()
        try:
            stream = self._stack.enter_context(pinned_open(self.root / TARGET_KEYS[2], self.pins[TARGET_KEYS[2]]))
            self._waveform_stream = stream
            self._waveform_stat = os.fstat(stream.fileno())
            self._waveforms = self._stack.enter_context(gzip.GzipFile(fileobj=stream))
        except BaseException:
            self._stack.close(); raise
        self._targets_opened = False

    def close(self):
        self._stack.close()

    def _verify_observation_source(self, cid=None):
        self.roster.verify() if cid is None else self.roster.verify_case(cid)
        now = os.fstat(self._waveform_stream.fileno())
        before = self._waveform_stat
        need((now.st_dev, now.st_ino, now.st_size, now.st_mtime_ns, now.st_ctime_ns) ==
             (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns), 'waveform descriptor changed')

    def new_pair(self, destination, programme, documentation_path=None):
        docpath = Path(documentation_path) if documentation_path is not None else Path(__file__).with_name('COMMON_DOCUMENTATION.txt')
        documents = read_pin(docpath, COMMON_DOCUMENTATION_PIN)
        self._verify_observation_source()
        pair = Pair(destination, self.roster, self.packet, programme, documents, source_identity=COMPLETE_PIN[1])
        pair._native_target = self
        return pair

    def packet(self, cid):
        self._verify_observation_source(cid)
        def reader(meta):
            self._waveforms.seek(meta['sample_offset'] * 8)
            raw = self._waveforms.read(meta['sample_count'] * 8)
            need(len(raw) == meta['sample_count'] * 8, 'truncated waveform file')
            a = array.array('d'); a.frombytes(raw)
            if sys.byteorder != 'little':
                a.byteswap()
            return a
        return self.roster.packet(cid, reader)

    def score_sealed(self, pair):
        """The only production target opener: all 1872 first finals must be sealed."""
        need(getattr(pair, '_native_target', None) is self and pair.roster is self.roster, 'pair must originate from this native reader')
        need(getattr(pair.provider, '__self__', None) is self and getattr(pair.provider, '__func__', None) is NativeTarget.packet, 'substituted native packet provider')
        pair.verify_seal()
        self._verify_observation_source()
        need(pair.source_identity == COMPLETE_PIN[1] and pair._documents_pin == COMMON_DOCUMENTATION_PIN, 'pair source/document mismatch')
        need(not self._targets_opened, 'protected projection already opened')
        self._targets_opened = True
        name = TARGET_KEYS[3]
        with pinned_open(self.root / name, self.pins[name]) as stream:
            with gzip.GzipFile(fileobj=stream) as gz:
                references = list(jsonl(gz, 2 * 1024**2))
        result = pair.score(references)
        result['source_kind'] = 'fixed_release_operator_only'
        return result


def validate_packet(packet):
    need(type(packet) is dict and set(packet) == {'case_id', 'stimulus', 'axis', 'amplitude_unit', 'labelled_support_count', 'traces'}, 'packet fields differ')
    opaque(packet['case_id']); stim(packet['stimulus'])
    need(packet['axis'] == 'sample_index' and packet['amplitude_unit'] == 'native_raw_value' and packet['labelled_support_count'] == 0, 'packet axes/support differ')
    need(type(packet['traces']) is list and 1 <= len(packet['traces']) <= 256, 'packet traces')
    ids = set()
    for trace in packet['traces']:
        need(set(trace) == {'trace_id', 'release_level_code', 'sample_indices', 'samples'}, 'trace packet fields differ')
        opaque(trace['trace_id']); need(trace['trace_id'] not in ids, 'packet duplicate trace'); ids.add(trace['trace_id'])
        number(trace['release_level_code'])
        samples = trace['samples']
        need(type(samples) is list and 2 <= len(samples) <= 1953 and trace['sample_indices'] == [0, len(samples) - 1], 'sample coverage differs')
        for x in samples:
            number(x)


def panels(packet):
    validate_packet(packet)
    return tuple(tuple(range(i, min(i + 3, len(packet['traces'])))) for i in range(0, len(packet['traces']), 3))


def png(canvas, raster):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    w, h = raster.WIDTH, raster.HEIGHT
    raw = b''.join(b'\0' + canvas.pixels[y*w*3:(y+1)*w*3] for y in range(h))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def render(packet, page, raster):
    """No sample decimation, clipping, physical conversion, or trace omission.

    All samples and adjacent segments on one page are rasterized. All pages are
    enumerated by panels(); 1953 samples can share pixels, so the same full numeric
    packet is also available to each arm. Plot-only transport has lower precision.
    """
    pages = panels(packet)
    need(type(page) is int and 0 <= page < len(pages), 'invalid page')
    c = raster.Canvas()
    c.text(30, 20, 'ABR RELEASE ANNOTATION CODE AGREEMENT')
    c.text(30, 50, 'SAMPLE INDEX / NATIVE AMPLITUDE / RELEASE LEVEL CODES')
    c.text(30, 80, f'PAGE {page + 1} OF {len(pages)} / ZERO LABELLED SUPPORT')
    all_max = max(abs(float(v)) for t in packet['traces'] for v in t['samples'])
    scale = all_max if all_max else 1.0
    c.text(30, 112, 'SAME COMPLETE NUMERIC PACKET AVAILABLE IN BOTH ARMS', scale=1)
    drawn = 0
    for row, index in enumerate(pages[page]):
        t = packet['traces'][index]; values = t['samples']; middle = 230 + row * 220
        c.text(30, middle - 85, f'TRACE {index + 1} LEVEL {float(t["release_level_code"]):.12G}', scale=1)
        c.text(30, middle - 65, f'AMPLITUDE +/- {scale:.12G}', scale=1)
        c.line(180, middle, 1300, middle, raster.GRID)
        previous = None
        for i, value in enumerate(values):
            x = 180 + round(i * 1120 / (len(values) - 1))
            y = middle - round(float(value) / scale * 75)
            if previous is None:
                c.pixel(x, y, raster.BLUE)
            else:
                c.line(*previous, x, y, raster.BLUE)
            previous = (x, y); drawn += 1
        c.text(180, middle + 85, '0', scale=1)
        c.text(1170, middle + 85, str(len(values) - 1), scale=1)
    c.text(30, 788, 'SAMPLE INDICES ONLY. NO MILLISECOND OR VOLTAGE CALIBRATION.', scale=1)
    return png(c, raster), {'page': page, 'pages': len(pages), 'trace_indices': list(pages[page]),
                            'samples_drawn': drawn, 'native_amplitude_scale': scale}


class Viewer:
    """Case-local typed actions. New instance per case, no cross-case data cache."""
    def __init__(self, packet, raster):
        validate_packet(packet)
        self._raw = canonical(packet)
        self._raster = raster
    def action(self, action):
        need(type(action) is dict and type(action.get('type')) is str, 'typed viewer action')
        packet = decode(self._raw)
        if action == {'type': 'numeric'}:
            return self._raw
        if action == {'type': 'pages'}:
            return {'pages': len(panels(packet)), 'trace_count': len(packet['traces']), 'packet_sha256': sha(self._raw)}
        need(set(action) == {'type', 'page'} and action['type'] == 'page', 'unknown/extraneous viewer action')
        return render(packet, action['page'], self._raster)


def exclusive(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())


class Pair:
    """Durable operator first-final collector, never a participant sandbox.

    A frozen programme and common documentation are recorded before any case can
    be exposed. Both arms follow the same observed order, one complete case at a
    time. Every response, including invalid/oversized JSON, consumes that case.
    No per-case evaluator feedback exists. Target parsing waits for both full sets.
    """
    def __init__(self, destination, roster, packet_provider, programme, documents, *, source_identity):
        need(type(programme) is bytes and 0 < len(programme) <= 1024**2, 'programme bytes required')
        need(type(documents) is bytes and 0 < len(documents) <= 1024**2, 'common documentation required')
        need(type(source_identity) is str and re.fullmatch('[0-9a-f]{64}', source_identity), 'source identity required')
        roster.verify()
        self.root = Path(destination); need(not self.root.exists(), 'fresh pair directory required')
        self.root.mkdir(mode=0o700, parents=True)
        self.roster, self.provider, self.source_identity = roster, packet_provider, source_identity
        self._next = {'direct': 0, 'programme': 0}; self._active = {}; self._finals = {}; self._packets = {}
        self._sealed = None; self._scored = False
        exclusive(self.root / 'programme', programme); exclusive(self.root / 'documents', documents)
        self._programme_pin = (len(programme), sha(programme)); self._documents_pin = (len(documents), sha(documents))
        descriptor = {'mode': MODE, 'source_identity': source_identity, 'roster_sha256': roster.identity,
                      'programme_sha256': sha(programme), 'documents_sha256': sha(documents),
                      'case_count': 936, 'support_labels': 0, 'case_state': 'fresh per case; fixed programme',
                      'representation': 'same full numeric packet and optional complete plot pages', **HOLDS}
        self._descriptor = canonical(descriptor); exclusive(self.root / 'PAIR.json', self._descriptor)

    def expose(self, arm):
        native = getattr(self, '_native_target', None)
        if native is not None:
            need(getattr(self.provider, '__self__', None) is native and getattr(self.provider, '__func__', None) is NativeTarget.packet, 'substituted native packet provider before exposure')
        need(arm in self._next and self._sealed is None and self._next[arm] < 936, 'arm complete/unknown/sealed')
        need(arm not in self._active, 'current case must receive its first final')
        read_pin(self.root / 'programme', self._programme_pin)
        read_pin(self.root / 'documents', self._documents_pin)
        cid = self.roster.ids[self._next[arm]]
        self.roster.verify_case(cid)
        packet = self.provider(cid); validate_packet(packet)
        need(packet['case_id'] == cid, 'provider returned wrong case')
        expected = self.roster.cases[cid]
        need([t['trace_id'] for t in packet['traces']] == expected['trace_ids'] and stim(packet['stimulus']) == stim(expected['stimulus']), 'provider trace roster differs')
        for t in packet['traces']:
            meta = self.roster.traces[t['trace_id']]
            need(len(t['samples']) == meta['sample_count'] and t['release_level_code'] == meta['level_db'], 'provider sample/level mismatch')
        raw = canonical(packet); digest = sha(raw)
        need(cid not in self._packets or self._packets[cid] == digest, 'arms received different samples')
        self._packets[cid] = digest
        self._active[arm] = (cid, digest)
        return raw

    def submit(self, arm, cid, raw):
        need(arm in self._active and self._active[arm][0] == cid and self._sealed is None, 'no active first-final slot')
        need(type(raw) is bytes, 'transport body must be bytes')
        # Preserve invalid first responses; never disclose parse validity here.
        digest = sha(raw); too_large = len(raw) > MAX_FINAL
        record = canonical({'case_id': cid, 'raw_hex': raw[:MAX_FINAL].hex(),
                            'raw_sha256': digest, 'oversized': too_large,
                            'observation_sha256': self._active[arm][1]})
        name = arm + '-' + cid + '.json'
        exclusive(self.root / name, record)
        self._finals[(arm, cid)] = (len(record), sha(record))
        del self._active[arm]; self._next[arm] += 1
        return {'accepted_first_final': True}

    def seal(self):
        need(self._sealed is None and not self._active and set(self._next.values()) == {936}, 'both complete first-final sets required')
        need(len(self._finals) == 1872 and len(self._packets) == 936, 'pair coverage differs')
        read_pin(self.root / 'programme', self._programme_pin); read_pin(self.root / 'documents', self._documents_pin)
        for (arm, cid), pin in self._finals.items():
            read_pin(self.root / (arm + '-' + cid + '.json'), pin)
        body = canonical({'pair_sha256': sha(self._descriptor), 'observation_sha256': sha(canonical(self._packets)),
                          'finals_sha256': sha(canonical({a + ':' + c: p[1] for (a, c), p in self._finals.items()})),
                          'first_final_count': 1872})
        exclusive(self.root / 'SEALED.json', body); self._sealed = (len(body), sha(body))
        return decode(body)

    def verify_seal(self):
        self.roster.verify()
        need(self._sealed is not None, 'target-last: complete pair is not sealed')
        read_pin(self.root / 'SEALED.json', self._sealed)
        read_pin(self.root / 'PAIR.json', (len(self._descriptor), sha(self._descriptor)))
        read_pin(self.root / 'programme', self._programme_pin); read_pin(self.root / 'documents', self._documents_pin)
        for (arm, cid), pin in self._finals.items():
            read_pin(self.root / (arm + '-' + cid + '.json'), pin)

    def score(self, references):
        """Only NativeTarget.score_sealed supplies fixed-release production labels.

        Direct calls are unverified operator arithmetic. Only the native adapter
        may label its own separately bound result as fixed-release operator input.
        """
        self.verify_seal(); need(not self._scored, 'pair already scored'); self._scored = True
        refs = validate_references(references, self.roster)
        result = {'mode': MODE, 'source_kind': 'unverified_operator_arithmetic', 'case_count': 936, 'animal_count': 104,
                  'target_100_count': sum(r['code'] == 100 for r in refs.values()), 'arms': {}, **HOLDS}
        for arm in self._next:
            predictions, failure = {}, []
            for cid in self.roster.ids:
                rec = decode(read_pin(self.root / (arm + '-' + cid + '.json'), self._finals[(arm, cid)]))
                try:
                    need(not rec['oversized'], 'oversized first final')
                    raw = bytes.fromhex(rec['raw_hex']); need(sha(raw) == rec['raw_sha256'], 'response hash differs')
                    value = decode(raw, decimal=True)
                    need(type(value) is dict and set(value) == {'case_id', 'predicted_annotation_code'} and value['case_id'] == cid, 'prediction schema/ID')
                    predictions[cid] = prediction_number(value['predicted_annotation_code'])
                except (ValueError, TypeError, KeyError, InvalidOperation, RecursionError):
                    failure.append(cid)
            output = {'coverage': {'required': 936, 'valid': len(predictions), 'invalid': len(failure)},
                      'failure_case_ids': failure, 'aggregate_withheld': bool(failure)}
            if not failure:
                output['metrics'] = metrics(refs, predictions)
                output['strata'] = {
                    'background': {g: metrics({c:r for c,r in refs.items() if r['background'] == g}, predictions) for g in sorted(BACKGROUND_COUNTS)},
                    'stimulus': {s: metrics({c:r for c,r in refs.items() if r['stimulus'] == s}, predictions) for s in sorted({r['stimulus'] for r in refs.values()})},
                    'source_code_100': metrics({c:r for c,r in refs.items() if r['code'] == 100}, predictions)}
            result['arms'][arm] = output
        return result


def validate_references(rows, roster):
    need(type(rows) is list and len(rows) == 936, 'complete protected reference denominator')
    refs, animals, joined = {}, {}, set()
    for r in rows:
        need(type(r) is dict and set(r) == {'case_id', 'animal_source_id', 'animal_id', 'genetic_background', 'annotation', 'observed_level_min', 'observed_level_max', 'outside_observed_levels', 'score_admission'}, 'native reference fields differ')
        cid = opaque(r['case_id']); aid = opaque(r['animal_id'])
        need(cid in roster.cases and cid not in refs, 'reference case join differs')
        source = r['animal_source_id']; background = r['genetic_background']
        need(type(source) is int and 1 <= source <= 104 and background == ('C57BL/6NTacCdh23+' if source <= 54 else 'C57BL/6N'), 'animal/background source join differs')
        need(r['score_admission'] is False, 'original native admission must remain false')
        need(aid not in animals or animals[aid] == (source, background), 'animal alias differs')
        animals[aid] = (source, background)
        a = r['annotation']
        need(type(a) is dict and set(a) == {'stimulus', 'raw_token', 'source_numeric_value', 'semantics', 'source_line', 'source_column'}, 'annotation schema differs')
        s = stim(a['stimulus']); need(s == stim(roster.cases[cid]['stimulus']) and (aid, s) not in joined, 'animal stimulus duplicate/mismatch')
        joined.add((aid, s)); code = number(a['source_numeric_value'])
        need(type(a['raw_token']) is str and 0 < len(a['raw_token']) <= 128, 'raw source token')
        try:
            token = Decimal(a['raw_token']); need(token.is_finite() and token == Decimal(str(code)), 'source token/value differs')
        except InvalidOperation as exc:
            raise ValueError('invalid source numeric token') from exc
        need(a['semantics'] == 'unresolved_exact_or_censored', 'source semantics rewritten')
        need(type(a['source_line']) is int and a['source_line'] >= 2 and type(a['source_column']) is str, 'source annotation provenance')
        levels = [roster.traces[t]['level_db'] for t in roster.cases[cid]['trace_ids']]
        need(r['observed_level_min'] == min(levels) and r['observed_level_max'] == max(levels), 'recorded level bounds differ')
        need(type(r['outside_observed_levels']) is bool and r['outside_observed_levels'] == (code < min(levels) or code > max(levels)), 'outside-level metadata differs')
        refs[cid] = {'animal': aid, 'background': background, 'stimulus': s, 'code': code}
    need(set(refs) == set(roster.ids) and len(animals) == 104 and {a[0] for a in animals.values()} == set(range(1, 105)), 'complete animal/case correspondence differs')
    need({g: sum(a[1] == g for a in animals.values()) for g in BACKGROUND_COUNTS} == BACKGROUND_COUNTS, 'background denominator differs')
    return refs


def metrics(refs, predictions):
    groups = {}
    with localcontext() as context:
        context.prec = 350  # Finite binary64 magnitude inputs; stable sums without overflow.
        for cid, r in refs.items():
            p, t = Decimal(str(predictions[cid])), Decimal(str(r['code']))
            error = abs(p - t)
            groups.setdefault(r['animal'], []).append((int(p == t), error, int(error <= 5), int(error <= 10)))
        if not groups:
            return {'case_count': 0, 'animal_count': 0, 'metrics': None}
        values = [sum(sum(Decimal(row[j]) for row in rows) / len(rows) for rows in groups.values()) / len(groups) for j in range(4)]
        distance = float(values[1])
        distance_ok = math.isfinite(distance)
        return {'case_count': len(refs), 'animal_count': len(groups), 'animal_macro_exact_numeric_code_agreement': float(values[0]),
                'animal_macro_code_mae': distance if distance_ok else None,
                'secondary_distance_status': 'finite' if distance_ok else 'not_representable_as_finite_binary64', 'animal_macro_within_5_code_units': float(values[2]),
                'animal_macro_within_10_code_units': float(values[3]), 'distance_units': 'annotation-code units; not physical dB'}
