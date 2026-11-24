"""Complete, targetless NEURAL-075 numeric observation and observer collection.

Trusted-host API only. Source/capture authority, provider isolation, effective
context capacity and authentic qualification are external, never inferred here.
"""
from dataclasses import dataclass
import ast
import hashlib
import io
import json
import math
from pathlib import Path
import stat
import time
import zipfile

import numpy as np

MODE = 'neural075_complete_numeric_observation_v1'
PROTOCOL = 'neural075-v1'
PEOPLE = tuple('Subject' + str(i) for i in range(1, 6))
ARMS = ('neural', 'no_neural', 'training_permuted')
PHASES = ('imagery', 'perception')
ROWS = {'imagery': 500, 'perception': 1750}
CASES = tuple((a, f'{p}/{r}/{t}') for a in ('A', 'B') for p in PEOPLE for r in ARMS for t in PHASES)
COMMON = ('train_y', 'bank', 'groups', 'runs')
ACTION_BYTES = 4096
FLOAT_ENTRY_BYTES = 25  # At most24 ASCII chars for finite float64 repr, plus comma.
NPZ_CAP = 512 * 2**20
_BINDINGS = json.loads((Path(__file__).parent / 'SOURCE_BINDINGS.json').read_bytes())
MATERIAL_PINS = _BINDINGS['material_pins']
CATEGORIES = tuple(_BINDINGS['categories'])
_ISSUED = object()


def need(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def pin(raw):
    need(type(raw) is bytes, 'Immutable captured bytes')
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def _json(raw):
    need(type(raw) is bytes, 'Immutable JSON bytes')
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, 'Duplicate JSON field')
            value[key] = item
        return value
    def constant(_):
        raise ValueError('Nonfinite JSON constant')
    def floating(value):
        number = float(value)
        need(math.isfinite(number), 'Finite JSON float')
        return number
    try:
        return json.loads(raw.decode('utf8'), object_pairs_hook=pairs,
                          parse_constant=constant, parse_float=floating)
    except (UnicodeError, OverflowError, RecursionError) as error:
        raise ValueError('Malformed JSON') from error


def _exact(value, fields, message):
    need(type(value) is dict and set(value) == set(fields), message)


def _descriptor(value):
    _exact(value, ('bytes', 'sha256'), 'Exact descriptor')
    need(type(value['bytes']) is int and value['bytes'] > 0 and
         type(value['sha256']) is str and len(value['sha256']) == 64 and
         all(c in '0123456789abcdef' for c in value['sha256']), 'Positive exact descriptor')


def _original_decoder():
    """Authenticate the bundled original primitive decoder, compile only arrays.

    No source CLI, filesystem loader, candidate or reference fit is executed.
    This exact helper is already part of every original public prepared view.
    """
    raw = (Path(__file__).parent / 'materials/public/array_io.py').read_bytes()
    need(pin(raw) == MATERIAL_PINS['public/array_io.py'], 'Original primitive decoder source')
    tree = ast.parse(raw)
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'arrays']
    need(len(selected) == 1, 'One original primitive decoder')
    namespace = {'np': np, 'zipfile': zipfile, 'io': io, 'stat': stat, 'math': math, 'need': need}
    exec(compile(ast.Module(body=selected, type_ignores=[]), '<pinned-neural075-array-decoder>', 'exec'), namespace)
    return namespace['arrays']


_ARRAYS = _original_decoder()


@dataclass(frozen=True)
class PreparedView:
    """Already captured PUBLIC view. Never pass an operator preparation tree."""
    identity: bytes
    context: bytes
    inputs: bytes
    materials: tuple  # Exact (original relative role, immutable source bytes) pairs.


