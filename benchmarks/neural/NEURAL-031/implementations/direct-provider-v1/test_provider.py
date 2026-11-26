"""Invented40-context composition; real production client with fake HTTP only.

All socket constructors are trapped in parent and generated children. The sole
Popen seam replaces the trusted client entry script with one calling the exact
client.main and an injected FakeHTTP. No real credential or model is used.
"""
import argparse
import copy
from contextlib import redirect_stdout
import http.client
import io
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).absolute().parent))
import common as c
import provider as p
import client

SCRATCH = None
MODE = 'success'
MARKER = b'GENERATED-NO-AUTHORITY-MARKER-031'
EXTRA_WRITES = 0


def blocked(*args, **kwargs):
    raise AssertionError('Real network is forbidden in generated controls')


def response_for(request, mode='success'):
    request = c.decode(request)
    assert set(request) == {'model', 'input', 'tools', 'tool_choice', 'parallel_tool_calls', 'store',
                            'stream', 'background', 'truncation', 'max_output_tokens', 'text'}
    assert request['tools'] == [] and request['tool_choice'] == 'none'
    assert request['parallel_tool_calls'] is False and request['truncation'] == 'disabled'
    assert request['store'] is False and request['stream'] is False and request['background'] is False
    assert len(request['input']) == 1 and request['input'][0]['role'] == 'user'
    assert len(request['input'][0]['content']) == 1
    content = request['input'][0]['content'][0]
    assert set(content) == {'type', 'text'} and content['type'] == 'input_text'
    obs = c.decode(content['text'])
    text = c.encode({'schema': 'neural031_direct_response_v1', 'request_id': obs['request_id'],
                     'rows': [{'row_id': row, 'prediction': 1.0} for row in obs['arrays']['query_rowid']]}).decode()
    value = {'object': 'response', 'status': 'completed', 'error': None, 'incomplete_details': None,
             'id': 'resp_' + ('duplicate' if mode == 'duplicate' else obs['request_id']),
             'model': request['model'], 'max_output_tokens': request['max_output_tokens'],
             'tools': [], 'tool_choice': 'none', 'parallel_tool_calls': False, 'store': False,
             'truncation': 'disabled', 'previous_response_id': None, 'conversation': None, 'background': False,
             'usage': {'input_tokens': 100, 'output_tokens': 200, 'total_tokens': 300},
             'output': [{'type': 'message', 'role': 'assistant', 'status': 'completed',
                         'content': [{'type': 'output_text', 'text': text}]}]}
    if mode == 'malformed':
        value['output'][0]['content'][0]['text'] = '{"invalid_first_answer":true}'
    elif mode == 'incomplete':
        value['status'] = 'incomplete'
        value['incomplete_details'] = {'reason': 'max_output_tokens'}
    elif mode == 'refusal':
        value['output'][0]['content'] = [{'type': 'refusal', 'refusal': 'generated refusal'}]
    elif mode == 'tool':
        value['output'].append({'type': 'function_call', 'name': 'forbidden'})
    elif mode == 'second':
        value['output'].append(copy.deepcopy(value['output'][0]))
    elif mode == 'history':
        value['previous_response_id'] = 'resp_previous'
    elif mode == 'capacity':
        value = {'error': {'code': 'context_length_exceeded'}}
    return c.encode(value)


class FakeResponse:
    def __init__(self, raw, mode):
        self.raw, self.mode, self.offset = raw, mode, 0
        self.length = len(raw)
        self.status = 400 if mode == 'capacity' else 200

    def read(self, size):
        if self.mode == 'partial':
            self.mode = 'partial_raised'
            raise http.client.IncompleteRead(self.raw[:17], len(self.raw))
        part = self.raw[self.offset:self.offset + size]
        self.offset += len(part)
        self.length -= len(part)
        return part

    def getheader(self, name, default=None):
        return default

    def close(self):
        pass


class FakeHTTP:
    def __init__(self, host, *, port, timeout, context):
        assert host == 'api.openai.com' and port == 443 and timeout > 0
        assert context.check_hostname
        self.sock = None
        self.calls = 0

    def set_debuglevel(self, level):
        assert level == 0

    def request(self, method, path, *, body, headers, encode_chunked):
        assert self.calls == 0 and method == 'POST' and path == '/v1/responses'
        assert headers['Authorization'] == 'Bearer ' + MARKER.decode() and not encode_chunked
        self.calls += 1
        self.body = body

    def getresponse(self):
        if MODE == 'timeout':
            raise TimeoutError('Generated ambiguous first request')
        raw = b'x' * (c.RAW_CAP + 1) if MODE == 'overflow' else response_for(self.body, MODE)
        return FakeResponse(raw, MODE)

    def close(self):
        pass


