"""Generated VALID owner controls; no native or scientific qualification."""
import ast
import copy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import sys
import types
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[4]
ART = None
ACTIVE = False
CTX = None
COUNTERS = {'source_read_bytes': 0, 'generated_read_bytes': 0,
            'generated_metadata_bytes': 0, 'physical_fixture_bytes': 0,
            'derived_source_work_bytes': 0}
SOURCE_IDENTITIES = {}
OBS = {}
PROFILE = {'cpu_seconds': 60000, 'wall_seconds': 10800,
           'memory_bytes': 8589934592, 'threads': 6}
PHASE = 'validation_reference'
OUTCOME = 'restricted_validation_reference'


def audit(event, args):
    if not ACTIVE:
        return
    if event in {'subprocess.Popen', 'os.fork', 'os.forkpty', 'os.exec', 'os.posix_spawn',
                 'os.system', 'os.kill', 'os.killpg', 'resource.setrlimit',
                 'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
        raise AssertionError('Actual native/network operation forbidden: ' + event)
    if event == 'import' and args[0].split('.')[0] in {'numpy', 'h5py', 'torch', 'jax', 'tensorflow', 'pyro'}:
        raise AssertionError('No scientific/model imports in metadata ownership controls')


sys.addaudithook(audit)


def charge(key, amount):
    assert type(amount) is int and amount >= 0
    COUNTERS[key] = COUNTERS.get(key, 0) + amount


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def source(path, expected=None):
    raw = Path(path).read_bytes()
    charge('source_read_bytes', len(raw))
    if expected is not None:
        assert pin(raw) == expected, str(path)
    SOURCE_IDENTITIES[str(Path(path).relative_to(REPO))] = pin(raw)
    return raw


def put(path, value):
    raw = value if isinstance(value, bytes) else encoded(value)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    charge('physical_fixture_bytes', len(raw))
    return {'path': str(path), **pin(raw)}


def descriptor(path):
    raw = Path(path).read_bytes()
    charge('generated_read_bytes', len(raw))
    return {'path': str(path), **pin(raw)}


def module(name, raw, filename, *, bindings=None, imports=True):
    ns = {'__name__': name, '__file__': str(filename)}
    if bindings:
        ns.update(bindings)
    tree = ast.parse(raw, str(filename))
    if not imports:
        tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
    exec(compile(tree, str(filename), 'exec'), ns)
    return types.SimpleNamespace(**ns)


def functions(raw, names, namespace, filename):
    tree = ast.parse(raw, filename)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, 'exec'), namespace)
    return namespace


def method(raw, cls, name, namespace, filename):
    classes = [n for n in ast.walk(ast.parse(raw, filename))
               if isinstance(n, ast.ClassDef) and n.name == cls]
    assert len(classes) == 1
    nodes = [n for n in classes[0].body if isinstance(n, ast.FunctionDef) and n.name == name]
    assert len(nodes) == 1
    # The exact method node/body is compiled unchanged, with declared outer boundaries.
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, 'exec'), namespace)
    return namespace[name]


def clone(original, changes):
    ns = dict(vars(original))
    original_globals = next(v.__globals__ for v in ns.values() if isinstance(v, types.FunctionType))
    for name, value in tuple(ns.items()):
        if isinstance(value, types.FunctionType) and value.__globals__ is original_globals:
            new = types.FunctionType(value.__code__, ns, value.__name__, value.__defaults__, value.__closure__)
            new.__kwdefaults__ = value.__kwdefaults__
            ns[name] = new
    ns.update(changes)
    return types.SimpleNamespace(**ns)


