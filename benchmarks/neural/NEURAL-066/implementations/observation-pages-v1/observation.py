"""Bounded target-free pages for an existing NEURAL-066 diagnostic INPUT.

This is an observation/response component, not a sandbox, scorer or model actor.
Only standard-library code is loaded. No operator package is imported.
"""
import argparse
import ast
import hashlib
import html
import itertools
import json
import math
import os
from pathlib import Path
import re
import select
import stat
import struct
import sys
import time

ARMS = ('TIMING', 'EOG', 'NEURAL_PRE', 'NEURAL', 'NEURAL_POST', 'SHUFFLE')
MODES = ('frozen_program', 'case_adaptive_equal_inputs_tools_compute')
CHANNELS = {'MEG': 306, 'EEG': 61}
CHARS = ('s', 'o', 't', 'e', 'n', 'c', 'i', 'a', ' ', 'd', 'l', 'r', 'b', '@',
         'z', 'v', 'f', 'm', 'u', 'h', 'p', 'g', 'q', 'w', 'x', 'y', 'j', 'k', '9')
WINDOWS = {'NEURAL_PRE': [-0.7, -0.2], 'NEURAL': [-0.2, 0.3],
           'NEURAL_POST': [0.3, 0.8], 'SHUFFLE': [-0.2, 0.3], 'EOG': [-0.2, 0.3]}
TIMING = ['duration_seconds', 'previous_onset_interval_seconds', 'first_key_indicator']
LIMIT_FIELDS = {'read_bytes', 'metadata_bytes', 'response_bytes', 'wall_seconds'}
INPUT_FIELDS = {'case', 'generation', 'condition', 'arm', 'mode', 'modality', 'channels',
                'feature_dimensions', 'samples_per_key', 'feature_spec', 'support_commitment',
                'source_contract_pin', 'projection_pin', 'language_policy_pin', 'schema',
                'task', 'realm', 'arrays', 'geometry', 'event_assisted', 'full_current_case_batch',
                'zero_labeled_target_person_calibration', 'training_layout', 'queries'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def exact(value, fields, message):
    need(type(value) is dict and set(value) == set(fields), message)


def integer(value, low, high, message):
    need(type(value) is int and low <= value <= high, message)
    return value


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def descriptor(value):
    exact(value, ('bytes', 'sha256'), 'Exact byte/digest pin')
    integer(value['bytes'], 1, 2**63 - 1, 'Positive bounded byte extent')
    need(type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
         'Lowercase SHA256 pin')
    return value


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON field')
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False) + '\n').encode()


def signature(s):
    return tuple(getattr(s, k) for k in ('st_dev', 'st_ino', 'st_mode', 'st_nlink',
                                       'st_size', 'st_mtime_ns', 'st_ctime_ns'))


