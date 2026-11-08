"""Independent invented engineering controls. No native/provider/scientific run."""
from pathlib import Path
import copy
import hashlib
import importlib
import importlib.metadata
import json
import sys
import types
from fractions import Fraction
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
manifest_bytes = (ROOT / 'RUNTIME_SOURCE_V2.json').read_bytes()
assert hashlib.sha256(manifest_bytes).hexdigest() == '321b9418d96c280f007972ff268c36113712fbd10791022710c78a9069e11bdc'
manifest = json.loads(manifest_bytes)
source_read = len(manifest_bytes)
for name, descriptor in manifest['files'].items():
    body = (ROOT / name).read_bytes()
    source_read += len(body)
    assert len(body) == descriptor['bytes'] and hashlib.sha256(body).hexdigest() == descriptor['sha256']
sys.path.insert(0, str(ROOT / 'program'))
import core
import numpy as np

encoded_bytes = 0
largest_encoding = 0
raw_encoded = core.encoded
def measured_encoded(value):
    global encoded_bytes, largest_encoding
    raw = raw_encoded(value)
    encoded_bytes += len(raw)
    largest_encoding = max(largest_encoding, len(raw))
    assert len(raw) <= 16384
    return raw
core.encoded = measured_encoded

def refuses(fn, kind=core.Refusal):
    try:
        fn()
    except kind:
        return
    raise AssertionError('Expected refusal: ' + repr(fn))

def equal(a, b):
    np.testing.assert_allclose(a, b, rtol=1e-12, atol=1e-14)

def inert_budget():
    return core.Budget(0., 100., 1 << 20, 1 << 20, clock=lambda: 1.)

def target_conversion_and_clock():
    import native_reader
    class Interval:
        def __init__(self, a, b, ids=None):
            self.start = np.array(a, dtype=np.float64)
            self.end = np.array(b, dtype=np.float64)
            if ids is not None:
                self.trial_index = np.array(ids, dtype=np.int64)
        def __and__(self, other):
            return Interval([2.01], [2.81])
    class Sampler:
        def __init__(self, sampling_intervals, shuffle):
            assert list(sampling_intervals) == ['fixed'] and shuffle is False
        def __iter__(self):
            yield types.SimpleNamespace(start=2.01, end=2.81)
    velocity = np.array([.10000000001, -.2000000001, .700000001], dtype=np.float64)
    wheel = types.SimpleNamespace(timestamps=np.array([0., .2, .5]), wheel_vel=velocity.copy(), wheel_speed=np.abs(velocity))
    sample = types.SimpleNamespace(absolute_start=12.01, domain=Interval([0.], [.8]), wheel=wheel,
        spikes=types.SimpleNamespace(timestamps=np.array([.01, .4]), unit_index=np.array([0, 1]), domain=Interval([0.], [.8])))
    data = types.SimpleNamespace(absolute_start=10.,
        task_aligned_intervals=types.SimpleNamespace(movement_window=Interval([2.], [3.], [7]), domain=Interval([2.], [3.])),
        wheel=types.SimpleNamespace(domain=Interval([2.], [3.])), ts1_test_domain=Interval([2.01], [2.81]),
        slice=lambda a, b: sample)
    sampler_module = types.ModuleType('torch_brain.samplers'); sampler_module.TrialSampler = Sampler
    with patch.dict(sys.modules, {'torch_brain': types.ModuleType('torch_brain'), 'torch_brain.samplers': sampler_module}), \
         patch.object(native_reader, 'anatomy', return_value=(np.zeros((2, 3)), np.zeros((2, 3), dtype=bool), ['A', 'B'])), \
         patch.object(native_reader, 'task_context', return_value=[None, 1., 0.]):
        rows = list(native_reader.iter_windows(data, 'evaluation', {'windows': 1, 'timestamps': 3, 'spikes': 2}, inert_budget()))
    assert len(rows) == 1
    row = rows[0]
    assert row['velocity'].dtype == row['speed'].dtype == np.dtype('float32')
    np.testing.assert_array_equal(row['velocity'], velocity.astype('float32'))
    np.testing.assert_array_equal(row['speed'], np.abs(row['velocity']))
    equal(row['times'], [.01, .21, .51]); equal(row['support'], [.01, .81])
    equal(row['spike_times'], [.02, .41]); equal(row['neural_domain'], [[.01, .81]])
    assert row['A0'] == 10. and row['source_onset'] == 2. and row['native_target_origin'] == 12.01