def context():
    global CTX
    if CTX is not None:
        return CTX
    overlay_raw = source(ROOT / 'validation_overlay.py')
    overlay = module('_control_overlay', overlay_raw, ROOT / 'validation_overlay.py')
    owner_root = REPO / overlay.OWNER_REL
    manifest = json.loads(source(owner_root / 'SOURCE.json', overlay.OWNER_SOURCE))
    originals = {name: source(owner_root / name, expected)
                 for name, expected in manifest['files'].items()}
    legacy_raw = source(ROOT / 'validation_legacy.py')
    derived, changes = overlay.derive_owner_sources(originals, manifest, legacy_raw)
    charge('derived_source_work_bytes', sum(map(len, derived.values())))
    common = module('_control_common', derived['common.py'], ART / 'derived-common.py')
    assert common.CONDITIONS == (PHASE,)
    core_raw = source(ROOT / 'validation_core.py')
    core = module('_control_owned_core', core_raw, ROOT / 'validation_core.py')
    old_root = ROOT.parent / 'restricted-validation-v1' / 'runtime'
    old_raw = source(old_root / 'validation_reference.py', core.VALIDATION_CORE_PIN)
    old = module('_control_predecessor', old_raw, old_root / 'validation_reference.py')
    episode_raw = source(ROOT / 'validation_episode.py')
    engine_raw = source(ROOT / 'transport/engine.py')
    engine_ns = functions(engine_raw, {'need', 'descriptor', 'path'},
                          {'Path': Path, 're': re}, 'selected-engine-functions.py')
    contract_raw = source(ROOT / 'transport/contract.py')
    contract = module('_control_contract', contract_raw, ROOT / 'transport/contract.py',
        bindings={**engine_ns, 'math': math, 'PurePosixPath': PurePosixPath, 're': re}, imports=False)
    provider_raw = source(ROOT / 'transport/provider.py')
    helper = module('_control_proofs', source(HERE / 'proof_fixtures.py'), HERE / 'proof_fixtures.py')
    CTX = types.SimpleNamespace(overlay=overlay, derived=derived, common=common, core=core,
        old=old, old_root=old_root, episode_raw=episode_raw, contract=contract,
        provider_raw=provider_raw, proofs=helper, changes=changes)
    return CTX


def build_material_fixture(c):
    root = ART / 'mount-fixture'
    component, material = root / 'component/runtime', root / 'materials'
    program = put(root / 'protocol' / PHASE / 'program.py', b'# generated program, never executed\n')
    manifest = {'files': {'validation_adapter.py': {k: program[k] for k in ('bytes', 'sha256')}}}
    for name in {'validation_worker.py', 'validation_reference.py',
                 'helpers/validation_author_manifest.json'} | {'helpers/' + n for n in c.old.HELPERS}:
        row = put(component / name, ('generated source leaf ' + name + '\n').encode())
        manifest['files'][name] = {k: row[k] for k in ('bytes', 'sha256')}
    projection = ROOT.parent / 'restricted-validation-v1/projection/project_validation.py'
    put(component.parent / 'projection/project_validation.py', source(projection, c.old.PROJECTOR_PIN))
    author = []
    files = {}
    for name in ('generated_model.py', 'generated_checkpoint.pt'):
        row = put(material / 'official_source' / name, ('generated authority fixture ' + name).encode())
        row_pin = {k: row[k] for k in ('bytes', 'sha256')}
        author.append({'path': name, **row_pin})
        files['official_source/' + name] = row_pin
    for name in ('inputs/PACKET.json', 'inputs/mc_maze/val/train_input_20ms.h5',
                 'inputs/mc_maze/val/eval_input_20ms.h5'):
        row = put(material / name, ('generated metadata-only material ' + name).encode())
        files[name] = {k: row[k] for k in ('bytes', 'sha256')}
    materials = {'schema': 'smc_restricted_validation_materials_v1', 'route': c.old.ROUTE,
        'packet': files['inputs/PACKET.json'], 'author_manifest': c.old.AUTHOR_MANIFEST_PIN,
        'files': files, 'train_rate_scope': 'canonical_metric_decoder_inputs_not_restricted_calibration',
        'checkpoint_training_cohort': 'unknown', 'resource_adequacy': False}
    # Only the author-manifest authority boundary is generated. No shape/profile or
    # mount validator is replaced, and no original checkpoint is opened.
    generated = clone(c.old, {'author_manifest': lambda: {'files': author}})
    bindings = put(root / 'protocol/BINDINGS.json', {'generated_metadata': True})
    bindings_pin = {k: bindings[k] for k in ('bytes', 'sha256')}
    program_pin = manifest['files']['validation_adapter.py']
    plan = c.old.method_plan(program_pin, bindings_pin, materials['packet']['sha256'], PROFILE)
    declaration = put(root / 'protocol' / PHASE / 'declaration.json', plan)
    owned_source = pin(b'generated owned component identity')
    job = {'schema': 'smc_restricted_validation_execution_job_v1', 'route': c.old.ROUTE,
        'outcome': OUTCOME, 'condition': PHASE, 'phase_id': PHASE, 'access_condition': c.old.ACCESS,
        'source': c.core.VALIDATION_SOURCE_PIN, 'resource_profile': PROFILE,
        'submission_keys': ['offline'], 'program_sha256': program_pin['sha256'],
        'declaration_sha256': declaration['sha256'], 'method_freeze_sha256': declaration['sha256'],
        'bindings': bindings_pin, 'max_file_bytes': c.old.FILE_CAP,
        'packet_sha256': materials['packet']['sha256']}
    actual_job = {**job, 'source': owned_source}
    execution = put(root / 'execution/EXECUTION.json', actual_job)
    retained_path = REPO / 'benchmarks/paper/PAPER-SMC-RNN-2024/implementations/aggregate-episode-v1/worker.py'
    source(retained_path, c.core.RETAINED_WORKER_PIN)
    retained = {'path': str(retained_path), **c.core.RETAINED_WORKER_PIN}
    inputs = {'core': generated, 'prepared': {'declaration': declaration, 'bindings': bindings},
        'manifest': manifest, 'materials': materials, 'component': component,
        'material_root': material, 'plan': plan, 'job': job}
    def actual_body(*args, **kwargs):
        raw = c.core.body(*args, **kwargs)
        charge('generated_read_bytes', len(raw))
        return raw
    builder = clone(c.core, {'body': actual_body})
    return types.SimpleNamespace(inputs=inputs, builder=builder, root=root, program=program,
        declaration=declaration, execution=execution, retained=retained, source=owned_source,
        materials=materials, plan=plan, job=job, actual_job=actual_job, generated=generated)


