"""Generated viewer grading controls: no authentic inputs, Docker or scoring.

The actual process fixture runs only the unchanged original owner and a tiny
explicitly generated child. Generated root records test admission mechanics;
they do not claim to be the accepted historical collection or execution approval.
All fixture writes are cumulatively charged, including files later removed.
"""
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
PREFIX = Path('benchmarks/neural/NEURAL-034/implementations')
OWNER_REL = Path('authoring/glial-context-v1/ordinary-completion-v1/ownership')
PINS = {
    'process_owner.py': 'd1f594eaf2bdc688e84f95d27bd6a6d1778d8ac77379a41d8c7bf95f650f5ec6',
    'group_bootstrap.py': 'da5587bc02db3084aa78ea7d12fecc32097507ce982bef4adde6ee71155736b0',
    'trusted_controller.py': '6ad9e2e74fdf9ee9dbbf8e4626cd8c8161ab0c3d64b7da2a3bcd45d1f0d4bdaa',
    'host_budget.py': 'bcd6907fa8314a4e26a860ae4da994fecd04a29bdc4ca10d6283931ae0159291',
    'comparisons.py': 'eafbdaf31dd1317d5c5aedee9332c3d5562c6d23096aa3467cc0b0028ba264a7',
    'absence.py': 'dd3ba3d0f54fe717cbce0c772e9e83f6a97674124baace4d67d7f1bb94b0a1b4',
}


