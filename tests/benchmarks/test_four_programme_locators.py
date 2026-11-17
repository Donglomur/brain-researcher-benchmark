"""Source-only controls for the two relocated inactive Four wrappers.

The real inspector authenticates public source and parses API definitions. These
controls never construct HostRuntime or open protected inputs/native datasets.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SHARED = Path('benchmarks/shared/four-programmes/_four_programmes_source_v1')
ENTRIES = {
    'NEURAL-098': Path('benchmarks/neural/NEURAL-098/implementations/registered-runtime/central_operator.py'),
    'PAPER-paper-method-replacement-016': Path('benchmarks/paper/PAPER-paper-method-replacement-016/implementations/registered-runtime/central_operator.py'),
}
BINDINGS = Path('benchmarks/integrity/current-closures/four-programme-wrappers/SOURCE_BINDINGS.json')


class FourProgrammeLocatorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='four-locator-test-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.checkout = self.base / 'relocated checkout'
        self.unrelated = self.base / 'unrelated working directory'
        self.unrelated.mkdir()

    def copied_checkout(self):
        shutil.copytree(ROOT / SHARED, self.checkout / SHARED)
        for relative in ENTRIES.values():
            target = self.checkout / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        return self.checkout

    def invoke(self, entry, command='inspect', flags=('-I', '-S', '-B')):
        return subprocess.run(
            [sys.executable, *flags, str(entry), command],
            cwd=self.unrelated, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=15, check=False,
        )

    def assert_inspection(self, result, task):
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['id'], task)
        self.assertEqual(report['current_roles'], 256)
        self.assertEqual(report['ordinary_original_bodies'], 264)
        self.assertEqual(report['original_scientific_roles'], 266)
        self.assertEqual(report['original_API_definitions'], 46)
        self.assertEqual(report['qualification_holds_open'], 65)
        self.assertEqual(report['extension_deployment_copies'], 68)
        self.assertEqual(report['extension_current_body_matches'], 67)
        self.assertEqual(report['extension_historical_predecessor_copies'], 1)
        self.assertEqual(len(report['current_source_repairs']), 1)
        repair = report['current_source_repairs'][0]
        self.assertEqual(repair['path'], 'current/source/extensions/critical_init/numerics.py')
        self.assertEqual(repair['predecessor'], {
            'bytes': 9089,
            'sha256': 'fa87084fee5caa1a82b9fff22927b7de84e64aac460352f4ede80f91e9c43d31',
        })
        self.assertEqual(repair['current'], {
            'bytes': 9273,
            'sha256': 'e3201eb4b0fb19c066b28a2d46c01e9fab6d80a21e778da93f7d50b27c4b3f95',
        })
        for field in ('held_bodies_opened', 'original_modules_imported', 'runnable',
                      'research_qualified', 'submission_ready',
                      'scientific_or_native_execution', 'authority_issued'):
            self.assertIs(report[field], False, field)
        self.assertEqual(report['scope']['NEURAL-098']['people'], 33)
        self.assertEqual(report['scope']['PAPER-paper-method-replacement-016']['reference_jobs'], 8223)

    def assert_refusal(self, result, message):
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn(message, result.stderr)

    def test_current_bindings_preserve_historical_manifests_and_shared_source(self):
        bindings = json.loads((ROOT / BINDINGS).read_text())
        self.assertEqual(bindings['schema'], 'four_programme_current_wrapper_bindings_v1')
        self.assertEqual(set(bindings['task_ids']), set(ENTRIES))
        self.assertFalse(bindings['execution_authority'])
        self.assertFalse(bindings['scientific_qualification'])
        self.assertEqual(bindings['qualification_holds_open'], 65)
        self.assertEqual({row['path'] for row in bindings['current_wrappers']},
                         {str(path) for path in ENTRIES.values()})
        for group in ('current_wrappers', 'current_shared_sources',
                      'historical_manifests', 'unchanged_shared_dependencies'):
            for pin in bindings[group]:
                with self.subTest(group=group, path=pin['path']):
                    body = (ROOT / pin['path']).read_bytes()
                    self.assertEqual(len(body), pin['bytes'])
                    self.assertEqual(hashlib.sha256(body).hexdigest(), pin['sha256'])
        for row in bindings['historical_manifests']:
            manifest = json.loads((ROOT / row['path']).read_text())
            self.assertEqual(manifest['status'], 'source_only_inactive')
            self.assertIsNone(manifest['run'])
            self.assertIsNone(manifest['score'])
            self.assertTrue(all(value is False for value in manifest['admission'].values()))

    def test_both_actual_current_entries_inspect_without_scientific_execution(self):
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                self.assert_inspection(self.invoke(ROOT / relative), task)

    def test_complete_relocated_layout_is_independent_of_current_working_directory(self):
        root = self.copied_checkout()
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                self.assert_inspection(self.invoke(root / relative), task)

    def test_wrong_wrapper_location_refuses_instead_of_guessing_repository(self):
        root = self.copied_checkout()
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                wrong = (root / relative).with_name('renamed_operator.py')
                shutil.copyfile(root / relative, wrong)
                self.assert_refusal(self.invoke(wrong), 'exact ordinary installed task entry')

    def test_symlinked_wrapper_refuses_even_with_a_valid_shared_tree(self):
        root = self.copied_checkout()
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                entry = root / relative
                original = entry.with_name('original.py')
                entry.rename(original)
                entry.symlink_to(original)
                self.assert_refusal(self.invoke(entry), 'exact ordinary installed task entry')

    def test_symlinked_shared_root_is_not_an_accepted_locator(self):
        root = self.copied_checkout()
        original = (root / SHARED).with_name('original-shared-source')
        (root / SHARED).rename(original)
        (root / SHARED).symlink_to(original, target_is_directory=True)
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                self.assert_refusal(self.invoke(root / relative), 'ordinary installed source ancestry')

    def test_same_size_central_tamper_refuses_before_executing_changed_bytes(self):
        root = self.copied_checkout()
        central = root / SHARED / 'central_source.py'
        marker = self.base / 'must-not-be-created'
        replacement = ('open(' + repr(str(marker)) + ', "w").write("executed")\n').encode()
        original_size = central.stat().st_size
        central.write_bytes(replacement + b' ' * (original_size - len(replacement)))
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                self.assert_refusal(self.invoke(root / relative), 'exact central source identity')
                self.assertFalse(marker.exists())

    def test_source_lock_tamper_still_refuses(self):
        root = self.copied_checkout()
        lock = root / SHARED / 'SOURCE_LOCK.json'
        body = lock.read_bytes()
        lock.write_bytes(b'x' + body[1:])
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                self.assert_refusal(self.invoke(root / relative), 'exact source body identity')

    def test_repaired_current_helper_cannot_roll_back_to_historical_bytes(self):
        root = self.copied_checkout()
        current = root / SHARED / 'current/source/extensions/critical_init/numerics.py'
        predecessor = root / SHARED / 'originals/_four_extensions/critical_init/numerics.py'
        current.write_bytes(predecessor.read_bytes())
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                self.assert_refusal(self.invoke(root / relative), 'exact ordinary source extent')

    def test_current_override_does_not_apply_to_either_historical_helper(self):
        root = self.copied_checkout()
        current_body = (root / SHARED / 'current/source/extensions/critical_init/numerics.py').read_bytes()
        originals = (
            'originals/_four_extensions/critical_init/numerics.py',
            'originals/authoring/delivery-20261105/common/remaining-builds-wave39/'
            'critical-init-complete-design/implementation-v1/successor-v3/critical_init/numerics.py',
        )
        for historical in originals:
            path = root / SHARED / historical
            old_body = path.read_bytes()
            try:
                path.write_bytes(current_body)
                for task, relative in ENTRIES.items():
                    with self.subTest(historical=historical, task=task):
                        self.assert_refusal(self.invoke(root / relative), 'exact ordinary source extent')
            finally:
                path.write_bytes(old_body)

    def test_hardlinked_central_source_still_refuses(self):
        root = self.copied_checkout()
        (self.base / 'linked-central.py').hardlink_to(root / SHARED / 'central_source.py')
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                self.assert_refusal(self.invoke(root / relative), 'exact central source extent')

    def test_held_body_insertion_is_rejected_without_reading_it(self):
        root = self.copied_checkout()
        held = root / SHARED / 'originals/authoring/delivery-20261105/neural098/public/COHORT.json'
        self.assertFalse(held.exists())
        held.write_text('generated forbidden-body sentinel\n')
        guarded = '''import pathlib, runpy, sys
entry, forbidden = sys.argv[1:]
def no_held_open(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        name = args[0].decode() if isinstance(args[0], bytes) else args[0]
        if pathlib.Path(name).absolute() == pathlib.Path(forbidden):
            raise AssertionError('held sentinel was opened')
sys.addaudithook(no_held_open)
sys.argv = [entry, 'inspect']
runpy.run_path(entry, run_name='__main__')
'''
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                result = subprocess.run(
                    [sys.executable, '-I', '-S', '-B', '-c', guarded,
                     str(root / relative), str(held)],
                    cwd=self.unrelated, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, timeout=15, check=False,
                )
                self.assert_refusal(result, 'held body cannot enter installed tree')
                self.assertNotIn('held sentinel was opened', result.stderr)

    def test_cli_execution_and_unisolated_hosts_remain_refused(self):
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                self.assert_refusal(self.invoke(ROOT / relative, command='run'),
                                    'CLI supports source inspection only')
                self.assert_refusal(self.invoke(ROOT / relative, flags=('-S', '-B')),
                                    'source entry requires a fresh python -I -B host')


if __name__ == '__main__':
    unittest.main()
