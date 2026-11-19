"""Generated-only controls for the single executed-author-reference entry.

The production entry functions execute. Native provider, store, numerical
collection/recovery and whole-tree authentication are explicit generated doubles.
No programme, original store, native process or scientific runtime is executed.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time
import types
import unittest
from unittest import mock

SOURCE_BYTES = 17979
SOURCE_SHA = 'f784cc450053c21bc6281a4b02f1b8e8a190cb6bf3bea68c2418369375b54ef2'
METHODS = [
    'test01_disabled_and_fixed_protocol_admission',
    'test02_exact_author_and_empty_assistance_manifest_guards',
    'test03_actual_orchestration_and_complete_collection_join',
    'test04_failure_propagation_and_resource_closure',
    'test05_actual_entry_publication_collision_and_failure_receipts',
]
LIMITS = {'wall_seconds': 25, 'source_read_bytes': 65536,
          'fixture_write_bytes': 32768, 'fixture_read_bytes': 32768,
          'log_bytes': 16384, 'result_bytes': 16384}
ROOT = A = None
DEADLINE = None
TIMEOUT = False
SOURCE_READ = FIXTURE_WRITTEN = FIXTURE_READ = 0
FIXTURE_ROWS = []
FIXTURE_UNCERTAIN = False
RESULT = None
CHECKS = []
SCENARIO_COUNT = 0


def need(ok, message):
    if not ok:
        raise ValueError(message)


def clock_check():
    if TIMEOUT or DEADLINE is None or time.monotonic() >= DEADLINE:
        raise TimeoutError('generated campaign deadline')


def alarm(signum, frame):
    global TIMEOUT
    TIMEOUT = True
    raise TimeoutError('generated campaign alarm')


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def ordinary_parents(path):
    need(path.is_absolute() and str(path) == os.path.normpath(str(path)), 'canonical absolute path')
    for parent in path.parents:
        need(stat.S_ISDIR(parent.lstat().st_mode), 'ordinary parent')


def source_read(path, cap, expected=None):
    global SOURCE_READ
    p = Path(path)
    ordinary_parents(p)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        stamp = lambda x: (x.st_dev, x.st_ino, x.st_mode, x.st_nlink,
                           x.st_size, x.st_mtime_ns, x.st_ctime_ns)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= cap, 'bounded ordinary source')
        if expected:
            need(before.st_size == expected['bytes'], 'source extent')
        need(SOURCE_READ + before.st_size + 1 <= LIMITS['source_read_bytes'], 'source read reservation')
        body = bytearray()
        while len(body) <= before.st_size:
            part = os.read(fd, min(65536, before.st_size + 1 - len(body)))
            SOURCE_READ += len(part)
            if not part:
                break
            body.extend(part)
        need(stamp(before) == stamp(os.fstat(fd)) == stamp(p.lstat())
             and len(body) == before.st_size, 'stable complete source')
        body = bytes(body)
        if expected:
            need(digest(body) == expected['sha256'], 'source hash')
        return body
    finally:
        os.close(fd)


def write_fixture(path, body):
    global FIXTURE_WRITTEN, FIXTURE_UNCERTAIN
    need(type(body) is bytes and len(body) <= 8192, 'small generated fixture')
    need(ROOT in Path(path).parents, 'fixture under selected output root')
    need(FIXTURE_WRITTEN + len(body) <= LIMITS['fixture_write_bytes'], 'cumulative fixture write stop')
    FIXTURE_WRITTEN += len(body)
    FIXTURE_ROWS.append({'path': str(path), 'bytes': len(body), 'sha256': digest(body)})
    fd = None
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        at = 0
        while at < len(body):
            count = os.write(fd, body[at:])
            need(count > 0, 'complete fixture publication')
            at += count
        os.fsync(fd)
    except BaseException:
        FIXTURE_UNCERTAIN = True
        raise
    finally:
        if fd is not None:
            os.close(fd)


def read_fixture(path, cap=8192):
    global FIXTURE_READ
    p = Path(path)
    need(ROOT in p.parents, 'only generated fixture read')
    st = p.lstat()
    need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size <= cap, 'bounded fixture')
    need(FIXTURE_READ + st.st_size + 1 <= LIMITS['fixture_read_bytes'], 'fixture read reservation')
    with p.open('rb') as stream:
        body = stream.read(st.st_size + 1)
    FIXTURE_READ += len(body)
    need(len(body) == st.st_size, 'complete fixture EOF')
    return body


def count_entry_publication(path, body):
    """Production publish uses this instrumented file wrapper, not a new publisher."""
    global FIXTURE_WRITTEN
    need(type(body) is bytes and len(body) <= 8192, 'bounded actual entry receipt')
    need(FIXTURE_WRITTEN + len(body) <= LIMITS['fixture_write_bytes'], 'cumulative entry receipt stop')
    FIXTURE_WRITTEN += len(body)
    FIXTURE_ROWS.append({'path': str(path), 'bytes': len(body), 'sha256': digest(body)})


class PublishedStream:
    def __init__(self, path, actual):
        self.path, self.actual = path, actual

    def __enter__(self):
        self.actual.__enter__()
        return self

    def __exit__(self, *args):
        return self.actual.__exit__(*args)

    def write(self, body):
        global FIXTURE_UNCERTAIN
        count_entry_publication(self.path, body)
        try:
            return self.actual.write(body)
        except BaseException:
            FIXTURE_UNCERTAIN = True
            raise

    def flush(self):
        return self.actual.flush()

    def fileno(self):
        return self.actual.fileno()


class Fixture:
    """Finite generated protocol and actor doubles; no real provider implementation."""
    def __init__(self, name):
        global SCENARIO_COUNT
        clock_check()
        SCENARIO_COUNT += 1
        need(SCENARIO_COUNT <= 32, 'finite generated scenario count')
        self.base = ROOT / 'fixtures' / name
        self.base.mkdir(mode=0o700)
        for leaf in ('task', 'store', 'runtime', 'candidate', 'assistance'):
            (self.base / leaf).mkdir(mode=0o700)
        self.events = []
        self.closed = []
        self.failure = None
        self.before_collect_return = None
        self.collection_delta = {}
        self.tree_calls = []
        self.native = self.reader = None
        self.native_admission = {
            'qualification_sha256': 'd' * 64,
            'admitted_until_unix': 10000, 'generated_boundary_only': True,
        }
        self.config = {
            'condition': 'paper_data_author_code', 'mode': 'exec_reset_bwrap_v1',
            'provider_source_sha256': 'c' * 64, 'store_sha256': 'e' * 64,
            'schedule_sha256': 'f' * 64, 'candidate_sha256': 'b' * 64,
            'caps': {'max_jobs': 42, 'max_requests': 5685,
                     'working_bytes': 1048576, 'run_seconds': 10},
        }
        for kind in ('runtime', 'candidate', 'assistance'):
            self.config[kind] = {'root': str(self.base / kind),
                                 'manifest': str(self.base / (kind + '.json')),
                                 'manifest_sha256': 'a' * 64}
        self.p = {
            'schema': 'language-original-author-reference-protocol/v1',
            'selected_for_execution': True, 'role': 'executed_author_reference',
            'entry_sha256': SOURCE_SHA, 'task_home': str(self.base / 'task'),
            'store_root': str(self.base / 'store'), 'store_sha256': 'e' * 64,
            'schedule_sha256': 'f' * 64,
            'source_support_sha256': '3d2d46bbc6534b282f97d29c51b1961c8d284cf7a9894839fb851550b7549e37',
            'output_root': str(self.base / 'operation'),
            'provider_config': self.config, 'provider_admission': self.native_admission,
            'limits': {'working_bytes': 1048576, 'cache_working_bytes': 1048576, 'wall_seconds': 2},
            'store_read_limit': 1048576, 'store_working_limit': 1048576,
            'extra_read_limit': 1048576, 'reference_working_limit': 268435456,
            'preflight_tree_read_limit': 1048576, 'output_limit': 8192,
            'wall_seconds': 60, 'numpy_version': '1.24.3',
            'operator_joint_admission_bytes': 536870912,
            'external_hard_deadline_required': True,
            'qualification_sha256': 'd' * 64,
        }
        self.product = {
            'schema': 'language-executed-selected-product/v1',
            'role': 'executed_author_reference', 'information_condition': None,
            'generated_boundary_only': True,
        }
        self.collection = {'jobs': 42, 'software_callbacks': 5685,
                           'provider': {'admission': copy.deepcopy(self.native_admission)}}
        self.pin = {'bytes': 123, 'sha256': '1' * 64}
        self.provider = types.SimpleNamespace(
            config_snapshot=lambda value: copy.deepcopy(value),
            admission_snapshot=lambda config, admission: copy.deepcopy(admission),
            identity=lambda: 'c' * 64,
            NativeProvider=self.new_native,
            LinuxBackend=types.SimpleNamespace(require_platform=lambda: self.events.append('platform-double')),
        )
        self.readers = types.SimpleNamespace(StoreReader=self.new_reader)
        self.e = types.SimpleNamespace(
            np=types.SimpleNamespace(__version__='1.24.3'),
            limits_snapshot=lambda value: copy.deepcopy(value),
            J=types.SimpleNamespace(make_run=self.make_run),
            collect=self.collect, close_owned=self.close_owned,
        )
        outer = self
        class Meter:
            def __init__(self, limit):
                self.limit, self.used = limit, 0
        def owned_bytes(path, expected, cap, meter):
            raw = read_fixture(path, cap)
            need(len(raw) == expected['bytes'] and digest(raw) == expected['sha256'],
                 'generated manifest descriptor')
            meter.used += len(raw)
            need(meter.used <= meter.limit, 'generated metadata meter')
            return raw
        self.reference = types.SimpleNamespace(
            Meter=Meter, owned_bytes=owned_bytes, parse=json.loads,
            recover_executed=self.recover, snapshot=lambda x: copy.deepcopy(x),
        )
        def preflight(one, provider, manifests):
            outer.events.append('tree-authentication-double')
            outer.tree_calls.append(copy.deepcopy((one, manifests)))
            return 850
        self.pairing = types.SimpleNamespace(file_records=lambda rows: list(rows),
                                             preflight_trees=preflight)
        self.manifest_number = 0
        self.set_manifests()

    def set_manifests(self, candidate=None, assistance=None, condition='paper_data_author_code'):
        self.manifest_number += 1
        if candidate is None:
            candidate = [{'path': 'candidate.py', 'mode': 0o444, 'bytes': 850,
                          'sha256': '7e806fb885dbba39bb6a4424134374e0d9dc9b405efe31b3c13ee2c517573bbb'}]
        if assistance is None:
            assistance = []
        for kind, files in (('candidate', candidate), ('assistance', assistance)):
            body = canonical({'schema': 'language-frozen-public-tree/v1',
                              'kind': kind, 'condition': condition, 'directories': [], 'files': files})
            path = self.base / (kind + '-' + str(self.manifest_number) + '.json')
            write_fixture(path, body)
            self.config[kind].update(manifest=str(path), manifest_sha256=digest(body))
        self.p['provider_config'] = self.config

    def admission(self, p=None):
        p = self.p if p is None else p
        return {'schema': 'language-original-author-reference-admission/v1',
                'protocol_sha256': digest(canonical(p)), 'entry_sha256': SOURCE_SHA,
                'root_admission_id': 'generated-no-original-authority',
                'expires_unix': 1060, 'wall_seconds': p['wall_seconds']}

    def throw(self, step):
        if self.failure == step:
            raise RuntimeError('generated failure at ' + step)

    def new_native(self, config, admission, *, evidence_root):
        self.events.append('native')
        self.native_args = copy.deepcopy((config, admission, str(evidence_root)))
        self.throw('native')
        self.native = types.SimpleNamespace(kind='native')
        return self.native

    def new_reader(self, root, **kwargs):
        self.events.append('reader')
        self.reader_args = copy.deepcopy((root, kwargs))
        self.throw('reader')
        self.reader = types.SimpleNamespace(kind='reader')
        return self.reader

    def make_run(self, **kwargs):
        self.events.append('make_run')
        self.run_args = copy.deepcopy(kwargs)
        self.throw('make_run')
        self.run = {'generated_run': True, **kwargs}
        return self.run

    def close_owned(self, native, reader):
        self.events.append('close_owned')
        self.closed.append((native, reader))

    def collect(self, reader, native, run, destination, *, limits):
        self.events.append('collect')
        self.collect_args = (reader, native, run, str(destination), copy.deepcopy(limits))
        # The maintained collector owns both actors on return and failure.
        self.close_owned(native, reader)
        self.throw('collect')
        if self.before_collect_return:
            self.before_collect_return()
        value = copy.deepcopy(self.collection)
        value.update(copy.deepcopy(self.collection_delta))
        return value, copy.deepcopy(self.pin)

    def recover(self, e, readers, run, collection, pin, role, config, **kwargs):
        self.events.append('recover')
        self.recover_args = (e, readers, copy.deepcopy(run), copy.deepcopy(collection),
                             copy.deepcopy(pin), role, copy.deepcopy(config), copy.deepcopy(kwargs))
        self.throw('recover')
        if self.failure == 'recovery_collision':
            raise ValueError('Fresh original recovery receipt required; preserve prior attempts')
        return copy.deepcopy(self.product)

    def live(self):
        clock_check()
        self.events.append('live')
        if self.failure == 'live_after_collection' and 'collect' in self.events:
            raise RuntimeError('generated deadline after collection')

    def execute(self):
        return A._execute_one(self.p, self.config, self.reference, self.e,
                              self.readers, self.provider, Path(self.p['output_root']), self.live)

    def run_entry(self, fail_fsync=False):
        original_open = Path.open
        fixture = self
        def intercepted_open(path, mode='r', *args, **kwargs):
            actual = original_open(path, mode, *args, **kwargs)
            if mode == 'xb' and path.parent == Path(fixture.p['output_root']):
                return PublishedStream(path, actual)
            return actual
        def self_auth(path, expected, cap):
            need(str(path) == A.__file__ and expected == {'bytes': SOURCE_BYTES, 'sha256': SOURCE_SHA}
                 and cap == 65536, 'only authenticated entry self-read is doubled')
            self.events.append('entry-self-auth-double')
            return b''
        proxy = types.SimpleNamespace(**vars(os))
        if fail_fsync:
            def failed_fsync(fd):
                self.events.append('injected-late-fsync')
                raise OSError('generated late fsync failure')
            proxy.fsync = failed_fsync
        with mock.patch.object(A, 'os', proxy), \
             mock.patch.object(A, 'read_pinned', self_auth), \
             mock.patch.object(A, 'load_maintained', return_value=(
                 self.pairing, self.reference, self.e, self.readers, self.provider)), \
             mock.patch.object(A.time, 'time', return_value=1000), \
             mock.patch.object(Path, 'open', intercepted_open):
            return A.run_original(self.p, self.admission(), SOURCE_SHA)


class AuthorReferenceControls(unittest.TestCase):
    def setUp(self):
        clock_check()

    def mark(self, name):
        CHECKS.append(name)

    def test01_disabled_and_fixed_protocol_admission(self):
        f = Fixture('protocol')
        p, config = A.validate_protocol(f.p, f.admission(), SOURCE_SHA, f.e, f.provider, now=1000)
        self.assertEqual(p, f.p)
        self.assertEqual(config, f.config)
        for role, selected in (('executed_author_reference', False),
                               ('paper_only', True), ('paper_data_author_code', True)):
            q = dict(f.p, role=role, selected_for_execution=selected)
            with mock.patch.object(A, 'load_maintained', side_effect=AssertionError('must not load')), \
                 mock.patch.object(A, 'read_pinned', side_effect=AssertionError('must not read')):
                with self.assertRaisesRegex(ValueError, 'unselected'):
                    A.run_original(q, f.admission(q), SOURCE_SHA)
        mutations = (
            ('role', lambda q: q.update(role='participant')),
            ('extra_programme', lambda q: q.update(programme='arbitrary.py')),
            ('support', lambda q: q.update(source_support_sha256='0' * 64)),
            ('runtime', lambda q: q.update(numpy_version='2.0.0')),
            ('jobs', lambda q: q['provider_config']['caps'].update(max_jobs=41)),
            ('callbacks', lambda q: q['provider_config']['caps'].update(max_requests=5684)),
            ('condition', lambda q: q['provider_config'].update(condition='paper_only')),
            ('provider', lambda q: q['provider_config'].update(provider_source_sha256='0' * 64)),
            ('root_overlap', lambda q: q.update(output_root=q['store_root'])),
            ('joint_budget', lambda q: q.update(operator_joint_admission_bytes=1)),
            ('deadline', lambda q: q.update(external_hard_deadline_required=False)),
        )
        for name, mutation in mutations:
            with self.subTest(name=name):
                q = copy.deepcopy(f.p)
                mutation(q)
                with self.assertRaises(ValueError):
                    A.validate_protocol(q, f.admission(q), SOURCE_SHA, f.e, f.provider, now=1000)
        for key, value in (('protocol_sha256', '0' * 64), ('entry_sha256', '0' * 64),
                           ('expires_unix', 1059)):
            q = f.admission()
            q[key] = value
            with self.assertRaises(ValueError):
                A.validate_protocol(f.p, q, SOURCE_SHA, f.e, f.provider, now=1000)
        for path in (str(f.base) + '/task/../store',
                     str(f.base) + '//store', str(f.base) + '/store/'):
            with self.assertRaisesRegex(ValueError, 'Canonical absolute spelling'):
                A.ordinary(path)
        self.assertFalse(f.events)
        self.mark('disabled before source loading; fixed role/programme/dependencies/full counts/custody/deadline')

    def test02_exact_author_and_empty_assistance_manifest_guards(self):
        f = Fixture('trees')
        value = A.authenticate_author_trees(f.p, f.config, f.pairing, f.reference, f.provider)
        self.assertEqual(value['tree_read_bytes'], 850)
        self.assertGreater(value['manifest_read_bytes'], 0)
        self.assertEqual(len(f.tree_calls), 1)
        one, manifests = f.tree_calls[0]
        self.assertEqual(one['roles'], [{'role': 'executed_author_reference', 'config': f.config}])
        expected = [{'path': 'candidate.py', 'mode': 0o444, 'bytes': 850,
                     'sha256': '7e806fb885dbba39bb6a4424134374e0d9dc9b405efe31b3c13ee2c517573bbb'}]
        self.assertEqual(manifests['executed_author_reference']['candidate']['files'], expected)
        self.assertEqual(manifests['executed_author_reference']['assistance']['files'], [])
        for key, value in (('path', 'other.py'), ('bytes', 849),
                           ('sha256', '0' * 64), ('mode', 0o644)):
            bad = copy.deepcopy(expected)
            bad[0][key] = value
            f.set_manifests(candidate=bad)
            with self.assertRaisesRegex(ValueError, 'exact author candidate.py'):
                A.authenticate_author_trees(f.p, f.config, f.pairing, f.reference, f.provider)
        f.set_manifests(assistance=expected)
        with self.assertRaisesRegex(ValueError, 'empty assistance'):
            A.authenticate_author_trees(f.p, f.config, f.pairing, f.reference, f.provider)
        f.set_manifests(condition='paper_only')
        with self.assertRaisesRegex(ValueError, 'information condition'):
            A.authenticate_author_trees(f.p, f.config, f.pairing, f.reference, f.provider)
        self.assertEqual(len(f.tree_calls), 1, 'mutations refuse before delegated tree authentication')
        self.mark('literal850B programme descriptor; empty assistance; no programme bodies executed')

    def test03_actual_orchestration_and_complete_collection_join(self):
        f = Fixture('orchestration')
        product = f.execute()
        self.assertEqual(product, f.product)
        self.assertEqual(f.events, ['live', 'native', 'reader', 'make_run', 'collect',
                                    'close_owned', 'live', 'recover', 'live', 'close_owned'])
        self.assertEqual(f.run_args, {
            'store_sha256': 'e' * 64, 'candidate_sha256': 'b' * 64,
            'schedule_sha256': 'f' * 64, 'provider_source_sha256': 'c' * 64,
            'condition': 'paper_data_author_code', 'working_limit': 1048576})
        self.assertEqual(f.native_args[1], f.native_admission)
        self.assertEqual(f.reader_args, (f.p['store_root'], {
            'expected_store_sha256': 'e' * 64, 'read_limit': 1048576, 'working_limit': 1048576}))
        self.assertEqual(f.collect_args[3], str(Path(f.p['output_root']) / 'collection'))
        self.assertEqual(f.recover_args[4], f.pin)
        self.assertEqual(f.recover_args[5], 'executed_author_reference')
        self.assertEqual(f.recover_args[7], {
            'store_root': f.p['store_root'], 'output_root': Path(f.p['output_root']) / 'collection',
            'evidence_root': Path(f.p['output_root']) / 'provider',
            'store_limit': 1048576, 'store_working': 1048576, 'limits': f.p['limits'],
            'support_sha256': f.p['source_support_sha256'], 'extra_read_limit': 1048576,
            'working_limit': 268435456})
        self.assertEqual(f.closed, [(f.native, f.reader), (None, None)])
        for name, delta in (
            ('jobs', {'jobs': 41}), ('callbacks', {'software_callbacks': 5684}),
            ('admission', {'provider': {'admission': {'different': True}}}),
        ):
            g = Fixture('incomplete-' + name)
            g.collection_delta = delta
            with self.assertRaisesRegex(ValueError, 'Complete collection'):
                g.execute()
            self.assertNotIn('recover', g.events)
            self.assertEqual(g.closed, [(g.native, g.reader), (None, None)])
        self.mark('actual NativeProvider→StoreReader→make_run→collect→recover order and42/5685 exact admission')

    def test04_failure_propagation_and_resource_closure(self):
        for step in ('native', 'reader', 'make_run', 'collect',
                     'recover', 'recovery_collision', 'live_after_collection'):
            with self.subTest(step=step):
                f = Fixture('failure-' + step)
                f.failure = step
                kind = ValueError if step == 'recovery_collision' else RuntimeError
                with self.assertRaises(kind):
                    f.execute()
                self.assertEqual(f.events[-1], 'close_owned')
                if step == 'native':
                    self.assertEqual(f.closed, [(None, None)])
                    self.assertNotIn('reader', f.events)
                elif step == 'reader':
                    self.assertEqual(f.closed, [(f.native, None)])
                    self.assertNotIn('make_run', f.events)
                elif step == 'make_run':
                    self.assertEqual(f.closed, [(f.native, f.reader)])
                    self.assertNotIn('collect', f.events)
                elif step == 'collect':
                    self.assertEqual(f.closed, [(f.native, f.reader), (f.native, f.reader)])
                    self.assertNotIn('recover', f.events)
                else:
                    self.assertEqual(f.closed, [(f.native, f.reader), (None, None)])
                if step == 'live_after_collection':
                    self.assertNotIn('recover', f.events)
        self.mark('constructor/collection/recovery/deadline failures preserved; idempotent fallback closure; no retries')

    def test05_actual_entry_publication_collision_and_failure_receipts(self):
        f = Fixture('entry-success')
        value = f.run_entry()
        result_path = Path(f.p['output_root']) / 'AUTHOR_REFERENCE.json'
        saved = json.loads(read_fixture(result_path))
        self.assertEqual(saved, value)
        self.assertEqual(saved['role'], 'executed_author_reference')
        self.assertEqual((saved['jobs'], saved['software_callbacks'], saved['fresh_exec_invocations_required']),
                         (42, 5685, 5685))
        self.assertTrue(saved['operator_calibration_not_AI'])
        self.assertTrue(saved['provided_author_reference_untouched'])
        self.assertFalse(saved['scientific_qualification'])
        self.assertFalse(saved['full_224_array_reproduction_executed'])
        self.assertIsNone(saved['binary_win'])
        self.assertFalse(saved['current_sota'])
        self.assertEqual(saved['protocol_sha256'], digest(canonical(f.p)))
        self.assertFalse((result_path.parent / 'AUTHOR_REFERENCE_FAILURE.json').exists())
        self.assertLess(f.events.index('platform-double'), f.events.index('native'))

        collision = Fixture('entry-existing-result')
        original = b'preserve generated prior result\n'
        prior = Path(collision.p['output_root']) / 'AUTHOR_REFERENCE.json'
        collision.before_collect_return = lambda: write_fixture(prior, original)
        with self.assertRaises(FileExistsError):
            collision.run_entry()
        self.assertEqual(read_fixture(prior), original)
        failed = json.loads(read_fixture(prior.parent / 'AUTHOR_REFERENCE_FAILURE.json'))
        self.assertEqual(failed['error_type'], 'FileExistsError')
        self.assertFalse(failed['complete'])

        refusal = Fixture('entry-recovery-refusal')
        refusal.failure = 'recovery_collision'
        with self.assertRaisesRegex(ValueError, 'Fresh original recovery receipt'):
            refusal.run_entry()
        root = Path(refusal.p['output_root'])
        self.assertFalse((root / 'AUTHOR_REFERENCE.json').exists())
        failed = json.loads(read_fixture(root / 'AUTHOR_REFERENCE_FAILURE.json'))
        self.assertEqual(failed['error_type'], 'ValueError')
        self.assertIn('preserve prior attempts', failed['error'])
        self.assertFalse(failed['scientific_qualification'])

        sealed = Fixture('entry-existing-failure')
        sealed.failure = 'recovery_collision'
        failure_path = Path(sealed.p['output_root']) / 'AUTHOR_REFERENCE_FAILURE.json'
        body = b'preserve generated prior failure\n'
        sealed.before_collect_return = lambda: write_fixture(failure_path, body)
        with self.assertRaisesRegex(ValueError, 'Fresh original recovery receipt'):
            sealed.run_entry()
        self.assertEqual(read_fixture(failure_path), body)
        late = Fixture('entry-late-fsync')
        # The successful result body is a direct observed sizing oracle. Paths
        # appear only inside the fixed-length protocol digest, so changing the
        # generated output leaf and its cap leaves this result's byte length.
        exact = len(canonical(saved))
        late.p['output_limit'] = exact
        with self.assertRaisesRegex(OSError, 'generated late fsync failure'):
            late.run_entry(fail_fsync=True)
        late_root = Path(late.p['output_root'])
        self.assertEqual((late_root / 'AUTHOR_REFERENCE.json').stat().st_size, exact)
        self.assertEqual(late.events.count('injected-late-fsync'), 1)
        self.assertFalse((late_root / 'AUTHOR_REFERENCE_FAILURE.json').exists(),
                         'spent successful-receipt bytes must block the extra failure receipt')
        self.assertEqual(late.closed, [(late.native, late.reader), (None, None)])
        self.mark('actual entry success/failure publication; exclusive collisions and late-fsync precharge preserve cause and output cap')


class BoundedText:
    def __init__(self):
        self.parts, self.size, self.truncated = [], 0, False

    def write(self, text):
        body = str(text).encode('utf-8', 'replace')
        take = min(len(body), LIMITS['log_bytes'] - self.size)
        self.parts.append(body[:take])
        self.size += take
        if take != len(body):
            self.truncated = True
            if RESULT is not None:
                RESULT.stop()
        return len(text)

    def flush(self):
        pass

    def body(self):
        return b''.join(self.parts)


class Recorded(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        global RESULT
        super().__init__(*args, **kwargs)
        RESULT = self
        self.starts, self.stops, self.successes, self.diagnostics = [], [], [], []

    def _exc_info_to_string(self, err, test):
        kind, value, tb = err
        frames = []
        while tb is not None and len(frames) < 12:
            frames.append('%s:%s:%s' % (Path(tb.tb_frame.f_code.co_filename).name,
                                       tb.tb_lineno, tb.tb_frame.f_code.co_name))
            tb = tb.tb_next
        return (kind.__name__ + ': ' + str(value)[:768] + '\n' + '\n'.join(frames))[:1536] + '\n'

    def startTest(self, test):
        self.starts.append(test._testMethodName)
        super().startTest(test)
        if TIMEOUT or time.monotonic() >= DEADLINE:
            self.stop()

    def stopTest(self, test):
        self.stops.append(test._testMethodName)
        super().stopTest(test)

    def addSuccess(self, test):
        self.successes.append(test._testMethodName)
        super().addSuccess(test)

    def addError(self, test, err):
        self.diagnostics.append({'method': test._testMethodName, 'kind': 'error',
                                 'type': err[0].__name__, 'message': str(err[1])[:512]})
        super().addError(test, err)

    def addFailure(self, test, err):
        self.diagnostics.append({'method': test._testMethodName, 'kind': 'failure',
                                 'type': err[0].__name__, 'message': str(err[1])[:512]})
        super().addFailure(test, err)


def publish_report(path, body, cap):
    need(len(body) <= cap, 'bounded report')
    with path.open('xb') as stream:
        need(stream.write(body) == len(body), 'complete report')
        stream.flush()
        os.fsync(stream.fileno())


def main():
    global ROOT, A, DEADLINE
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=str(Path(__file__).with_name('author_reference.py')))
    parser.add_argument('--artifact-dir', required=True)
    parser.add_argument('--execute-generated-controls', action='store_true')
    args = parser.parse_args()
    need(args.execute_generated_controls, 'explicit generated-only token')
    need(sys.version_info[:3] == (3, 11, 6), 'selected host Python3.11.6')
    source = {'path': args.source, 'bytes': SOURCE_BYTES, 'sha256': SOURCE_SHA}
    ROOT = Path(args.artifact_dir)
    ordinary_parents(ROOT)
    need(not os.path.lexists(ROOT), 'fresh absent generated output leaf')
    body = source_read(source['path'], SOURCE_BYTES, source)
    A = types.ModuleType('generated_author_reference_entry')
    A.__file__ = source['path']
    sys.dont_write_bytecode = True
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    ROOT.mkdir(mode=0o700)
    (ROOT / 'fixtures').mkdir(mode=0o700)
    started = time.monotonic()
    DEADLINE = started + LIMITS['wall_seconds']
    previous = signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, LIMITS['wall_seconds'])
    log = BoundedText()
    error = None
    result = None
    try:
        exec(compile(body, source['path'], 'exec', dont_inherit=True), A.__dict__)
        suite = unittest.TestSuite(AuthorReferenceControls(name) for name in METHODS)
        result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=Recorded).run(suite)
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)[:512]
        result = RESULT
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    elapsed = time.monotonic() - started
    timeout = TIMEOUT or elapsed >= LIMITS['wall_seconds']
    passed = bool(result and result.wasSuccessful() and result.starts == METHODS
                  and result.stops == METHODS and result.successes == METHODS
                  and not result.failures and not result.errors and not result.skipped
                  and len(CHECKS) == 5 and SCENARIO_COUNT == 18 and not error and not timeout
                  and not log.truncated and not FIXTURE_UNCERTAIN)
    log_raw = log.body()
    retained = None
    retained_error = None
    try:
        retained = sum(Path(row['path']).lstat().st_size for row in FIXTURE_ROWS)
        need(retained <= FIXTURE_WRITTEN, 'retained fixtures within cumulative writes')
    except BaseException as exc:
        retained_error = type(exc).__name__ + ': ' + str(exc)[:512]
        passed = False
    report = {
        'schema': 'language-author-reference-generated-result/v1',
        'status': 'passed' if passed else 'failed',
        'entry': source, 'generated_only_token': True,
        'methods': METHODS, 'tests_run': result.testsRun if result else 0,
        'starts': result.starts if result else [], 'stops': result.stops if result else [],
        'successes': result.successes if result else [],
        'failures': len(result.failures) if result else 0,
        'errors': len(result.errors) if result else 0,
        'skips': len(result.skipped) if result else 0,
        'diagnostics': result.diagnostics if result else [],
        'checks': CHECKS, 'generated_scenarios': SCENARIO_COUNT,
        'runner_error': error, 'timeout': timeout, 'elapsed_seconds': elapsed,
        'log_truncated': log.truncated,
        'test_log': {'bytes': len(log_raw), 'sha256': digest(log_raw)},
        'accounting': {'driver_instrumented_source_reads': SOURCE_READ,
                       'generated_fixture_reads': FIXTURE_READ,
                       'cumulative_fixture_and_entry_receipt_writes': FIXTURE_WRITTEN,
                       'retained_fixture_payload_bytes': retained,
                       'retained_fixture_error': retained_error,
                       'fixture_write_uncertain': FIXTURE_UNCERTAIN,
                       'fixture_descriptors_sha256': digest(canonical(FIXTURE_ROWS)),
                       'fixture_write_stop_bytes': 32768, 'reports_stop_bytes': 32768,
                       'ordinary_interpreter_and_stdlib_reads_metered': False,
                       'filesystem_allocated_blocks_measured': False},
        'scope': {'actual_entry_guards_orchestration_and_publication': True,
                  'native_provider_store_collection_recovery_and_tree_authentication': 'explicit generated boundary doubles',
                  'actual_recovery_collision_implementation_executed': False,
                  'exact_recovery_collision_refusal_propagated': True,
                  'real_fourteen_session_eight_person_forty_two_cell_population_observed': False,
                  'full_scope_join': 'fixed42/5685 and source-support/store/schedule identities; maintained population validation delegated',
                  'real_fresh_fits': 0, 'original_store_reads': 0,
                  'programme_body_reads': 0, 'native_processes': 0,
                  'docker_calls': 0, 'network_calls': 0,
                  'actual_scientific_runtime_executed': False,
                  'scientific_or_provider_qualification': False,
                  'hard_memory_or_pool_drainer_eof_qualified': False},
    }
    result_raw = (json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    publish_report(ROOT / 'TEST_LOG.txt', log_raw, LIMITS['log_bytes'])
    publish_report(ROOT / 'RESULT.json', result_raw, LIMITS['result_bytes'])
    sys.stdout.write(log_raw.decode('utf-8', 'replace'))
    sys.stdout.flush()
    print(json.dumps({'status': report['status'], 'tests': report['tests_run'],
                      'result_bytes': len(result_raw), 'result_sha256': digest(result_raw)}, sort_keys=True), flush=True)
    return 0 if passed else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'status': 'refused_or_unpublished', 'type': type(exc).__name__,
                          'message': str(exc)[:512]}, sort_keys=True), flush=True)
        raise SystemExit(2)