class Reader:
    def __init__(self, root, limits):
        exact(limits, LIMIT_FIELDS, 'Explicit read/metadata/response/time limits required')
        for key in LIMIT_FIELDS:
            integer(limits[key], 1, 2**63 - 1, 'Positive integer limit: ' + key)
        self.root = Path(root).resolve(strict=True)
        need(self.root.is_dir(), 'Prepared public input directory')
        self.limits = limits
        self.reads = 0
        self.started = time.monotonic()

    def tick(self):
        need(time.monotonic() - self.started <= self.limits['wall_seconds'], 'Observation deadline')

    def open(self, name, expected):
        need(name in ('INPUT.json', 'GEOMETRY.json', 'TRAIN_LAYOUT.json', 'train.npy', 'query.npy'),
             'Only fixed public packet names')
        descriptor(expected)
        self.tick()
        need(self.reads + expected['bytes'] <= self.limits['read_bytes'], 'Read reservation exhausted')
        # Charge the whole prospective extent, including failed/short reads.
        self.reads += expected['bytes']
        path = self.root / name
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_size == expected['bytes'],
                 'Exact regular public extent')
            return fd, before
        except BaseException:
            os.close(fd)
            raise

    def stable(self, fd, before, name):
        need(signature(before) == signature(os.fstat(fd)) == signature((self.root / name).lstat()),
             'Complete stable named public capture')
        self.tick()

    def document(self, name, expected):
        need(expected['bytes'] <= self.limits['metadata_bytes'], 'Metadata byte limit')
        fd, before = self.open(name, expected)
        try:
            raw = bytearray()
            while len(raw) < expected['bytes']:
                self.tick()
                block = os.read(fd, min(65536, expected['bytes'] - len(raw)))
                need(block, 'Short metadata capture')
                raw.extend(block)
            self.stable(fd, before, name)
            need(pin(raw) == expected, 'Exact public metadata hash')
            return strict(raw)
        finally:
            os.close(fd)

    def matrix_page(self, name, desc, wanted, dimensions):
        """Stream-authenticate the full array; retain only requested exact float32s."""
        expected = {k: desc[k] for k in ('bytes', 'sha256')}
        fd, before = self.open(name, expected)
        digest = hashlib.sha256()
        values = {}
        try:
            def take(n):
                raw = os.read(fd, n)
                need(len(raw) == n, 'Short array capture')
                digest.update(raw)
                return raw
            prefix = take(10)
            need(prefix[:8] == b'\x93NUMPY\x01\x00', 'Primitive NPY1 only')
            length = struct.unpack('<H', prefix[8:])[0]
            need(10 + length <= expected['bytes'], 'Bounded complete NPY header')
            header = ast.literal_eval(take(length).decode('latin1'))
            exact(header, ('descr', 'shape', 'fortran_order'), 'Exact primitive array header')
            need(header['descr'] == '<f4' and header['fortran_order'] is False and
                 type(header['shape']) is tuple and list(header['shape']) == desc['shape'] and
                 all(type(v) is int for v in header['shape']), 'Exact C-order float32 axes')
            rows, cols = desc['shape']
            need(10 + length + rows * cols * 4 == expected['bytes'], 'No truncated/trailing array bytes')
            remaining, index = rows * cols * 4, 0
            while remaining:
                self.tick()
                block = take(min(65536, remaining))
                for (value,) in struct.iter_unpack('<f', block):
                    need(math.isfinite(value), 'All public matrix entries finite')
                    column = index % cols
                    if name == 'train.npy' and column == dimensions:
                        need(value.is_integer() and 0 <= value < 29, 'Every training label maps to 29 classes')
                    if name == 'train.npy' and column == dimensions + 1:
                        need(value > 0, 'Every original training weight positive')
                    if index in wanted:
                        values[index] = value
                    index += 1
                remaining -= len(block)
            self.stable(fd, before, name)
            need(digest.hexdigest() == expected['sha256'], 'Exact complete public matrix hash')
            need(set(values) == wanted, 'Every requested coordinate delivered')
            return values
        finally:
            os.close(fd)


def relative_pin(value, name, array=False):
    fields = {'path', 'bytes', 'sha256'} | ({'shape', 'dtype'} if array else set())
    exact(value, fields, 'Exact public file descriptor')
    need(value['path'] == name, 'Fixed public file path')
    result = descriptor({k: value[k] for k in ('bytes', 'sha256')})
    if array:
        need(value['dtype'] == '<f4' and type(value['shape']) is list and len(value['shape']) == 2,
             'Public float32 matrix descriptor')
        for n in value['shape']:
            integer(n, 1, 2**63 - 1, 'Positive matrix axis')
    return result


def layout(rows, training, count):
    need(type(rows) is list and rows, 'Complete nonempty public sentence layout')
    seen, at = set(), 0
    fields = {'id', 'begin', 'n_keys'} | ({'person', 'session', 'template'} if training else set())
    for row in rows:
        exact(row, fields, 'Only declared opaque public sentence fields')
        for key in fields - {'begin', 'n_keys'}:
            need(type(row[key]) is str and re.fullmatch('[0-9a-f]{64}', row[key]), 'Case-scoped opaque token')
        need(row['id'] not in seen and type(row['begin']) is int and row['begin'] == at,
             'Unique contiguous complete sentence partition')
        seen.add(row['id'])
        at += integer(row['n_keys'], 1, 256, 'Original complete sentence key count')
    need(at == count, 'All matrix rows represented exactly once')
    return rows


