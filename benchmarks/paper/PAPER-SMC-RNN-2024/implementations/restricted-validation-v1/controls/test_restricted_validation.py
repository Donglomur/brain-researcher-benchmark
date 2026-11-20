"""Generated restricted-VALID controls, never original-data/inference qualification.

The projector positive uses an isolated, explicitly synthetic authority namespace.
The grader uses original panel metadata and a declared packet-metadata contract;
it does not authenticate physical original packet delivery. Actual HDF5 shapes,
projection, snapshots and guards remain real. No model or native job is run.
"""
import copy
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
ART = None
ACTIVE = False
MODULES = {}
SOURCE_IDENTITIES = {}
FIXTURE_LIMIT = 800 * 1024
WRITTEN = 0
VERSIONS = {}
OBS = {'original_authority_refusals': 0, 'forbidden_numeric_reads': 0,
       'projector_authority': 'generated_only', 'grader_packet_delivery_authenticated': False,
       'expanded_h5_projection_bytes': 0, 'canonical_f8_projection_bytes': 0,
       'target_loader_calls': 0, 'evaluator_calls': 0}
EXPANDED_BOUND = 1280 * 1024**2
REFERENCE_PROFILE = {'cpu_seconds':60000,'wall_seconds':10800,'memory_bytes':8589934592,'threads':6}
SHARED = {}


