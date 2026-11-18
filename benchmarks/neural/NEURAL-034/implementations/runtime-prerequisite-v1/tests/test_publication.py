"""Generated source/permission controls only; never Docker or authentic data."""
from pathlib import Path
import importlib.util
import json
import os
import stat
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[4]
spec = importlib.util.spec_from_file_location('_neural034_publication', HERE / 'configure.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


def module(path):
    value = types.ModuleType('_publication_' + path.stem)
    value.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), value.__dict__)
    return value


class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        explicit_output = os.environ.get('NEURAL034_PUBLICATION_TEST_OUTPUT')
        cls.owned_temporary = None
        if explicit_output:
            cls.out = Path(explicit_output).absolute()
        else:
            cls.owned_temporary = tempfile.TemporaryDirectory(prefix='neural034-publication-test-')
            cls.out = Path(cls.owned_temporary.name).resolve() / 'output'
        if cls.out.exists():
            raise ValueError('Fresh retained fixture output required')
        cls.out.mkdir(mode=0o700)
        reuse = os.environ.get('NEURAL034_PUBLICATION_REUSE_SOURCE')
        if reuse:
            cls.dest = Path(reuse).absolute()
            cls.receipt = C.load(cls.dest)
        else:
            cls.dest = cls.out / 'source'
            original = os.umask(0o077)
            try:
                cls.receipt = C.configure(ROOT, cls.dest)
            finally:
                os.umask(original)
        cls.admission = module(cls.dest / C.ADMISSION)

    @classmethod
    def tearDownClass(cls):
        if cls.owned_temporary is not None:
            cls.owned_temporary.cleanup()

    def setUp(self):
        self.fixture = self.out / self._testMethodName
        self.fixture.mkdir(mode=0o700)

    def test_complete_source_closure_and_no_data_members(self):
        self.assertEqual(C.load(self.dest), self.receipt)
        self.assertLessEqual(self.receipt['source_bytes'], 300 * 1024)
        self.assertEqual(stat.S_IMODE(self.dest.stat().st_mode), 0o700)
        selected = json.loads((self.dest / 'SOURCE_MANIFEST.json').read_text())
        self.assertLessEqual(len(selected['files']), 64)
        inputs = json.loads((self.dest / 'INPUTS.json').read_text())
        for row in inputs['files']:
            self.assertNotIn(row['path'], selected['files'])
            self.assertFalse((self.dest / row['path']).exists())
        freeze, bodies = self.admission.source_gate(self.receipt['source_freeze'])
        self.assertEqual(freeze['historical_source_freeze'], C.HISTORICAL)
        self.assertEqual(freeze['predecessor_source_freeze'], {'path': C.FREEZE, **C.FREEZE_PIN})
        for name in ('runtime.py', 'run.py', 'scheduler.py', 'transport/engine_profile.py',
                     'transport/contract_profile.py', 'transport/recovery.py'):
            rel = C.LOCAL + name
            self.assertEqual(bodies[rel], (ROOT / C.PORTABLE / rel).read_bytes())
        for rel in ('authoring/shared-program-runner-v2/unit.py',
                    'authoring/shared-program-runner-v2/holder_profile.py',
                    'authoring/dmfc-timing/program-runner-v2/host_budget.py'):
            self.assertEqual(bodies[rel], (ROOT / C.PORTABLE / rel).read_bytes())
        with patch.dict(sys.modules, {'admission': self.admission}), patch.dict(os.environ, {
                'NEURAL034_DOCKER': '/generated/not-executed/docker',
                'NEURAL034_DOCKER_HOST': 'unix:///generated/not-executed.sock'}):
            runtime = module(self.dest / C.LOCAL / 'runtime.py')
            api = runtime.load(bodies)
        self.assertTrue(callable(api.unit.run_unit))
        self.assertTrue(callable(api.recovery.recover_unit))

    def test_exact_fchmod_publications_under_077(self):
        provision = module(self.dest / 'provision.py')
        grader = module(self.dest / C.GRADER)
        original = os.umask(0o077)
        try:
            source = self.fixture / 'generated-source.txt'
            source.write_bytes(b'generated public fixture\n')
            copied = self.fixture / 'published.txt'
            provision.stable(source, C.pin(source.read_bytes()), 1000, copied)
            root = self.fixture / 'grader'
            root.mkdir(mode=0o700)
            operator = root / 'operator'
            operator.mkdir(mode=0o700)
            invocation = operator / 'invocation.json'
            grader.write(invocation, {'fixture': True})
            direct = self.fixture / 'configured.txt'
            C.publish(direct, b'configured source\n')
        finally:
            os.umask(original)
        self.assertEqual(stat.S_IMODE(copied.stat().st_mode), 0o444)
        self.assertEqual(stat.S_IMODE(direct.stat().st_mode), 0o444)
        self.assertEqual(stat.S_IMODE(invocation.stat().st_mode), 0o644)
        self.assertEqual(stat.S_IMODE(operator.stat().st_mode), 0o700)
        self.assertEqual(copied.read_bytes(), source.read_bytes())
        self.assertEqual(json.loads(invocation.read_text()), {'fixture': True})
        with self.assertRaises(FileExistsError):
            C.publish(direct, b'must not overwrite\n')
        self.assertEqual(direct.read_bytes(), b'configured source\n')

    def test_historical_and_predecessor_costs_preserved_without_reset(self):
        a = self.admission
        prior = {'candidate_id': a.ID, 'runtime_id': a.RUNTIME_ID,
                 'cost_family_id': 'astrocyte_source_family',
                 'all_owned_absent': True, 'all_process_groups_absent_and_reaped': True,
                 'all_owned_cli_processes_absent': True, 'controller_direct_handle_reaped': True,
                 'status': 'execution_failed_preserved', 'known_seconds_before': a.BASELINE + 480,
                 'known_seconds_after': a.BASELINE + 960, 'charged_seconds': 480}
        for old in (C.HISTORICAL, {'path': C.FREEZE, **C.FREEZE_PIN}, self.receipt['source_freeze']):
            prior['source_freeze'] = old
            with patch.object(a, 'pinned', return_value=dict(prior)):
                self.assertEqual(a.known_cost({'fixture': 'generated'}, self.receipt['source_freeze']), a.BASELINE + 960)
        for bad in ({'all_owned_absent': False}, {'known_seconds_after': a.BASELINE},
                    {'source_freeze': {'path': C.FREEZE, 'bytes': 5437, 'sha256': '0' * 64}}):
            row = dict(prior, **bad)
            with patch.object(a, 'pinned', return_value=row), self.assertRaises(ValueError):
                a.known_cost({'fixture': 'generated'}, self.receipt['source_freeze'])

    def test_tamper_and_link_refusals_preserve_existing_bytes(self):
        target = self.dest / 'SOURCE_MANIFEST.json'
        saved = target.read_bytes()
        try:
            target.chmod(0o644)
            target.write_bytes(saved.replace(b'"NEURAL-034"', b'"NEURAL-035"', 1))
            target.chmod(0o444)
            with self.assertRaisesRegex(ValueError, 'checksum'):
                C.load(self.dest)
        finally:
            target.chmod(0o644)
            target.write_bytes(saved)
            target.chmod(0o444)
        linked = self.fixture / 'linked'
        linked.symlink_to(target)
        with self.assertRaises(ValueError):
            C.publish(linked, b'forbidden\n')
        self.assertEqual(target.read_bytes(), saved)
        with self.assertRaises(ValueError):
            C.configure(ROOT, self.dest)
        self.assertEqual(C.load(self.dest), self.receipt)


if __name__ == '__main__':
    unittest.main(verbosity=2)