class OwnedValidationControls(unittest.TestCase):
    def test_01_valid_identity_profile_and_prerequest_readonly_composition(self):
        c = context(); f = build_material_fixture(c)
        # Genuine fixed original author-manifest authority rejects this synthetic roster.
        with self.assertRaisesRegex(ValueError, 'Only projected packet'):
            c.old.validate_material_record(f.materials)
        def build():
            return f.builder.owner_mounts(f.inputs, f.program['path'], f.declaration['path'],
                f.execution['path'], {k: f.execution[k] for k in ('bytes', 'sha256')},
                retained_worker_descriptor=f.retained, component_source=f.source)
        rows = build()
        self.assertTrue(rows); self.assertTrue(all(x['readonly'] is True for x in rows))
        self.assertFalse(any(x['destination'] in {'/request.json', '/output', '/work', '/tmp'} for x in rows))
        self.assertFalse(any(f.root.rglob('REQUEST.json')))
        ep = types.SimpleNamespace(_protocol={'generated': True}, data=f.inputs,
            repository_root=REPO, source_identity=lambda: f.source,
            file_mount=lambda path, expected, purpose: {'path': str(path), 'kind': 'file',
                'purpose': purpose, 'files': {'.': expected}})
        mount_method = method(c.episode_raw, 'ValidationEpisode', 'mounts_for',
            {'need': c.core.need, 'path': c.core.path, 'PHASE': PHASE,
             'EPISODE_REL': Path('benchmarks/paper/PAPER-SMC-RNN-2024/implementations/aggregate-episode-v1'),
             'owner_mounts': f.builder.owner_mounts}, 'selected-episode-mounts.py')
        owner_mounts = mount_method(ep, f.root / 'protocol/PROTOCOL.json', ep._protocol, PHASE,
            f.execution['path'], {k: f.execution[k] for k in ('bytes', 'sha256')}, {})
        self.assertEqual(set(owner_mounts), {x['destination'] for x in rows})
        self.assertFalse(any(f.root.rglob('REQUEST.json')))
        target = f.inputs['material_root'] / 'official_source/generated_model.py'
        original = target.read_bytes(); charge('generated_read_bytes', len(original))
        for alteration in ('directory', 'symlink', 'hardlink'):
            with self.subTest(alteration=alteration):
                target.unlink()
                if alteration == 'directory': target.mkdir()
                elif alteration == 'symlink': target.symlink_to(f.root)
                else:
                    donor = f.root / 'hardlink-donor'; put(donor, original); os.link(donor, target)
                with self.assertRaises((ValueError, OSError)): build()
                if alteration == 'directory': target.rmdir()
                else: target.unlink()
                if alteration == 'hardlink': donor.unlink()
                put(target, original)
        with self.assertRaisesRegex(ValueError, 'Exact selected leaf mounts'):
            c.old.validate_worker_mounts([{**rows[0], 'source': str(f.root)}] + rows[1:], rows)
        limits = {key: 1 for key in c.contract.RESOURCE_KEYS}
        limits.update(memory_bytes=8589934592, cpu_nanos=6000000000, cpu_seconds=60000,
            producer_seconds=10800, scratch_bytes=4096, max_output_bytes=4096,
            max_file_bytes=4096, manifest_bytes=1024, inventory_bytes=4096)
        name = 'smc-' + 'a' * 32 + '-b'
        request = {'schema': 'smc_aggregate_phase_request_v1', 'phase_id': PHASE,
            'action': 'held_attempt', 'role': 'B', 'image': 'sha256:' + 'b' * 64,
            'command': ['/usr/local/bin/python', '-I', '-S', '-B', '/runner/worker.py'],
            'workdir': '/work', 'source': f.source, 'exposure': pin(b'generated exposure'),
            'clock': {'origin': 1.0, 'phase_deadline': 10801.0}, 'resources': limits,
            'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'},
            'aggregate': {'schema': 'smc_cgroup_plan_v1', 'phase_id': PHASE, 'name': name,
                'parent': '/generated/cgroup', 'path': '/generated/cgroup/' + name,
                'cgroup_parent': '/cgroup/' + name, 'deployment_pin': pin(b'generated deployment'),
                'invocation_pin': pin(b'generated invocation')}}
        self.assertIs(c.contract.validate_request(request, owner_mounts, 11281.0), request)
        changes = [('phase_id', 'test'), ('role', 'A'), ('action', 'native_attempt')]
        for key, value in changes:
            bad = copy.deepcopy(request); bad[key] = value
            with self.assertRaises(ValueError): c.contract.validate_request(bad, owner_mounts, 11281.0)
        for key, values in {'cpu_seconds': [True, 0, 64801, 1.5], 'producer_seconds': [7200, True],
                            'memory_bytes': [8589934591], 'cpu_nanos': [1000000000],
                            'pids': [False]}.items():
            for value in values:
                bad = copy.deepcopy(request); bad['resources'][key] = value
                with self.assertRaises(ValueError): c.contract.validate_request(bad, owner_mounts, 11281.0)
        for cpu in (1, 64800):
            allowed = copy.deepcopy(request); allowed['resources']['cpu_seconds'] = cpu
            c.contract.validate_request(allowed, owner_mounts, 11281.0)
        for change in ({'phase_id': 'test'}, {'condition': 'test'},
                       {'resource_profile': {**PROFILE, 'cpu_seconds': True}}):
            bad = {**f.actual_job, **change}
            with self.assertRaises(ValueError):
                c.old.validate_job(f.plan, bad, f.inputs['manifest']['files']['validation_adapter.py'],
                    {k: f.inputs['prepared']['bindings'][k] for k in ('bytes', 'sha256')})
        OBS['mounts'] = {'count': len(rows), 'no_request_before_mounts': True,
            'generated_author_manifest_boundary': True, 'original_material_admission': False}

    def test_02_attachment_acknowledgement_precedes_single_release(self):
        c = context()
        helper = module('_control_ack', source(HERE / 'ack_controls.py'), HERE / 'ack_controls.py')
        counters = {}
        OBS['ack'] = helper.exercise_ack(self, c.derived['common.py'], c.derived['journal.py'],
            c.provider_raw, artifact_root=ART / 'ack', accounting=counters)
        OBS['ack_counters'] = counters

    def test_03_failure_closure_distinguishes_never_launched_and_unknown(self):
        c = context()
        helper = module('_control_closure', source(HERE / 'closure_controls.py'), HERE / 'closure_controls.py')
        counters = {}
        OBS['closure'] = helper.exercise_closure(self, c.derived['common.py'], c.derived['runner.py'],
            c.derived['process_owner.py'], ART, accounting=counters)
        OBS['closure_counters'] = counters

    def test_04_capture_is_unadmitted_until_real_parent_proofs_and_exact_frozen_bytes(self):
        c = context(); common = c.common
        def gate(fixture, admitted):
            namespace = {'Path': Path, 'CONDITIONS': (PHASE,), 'need': common.need,
                'ordinary': lambda p: Path(p), 'body': fixture.files.body, 'read': fixture.files.read,
                'pin': common.pin, 'encoded': common.encoded,
                'legacy': types.SimpleNamespace(source_identity=lambda: fixture.source,
                    load=lambda: types.SimpleNamespace(admit_closed_prediction=admitted))}
            functions(c.derived['runner.py'], {'custody', 'validate_aggregate_completion'},
                namespace, 'selected-derived-runner.py')
            return namespace['custody'](fixture.root, fixture.result_pin['sha256'], ART / 'unused-custody')
        calls = []
        positive = c.proofs.ClosureFixture(common, charge)
        self.assertEqual(gate(positive, lambda *a: calls.append('admitted') or 'eligible'), 'eligible')
        self.assertEqual(calls, ['admitted'])
        mutations = [
            ('controller_closure', lambda d: d['controller_group'].update(absence_verified=False)),
            ('result', lambda d: d['controller_execution'].update(natural_exit=False)),
            ('result', lambda d: d.update(error={'type': 'TimeoutError'})),
            ('finished', lambda d: d['counters']['memory_events'].update(oom_kill=1)),
            ('closed', lambda d: d.update(complete=False)),
            ('removed_wrapper', lambda d: d['value'].update(all_scopes_removed=False)),
            ('provider_receipt', lambda d: d.update(all_native_resources_closed=False)),
            ('attached', lambda d: d['event'].update(container_id='d' * 64))]
        for stage, change in mutations:
            with self.subTest(stage=stage):
                fixture = c.proofs.ClosureFixture(common, charge,
                    lambda actual, doc, stage=stage, change=change: change(doc) if actual == stage else None)
                before = len(calls)
                with self.assertRaises((ValueError, KeyError)):
                    gate(fixture, lambda *a: calls.append('forbidden'))
                self.assertEqual(len(calls), before)
        # Exact controller callback body may publish only an explicitly unadmitted capture.
        files = c.proofs.ProofFiles(common, charge)
        declaration = {'generated_method': True}
        declaration_pin = files.put('/generated/protocol/declaration.json', declaration)
        prediction_pin = pin(b'generated prediction bytes, not HDF5')
        prediction = {'path': '/generated/quarantine/offline.h5', **prediction_pin}
        method_pin = {'path': '/generated/protocol/declaration.json', **declaration_pin}
        component_pin = pin(b'generated VALID component')
        e = types.SimpleNamespace(PAIR_SHA='a' * 64, TASK_SHA='b' * 64,
            _captured_actual={PHASE: {'prediction': prediction, 'actual': {'generated': True}}},
            _protocol={'programs': {PHASE: {'declaration': declaration_pin, 'method': method_pin}}},
            source_identity=lambda: component_pin, data={'job': {'packet_sha256': 'c' * 64}})
        def write_capture(path, raw, mode=0o400):
            if str(path) in files.files: raise FileExistsError(str(path))
            charge('generated_metadata_bytes', len(raw)); files.files[str(path)] = raw
            return pin(raw)
        base = {'PHASE': PHASE, 'OUTCOME': OUTCOME, 'ROUTE': 'smc_validation_owned_reference_v1',
            'need': common.need, 'path': c.core.path, 'pin': pin, 'body': files.body,
            'encode': c.core.encode, 'write_new': write_capture,
            'ref': lambda p: {'path': str(p), **pin(files.body(p))}}
        freeze_callback = method(c.episode_raw, 'ValidationBenchmark', 'freeze', base,
            'selected-unadmitted-capture-method.py')
        destination = Path('/generated/capture.json')
        capture_desc = freeze_callback(types.SimpleNamespace(episode=e), '/generated/pair', e.PAIR_SHA,
            '/generated/task', e.TASK_SHA, PHASE, OUTCOME, {'offline': prediction['path']},
            '/generated/protocol/declaration.json', destination, max_bytes=1024)
        capture = files.read(destination, {k: capture_desc[k] for k in ('bytes', 'sha256')})
        self.assertIs(capture['custody_admitted'], False)
        self.assertIs(capture['parent_aggregate_closure_still_required'], True)
        self.assertNotIn('freeze', capture)
        # Final admission uses the exact method body, generated metadata and the
        # numerical freeze boundary only. Differing completed snapshot bytes refuse.
        for drift in (False, True):
            fixture = c.proofs.ClosureFixture(common, charge)
            f = fixture.files
            protocol = {'programs': {PHASE: {'method': method_pin}}}
            cap = {**capture, 'component_source': fixture.component_source}
            cap_pin = f.put('/generated/unadmitted.json', cap)
            receipt = {'quarantine_root': '/generated/quarantine',
                       'output_inventory': {'files': {'offline.h5': prediction_pin}}}
            receipt_pin = f.put('/generated/provider-receipt.json', receipt)
            pair = {'schema': 'smc_validation_unadmitted_closed_phase_v1',
                'route': 'smc_validation_owned_reference_v1',
                'conditions': {PHASE: {'freeze_path': '/generated/unadmitted.json', 'freeze': cap_pin,
                    'receipt_path': '/generated/provider-receipt.json', 'receipt': receipt_pin}},
                'owner_source': fixture.source, 'owner_invocation_pin': fixture.invocation_pin,
                'protocol_path': fixture.invocation['protocol_path'],
                'protocol_sha256': fixture.invocation['protocol_pin']['sha256'],
                'outcome': fixture.invocation['clock']['outcome'], 'private_target_accessed': False}
            fixture.result['pair_closed_pin'] = f.put(fixture.output / 'PAIR_CLOSED.json', pair)
            fixture.result_pin = f.put(fixture.root / 'RESULT.json', fixture.result)
            grade_root = Path('/generated/grader')
            grade_manifest = {'files': {}}
            for name in ('validation_grade.py', 'VALID_PANEL.json'):
                raw = ('generated external grading source ' + name).encode()
                f.files[str(grade_root / name)] = raw; charge('generated_metadata_bytes', len(raw))
                grade_manifest['files'][name] = pin(raw)
            grade_pin = f.put(grade_root / 'SOURCE.json', grade_manifest)
            episode = types.SimpleNamespace(HERE=Path('/generated/component'),
                _protocol_path=Path('/generated/protocol/PROTOCOL.json'),
                CLOSED_SCHEMA='smc_validation_unadmitted_closed_phase_v1',
                source_identity=lambda: fixture.component_source,
                admit_protocol=lambda *a: (protocol, {}),
                data={'job': {'packet_sha256': 'c' * 64}, 'material_root': Path('/generated/materials'),
                    'materials': {'packet': pin(b'generated packet metadata')},
                    'binding': {'grade_source': {'path': str(grade_root / 'SOURCE.json'), **grade_pin}}})
            final_calls = []
            def final_freeze(*args, **kwargs):
                final_calls.append((args, kwargs))
                frozen = {'snapshot': {**prediction_pin, 'path': '/generated/frozen/prediction.h5'}}
                if drift: frozen['snapshot']['sha256'] = 'f' * 64
                p = Path('/generated/frozen/FREEZE.json'); return {'path': str(p), **f.put(p, frozen)}
            def write_final(path, raw, mode=0o400):
                if str(path) in f.files: raise FileExistsError(str(path))
                charge('generated_metadata_bytes', len(raw)); f.files[str(path)] = raw
                return pin(raw)
            namespace = {'Path': Path, 'os': os, 'PHASE': PHASE,
                'ROUTE': 'smc_validation_owned_reference_v1', 'need': common.need,
                'path': c.core.path, 'read': f.read, 'body': f.body, 'pin': pin,
                'encode': c.core.encode, 'decode': c.core.decode,
                'checked': lambda d: f.body(d['path'], {k: d[k] for k in ('bytes', 'sha256')}),
                'write_new': write_final, 'ref': lambda p: {'path': str(p), **pin(f.body(p))},
                'load_module': lambda *a: types.SimpleNamespace(freeze_prediction=final_freeze)}
            admit = method(c.episode_raw, 'ValidationEpisode', 'admit_closed_prediction', namespace,
                           'selected-postclosure-admission-method.py')
            output = ART / ('custody-drift' if drift else 'custody-exact')
            if drift:
                with self.assertRaisesRegex(ValueError, 'Final immutable snapshot'):
                    gate(fixture, lambda folder, result, invocation, unused: admit(episode, folder, result, invocation, output))
                self.assertNotIn(str(output / 'CUSTODY.json'), f.files)
            else:
                result = gate(fixture, lambda folder, result, invocation, unused: admit(episode, folder, result, invocation, output))
                record = f.read(result['path'], {k: result[k] for k in ('bytes', 'sha256')})
                self.assertIs(record['operational_custody_admitted'], True)
                self.assertIsNone(record['scientific_success'])
                with self.assertRaises(FileExistsError):
                    gate(fixture, lambda folder, result, invocation, unused: admit(episode, folder, result, invocation, ART / 'custody-repeat'))
            self.assertEqual(len(final_calls), 1)
            self.assertIn(str(fixture.root / 'VALIDATION_CUSTODY_STARTED.json'), f.files)
        OBS['custody'] = {'actual_retained_proof_gate': True, 'generated_proofs_only': True,
            'unadmitted_capture_callback': True, 'different_frozen_bytes_refused': True,
            'actual_numerical_freezing': False, 'target_or_checkpoint_read': False}