@dataclass(frozen=True)
class Limits:
    max_captured_bytes: int
    max_total_decoded_bytes: int
    max_single_decoded_bytes: int
    max_input_scalars: int
    max_numeric_pages: int
    max_exposure_bytes: int
    max_actor_bytes: int
    max_collection_bytes: int
    max_actions: int
    page_values: int
    read_repetitions: int
    draft_repetitions: int
    deadline: float

    def check(self):
        for name in self.__dataclass_fields__:
            if name != 'deadline':
                value = getattr(self, name)
                need(type(value) is int and 0 < value < 2**63, 'Explicit positive logical capacity: ' + name)
        need(self.page_values <= 4096 and self.read_repetitions <= 100 and self.draft_repetitions <= 100,
             'Bounded explicit partition/repetition policy')
        need(self.max_single_decoded_bytes <= NPZ_CAP, 'Original expanded NPZ ceiling')
        need(type(self.deadline) in (int, float) and math.isfinite(self.deadline), 'Explicit monotonic deadline')
        self.tick()

    def tick(self):
        need(time.monotonic() < self.deadline, 'Observation deadline')


def _context(view, access, case):
    need(type(view) is PreparedView and all(type(x) is bytes for x in (view.identity, view.context, view.inputs))
         and type(view.materials) is tuple, 'Immutable prepared-view capture')
    need(len(view.context) <= 2**20 and len(view.identity) <= 30000 and len(view.inputs) <= 200000000,
         'Original bounded public operands')
    c = _json(view.context)
    _exact(c, ('protocol', 'case_id', 'person', 'arm', 'phase', 'categories', 'trial_ids',
               'design_sha256', 'inputs', 'n_units', 'access_condition'), 'Original exact context fields')
    person, arm, phase = case.split('/')
    need(c['protocol'] == PROTOCOL and c['case_id'] == case and c['person'] == person and
         c['arm'] == arm and c['phase'] == phase and c['access_condition'] == access and
         type(c['n_units']) is int and c['n_units'] == 1000, 'Exact complete case identity and features')
    need(c['categories'] == list(CATEGORIES), 'Original exact ordered50 category bank')
    ids = c['trial_ids']
    need(type(ids) is list and len(ids) == ROWS[phase] and len(set(ids)) == len(ids) and
         all(type(x) is str and len(x) == 25 and x[0] == 'q' and
             all(ch in '0123456789abcdef' for ch in x[1:]) for x in ids), 'Complete original opaque trial rows')
    need(type(c['design_sha256']) is str and len(c['design_sha256']) == 64 and
         all(ch in '0123456789abcdef' for ch in c['design_sha256']), 'Original opaque design identity')
    _exact(c['inputs'], ('path', 'bytes', 'sha256'), 'Original input descriptor')
    need(c['inputs']['path'] == 'inputs.npz' and
         {k: c['inputs'][k] for k in ('bytes', 'sha256')} == pin(view.inputs), 'Exact captured prepared inputs')
    wanted = {name: pp for name, pp in MATERIAL_PINS.items()
              if name.startswith('public/') or access == 'B'}
    need(all(type(row) is tuple and len(row) == 2 and type(row[0]) is str and type(row[1]) is bytes
             for row in view.materials), 'Immutable named source text')
    material = dict(view.materials)
    need(len(material) == len(view.materials) and set(material) == set(wanted), 'Complete exact A/B materials')
    for name, body in material.items():
        need(pin(body) == wanted[name], 'Exact permitted source material')
        body.decode('utf8')
    identity = _json(view.identity)
    _exact(identity, ('schema', 'case_id', 'access', 'files', 'context_pin'), 'Original input identity fields')
    expected = {'case.json': pin(view.context), 'inputs.npz': pin(view.inputs), **wanted}
    need(identity['schema'] == 'neural075_input_identity_v1' and identity['case_id'] == case and
         identity['access'] == access and identity['files'] == expected and
         identity['context_pin'] == pin(view.context), 'Exact complete prepared view identity')
    return c