def packet(reader, input_pin):
    doc = reader.document('INPUT.json', descriptor(input_pin))
    exact(doc, INPUT_FIELDS, 'Only complete diagnostic public INPUT fields')
    need(doc['schema'] == 'neural066_candidate_input_v3' and doc['task'] == 'NEURAL-066' and
         doc['realm'] == 'diagnostic' and doc['mode'] in MODES and doc['condition'] in ARMS and
         doc['arm'] == doc['condition'] and doc['modality'] in CHANNELS,
         'Exact existing current-case public diagnostic input')
    need(doc['event_assisted'] is True and doc['full_current_case_batch'] is True and
         doc['zero_labeled_target_person_calibration'] is True, 'Original assistance and calibration scope')
    for name in ('case', 'generation', 'support_commitment'):
        need(type(doc[name]) is str and re.fullmatch('[0-9a-f]{64}', doc[name]), 'Opaque current-case identity')
    for name in ('source_contract_pin', 'projection_pin', 'language_policy_pin'):
        descriptor(doc[name])
    exact(doc['arrays'], ('train.npy', 'query.npy'), 'Complete training and query entitlement')
    for name in ('train.npy', 'query.npy'):
        relative_pin(doc['arrays'][name], name, array=True)
    d = doc['feature_dimensions']
    integer(d, 1, 306 * 25, 'Original feature dimension')
    need(doc['arrays']['train.npy']['shape'][1] == d + 2 and
         doc['arrays']['query.npy']['shape'][1] == d, 'Training-only labels and weights; no query target column')
    spec, arm = doc['feature_spec'], doc['arm']
    if arm == 'TIMING':
        need(spec == {'kind': 'timing3', 'dimensions': 3, 'features': TIMING,
                      'units': ['seconds', 'seconds', 'indicator'], 'samples_per_key': 1, 'geometry': None}
             and doc['channels'] == [] and type(doc['samples_per_key']) is int and doc['samples_per_key'] == 1
             and d == 3, 'Exact timing features and units')
    else:
        exact(spec, ('kind', 'dimensions', 'channel_names', 'channel_types', 'samples_per_key',
                     'window_seconds', 'geometry'), 'Exact channel-window features')
        names, types = spec['channel_names'], spec['channel_types']
        need(type(names) is list and names and len(set(names)) == len(names) and
             all(type(x) is str and x for x in names), 'All unique original channels')
        need(type(types) is list and len(types) == len(names) and all(type(x) is str and x for x in types),
             'All original channel types')
        need((1 <= len(names) <= 8) if arm == 'EOG' else len(names) == CHANNELS[doc['modality']],
             'Complete original channel count; no substitute/padded geometry')
        need(spec['kind'] == 'channel_window' and type(spec['dimensions']) is int and
             spec['dimensions'] == d == len(names) * 25 and type(spec['samples_per_key']) is int and
             spec['samples_per_key'] == doc['samples_per_key'] == 25 and
             spec['window_seconds'] == WINDOWS[arm] and doc['channels'] == names and
             spec['geometry'] == (None if arm == 'EOG' else 'source_authenticated_neural'),
             'Exact flattened channel-major 25-bin window')
    geo = reader.document('GEOMETRY.json', relative_pin(doc['geometry'], 'GEOMETRY.json'))
    fields = {'schema', 'modality', 'channel_names', 'channel_types', 'positions'}
    spatial = arm not in ('EOG', 'TIMING')
    exact(geo, fields | ({'source_method', 'layout_kind'} if spatial else {'kind', 'R2_supported'}),
          'Exact existing public geometry schema')
    names = [] if arm == 'TIMING' else spec['channel_names']
    types = [] if arm == 'TIMING' else spec['channel_types']
    need(geo['modality'] == doc['modality'] and geo['channel_names'] == names and geo['channel_types'] == types,
         'Same declared channel/geometry order')
    if spatial:
        need(geo['schema'] == 'neural066_geometry_v1' and type(geo['positions']) is list and
             len(geo['positions']) == len(names) and all(type(p) is list and len(p) == 2 and
             all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1 for x in p)
             for p in geo['positions']), 'Complete original normalized 2D geometry')
        need(geo['source_method'] == 'MNE1.11.0 minimalInfo/find_layout per-axis minmax; fullcoverage'
             and type(geo['layout_kind']) is str and geo['layout_kind'], 'Original geometry semantics')
    else:
        need(geo['schema'] == 'neural066_nonspatial_features_v1' and geo['positions'] is None and
             geo['kind'] == spec['kind'] and geo['R2_supported'] is False, 'No invented control geometry')
    training = reader.document('TRAIN_LAYOUT.json', relative_pin(doc['training_layout'], 'TRAIN_LAYOUT.json'))
    exact(training, ('schema', 'sentences'), 'Exact training layout')
    need(training['schema'] == 'neural066_train_layout_v1', 'Original training layout schema')
    train = layout(training['sentences'], True, doc['arrays']['train.npy']['shape'][0])
    query = layout(doc['queries'], False, doc['arrays']['query.npy']['shape'][0])
    need(not ({r['id'] for r in train} & {r['id'] for r in query}), 'Disjoint training/query sentence IDs')
    return doc, geo, {'train': train, 'query': query}