def child_main():
    global MODE
    MODE = sys.argv[1]
    socket.socket = blocked
    socket.create_connection = blocked
    socket.getaddrinfo = blocked
    result = client.main(sys.argv[2:], http_factory=FakeHTTP)
    if MODE == 'extra_stdout' and result == 0:
        os.write(1, b'extra')
    raise SystemExit(result)


def close_fixture(temp, extra_writes, launches, complete_setup):
    """Always record acquired fixture bytes, including an interrupted setUpClass."""
    try:
        retained = sum(f.stat().st_size for f in Path(temp.name).rglob('*') if f.is_file())
        total = retained + extra_writes
        print(c.encode({'scope': 'generated_provider_fixture_cleanup', 'complete_setup': complete_setup,
                        'contexts': 40 if complete_setup else None, 'predictions': 1548 if complete_setup else None,
                        'fixture_artifact_bytes': total, 'retained_before_cleanup': retained, 'real_network_calls': 0,
                        'model_calls': 0, 'private_target_reads': 0, 'scores_computed': 0,
                        'mock_boundary': 'Popen entry script substitutes client.main HTTP factory; production broker/client/Sender/capture/collector execute',
                        'launches': launches}).decode())
        if total > 20 * 1024**2:
            raise AssertionError('Generated artifact allocation exceeded')
    finally:
        temp.cleanup()