def _decode(view, context, limit):
    keys = COMMON + (() if context['arm'] == 'no_neural' else ('train_x', 'query_x'))
    # Inspect header extents before the original decoder allocates any array.
    total = 0
    with zipfile.ZipFile(io.BytesIO(view.inputs)) as z:
        members = z.infolist()
        need(len(members) == len(keys) and {m.filename for m in members} == {k + '.npy' for k in keys},
             'Exact arm members; no neural array in no_neural')
        for m in members:
            with z.open(m) as stream:
                version = np.lib.format.read_magic(stream)
                if version == (1, 0):
                    shape, _, dtype = np.lib.format.read_array_header_1_0(stream, max_header_size=4096)
                elif version == (2, 0):
                    shape, _, dtype = np.lib.format.read_array_header_2_0(stream, max_header_size=4096)
                else:
                    raise ValueError('Original primitive NPY version')
            need(dtype.fields is None and dtype.kind in 'if' and dtype.itemsize in (4, 8) and
                 1 <= len(shape) <= 2 and all(type(n) is int and 0 < n <= 200000 for n in shape),
                 'Bounded original primitive shape and dtype')
            total += math.prod(shape) * dtype.itemsize
            need(total <= limit, 'Single-view decoded capacity before allocation')
    data = _ARRAYS(view.inputs, keys, min(NPZ_CAP, limit + 6 * 8192))
    shapes = {'train_y': (1200, 1000), 'bank': (50, 1000), 'groups': (1200,), 'runs': (1200,)}
    if context['arm'] != 'no_neural':
        need(data['train_x'].ndim == 2, 'Complete native training matrix')
        width = data['train_x'].shape[1]
        shapes.update(train_x=(1200, width), query_x=(ROWS[context['phase']], width))
    for name in keys:
        a = data[name]
        need(a.shape == shapes[name], 'Full original shape: ' + name)
        if name == 'groups':
            need(a.dtype.kind == 'i' and a.dtype.itemsize in (4, 8) and a.dtype.isnative,
                 'Original native signed group-index dtype')
            need(np.array_equal(np.unique(a), np.arange(150)) and
                 np.all(np.bincount(a.astype(np.int64)) == 8), 'All150 opaque support groups/eight images')
        else:
            need(a.dtype == np.dtype('float64') and np.isfinite(a).all(), 'Finite original float64: ' + name)
        a.flags.writeable = False
    need(len(np.unique(data['runs'])) == 24, 'Complete24 finite support runs')
    return data


def _digest_array(a):
    # Native row/column index order, with exact float64 bits (including -0).
    return a.dtype.str, a.shape, hashlib.sha256(a.tobytes(order='C')).hexdigest()


def _same(table, key, value, message):
    if key in table:
        need(table[key] == value, message)
    else:
        table[key] = value


def _layout(data, page_values):
    return tuple((name, a.dtype.str, tuple(a.shape), int(a.size), math.ceil(a.size / page_values))
                 for name, a in data.items())


def _description(c, layout):
    return {'event': 'describe', 'mode': MODE, 'context': c,
            'index_order': 'C: original rows, then original columns; no reduction or transform',
            'arrays': [{'name': n, 'dtype': d, 'shape': list(s), 'scalars': size, 'pages': pages}
                       for n, d, s, size, pages in layout],
            'visual_only': False, 'no_tools_enforcement_established': False}


def _prediction(c, rows):
    return {'protocol': PROTOCOL, 'case_id': c['case_id'], 'context_sha256': c['_context_sha256'],
            'categories': c['categories'], 'trial_ids': c['trial_ids'], 'scores': rows}


@dataclass(frozen=True)
class _AdmittedPanel:
    views: tuple
    layouts: tuple
    limits: Limits
    selected_pins: tuple
    requirements: bytes  # Operator-only preflight report, not provider qualification.
    seal: object


