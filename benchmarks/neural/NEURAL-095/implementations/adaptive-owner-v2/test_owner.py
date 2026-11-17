"""Generated source/owner controls; no authentic arrays, Docker or AI execution."""
import base64
import builtins
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('_dmfc_adaptive_owner_test', HERE / 'configure.py')
builder = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(builder)
c, unused = builder.helpers()
BASE, Q = c.BASE, c.Q
IDS = tuple('case%06d' % i for i in range(258))
CHILD_PYTHON = '/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11'
CALLBACK = b'''calls = 0
def decide(context):
    global calls
    calls += 1
    assert context['query_count'] == 258 and context['training_count'] == 748
    assert context['current']['full_query_batch_visible']
    assert not context['query_fitting_allowed'] and not context['private_feedback_available']
    obs = context['tool_observations']
    if not obs:
        assert calls == 1 and not context['committed_predictions']
        return {'action': 'tool', 'tool_id': context['tool_id'], 'arguments': {'analysis': 'summary'}}
    if len(obs) == 1:
        mean = obs[0]['observation']['mean_unlabeled_count']
        return {'action': 'tool', 'tool_id': context['tool_id'], 'arguments': {'analysis': 'batch', 'offset': mean}}
    batch = obs[1]['observation']
    assert len(batch['case_id']) == len(batch['prediction_ms']) == 258
    index = context['current']['completed_cases']
    assert calls == index + 3 and len(context['committed_predictions']) == index
    return {'action': 'predict', 'case_id': context['current']['case_id'], 'prediction_ms': batch['prediction_ms'][index]}
'''
NUMERIC = b'''# Generated numerical unit fixture only; no real dataset or fit.
import base64, io, json
import numpy as np
def execute(inputs):
    request = json.loads(inputs['/input/operation.json'])
    op = request['operation']
    with np.load(io.BytesIO(inputs['/input/train.npz']), allow_pickle=False) as data:
        assert len(data['case_id']) == 748
        training_mean = float(np.mean(data['tp_ms']))
        if 'counts' in data.files:
            assert data['counts'].shape == (748, 4, 40)
    if op == 'prepare':
        assert '/input/query.npz' not in inputs
        result = {'artifact_base64': base64.b64encode(json.dumps(training_mean).encode()).decode()}
    else:
        assert float(json.loads(inputs['/input/fitted.bin'])) == training_mean
        with np.load(io.BytesIO(inputs['/input/query.npz']), allow_pickle=False) as data:
            ids = data['case_id'].tolist(); assert len(ids) == 258
            mean = float(np.mean(data['counts'])) if 'counts' in data.files else 0.0
            if 'counts' in data.files:
                assert data['counts'].shape == (258, 4, 40)
        args = request['payload']['arguments']
        if args.get('analysis') == 'summary':
            result = {'mean_unlabeled_count': mean}
        else:
            result = {'case_id': ids, 'prediction_ms': [training_mean + args.get('offset', 0.0)] * 258}
    return {'payload': result, 'state': None}
'''


def operator():
    return {'schema': 'dmfc-portable-deployment/v1', 'output_relative': 'artifacts-build/run',
        'runtime_identity': {'transport': {'docker': '/invented/docker', 'environment': {
            'PATH': '/usr/bin:/bin', 'HOME': '/invented/home', 'TMPDIR': '/invented/tmp',
            'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'DOCKER_HOST': 'unix:///invented/socket',
            'DOCKER_CONFIG': '/invented/config'}}, 'server': {'ID': 'invented', 'Name': 'invented',
            'ServerVersion': 'invented', 'OSType': 'linux', 'Architecture': 'arm64'},
            'image': {'reference': c.IMAGE, 'Id': c.IMAGE, 'Os': 'linux', 'Architecture': 'arm64'}}}


class OwnerControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = Path(tempfile.mkdtemp(prefix='da', dir=Path('/tmp').resolve()))
        cls.root = cls.temp / 'r'
        cls.operands = cls.temp / 'operands'; cls.operands.mkdir()
        method = c.capture(c.HERE / 'source' / BASE / 'numerical-policy/METHOD.json')
        gate = builder.module('_gate_review_fields', HERE / 'configuration_gate.py', (HERE / 'configuration_gate.py').read_bytes())
        reader = builder.module('_method_review_fields', c.HERE / 'source/authoring/dmfc-timing/paired-program-cli-v1/admission.py',
            (c.HERE / 'source/authoring/dmfc-timing/paired-program-cli-v1/admission.py').read_bytes())
        review = {'schema': 'dmfc-stateful-investigator-review/v2', 'candidate_id': 'NEURAL-095',
            'decision': 'source_and_procedure_reviewed_for_original_contract', 'reviewer': 'Generated fixture; not a real source review',
            'execution_authority': False, 'matched_method_proven_by_grader': False,
            'callback': c.pin(CALLBACK), 'program': c.pin(NUMERIC), 'method': c.pin(method),
            'method_field_findings': dict.fromkeys(reader.METHOD_FIELDS, 'Generated fixture assertion only.'),
            'checks': dict.fromkeys(gate.REVIEW_CHECKS, True), 'findings': 'Generated wiring control, not scientific method approval.'}
        cls.raw = {'callback': CALLBACK, 'program': NUMERIC, 'method': method, 'review': c.encode(review)}
        for name, body in cls.raw.items():
            (cls.operands / name).write_bytes(body)
        with patch('subprocess.Popen', side_effect=AssertionError('construction must not launch')):
            cls.deployment = builder.configure(operator(), cls.root,
                **{k: cls.operands / k for k in cls.raw}, expected={k: c.pin(v)['sha256'] for k, v in cls.raw.items()})
        cls.payload = c.decode((cls.root / 'CONFIGURATION_PAYLOAD.json').read_bytes())
        cls.freeze = c.decode((cls.root / BASE / 'SOURCE_FREEZE.json').read_bytes())
        cls.captured = {name: (cls.root / name).read_bytes() for name in cls.freeze['files']}
        cls.cm = builder.module('_rendered_gate_test', cls.root / BASE / 'configuration.py', cls.captured[BASE + '/configuration.py'])
        # Deliberately not an executable owner request. It only permits source
        # bootstrap; operation_owner.admit must reject these missing fields.
        request = c.canonical({'configuration_payload_sha256': c.pin(c.canonical(cls.payload))['sha256']})
        (cls.root / 'INVENTED_REQUEST.json').write_bytes(request)
        cls.configuration = {**copy.deepcopy(cls.payload), 'request': {'path': 'INVENTED_REQUEST.json', **c.pin(request)}}
        cls.config_path = cls.root / 'INVENTED_CONFIG.json'
        cls.config_raw = c.encode(cls.configuration); cls.config_path.write_bytes(cls.config_raw)
        cls.config_sha = c.pin(cls.config_raw)['sha256']
        cls.logical_retained_lower_bound = sum(p.stat().st_size for p in cls.temp.rglob('*') if p.is_file())

    @classmethod
    def tearDownClass(cls):
        retained = sum(p.stat().st_size for p in cls.temp.rglob('*') if p.is_file())
        print('GENERATED_RETAINED_BYTES_BEFORE_CLEANUP=' + str(retained), flush=True)
        print('SOURCE_AND_FIXTURE_OVERWRITE_IO_NOT_FULLY_METERED=true', flush=True)
        shutil.rmtree(cls.temp)

    def test_01_rendered_configuration_and_real_bootstrap(self):
        config, captured, freeze = self.cm.load(self.config_path, self.config_sha)
        self.assertEqual(freeze['adaptive_admission'], self.payload['adaptive_admission'])
        entry = builder.module('_actual_entry_test', self.root / BASE / 'entrypoint.py', captured[BASE + '/entrypoint.py'])
        with patch('subprocess.Popen', side_effect=AssertionError('no source bootstrap launch')), \
             patch('subprocess.run', side_effect=AssertionError('no Docker probe')):
            unused, config, stack, runtime = entry.bootstrap(self.config_path, self.config_sha)
        self.assertIs(stack.actor_backend.live, stack.live)
        self.assertEqual(stack.configuration.__file__, str(self.root / BASE / 'configuration.py'))
        self.assertEqual(runtime.contract.IMAGE, c.IMAGE)
        with self.assertRaises((ValueError, KeyError)):
            stack.operation_owner.admit(config)
        self.assertFalse(Path(config.value['output_root']).exists())

    def test_02_frozen_and_adaptive_bindings_are_distinct_and_view_matched(self):
        arms = self.payload['actor']['arms']
        for mode, schema, policy in (('frozen_program', 'dmfc-offline-reference/v1', 'single_frozen_fit_batch/v1'),
                                      ('case_adaptive', 'dmfc-case-investigator/v1', 'stateful_case_decisions/v1')):
            self.assertEqual(arms[mode + '__cue_only']['program'], arms[mode + '__neural']['program'])
            for view in ('cue_only', 'neural'):
                value = c.decode(self.captured[arms[mode + '__' + view]['config']['path']])
                self.assertEqual((value['schema'], value['policy']), (schema, policy))
        self.assertEqual(c.pin(self.captured[arms['frozen_program__neural']['program']['path']]), self.cm.FROZEN_ACTOR_PIN)
        self.assertNotEqual(arms['case_adaptive__neural']['program'], arms['frozen_program__neural']['program'])
        self.assertEqual(self.payload['limits'], self.cm.LIMITS)
        self.assertTrue(all(v[k] == 0 for v in self.payload['reservation_policy'].values()
                            for k in ('model_input_tokens', 'model_output_tokens', 'model_cost_microusd')))

    def test_03_all_data_references_and_non_arithmetic_scoring_preserved(self):
        unused, original, pin = c.source_templates(c.HERE)
        path = Q + '/dmfc-paired-delivery-20261114-v1/DELIVERY_MANIFEST.json'
        before, after = map(c.decode, (original[path], self.captured[path]))
        before['evaluator_sources']['pair_worker'] = after['evaluator_sources']['pair_worker']
        self.assertEqual(before, after)
        for name in ('entrypoint.py', 'controller.py', 'actor_backend.py', 'operation_owner.py', 'offline_actor.py'):
            self.assertEqual(self.captured[BASE + '/' + name], original[BASE + '/' + name])
        worker = 'authoring/dmfc-timing/paired-investigation-v1/pair_worker.py'
        self.assertIn(builder.source('paired-arithmetic-v2/paired.py'), self.captured[worker])
        def protected_ast(raw):
            import ast
            return [ast.dump(n, include_attributes=False) for n in ast.parse(raw).body
                    if isinstance(n, ast.FunctionDef) and n.name in ('strict', 'read_pin', 'run', 'main')]
        self.assertEqual(protected_ast(original[worker]), protected_ast(self.captured[worker]))
        self.assertEqual(after['scientific_scope']['training_trials'], 748)
        self.assertEqual(after['scientific_scope']['assessment_cases_per_view'], 258)
        self.assertEqual(after['scientific_scope']['neural_shape_per_case'], [4, 40])
        self.assertEqual(len(after['scientific_scope']['references']), 5)

    def test_04_altered_callback_or_review_refused_by_deployed_gate(self):
        for mutation in ('callback', 'review'):
            value = copy.deepcopy(self.payload)
            value['adaptive_admission'][mutation]['sha256'] = '0' * 64
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.cm.validate_adaptive_binding(value, self.captured, self.freeze)

    def test_05_frozen_source_replacement_and_cross_view_drift_refused(self):
        for key in ('frozen_program__cue_only', 'case_adaptive__neural'):
            value = copy.deepcopy(self.payload)
            value['actor']['arms'][key]['program'] = value['adaptive_admission']['callback']
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.cm.validate_adaptive_binding(value, self.captured, self.freeze)

    def test_06_unreviewed_assembly_refused_before_destination(self):
        review = c.decode(self.raw['review']); review['checks']['no_query_fitting'] = False
        path = self.operands / 'bad-review'; path.write_bytes(c.encode(review))
        expected = {k: c.pin(v)['sha256'] for k, v in self.raw.items()}; expected['review'] = c.pin(path.read_bytes())['sha256']
        destination = self.temp / 'bad'
        with self.assertRaisesRegex(ValueError, 'all adaptive and frozen'):
            builder.configure(operator(), destination, callback=self.operands / 'callback',
                program=self.operands / 'program', method=self.operands / 'method', review=path, expected=expected)
        self.assertFalse(destination.exists())

    def test_07_exact_negative_and_zero_paired_results(self):
        path = 'authoring/dmfc-timing/paired-investigation-v1/pair_worker.py'
        worker = builder.module('_deployed_pair_arithmetic', self.root / path, self.captured[path])
        groups = [i % 40 for i in range(258)]; contexts = [i // 5 for i in groups]
        zero = worker.pair_difference([700.0]*258, [700.0]*258, [700.0]*258, groups, contexts)
        negative = worker.pair_difference([700.0]*258, [701.0]*258, [700.0]*258, groups, contexts)
        self.assertEqual(zero['cue_minus_neural_mae_ms'], 0.0)
        self.assertEqual(negative['cue_minus_neural_mae_ms'], -1.0)
        self.assertIsNone(negative['scientific_pass_floor'])

    def test_08_real_owner_composition_complete_four_cells_adapts_and_closes(self):
        entry = builder.module('_actual_entry_e2e', self.root / BASE / 'entrypoint.py', self.captured[BASE + '/entrypoint.py'])
        unused, config, stack, runtime = entry.bootstrap(self.config_path, self.config_sha)
        out = Path(config.value['output_root']); out.mkdir()
        for name in ('arms', 'cells', 'invitations', 'actors'):
            (out / name).mkdir()
        # Generated data gets its own in-memory manifest. The production delivery
        # pins remain immutable. No authentic body is opened during this control.
        manifest = copy.deepcopy(stack.producer.load_manifest())
        def install(relative, raw):
            path = self.root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
            return {'path': relative, **c.pin(raw)}
        manifest['evaluator_only_assets']['identity'] = install('generated/identity.json', c.encode({'schema_version': 1, 'case_id': IDS}))
        for view in stack.producer.VIEWS:
            inputs = []
            for partition, n in (('train', 748), ('query', 258)):
                values = {'case_id': np.asarray(IDS if partition == 'query' else ['train%06d'%i for i in range(n)]),
                          'condition': np.arange(n) % 40, 'context': (np.arange(n)%40)//5,
                          'nominal_ts_ms': np.full(n, 700.0), 'clock_seconds': np.arange(n, dtype=float)}
                if partition == 'train':
                    values.update(tp_ms=np.full(n, 700.0), fold=np.minimum(np.arange(n)*5//n,4))
                if view == 'neural':
                    values['counts'] = np.full((n,4,40), 3, dtype='<u4')
                buffer = io.BytesIO(); np.savez(buffer, **values)
                p = install('generated/' + view + '/' + partition + '.npz', buffer.getvalue())
                inputs.append({**p, 'mount_destination': '/input/' + partition + '.npz', 'read_only': True})
            manifest['public_views'][view]['public_inputs'] = inputs
        events, numeric_requests, channels, actors, backends = [], [], {}, [], []
        fixture_numeric = builder.module('_generated_numeric_only', '<generated>', NUMERIC)
        class FixtureExecutor:
            def __init__(self, *args, **kwargs): pass
            def absence(self): return True
            def execute(self, source, inputs, *, output_name, **kwargs):
                by_mount = {v['mount_destination']: Path(v['path']).read_bytes() for v in inputs}
                if output_name == 'submission.npz':
                    self_test.assertTrue(all(p.poll() is not None for p in actors))
                    events.append('export'); return by_mount['/input/opaque.bin'], 0
                self_test.assertEqual(source, NUMERIC)
                request = c.decode(by_mount['/input/operation.json'])
                numeric_requests.append(copy.deepcopy(request))
                result = fixture_numeric.execute(by_mount)
                return c.canonical(result), 0
        class PipeChannel:
            def __init__(self, path, *args):
                self.path = path; self.token = 'fixture-token'; self.proc = None; channels[str(path)] = self
            def accept(self, until): self_test.assertIsNotNone(self.proc)
            def receive(self, expected, until):
                selector = selectors.DefaultSelector(); selector.register(self.proc.stdout, selectors.EVENT_READ)
                try:
                    self_test.assertTrue(selector.select(max(0, min(10, until-time.monotonic()))), 'actor response deadline')
                finally: selector.close()
                line = self.proc.stdout.readline(65537)
                self_test.assertTrue(line and len(line) <= 65536, 'bounded first actor line')
                result = c.decode(line); self_test.assertEqual(result['op'], expected)
                return result.get('source') if expected == 'freeze' else result.get('request')
            def answer(self, value, until, status='ok'):
                result = {'status': status, **value} if status == 'committed' else {'status': status, 'payload': value}
                self.proc.stdin.write(c.canonical(result) + b'\n'); self.proc.stdin.flush()
            def close(self):
                if self.proc:
                    self.proc.stdin.close(); self.proc.stdout.close(); self.proc.stderr.close()
        launcher = self.temp / 'generated_actor_launcher.py'
        launcher.write_text('''import builtins, pathlib, sys, types
p = pathlib.Path(sys.argv[1]); body = p.read_bytes(); original = builtins.__import__
def importing(name, *args, **kwargs):
    if name == 'pathlib':
        return types.SimpleNamespace(Path=lambda value: p if value == '/actor/program.py' else pathlib.Path(value))
    return original(name, *args, **kwargs)
ns = {'__name__': '__main__', '__file__': str(p), '__builtins__': dict(vars(builtins), __import__=importing)}
exec(compile(body, str(p), 'exec'), ns)
''')
        class Supervisor:
            def __init__(self, config, stack, runtime, session, budget, work_end):
                self.key = session.mode; self.binding = config.value['actor']['arms'][self.key]
            def launch(self):
                channel = channels[str(out / 'arms' / self.key / 'arm.sock')]
                cwd = out / 'actors' / self.key; cwd.mkdir()
                self.proc = subprocess.Popen([CHILD_PYTHON, '-I', '-B', str(launcher), str(self_root / self.binding['program']['path'])],
                    cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env={'PATH':'/usr/bin:/bin', 'LANG':'C', 'LC_ALL':'C'}, close_fds=True, bufsize=0)
                actors.append(self.proc); channel.proc = self.proc
                self.proc.stdin.write(c.canonical(c.decode((self_root / self.binding['config']['path']).read_bytes())) + b'\n'); self.proc.stdin.flush()
            def stop(self):
                code = self.proc.wait(timeout=5)
                self_test.assertEqual(code, 0, self.proc.stderr.read().decode())
                events.append('actor-stopped'); return {'absence_verified': True}
        self_test, self_root = self, self.root
        original_backend = stack.actor_backend.ActorBackend
        def record_backend(**kwargs):
            backend = original_backend(**kwargs); backends.append(backend); return backend
        def generated_pair(evaluator, mode, outputs, joint, source_manifest, stage, prior=None):
            self.assertEqual(len(backends), 4)
            self.assertTrue(all(b.closed and b.actor_absent and b.state == 'committed' for b in backends))
            self.assertTrue(all(p.poll() == 0 for p in actors))
            if stage == 'grade': self.assertEqual(set(evaluator.validated), set(stack.producer.MODES))
            events.append(stage)
            result = {'status': 'valid_complete_pair' if stage == 'validate' else 'paired_predictions_scored',
                'submissions': {v: c.pin(raw) for v, raw in outputs.items()}, 'joint_commit_sha256': joint,
                'identity': manifest['evaluator_only_assets']['identity'],
                'private_target_reads': int(stage == 'grade'), 'private_target_decodes': int(stage == 'grade'),
                'private_reference_reads': 3 if stage == 'grade' else 0,
                'new_fits_in_trusted_grader': 0, 'logical_metric_calls': 2}
            return result
        try:
            with patch.object(stack.producer, 'load_manifest', return_value=manifest), \
                 patch.object(stack.live, 'UnitExecutor', FixtureExecutor), \
                 patch.object(stack.actor_backend, 'ActorBackend', side_effect=record_backend), \
                 patch.object(stack.actor_backend, 'Channel', PipeChannel), \
                 patch.object(stack.actor_runtime, 'Supervisor', Supervisor), \
                 patch.object(stack.live.PairedEvaluator, '_pair', generated_pair):
                study, actual_backends, budget = stack.controller.compose(config, stack, runtime, time.monotonic()+120)
                result = study.run()
            self.assertEqual(result['status'], 'four_cell_outputs_scored')
            self.assertEqual(len(study.outputs), 4)
            self.assertEqual([b.decisions for b in backends], [258]*4)
            self.assertEqual([b.tool_calls for b in backends], [1,1,2,2])
            self.assertEqual(events[-4:], ['validate','validate','grade','grade'])
            offsets = [r['payload']['arguments']['offset'] for r in numeric_requests
                       if r['operation'] == 'tool' and 'offset' in r['payload']['arguments']]
            self.assertEqual(offsets, [0.0,3.0], 'actual permitted count observation changes subsequent action')
            for key, raw in study.outputs.items():
                with np.load(io.BytesIO(raw), allow_pickle=False) as data:
                    self.assertEqual(tuple(data['case_id']), IDS)
                    expected = 703.0 if key == ('case_adaptive','neural') else 700.0
                    np.testing.assert_array_equal(data['prediction_ms'], np.full(258,expected))
            self.assertEqual(len({b.spec['source_sha256'] for b in backends[:2]}),1)
            self.assertEqual(len({b.spec['source_sha256'] for b in backends[2:]}),1)
            print('GENERATED_E2E=4_cells_1032_predictions_6_tool_observations_4_fresh_actor_children', flush=True)
        finally:
            for process in actors:
                if process.poll() is None:
                    process.kill(); process.wait(timeout=3)
            for channel in channels.values():
                if channel.proc:
                    for stream in (channel.proc.stdin,channel.proc.stdout,channel.proc.stderr):
                        if not stream.closed: stream.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
