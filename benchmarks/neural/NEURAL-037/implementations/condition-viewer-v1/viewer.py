"""Restricted, single-context mean/count observation and exact-row submission."""
import base64
import copy
import math
from pathlib import Path
import stat
import numpy as np
import render
import source

ROW_BYTES = 8192
ROW_OUTPUT_TOKEN_RESERVATION = 8192  # Independent external quota; never inferred from bytes.
SESSION_BYTES = 4_500_000
PANEL_BYTES = 64_000_000
OBSERVATION_BYTES = 2_000_000


def load_view(root, context_id, bundle):
    io = bundle.io
    root = io.regular(root)
    index, rows = source.selected_rows(bundle, context_id)
    expected = {str(Path(row['target']).relative_to('view')): row for row in rows}
    files = set()
    for path in root.iterdir():
        s = path.lstat()
        if stat.S_ISDIR(s.st_mode) and path.name == 'arrays':
            for item in path.iterdir():
                t = item.lstat()
                io.need(stat.S_ISREG(t.st_mode) and t.st_nlink == 1, 'Ordinary selected training files')
                files.add('arrays/' + item.name)
        else:
            io.need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'Ordinary selected view files')
            files.add(path.name)
    io.need(files == set(expected), 'Exactly all32 selected view files; no extra paths')
    descriptor = expected['input.json']; input_pin = {k: descriptor[k] for k in ('bytes', 'sha256')}
    raw = io.read(root / 'input.json', 32768, input_pin)
    metadata = bundle.contract.validate(raw, index, rows, bundle.panel['packet_id'])
    io.need(metadata['query'] == bundle.panel['contexts'][index], 'Same public query geometry')
    # Authenticate all original non-array material too; it is not executed.
    for name, row in expected.items():
        if name != 'input.json' and not name.startswith('arrays/'):
            io.read(root / name, 1_000_000, {k: row[k] for k in ('bytes', 'sha256')}, retain=False)
    arrays = {}
    for row in metadata['training']:
        means = bundle.array.array_file(io.resolve(root, row['means']['path']), row['means'], np, '<f8', row['shape'])
        counts = bundle.array.array_file(io.resolve(root, row['counts']['path']), row['counts'], np, '<u2', row['shape'])
        io.need(np.isfinite(means).all() and np.all(counts <= 50) and np.any(counts > 0) and
                np.all(means[counts == 0] == 0),
                'Unchanged finite means and unavailable-source placeholders')
        means.flags.writeable = counts.flags.writeable = False
        arrays[row['acquisition'] + '_' + row['order']] = (means, counts)
    io.need(len(arrays) == 11, 'Complete eleven authorized conditions')
    return metadata, input_pin, arrays