def preflight(views, selected_identity_pins, limits):
    """Admit ALL60 complete views and capacity before issuing a participant API.

    selected_identity_pins are independently selected operator operands, not
    proof of source authenticity/authority. No target or design body is accepted.
    """
    need(type(limits) is Limits, 'Explicit whole-panel limits')
    limits.check()
    need(type(views) is tuple and len(views) == 60 and type(selected_identity_pins) is tuple and
         len(selected_identity_pins) == 60, 'Complete original60 selected views')
    totals = dict(captured_bytes=0, total_decoded_bytes=0, single_decoded_bytes=0,
                  input_scalars=0, numeric_pages=0, exposure_bytes=0, actor_bytes=0,
                  collection_bytes=32768, actions=0, response_rows=0, response_scalars=0)
    layouts, selected, support, common = [], [], {}, {}
    for (access, case), view, expected in zip(CASES, views, selected_identity_pins):
        limits.tick()
        _descriptor(expected)
        need(pin(view.identity) == expected, 'Independently selected prepared view')
        c = _context(view, access, case)
        totals['captured_bytes'] += sum(map(len, (view.identity, view.context, view.inputs))) + sum(len(b) for _, b in view.materials)
        need(totals['captured_bytes'] <= limits.max_captured_bytes, 'Whole captured input capacity')
        data = _decode(view, c, limits.max_single_decoded_bytes)
        decoded = sum(a.nbytes for a in data.values())
        totals['total_decoded_bytes'] += decoded
        totals['single_decoded_bytes'] = max(totals['single_decoded_bytes'], decoded)
        totals['input_scalars'] += sum(a.size for a in data.values())
        _same(support, ('design',), c['design_sha256'], 'One prepared design across60')
        _same(support, ('trial', c['person'], c['phase']), tuple(c['trial_ids']), 'Matched original query support across arms/accesses')
        for name, a in data.items():
            if name in ('bank', 'train_y'):
                key = (name, 'permuted' if name == 'train_y' and c['arm'] == 'training_permuted' else 'original')
            elif name == 'query_x':
                key = (name, c['person'], c['phase'])
            else:
                key = (name, c['person'])
            _same(common, key, _digest_array(a), 'Same prepared values/dtypes/order across matched contexts')
        layout = _layout(data, limits.page_values)
        layouts.append(layout)
        pages = sum(r[4] for r in layout)
        totals['numeric_pages'] += pages
        exposure = len(encoded(_description(c, layout)))
        for name, body in view.materials:
            exposure += len(encoded({'event': 'material', 'path': name, 'text': body.decode('utf8')}))
        for name, dtype, shape, size, count in layout:
            # Every page gets the conservative largest offset/header envelope.
            header = len(encoded({'event': 'numeric_page', 'array': name, 'dtype': dtype,
                                  'shape': list(shape), 'offset': size, 'values': []}))
            exposure += count * header + FLOAT_ENTRY_BYTES * size
        read_actions = (1 + len(view.materials) + pages) * limits.read_repetitions
        answer_actions = ROWS[c['phase']] * limits.draft_repetitions
        actions = read_actions + answer_actions + 1  # final case freeze
        # Include acknowledgments in provider-input byte reservation too.
        totals['exposure_bytes'] += exposure * limits.read_repetitions + 128 * (answer_actions + 1)
        totals['actions'] += actions
        totals['actor_bytes'] += ACTION_BYTES * actions
        cc = dict(c, _context_sha256=pin(view.context)['sha256'])
        matrix_bound = ROWS[c['phase']] * (50 * FLOAT_ENTRY_BYTES + 3)
        totals['collection_bytes'] += len(encoded(_prediction(cc, []))) + matrix_bound
        totals['response_rows'] += ROWS[c['phase']]
        totals['response_scalars'] += ROWS[c['phase']] * 50
        selected.append((expected['bytes'], expected['sha256']))
        del data
        for key in ('total_decoded_bytes', 'input_scalars', 'numeric_pages', 'exposure_bytes',
                    'actor_bytes', 'collection_bytes', 'actions'):
            need(totals[key] <= getattr(limits, 'max_' + key), 'Whole-condition capacity: ' + key)
    limits.tick()
    need(totals['response_rows'] == 67500 and totals['response_scalars'] == 3375000, 'Complete original response obligation')
    report = {'schema': 'neural075_numeric_observation_preflight_v1', 'mode': MODE,
              'contexts_admitted': 60, 'requirements': totals,
              'page_values': limits.page_values, 'read_repetitions': limits.read_repetitions,
              'draft_repetitions': limits.draft_repetitions,
              'bounds_are_conservative': True, 'provider_tokens_measured': False,
              'provider_context_qualified': False, 'runtime_qualified': False,
              'source_authenticity_or_authority_established': False,
              'training_permutation_reconstructed': False, 'targets_read': False}
    return _AdmittedPanel(views, tuple(layouts), limits, tuple(selected), encoded(report), _ISSUED)