def qualification_before_effects():
    import preparation
    def poison(*a, **k):
        raise AssertionError('Effect before admission')
    with patch.object(preparation, 'cohort', return_value={}), patch.object(preparation, 'validate_authority', return_value={}), \
         patch.object(preparation, 'versions', side_effect=poison), patch.object(preparation, 'fresh', side_effect=poison):
        for result in (False, None, 1):
            refuses(lambda result=result: preparation.run({}, {}, inert_budget(), lambda *a: result))

def scientific_math():
    import features, scores
    window = {'spike_times': np.array([.005, .045, .065]), 'spike_units': np.array([0, 1, 0]),
        'neural_domain': np.array([[0., .01], [.04, .08]]), 'support': np.array([0., .08]),
        'times': np.array([0., .04, .98]), 'context': [0., None, 1.],
        'locations': np.zeros((2, 3)), 'location_missing': np.zeros((2, 3), dtype=bool), 'regions': ['A', 'B']}
    x, exposure, available = features.spike_features(window, 2)
    equal(exposure[:5], [.01, 0., .02, .02, 0.]); equal(x[0, 0], np.log(3.))
    equal(x[1, 2], np.log(2.)); equal(x[0, 3], np.log(2.))
    assert not available[1] and np.all(x[:, 1] == 0)
    bad = dict(window, spike_times=np.array([.015]), spike_units=np.array([0]))
    refuses(lambda: features.spike_features(bad, 2))
    rep = {'regions': ['<UNK>', '<MISSING>', 'A', 'B'], 'categories': [[0.], [], [1.]],
        'location_mean': np.zeros(3), 'location_scale': np.ones(3)}
    j = features.encode(window, rep, 'J')
    c = features.encode({k: v for k, v in window.items() if k not in ('spike_times', 'spike_units', 'neural_domain')}, rep, 'C')
    expected_masks = []
    for t in window['times']:
        expected_masks.append([int(0 <= int(np.floor(t/.02))+lag < 50 and available[int(np.floor(t/.02))+lag]) for lag in range(-5, 6)])
    np.testing.assert_array_equal(j['tabular'][:, -11:], expected_masks)
    assert c['unit'] is None and c['exposure'] is None and c['tabular'].shape[1] < j['tabular'].shape[1]
    assert sum(v.nbytes for v in j.values() if isinstance(v, np.ndarray)) < 131072
    matrix = np.array([[.1, 1.], [.1, 1.+1e-7], [.1, 1.-1e-7]])
    state = features.weighted_scaler(matrix, np.array([.2, .3, .5]))
    assert state['constant'].tolist() == [True, False]
    np.testing.assert_array_equal(features.standardized(matrix, state)[:, 0], np.zeros(3))
    values = [[np.array([[0., 0.], [2., 2.]]), np.array([[4., 4.]])], [np.array([[6., 6.], [8., 8.], [10., 10.]])]]
    sessions = [[(y, np.column_stack((np.zeros(len(y)), y[:, 1]))) for y in s] for s in values]
    score = scores.animal_score(sessions)
    scalar = [(int(y), Fraction(1, len(values)*len(s)*len(w))) for s in values for w in s for y in w[:, 0]]
    mean = sum(Fraction(y)*w for y, w in scalar)
    mse = sum(Fraction(y*y)*w for y, w in scalar)
    sst = sum((Fraction(y)-mean)**2*w for y, w in scalar)
    equal(score['mean'], [float(mean), float(mean)]); equal(score['mse'], [float(mse), 0.])
    equal(score['mae'], [float(mean), 0.]); equal(score['r2'], [float(1-mse/sst), 1.])
    assert score['support']['sessions'] == 2 and score['support']['windows'] == 3 and score['support']['timestamps'] == 6
    assert score['undefined_reason'] == [None, None]
    constants = [[(np.full_like(y, .1), np.zeros_like(y)) for y in s] for s in values]
    constant = scores.animal_score(constants)
    assert constant['r2'] == [None, None] and constant['sst'] == [0., 0.]
    assert constant['undefined_reason'] == ['exact constant target']*2
    equal(constant['mae'], [.1, .1]); equal(constant['mse'], [.01, .01])

