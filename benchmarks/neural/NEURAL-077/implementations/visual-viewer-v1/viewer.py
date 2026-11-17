"""Operator-side image-only NEURAL-077 viewer and complete response collection.

Agent requests are JSON data, never code. This module is not a process sandbox.
Only the documented response projection is for the participant transport.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys

HERE = Path(__file__).resolve().parent
MODES = ('zero_shot', 'four_demo')
GAINS = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)
MAX_REQUEST = 8192
MAX_ACTIONS = 128


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, 'Duplicate JSON field')
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def write_new(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def read_regular(path, cap):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'Bounded single-link regular file required')
        body = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
        need(len(body) <= cap and all(getattr(before, f) == getattr(after, f)
             for f in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')), 'File changed while read')
        return body


def load_module(name, path, body):
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def dependencies(implementation_root=None):
    """Only trusted operator chooses root; every executable dependency is pinned."""
    root = Path(implementation_root) if implementation_root else HERE.parent
    bindings = decode((HERE / 'SOURCE_BINDINGS.json').read_bytes())
    bodies = {}
    for relative, pin in bindings['members'].items():
        body = read_regular(root / relative, pin['bytes'])
        need(len(body) == pin['bytes'] and digest(body) == pin['sha256'], 'Dependency pin mismatch')
        bodies[relative] = body
    path = root / 'complete-direct-condition-v1/delivery.py'
    delivery = load_module('viewer_delivery', path, bodies['complete-direct-condition-v1/delivery.py'])
    # The original loader pins exporter, response parser, validator and assets.
    modules = delivery.dependencies()
    return delivery, modules


def source(packet, implementation_root=None):
    delivery, modules = dependencies(implementation_root)
    members = delivery.packet_members(packet, modules['exporter'])
    # Reuse the authenticated complete roster and exact original context checks.
    roster = [{'ordinal': row['ordinal'], 'trial_id': row['trial_id']}
              for row in delivery.context_rows(members, 'legacy_waveform_no_tools')]
    rows = [decode(line) for line in members['queries.jsonl'].splitlines()]
    demos = decode(members['demonstrations.json'])
    need(len(demos) == 4, 'Exactly four permitted demonstrations')
    for row in rows + demos:
        expected = {'trial_id', 'channels'} | ({'target'} if row in demos else set())
        need(set(row) == expected, 'Unexpected waveform fields')
        need(type(row['channels']) is list and len(row['channels']) == 2, 'Two channels required')
        for channel in row['channels']:
            need(type(channel) is list and len(channel) == 1024, 'All 1024 samples required')
            need(all(type(v) in (int, float) and math.isfinite(v) for v in channel), 'Finite native samples required')
    need(all(type(d['target']) is int and d['target'] in (0, 1) for d in demos), 'Binary demonstration labels')
    return {'rows': rows, 'demos': demos, 'roster': roster, 'parser': modules['response'],
            'validator': modules['validator'], 'packet': {k: digest(v) for k, v in members.items()}}


def scientific_prompt(trial_id, mode):
    permission = ('No labeled demonstrations or feedback are available.' if mode == 'zero_shot' else
                  'Four labeled training demonstrations are available as demo1 through demo4. They are deliberately '
                  'balanced; their label fraction does not estimate natural target prevalence. No full-training prior is supplied.')
    return (f'Estimate the probability that the current EEG trial {trial_id} contains a target stimulus rather than '
            'a non-target stimulus. Inspect only the trace images using the bounded viewer actions. '
            'Do not use code execution, raw arrays, files, external retrieval, other tools or memory from other query trials. '
            'Return the final response through finalize as exactly one JSON object with trial_id copied exactly and '
            'target_probability as a finite number in [0,1]. No reasoning or additional text. ' + permission +
            ' The query label is unavailable. Cz and Pz have all 1024 samples at 1024 Hz, offsets -256 through 767 '
            'relative to the released event marker. Offset 0 is array index 256. The committed source subtracts '
            '(P9+P10)/2 in float64, then subtracts each channel mean over offsets -256 through -1. '
            'Native stored EEG amplitude units are used; microvolt calibration is not independently established. '
            'No additional filtering, resampling or amplitude scaling is applied to the underlying samples. '
            'Physical display-delay correction is unresolved and post-marker activity may include behavioral responses. '
            'Gain changes only pixels per native unit. Positive values are plotted upwards. No class prior is supplied.')


def initial_state():
    return {'record': 'query', 'start_sample': -256, 'stop_sample': 768,
            'units_per_division': 20, 'channels': ['Cz', 'Pz'], 'display_filter': 'none'}


def transition(state, request, mode):
    """Pure strict action validator. Integers are sample offsets, never array indexes."""
    need(type(request) is dict and type(request.get('action')) is str, 'Exact action object required')
    action = request['action']
    fields = {'inspect': set(), 'select': {'record'}, 'window': {'start_sample', 'stop_sample'},
              'scroll': {'samples'}, 'zoom': {'factor', 'center_sample'}, 'gain': {'units_per_division'},
              'channels': {'channels'}, 'finalize': {'response'}}
    need(action in fields and set(request) == fields[action] | {'action'}, 'Unknown action or extra/missing fields')
    new = dict(state)
    if action == 'select':
        permitted = ['query'] + ([f'demo{i}' for i in range(1, 5)] if mode == 'four_demo' else [])
        need(type(request['record']) is str and request['record'] in permitted, 'Unavailable record')
        new.update(record=request['record'], start_sample=-256, stop_sample=768)
    elif action == 'window':
        start, stop = request['start_sample'], request['stop_sample']
        need(type(start) is int and type(stop) is int and -256 <= start < stop <= 768 and stop - start >= 16,
             'Window must be a half-open native-sample interval within [-256,768), width at least 16')
        new.update(start_sample=start, stop_sample=stop)
    elif action == 'scroll':
        shift = request['samples']
        need(type(shift) is int and 0 < abs(shift) <= 1024, 'Nonzero integer sample shift required')
        start, stop = state['start_sample'] + shift, state['stop_sample'] + shift
        need(-256 <= start < stop <= 768, 'Scroll exceeds epoch support; no clamping')
        new.update(start_sample=start, stop_sample=stop)
    elif action == 'zoom':
        factor, center = request['factor'], request['center_sample']
        need(type(factor) in (int, float) and factor in (0.5, 2) and type(center) is int,
             'Zoom factor is 2 (in) or 0.5 (out), centered on an integer sample')
        need(state['start_sample'] <= center < state['stop_sample'], 'Zoom center must be in current window')
        width = round((state['stop_sample'] - state['start_sample']) / factor)
        need(16 <= width <= 1024, 'Zoom width outside 16 through 1024 samples')
        start = max(-256, min(768 - width, center - width // 2))
        new.update(start_sample=start, stop_sample=start + width)
    elif action == 'gain':
        gain = request['units_per_division']
        need(type(gain) is int and gain in GAINS, 'Unsupported integer native units per division')
        new['units_per_division'] = gain
    elif action == 'channels':
        channels = request['channels']
        need(type(channels) is list and channels in (['Cz'], ['Pz'], ['Cz', 'Pz']), 'Ordered unique Cz/Pz channel selection required')
        new['channels'] = channels[:]
    elif action == 'finalize':
        need(type(request['response']) is str and len(request['response'].encode()) <= 4096, 'Bounded raw response text required')
    return new


def display_metadata(state, record):
    metadata = dict(state, channels=state['channels'][:], sampling_hz=1024,
                        start_ms=state['start_sample'] * 1000 / 1024,
                        stop_ms_exclusive=state['stop_sample'] * 1000 / 1024,
                        last_sample_ms=(state['stop_sample'] - 1) * 1000 / 1024,
                        units='native stored EEG amplitude; calibration unresolved', positive='up',
                        renderer='all samples and adjacent segments; clipping flagged in image')
    if state['record'] != 'query':
        metadata['demonstration_target'] = record['target']
    return metadata


def session_contract(dataset, ordinal, mode):
    return {'schema': 'neural077_visual_session_v1', 'ordinal': ordinal,
                         'trial_id': dataset['rows'][ordinal]['trial_id'], 'condition': mode,
                         'demonstrations_available': 4 if mode == 'four_demo' else 0,
                         'feedback_available': False, 'max_actions': MAX_ACTIONS,
                         'packet_sha256': dataset['packet'], 'prompt_sha256': digest(scientific_prompt(dataset['rows'][ordinal]['trial_id'], mode).encode()),
                         'action_schema_sha256': digest((HERE / 'actions.schema.json').read_bytes()),
                         'implementation_sha256': {name: digest((HERE / name).read_bytes())
                             for name in ('viewer.py', 'raster.py', 'SOURCE_BINDINGS.json')},
                         'isolation_qualified': False}


class Session:
    """One operator-owned process/session; raw records never leave this instance."""
    def __init__(self, dataset, ordinal, mode, output):
        need(type(ordinal) is int and 0 <= ordinal < len(dataset['rows']), 'Unknown query ordinal')
        need(mode in MODES, 'Unknown condition')
        self.dataset, self.ordinal, self.mode = dataset, ordinal, mode
        self.query = dataset['rows'][ordinal]
        self.output = Path(output)
        self.output.mkdir(mode=0o700, parents=False, exist_ok=False)
        (self.output / 'frames').mkdir(mode=0o700)
        self.state, self.closed, self.sequence = initial_state(), False, 0
        self.previous = '0' * 64
        self.raster = load_module('viewer_raster', HERE / 'raster.py', (HERE / 'raster.py').read_bytes())
        self.prompt = scientific_prompt(self.query['trial_id'], mode)
        self.contract = session_contract(dataset, ordinal, mode)
        self.contract_hash = digest(encode(self.contract))
        write_new(self.output / 'SESSION.json', encode(self.contract))
        write_new(self.output / 'prompt.txt', self.prompt.encode())

    def _event(self, raw, status, detail):
        event = {'sequence': self.sequence, 'previous_sha256': self.previous,
                 'request_base64': base64.b64encode(raw).decode('ascii'), 'request_sha256': digest(raw),
                 'status': status, 'detail': detail}
        body = encode(event)
        write_new(self.output / f'action-{self.sequence:04d}.json', body)
        self.previous = digest(body)
        self.sequence += 1

    def _record(self):
        if self.state['record'] == 'query':
            return self.query
        return self.dataset['demos'][int(self.state['record'][4:]) - 1]

    def _frame(self):
        png = self.raster.render(self._record(), self.state, self.mode)
        filename = f'frames/{self.sequence:04d}.png'
        write_new(self.output / filename, png)
        metadata = display_metadata(self.state, self._record())
        return png, filename, metadata

    def handle(self, raw):
        """Candidate-facing method: bytes in; JSON projection containing PNG only out."""
        if self.closed:
            return {'status': 'closed', 'error': 'Session is terminal; no replacement response'}
        need(type(raw) is bytes, 'Request must be UTF-8 bytes')
        # Preserve bounded rejected requests too. Oversize requests terminate.
        if len(raw) > MAX_REQUEST:
            self._event(raw[:MAX_REQUEST], 'terminal_error', {'error': 'Request exceeds byte limit',
                        'complete_request_sha256': digest(raw), 'complete_request_bytes': len(raw)})
            self.closed = True
            write_new(self.output / 'FAILED.json', encode({'reason': 'oversize_request', 'last_action_sha256': self.previous}))
            return {'status': 'closed', 'error': 'Request exceeds byte limit'}
        if self.sequence >= MAX_ACTIONS:
            self.closed = True
            write_new(self.output / 'FAILED.json', encode({'reason': 'action_limit', 'last_action_sha256': self.previous}))
            return {'status': 'closed', 'error': 'Action limit; no response admitted'}
        try:
            request = decode(raw)
            state = transition(self.state, request, self.mode)
        except (ValueError, UnicodeError, TypeError, RecursionError, OverflowError):
            self._event(raw, 'rejected', {'error': 'Invalid action or parameters'})
            return {'status': 'rejected', 'error': 'Invalid action or parameters', 'remaining_actions': MAX_ACTIONS - self.sequence}
        if request['action'] == 'finalize':
            self.closed = True  # First final response is terminal even if invalid.
            response = request['response'].encode('utf-8')
            write_new(self.output / 'response.txt', response)
            try:
                probability = self.dataset['parser'].parse(response, self.query['trial_id'])
                status = 'valid_unscored'
            except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
                probability, status = None, 'invalid_response'
            self._event(raw, status, {'response_sha256': digest(response)})
            receipt = {'schema': 'neural077_visual_final_v1', 'status': status,
                       'session_sha256': self.contract_hash, 'last_action_sha256': self.previous,
                       'actions': self.sequence, 'response_sha256': digest(response),
                       'target_probability': probability, 'scoring_performed': False}
            write_new(self.output / 'FINAL.json', encode(receipt))
            return {'status': status, 'response_sha256': digest(response), 'terminal': True}
        self.state = state
        png, filename, metadata = self._frame()
        self._event(raw, 'rendered', {'frame': filename, 'frame_sha256': digest(png), 'display': metadata})
        return {'status': 'rendered', 'display': metadata, 'remaining_actions': MAX_ACTIONS - self.sequence,
                'image': {'mime_type': 'image/png', 'base64': base64.b64encode(png).decode('ascii')}}


def audit_session(path, dataset, ordinal, mode):
    """Trusted-operator integrity audit; hashes do not attest transport isolation."""
    path = Path(path)
    contract = decode(read_regular(path / 'SESSION.json', 16384))
    final = decode(read_regular(path / 'FINAL.json', 16384))
    row = dataset['rows'][ordinal]
    need(contract == session_contract(dataset, ordinal, mode), 'Session contract mismatch')
    need(contract['ordinal'] == ordinal and contract['trial_id'] == row['trial_id'] and contract['condition'] == mode,
         'Session identity/condition mismatch')
    need(contract['packet_sha256'] == dataset['packet'] and contract['prompt_sha256'] == digest(scientific_prompt(row['trial_id'], mode).encode()),
         'Session source/prompt mismatch')
    need(contract['demonstrations_available'] == (4 if mode == 'four_demo' else 0) and contract['feedback_available'] is False,
         'Demonstration/feedback condition mismatch')
    need(contract['implementation_sha256'] == {name: digest((HERE / name).read_bytes())
         for name in ('viewer.py', 'raster.py', 'SOURCE_BINDINGS.json')} and
         contract['action_schema_sha256'] == digest((HERE / 'actions.schema.json').read_bytes()), 'Viewer version mismatch')
    need(read_regular(path / 'prompt.txt', 16384) == scientific_prompt(row['trial_id'], mode).encode(), 'Stored prompt mismatch')
    need(final['status'] == 'valid_unscored' and final['session_sha256'] == digest(encode(contract)), 'Invalid final capture')
    count = final['actions']
    need(type(count) is int and 1 <= count <= MAX_ACTIONS, 'Invalid action count')
    need(sorted(p.name for p in path.glob('action-*.json')) == [f'action-{i:04d}.json' for i in range(count)], 'Action history missing or extended')
    previous = '0' * 64
    state = initial_state()
    response = read_regular(path / 'response.txt', 4096)
    raster = load_module('viewer_audit_raster', HERE / 'raster.py', (HERE / 'raster.py').read_bytes())
    for index in range(count):
        raw = read_regular(path / f'action-{index:04d}.json', 32768)
        event = decode(raw)
        need(type(event) is dict and set(event) == {'sequence', 'previous_sha256', 'request_base64', 'request_sha256', 'status', 'detail'}, 'Exact event schema required')
        need(event['sequence'] == index and event['previous_sha256'] == previous, 'Broken action chain')
        request_raw = base64.b64decode(event['request_base64'], validate=True)
        need(digest(request_raw) == event['request_sha256'], 'Request byte integrity mismatch')
        previous = digest(raw)
        try:
            request = decode(request_raw)
            next_state = transition(state, request, mode)
        except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
            need(event['status'] == 'rejected' and index != count - 1 and event['detail'] == {'error': 'Invalid action or parameters'}, 'Invalid rejected request history')
            continue
        if request['action'] == 'finalize':
            need(index == count - 1 and event['status'] == 'valid_unscored' and request['response'].encode() == response,
                 'Final response must be the last immutable action')
            need(event['detail'] == {'response_sha256': digest(response)}, 'Final action metadata mismatch')
        else:
            need(index < count - 1 and event['status'] == 'rendered', 'Missing rendered action')
            state = next_state
            record = row if state['record'] == 'query' else dataset['demos'][int(state['record'][4:]) - 1]
            expected = raster.render(record, state, mode)
            detail = event['detail']
            need(detail['frame'] == f'frames/{index:04d}.png' and detail['frame_sha256'] == digest(expected), 'Rendered frame mismatch')
            need(read_regular(path / detail['frame'], 4 * 1024 * 1024) == expected, 'Stored frame mismatch')
            need(detail['display'] == display_metadata(state, record), 'Rendered metadata mismatch')
    need(previous == final['last_action_sha256'] and digest(response) == final['response_sha256'], 'Final integrity mismatch')
    probability = dataset['parser'].parse(response, row['trial_id'])
    need(final['target_probability'] == probability, 'Final scalar mismatch')
    return probability


def collect(packet, sessions, mode, output, implementation_root=None):
    dataset = source(packet, implementation_root)
    output = Path(output)
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    try:
        need(mode in MODES, 'Unknown condition')
        sessions = Path(sessions)
        need(sorted(p.name for p in sessions.iterdir()) == [f'{i:03d}' for i in range(400)], 'Exactly 400 session directories required')
        values = [audit_session(sessions / f'{i:03d}', dataset, i, mode) for i in range(400)]
        import numpy as np
        ids = [row['trial_id'] for row in dataset['rows']]
        with (output / 'submission.npz').open('xb') as destination:
            np.savez(destination, trial_ids=np.asarray(ids, dtype='<U48'), target_probability=np.asarray(values, dtype=np.float64))
            destination.flush()
            os.fsync(destination.fileno())
        expected = {case: np.asarray([x for x in ids if x.startswith(case + '-')])
                    for case in ('development-001', 'development-002')}
        dataset['validator'].validate(output / 'submission.npz', expected)
        receipt = {'schema': 'neural077_visual_collection_v1', 'status': 'complete_unscored_submission',
                   'condition': mode, 'queries': 400, 'submission_sha256': digest((output / 'submission.npz').read_bytes()),
                   'scoring_performed': False, 'transport_isolation_qualified': False}
        write_new(output / 'COMPLETE.json', encode(receipt))
        return receipt
    except Exception:
        write_new(output / 'FAILED.json', encode({'status': 'incomplete_or_invalid_sessions', 'scoring_performed': False}))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('serve', 'collect'):
        p = sub.add_parser(name)
        p.add_argument('--packet', type=Path, required=True)
        p.add_argument('--implementation-root', type=Path)
        p.add_argument('--mode', choices=MODES, required=True)
        p.add_argument('--output', type=Path, required=True)
        if name == 'serve':
            p.add_argument('--ordinal', type=int, required=True)
        else:
            p.add_argument('--sessions', type=Path, required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    try:
        if command == 'collect':
            print(json.dumps(collect(**args)))
        else:
            dataset = source(args.pop('packet'), args.pop('implementation_root'))
            session = Session(dataset=dataset, **args)
            print(json.dumps({'status': 'ready', 'prompt': session.prompt,
                              'actions': decode((HERE / 'actions.schema.json').read_bytes()),
                              'initial': session.handle(b'{"action":"inspect"}')}), flush=True)
            while not session.closed:
                raw = sys.stdin.buffer.readline(MAX_REQUEST + 1)
                if not raw:
                    write_new(session.output / 'FAILED.json', encode({'reason': 'transport_eof', 'last_action_sha256': session.previous}))
                    return 2
                print(json.dumps(session.handle(raw)), flush=True)
            return 0 if (session.output / 'FINAL.json').exists() and decode((session.output / 'FINAL.json').read_bytes())['status'] == 'valid_unscored' else 2
    except (ValueError, OSError, UnicodeError, KeyError, TypeError) as error:
        print('Viewer refused: ' + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