def initialize():
    global ART, ACTIVE
    text = os.environ.get('ARTIFACT_DIR')
    if not text: raise ValueError('Fresh external ARTIFACT_DIR required')
    path = Path(text)
    if not path.is_absolute() or str(path) != text or path.resolve() != path or '..' in path.parts:
        raise ValueError('Canonical absolute ARTIFACT_DIR required')
    if os.path.lexists(path) or not path.parent.is_dir() or path.is_relative_to(REPO) or REPO.is_relative_to(path):
        raise ValueError('Fresh ARTIFACT_DIR outside the source repository required')
    if any((p / '.git').exists() for p in (path.parent, *path.parent.parents)):
        raise ValueError('ARTIFACT_DIR outside Git required')
    path.mkdir(mode=0o700); ART = path; ACTIVE = True


def main():
    initialize()
    result = unittest.main(exit=False).result
    receipt = {'schema': 'smc-validation-owned-source-controls/v1', 'testsRun': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
        'successful': result.wasSuccessful(), 'source_identities': SOURCE_IDENTITIES,
        'counters': COUNTERS, 'observations': OBS,
        'old_tests_replayed': 0, 'actual_process_socket_signal_cgroup_Docker_or_scientific_execution': False,
        'source_authority': 'Generated selected material metadata; original author roster refusal is separate',
        'provider_release_evidence': 'Actual Channel and ParentJournal; native Provider release is static AST evidence only',
        'freeze_evidence': 'Actual custody proof prefix and exact method bodies; numerical freeze boundary is a spy',
        'checkpoint_training_cohort': 'unknown', 'resource_adequacy': False,
        'operational_native_qualification': False, 'scientific_success': None}
    raw = (json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode()
    (ART / 'CONTROL_RESULT.json').write_bytes(raw)
    print(json.dumps(receipt, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
