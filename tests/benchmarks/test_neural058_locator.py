"""Generated/public-source controls; no native or private NEURAL-058 operands."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
REL = Path('benchmarks/neural/NEURAL-058/implementations/registered-runtime')
PREPARER = REPO / REL / 'source-resolution/prepare_sources.py'
CENTRAL = 'authoring/delivery-20261105/common/remaining-builds-wave29/neural058-complete-design/implementation-v1/central-integration-v1'
ALIAS = 'benchmarks/neuroscience/neural-058-brainwide-wheel/score.py'
PIN = (886, 'f3df6e660df0c81f330f6c2e7be255a95d079be408615a0842cfe040d953f214')
spec = importlib.util.spec_from_file_location('neural058_source_preparation', PREPARER)
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)


def budget(**changes):
    values = dict(reads=16 * 2**20, writes=8 * 2**20, live=2**20, seconds=30)
    values.update(changes)
    return prep.Budget(**values)


def argv(entry, protected, operation='collect', condition='default'):
    return [str(entry), '--operation', operation, '--condition', condition,
            '--program', str(protected / 'program'), '--output', str(protected / 'output'),
            '--review', str(protected / 'review'), '--other-reserve-bytes', '0',
            '--source-bytes', str(PIN[0]), '--source-sha256', PIN[1]]


class SourcePreparation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='neural058-source-only-')
        cls.root = Path(cls.temp.name).resolve()
        cls.prepared = cls.root / 'prepared'
        cls.result = prep.prepare(REPO, cls.prepared, budget())
        cls.rows = json.loads((PREPARER.parent / 'SOURCE_MAP.json').read_bytes())['files']

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def destination(self, name):
        return self.root / self._testMethodName / name

    def fixture(self):
        source = self.destination('source')
        source.mkdir(parents=True)
        for row in self.rows:
            target = source / row['current_path']
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copyfile(REPO / row['current_path'], target)
        return source

    def test_complete_exact_public_tree_and_unqualified_receipt(self):
        self.assertEqual(len(self.rows), 326)
        self.assertEqual(sum(row['bytes'] for row in self.rows), 3010666)
        for row in self.rows:
            raw = (self.prepared / row['logical_path']).read_bytes()
            self.assertEqual(len(raw), row['bytes'], row['logical_path'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'], row['logical_path'])
        receipt = json.loads((self.prepared / prep.RECEIPT).read_bytes())
        self.assertEqual(receipt['state'], 'source_prepared_not_qualified')
        for key in ('runtime_authorization', 'scientific_execution', 'scientific_qualification'):
            self.assertIs(receipt[key], False)
        counters = self.result['budget']
        self.assertGreater(counters['read_observed'], 3 * 3010666)
        self.assertLessEqual(counters['read_observed'], counters['read_reserved'])
        self.assertLessEqual(counters['write_observed'], counters['write_reserved'])
        self.assertLessEqual(counters['peak_live_source_buffer_bytes'], 2**20)

    def test_advertised_preparation_cli(self):
        destination = self.destination('prepared')
        destination.parent.mkdir()
        result = subprocess.run([sys.executable, '-I', '-S', '-B', str(PREPARER),
            '--repository', str(REPO), '--destination', str(destination),
            '--max-read-bytes', '16777216', '--max-write-bytes', '8388608',
            '--max-live-bytes', '1048576', '--deadline-seconds', '30'],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['members'], 326)
        self.assertTrue((destination / prep.RECEIPT).is_file())

    def test_relocated_source_checkout(self):
        source = self.fixture()
        destination = source.parent / 'prepared'
        result = prep.prepare(source, destination, budget())
        self.assertEqual(result['members'], 326)
        self.assertEqual((destination / ALIAS).read_bytes(), (REPO / REL / 'score.py').read_bytes())

    def test_real_prepared_entry_authenticates_then_preserves_authority_gate(self):
        # Audit rejects any protected operand read or native process launch;
        # tracing observes the original exception without replacing its gate.
        wrapper = r'''
import json, os, runpy, sys
protected = sys.argv[1]
entry_args = sys.argv[2:]
events = {'protected_opens': 0, 'native_launches': 0, 'gate_messages': []}
def audit(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        name = os.fsdecode(args[0])
        if name == protected or name.startswith(protected + os.sep):
            events['protected_opens'] += 1
            raise RuntimeError('protected operand must remain unopened')
    if event in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.exec', 'os.fork'):
        events['native_launches'] += 1
        raise RuntimeError('native launch forbidden in source-only test')
def trace(frame, event, arg):
    if event == 'exception' and frame.f_code.co_name == 'qualify' and frame.f_code.co_filename.endswith('/routing.py'):
        events['gate_messages'].append(str(arg[1]))
    return trace
sys.addaudithook(audit)
sys.settrace(trace)
sys.argv = entry_args
try:
    runpy.run_path(entry_args[0], run_name='__main__')
except SystemExit as error:
    code = error.code
else:
    code = 0
sys.settrace(None)
print(json.dumps(events, sort_keys=True))
raise SystemExit(code)
'''
        for operation, condition, entry in (
            ('collect', 'default', CENTRAL + '/entry.py'),
            ('collect', 'full423_29_held_animal_v1', CENTRAL + '/entry.py'),
            ('grade', 'default', ALIAS),
        ):
            with self.subTest(operation=operation, condition=condition):
                protected = self.root / 'never-open-protected-operands'
                result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', wrapper,
                    str(protected), *argv(self.prepared / entry, protected, operation, condition)],
                    cwd=self.prepared, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                report, audit = [json.loads(line) for line in result.stdout.splitlines()]
                self.assertIsNotNone(report['source'])
                self.assertIsNotNone(report['central_costs'])
                source = report['source']
                attempted = (len(source['attempted']) if 'attempted' in source else
                             source['central']['attempted_path_count'])
                self.assertGreaterEqual(attempted, 324)
                self.assertEqual(audit['protected_opens'], 0)
                self.assertEqual(audit['native_launches'], 0)
                self.assertIn('not qualified: complete NEURAL058 central interface', audit['gate_messages'])

    def test_direct_current_operational_refusal_and_help(self):
        protected = self.root / 'never-open-protected-operands'
        result = subprocess.run([sys.executable, '-I', '-S', '-B', *argv(REPO / REL / 'score.py', protected)],
                                cwd=REPO, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertIsNone(json.loads(result.stdout)['source'])
        result = subprocess.run([sys.executable, '-I', '-S', '-B', str(REPO / REL / 'score.py'), '--help'],
                                cwd=REPO, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0)

    def test_missing_or_modified_source_refuses_before_destination(self):
        source = self.fixture()
        row = self.rows[-1]
        member = source / row['current_path']
        original = member.read_bytes()
        destination = source.parent / 'prepared'
        member.unlink()
        with self.assertRaises(OSError):
            prep.prepare(source, destination, budget())
        self.assertFalse(destination.exists())
        member.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        with self.assertRaisesRegex(ValueError, 'source hash'):
            prep.prepare(source, destination, budget())
        self.assertFalse(destination.exists())

    def test_source_symlink_and_hardlink_refused(self):
        source = self.fixture()
        member = source / self.rows[0]['current_path']
        original = member.with_name(member.name + '.original')
        member.rename(original)
        member.symlink_to(original)
        destination = source.parent / 'prepared'
        with self.assertRaises(OSError):
            prep.prepare(source, destination, budget())
        self.assertFalse(destination.exists())
        member.unlink()
        os.link(original, member)
        with self.assertRaisesRegex(ValueError, 'ordinary source'):
            prep.prepare(source, destination, budget())
        self.assertFalse(destination.exists())

    def test_source_changes_after_preflight_are_recaptured(self):
        source = self.fixture()
        destination = source.parent / 'prepared'
        selected = source / self.rows[0]['current_path']
        original = selected.read_bytes()
        actual_constructor = prep.Destination

        def create_then_change(path):
            owner = actual_constructor(path)
            selected.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            return owner

        with mock.patch.object(prep, 'Destination', side_effect=create_then_change):
            with self.assertRaisesRegex(ValueError, 'source hash'):
                prep.prepare(source, destination, budget())
        self.assertFalse((destination / prep.RECEIPT).exists())

    def test_source_replacement_during_capture_is_refused(self):
        directory = self.destination('source')
        directory.mkdir(parents=True)
        member = directory / 'member'
        raw = b'generated source identity'
        member.write_bytes(raw)
        pin = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        original_read = prep.os.read
        replaced = False

        def read_and_replace(fd, count):
            nonlocal replaced
            result = original_read(fd, count)
            if not replaced:
                replaced = True
                member.rename(directory / 'original')
                member.write_bytes(raw)
            return result

        with mock.patch.object(prep.os, 'read', side_effect=read_and_replace):
            with self.assertRaisesRegex(ValueError, 'source changed'):
                prep.capture(member, pin, budget())

    def test_overlong_read_reserves_eof_byte_and_rejects(self):
        directory = self.destination('source')
        directory.mkdir(parents=True)
        member = directory / 'member'
        raw = b'generated'
        member.write_bytes(raw)
        pin = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        with self.assertRaisesRegex(ValueError, 'live source buffer'):
            prep.capture(member, pin, budget(live=2 * len(raw)))
        limited = budget(live=2 * len(raw) + 1)
        original_read = prep.os.read

        def overlong(fd, count):
            value = original_read(fd, count)
            return b'x' if count == 1 and value == b'' else value

        with mock.patch.object(prep.os, 'read', side_effect=overlong):
            with self.assertRaisesRegex(ValueError, 'source changed'):
                prep.capture(member, pin, limited)
        self.assertEqual(limited.live, 0)
        self.assertEqual(limited.peak_live, 2 * len(raw) + 1)

    def test_map_tampering_refused_before_destination(self):
        copied = self.destination('resolver')
        copied.mkdir(parents=True)
        raw = (PREPARER.parent / 'SOURCE_MAP.json').read_bytes()
        (copied / 'SOURCE_MAP.json').write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        destination = copied.parent / 'prepared'
        with mock.patch.object(prep, 'HERE', copied), self.assertRaisesRegex(ValueError, 'source hash'):
            prep.prepare(REPO, destination, budget())
        self.assertFalse(destination.exists())

    def test_canonical_disjoint_absent_destination(self):
        with self.assertRaisesRegex(ValueError, 'destination must be absent'):
            prep.prepare(REPO, self.prepared, budget())
        with self.assertRaisesRegex(ValueError, 'disjoint'):
            prep.prepare(REPO, REPO / 'never-create-test-output', budget())
        with self.assertRaisesRegex(ValueError, 'canonical'):
            prep.prepare(str(REPO) + '/../' + REPO.name, self.root / 'never-create', budget())
        link = self.destination('alias')
        link.parent.mkdir()
        link.symlink_to(REPO, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'directory ancestry'):
            prep.prepare(link, self.root / 'never-create', budget())

    def test_resource_caps_fail_without_success_receipt(self):
        base = self.destination('limits')
        base.mkdir(parents=True)
        for name, changes in [('read', {'reads': 100}), ('write', {'writes': 1}),
                              ('live', {'live': 1}), ('deadline', {'seconds': 0.000001})]:
            with self.subTest(limit=name):
                destination = base / name
                with self.assertRaises(ValueError):
                    prep.prepare(REPO, destination, budget(**changes))
                self.assertFalse((destination / prep.RECEIPT).exists())
        for changes in ({'reads': True}, {'writes': -1}, {'seconds': float('inf')}, {'seconds': 0}):
            with self.assertRaises(ValueError):
                budget(**changes)

    def test_destination_root_replacement_is_not_published(self):
        path = self.destination('owned')
        path.parent.mkdir()
        owner = prep.Destination(path)
        try:
            path.rename(path.with_name('moved'))
            path.mkdir()
            with self.assertRaisesRegex(ValueError, 'identity changed'):
                owner.publish('member', b'generated', budget())
            self.assertEqual(list(path.iterdir()), [])
        finally:
            owner.close()

    def test_writeback_failure_is_not_success(self):
        path = self.destination('owned')
        path.parent.mkdir()
        owner = prep.Destination(path)
        try:
            with mock.patch.object(prep.os, 'read', return_value=b''), self.assertRaisesRegex(ValueError, 'readback'):
                owner.publish('member', b'generated', budget())
            self.assertFalse((path / prep.RECEIPT).exists())
        finally:
            owner.close()


if __name__ == '__main__':
    unittest.main()