def coordinate(doc, geo, index):
    spec = doc['feature_spec']
    if doc['arm'] == 'TIMING':
        return f"{index}: {spec['features'][index]} ({spec['units'][index]})"
    channel, bin_index = divmod(index, 25)
    start_ms = round(1000 * spec['window_seconds'][0]) + 20 * bin_index
    geometry = '' if geo['positions'] is None else f"; normalized layout xy={geo['positions'][channel]!r}"
    # Source stores MNE native amplitudes but publishes no physical-unit column.
    # Explicitly disclose that gap instead of inventing or rescaling units.
    return (f"{index}: {spec['channel_names'][channel]} ({spec['channel_types'][channel]}); "
            f"bin {bin_index} [{start_ms},{start_ms + 20}) ms; native stored amplitude "
            f"(physical unit not encoded by producer){geometry}")


def table(headers, rows, cap):
    # Iterate coordinates lazily: a long metadata label must not be expanded
    # into an unbounded collection of repeated headers before the cap check.
    parts, size = [], 0
    def add(text):
        nonlocal size
        size += len(text.encode('utf-8'))
        need(size <= cap, 'Rendered table exceeds response ceiling')
        parts.append(text)
    def cell(tag, value):
        text = str(value)
        need(len(text) <= cap - size, 'Rendered cell exceeds remaining response ceiling')
        escaped = html.escape(text, quote=True)
        add('<' + tag + '>' + escaped + '</' + tag + '>')
    add('<table><thead><tr>')
    for header in headers:
        cell('th', header)
    add('</tr></thead><tbody>')
    for row in rows:
        add('<tr>')
        for value in row:
            cell('td', value)
        add('</tr>')
    add('</tbody></table>')
    return ''.join(parts)


def response(doc, body):
    exact(body, ('format', 'task', 'generation', 'case', 'arm', 'sentences'), 'Exact original response envelope')
    need(body['format'] == 'typing_predictions_v1' and body['task'] == 'NEURAL-066' and
         all(body[k] == doc[k] for k in ('generation', 'case', 'arm')), 'Response belongs to exact public case/arm')
    wanted = {r['id']: r['n_keys'] for r in doc['queries']}
    need(type(body['sentences']) is list and len(body['sentences']) == len(wanted), 'Every query sentence required')
    seen = set()
    for row in body['sentences']:
        exact(row, ('id', 'p'), 'Exact sentence probability output')
        need(type(row['id']) is str and row['id'] in wanted and row['id'] not in seen,
             'Unique original query sentence')
        seen.add(row['id'])
        need(type(row['p']) is list and len(row['p']) == wanted[row['id']], 'Every original query key required')
        for vector in row['p']:
            need(type(vector) is list and len(vector) == 29 and all(type(x) in (int, float) and
                 math.isfinite(x) and 0 <= x <= 1 for x in vector) and abs(sum(vector) - 1) <= 1e-6,
                 '29 finite probabilities summing to one; no repair')
    return {'complete_case_response': True, 'query_sentences': len(wanted),
            'query_keys': sum(wanted.values()), 'score': None, 'campaign_complete': False}


