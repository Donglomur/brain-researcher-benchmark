"""Full public input admission and restricted views; never opens target bodies."""
from pathlib import Path
import math

from core import capture, descriptor, encoded, finite, integer, need, parse, pin, publish, relative
import projection


def body_pin(row):
    return descriptor({k: row[k] for k in ('bytes', 'sha256')})


def context(value, session, split, nuisance=False):
    fields = {'schema', 'split', 'session_id', 'unit_count', 'unit_axis_sha256', 'rows'}
    need(type(value) is dict and set(value) == fields and value['schema'] == 'neural060_context_v2'
         and value['split'] == split and value['session_id'] == session['session_id'], 'exact typed context')
    need(type(value['unit_count']) is int and value['unit_count'] == (0 if nuisance else session['unit_count']),
         'typed view unit count')
    need(value['unit_axis_sha256'] == (None if nuisance else session['unit_axis_sha256']), 'native axis binding')
    rows = value['rows']; expected = session['splits'][split]['case_ids']
    need(type(rows) is list and len(rows) == len(expected), 'all ordered context cases')
    for case, row in zip(expected, rows):
        allowed = projection.CONTEXT_FIELDS | ({'wheel_speed'} if split != 'test' else set())
        need(type(row) is dict and set(row) == allowed and row['case_id'] == case
             and row['session_id'] == session['session_id'], 'exact case join/no undeclared outcomes')
        for key in ('history_speed', 'history_position', 'history_offsets', 'target_offsets'):
            need(type(row[key]) is list and len(row[key]) == 50, 'full50 nuisance field')
            for number in row[key]:
                finite(number)
        need(all(x >= 0 for x in row['history_speed']) and row['history_position'][-1] == 0,
             'absolute speed and translated position')
        need(all(-1-1e-10 <= x < 0 for x in row['history_offsets'])
             and all(0 <= x < 1 for x in row['target_offsets']), 'retained actual sampling offsets')
        need(all(b > a for a, b in zip(row['history_offsets'], row['history_offsets'][1:]))
             and all(b > a for a, b in zip(row['target_offsets'], row['target_offsets'][1:])),
             'monotone actual sample clocks')
        sb = row['stimulus_block']
        need(type(sb) is list and len(sb) == 12 and all(type(x) in (int, float) and x in (0, 1) for x in sb)
             and sum(sb[:9]) == 1 and sum(sb[9:]) == 1, 'exact signed contrast/block encoding')
        need(finite(row['stimulus_latency_s']) > 0, 'stimulus precedes movement')
        if split != 'test':
            y = row['wheel_speed']
            need(type(y) is list and len(y) == 50 and all(finite(x) >= 0 for x in y),
                 'all50 public original training/validation targets')
    return value


