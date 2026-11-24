"""Operator-only complete full32 adaptive-gain observation; no model or scoring.

Only participant_projection() is participant-facing. Capture is not a sandbox.
Production admits the original packet, all four demos, and all 6400 queries.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import struct
import sys
import time
import types
import zlib

HERE = Path(__file__).resolve().parent
PREFIX = 'benchmarks/neural/NEURAL-077/implementations/'
CONDITION = 'erp-full32-first-unclipped-gain-observation-v1'
GAINS = (20, 50, 100, 200, 500, 1000)
COUNT = 6400
MANIFEST = {'bytes': 5428, 'sha256': '241870678fed37fca67cc9c64e2e3a0830e0a97f9815332e27fa3018ed6c9f3f'}
DEMO_LABELS = (0, 1, 0, 1)
DEPENDENCIES = {'viewer': 'visual-viewer-v1/viewer.py', 'raster': 'visual-viewer-v1/raster.py',
    'codec': 'visual-provider-pair-v1/transfer_png.py', 'consumer': 'full32-paired-benchmark-v1/consumer.py',
    'actions': 'visual-viewer-v1/actions.schema.json'}
WARNING = 'CLIPPED: INCREASE UNITS/DIV'
POLICY = {'condition': CONDITION, 'gains': list(GAINS), 'selection': 'first_both_channel_warning_absent_else_cap_clipped',
    'samples_half_open': [-256, 768], 'sampling_hz': 1024, 'channels': ['Cz', 'Pz'],
    'display_filter': 'none', 'queries': COUNT, 'people': 32, 'queries_per_person': 200,
    'demonstrations': 4, 'same_rule_for_demos_and_queries': True,
    'population': 'predefined_32_person_complement_to_six_training_and_two_development_people',
    'observation_only': True, 'query_labels_available': False, 'automatic_retry': False,
    'same_information_budget_as_fixed_gain20': False, 'guaranteed_full_visibility': False,
    'native_units_are_known_microvolts': False, 'isolation_qualified': False}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def decode(body):
    def unique(items):
        out = {}
        for key, value in items:
            need(key not in out, 'Duplicate JSON field')
            out[key] = value
        return out
    return json.loads(body, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def descriptor(value, cap):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'} and
         type(value['bytes']) is int and 0 < value['bytes'] <= cap and
         type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'Exact bounded pin')


def ordinary(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and
         all(not p.is_symlink() for p in (path, *path.parents)), 'Ordinary absolute path')
    return path


class Budget:
    def __init__(self, read_bytes, write_bytes, seconds):
        need(type(read_bytes) is int and type(write_bytes) is int and
             read_bytes > 0 and write_bytes >= 8192 and type(seconds) is int and 0 < seconds <= 86400,
             'Explicit positive bounded resource envelope')
        self.read_limit, self.write_limit = read_bytes, write_bytes
        self.read = self.written = 0
        self.deadline = time.monotonic() + seconds

    def check(self):
        need(time.monotonic() < self.deadline, 'Observation work deadline')

    def input(self, amount):
        self.check()
        self.read += amount
        need(self.read <= self.read_limit, 'Named read cap')

    def output(self, amount, failure=False):
        if not failure:
            self.check()
        need(self.written + amount <= self.write_limit - (0 if failure else 8192), 'Artifact cap')
        self.written += amount


def read(path, cap, expected=None, budget=None):
    path = ordinary(path)
    if expected is not None:
        descriptor(expected, cap)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'Bounded single-link regular file')
        if budget:
            budget.input(before.st_size + 1)
        body = stream.read(before.st_size + 1)
        after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    need(identity(before) == identity(after) == identity(path.lstat()) and len(body) == before.st_size,
         'File changed during capture')
    need(expected is None or pin(body) == expected, 'Frozen content changed')
    return body


def write(path, body, budget, failure=False):
    path = ordinary(path)
    budget.output(len(body), failure)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    return pin(body)


def dependencies(repository_root, budget=None):
    root = ordinary(repository_root)
    body = read(HERE / 'SOURCE_BINDINGS.json', 65536, budget=budget)
    bindings = decode(body)
    need(set(bindings) == {'schema', 'own', 'external'} and
         bindings['schema'] == 'erp-adaptive-observation-sources-v1' and
         set(bindings['own']) == {'observation.py'} and
         set(bindings['external']) == {PREFIX + p for p in DEPENDENCIES.values()}, 'Exact source dependency closure')
    read(HERE / 'observation.py', 131072, bindings['own']['observation.py'], budget)
    result = {'binding': pin(body), 'sources': bindings}
    for name, relative in DEPENDENCIES.items():
        path = root / (PREFIX + relative)
        source = read(path, 131072, bindings['external'][PREFIX + relative], budget)
        if name == 'actions':
            result[name] = decode(source)
        else:
            module = types.ModuleType('adaptive_observation_' + name)
            module.__file__ = str(path)
            exec(compile(source, str(path), 'exec'), module.__dict__)
            result[name] = module
    # Only pure initial_state/transition/display_metadata viewer functions are used.
    # PacketSession and codec/renderer import standard library only; no dynamic loaders called.
    need(all(g in result['viewer'].GAINS for g in GAINS), 'Existing allowed gains only')
    return result


def validate_record(record, demonstration):
    fields = {'trial_id', 'channels'} | ({'target'} if demonstration is not None else set())
    need(type(record) is dict and set(record) == fields and type(record['trial_id']) is str,
         'Exact operator record fields')
    if demonstration is not None:
        need(type(demonstration) is int and 0 <= demonstration < 4 and
             type(record['target']) is int and record['target'] == DEMO_LABELS[demonstration], 'Fixed demonstration label/order')
    else:
        need(re.fullmatch('q-[0-9a-f]{32}', record['trial_id']), 'Original opaque query ID')
    channels = record['channels']
    need(type(channels) is list and len(channels) == 2 and
         all(type(c) is list and len(c) == 1024 for c in channels) and
         all(type(v) in (int, float) and math.isfinite(v) for c in channels for v in c),
         'Both complete finite native channels; booleans forbidden')


def warning_evidence(png, modules):
    """Decision input is exclusively the two authenticated rendered warning ROIs.

    Accept only exact blank white or exact source-font red warning. A malformed
    or partial warning is an error, never evidence of visibility.
    """
    scan = modules['codec'].scanlines(png)
    raster = modules['raster']
    width, height, stride = len(WARNING) * 6, 7, 4201
    expected = bytearray(b'\xff' * (width * height * 3))
    for ci, char in enumerate(WARNING):
        for y, bits in enumerate(raster.FONT[char]):
            for x in range(5):
                if bits & (1 << (4 - x)):
                    start = (y * width + ci * 6 + x) * 3
                    expected[start:start + 3] = bytes(raster.RED)
    white = b'\xff' * len(expected)
    channels = []
    for name, top in (('Cz', 185), ('Pz', 445)):
        crop = b''.join(scan[y * stride + 1 + 1030 * 3:y * stride + 1 + (1030 + width) * 3]
                        for y in range(top, top + height))
        need(crop in (white, bytes(expected)), 'Unexpected clipping-warning pixels')
        channels.append({'channel': name, 'roi_xyxy': [1030, top, 1030 + width, top + height],
                         'pixels': pin(crop), 'clipped': crop != white})
    return {'schema': 'erp-rendered-warning-evidence-v1', 'template_rgb': pin(bytes(expected)),
            'scanlines': pin(scan), 'channels': channels,
            'both_channels_unclipped': all(not c['clipped'] for c in channels)}


def resolution(gain):
    need(type(gain) is int and gain in GAINS, 'Declared gain')
    return {'image_pixels': [1400, 820], 'plot_width_pixels': 1120, 'channel_height_pixels': 180,
            'native_units_per_division': gain, 'pixels_per_division': 30,
            'native_units_per_vertical_pixel': gain / 30,
            'in_range_sample_vertical_rounding_bound_native_units': gain / 60,
            'horizontal_sample_position_rounding_bound_pixels': 0.5,
            'displayed_native_range': [-3 * gain, 3 * gain],
            'all_1024_samples_and_adjacent_segments_rendered': True,
            'lossless_png_reencoding': True, 'raster_quantization_loss': True,
            'exact_sample_values_recoverable': False, 'pixel_interpolation_is_not_new_measurement': True,
            'clipped_segments_outside_range_omitted': True,
            'units': 'native stored EEG amplitude; calibration unresolved'}


def action_at(index, demonstration):
    if index:
        return {'action': 'gain', 'units_per_division': GAINS[index]}
    return ({'action': 'inspect'} if demonstration is None else
            {'action': 'select', 'record': f'demo{demonstration + 1}'})


def observe_record(record, demonstration, directory, modules, budget):
    validate_record(record, demonstration)
    directory = ordinary(directory)
    directory.mkdir(mode=0o700)
    viewer, raster, codec = (modules[n] for n in ('viewer', 'raster', 'codec'))
    state = viewer.initial_state()
    attempts = []
    for index, gain in enumerate(GAINS):
        budget.check()
        action = action_at(index, demonstration)
        new = viewer.transition(state, action, 'four_demo')
        need(new['units_per_division'] == gain, 'Ascending gain state')
        attempt = {'index': index, 'action': action, 'action_pin': pin(encode(action)),
                   'state_before': state, 'state': new, 'state_pin': pin(encode(new))}
        attempt_pin = write(directory / f'ATTEMPT-{index}.json', encode(attempt), budget)
        original = raster.render(record, new, 'four_demo')
        png, encoding = codec.encode_transport_image(original)
        codec.verify_equivalence(original, png, encoding)
        png_pin = write(directory / f'FRAME-{index}.png', png, budget)
        evidence = warning_evidence(png, modules)
        view = {'attempt': attempt_pin, 'image': png_pin, 'encoding': encoding,
                'display': viewer.display_metadata(new, record), 'warning_evidence': evidence,
                'resolution': resolution(gain)}
        view_pin = write(directory / f'VIEW-{index}.json', encode(view), budget)
        attempts.append({'index': index, 'attempt': attempt_pin, 'image': png_pin, 'view': view_pin})
        state = new
        if evidence['both_channels_unclipped']:
            break
    result = {'schema': 'erp-adaptive-record-v1', 'condition': CONDITION,
              'trial_id': record['trial_id'], 'demonstration': demonstration, 'attempts': attempts,
              'selected_index': index, 'selected_gain': gain,
              'outcome': 'unclipped' if evidence['both_channels_unclipped'] else 'cap_clipped',
              'selection_uses_rendered_warning_pixels_only': True,
              'raw_samples_in_projection': False}
    result_pin = write(directory / 'RECORD.json', encode(result), budget)
    return result, result_pin


def original_png(scan, codec):
    """Reconstruct unchanged stored-DEFLATE raster bytes from retained scanlines."""
    data = bytearray(b'\x78\x01')
    for start in range(0, len(scan), 65535):
        block = scan[start:start + 65535]
        data.append(int(start + len(block) == len(scan)))
        data += struct.pack('<HH', len(block), len(block) ^ 65535) + block
    data += struct.pack('>I', zlib.adler32(scan))
    return codec.SIGNATURE + codec.chunk(b'IHDR', codec.IHDR) + codec.chunk(b'IDAT', data) + codec.chunk(b'IEND', b'')


def audit_record(directory, expected, trial_id, demonstration, modules, budget):
    directory = ordinary(directory)
    value = decode(read(directory / 'RECORD.json', 65536, expected, budget))
    need(set(value) == {'schema', 'condition', 'trial_id', 'demonstration', 'attempts', 'selected_index',
         'selected_gain', 'outcome', 'selection_uses_rendered_warning_pixels_only', 'raw_samples_in_projection'} and
         value['schema'] == 'erp-adaptive-record-v1' and value['condition'] == CONDITION and
         value['trial_id'] == trial_id and value['demonstration'] == demonstration and
         value['selection_uses_rendered_warning_pixels_only'] is True and value['raw_samples_in_projection'] is False,
         'Exact record identity/projection')
    need(type(value['attempts']) is list and 1 <= len(value['attempts']) <= len(GAINS), 'Bounded nonempty gain prefix')
    state = modules['viewer'].initial_state()
    names = {'RECORD.json'}
    projections = []
    for index, row in enumerate(value['attempts']):
        need(type(row) is dict and set(row) == {'index', 'attempt', 'image', 'view'} and
             type(row['index']) is int and row['index'] == index, 'Ordered attempt inventory')
        action = action_at(index, demonstration)
        new = modules['viewer'].transition(state, action, 'four_demo')
        expected_attempt = {'index': index, 'action': action, 'action_pin': pin(encode(action)),
                            'state_before': state, 'state': new, 'state_pin': pin(encode(new))}
        need(read(directory / f'ATTEMPT-{index}.json', 8192, row['attempt'], budget) == encode(expected_attempt),
             'Action/state custody')
        png = read(directory / f'FRAME-{index}.png', 4 * 1024**2, row['image'], budget)
        view = decode(read(directory / f'VIEW-{index}.json', 16384, row['view'], budget))
        need(type(view) is dict and set(view) == {'attempt', 'image', 'encoding', 'display', 'warning_evidence', 'resolution'},
             'Exact view metadata')
        evidence = warning_evidence(png, modules)
        codec = modules['codec']
        original = original_png(codec.scanlines(png), codec)
        codec.verify_equivalence(original, png, view['encoding'])
        display_record = {} if demonstration is None else {'target': DEMO_LABELS[demonstration]}
        need(view['attempt'] == row['attempt'] and view['image'] == row['image'] and
             view['warning_evidence'] == evidence and view['resolution'] == resolution(GAINS[index]) and
             view['display'] == modules['viewer'].display_metadata(new, display_record), 'View metadata/pixel custody')
        need(not evidence['both_channels_unclipped'] or index == len(value['attempts']) - 1,
             'Cannot continue after first unclipped view')
        projections.append({'action': action, 'state': new, 'image': {'file': f'FRAME-{index}.png', **row['image']},
                            'display': view['display'], 'warning_evidence': evidence, 'resolution': view['resolution']})
        names.update((f'ATTEMPT-{index}.json', f'FRAME-{index}.png', f'VIEW-{index}.json'))
        state = new
    need(set(p.name for p in directory.iterdir()) == names, 'No omitted or uncommitted attempts')
    final = evidence['both_channels_unclipped']
    need(final or len(value['attempts']) == len(GAINS), 'Clipped termination only at cap')
    need(type(value['selected_index']) is int and value['selected_index'] == len(value['attempts']) - 1 and
         type(value['selected_gain']) is int and value['selected_gain'] == GAINS[-1 if not final else value['selected_index']] and
         value['outcome'] == ('unclipped' if final else 'cap_clipped'), 'Exact first-unclipped/cap outcome')
    return value, projections


def participant_projection(directory, expected, trial_id, demonstration, modules, budget):
    """Audited images/metadata only, no raw channels, source paths or cohort roster.

    Relative frame paths resolve inside this one record directory. For each query
    an external transport must supply four separately audited demo projections.
    This source alone makes no participant isolation or delivery claim.
    """
    value, attempts = audit_record(directory, expected, trial_id, demonstration, modules, budget)
    return {'condition': CONDITION, 'trial_id': trial_id, 'demonstration': demonstration,
            'attempts': attempts, 'selected_index': value['selected_index'],
            'selected_gain': value['selected_gain'], 'outcome': value['outcome']}


def roster(ids):
    need(type(ids) is tuple and len(ids) == COUNT and all(type(i) is str and
         re.fullmatch('q-[0-9a-f]{32}', i) for i in ids) and ids == tuple(sorted(set(ids))),
         'All original 6400 unique sorted opaque query IDs required')


def validate_inventory(value):
    need(type(value) is dict and set(value) == {'schema', 'status', 'condition', 'intent', 'demos', 'queries',
         'private_target_reads', 'predictions', 'scoring_performed'} and
         value['schema'] == 'erp-adaptive-observation-complete-v1' and value['status'] == 'complete_observation_only' and
         value['condition'] == CONDITION and value['private_target_reads'] == 0 and value['predictions'] == 0 and
         value['scoring_performed'] is False, 'Complete observation-only receipt')
    need(type(value['demos']) is list and len(value['demos']) == 4 and
         type(value['queries']) is list and len(value['queries']) == COUNT, 'Four demos and all6400 queries')
    roster(tuple(row['trial_id'] for row in value['queries']))
    for rows in (value['demos'], value['queries']):
        for ordinal, row in enumerate(rows):
            need(type(row) is dict and set(row) == {'ordinal', 'trial_id', 'record'} and
                 type(row['ordinal']) is int and row['ordinal'] == ordinal and type(row['trial_id']) is str,
                 'Exact ordered record inventory')
            descriptor(row['record'], 65536)
    need(len({row['trial_id'] for row in value['demos']}) == 4, 'Unique four demonstrations')
    descriptor(value['intent'], 65536)


def capture(public_root, output, modules, budget):
    """No query-count/subset/target/fit interface; all original cases or failure."""
    public_root, output = ordinary(public_root), ordinary(output)
    need(not output.exists() and not output.is_relative_to(public_root) and
         not public_root.is_relative_to(output), 'Fresh disjoint observation output')
    output.mkdir(mode=0o700)
    completed_demos, completed_queries = [], []
    intent = {'schema': 'erp-adaptive-observation-intent-v1', 'policy': POLICY,
              'source_bindings': modules['binding'], 'public_manifest': MANIFEST}
    intent_pin = write(output / 'INTENT.json', encode(intent), budget)
    try:
        # Exact original manifest disallows substitutes before even a demo read.
        with modules['consumer'].PacketSession(public_root, MANIFEST, budget=budget) as session:
            ids = tuple(session.trial_ids)
            roster(ids)
            demos = session.demonstration_records()
            need(len(demos) == 4, 'Exactly four original demonstrations')
            for ordinal, record in enumerate(demos):
                _, committed = observe_record(record, ordinal, output / f'demo-{ordinal}', modules, budget)
                completed_demos.append({'ordinal': ordinal, 'trial_id': record['trial_id'], 'record': committed})
            for ordinal, trial_id in enumerate(ids):
                record = session.query_record(trial_id)
                need(record['trial_id'] == trial_id, 'Original query ordering')
                _, committed = observe_record(record, None, output / f'query-{ordinal:04d}', modules, budget)
                completed_queries.append({'ordinal': ordinal, 'trial_id': trial_id, 'record': committed})
        result = {'schema': 'erp-adaptive-observation-complete-v1', 'status': 'complete_observation_only',
                  'condition': CONDITION, 'intent': intent_pin, 'demos': completed_demos, 'queries': completed_queries,
                  'private_target_reads': 0, 'predictions': 0, 'scoring_performed': False}
        validate_inventory(result)
        return write(output / 'COMPLETE.json', encode(result), budget)
    except BaseException as error:
        failure = {'schema': 'erp-adaptive-observation-failure-v1', 'condition': CONDITION,
                   'status': 'incomplete_observation', 'intent': intent_pin,
                   'completed_demonstrations': len(completed_demos), 'completed_queries': len(completed_queries),
                   'uncompleted_queries': COUNT - len(completed_queries),
                   'attempted_files_retained': True, 'automatic_retry': False,
                   'error_type': type(error).__name__, 'message': str(error)[:512],
                   'private_target_reads': 0, 'predictions': 0, 'scoring_performed': False}
        write(output / 'FAILED.json', encode(failure), budget, failure=True)
        raise


def audit(output, expected, modules, budget):
    output = ordinary(output)
    result = decode(read(output / 'COMPLETE.json', 4 * 1024**2, expected, budget))
    validate_inventory(result)
    intent = decode(read(output / 'INTENT.json', 65536, result['intent'], budget))
    need(intent == {'schema': 'erp-adaptive-observation-intent-v1', 'policy': POLICY,
                    'source_bindings': modules['binding'], 'public_manifest': MANIFEST}, 'Exact original scope/source intent')
    names = {'COMPLETE.json', 'INTENT.json'}
    gains = {str(g): 0 for g in GAINS}
    caps = 0
    attempts = 0
    for kind in ('demos', 'queries'):
        for row in result[kind]:
            i = row['ordinal']
            name = f'demo-{i}' if kind == 'demos' else f'query-{i:04d}'
            value, _ = audit_record(output / name, row['record'], row['trial_id'],
                                    i if kind == 'demos' else None, modules, budget)
            names.add(name)
            gains[str(value['selected_gain'])] += 1
            caps += int(value['outcome'] == 'cap_clipped')
            attempts += len(value['attempts'])
    need(set(p.name for p in output.iterdir()) == names, 'No incomplete, omitted or extra records')
    return {'status': 'complete_observation_audited', 'records': COUNT + 4, 'attempted_images': attempts,
            'selected_gain_counts': gains, 'cap_clipped_records': caps, 'predictions': 0,
            'private_target_reads': 0, 'scoring_performed': False, 'isolation_qualified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('capture', 'audit'))
    parser.add_argument('--repository-root', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--public-root')
    parser.add_argument('--receipt-bytes', type=int)
    parser.add_argument('--receipt-sha256')
    parser.add_argument('--read-bytes', type=int, required=True)
    parser.add_argument('--write-bytes', type=int, required=True)
    parser.add_argument('--work-seconds', type=int, required=True)
    args = parser.parse_args(argv)
    budget = Budget(args.read_bytes, args.write_bytes, args.work_seconds)
    def alarm(_signum, _frame):
        raise TimeoutError('Whole observation deadline')
    old = signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, args.work_seconds + 5)
    try:
        modules = dependencies(args.repository_root, budget)
        if args.command == 'capture':
            need(args.public_root and args.receipt_bytes is None and args.receipt_sha256 is None,
                 'Capture requires original public root only')
            result = {'status': 'complete_observation_only',
                      'receipt': capture(args.public_root, args.output, modules, budget)}
        else:
            need(args.public_root is None, 'Audit reads captured images only')
            expected = {'bytes': args.receipt_bytes, 'sha256': args.receipt_sha256}
            descriptor(expected, 4 * 1024**2)
            result = audit(args.output, expected, modules, budget)
        result.update(read_bytes_charged=budget.read, write_bytes_charged=budget.written)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({'status': 'refused_or_incomplete', 'error_type': type(error).__name__,
                          'message': str(error)[:512], 'read_bytes_charged': budget.read,
                          'write_bytes_charged': budget.written}), file=sys.stderr)
        return 2
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


if __name__ == '__main__':
    raise SystemExit(main())