class Session:
    """Trusted broker state. External model/process isolation is not established here."""
    def __init__(self, root, context_id, *, bundle=None):
        self.b = source.load() if bundle is None else bundle
        self.metadata, self.input_pin, self.arrays = load_view(root, context_id, self.b)
        self.query = self.metadata['query']
        self.rows = {}
        self.closed = False
        self.outcome = None
        self.actions = self.observations = self.response_bytes = self.observation_bytes = 0
        self.training_rows = sum(values[0].shape[0] for values in self.arrays.values())
        self.observation_limit = 2 * self.training_rows
        self.action_limit = self.observation_limit + len(self.query['cell_keys']) + 2

    def describe(self):
        return {'mode': 'restricted_condition_mean_viewer_with_exact_numeric_readout',
            'instructions': self.b.instructions, 'query': copy.deepcopy(self.query),
            'training': [{'condition': key, 'cells': a.shape[0], 'frames': a.shape[1]}
                         for key, (a, _) in self.arrays.items()],
            'training_only_scale': self.metadata['training_scale'],
            'budgets': {'observe_actions': self.observation_limit, 'answer_rows': len(self.query['cell_keys']),
                'answer_bytes_per_action': ROW_BYTES, 'external_output_tokens_per_row': ROW_OUTPUT_TOKEN_RESERVATION,
                'external_output_tokens_this_context': ROW_OUTPUT_TOKEN_RESERVATION * len(self.query['cell_keys']),
                'token_quota_measured_or_enforced_here': False, 'native_study_admission': 'unavailable'}}

    def act(self, raw):
        io = self.b.io
        io.need(not self.closed, 'Session already ended')
        self.actions += 1
        try:
            io.need(self.actions <= self.action_limit and type(raw) is bytes and len(raw) <= ROW_BYTES,
                    'Bounded complete typed action; truncation is not accepted')
            raw.decode('ascii')
            action = io.decode(raw)
            io.need(type(action) is dict and type(action.get('action')) is str, 'Typed action object')
            kind = action['action']
            if kind == 'describe':
                io.exact(action, ['action']); return self.describe()
            if kind == 'observe':
                io.exact(action, ['action', 'training_condition', 'cell_key'])
                self.observations += 1
                io.need(self.observations <= self.observation_limit, 'Observation budget exhausted')
                key = action['training_condition']; cell = action['cell_key']
                io.need(key in self.arrays and type(cell) is str, 'Only selected training condition')
                means, counts = self.arrays[key]
                keys = ['cell_%04d' % i for i in range(means.shape[0])]
                io.need(cell in keys, 'Original acquisition-local ROI key')
                index = keys.index(cell); values = means[index].tolist(); support = counts[index].tolist()
                png, legend = render.trace(values, support)
                result = {'condition': key, 'cell_key': cell, 'means': values, 'counts': support,
                    'png_base64': base64.b64encode(png).decode('ascii'), 'legend': legend}
                body = io.canonical(result)
                io.need(len(body) <= OBSERVATION_BYTES, 'Observation envelope')
                self.observation_bytes += len(body)
                return result
            if kind == 'submit':
                self.response_bytes += len(raw)
                io.exact(action, ['action', 'cell_key', 'values'])
                key, values = action['cell_key'], action['values']
                io.need(type(key) is str and key in self.query['cell_keys'] and key not in self.rows,
                        'One explicit response per query ROI; no duplicate replacement')
                io.need(type(values) is list and len(values) == self.query['frames'] and
                        all(type(v) in (int, float) and math.isfinite(v) for v in values),
                        'Every original frame needs an explicit finite number; no fill')
                self.rows[key] = values
                return {'accepted_cell_key': key, 'remaining_rows': len(self.query['cell_keys']) - len(self.rows)}
            if kind == 'finish':
                io.exact(action, ['action'])
                io.need(set(self.rows) == set(self.query['cell_keys']), 'No missing ROI/frame or subset completion')
                self.outcome = {'context_id': self.query['context_id'], 'status': 'complete',
                    'responses': [{'cell_key': key, 'values': self.rows[key]} for key in self.query['cell_keys']]}
            elif kind == 'abstain':
                io.exact(action, ['action', 'reason'])
                io.need(type(action['reason']) is str and 0 < len(action['reason']) <= 256, 'Explicit bounded abstention')
                self.outcome = {'context_id': self.query['context_id'], 'status': 'abstain', 'reason': action['reason']}
            else:
                raise ValueError('Unsupported action')
            self.closed = True
            return {'context_complete': self.outcome['status'] == 'complete', 'status': self.outcome['status']}
        except (ValueError, TypeError, KeyError, OverflowError, UnicodeError):
            self.closed = True
            self.outcome = None
            raise ValueError('Invalid or incomplete typed action; session failed') from None

    def result(self):
        self.b.io.need(self.closed and self.outcome is not None, 'Only explicit terminal response can be collected')
        value = {'schema': 'neural037-condition-viewer-session-v1', 'packet_id': self.b.panel['packet_id'],
            'context_id': self.query['context_id'], 'source_binding': self.b.source_binding,
            'instructions_pin': self.b.instructions_pin, 'input_pin': self.input_pin,
            'outcome': self.outcome, 'actions': self.actions, 'observations': self.observations,
            'response_bytes': self.response_bytes, 'observation_bytes': self.observation_bytes,
            'external_output_token_reservation': ROW_OUTPUT_TOKEN_RESERVATION * len(self.query['cell_keys']),
            'provider_tokens_measured': False, 'external_model_state_reset_verified': False,
            'runtime_qualified': False, 'scientific_qualified': False}
        self.b.io.need(len(self.b.io.canonical(value)) <= SESSION_BYTES, 'Complete session result cap')
        return value