class Packet:
    def __init__(self, root, projection_pin, source_bytes, preparation_pins, limits, budget):
        self.root, self.budget, self.limits = Path(root).absolute(), budget, limits
        sources = projection.admit_sources(source_bytes)
        raw, _ = capture(self.root/'operator/PROJECTION.json', projection_pin,
                         limits['projection_bytes'], budget, readonly=True)
        self.body = projection.admit_projection(parse(raw), sources)
        need(self.body['producer_sources'] == preparation_pins, 'exact independently qualified preparation source')
        self.projection_pin = pin(raw)
        self.stamps = {}
        # Authenticate ALL public bodies, not just the currently convenient case.
        for name, row in projection.public_file_map(self.body).items():
            path = self.root/relative(name)
            is_json = name.endswith('.json')
            cap = limits['context_bytes'] if name.endswith('/context.json') else limits['public_file_bytes']
            body, st = capture(path, body_pin(row), cap, budget, retain=is_json, readonly=True)
            self.stamps[name] = st
            if name == 'public/QUERY_INDEX.json':
                projection.admit_query(parse(body), self.body)
            elif is_json:
                # Session indexing is source-derived; no private provenance read.
                parts = name.split('/')
                session = next(x for x in self.body['sessions'] if x['session_id'] == parts[1])
                context(parse(body), session, parts[2])
        self.session_by_id = {x['session_id']: x for x in self.body['sessions']}
        self.index = {case: row['session_id'] for row in self.body['sessions']
                      for case in row['splits']['test']['case_ids']}

    def unchanged(self, rows):
        for row in rows:
            name = row['packet_path']
            _, st = capture(self.root/relative(name), body_pin(row), self.limits['public_file_bytes'],
                            self.budget, retain=False, readonly=True)
            need(st == self.stamps[name], 'public packet changed during whole study')

    def view(self, session, role, phase, destination, shifted=False):
        need(role in ('nuisance', 'joint') and phase in ('fit', 'infer', 'investigate'), 'named phase/role')
        need(type(shifted) is bool and (not shifted or phase == 'infer' and role == 'joint'),
             'test-only shifted replay; no shifted investigator/fit')
        splits = ('train', 'val') if phase == 'fit' else ('test',) if phase == 'infer' else ('train', 'val', 'test')
        mounts, descriptors, provenance = [], {}, []
        destination = Path(destination)
        for split in splits:
            view = session['splits'][split]
            row = view['context']
            source_name = row['path']
            raw, st = capture(self.root/relative(source_name), body_pin(row), self.limits['context_bytes'],
                              self.budget, readonly=True)
            need(st == self.stamps[source_name], 'context custody')
            value = context(parse(raw), session, split)
            if role == 'nuisance':
                value = dict(value, unit_count=0, unit_axis_sha256=None)
                context(value, session, split, nuisance=True)
                raw = encoded(value)
                path = destination/(split+'_context.json')
                pinned = publish(path, raw, self.budget, readonly=True)
            else:
                path = self.root/relative(source_name); pinned = body_pin(row)
            relative_name = split+'/context.json'
            mounts.append({'source': str(path), 'target': '/input/'+relative_name,
                           'pin': pinned, 'cap': self.limits['context_bytes']})
            descriptors[relative_name] = pinned
            provenance.append({'packet_path': source_name, **body_pin(row)})
            if role == 'joint':
                key = 'neural_shift10' if shifted else 'neural'
                row = view[key]
                source_name = row['path']
                _, st = capture(self.root/relative(source_name), body_pin(row), self.limits['public_file_bytes'],
                                 self.budget, retain=False, readonly=True)
                need(st == self.stamps[source_name], 'counts custody')
                relative_name = split+'/neural.h5'
                mounts.append({'source': str(self.root/relative(source_name)), 'target': '/input/'+relative_name,
                               'pin': body_pin(row), 'cap': self.limits['public_file_bytes']})
                descriptors[relative_name] = body_pin(row)
                provenance.append({'packet_path': source_name, **body_pin(row)})
        return {'mounts': mounts, 'files': descriptors, 'provenance': provenance,
                'unit_count': session['unit_count'] if role == 'joint' else 0}


def prediction(value, ids, source=None, model=None):
    need(type(value) is dict and set(value) == {'schema', 'request', 'source', 'model', 'rows'}
         and value['schema'] == 'neural060_candidate_predictions_v1', 'exact candidate prediction schema')
    descriptor(value['request']); descriptor(value['source']); descriptor(value['model'])
    if source is not None:
        need(value['source'] == source, 'same candidate source')
    if model is not None:
        need(value['model'] == model, 'same sealed model')
    need(type(value['rows']) is list and len(value['rows']) == len(ids), 'all current query cases')
    result = {}
    for row in value['rows']:
        need(type(row) is dict and set(row) == {'case_id', 'prediction'} and row['case_id'] in ids
             and row['case_id'] not in result, 'unique known output identity')
        values = row['prediction']
        need(type(values) is list and len(values) == 50, 'all50 output values')
        result[row['case_id']] = [finite(x) for x in values]
    need(set(result) == set(ids), 'full output membership')
    return result