def alias_order():
    import ordering, contracts, reference_models
    original = {'source': {'z': {'animal': 'last'}, 'a': {'animal': 'first'}, 'm': {'animal': 'first'}},
        'source_order': ['a', 'm', 'z'], 'source_animals': ['first', 'last'],
        'evaluation': {'v': {'animal': 'held'}}, 'evaluation_order': ['v'], 'eval_animals': ['held'], 'folds': {'first': 0, 'last': 1}}
    rename = {'z': 'AAA', 'a': 'ZZZ', 'm': 'MMM', 'v': 'QQQ'}
    renamed = copy.deepcopy(original)
    for role in ('source', 'evaluation'):
        renamed[role] = {rename[k]: v for k, v in original[role].items()}
        renamed[role+'_order'] = [rename[s] for s in original[role+'_order']]
    for fold in (0, 1, 'full'):
        old = contracts.source_animal_split(original, fold); new = contracts.source_animal_split(renamed, fold)
        assert new == tuple([rename[s] for s in rows] for rows in old)
    assert ordering.animals([{'animal': 'zzz', 'animal_ordinal': 0}, {'animal': 'aaa', 'animal_ordinal': 1}]) == ['zzz', 'aaa']
    refuses(lambda: ordering.animals([{'animal': 'zzz', 'animal_ordinal': 0}, {'animal': 'aaa', 'animal_ordinal': 0}]))
    def session(sid, animal, ordinal, y):
        window = {'context': [0., 1., None], 'support': np.array([0., 1.]), 'times': np.array([.05]),
            'locations': np.zeros((1, 3)), 'location_missing': np.zeros((1, 3), dtype=bool), 'regions': ['A'], 'labels': np.array([y], dtype=np.float64)}
        return {'session': sid, 'animal': animal, 'animal_ordinal': ordinal, 'regions': ['A'],
            'locations': window['locations'], 'location_missing': window['location_missing'], 'windows': [window]}
    rows = [session('a', 'first', 0, [0., 1.]), session('m', 'first', 0, [2., 4.]), session('z', 'last', 1, [5., 3.])]
    alt = copy.deepcopy(rows)
    for row in alt: row['session'] = rename[row['session']]
    left = reference_models.training_rows(rows, 'C', inert_budget()); right = reference_models.training_rows(alt, 'C', inert_budget())
    for index in (2, 3, 4): np.testing.assert_array_equal(left[index], right[index])
    equal(left[4], [.25, .25, .5])

def actual_artifact_bodies():
    import admission
    result = {'schema': 'invented', 'value': [1, 2]}; rp = core.pin(core.encoded(result))
    terminal = {'result': {'path': 'RESULT.json', 'pin': rp}, 'source': 'invented'}
    p = {'derived': {'members': [{'path': 'RESULT.json', 'pin': rp}]}, 'result_pin': rp, 'result': result,
        'terminal': terminal, 'native': {'artifacts': {'TERMINAL.json': core.pin(core.encoded(terminal))}}}
    assert admission.authenticate_product(p) is True
    for kind in ('result', 'terminal', 'duplicate', 'missing'):
        bad = copy.deepcopy(p)
        if kind == 'result': bad['result']['value'][0] = 9
        elif kind == 'terminal': bad['terminal']['source'] = 'changed'
        elif kind == 'duplicate': bad['derived']['members'].append(copy.deepcopy(bad['derived']['members'][0]))
        else: bad['derived']['members'][0]['path'] = 'other.json'
        refuses(lambda: admission.authenticate_product(bad))