@dataclass(frozen=True)
class ObserverResult:
    """Operator-only targetless result; no program/ClosedPair production receipt."""
    report: bytes
    predictions: tuple  # (access, case_id, exact original-format prediction bytes)


class ObserverSession:
    """Only dispatch(bytes)->bytes belongs on participant transport.

    The object, admitted views, preflight report and finish result are operator
    only. This class is not a sandbox against arbitrary host Python.
    """
    def __init__(self, admitted):
        need(type(admitted) is _AdmittedPanel and admitted.seal is _ISSUED, 'Completed whole60 preflight required')
        admitted.limits.check()
        self._panel = admitted
        self._index = 0
        self._data = None
        self._context = None
        self._trial_set = frozenset()
        self._drafts = {}
        self._draft_counts = {}
        self._reads = {}
        self._frozen = []
        self._failed = False
        self._finished = False
        self._actions = self._actor_bytes = self._exposure_bytes = 0
        self._prediction_bytes = 0

    def _current(self):
        need(self._index < 60, 'All contexts already frozen')
        view = self._panel.views[self._index]
        if self._context is None:
            self._context = _json(view.context)
            self._trial_set = frozenset(self._context['trial_ids'])
        return view, self._context, self._panel.layouts[self._index]

    def _read(self, key):
        count = self._reads.get(key, 0) + 1
        need(count <= self._panel.limits.read_repetitions, 'Frozen read repetition budget')
        self._reads[key] = count

    def dispatch(self, raw):
        limits = self._panel.limits
        need(not self._failed and not self._finished, 'Observer session closed')
        try:
            limits.tick()
            need(type(raw) is bytes and 0 < len(raw) <= ACTION_BYTES, 'Bounded whole typed action')
            self._actions += 1
            self._actor_bytes += len(raw)
            need(self._actions <= limits.max_actions and self._actor_bytes <= limits.max_actor_bytes,
                 'Whole-condition participant action capacity')
            action = _json(raw)
            need(type(action) is dict and type(action.get('action')) is str, 'Closed typed action')
            view, c, layout = self._current()
            kind = action['action']
            if kind == 'describe':
                _exact(action, ('action',), 'Describe fields')
                self._read(('describe',))
                value = _description(c, layout)
            elif kind == 'material':
                _exact(action, ('action', 'path'), 'Material fields')
                material = dict(view.materials)
                name = action['path']
                need(type(name) is str and name in material, 'Only original permitted material')
                self._read(('material', name))
                value = {'event': 'material', 'path': name, 'text': material[name].decode('utf8')}
            elif kind == 'numeric_page':
                _exact(action, ('action', 'array', 'page'), 'Numeric page fields')
                name, page = action['array'], action['page']
                match = [r for r in layout if r[0] == name]
                need(type(name) is str and len(match) == 1 and type(page) is int and
                     0 <= page < match[0][4], 'Exact original array and fixed page')
                self._read(('page', name, page))
                if self._data is None:
                    self._data = _decode(view, c, limits.max_single_decoded_bytes)
                array = self._data[name]
                start = page * limits.page_values
                values = array.reshape(-1, order='C')[start:start + limits.page_values].tolist()
                value = {'event': 'numeric_page', 'array': name, 'dtype': array.dtype.str,
                         'shape': list(array.shape), 'offset': start, 'values': values}
            elif kind == 'draft_row':
                _exact(action, ('action', 'trial_id', 'scores'), 'Explicit50-score draft fields')
                key, scores = action['trial_id'], action['scores']
                need(type(key) is str and key in self._trial_set and type(scores) is list and len(scores) == 50,
                     'Original trial ID and all50 explicit scores')
                need(all(type(v) in (int, float) and math.isfinite(v) and abs(v) <= 1000000 for v in scores),
                     'Original finite bounded score numbers; no implicit filling')
                count = self._draft_counts.get(key, 0) + 1
                need(count <= limits.draft_repetitions, 'Frozen draft repetition budget')
                self._draft_counts[key] = count
                self._drafts[key] = scores
                value = {'event': 'draft_accepted', 'trial_id': key}
            elif kind == 'freeze_case':
                _exact(action, ('action',), 'Freeze fields')
                need(set(self._drafts) == set(c['trial_ids']), 'Complete500/1750 rows before case freeze')
                cc = dict(c, _context_sha256=pin(view.context)['sha256'])
                prediction = encoded(_prediction(cc, [self._drafts[key] for key in c['trial_ids']]))
                need(len(prediction) <= 4 * 2**20, 'Original per-case prediction bound')
                self._prediction_bytes += len(prediction)
                need(self._prediction_bytes + 32768 <= limits.max_collection_bytes, 'Complete captured response capacity')
                access, case = CASES[self._index]
                self._frozen.append((access, case, prediction))
                self._index += 1
                self._data = None
                self._context = None
                self._trial_set = frozenset()
                self._drafts, self._draft_counts, self._reads = {}, {}, {}
                value = {'event': 'case_frozen', 'contexts_frozen': self._index, 'required_contexts': 60}
            else:
                raise ValueError('Unknown observation action')
            body = encoded(value)
            self._exposure_bytes += len(body)
            need(self._exposure_bytes <= limits.max_exposure_bytes, 'Whole-condition observation traffic capacity')
            limits.tick()
            return body
        except (ValueError, TypeError, KeyError, OverflowError, UnicodeError, OSError, zipfile.BadZipFile):
            self._failed = True
            self._data = None
            raise ValueError('Observer action failed; no partial collection or automatic retry') from None

    def finish(self):
        """One operator-only complete collection, with explicit unattested status."""
        need(not self._failed and not self._finished and self._index == 60 and len(self._frozen) == 60,
             'Exactly all60 frozen observer responses required')
        self._panel.limits.tick()
        rows = []
        for i, (access, case, body) in enumerate(self._frozen):
            need((access, case) == CASES[i], 'Original complete ordered observer roster')
            rows.append({'access': access, 'case_id': case, 'prediction': pin(body),
                         'context': pin(self._panel.views[i].context),
                         'prepared_identity': {'bytes': self._panel.selected_pins[i][0],
                                               'sha256': self._panel.selected_pins[i][1]}})
        report = encoded({'schema': 'neural075_observer_collection_v1', 'mode': MODE,
                          'contexts': rows, 'response_rows': 67500, 'response_scalars': 3375000,
                          'preflight': pin(self._panel.requirements),
                          'actions': self._actions, 'actor_bytes': self._actor_bytes,
                          'exposure_bytes': self._exposure_bytes,
                          'observer_execution_attested': False, 'provider_context_qualified': False,
                          'no_tools_enforcement_established': False, 'program_commitment': None,
                          'closed_program_receipt': False, 'private_production_grader_compatible': False,
                          'targets_read': False, 'scoring_performed': False,
                          'scientific_qualification_added': False})
        need(len(report) <= 32768 and self._prediction_bytes + len(report) <= self._panel.limits.max_collection_bytes,
             'Complete observer collection serialized capacity')
        self._panel.limits.tick()
        self._finished = True
        return ObserverResult(report, tuple(self._frozen))