def audit(event, args):
    if not ACTIVE:
        return
    if event in {'subprocess.Popen', 'os.fork', 'os.forkpty', 'os.exec', 'os.posix_spawn',
                 'os.system', 'os.kill', 'os.killpg', 'resource.setrlimit',
                 'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
        raise AssertionError('Native/network boundary forbidden: ' + event)
    if event == 'import' and args[0].split('.')[0] in {'torch', 'jax', 'tensorflow', 'pyro'}:
        raise AssertionError('Original/heavy model import forbidden')


sys.addaudithook(audit)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def account():
    """Charge every observed complete/partial file version, including deletions."""
    global WRITTEN
    if ART is None:
        return
    for base, dirs, files in os.walk(ART):
        for name in files:
            p = Path(base) / name
            s = p.stat()
            version = (s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            if VERSIONS.get(str(p)) != version:
                WRITTEN += s.st_size
                VERSIONS[str(p)] = version
    if WRITTEN > FIXTURE_LIMIT:
        raise AssertionError('Cumulative serialized fixture allowance exceeded')


def reserve(amount):
    account()
    if WRITTEN + amount > FIXTURE_LIMIT:
        raise AssertionError('Prospective serialized fixture allowance exhausted')


def put(path, value):
    raw = value if isinstance(value, bytes) else encoded(value)
    reserve(len(raw)); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw); account()
    return {'path': str(path), **pin(raw)}


def ref(path):
    raw = path.read_bytes()
    return {'path': str(path), **pin(raw)}


def initialize():
    global ART
    if ART is not None:
        return
    text = os.environ.get('ARTIFACT_DIR')
    if not text:
        raise ValueError('Fresh external ARTIFACT_DIR required')
    p = Path(text)
    if not p.is_absolute() or str(p) != text or p.resolve() != p or '..' in p.parts:
        raise ValueError('Canonical absolute ARTIFACT_DIR required')
    if os.path.lexists(p) or not p.parent.is_dir():
        raise ValueError('Fresh ARTIFACT_DIR with existing parent required')
    if p.is_relative_to(ROOT) or ROOT.is_relative_to(p):
        raise ValueError('ARTIFACT_DIR must be outside the component source layout')
    if any((q / '.git').exists() for q in (p.parent, *p.parent.parents)):
        raise ValueError('ARTIFACT_DIR must be outside Git worktrees')
    p.mkdir(mode=0o700); ART = p


def load(name, relative):
    if name not in MODULES:
        p = ROOT / relative; raw = p.read_bytes()
        SOURCE_IDENTITIES[relative] = pin(raw)
        module = types.ModuleType(name); module.__file__ = str(p)
        sys.modules[name] = module
        exec(compile(raw, str(p), 'exec'), module.__dict__)
        MODULES[name] = module
    return MODULES[name]


def clone(module, changes):
    """Identical code objects, isolated globals; production globals never mutate."""
    ns = dict(module.__dict__)
    for name, value in tuple(ns.items()):
        if isinstance(value, types.FunctionType) and value.__globals__ is module.__dict__:
            f = types.FunctionType(value.__code__, ns, value.__name__, value.__defaults__, value.__closure__)
            f.__kwdefaults__ = value.__kwdefaults__; ns[name] = f
    ns.update(changes)
    return types.SimpleNamespace(**ns)


def scientific():
    import numpy as np
    import h5py
    if np.__version__ != '1.26.3' or h5py.__version__ != '3.11.0':
        raise AssertionError('Selected source-control scientific dependencies changed')
    return h5py, np


def h5_file(path, shapes, *, rates=False, excluded=None):
    """Full shapes, genuine observed fill values and sparse order canaries."""
    h5py, np = scientific()
    reserve(96 * 1024)
    try:
        with h5py.File(path, 'w') as f:
            group = f.create_group('mc_maze_20') if rates else f
            for name, shape in shapes.items():
                dtype = '<f4' if rates else '|u1'
                item = group.create_dataset(name, shape=shape, dtype=dtype,
                    fillvalue=1.0 if rates else (19 if excluded and name in excluded else 0),
                    chunks=(min(32 if rates else 16, shape[0]), shape[1], shape[2]), compression='gzip',
                    compression_opts=9, track_times=False)
                if not excluded or name not in excluded:
                    item[0, 0, 0] = 1.25 if rates else 0
                    item[1, 0, 0] = 1.5 if rates else 2
    finally:
        account()
    return ref(path)


def tensor_pin(item, np):
    h = hashlib.sha256(json.dumps(list(item.shape), separators=(',', ':')).encode())
    for first in range(0, item.shape[0], 16):
        block = item[first:first + 16]
        OBS['expanded_h5_projection_bytes'] += block.nbytes
        raw = np.asarray(block, dtype='<f8', order='C').tobytes(order='C')
        OBS['canonical_f8_projection_bytes'] += len(raw); h.update(raw)
    return h.hexdigest()


def projection_fixture():
    if 'projection' in SHARED:
        return SHARED['projection']
    p = load('project_validation', 'projection/project_validation.py')
    h5py, np = scientific()
    root = ART / 'projection-inputs'; root.mkdir()
    rows = {}
    content = {}
    for role in ('train', 'eval'):
        shapes = {**p.SHAPES[role], **p.EXCLUDED_SOURCE_SHAPES[role]}
        rows[role] = h5_file(root / (role + '.h5'), shapes, excluded=p.EXCLUDED_SOURCE_SHAPES[role])
        with h5py.File(rows[role]['path'], 'r') as f:
            for name in p.SHAPES[role]: content[name] = tensor_pin(f[name], np)
    identity = {'conditions': list(range(108)),
        'neurons': {'spikes': ['in-' + str(i) for i in range(137)],
                    'heldout_spikes': ['out-' + str(i) for i in range(45)]},
        'ordered_trials': {'train': list(range(1721)), 'val': list(range(1721, 2295)),
                           'test': list(range(2295, 2869))}}
    order = {'trial_indices_sha256': p.digest(identity['ordered_trials']),
             'neuron_indices_sha256': p.digest(identity['neurons']),
             'conditions_sha256': p.digest(identity['conditions']),
             'tensor_trial_indices_sha256': p.digest({'train': identity['ordered_trials']['train'],
                                                     'eval': identity['ordered_trials']['val']})}
    rows['identity'] = put(root / 'identity.json', identity)
    rows['panel'] = put(root / 'panel.json', {'fixture': 'generated authority only', 'phase': 'val'})
    pins = {k: {a: v[a] for a in ('bytes', 'sha256')} for k, v in rows.items()}
    request = {'schema': p.REQUEST_SCHEMA, 'source': rows, 'output_root': str(ART / 'projected'),
               'receipt': str(ART / 'projection-receipt.json')}
    request_pin = put(root / 'request.json', request)
    forbidden = {'train_behavior', 'eval_spikes_heldout'}
    class GuardDataset(h5py.Dataset):
        def __getitem__(self, key, *args, **kwargs):
            if self.name.rsplit('/', 1)[-1] in forbidden:
                OBS['forbidden_numeric_reads'] += 1
                raise AssertionError('Excluded source dataset numerically indexed')
            value = super().__getitem__(key, *args, **kwargs)
            OBS['expanded_h5_projection_bytes'] += getattr(value, 'nbytes', 0)
            return value
    class GuardFile(h5py.File):
        def __getitem__(self, name):
            item = super().__getitem__(name)
            return GuardDataset(item.id) if isinstance(item, h5py.Dataset) else item
    proxy = types.SimpleNamespace(File=GuardFile, Dataset=h5py.Dataset, HardLink=h5py.HardLink,
                                  check_dtype=h5py.check_dtype)
    class NumericReadSpy:
        def __getattr__(self, name): return getattr(np, name)
        def asarray(self, *args, **kwargs):
            result = np.asarray(*args, **kwargs)
            OBS['canonical_f8_projection_bytes'] += result.nbytes
            return result
    numeric_spy = NumericReadSpy()
    generated = clone(p, {'SOURCE_PINS': pins, 'CONTENT_PINS': content, 'ORDER_PINS': order,
                          'scientific_modules': lambda: (proxy, numeric_spy)})
    original = {k: copy.deepcopy(getattr(p, k)) for k in ('SOURCE_PINS', 'CONTENT_PINS', 'ORDER_PINS',
                'GEOMETRY', 'SHAPES', 'ROLES', 'EXCLUDED_SOURCE_SHAPES', 'RELATIVE_FILES')}
    f = types.SimpleNamespace(p=p, api=generated, request=request, request_pin=request_pin,
        rows=rows, content=content, identity=identity, order=order, original=original, proxy=proxy, np=numeric_spy)
    SHARED['projection'] = f
    return f


def grading_fixture():
    if 'grading' in SHARED:
        return SHARED['grading']
    g = load('validation_grade', 'runtime/grader/validation_grade.py')
    root = ART / 'grade-inputs'; root.mkdir()
    panel = ref(ROOT / 'runtime/grader/VALID_PANEL.json')
    packet = {'schema': 'smc_restricted_validation_packet_v1', 'dataset': 'mc_maze', 'phase': 'val',
        'units': 'spike_counts_per_20ms_bin', 'geometry': g.GEOMETRY, 'roles': g.PACKET_ROLES,
        'order': g.ORDER, 'projector': g.PROJECTOR_PIN,
        'files': {relative: {'bytes': 1, 'sha256': 'd' * 64,
                 'datasets': {name: {'shape': shape, 'dtype': '|u1', 'content_sha256': g.INPUT_CONTENT[name]}
                              for name, shape in shapes.items()}} for relative, shapes in g.INPUT_SHAPES.items()}}
    packet_pin = put(root / 'PACKET.json', packet)
    methods = {}; predictions = {}
    for role in g.ROLES:
        method = {'schema': 'smc_restricted_validation_method_v1', 'route': g.ROUTE, 'phase': 'val',
            'role': role, 'program': pin(b'generated program'), 'bindings': pin(b'generated bindings'),
            'recipe': g.REFERENCE_RECIPE if role == 'reference' else {'method_id': 'generated-candidate', 'seed': 7},
            'packet_sha256': packet_pin['sha256'], 'AI_attempt': False, 'scientific_improvement': False}
        if role == 'reference': method['author_reference_resource_profile'] = dict(REFERENCE_PROFILE)
        methods[role] = put(root / (role + '-method.json'), method)
        keys = g.RATE_KEYS if role == 'reference' else sorted(g.REQUIRED_KEYS)
        predictions[role] = h5_file(root / (role + '.h5'), {k: g.SHAPES[k] for k in keys}, rates=True)
    f = types.SimpleNamespace(g=g, root=root, panel=panel, packet=packet, packet_pin=packet_pin,
                               methods=methods, predictions=predictions, freezes={})
    SHARED['grading'] = f
    return f


def ensure_freezes(f):
    if not f.freezes:
        for role in f.g.ROLES:
            reserve(f.predictions[role]['bytes'] + 16 * 1024)
            try:
                f.freezes[role] = f.g.freeze_prediction(f.predictions[role]['path'], f.panel,
                    f.packet_pin, f.methods[role], str(ART / (role + '-freeze')), role=role)
            finally: account()
    return f.freezes


class RestrictedValidationControls(unittest.TestCase):
    def setUp(self):
        global ACTIVE
        initialize(); ACTIVE = True; self.addCleanup(self.finish_test)

    @staticmethod
    def finish_test():
        global ACTIVE
        try: account()
        finally: ACTIVE = False

    def test_01_original_authority_refuses_and_generated_projector_preserves_exact_view(self):
        f = projection_fixture()
        with self.assertRaisesRegex(ValueError, 'Original source selection mismatch'):
            f.p.project(f.request_pin['path'], f.request_pin['sha256'])
        OBS['original_authority_refusals'] += 1
        self.assertFalse(Path(f.request['output_root']).exists())
        self.assertFalse(Path(f.request['receipt']).exists())
        for name in ('GEOMETRY', 'SHAPES', 'ROLES', 'EXCLUDED_SOURCE_SHAPES', 'RELATIVE_FILES'):
            self.assertEqual(getattr(f.api, name), getattr(f.p, name))
        for name, value in vars(f.p).items():
            if isinstance(value, types.FunctionType) and name != 'scientific_modules':
                self.assertIs(getattr(f.api, name).__code__, value.__code__)
            elif not isinstance(value, types.FunctionType) and name not in {'SOURCE_PINS','CONTENT_PINS','ORDER_PINS'}:
                self.assertIs(getattr(f.api, name), value)
        reserve(192 * 1024)
        try: result = f.api.project(f.request_pin['path'], f.request_pin['sha256'])
        finally: account()
        packet = json.loads(Path(result['packet']['path']).read_bytes())
        SHARED['projected'] = (result, packet)
        self.assertEqual(set(packet), f.p.expected_packet_fields())
        self.assertEqual(packet['phase'], 'val'); self.assertEqual(packet['geometry']['train_trials'], 1721)
        h5py, np = scientific()
        for role, relative in f.p.RELATIVE_FILES.items():
            with h5py.File(Path(f.request['output_root']) / relative, 'r') as handle:
                self.assertEqual(set(handle), set(f.p.SHAPES[role]))
                for name, shape in f.p.SHAPES[role].items():
                    self.assertEqual(handle[name].shape, shape); self.assertEqual(handle[name].dtype.str, '|u1')
                    self.assertEqual(int(handle[name][0, 0, 0]), 0)  # True observed zero remains zero.
                    self.assertEqual(int(handle[name][1, 0, 0]), 2)
        serialized = json.dumps(packet)
        self.assertNotIn(str(ART / 'projection-inputs'), serialized)
        self.assertNotIn('train_behavior', serialized); self.assertNotIn('eval_spikes_heldout', serialized)
        self.assertEqual(OBS['forbidden_numeric_reads'], 0)
        for key, value in f.original.items(): self.assertEqual(getattr(f.p, key), value)

    def test_02_hidden_sentinel_changes_leave_real_projected_fields_unchanged(self):
        f = projection_fixture(); h5py, np = scientific()
        outputs = ART / 'sentinel-projections'; outputs.mkdir()
        for role in ('train', 'eval'):
            reserve(48 * 1024)
            try:
                with h5py.File(f.rows[role]['path'], 'r+') as handle:
                    for name, shape in f.p.EXCLUDED_SOURCE_SHAPES[role].items():
                        del handle[name]
                        handle.create_dataset(name, shape=shape, dtype='u1', fillvalue=233,
                            chunks=(min(128, shape[0]), shape[1], shape[2]), compression='gzip',
                            compression_opts=9, track_times=False)
            finally: account()
            reserve(96 * 1024)
            try: actual = f.api.project_file(ref(Path(f.rows[role]['path'])), outputs / (role + '.h5'), role, f.proxy, f.np)
            finally: account()
            self.assertEqual(set(actual['datasets']), set(f.p.SHAPES[role]))
            for name, item in actual['datasets'].items():
                self.assertEqual(item['content_sha256'], f.content[name])
                self.assertEqual(item['shape'], list(f.p.SHAPES[role][name])); self.assertEqual(item['dtype'], '|u1')
        self.assertEqual(OBS['forbidden_numeric_reads'], 0)

    def test_03_phase_lengths_hidden_fields_overlap_and_order_are_rejected(self):
        f = projection_fixture(); h5py, np = scientific()
        for label in ('phase_length', 'overlap', 'trial_order', 'neuron_overlap', 'neuron_order'):
            bad = copy.deepcopy(f.identity)
            if label == 'phase_length': bad['ordered_trials']['train'].pop()
            elif label == 'overlap': bad['ordered_trials']['val'][0] = bad['ordered_trials']['train'][0]
            elif label == 'trial_order': bad['ordered_trials']['val'][:2] = reversed(bad['ordered_trials']['val'][:2])
            elif label == 'neuron_overlap': bad['neurons']['heldout_spikes'][0] = bad['neurons']['spikes'][0]
            else: bad['neurons']['spikes'][:2] = reversed(bad['neurons']['spikes'][:2])
            with self.subTest(label=label), self.assertRaises(ValueError): f.api.validate_identity(bad)
        bad_path = ART / 'bad-fields.h5'
        h5_file(bad_path, {**f.p.SHAPES['eval'], **f.p.EXCLUDED_SOURCE_SHAPES['eval']},
                excluded=f.p.EXCLUDED_SOURCE_SHAPES['eval'])
        for forbidden in ('eval_spikes_heldin_forward', 'eval_behavior'):
            reserve(16 * 1024)
            try:
                with h5py.File(bad_path, 'r+') as handle:
                    handle.create_dataset(forbidden, shape=(574, 10, 1), dtype='u1', fillvalue=77)
                with h5py.File(bad_path, 'r') as handle, self.assertRaisesRegex(ValueError, 'allowlist'):
                    f.p.validate_h5(handle, 'eval', raw=True, h5py=h5py)
                with h5py.File(bad_path, 'r+') as handle: del handle[forbidden]
            finally: account()
        reserve(16 * 1024)
        try:
            with h5py.File(bad_path,'r+') as handle:
                handle['eval_spikes_heldin'][0,0,0]=2
                handle['eval_spikes_heldin'][1,0,0]=0
            with f.proxy.File(bad_path,'r') as handle,self.assertRaisesRegex(ValueError,'content/order'):
                f.api.scan_dataset(handle['eval_spikes_heldin'],f.content['eval_spikes_heldin'],f.np)
        finally:account()
        reserve(16 * 1024)
        try:
            with h5py.File(bad_path, 'r+') as handle:
                del handle['eval_spikes_heldin']
                handle.create_dataset('eval_spikes_heldin', shape=(573, 35, 137), dtype='u1', fillvalue=0)
            with h5py.File(bad_path, 'r') as handle, self.assertRaisesRegex(ValueError, 'shape/phase'):
                f.p.validate_h5(handle, 'eval', raw=True, h5py=h5py)
        finally: account()
        with self.assertRaisesRegex(ValueError, 'overlaps input parent'):
            f.p.fresh_outputs(ART / 'projection-inputs/leaked', ART / 'leaked-receipt.json',
                              [Path(f.rows['train']['path'])])
        self.assertFalse((ART / 'projection-inputs/leaked').exists())

    def test_04_packet_phase_and_extra_target_paths_refuse_before_dataset_scan(self):
        f = projection_fixture()
        if 'projected' not in SHARED:
            reserve(192 * 1024)
            try: result = f.api.project(f.request_pin['path'], f.request_pin['sha256'])
            finally: account()
            SHARED['projected'] = (result, json.loads(Path(result['packet']['path']).read_bytes()))
        selected, original = SHARED['projected']
        manifest = Path(selected['packet']['path'])
        for key, value in [('phase', 'test'), ('geometry', {**original['geometry'], 'train_trials': 2295}),
                           ('order', {**original['order'], 'tensor_trial_indices_sha256': '0' * 64})]:
            bad = copy.deepcopy(original); bad[key] = value
            os.chmod(manifest, 0o600); row = put(manifest, bad)
            before = OBS['expanded_h5_projection_bytes']
            with self.assertRaises(ValueError): f.api.inspect_packet(row['path'], row['sha256'])
            self.assertEqual(OBS['expanded_h5_projection_bytes'], before)
        os.chmod(manifest, 0o600); restored = put(manifest, original)
        target = put(manifest.parent / 'target.h5', b'generated forbidden target')
        with self.assertRaisesRegex(ValueError, 'extra path'):
            f.api.inspect_packet(restored['path'], restored['sha256'])
        Path(target['path']).unlink()

    def test_05_exact_reference_recipe_and_adapter_argv_never_launch_model(self):
        core = load('validation_reference', 'runtime/validation_reference.py')
        adapter = load('validation_adapter', 'runtime/validation_adapter.py')
        selected = core.recipe()
        self.assertEqual(selected, {'arm': 'noncausal', 'seed': 20261118, 'particles': 192, 'repeats': 32,
            'smooth': False, 'device': 'cpu', 'training': False, 'checkpoint_search': False,
            'access_condition': core.ACCESS})
        captured = []; fake_sys = types.SimpleNamespace(argv=['prior'], path=['prior-path'])
        report = {'schema': 'smc_restricted_validation_native_attempt_v1', 'mode': 'predict',
            'arm': 'noncausal', 'seed': 20261118, 'particles': 192, 'source_requested_repeats': 32,
            'smooth': False, 'phase': 'val', 'packet_sha256': 'a' * 64, 'restricted_eval_shape': [574,35,137],
            'train_rates_role': 'canonical_metric_decoder_inputs_not_restricted_calibration',
            'checkpoint_training_cohort': 'unknown', 'resource_adequacy': False, 'complete_source_prediction': True,
            'selected_cpu_seconds': REFERENCE_PROFILE['cpu_seconds']}
        def run_path(path, run_name): captured.append((path, run_name, list(fake_sys.argv)))
        api = clone(adapter, {'sys': fake_sys, 'runpy': types.SimpleNamespace(run_path=run_path),
                              'read': lambda path: copy.deepcopy(report)})
        actual = api.invoke_author(ART / 'helpers', selected, ART / 'materials', ART / 'out', ART / 'scratch', 'a' * 64, REFERENCE_PROFILE)
        self.assertEqual(actual, report); self.assertEqual(len(captured), 1)
        argv = captured[0][2]
        self.assertEqual(captured[0][1], '__main__'); self.assertEqual(fake_sys.argv, ['prior'])
        self.assertEqual(fake_sys.path, ['prior-path'])
        for flag, value in [('--inputs', str(ART / 'materials/inputs')), ('--arm', 'noncausal'),
                            ('--mode', 'predict'), ('--packet-sha256', 'a' * 64)]:
            self.assertEqual(argv[argv.index(flag) + 1], value)
        self.assertEqual(argv[argv.index('--cpu-seconds')+1], str(REFERENCE_PROFILE['cpu_seconds']))
        self.assertEqual(adapter.validate_author_report(actual, selected, 'a' * 64, REFERENCE_PROFILE), report)
        self.assertEqual(core.validate_reference_profile(REFERENCE_PROFILE), REFERENCE_PROFILE)
        for bad in (None, {k:v for k,v in REFERENCE_PROFILE.items() if k!='cpu_seconds'},
                    *[{**REFERENCE_PROFILE,'cpu_seconds':v} for v in (True,0,64801,60000.0)],
                    {**REFERENCE_PROFILE,'threads':1}):
            with self.assertRaises(ValueError): core.validate_reference_profile(bad)
        for key, value in [('phase','test'), ('seed',1), ('particles',1), ('source_requested_repeats',1),
                            ('restricted_eval_shape',[574,45,137]), ('resource_adequacy',True)]:
            bad = copy.deepcopy(report); bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                adapter.validate_author_report(bad, selected, 'a' * 64, REFERENCE_PROFILE)

    def test_06_real_builder_selects_only_exact_readonly_leaves_and_refuses_raw_parent_mounts(self):
        # Source/material authority is generated; every actual mount operand,
        # including the retained custody worker, is really reauthenticated.
        core = load('validation_reference', 'runtime/validation_reference.py')
        root = ART / 'builder'; root.mkdir(); component = root / 'component'; component.mkdir()
        materials_root = root / 'materials'; materials_root.mkdir(); prepared_root = root / 'prepared'; prepared_root.mkdir()
        output = root / 'output'; output.mkdir()
        manifest = {'files': {}}
        for name in sorted(core.SOURCE_FILES):
            row=put(component/name, ('generated source '+name).encode())
            manifest['files'][name]={k:row[k] for k in ('bytes','sha256')}
        source_row=put(component/'SOURCE.json', {'generated_authority':True,'files':manifest['files']})
        p={k:source_row[k] for k in ('bytes','sha256')}
        put(root/'projection/project_validation.py', (ROOT/'projection/project_validation.py').read_bytes())
        material={'packet':None,'files':{}}
        for name in ('inputs/PACKET.json','inputs/mc_maze/val/train_input_20ms.h5',
                     'inputs/mc_maze/val/eval_input_20ms.h5','official_source/generated.py',
                     'official_source/checkpoints/generated.pt'):
            row=put(materials_root/name, ('generated operand '+name).encode())
            material['files'][name]={k:row[k] for k in ('bytes','sha256')}
        material['packet']=material['files']['inputs/PACKET.json']
        material_row = put(materials_root / 'MATERIALS.json', material)
        binding = {'schema': 'smc_restricted_validation_bindings_v1', 'helpers': {},
                   'packet': material['packet'], 'materials': {k: material_row[k] for k in ('bytes','sha256')}}
        bindings_row = put(prepared_root / 'BINDINGS.json', binding)
        plan = core.method_plan(manifest['files']['validation_adapter.py'],
            {k: bindings_row[k] for k in ('bytes','sha256')}, material['packet']['sha256'],REFERENCE_PROFILE)
        plan_row = put(prepared_root / 'declaration.json', plan)
        job = {'schema':'smc_restricted_validation_execution_job_v1','route':core.ROUTE,'outcome':core.OUTCOME,
            'condition':core.PHASE,'phase_id':core.PHASE,'access_condition':core.ACCESS,'source':p,
            'resource_profile':REFERENCE_PROFILE,'submission_keys':['offline'],
            'program_sha256':manifest['files']['validation_adapter.py']['sha256'],
            'declaration_sha256':plan_row['sha256'],'method_freeze_sha256':plan_row['sha256'],
            'bindings':{k:bindings_row[k] for k in ('bytes','sha256')},'max_file_bytes':core.FILE_CAP,
            'packet_sha256':material['packet']['sha256']}
        execution = put(prepared_root / 'execution.json', job)
        prepared = put(prepared_root / 'PREPARED.json', {'schema':'smc_restricted_validation_prepared_v1',
            'component_source':source_row,'materials':material_row,
            'bindings':bindings_row,'declaration':plan_row,'execution':execution,
            'runtime_qualified_by_preparation':False,'resource_adequacy':False})
        owner = {'schema':'smc_aggregate_phase_request_v1','phase_id':core.PHASE,'role':'B','source':p,
            'resources':{'cpu_seconds':REFERENCE_PROFILE['cpu_seconds'],'producer_seconds':REFERENCE_PROFILE['wall_seconds'],
                         'memory_bytes':REFERENCE_PROFILE['memory_bytes'],'cpu_nanos':REFERENCE_PROFILE['threads']*1000000000,'pids':128}}
        owner_row = put(root / 'request.json', core.encode(owner))
        retained = ref(ROOT/'controls/fixtures/retained_worker.py')
        self.assertEqual({k:retained[k] for k in ('bytes','sha256')},core.RETAINED_WORKER_PIN)
        api = clone(core, {'source_identity':lambda *a, **k:(p,manifest),
                           'inspect_materials':lambda row:copy.deepcopy(material)})
        invocation = api.build_invocation(prepared, owner_row, retained, str(output))
        self.assertEqual(invocation['argv'], ['/usr/local/bin/python3.11','-I','-S','-B','/runner/worker.py'])
        self.assertIs(invocation['runtime_qualified'],False); self.assertIs(invocation['resource_adequacy'],False)
        self.assertEqual(invocation['working_dir'],'/work');self.assertTrue(invocation['readonly_rootfs'])
        self.assertEqual(invocation['ephemeral_write_paths'],['/work','/tmp'])
        self.assertIs(invocation['additional_bind_mounts_allowed'],False)
        selected = invocation['readonly_mounts']; self.assertTrue(all(x['readonly'] is True for x in selected))
        self.assertEqual(core.validate_worker_mounts(selected, selected), selected)
        for kind in ('raw_source', 'parent_guest', 'extra_parent', 'writable', 'duplicate'):
            bad = copy.deepcopy(selected)
            if kind == 'raw_source': bad[0]['source'] = str(root / 'raw-eval-with-heldout.h5')
            elif kind == 'parent_guest': bad[0]['destination'] = '/materials'
            elif kind == 'extra_parent': bad.append({**bad[0],'destination':'/materials'})
            elif kind == 'writable': bad[0]['readonly'] = False
            else: bad.append(copy.deepcopy(bad[0]))
            with self.subTest(kind=kind), self.assertRaises(ValueError): core.validate_worker_mounts(bad, selected)
        for destination in ('/','/work','/work/source.py','/tmp','/output'):
            bad=copy.deepcopy(selected);bad[0]['destination']=destination
            with self.subTest(destination=destination),self.assertRaises(ValueError):
                core.validate_mount_operands(bad,output)
        # Exercise the real builder, not only a copied selected-mount comparison.
        for relative in ('official_source/generated.py','official_source/checkpoints/generated.pt',
                         'inputs/mc_maze/val/eval_input_20ms.h5'):
            leaf=materials_root/relative;backup=leaf.with_name(leaf.name+'.saved')
            leaf.rename(backup);leaf.mkdir()
            try:
                with self.subTest(directory=relative),self.assertRaises(ValueError):
                    api.build_invocation(prepared,owner_row,retained,str(output))
            finally:leaf.rmdir();backup.rename(leaf)
        leaf=component/'helpers/author_predict_val.py';backup=leaf.with_name(leaf.name+'.saved')
        leaf.rename(backup);leaf.symlink_to(materials_root)
        try:
            with self.assertRaises(ValueError):api.build_invocation(prepared,owner_row,retained,str(output))
        finally:leaf.unlink();backup.rename(leaf)
        alias=root/'hardlink';os.link(leaf,alias)
        try:
            with self.assertRaises(ValueError):api.build_invocation(prepared,owner_row,retained,str(output))
        finally:alias.unlink()
        for resources in ({**owner['resources'],'cpu_seconds':59999},
                          {**owner['resources'],'cpu_seconds':True}):
            row=put(root/'request.json',core.encode({**owner,'resources':resources}))
            with self.assertRaises(ValueError):api.build_invocation(prepared,row,retained,str(output))
        bad = copy.deepcopy(plan); bad['recipe']['seed'] += 1
        with self.assertRaises(ValueError):
            core.validate_job(bad, job, manifest['files']['validation_adapter.py'],job['bindings'])

    def test_07_both_full_shape_freezes_precede_target_and_report_all_four_deltas(self):
        f = grading_fixture(); g = f.g; freezes = ensure_freezes(f)
        target = put(f.root / 'generated-target.bin', b'generated numerical target boundary')
        evaluator = ref(ROOT/'controls/fixtures/evaluation.py')
        output = ART / 'paired-host/report/validation'; output.parent.mkdir(parents=True); events = []
        def load_evaluator(path):
            self.assertEqual(str(path), evaluator['path'])
            self.assertTrue((output / 'BOTH_SNAPSHOTS.json').is_file())
            self.assertFalse(events); events.append('evaluator_after_both_snapshots')
            def evaluate(target_path, prediction_path):
                self.assertEqual(events[1], 'target_after_both_snapshots')
                role = Path(prediction_path).stem; OBS['evaluator_calls'] += 1
                values = {k:(index + (1 if role=='candidate' else 0))/8 for index,k in enumerate(g.METRICS)}
                return [{g.DATASET + '_split':values}]
            return types.SimpleNamespace(evaluate=evaluate)
        def target_loader(path):
            self.assertTrue((output / 'BOTH_SNAPSHOTS.json').is_file())
            for role in g.ROLES:
                self.assertTrue((output / (role + '.h5')).is_file())
                self.assertEqual(g.content_pin(output/(role+'.h5')),
                    {k:json.loads(Path(freezes[role]['path']).read_bytes())['snapshot'][k] for k in ('bytes','sha256')})
            events.append('target_after_both_snapshots'); OBS['target_loader_calls'] += 1
            return target
        api = clone(g, {'load_original_evaluator':load_evaluator,'authenticate_target':target_loader})
        reserve(sum(x['bytes'] for x in f.predictions.values())+32*1024)
        try: selected = api.score_pair(freezes, target['path'], evaluator['path'], str(output))
        finally: account()
        report = json.loads(Path(selected['path']).read_bytes())
        self.assertEqual(report['phase'],'val'); self.assertEqual(set(report['metrics']),set(g.ROLES))
        self.assertEqual(report['candidate_minus_reference'],{k:.125 for k in g.METRICS})
        for role in g.ROLES: self.assertEqual(set(report['metrics'][role]),set(g.METRICS))
        for key in ('inference_execution_qualified','pipeline_execution_qualified','physical_owner_qualified',
                    'resource_adequacy','scientific_improvement','SOTA','packet_payloads_reopened_by_grader'):
            self.assertIs(report[key],False)
        self.assertEqual(events,['evaluator_after_both_snapshots','target_after_both_snapshots'])
        self.assertIsNone(report['scientific_equivalence'])
        host=load('validation_grade_host','runtime/bounded-grade/validation_grade_host.py')
        report_child={'schema':'smc_restricted_validation_bounded_grade_request_v1',
            'source':ref(ROOT/'runtime/grader/SOURCE.json'),'freezes':freezes,'target':target,
            'evaluator':evaluator,'output_root':str(output)}
        # Structural host-report join under the same explicit numerical target
        # boundary. This is NOT original-target admission by validate_child_request.
        self.assertEqual(host.validate_report(report,report_child,'a'*64),report)
        for key,value in [('phase','test'),('dataset','mc_maze'),
                          ('metrics',{'causal':report['metrics']['reference'],'noncausal':report['metrics']['candidate']}),
                          ('candidate_minus_reference',{k:99 for k in g.METRICS})]:
            bad=copy.deepcopy(report);bad[key]=value
            with self.subTest(report_field=key),self.assertRaises(ValueError):
                host.validate_report(bad,report_child,'a'*64)
        bad_evaluator=put(f.root/'wrong-evaluator.py',b'# generated wrong evaluator\n')
        with self.assertRaisesRegex(ValueError,'unchanged canonical original'):
            g.load_original_evaluator(bad_evaluator['path'])
        with self.assertRaisesRegex(ValueError,'exact original VALID target'):
            g.authenticate_target(target['path'])
        for bad in ([{g.DATASET+'_split':{'co-bps':1}}],
                    [{g.DATASET+'_split':{k:math.nan for k in g.METRICS}}],
                    [{g.DATASET+'_split':{k:True for k in g.METRICS}}]):
            with self.assertRaises(ValueError):g.extract_metrics(bad)

    def test_08_bounded_host_typed_pair_real_leaf_actor_and_one_budget_closure(self):
        f=grading_fixture();freezes=ensure_freezes(f)
        host=load('validation_grade_host','runtime/bounded-grade/validation_grade_host.py')
        source=ref(ROOT/'runtime/grader/SOURCE.json')
        target=put(ART/'host-generated-target',b'generated target body, never original authority')
        evaluator=ref(ROOT/'controls/fixtures/evaluation.py')
        host_root=ART/'bounded-host';report_root=host_root/'report';report_root.mkdir(parents=True)
        child={'schema':'smc_restricted_validation_bounded_grade_request_v1','source':source,
               'freezes':freezes,'target':target,'evaluator':evaluator,'output_root':str(report_root/'validation')}
        with self.assertRaisesRegex(ValueError,'fixed VALID target'):
            host.validate_child_request(child,source,report_root)
        # Declared target metadata is an external operator/numerical contract;
        # its generated body does NOT match the original target and is not read.
        child['target']={**target,'sha256':host.TARGET_SHA256}
        self.assertEqual(host.validate_child_request(child,source,report_root),child)
        child_row=put(ART/'host-inputs/request.json',child)
        manifest=json.loads(Path(source['path']).read_bytes())
        records,leaves=host.admit_freeze_metadata(child,manifest)
        self.assertEqual(set(records),{'reference','candidate'})
        base={'generated.example/runtime':'synthetic'}
        labels={**base,**{k:'generated' for k in host.label_policy().OMITTED_DESKTOP_KEYS}}
        provenance={'image':{'Id':host.IMAGE_ID,'Architecture':'arm64',
            'Config':{'Labels':labels,'Env':['PATH=/usr/local/bin:/usr/bin:/bin']}},'container_base_labels':base}
        request={'output_root':str(host_root),'adapter_source':source,'child_request':child_row,
                 'socket':'unix://'+str(ART/'unmounted-docker.sock'),'token':'a'*32}
        actor,private=host.actor_for(request,child,provenance)
        self.assertLessEqual(len(actor['readonly_mounts']),16)
        self.assertTrue(all(Path(m['source']).is_file() for m in actor['readonly_mounts']))
        self.assertFalse(any(m['source']==str(ART) for m in actor['readonly_mounts']))
        built=host.build_create(actor,private);argv=built['argv']
        self.assertEqual((host.GRADE_MEMORY,host.CPU_SOFT,host.CPU_HARD,host.WORK_SECONDS,host.CLEANUP_SECONDS),
                         (2147483648,600,605,720,60))
        for flag,value in [('--memory','2147483648'),('--memory-swap','2147483648'),('--cpus','1'),('--network','none')]:
            self.assertEqual(argv[argv.index(flag)+1],value)
        self.assertIn('cpu=600:605',argv)
        bad=copy.deepcopy(child);bad['schema']='smc_historical_reference_grade_request_v1'
        with self.assertRaises(ValueError):host.validate_child_request(bad,source,report_root)
        bad=copy.deepcopy(child);bad['freezes']={'causal':freezes['reference'],'noncausal':freezes['candidate']}
        with self.assertRaises(ValueError):host.validate_child_request(bad,source,report_root)
        bad=copy.deepcopy(child);bad['target']['path']=str(ART)
        with self.assertRaises(ValueError):host.actor_for(request,bad,provenance)
        alias=ART/'aliased-host-target';os.link(Path(target['path']),alias)
        try:
            with self.assertRaises(ValueError):host.actor_for(request,child,provenance)
        finally:alias.unlink()
        call={'pid':123,'returncode':0,'errors':[],
            'cleanup':{'cleanup_complete':True,'reaped':True,'group_absence_observed':True,'error':None,'pid':123,'returncode':0},
            'capture':{'all_eof_observed':True,'storage_truncated':False,'read_ceiling_exhausted':False,
                       'closed_without_eof':False,'stream_close_errors':[]}}
        self.assertTrue(host.completion(None,{'container_absent':True},[call])['success'])
        self.assertEqual(host.completion(None,{'container_absent':False},[call])['status'],'closure_unknown')
        bad=copy.deepcopy(call);bad['capture']['all_eof_observed']=False
        self.assertEqual(host.completion(None,{'container_absent':True},[bad])['status'],'closure_unknown')
        self.assertEqual(host.completion({'error':'generated score failure'},{'container_absent':True},[call])['status'],'failed')

    def test_09_bounded_child_sets_one_cpu_thread_limit_before_one_paired_delegate(self):
        f=grading_fixture();freezes=ensure_freezes(f)
        child=load('validation_grade_child','runtime/grader/validation_grade_child.py')
        source=ref(ROOT/'runtime/grader/SOURCE.json')
        admitted=child.load_grader(source)
        self.assertEqual(admitted.source_identity(),child.GRADE_PIN)
        target=put(ART/'child-generated-target',b'generated target body, not original identity')
        output=ART/'child-host/report/validation'
        request={'schema':'smc_restricted_validation_bounded_grade_request_v1','source':source,
            'freezes':freezes,'target':{**target,'sha256':child.TARGET_SHA256},
            'evaluator':ref(ROOT/'controls/fixtures/evaluation.py'),'output_root':str(output)}
        request_row=put(ART/'child-inputs/request.json',request)
        events=[]
        resource=types.SimpleNamespace(RLIMIT_CPU=child.resource.RLIMIT_CPU,RLIMIT_CORE=child.resource.RLIMIT_CORE,
            setrlimit=lambda kind,value:events.append(('limit',kind,value)))
        fake_os=types.SimpleNamespace(**{**vars(os),'environ':{}})
        def guarded_body(path):
            self.assertNotIn(str(path),[request['target']['path'],request['evaluator']['path']])
            return child.body(path)
        def load_grader(selected):
            self.assertEqual(selected,source)
            self.assertEqual(events[:2],[('limit',child.resource.RLIMIT_CPU,(600,605)),
                                       ('limit',child.resource.RLIMIT_CORE,(0,0))])
            self.assertEqual(fake_os.environ,{k:'1' for k in child.THREAD_ENV})
            events.append(('grader_after_limits',))
            def score_pair(selected_freezes,target_path,evaluator_path,output_root):
                self.assertEqual(selected_freezes,freezes)
                self.assertEqual((target_path,evaluator_path,output_root),
                                 (request['target']['path'],request['evaluator']['path'],request['output_root']))
                events.append(('one_pair',))
                return put(Path(output_root)/'REPORT.json',{'target':request['target'],'freezes':freezes,
                          'source':child.GRADE_PIN,'evaluator':child.EVALUATOR_PIN})
            return types.SimpleNamespace(score_pair=score_pair)
        api=clone(child,{'resource':resource,'os':fake_os,'body':guarded_body,'load_grader':load_grader})
        result=api.run(request_row['path'],request_row['sha256'])
        self.assertEqual([x[0] for x in events],['limit','limit','grader_after_limits','one_pair'])
        self.assertIs(result['inference_execution_qualified'],False)
        self.assertIs(result['physical_owner_qualified'],False)
        wrong=copy.deepcopy(request);wrong['target']=target
        with self.assertRaisesRegex(ValueError,'exact original VALID target'):child.validate_request(wrong)

    def test_10_phase_target_fields_and_second_frozen_artifact_drift_block_target_access(self):
        f = grading_fixture(); g = f.g; freezes = ensure_freezes(f)
        source = json.loads(Path(freezes['reference']['path']).read_bytes())
        bad = copy.deepcopy(source); bad['phase'] = 'test'
        bad_row = put(ART / 'wrong-phase-FREEZE.json', bad)
        with self.assertRaisesRegex(ValueError,'exact frozen VALID'):g.validate_freeze(bad_row)
        method=json.loads(Path(f.methods['reference']['path']).read_bytes())
        for label,value in [('missing',None),('bool',True),('zero',0),('range',64801)]:
            invalid=copy.deepcopy(method)
            if label=='missing':del invalid['author_reference_resource_profile']
            else:invalid['author_reference_resource_profile']['cpu_seconds']=value
            row=put(ART/('bad-profile-'+label+'.json'),invalid)
            with self.assertRaises(ValueError):g.validate_method(row,f.packet_pin,'reference')
        cli_request=put(ART/'blocked-grade-request.json',{'schema':'smc_restricted_validation_grade_request_v1',
            'source':g.source_identity(),'freezes':freezes,'target':str(ART/'never-read-cli-target'),
            'evaluator':str(ART/'never-read-cli-evaluator'),'output_root':str(ART/'never-created-cli-output')})
        cli_calls=[]
        def forbidden_cli(*a,**k):cli_calls.append('unbounded grade');raise AssertionError('Unbounded CLI')
        cli=clone(g,{'score_pair':forbidden_cli,'authenticate_target':forbidden_cli,'load_original_evaluator':forbidden_cli})
        with self.assertRaisesRegex(ValueError,'VALID grading CLI unavailable'):
            cli.main(['--request',cli_request['path'],'--sha256',cli_request['sha256']])
        self.assertEqual(cli_calls,[]);self.assertFalse((ART/'never-created-cli-output').exists())
        packet = copy.deepcopy(f.packet); packet['target'] = {'path':'/forbidden'}
        packet_row = put(ART / 'target-bearing-PACKET.json', packet)
        with self.assertRaisesRegex(ValueError,'closed restricted packet'):g.validate_packet_metadata(packet_row)
        h5py,np = scientific(); bad_pred = ART/'bad-prediction.h5'
        reserve(16*1024)
        try:
            with h5py.File(bad_pred,'w') as handle:
                group=handle.create_group(g.DATASET)
                for name in sorted(g.REQUIRED_KEYS):
                    shape=[573,35,137] if name=='eval_rates_heldin' else g.SHAPES[name]
                    group.create_dataset(name,shape=shape,dtype='<f4',fillvalue=1)
            with self.assertRaisesRegex(ValueError,'full VALID prediction array'):
                g.validate_prediction(bad_pred,'candidate')
        finally:account()
        second=Path(freezes['candidate']['path']).parent/'prediction.h5'
        reserve(second.stat().st_size+1)
        os.chmod(second,0o600)
        with second.open('ab') as stream:stream.write(b'X')
        os.chmod(second,0o400);account()
        calls=[]
        def forbidden(*args):calls.append('forbidden target/evaluator');raise AssertionError('Target crossed early')
        api=clone(g,{'load_original_evaluator':forbidden,'authenticate_target':forbidden})
        with self.assertRaisesRegex(ValueError,'frozen prediction identity'):
            api.score_pair(freezes,str(ART/'never-read-target'),str(ART/'never-read-evaluator'),str(ART/'must-not-score'))
        self.assertEqual(calls,[]);self.assertFalse((ART/'must-not-score').exists())


def main():
    initialize(); result=unittest.main(exit=False).result; account()
    receipt={'schema':'smc-restricted-validation-source-controls/v1','testsRun':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
        'successful':result.wasSuccessful(),'source_identities':SOURCE_IDENTITIES,'observations':OBS,
        'scientific_test_versions':{'numpy':importlib.metadata.version('numpy'),'h5py':importlib.metadata.version('h5py')},
        'original_data_source_admission_qualified':False,'projector_positive_authority':'isolated_generated_pins_only',
        'grader_packet_fixture':'metadata declares original identities; physical packet delivery not authenticated',
        'native_or_inference_or_scientific_result_qualified':False,
        'expanded_generated_read_work_upper_bytes':EXPANDED_BOUND,
        'fixture_write_bytes_before_receipt':WRITTEN,'receipt_bytes':0,'cumulative_generated_fixture_bytes':0,
        'includes_partial_rewritten_and_deleted_serialized_fixture_versions':True,'fixture_limit_bytes':FIXTURE_LIMIT}
    for _ in range(8):
        raw=encoded(receipt)
        if receipt['receipt_bytes']==len(raw):break
        receipt['receipt_bytes']=len(raw);receipt['cumulative_generated_fixture_bytes']=WRITTEN+len(raw)
    put(ART/'CONTROL_RESULT.json',receipt);print(json.dumps(receipt,sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