class EpisodeClockTests(unittest.TestCase):
    """Pure metadata controls call the production admission guard directly."""

    def test_cli_selects_complete_ordered_roster_and_accounting_only(self):
        def identifiers(suite):
            if isinstance(suite, unittest.TestSuite):
                return [identifier for child in suite for identifier in identifiers(child)]
            return [suite.id()]

        module = sys.modules[__name__]
        loader = unittest.TestLoader()
        discovered = loader.loadTestsFromModule(module)
        expected = sorted(identifiers(discovered))
        self.assertEqual(loader.errors, [])
        self.assertEqual(len(expected), 27)
        self.assertEqual(len(set(expected)), discovered.countTestCases())
        accounting = [__name__ + '.FixtureAccountingTests.test_setup_failure_is_accounted_before_cleanup']
        captured = []

        class CaptureRunner:
            def __init__(self, **kwargs):
                pass

            def run(self, suite):
                captured.append((identifiers(suite), suite.countTestCases()))
                return unittest.TestResult()

        scratch_before, argv_before, runner_before = SCRATCH, sys.argv, unittest.TextTestRunner
        with tempfile.TemporaryDirectory(prefix='generated-cli-roster-', dir=scratch_before) as temporary:
            with patch.object(module, 'SCRATCH', scratch_before), \
                    patch.object(unittest, 'TextTestRunner', CaptureRunner):
                for flags, selected in (([], expected), (['--accounting-only'], accounting)):
                    with self.subTest(flags=flags), patch.object(
                            sys, 'argv', [__file__, '--scratch-root', str(Path(temporary).resolve()), *flags]):
                        self.assertEqual(main(), 0)
                        self.assertEqual(captured[-1], (selected, len(selected)))
        self.assertEqual(len(captured), 2)
        self.assertIs(SCRATCH, scratch_before)
        self.assertIs(sys.argv, argv_before)
        self.assertIs(unittest.TextTestRunner, runner_before)
        self.assertFalse(Path(temporary).exists())

    def check_clock(self, started=63.9, deadline=None, finished=None, config_deadline=None):
        deadline = started + 6 if deadline is None else deadline
        end = {'started': started, 'deadline': deadline,
               'finished': started if finished is None else finished}
        config = {'deadline': deadline if config_deadline is None else config_deadline}
        p.admit_episode_clock(end, config, {'episode_seconds': 6, 'cleanup_seconds': 1})

    def test_producer_bound_across_binary_exponents(self):
        for started in (63.9, 127.3):
            with self.subTest(started=started):
                deadline = started + 6
                self.assertGreater(deadline - started, 6)
                self.check_clock(started, deadline, deadline)

    def test_ordinary_exact_and_shorter_positive_bounds(self):
        for started, deadline in ((0, 6), (64.0, 70.0), (100.0, 105.0),
                                  (63.9, 65.0), (63.9, math.nextafter(63.9, math.inf))):
            with self.subTest(started=started, deadline=deadline):
                self.check_clock(started, deadline, deadline)

    def test_one_tick_beyond_producer_bound_refused(self):
        for started in (63.9, 127.3, 100.0):
            with self.subTest(started=started), self.assertRaisesRegex(ValueError, '^owned_episode_clock$'):
                self.check_clock(started, math.nextafter(started + 6, math.inf))

    def test_zero_and_negative_span_refused(self):
        for deadline in (63.9, math.nextafter(63.9, -math.inf), 62.9):
            with self.subTest(deadline=deadline), self.assertRaisesRegex(ValueError, '^owned_episode_clock$'):
                self.check_clock(deadline=deadline)

    def test_bad_nonfinite_bool_and_missing_times_refused(self):
        for field in ('started', 'finished', 'deadline'):
            for bad in (None, '63.9', True, False, float('nan'), float('inf'), -float('inf'), [], {}):
                end = {'started': 63.9, 'finished': 64.0, 'deadline': 69.9}
                end[field] = bad
                with self.subTest(field=field, bad=bad), self.assertRaisesRegex(ValueError, '^owned_episode_clock$'):
                    p.admit_episode_clock(end, {'deadline': 69.9}, {'episode_seconds': 6, 'cleanup_seconds': 1})
            end = {'started': 63.9, 'finished': 64.0, 'deadline': 69.9}
            del end[field]
            with self.subTest(missing=field), self.assertRaisesRegex(ValueError, '^owned_episode_clock$'):
                p.admit_episode_clock(end, {'deadline': 69.9}, {'episode_seconds': 6, 'cleanup_seconds': 1})

    def test_configuration_deadline_mismatch_refused(self):
        for deadline in (math.nextafter(69.9, -math.inf), math.nextafter(69.9, math.inf)):
            with self.subTest(config_deadline=deadline), self.assertRaisesRegex(ValueError, '^owned_episode_clock$'):
                self.check_clock(config_deadline=deadline)

    def test_finished_before_start_refused(self):
        with self.assertRaisesRegex(ValueError, '^owned_episode_clock$'):
            self.check_clock(finished=math.nextafter(63.9, -math.inf))

    def test_cleanup_bound_inclusive_but_next_tick_refused(self):
        for started in (63.9, 127.3, 100.0):
            deadline = started + 6
            cleanup_end = deadline + 1
            with self.subTest(started=started):
                self.check_clock(started, deadline, cleanup_end)
                with self.assertRaisesRegex(ValueError, '^owned_episode_clock$'):
                    self.check_clock(started, deadline, math.nextafter(cleanup_end, math.inf))


class FixtureAccountingTests(unittest.TestCase):
    def test_setup_failure_is_accounted_before_cleanup(self):
        holder = {}
        class BrokenFixture(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                cls.temp = tempfile.TemporaryDirectory(prefix='generated-accounting-only-', dir=SCRATCH)
                holder['root'] = Path(cls.temp.name)
                cls.addClassCleanup(lambda: close_fixture(cls.temp, 7, 0, False))
                (holder['root'] / 'retained-prefix.bin').write_bytes(b'abc')
                raise ValueError('Expected generated setup failure')

            def test_not_reached(self):
                raise AssertionError('Failed setup must prevent method execution')
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output):
            result = unittest.TextTestRunner(stream=errors).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(BrokenFixture))
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.testsRun, 0)
        self.assertIn('Expected generated setup failure', errors.getvalue())
        receipt = c.decode(output.getvalue())
        self.assertEqual(receipt['fixture_artifact_bytes'], 10)
        self.assertEqual(receipt['retained_before_cleanup'], 3)
        self.assertFalse(receipt['complete_setup'])
        self.assertIsNone(receipt['contexts'])
        self.assertFalse(holder['root'].exists())
        print(c.encode({'scope': 'expected_generated_setup_failure_accounting', 'expected_inner_errors': 1,
                        'fixture_bytes_written': 3, 'simulated_prior_overwrite_bytes': 7,
                        'source_runtime_controls_replayed': 0}).decode())


class ProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.temp = tempfile.TemporaryDirectory(prefix='generated-n031-provider-', dir=SCRATCH)
        cls.setup_complete = False
        cls.addClassCleanup(lambda: close_fixture(cls.temp, EXTRA_WRITES, len(getattr(cls, 'launches', [])), cls.setup_complete))
        cls.root = Path(cls.temp.name)
        cls.source_sha = c.pin((c.HERE / 'SOURCE.json').read_bytes())['sha256']
        cls.modules = c.load(cls.source_sha)
        engine = cls.modules['engine']
        cls.engine = engine
        counts = [37, 23, 52, 94, 50, 21, 33, 64, 53, 24, 67, 18, 23, 31, 57, 22, 28, 24, 31, 22]
        ids = np.arange(774, dtype=np.int64)
        groups = np.repeat(np.arange(20, dtype=np.int64), counts)
        common = np.column_stack((1 + (ids % 7) / 4, ids % 2, ids % 7 == 0, ids % 11 == 0)).astype(np.float64)
        common[0, 1] = -0.0
        activity = np.column_stack(((ids % 5) / 8, -(ids % 9) / 8))
        activity[common[:, 2:].astype(bool)] = np.nan
        activity[5, 0] = -0.0
        y = np.ones(774)
        y[np.arange(0, 731, 17)] = np.nan
        y[1] = -0.0
        assert np.isnan(y).sum() == 43
        original = copy.deepcopy(engine.source_inputs())
        support = {'schema': 'neural031_ordinary_public_support_v1', 'candidate_id': 'NEURAL-031',
                   'folds': [], 'request_rows': 774, 'query_targets_included': False}
        inputs = cls.root / 'inputs'
        for fold in range(20):
            train, query = groups != fold, groups == fold
            support_fold = {'fold': fold, 'rowids': ids[query].tolist(), 'views': {}}
            for offset, view in enumerate(('baseline', 'neural')):
                x = common if view == 'baseline' else np.column_stack((common, activity))
                packet = {'train_x': x[train], 'train_y': y[train], 'train_mouse': groups[train],
                          'train_rowid': ids[train], 'query_x': x[query], 'query_rowid': ids[query]}
                raw = engine.io.archive(np, packet)
                manifest = {'schema': 'neural031_ordinary_public_view_v1', 'candidate_id': 'NEURAL-031',
                    'fold': fold, 'held_mouse': engine.endpoint.MICE[fold], 'view': view, 'data': c.pin(raw),
                    'features': cls.modules['numeric'].COMMON + (['local_coactivity_norm', 'dendrite_coincident_norm'] if view == 'neural' else []),
                    'training_mouse_indices': [i for i in range(20) if i != fold], 'train_rows': int(train.sum()),
                    'query_rows': int(query.sum()), 'training_target': 'next_day_ratio_with_NaN_unavailable',
                    'query_target_or_followup_metadata': False, 'neural_activity_values_physically_present': view == 'neural',
                    'prediction_time': 'after_complete_Early_recording_for_next_day_size'}
                body = engine.io.encoded(manifest)
                directory = inputs / f'fold{fold:02d}' / view
                directory.mkdir(parents=True)
                (directory / 'data.npz').write_bytes(raw)
                (directory / 'manifest.json').write_bytes(body)
                selected = {'fold': fold, 'view': view, 'data': c.pin(raw), 'manifest': c.pin(body)}
                original['paired_views'][2 * fold + offset] = selected
                support_fold['views'][view] = {k: selected[k] for k in ('data', 'manifest')}
            support['folds'].append(support_fold)
        support_body = engine.io.encoded(support)
        support_path = inputs / 'support.json'
        support_path.write_bytes(support_body)
        original['support'] = c.pin(support_body)
        # Generated in-memory cohort only; no production CLI replacement exists.
        engine._source_inputs = original
        interpreter = Path(sys.executable).resolve()
        cls.spec = {'schema': 'neural031_provider_spec_v1', 'input_root': str(inputs), 'support_path': str(support_path),
            'provider': {'model': 'generated-provider-v1', 'max_output_tokens': 8192},
            'interpreter': {'path': str(interpreter), **c.pin(interpreter.read_bytes())},
            'limits': {'episode_seconds': 6, 'cleanup_seconds': 2, 'arm_seconds': 55,
                       'read_bytes': 1024**3, 'write_bytes': 256 * 1024**2},
            'authoring_exposure': 'Generated fixtures only. No original population, private targets, model or provider.'}
        cls.freeze = cls.root / 'freeze'
        cls.contract_pin = p.prepare(cls.spec, cls.freeze, cls.source_sha, modules=cls.modules)['contract']
        cls.value = c.decode((cls.freeze / 'CONTRACT.json').read_bytes())
        cls.child = cls.root / 'fake_http_child.py'
        cls.child.write_text('import sys\nsys.path.insert(0,' + repr(str(c.HERE)) + ')\nimport test_provider\ntest_provider.child_main()\n')
        cls.real_popen = subprocess.Popen
        cls.launches = []
        cls.arm = cls.root / 'arm'
        cls.arm_pin = cls.run_fake(cls.arm, 'success')['arm']
        cls.setup_complete = True

    @classmethod
    def run_fake(cls, output, mode):
        def launch(command, **kwargs):
            assert command[:5] == [cls.spec['interpreter']['path'], '-I', '-S', '-B', str(c.HERE / 'client.py')]
            assert kwargs['env'] == {'LANG': 'C', 'LC_ALL': 'C'} and kwargs['start_new_session'] is True
            assert len(kwargs['pass_fds']) == 3 and kwargs['close_fds'] is True
            cls.launches.append({'mode': mode, 'command': command[:7], 'cwd': str(kwargs['cwd'])})
            return cls.real_popen([*command[:4], str(cls.child), mode, *command[5:]], **kwargs)
        read_fd, write_fd = os.pipe()
        os.write(write_fd, MARKER)
        os.close(write_fd)
        try:
            with patch.object(p.subprocess, 'Popen', launch), patch.object(socket, 'socket', blocked), \
                    patch.object(socket, 'create_connection', blocked), patch.object(socket, 'getaddrinfo', blocked):
                return p.run(cls.freeze, cls.contract_pin, output, cls.source_sha, read_fd, modules=cls.modules)
        finally:
            try:
                os.close(read_fd)
            except OSError:
                pass

    def budget(self):
        return c.Budget(self.value['limits'])

    def prompt(self, index=0):
        return p.context(self.freeze, self.value['contexts'][index], self.engine, self.budget())[0]

    def admission(self):
        return p.admit(self.freeze, self.contract_pin, self.arm, self.arm_pin, self.source_sha, modules=self.modules)

    def mutate_and_refuse(self, path, transform):
        global EXTRA_WRITES
        before = path.read_bytes()
        after = transform(before)
        path.chmod(0o600)
        path.write_bytes(after)
        EXTRA_WRITES += len(after) + len(before)
        try:
            with self.assertRaises((ValueError, OSError, KeyError, TypeError)):
                self.admission()
        finally:
            path.write_bytes(before)

    def test_complete_forty_real_binding_exchanges_collect_original1548(self):
        result = self.admission()
        self.assertEqual((result['contexts'], result['predictions']), (40, 1548))
        self.assertFalse(result['remote_context_qualified'])
        self.assertFalse(result['scientific_qualification'])
        self.assertEqual(len([x for x in self.launches if x['mode'] == 'success']), 40)
        collection = c.decode((self.arm / 'collection/COLLECTION.json').read_bytes())
        self.assertFalse(collection['actual_provider_first_responses_verified'])
        self.assertFalse(collection['no_tools_enforced'])

    def test_full_observation_only_no_history_and_numeric_presentation_unchanged(self):
        for index, row in enumerate(self.value['contexts']):
            prompt = self.prompt(index)
            request = c.decode((self.arm / f'episodes/{index:02d}/custody/REQUEST.bin').read_bytes())
            self.assertEqual(request, c.decode(self.modules['bridge'].request_body(prompt, **self.value['provider'])))
            self.assertEqual(request['input'][0]['content'][0]['text'].encode(),
                             (self.freeze / f"presentations/fold{row['fold']:02d}/{row['view']}/OBSERVATION.json").read_bytes())
            obs = c.decode(prompt)
            self.assertEqual(len(obs['arrays']['train_x'][0]), 4 if row['view'] == 'baseline' else 6)
            self.assertNotIn('query_y', obs['arrays'])
        self.assertIn('null', self.prompt())
        self.assertIn('-0.0', self.prompt())

    def test_source_or_configuration_drift_refused(self):
        with self.assertRaises(ValueError):
            c.load('0' * 64)
        self.mutate_and_refuse(self.freeze / 'CONTRACT.json', lambda b: b + b' ')
        self.mutate_and_refuse(self.arm / 'episodes/00/CONFIG.json', lambda b: b.replace(b'generated-provider-v1', b'other-provider-value'))

    def test_altered_raw_provider_body_cannot_borrow_old_arm_pin(self):
        self.mutate_and_refuse(self.arm / 'episodes/00/custody/RESPONSE.bin', lambda b: b + b' ')

    def test_changed_original_answer_or_local_prediction_refused(self):
        for name in ('episodes/00/OUTPUT.bin', 'captures/fold00/baseline/FIRST_RESPONSE.bin',
                     'captures/fold00/baseline/predictions.json'):
            self.mutate_and_refuse(self.arm / name, lambda b: b.replace(b'1.0', b'2.0', 1))

    def test_cross_context_presentation_and_request_refused(self):
        other = (self.freeze / 'presentations/fold00/neural/OBSERVATION.json').read_bytes()
        self.mutate_and_refuse(self.freeze / 'presentations/fold00/baseline/OBSERVATION.json', lambda _: other)
        other = (self.arm / 'episodes/01/custody/REQUEST.bin').read_bytes()
        self.mutate_and_refuse(self.arm / 'episodes/00/custody/REQUEST.bin', lambda _: other)

    def test_missing_and_extra_episode_context_refused(self):
        directory = self.arm / 'episodes/39'
        moved = self.arm / 'missing-39'
        directory.rename(moved)
        try:
            with self.assertRaises(ValueError):
                self.admission()
        finally:
            moved.rename(directory)
        extra = self.arm / 'episodes/40'
        extra.mkdir()
        try:
            with self.assertRaises(ValueError):
                self.admission()
        finally:
            extra.rmdir()

    def test_reordered_inventory_and_self_reported_qualification_refused(self):
        self.mutate_and_refuse(self.arm / 'INVENTORY.json', lambda b: c.encode({**c.decode(b), 'captures': list(reversed(c.decode(b)['captures']))}))
        self.mutate_and_refuse(self.arm / 'ARM.json', lambda b: c.encode({**c.decode(b), 'remote_context_qualified': True}))

    def test_missing_raw_custody_not_replaced_by_closed_flag(self):
        path = self.arm / 'episodes/00/custody/HTTP.json'
        moved = self.arm / 'HTTP.missing'
        path.rename(moved)
        try:
            with self.assertRaises(ValueError):
                self.admission()
        finally:
            moved.rename(path)

    def test_bridge_refuses_policy_history_tools_refusal_and_second_answer(self):
        bridge = self.modules['bridge']
        prompt = self.prompt()
        request = bridge.request_body(prompt, **self.value['provider'])
        for mode in ('incomplete', 'refusal', 'tool', 'second', 'history', 'malformed'):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                bridge.completed(response_for(request, mode), prompt, **self.value['provider'])
        value = c.decode(response_for(request))
        for key, wrong in [('model', 'substitute'), ('truncation', 'auto'), ('tools', [{}]), ('max_output_tokens', 12)]:
            changed = copy.deepcopy(value)
            changed[key] = wrong
            with self.subTest(key=key), self.assertRaises(ValueError):
                bridge.completed(c.encode(changed), prompt, **self.value['provider'])

    def test_response_rows_must_be_complete_ordered_finite_and_bound(self):
        bridge = self.modules['bridge']
        prompt = self.prompt()
        good = c.decode(response_for(bridge.request_body(prompt, **self.value['provider'])))
        original = c.decode(good['output'][0]['content'][0]['text'])
        variants = [dict(original, request_id='0' * 64), dict(original, rows=original['rows'][:-1]),
                    dict(original, rows=list(reversed(original['rows']))),
                    dict(original, rows=[original['rows'][0]] * len(original['rows']))]
        for number in (True, -1, '1'):
            changed = copy.deepcopy(original)
            changed['rows'][0]['prediction'] = number
            variants.append(changed)
        for value in variants:
            with self.assertRaises(ValueError):
                bridge.answer(c.encode(value), prompt)

    def test_oversize_observation_refused_before_sender(self):
        calls = []
        with self.assertRaises(ValueError):
            self.modules['bridge'].exchange('x' * (c.OBS_CAP + 1), **self.value['provider'],
                     send_json=lambda body: calls.append(body), record=lambda receipt: None)
        self.assertEqual(calls, [])

    def test_one_frame_no_second_prompt_and_sink_failure_withholds_answer(self):
        bridge = self.modules['bridge']
        prompt = self.prompt().encode()
        frame = p.PREFIX.pack(len(prompt)) + prompt
        for incoming, sink in [(frame + frame, lambda _: None), (frame, lambda _: (_ for _ in ()).throw(ValueError('sink')))]:
            out = io.BytesIO()
            with self.assertRaises(ValueError):
                bridge.serve(io.BytesIO(incoming), out, **self.value['provider'],
                             send_json=response_for, record=sink)
            self.assertEqual(out.getvalue(), b'')

    def test_malformed_first_answer_retained_and_attempt_not_replaceable(self):
        output = self.root / 'failed-malformed'
        before = len(self.launches)
        with self.assertRaises(ValueError):
            self.run_fake(output, 'malformed')
        self.assertEqual(len(self.launches) - before, 1)
        raw = (output / 'episodes/00/custody/RESPONSE.bin').read_bytes()
        self.assertIn(b'invalid_first_answer', raw)
        self.assertTrue((output / 'FAILED.json').is_file())
        self.assertFalse((output / 'ARM.json').exists())
        with self.assertRaises(ValueError):
            self.run_fake(output, 'success')
        self.assertEqual((output / 'episodes/00/custody/RESPONSE.bin').read_bytes(), raw)

    def test_duplicate_provider_identity_stops_complete_arm(self):
        output = self.root / 'failed-duplicate'
        before = len(self.launches)
        with self.assertRaises(ValueError):
            self.run_fake(output, 'duplicate')
        self.assertEqual(len(self.launches) - before, 2)
        failure = c.decode((output / 'FAILED.json').read_bytes())
        self.assertEqual((failure['attempted'], failure['succeeded'], failure['unattempted']), (2, 1, 38))
        self.assertFalse((output / 'ARM.json').exists())

    def test_capacity_error_partial_overflow_and_timeout_preserve_first_failure(self):
        for mode in ('capacity', 'partial', 'overflow', 'timeout', 'incomplete', 'extra_stdout'):
            output = self.root / ('failed-' + mode)
            before = len(self.launches)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.run_fake(output, mode)
            self.assertEqual(len(self.launches) - before, 1)
            self.assertFalse((output / 'ARM.json').exists())
            failure = c.decode((output / 'FAILED.json').read_bytes())
            self.assertEqual(failure['unattempted'], 39)
            self.assertFalse(failure['automatic_retry'])
            http = c.decode((output / 'episodes/00/custody/HTTP.json').read_bytes())
            self.assertEqual((http['requests_attempted'], http['retries']), (1, 0))
            self.assertTrue((output / 'episodes/00/END.json').is_file())

    def test_attempt_metadata_cannot_replace_complete_source_selected_inventory(self):
        with self.assertRaises(ValueError):
            p.admit(self.freeze, self.contract_pin, self.arm, {'bytes': self.arm_pin['bytes'], 'sha256': '0' * 64},
                    self.source_sha, modules=self.modules)
        self.mutate_and_refuse(self.arm / 'collection/submission.json', lambda b: b + b' ')


def main():
    global SCRATCH
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch-root', required=True)
    parser.add_argument('--accounting-only', action='store_true')
    args = parser.parse_args()
    SCRATCH = c.ordinary(args.scratch_root)
    c.need(SCRATCH.is_dir() and not SCRATCH.is_relative_to(c.HERE.parents[4]), 'external_generated_scratch')
    with patch.object(socket, 'socket', blocked), patch.object(socket, 'create_connection', blocked), \
            patch.object(socket, 'getaddrinfo', blocked):
        suite = unittest.TestSuite()
        if not args.accounting_only:
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(EpisodeClockTests))
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(FixtureAccountingTests))
        if not args.accounting_only:
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(ProviderTests))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