def optional_treatment_and_provider():
    import optional_admission as oa
    roster = {'source': {'s': {'animal': 'source'}}, 'source_order': ['s'],
        'evaluation': {'e': {'animal': 'held'}, 'x': {'animal': 'other'}}, 'evaluation_order': ['x', 'e']}
    spec = {'panel': 'I/C/T0/r1', 'animal': 'held', 'session': 'e'}
    analysis = {'stage': 'analysis', 'panel': spec['panel'], 'mode': 'I', 'role': 'C', 'tool': 'T0', 'animal': 'held',
        'recipe': {'numeric_slots': []}, 'training': [{'session': 's'}], 'evaluation': [{'session': 'e'}], 'animal_sessions': ['e']}
    assert oa.analysis(analysis, spec, roster) is True
    for key, value in [('role', 'J'), ('tool', 'T1'), ('mode', 'F'), ('animal', 'other'), ('evaluation', [{'session': 'x'}])]:
        bad = copy.deepcopy(analysis); bad[key] = value
        refuses(lambda: oa.analysis(bad, spec, roster))
    method = {'program': {'pin': core.pin(b'invented source')}, 'recipe': {'numeric_slots': [{'prompt': 'Return the input.'}]}}
    fit = {'result': {'state': {'pin': core.pin(b'invented state')}}}
    request = dict(analysis, stage='numeric_features', current_session='e', training=[], recipe=method['recipe'],
        program=method['program'], state=fit['result']['state'], provider_values=[])
    assert oa.features(request, spec, roster, method, fit) is True
    for key, value in [('training', [{'session': 's'}]), ('state', {}), ('recipe', {'numeric_slots': []}), ('tool', 'T1')]:
        bad = copy.deepcopy(request); bad[key] = value
        refuses(lambda: oa.features(bad, spec, roster, method, fit))
    numbers = [1., 2.]; product = {'result': {'features': [numbers]}, 'result_pin': core.pin(b'feature-result')}
    following = dict(request, stage='infer', provider_values=[[3., 4.]])
    selection = {'provider': {'model': 'model', 'response_model': 'response-model', 'temperature': 0., 'seed_supported': True}}
    messages = [{'role': 'system', 'content': 'Return exactly JSON {"values": [finite numbers]}. Return the input.'},
        {'role': 'user', 'content': core.encoded(numbers).decode()}]
    payload = {'model': 'model', 'messages': messages, 'stream': False, 'max_tokens': 20, 'temperature': 0., 'seed': 13}
    response = core.encoded({'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': '{"values":[3.0,4.0]}'}}], 'model': 'response-model'})
    key = ((spec['panel'], 'held'), 5)
    events = {key: {'attempt': {'output_token_ceiling': 20, 'request_seed': 13, 'request': core.pin(core.encoded(payload))},
        'complete': {'response': core.pin(response), 'action': {'values': [3., 4.]}}}}
    bridge = {'operation': 'op', 'slot': 0, 'episode': [spec['panel'], 'held'], 'ordinal': 5, 'feature_result': product['result_pin'],
        'request': events[key]['attempt']['request'], 'response': core.pin(response), 'response_text': response.decode(), 'values': [3., 4.]}
    assert oa.numeric_bridge('op', product, following, [bridge], method, events, selection) == [key]
    for mutate in ('feature', 'prompt', 'response', 'consumer', 'episode', 'ordinal'):
        pp, ff, rr, mm = copy.deepcopy(product), copy.deepcopy(following), copy.deepcopy(bridge), copy.deepcopy(method)
        if mutate == 'feature': pp['result']['features'][0][0] = 9.
        elif mutate == 'prompt': mm['recipe']['numeric_slots'][0]['prompt'] += '!'
        elif mutate == 'response': rr['response_text'] += ' '
        elif mutate == 'consumer': ff['provider_values'][0][0] = 99.
        elif mutate == 'episode': rr['episode'][1] = 'other'
        else: rr['ordinal'] = 6
        refuses(lambda: oa.numeric_bridge('op', pp, ff, [rr], mm, events, selection))

def journal_panel_accounting():
    import journal, panel_budget, engine
    now = [1.]; parent = core.Budget(0., 100., 1 << 20, 1 << 20, clock=lambda: now[0])
    writes = []
    fake_os = types.SimpleNamespace(write=lambda fd, data: (writes.append(bytes(data)) or len(data)), fsync=lambda fd: None)
    j = journal.Journal.__new__(journal.Journal)
    j.budget = parent; j.cap = 131072; j.event_cap = 4096; j.fd = 123; j.sequence = 0; j.total = 0; j.chain = '0'*64; j.pending = None
    e = engine.Engine.__new__(engine.Engine); e.budget = parent; e.scope = None; e.record = j.append
    profile = {'wall_seconds': 20., 'read_bytes': 65536, 'write_bytes': 131072, 'native_cpu_ns': 1000, 'gpu_device_seconds': 0.}
    provider = {'endpoint': 'https://example.invalid/completions', 'wire_protocol': 'neural058_chat_json_v1', 'seed_supported': True, 'model': 'inert'}
    with patch.object(journal, 'os', fake_os):
        p = panel_budget.PanelBudget(parent, profile, 'I/C/T0/r1', e, provider, j.append, j)
        assert parent.write_bytes == p.write_bytes == 8192 and j.budget is p and e.budget is p
        j.append({'kind': 'invented_analysis', 'text': 'a'})
        assert parent.write_bytes == p.write_bytes == 16384
        result = p.finish({'id': 'I/C/T0/r1'})
        assert result['closed'] is True and result['write_reserved_bytes'] == 32768
        assert result['write_reserved_bytes'] == parent.write_bytes == p.write_bytes
        assert e.budget is parent and j.budget is parent and p.closed is True
        events, _ = journal.decode(b''.join(writes), event_cap=4096)
        assert [r['kind'] for r in events] == ['scope_started', 'invented_analysis', 'scope_completed', 'panel_completed']
        assert events[-1]['accounting']['write_reserved_bytes'] == parent.write_bytes
        token = j.reserve_event(); j.append_reserved({'kind': 'one_use'}, token)
        refuses(lambda: j.append_reserved({'kind': 'replay'}, token))
        # A new panel cannot turn a late fsync into successful completion.
        p2 = panel_budget.PanelBudget(parent, profile, 'F/C/T0/r1', e, provider, j.append, j)
        before = p2.write_bytes
        calls = [0]
        def late(fd):
            calls[0] += 1
            if calls[0] == 2: now[0] = p2.deadline
        fake_os.fsync = late
        refuses(lambda: p2.finish({'id': 'F/C/T0/r1'}))
        assert p2.write_bytes == before + 16384 and not p2.closed
        failed = p2.fail()
        assert failed['failed'] is True and failed['write_reserved_bytes'] == p2.write_bytes
        assert j.budget is parent and e.budget is parent
        assert sum(len(x) for x in writes) < 16384