def compact(value):
    return (json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n').encode()


def load(name, path, expected=None):
    path = Path(path)
    body = path.read_bytes()
    if len(body) > 65536 or expected is not None and hashlib.sha256(body).hexdigest() != expected:
        raise ValueError('Bounded exact generated-control dependency')
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


class Writes:
    limit = 128 * 1024

    def __init__(self):
        self.total = 0
        self.reserved = 0
        self.original_owner_bytes = 0

    def charge(self, size):
        if type(size) is not int or size < 0 or self.total + self.reserved + size > self.limit:
            raise AssertionError('Generated cumulative fixture write ceiling')
        self.total += size

    def save(self, path, body, mode=0o400):
        self.charge(len(body))
        with path.open('xb') as stream:
            stream.write(body)
        path.chmod(mode)
        return {'path': str(path), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


class ViewerGradingControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repository = os.environ.get('NEURAL034_TEST_REPOSITORY')
        cls.repo = Path(repository).resolve() if repository else HERE.parents[4]
        cls.portable = cls.repo / PREFIX / 'neural034-portable'
        cls.temp = tempfile.TemporaryDirectory(prefix='generated-viewer-grade-')
        cls.root = Path(cls.temp.name).resolve()
        cls.writes = Writes()
        cls.old_run = sys.modules.get('run')
        cls.R = load('run', HERE / 'run.py')
        cls.C = load('generated_viewer_controller', HERE / 'controller.py')
        cls.K = load('generated_viewer_checker', HERE / 'check_result.py')
        cls.B = load('generated_original_budget', cls.portable /
                     'authoring/dmfc-timing/program-runner-v2/host_budget.py', PINS['host_budget.py'])
        cls.P = load('generated_original_comparisons', cls.repo / PREFIX /
                     'result-integrity-v2/check_result.py', PINS['comparisons.py'])
        cls.A = load('generated_original_absence', cls.portable /
                     'authoring/dmfc-timing/program-runner-v2/absence.py', PINS['absence.py'])
        cls.source_pins = {name: cls.R.pin((HERE / name).read_bytes())
                           for name in ('run.py', 'controller.py', 'check_result.py')}
        original_publish = cls.R.publish

        def charged_publish(path, body, budget, mode=0o400):
            # Charge before the attempted write, conservatively including refused writes.
            cls.writes.charge(len(body))
            return original_publish(path, body, budget, mode)

        cls.publication_patch = patch.object(cls.R, 'publish', charged_publish)
        cls.publication_patch.start()
        cls.ids = [[format(fold * 20 + index, '024x') for index in range(20)] for fold in range(7)]
        cls.value = {'schema_version': 1, 'probabilities': [
            {'fold': fold, 'query_id': query, 'probability': 0.5}
            for fold, ids in enumerate(cls.ids) for query in ids]}
        cls.corpus = compact(cls.value)
        cls.input_pin = cls.writes.save(cls.root / 'GENERATED-submission.json', cls.corpus)
        cls.out = cls.root / 'snapshot'; cls.out.mkdir(mode=0o700)
        budget = cls.B.HostBudget(cls.out, 2097152, 65536)
        old_umask = os.umask(0o077)
        try:
            cls.snapshot = cls.R.freeze_submission(cls.input_pin, cls.ids, cls.out, budget)
        finally:
            os.umask(old_umask)
        cls.serial = 0

    @classmethod
    def tearDownClass(cls):
        print(json.dumps({'generated_fixture_cumulative_bytes': cls.writes.total,
                          'fixture_limit_bytes': cls.writes.limit,
                          'original_owner_atomic_bytes': cls.writes.original_owner_bytes,
                          'source_pins': cls.source_pins,
                          'authentic_inputs': 0, 'docker_calls': 0, 'scientific_scores': 0}, sort_keys=True))
        cls.publication_patch.stop()
        if cls.old_run is None:
            sys.modules.pop('run', None)
        else:
            sys.modules['run'] = cls.old_run
        cls.temp.cleanup()

    def fresh(self, prefix):
        type(self).serial += 1
        path = self.root / (prefix + str(self.serial))
        path.mkdir(mode=0o700)
        return path

    def request(self, out=None):
        out = self.out if out is None else out
        return {'schema': 'neural034-viewer-grading-request/v1', 'output_root': str(out),
                'snapshot': self.snapshot, 'expected_ids': self.ids, 'artifact_limit_bytes': 2097152,
                'stage_seconds': 60, 'known_family_before': 3789.932040249051,
                'request_pin': self.R.pin(b'GENERATED request'),
                'collection_authority': {'path': str(self.root / 'GENERATED-authority.json'),
                                         **self.R.pin(b'GENERATED authority')},
                'controller': {'path': 'authoring/generated-viewer-grade/controller.py',
                               **self.R.pin(b'GENERATED controller')},
                'controller_argv': [sys.executable, '/GENERATED/controller.py']}

    def owner(self, request):
        return {'pid': 43101, 'pgid': 43101, 'token': 'a' * 32, 'seconds': 55.0,
                'controller': request['controller'], 'child_argv': request['controller_argv']}

    def reset_controller_files(self):
        for name in ('grade_attempted.json', 'controller-result.json'):
            (self.out / name).unlink(missing_ok=True)

    def test_complete_140_snapshot_and_restrictive_umask(self):
        cases = compact({'schema_version': 1, 'cases': [
            {'fold': row['fold'], 'query_id': row['query_id']} for row in self.value['probabilities']]})
        self.assertEqual(self.R.expected_ids(cases), self.ids)
        self.assertEqual(self.R.validate_probabilities(self.corpus, self.ids), self.value)
        self.assertEqual(self.R.validate_snapshot(self.request(), self.out), self.corpus)
        self.assertEqual(stat.S_IMODE((self.out / 'submission.json').stat().st_mode), 0o444)
        self.assertEqual(self.snapshot, {'path': 'submission.json', **self.R.pin(self.corpus)})

    def test_invalid_probability_roster_and_numbers(self):
        changes = [lambda v: v['probabilities'].pop(),
                   lambda v: v['probabilities'].append(v['probabilities'][0]),
                   lambda v: v['probabilities'].__setitem__(1, v['probabilities'][0]),
                   lambda v: v['probabilities'].__setitem__(slice(0, 2), v['probabilities'][1::-1]),
                   lambda v: v['probabilities'][0].update(fold=True),
                   lambda v: v['probabilities'][20].update(fold=0),
                   lambda v: v.update(schema_version=True)]
        for invalid in (True, False, -0.01, 1.01, '0.5', None):
            changes.append(lambda v, x=invalid: v['probabilities'][0].update(probability=x))
        for mutate in changes:
            value = copy.deepcopy(self.value); mutate(value)
            with self.subTest(value=str(value)[:70]), self.assertRaises(ValueError):
                self.R.validate_probabilities(compact(value), self.ids)
        for number in ('NaN', 'Infinity', '-Infinity'):
            with self.subTest(nonfinite=number), self.assertRaises(ValueError):
                self.R.validate_probabilities(self.corpus.replace(b'0.5', number.encode(), 1), self.ids)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.R.decode(b'{"schema_version":1,"schema_version":1}')

    def test_snapshot_pin_mode_and_overwrite_refusals(self):
        bad = copy.deepcopy(self.input_pin); bad['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'pinned'):
            self.R.freeze_submission(bad, self.ids, self.out, self.B.HostBudget(self.out))
        with self.assertRaises((ValueError, FileExistsError)):
            self.R.freeze_submission(self.input_pin, self.ids, self.out, self.B.HostBudget(self.out))
        snapshot = self.out / 'submission.json'; snapshot.chmod(0o400)
        try:
            with self.assertRaisesRegex(ValueError, 'publication mode'):
                self.R.validate_snapshot(self.request(), self.out)
        finally:
            snapshot.chmod(0o444)

    def test_capture_links_and_mid_read_mutation(self):
        folder = self.fresh('capture')
        item = folder / 'plain'; self.writes.save(item, b'original')
        linked = folder / 'hard'; os.link(item, linked)
        with self.assertRaisesRegex(ValueError, 'single-link'):
            self.R.capture(item)
        linked.unlink()
        sym = folder / 'sym'; os.symlink(item, sym)
        with self.assertRaisesRegex(ValueError, 'unlinked'):
            self.R.capture(sym)
        parent_link = self.root / 'linked-parent'; os.symlink(folder, parent_link)
        try:
            with self.assertRaisesRegex(ValueError, 'unlinked'):
                self.R.capture(parent_link / 'plain')
        finally:
            parent_link.unlink()
        original_fdopen = os.fdopen
        writes = self.writes

        class MutatingStream:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *unused): self.stream.close()
            def read(self, size):
                body = self.stream.read(size)
                writes.charge(8); item.chmod(0o600)
                with item.open('wb') as target: target.write(b'changed!')
                return body

        with patch.object(self.R.os, 'fdopen', lambda *a, **k: MutatingStream(original_fdopen(*a, **k))):
            with self.assertRaisesRegex(ValueError, 'Stable'):
                self.R.capture(item)

    def generated_collection(self):
        folder = self.fresh('authority')
        review = self.writes.save(folder / 'review.json', b'{"generated_fixture_only":true}\n')
        source = {'generated_source.py': self.R.pin(b'GENERATED source only')}
        sessions = {}
        for fold in range(7):
            episode = format(fold + 1, '032x')
            sessions[str(fold)] = {'boundary': {
                'schema': 'neural034-viewer-transport/v1', 'fold': fold, 'mode': self.R.MODE,
                'sandbox': 'macos', 'source': source, 'client_sha256': self.R.pin(b'GENERATED client')['sha256'],
                'python': '/GENERATED/framework/python', 'episode_id': episode,
                'workspace': '/GENERATED/removed-fold-' + str(fold),
                'limits': {'max_actions': 161, 'max_images': 140, 'max_output_bytes': 16777216,
                           'wall_seconds': 60}},
                'result': {'schema': 'neural034-viewer-transport-result/v1', 'fold': fold,
                    'status': 'complete_unscored', 'episode_id': episode, 'client_exit_code': 0,
                    'forced_stop': False, 'workspace_destroyed': True, 'process_group_cleanup': 'absent'}}
        receipt = self.writes.save(folder / 'transport.json', compact({
            'schema': 'neural034-viewer-transport-collection/v1', 'mode': self.R.MODE,
            'folds': 7, 'queries': 140, 'status': 'complete_unscored',
            'submission': self.R.pin(self.corpus), 'restricted_local_process_transport': True,
            'source': source, 'sessions': sessions}))
        collection = {'route': 'separately_admitted_closed_collection', 'submission': self.input_pin,
                      'transport_receipt': receipt, 'independent_review': review,
                      'execution_identity': 'GENERATED-owned-collection',
                      'source_bindings': source}
        authority = {'schema': 'neural034-closed-viewer-collection-authority/v1', 'reviewer': 'root',
                     'decision': 'accept_closed_combined_viewer_collection', 'task_id': 'NEURAL-034',
                     'mode': self.R.MODE, 'source_commit': self.R.SOURCE_COMMIT, 'folds': 7, 'queries': 140,
                     'all_participant_groups_closed': True, 'all_workspaces_removed': True,
                     'owner_controlled_collection_reviewed': True, 'protocol_only': False,
                     'status': 'complete_unscored', **{k: collection[k] for k in (
                         'submission', 'transport_receipt', 'independent_review',
                         'execution_identity', 'source_bindings')}}
        collection['authority'] = self.writes.save(folder / 'authority.json', compact(authority))
        return collection, authority

    def test_generated_admission_mechanics_do_not_replace_root_trust(self):
        collection, authority = self.generated_collection()
        self.assertEqual(self.R.admit_collection(collection), collection['authority'])
        self.assertEqual(self.R.closed_authority(authority, collection), authority)
        receipt = self.R.decode(self.R.checked(collection['transport_receipt']))
        changes = [lambda v: v['sessions'].pop('6'),
                   lambda v: v.update(source={'wrong_source': True}),
                   lambda v: v['sessions']['0']['boundary'].update(sandbox='protocol_only'),
                   lambda v: v['sessions']['0']['boundary'].update(fold=True),
                   lambda v: v['sessions']['0']['boundary'].update(client_sha256='0' * 64),
                   lambda v: v['sessions']['0']['boundary'].update(source={'wrong_source': True}),
                   lambda v: v['sessions']['0']['result'].update(fold=1),
                   lambda v: v['sessions']['0']['result'].update(client_exit_code=1),
                   lambda v: v['sessions']['0']['result'].update(workspace_destroyed=False),
                   lambda v: v['sessions']['0']['result'].update(process_group_cleanup='unverified'),
                   lambda v: v['sessions']['1']['boundary'].update(
                       workspace=v['sessions']['0']['boundary']['workspace'])]
        for index, mutate in enumerate(changes):
            value = copy.deepcopy(receipt); mutate(value)
            with self.subTest(receipt_mutation=index), self.assertRaises(ValueError):
                self.R.closed_receipt(value, collection)
        # An external root pin is checked BEFORE configured imports, not supplied by this shape check.
        with patch.object(self.R, 'package', side_effect=AssertionError('must not import source')):
            with self.assertRaisesRegex(ValueError, 'External exact root'):
                self.R.review_context(collection['authority']['path'], '0' * 64)
        bad = copy.deepcopy(collection); bad['authority']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'pinned'):
            self.R.admit_collection(bad)
        for key, value in [('reviewer', 'participant'), ('status', 'failed'), ('protocol_only', True),
                           ('source_commit', '0' * 40), ('all_participant_groups_closed', False),
                           ('all_workspaces_removed', False), ('owner_controlled_collection_reviewed', False),
                           ('queries', 139), ('execution_identity', 'other-run'),
                           ('source_bindings', {'other_source': True})]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.R.closed_authority(dict(authority, **{key: value}), collection)
        with self.assertRaises(ValueError):
            self.R.admit_collection({'route': 'self_asserted_complete'})
        # Generated files must never impersonate the accepted historical route.
        with self.assertRaises(ValueError):
            self.R.admit_collection({'route': 'retained_20261117', 'receipt': collection['transport_receipt'],
                                     'independent_review': collection['independent_review'],
                                     'submission': self.input_pin})

    def test_controller_owner_gates_precede_grade_intent(self):
        request = self.request(); original = self.owner(request)
        for field, value in [('pgid', 99), ('token', 'invalid'), ('seconds', 56),
                             ('child_argv', ['wrong']), ('controller', {'wrong': True})]:
            owner = dict(original, **{field: value})
            api = types.SimpleNamespace(HostBudget=self.B.HostBudget,
                owner=types.SimpleNamespace(expected=lambda _: (owner, [])),
                grader=types.SimpleNamespace(grade=lambda *a: self.fail('premature grading')))
            self.reset_controller_files()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.C.execute(api, request, self.out, pid=43102, pgid=43101, argv=request['controller_argv'])
            self.assertFalse((self.out / 'grade_attempted.json').exists())
        for pid, pgid in [(43101, 43101), (43102, 999), (True, 43101)]:
            api.owner.expected = lambda _: (original, [])
            with self.subTest(pid=pid, pgid=pgid), self.assertRaises(ValueError):
                self.C.execute(api, request, self.out, pid=pid, pgid=pgid, argv=request['controller_argv'])

    def test_controller_exactly_one_grade_and_preserved_failures(self):
        request = self.request(); owner = self.owner(request)
        base = {'status': 'scored', 'absence_verified': True, 'id_absent': True, 'name_absent': True,
                'submission_sha256': self.snapshot['sha256']}
        for mutation in ({}, {'absence_verified': False}, {'submission_sha256': '0' * 64}, {'status': 'failed'}):
            self.reset_controller_files(); called = []
            def grade(submission, output, budget):
                called.append((submission, output))
                self.assertTrue((self.out / 'grade_attempted.json').exists())
                return dict(base, **mutation)
            api = types.SimpleNamespace(HostBudget=self.B.HostBudget,
                owner=types.SimpleNamespace(expected=lambda _: (owner, [])),
                grader=types.SimpleNamespace(grade=grade,
                    recover_grade=lambda *a: self.fail('controller must not recover before group stop')))
            value = self.C.execute(api, request, self.out, pid=43102, pgid=43101,
                                   argv=request['controller_argv'])
            self.assertEqual(len(called), 1)
            self.assertEqual(value['status'], 'execution_failed_preserved' if mutation else 'scored')
            self.assertEqual(value, self.R.decode((self.out / 'controller-result.json').read_bytes()))
        self.reset_controller_files()

    def stub_owner_case(self, absence=True, token='a' * 32):
        out = self.fresh('outer'); request = self.request(out); owner = self.owner(request)
        events = []; proc = types.SimpleNamespace(returncode=None, poll=lambda: None)
        def launch(*unused):
            events.append('launch')
            self.writes.save(out / 'process_completion.json', compact({
                'token': token, 'returncode': 0, 'child_pid': 43102,
                'group_leader_waits_for_owner_stop': True}))
            self.writes.save(out / 'controller-result.json', compact({
                'status': 'scored', 'owner_token': owner['token'], 'pid': 43102, 'returncode': 0}))
            return proc
        def stop(*unused):
            events.append('stop'); proc.returncode = -9
            return {'absence_verified': absence}
        def recover(*unused):
            self.assertEqual(events, ['launch', 'stop']); events.append('recover')
            return {'absence_verified': True}
        api = types.SimpleNamespace(HostBudget=self.B.HostBudget,
            owner=types.SimpleNamespace(launch=launch, stop=stop, expected=lambda _: (owner, [])),
            grader=types.SimpleNamespace(recover_grade=recover))
        with patch.object(self.R, 'validate_snapshot', return_value=self.corpus):
            result = self.R.own_grade(api, request, out)
        self.assertEqual(self.R.decode((out / 'outer-result.json').read_bytes()), result)
        return result, events

    def test_outer_stops_before_recovery_and_refuses_unresolved_cleanup(self):
        result, events = self.stub_owner_case()
        self.assertEqual(events, ['launch', 'stop', 'recover'])
        self.assertTrue(result['all_owned_absent'])
        result, events = self.stub_owner_case(absence=False)
        self.assertEqual(events, ['launch', 'stop'])
        self.assertEqual(result['status'], 'execution_failed_preserved')
        self.assertFalse(result['all_owned_absent'])

    def test_outer_owner_mismatch_preserves_failure_receipt(self):
        result, events = self.stub_owner_case(token='b' * 32)
        self.assertEqual(events, ['launch', 'stop', 'recover'])
        self.assertEqual(result['status'], 'execution_failed_preserved')
        self.assertIn('finalization_error', result)

    def score(self):
        rows = [{'fold': fold, 'balanced_accuracy': (fold + 1) / 8, 'log_loss': (fold + 2) / 10}
                for fold in range(7)]
        primary = {key: math.fsum(row[key] for row in rows) / 7 for key in self.K.METRICS}
        refs = {name: {'balanced_accuracy': (index + 1) / 10, 'log_loss': (index + 3) / 11}
                for index, name in enumerate(self.P.COMPARATORS)}
        return {'status': 'scored', 'private_targets_decoded': True, 'candidate_program_replayed': False,
                'candidate_code_executed': False, 'full_contract_qualified': False,
                'scientific_success_threshold': None, 'scientific_success': None,
                'per_mouse': rows, 'co_primary_metrics': primary, 'score': dict(primary),
                'directions': dict(self.P.DIRECTIONS), 'reference_metrics': refs,
                'signed_candidate_minus_reference': {
                    name: {key: primary[key] - row[key] for key in self.K.METRICS}
                    for name, row in refs.items()}}

    def test_original_equal_mouse_and_all_six_reference_arithmetic(self):
        score = self.score(); observed = self.K.macro_score(score, self.P)
        self.assertEqual(observed['co_primary_metrics'], {'balanced_accuracy': 0.5, 'log_loss': 0.5})
        self.assertEqual(set(observed['reference_metrics']), set(self.P.COMPARATORS))
        self.assertEqual(observed['signed_candidate_minus_reference'], score['signed_candidate_minus_reference'])
        score['per_mouse'].reverse()
        self.assertEqual(self.K.macro_score(score, self.P)['per_mouse'], observed['per_mouse'])

    def test_metric_and_reference_tampering_is_refused(self):
        mutations = [lambda s: s['per_mouse'].pop(),
                     lambda s: s['per_mouse'][1].update(fold=0),
                     lambda s: s['per_mouse'][0].update(balanced_accuracy=True),
                     lambda s: s['per_mouse'][0].update(log_loss=float('nan')),
                     lambda s: s['co_primary_metrics'].update(log_loss=0.75),
                     lambda s: s['score'].update(log_loss=0.75),
                     lambda s: s.update(candidate_program_replayed=True),
                     lambda s: s.update(full_contract_qualified=True),
                     lambda s: s['directions'].update(log_loss='higher')]
        for name in self.P.COMPARATORS:
            mutations.extend([
                lambda s, n=name: s['reference_metrics'].pop(n),
                lambda s, n=name: s['signed_candidate_minus_reference'].pop(n),
                lambda s, n=name: s['signed_candidate_minus_reference'][n].update(log_loss=123),
                lambda s, n=name: s['reference_metrics'][n].update(balanced_accuracy=True)])
        for index, mutate in enumerate(mutations):
            score = self.score(); mutate(score)
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.K.macro_score(score, self.P)

    def checker_fixture(self):
        """Generated saved journals in memory; placeholders serve directory checks.

        This tests the declared metadata-consistency checker, not Docker config
        attestation. No real former run files or target/reference bodies appear.
        """
        root = self.fresh('checker'); request = self.request(root); owner = self.owner(request)
        grade_root = root / 'grader'; operator = grade_root / 'operator'; operator.mkdir(parents=True)
        for name in self.K.OPERATOR_FILES:
            self.writes.save(operator / name, b'')
        self.writes.save(grade_root / 'score.json', b'')
        score = self.score(); score_body = compact(score)
        name, identity = 'neural034-score-' + 'd' * 16, 'e' * 64
        missing = lambda resource: {'returncode': 1, 'stdout': '',
            'stderr': 'Error response from daemon: No such container: ' + resource}
        cleanup = {'name': name, 'immutable_id': identity, 'absence_verified': True, 'absent': True,
                   'id_absent': True, 'name_absent': True, 'create_extent_unknown': False,
                   'id_inspect': missing(identity), 'name_inspect': missing(name)}
        grade = {'status': 'scored', 'container': name, 'immutable_id': identity,
                 'absence_verified': True, 'id_absent': True, 'name_absent': True,
                 'score_sha256': self.R.pin(score_body)['sha256'],
                 'submission_sha256': request['snapshot']['sha256'], 'private_targets_decoded': True,
                 'same_shared_controller_group': True, 'no_new_host_process_group': True}
        controller = {'schema': 'neural034-viewer-grading-controller/v1', 'status': 'scored',
            'request': request['request_pin'], 'controller': request['controller'], 'owner_token': owner['token'],
            'pid': 43102, 'pgid': owner['pid'], 'snapshot': request['snapshot'],
            'collection_authority': request['collection_authority'], 'grade_attempted': True,
            'grade': grade, 'returncode': 0, 'error': None}
        completion = {'token': owner['token'], 'returncode': 0, 'child_pid': 43102,
                      'group_leader_waits_for_owner_stop': True}
        controller_pin = self.R.pin(compact(controller)); completion_pin = self.R.pin(compact(completion))
        outer = {'schema': 'neural034-viewer-grading-result/v1', 'status': 'viewer_scored',
            'request': request['request_pin'], 'snapshot': request['snapshot'],
            'collection_authority': request['collection_authority'], 'controller_result': controller_pin,
            'process_completion': completion_pin, 'controller_direct_handle_reaped': True,
            'all_owned_absent': True, 'private_grade_dispatched': True, 'scientific_qualification': False,
            'provider_qualification': False, 'wall_seconds_before_receipt': 0.5,
            'costs': {'stage_allowance_seconds': 60, 'prior_costs_reset': False,
                      'known_family_before': request['known_family_before'], 'historical_lifetime_complete': False},
            'process_cleanup': {'status': 'owned_group_absent', 'absence_verified': True,
                'pid': owner['pid'], 'pgid': owner['pid'], 'bootstrap_returncode': -9, 'stderr': '',
                'stdout': compact({'status': 'scored', 'returncode': 0,
                                   'controller_result': controller_pin}).decode()},
            'grader_cleanup': {'container': name, 'absence_verified': True,
                               'create_extent_unknown': False, 'evidence': cleanup}}
        owned = {'container': name, 'intent_before_create': True,
                 'mounts': {'/submission/probabilities.json': str(root / 'submission.json')}}
        create = {'returncode': 0, 'stdout': identity, 'stderr': ''}
        initial = {'Id': identity, 'Name': '/' + name, 'Image': 'GENERATED-image-not-attested',
                   'Config': {'GENERATED_fixture_only': True},
                   'State': {'Status': 'created', 'Running': False, 'Pid': 0}}
        terminal = copy.deepcopy(initial)
        terminal['State'] = {'Status': 'exited', 'Running': False, 'Pid': 0, 'ExitCode': 0, 'OOMKilled': False}
        docs = {
            root / 'outer-result.json': outer, root / 'process_owner.json': owner,
            root / 'process_ready.json': {'token': owner['token'], 'pid': owner['pid'], 'pgid': owner['pid'],
                                         'python_initialized_before_identity_snapshot': True},
            root / 'process_gate.json': {'token': owner['token'], 'activate': True},
            root / 'controller-result.json': controller, root / 'process_completion.json': completion,
            root / 'grade_attempted.json': {'schema': 'neural034-viewer-grade-intent/v1',
                'request': request['request_pin'], 'controller': request['controller'],
                'owner_token': owner['token'], 'snapshot': request['snapshot'], 'grade_output': str(grade_root)},
            operator / 'ownership.json': owned,
            operator / 'create_attempt.json': {'container': name, 'create_attempted': True,
                                               'ownership_pin': self.R.pin(compact(owned))},
            operator / 'create_result.json': {'container': name, 'create_returned': True, 'result': create},
            operator / 'child_receipt.json': {'status': 'scored', 'container': name, 'created_id': identity,
                'create': create, 'precreate_absence': missing(name), 'candidate_code_executed': False,
                'result': score, 'worker': {'returncode': 0, 'stdout': score_body.decode(), 'stderr': ''},
                'cleanup': cleanup},
            operator / 'child_ownership.json': {'pid': 43102, 'process_group': owner['pid'],
                'container': name, 'journal_before_child_resource_dispatch': True},
            operator / 'outer_intent.json': {'container': name, 'same_shared_controller_group': True,
                'bridge_source': 'ordinary-completion-v1/grader/grade_bridge.py',
                'no_new_host_process_group': True, 'grader_retained_cap_bytes': 1813840},
            operator / 'invocation.json': {'submission': self.R.pin(self.corpus),
                'producer_stopped_attested': False,
                'scope': 'Static numerical-file scoring, not candidate-program replay.'},
            operator / 'inspection.json': initial, operator / 'terminal_inspection.json': terminal,
            operator / 'cleanup-00.json': cleanup, operator / 'cleanup-01.json': cleanup,
            grade_root / 'score.json': score,
        }
        api = types.SimpleNamespace(owner=types.SimpleNamespace(expected=lambda _: (owner, [])),
                                    recovery=types.SimpleNamespace(absence=self.A.absence))
        return root, request, api, docs

    def test_full_generated_saved_checker_and_identity_cleanup_mutations(self):
        root, request, api, baseline = self.checker_fixture()
        def check(docs):
            def capture(path, cap=262144):
                value = compact(docs[Path(path)])
                self.assertLessEqual(len(value), cap)
                return value
            with patch.object(self.R, 'capture', capture), \
                 patch.object(self.R, 'validate_snapshot', return_value=self.corpus), \
                 patch.object(self.R, 'load_comparisons', return_value=self.P):
                return self.K.check(root, request, api,
                    historical_viewer_authority=request['collection_authority'])
        result = check(baseline)
        self.assertEqual(result['status'], 'consistent_closed_viewer_score')
        self.assertEqual((result['cases'], result['mice'], result['cleanup_receipts']), (140, 7, 2))
        self.assertFalse(result['runtime_qualified'])
        self.assertFalse(result['scientific_qualification'])
        operator = root / 'grader/operator'
        mutations = [
            lambda d: d[operator / 'child_ownership.json'].update(pid=999),
            lambda d: d[operator / 'terminal_inspection.json'].update(Id='f' * 64),
            lambda d: d[operator / 'cleanup-01.json']['id_inspect'].update(stderr='permission denied'),
            lambda d: d[operator / 'cleanup-00.json']['name_inspect'].update(
                stderr='Error response from daemon: No such container: different-name'),
            lambda d: d[operator / 'child_receipt.json']['worker'].update(returncode=1),
            lambda d: d[root / 'outer-result.json'].update(all_owned_absent=False),
        ]
        for index, mutate in enumerate(mutations):
            docs = copy.deepcopy(baseline); mutate(docs)
            with self.subTest(index=index), self.assertRaises(ValueError):
                check(docs)

    def actual_owner_fixture(self, force_stop_error=False):
        stage = self.fresh('stage'); owned = stage / OWNER_REL; owned.mkdir(parents=True, mode=0o700)
        for name in ('process_owner.py', 'group_bootstrap.py', 'trusted_controller.py'):
            body = (self.portable / OWNER_REL / name).read_bytes()
            self.assertEqual(hashlib.sha256(body).hexdigest(), PINS[name])
            self.writes.save(owned / name, body)
        control = stage / 'authoring/generated-viewer-grade'; control.mkdir(parents=True, mode=0o700)
        source = b'''"""GENERATED grader only; actual owner and production controller."""
import hashlib,importlib.util,json,os,sys,types
from pathlib import Path
p=Path(sys.argv[1]); package=Path(sys.argv[2]); request=json.loads((p/'GENERATED-request.json').read_text())
for name,pin in request.pop('generated_source_pins').items():
    body=(package/name).read_bytes()
    assert len(body)==pin['bytes'] and hashlib.sha256(body).hexdigest()==pin['sha256']
sys.path[:0]=[str(package),sys.argv[4]]
import controller,process_owner
spec=importlib.util.spec_from_file_location('generated_budget',sys.argv[3]); budget=importlib.util.module_from_spec(spec);spec.loader.exec_module(budget)
def grade(submission,out,host):
    out.mkdir(mode=0o700)
    return {'status':'scored','absence_verified':True,'id_absent':True,'name_absent':True,
            'submission_sha256':request['snapshot']['sha256']}
api=types.SimpleNamespace(owner=process_owner,HostBudget=budget.HostBudget,grader=types.SimpleNamespace(grade=grade))
result=controller.execute(api,request,p)
print(json.dumps({'status':result['status'],'returncode':result['returncode'],
 'controller_result':controller.shared.pin((p/'controller-result.json').read_bytes())}),flush=True)
raise SystemExit(result['returncode'])
'''
        descriptor = self.writes.save(control / 'controller.py', source)
        descriptor['path'] = (control / 'controller.py').relative_to(stage).as_posix()
        out = self.fresh('actual-owner'); request = self.request(out)
        request['snapshot'] = self.R.freeze_submission(self.input_pin, self.ids, out,
                                                       self.B.HostBudget(out, 2097152, 65536))
        request['controller'] = descriptor
        request['controller_argv'] = [sys.executable, str(control / 'controller.py'), str(out), str(HERE),
            str(self.portable / 'authoring/dmfc-timing/program-runner-v2/host_budget.py'), str(owned)]
        self.writes.save(out / 'GENERATED-request.json', compact(dict(request, generated_source_pins=self.source_pins)))
        old_trusted = sys.modules.get('trusted_controller')
        trusted = load('trusted_controller', owned / 'trusted_controller.py', PINS['trusted_controller.py'])
        owner = load('generated_viewer_real_owner', owned / 'process_owner.py', PINS['process_owner.py'])
        recoveries = []
        retained = []
        stop_calls = []
        original_launch, original_stop = owner.launch, owner.stop
        def launch(*args):
            proc = original_launch(*args)
            retained.append(proc)
            return proc
        def stop(*args):
            stop_calls.append(True)
            if force_stop_error and len(stop_calls) == 1:
                self.assertEqual(len(retained), 1)
                self.assertTrue(owner.group_exists(retained[0].pid))
                raise RuntimeError('GENERATED first stop refusal while exact owned group is alive')
            return original_stop(*args)
        def recover(*unused):
            identity, _ = owner.expected(out)
            self.assertFalse(owner.group_exists(identity['pid']))
            recoveries.append(identity['pid'])
            return {'absence_verified': True, 'generated_recovery_only': True}
        api = types.SimpleNamespace(owner=types.SimpleNamespace(launch=launch, stop=stop, expected=owner.expected),
                                    HostBudget=self.B.HostBudget,
                                    grader=types.SimpleNamespace(recover_grade=recover))
        # Seven once-written original-owner/production-controller records are bounded before launch.
        reserve = 20000
        self.assertLessEqual(self.writes.total + reserve, self.writes.limit)
        self.writes.reserved += reserve
        result = None
        try:
            result = self.R.own_grade(api, request, out)
            self.assertEqual(len(retained), 1)
            if force_stop_error:
                self.assertEqual(result['status'], 'execution_failed_preserved')
                self.assertFalse(result['all_owned_absent'])
                self.assertFalse(result['controller_direct_handle_reaped'])
                self.assertIsNone(result['private_grade_dispatched'])
                self.assertTrue(result['grader_cleanup']['not_attempted_before_group_absence'])
                self.assertEqual(recoveries, [])
                self.assertTrue(owner.group_exists(retained[0].pid))
                self.assertIsNone(retained[0].returncode)
                self.assertEqual(self.R.decode((out / 'outer-result.json').read_bytes()), result)
            else:
                self.assertEqual(result['status'], 'viewer_scored')
                self.assertTrue(result['all_owned_absent'])
                self.assertEqual(len(recoveries), 1)
                self.assertEqual(result['process_cleanup']['stderr'], '')
                self.assertTrue(result['private_grade_dispatched'])
                self.assertNotEqual(owner.read(out / 'process_completion.json')['child_pid'], recoveries[0])
        finally:
            try:
                if result is None or not result.get('all_owned_absent'):
                    proc = retained[0] if retained else None
                    closed = original_stop(out, time.monotonic() + 3, proc)
                    self.assertTrue(closed['absence_verified'])
                    if proc is not None:
                        self.assertIsNotNone(proc.returncode)
                        self.assertFalse(owner.group_exists(proc.pid))
                    else:
                        self.assertEqual(closed['status'], 'never_activated')
            finally:
                self.writes.reserved -= reserve
                files = [out / name for name in ('process_intent.json', 'process_ready.json', 'process_owner.json',
                         'process_gate.json', 'process_completion.json', 'grade_attempted.json', 'controller-result.json')]
                produced = sum(path.stat().st_size for path in files if path.exists())
                try:
                    self.assertLessEqual(produced, reserve)
                    self.writes.charge(produced); self.writes.original_owner_bytes += produced
                finally:
                    if old_trusted is None: sys.modules.pop('trusted_controller', None)
                    else: sys.modules['trusted_controller'] = old_trusted

    def test_actual_original_owner_through_production_controller(self):
        self.actual_owner_fixture()

    def test_actual_owner_failed_stop_fallback_reaps_retained_handle(self):
        self.actual_owner_fixture(force_stop_error=True)


if __name__ == '__main__':
    unittest.main()