def present(root, input_pin, action, limits):
    """Allowlisted page or local response check. Caller owns transport/campaign budget."""
    return render(Reader(root, limits), input_pin, action)


def render(reader, input_pin, action):
    try:
        return _render(reader, input_pin, action)
    except BaseException as error:
        # Preserve reservations even when no page can be returned. The caller
        # must retain failures instead of retrying with a fresh campaign budget.
        error.observation_costs = {'reserved_read_bytes': reader.reads,
                                   'elapsed_seconds': time.monotonic() - reader.started}
        raise


def _render(reader, input_pin, action):
    limits = reader.limits
    need(type(action) is dict and type(action.get('action')) is str, 'Typed action required')
    doc, geo, layouts = packet(reader, input_pin)
    kind = action['action']
    base = {'schema': 'neural066_observation_page_v1', 'task': 'NEURAL-066',
            'case': doc['case'], 'generation': doc['generation'], 'arm': doc['arm'],
            'modality': doc['modality'], 'source_mode': doc['mode'],
            'support_commitment': doc['support_commitment'], 'input_pin': input_pin,
            'scientific_qualified': False, 'restricted_transport_qualified': False,
            'direct_interpretation_measured': False, 'campaign_complete': False}
    if kind == 'overview':
        exact(action, ('action',), 'Exact overview action')
        rows = [[realm, len(layouts[realm]), doc['arrays'][realm + '.npy']['shape'][0]]
                for realm in ('train', 'query')]
        body = ('<p>Event-assisted observed-key prediction; known sentence lengths and order. '
                'All same-case training calibration is available. No target-person labels. '
                'Class indices follow the exact public 29-class order below. '
                'Window comparisons do not identify physiological latency.</p>' +
                table(['Class index', 'Mapped character'], enumerate(CHARS), limits['response_bytes']) +
                table(['Realm', 'Sentences', 'Keys'], rows, limits['response_bytes']))
        if doc['arm'] == 'SHUFFLE':
            body += '<p>SHUFFLE retains original labels/weights; prepared training neural vectors are permuted. Query equals NEURAL.</p>'
        base.update(html=body, feature_dimensions=doc['feature_dimensions'],
                    actions=['overview', 'sentences', 'features', 'values', 'check_response'])
    elif kind == 'sentences':
        exact(action, ('action', 'realm', 'offset', 'count'), 'Exact sentence page action')
        need(action['realm'] in layouts, 'Training or query realm')
        rows = layouts[action['realm']]
        start = integer(action['offset'], 0, len(rows) - 1, 'Sentence page start')
        count = integer(action['count'], 1, 64, 'Sentence page count')
        need(start + count <= len(rows), 'Exact page within complete support')
        keys = ['id', 'begin', 'n_keys'] + (['person', 'session', 'template'] if action['realm'] == 'train' else [])
        base.update(html=table(keys, ([r[k] for k in keys] for r in rows[start:start + count]), limits['response_bytes']),
                    total_sentences=len(rows), next_offset=start + count if start + count < len(rows) else None)
    elif kind == 'features':
        exact(action, ('action', 'offset', 'count'), 'Exact feature page action')
        start = integer(action['offset'], 0, doc['feature_dimensions'] - 1, 'Feature page start')
        count = integer(action['count'], 1, 64, 'Feature page count')
        need(start + count <= doc['feature_dimensions'], 'No reduced or padded feature support')
        base.update(html=table(['Coordinate'], ([coordinate(doc, geo, i)] for i in range(start, start + count)), limits['response_bytes']),
                    total_features=doc['feature_dimensions'],
                    next_offset=start + count if start + count < doc['feature_dimensions'] else None)
    elif kind == 'values':
        exact(action, ('action', 'realm', 'sentence', 'key_offset', 'key_count', 'feature_offset', 'feature_count'),
              'Exact numerical page action')
        need(action['realm'] in layouts and type(action['sentence']) is str, 'Declared realm and opaque sentence')
        lookup = {r['id']: r for r in layouts[action['realm']]}
        need(action['sentence'] in lookup, 'Current-case sentence only')
        row = lookup[action['sentence']]
        k0 = integer(action['key_offset'], 0, row['n_keys'] - 1, 'Key page start')
        nk = integer(action['key_count'], 1, 4, 'Bounded key page')
        f0 = integer(action['feature_offset'], 0, doc['feature_dimensions'] - 1, 'Feature page start')
        nf = integer(action['feature_count'], 1, 64, 'Bounded feature page')
        need(k0 + nk <= row['n_keys'] and f0 + nf <= doc['feature_dimensions'], 'Exact full coordinate range')
        training = action['realm'] == 'train'
        name = action['realm'] + '.npy'
        d = doc['feature_dimensions']
        width = d + 2 if training else d
        columns = list(range(f0, f0 + nf)) + ([d, d + 1] if training else [])
        wanted = {(row['begin'] + k) * width + f for k in range(k0, k0 + nk) for f in columns}
        values = reader.matrix_page(name, doc['arrays'][name], wanted, d)
        headers = itertools.chain(['Key ordinal'],
                                  (coordinate(doc, geo, f) for f in range(f0, f0 + nf)),
                                  ['Observed training class index', 'Original training weight'] if training else [])
        rows = [[k] + [repr(values[(row['begin'] + k) * width + f]) for f in columns]
                for k in range(k0, k0 + nk)]
        base.update(html=table(headers, rows, limits['response_bytes']), exact_float32_values=True,
                    offered_sentence_keys=row['n_keys'], offered_features=d,
                    query_targets_delivered=False, complete_matrix_hash_checked=True)
    elif kind == 'check_response':
        exact(action, ('action', 'predictions'), 'Exact response-check action')
        base.update(response(doc, action['predictions']))
    else:
        raise ValueError('Unsupported typed observation action')
    reader.tick()
    base['reserved_read_bytes'] = reader.reads
    need(len(encoded(base)) <= limits['response_bytes'], 'Complete response fits ceiling; never truncate')
    return base


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--input-root', required=True)
    parser.add_argument('--input-bytes', required=True, type=int)
    parser.add_argument('--input-sha256', required=True)
    parser.add_argument('--read-bytes', required=True, type=int)
    parser.add_argument('--metadata-bytes', required=True, type=int)
    parser.add_argument('--response-bytes', required=True, type=int)
    parser.add_argument('--wall-seconds', required=True, type=int)
    args = parser.parse_args()
    limits = {'read_bytes': args.read_bytes, 'metadata_bytes': args.metadata_bytes,
              'response_bytes': args.response_bytes, 'wall_seconds': args.wall_seconds}
    # Validate every cap and start the clock before stdin effects. Reserve the
    # entire bounded ingress including the extra byte used to detect overflow.
    reader = Reader(args.input_root, limits)
    cap = limits['metadata_bytes'] + 1
    need(cap <= limits['read_bytes'], 'Action ingress reservation exhausted')
    reader.reads += cap
    raw = bytearray()
    fd = sys.stdin.fileno()
    while len(raw) < cap:
        reader.tick()
        remaining = limits['wall_seconds'] - (time.monotonic() - reader.started)
        ready, _, _ = select.select([fd], [], [], max(0, remaining))
        need(ready, 'Action ingress deadline')
        block = os.read(fd, min(65536, cap - len(raw)))
        if not block:
            break
        raw.extend(block)
    reader.tick()
    need(len(raw) <= limits['metadata_bytes'], 'Complete action byte limit')
    answer = render(reader, {'bytes': args.input_bytes, 'sha256': args.input_sha256}, strict(raw))
    sys.stdout.buffer.write(encoded(answer))


if __name__ == '__main__':
    main()