def native_diagnostic_separation():
    import native_diagnostic, scores
    target = np.array([[0., 0.], [1., 1.], [2., 2.]])
    pred = np.full((3, 2), 1e20)
    class Metric:
        def update(self, p, y):
            with np.errstate(over='ignore', invalid='ignore'):
                self.value = np.float32(1.)-np.sum((p-y)**2, dtype=np.float32)/np.sum((y-np.mean(y, dtype=np.float32))**2, dtype=np.float32)
        def compute(self): return np.asarray(self.value)
    torch = types.ModuleType('torch'); torch.from_numpy = lambda x: x; torch.isfinite = np.isfinite
    tm = types.ModuleType('torchmetrics'); tm.R2Score = Metric
    with patch.dict(sys.modules, {'torch': torch, 'torchmetrics': tm}), patch.object(importlib.metadata, 'version', return_value='1.9.0'):
        diagnostic = native_diagnostic.session(target, pred, np.array([0, 3]), [{'source_trial': 1}])
        assert diagnostic['status'] == 'not_comparable' and 'reduction' in diagnostic['reason']
        score = scores.animal_score([[(target, pred)]])
        assert np.isfinite(score['r2']).all() and max(score['r2']) < 0
        class Broken(Metric):
            def update(self, *a): raise RuntimeError('inert dependency failure')
        tm.R2Score = Broken
        refuses(lambda: native_diagnostic.session(target, pred, np.array([0, 3]), [{'source_trial': 1}]), RuntimeError)
    # Ragged support remains explicit non-comparability without importing a metric.
    assert native_diagnostic.session(target, pred, np.array([0, 1, 3]), [{'source_trial': 1}, {'source_trial': 2}])['status'] == 'not_comparable'

groups = [target_conversion_and_clock, qualification_before_effects, scientific_math, alias_order,
    actual_artifact_bodies, optional_treatment_and_provider, journal_panel_accounting, native_diagnostic_separation]
results = []
for group in groups:
    try:
        group()
        results.append({'group': group.__name__, 'passed': True})
    except BaseException as error:
        results.append({'group': group.__name__, 'passed': False, 'type': type(error).__name__, 'message': str(error)})
        break
out = {'schema': 'neural058_independent_controls_v1', 'groups': results, 'complete': len(results) == len(groups) and all(r['passed'] for r in results),
    'runtime_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(), 'authenticated_source_reads': source_read,
    'conservative_additional_module_import_source_read_charge': sum(r['bytes'] for r in manifest['files'].values()),
    'observed_canonical_encoding_bytes': encoded_bytes, 'largest_canonical_encoding_bytes': largest_encoding,
    'fixture_debit_bytes': 8388608, 'scope': 'invented engineering only; explicit inert capability/dependency doubles; no authentic inputs, native/provider/backend/scientific operations',
    'numpy_version_observed': np.__version__, 'physical_OS_IO_RSS_external_library_working_set': 'not measured or certified'}
raw = (json.dumps(out, sort_keys=True, indent=2)+'\n').encode()
with (HERE / 'CONTROL_RESULTS_V1.json').open('xb') as handle: handle.write(raw)
print(raw.decode(), end='')
raise SystemExit(0 if out['complete'] else 1)
