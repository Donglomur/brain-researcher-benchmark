"""Task projections only; never loads packets, signal arrays, targets or models."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def pinned_module(task):
    bindings = json.loads((HERE / 'SOURCE_BINDINGS.json').read_bytes())
    need(bindings['schema'] == 'neural-viewer-provider-dependencies/v1', 'Source binding schema')
    for relative, pin in bindings['members'].items():
        path = ROOT / relative
        need(not path.is_symlink() and path.stat().st_size == pin['bytes'], 'Source size')
        need(hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256'], 'Source identity')
    name = 'viewer-transport-v1' if task == 'NEURAL-007' else 'visual-transport-v1'
    path = ROOT / 'benchmarks/neural' / task / 'implementations' / name / 'transport.py'
    spec = importlib.util.spec_from_file_location('provider_' + task.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def object_schema(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


class Policy:
    def __init__(self, task, condition):
        need(task in ('NEURAL-007', 'NEURAL-077'), 'Unknown task')
        self.t = pinned_module(task)
        self.task, self.condition = task, condition
        self.pending, self.accepted, self.seen = None, set(), set()
        self.started, self.terminal, self.sequence = False, False, 0
        self.episode = None
        need(condition == self.t.v.MODE if task == 'NEURAL-007' else condition in self.t.v.MODES,
             'Unknown condition')

    def schema(self):
        if self.task == 'NEURAL-077':
            variants = json.loads((self.t.v.HERE / 'actions.schema.json').read_bytes())['oneOf']
            # Responses strict schemas require typed enum fields; same existing values.
            for variant in variants:
                for value in variant['properties'].values():
                    if 'const' in value:
                        value.update(type='string', enum=[value.pop('const')])
                    elif 'enum' in value:
                        first = value['enum'][0]
                        value['type'] = 'array' if isinstance(first, list) else 'string' if isinstance(first, str) else 'number'
                        if value['type'] == 'array':
                            value['items'] = {'type': 'string'}
            return object_schema({'viewer_action': {'anyOf': variants}})
        v = self.t.v
        fields = {'inspect': {}, 'epoch': {'index': {'type': 'integer'}},
                  'window': {key: {'type': 'integer'} for key in ('start_sample', 'stop_sample')},
                  'gain': {'microvolts_per_division': {'type': 'integer', 'enum': list(v.GAINS)}},
                  'channels': {'channels': {'type': 'array', 'items': {'type': 'string', 'enum': list(v.CHANNELS)}}},
                  'respond': {'epoch_id': {'type': 'string'}, 'probabilities': {'type': 'array', 'items': {'type': 'number'}, 'minItems': 5, 'maxItems': 5}},
                  'finish': {}}
        return object_schema({'viewer_action': {'anyOf': [object_schema(dict(action={'type': 'string', 'enum': [name]}, **props))
                                                        for name, props in fields.items()]}})

    def ready(self, header, png):
        t, v = self.t, self.t.v
        need(not self.started and type(header) is dict, 'One fresh ready frame')
        episode = header.get('episode_id')
        need(type(episode) is str and re.fullmatch('[0-9a-f]{32}', episode), 'Episode identity')
        limits = header.get('limits')
        need(type(limits) is dict and set(limits) == {'max_actions', 'max_images', 'max_output_bytes', 'wall_seconds', 'max_request_bytes', 'max_image_bytes'}, 'Transport limits')
        self.limits = t.Limits(**{key: limits[key] for key in ('max_actions', 'max_images', 'max_output_bytes', 'wall_seconds')})
        if self.task == 'NEURAL-007':
            self.case, self.epochs = header.get('case_id'), header.get('epochs')
            need(self.case in v.CASES and type(self.epochs) is int and self.epochs == v.CASES[self.case], 'Complete original person')
            self.limits.validate(self.epochs)
            expected = t.ready_header(SimpleNamespace(case=self.case, epochs=self.epochs), self.limits, episode)
            need(header == expected and not png, 'Original sleep ready projection')
            self.state = {'epoch': 0, 'start_sample': 0, 'stop_sample': 3000, 'gain_uv': 50, 'channels': list(v.CHANNELS)}
        else:
            trial = header.get('trial_id')
            need(type(trial) is str and re.fullmatch('development-00[12]-[0-9a-f]{24}', trial), 'Query identity')
            self.limits.validate()
            session = SimpleNamespace(query={'trial_id': trial}, prompt=v.scientific_prompt(trial, self.condition))
            expected = t.ready_header(session, self.limits, episode)
            need(set(header) == set(expected) | {'initial'} and all(header[key] == value for key, value in expected.items()), 'Original EEG ready projection')
            self.state, self.sequence = v.initial_state(), 1
            self.eeg_view(header['initial'], png)
        self.started, self.episode = True, episode

    def image(self, header, png):
        need(type(png) is bytes and png.startswith(b'\x89PNG\r\n\x1a\n'), 'PNG frame required')
        need(header['image'] == {'mime_type': 'image/png', 'bytes': len(png)}, 'Exact image projection')

    def eeg_view(self, header, png):
        need(set(header) == {'status', 'display', 'remaining_actions', 'image'} and header['status'] == 'rendered', 'EEG view fields')
        display = header['display']
        need(type(display) is dict, 'Display object')
        record = {}
        if self.state['record'] != 'query':
            need(self.condition == 'four_demo' and type(display.get('demonstration_target')) is int and display['demonstration_target'] in (0, 1), 'Permitted demonstration only')
            record['target'] = display['demonstration_target']
        need(display == self.t.v.display_metadata(self.state, record), 'Original scalar display metadata')
        need(type(header['remaining_actions']) is int and header['remaining_actions'] == self.limits.max_actions - self.sequence, 'Exact remaining actions')
        self.image(header, png)

    def action(self, action):
        need(self.started and not self.terminal and self.pending is None, 'Action state')
        need(type(action) is dict and type(action.get('action')) is str, 'Typed action')
        raw = self.t.wire(action)
        self.t.unpack(raw, inbound=True)
        self.sequence += 1
        need(self.sequence <= self.limits.max_actions, 'Viewer action budget')
        if self.task == 'NEURAL-077':
            # Original transition owns rejections. The first valid finalize action
            # is forwarded even when its inner scalar is malformed.
            try:
                self.next_state = self.t.v.transition(self.state, action, self.condition)
                self.rejected = False
            except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
                self.rejected = True
        else:
            name, state, v = action['action'], self.state, self.t.v
            fields = {'inspect': set(), 'epoch': {'index'}, 'window': {'start_sample', 'stop_sample'}, 'gain': {'microvolts_per_division'}, 'channels': {'channels'}, 'respond': {'epoch_id', 'probabilities'}, 'finish': set()}
            need(name in fields and set(action) == fields[name] | {'action'}, 'Sleep action fields')
            if name == 'epoch':
                i = action['index']; need(type(i) is int and 0 <= i < self.epochs, 'Epoch ordinal')
                state.update(epoch=i, start_sample=i * 3000, stop_sample=(i + 1) * 3000)
            elif name == 'window':
                a, b = action['start_sample'], action['stop_sample']
                need(type(a) is int and type(b) is int and 0 <= a < b <= self.epochs * 3000 and 100 <= b - a <= 6000, 'Sleep window')
                state.update(start_sample=a, stop_sample=b)
            elif name == 'gain':
                x = action['microvolts_per_division']; need(type(x) is int and x in v.GAINS, 'Sleep gain'); state['gain_uv'] = x
            elif name == 'channels':
                x = action['channels']; need(type(x) is list and x and x == [c for c in v.CHANNELS if c in x], 'Sleep channels'); state['channels'] = x[:]
            elif name == 'respond':
                need(action['epoch_id'] == self.epoch_id() and state['epoch'] in self.seen and state['epoch'] not in self.accepted, 'First response after complete view')
                v.probabilities(action['probabilities'])
            elif name == 'finish':
                need(self.accepted == set(range(self.epochs)), 'Full person required')
        self.pending = action
        return raw

    def epoch_id(self):
        return f'{self.case}/{self.state["epoch"]:05d}'

    def observe(self, header, png):
        need(type(header) is dict and self.pending is not None and not self.terminal, 'Reply state')
        action, self.pending = self.pending, None
        if self.task == 'NEURAL-077':
            status = header.get('status')
            if status == 'closed':
                need(set(header) == {'status', 'error', 'terminal'} and header['terminal'] is True and header['error'] in ('action_limit', 'image_limit', 'output_byte_limit') and not png, 'Closure projection')
                raise ValueError('Viewer resource closure')
            if self.rejected:
                need(header == {'status': 'rejected', 'error': 'Invalid action or parameters', 'remaining_actions': self.limits.max_actions - self.sequence} and not png, 'Original rejection')
            elif action['action'] == 'finalize':
                need(status in ('valid_unscored', 'invalid_response') and header == {'status': status, 'response_sha256': hashlib.sha256(action['response'].encode()).hexdigest(), 'terminal': True} and not png, 'First-final terminal acknowledgment')
                self.terminal = True
            else:
                self.state = self.next_state
                self.eeg_view(header, png)
        elif action['action'] == 'respond':
            need(header == {'kind': 'response_accepted', 'epoch_id': self.epoch_id(), 'completed_epochs': len(self.accepted) + 1} and not png, 'Accepted response acknowledgment')
            self.accepted.add(self.state['epoch'])
        elif action['action'] == 'finish':
            need(header == {'kind': 'complete', 'case_id': self.case, 'epochs': self.epochs} and not png, 'Whole-person terminal acknowledgment')
            self.terminal = True
        else:
            need(set(header) == {'kind', 'mode', 'epoch_id', 'state', 'clock_features', 'sample_rate_hz', 'signal_units', 'display_units', 'image'}, 'Sleep view fields')
            need(header['kind'] == 'view' and header['mode'] == self.condition and header['epoch_id'] == self.epoch_id() and header['state'] == self.state and header['sample_rate_hz'] == 100 and header['signal_units'] == 'V' and header['display_units'] == 'uV', 'Sleep view state')
            clock = header['clock_features']
            need(type(clock) is dict and set(clock) == set(self.t.v.CLOCK) and all(type(x) in (int, float) and math.isfinite(x) for x in clock.values()), 'Only scalar clock features')
            self.image(header, png)
            i = self.state['epoch']
            if self.state['start_sample'] <= i * 3000 and self.state['stop_sample'] >= (i + 1) * 3000 and self.state['channels'] == list(self.t.v.CHANNELS):
                self.seen.add(i)
        return self.terminal
