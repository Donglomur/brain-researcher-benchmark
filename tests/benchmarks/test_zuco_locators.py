"""Check current ZuCo source discovery without a campaign or protected inputs."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SHARED = Path('benchmarks/shared/zuco2/zuco2-neural085-086-complete-v1/score_campaign.py')
ENTRIES = {
    task: Path(f'benchmarks/neural/{task}/implementations/registered-runtime/score.py')
    for task in ('NEURAL-085', 'NEURAL-086')
}
BINDINGS = Path('benchmarks/integrity/current-closures/relocation-zuco/SOURCE_BINDINGS.json')


class ZuCoLocatorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='zuco-locator-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.checkout = self.base / 'relocated checkout'
        self.cwd = self.base / 'unrelated working directory'
        self.cwd.mkdir()

    def copied_checkout(self):
        for relative in (*ENTRIES.values(), SHARED):
            destination = self.checkout / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        return self.checkout

    def invoke(self, entry, *arguments):
        return subprocess.run(
            [sys.executable, '-I', '-S', '-B', str(entry), *arguments],
            cwd=self.cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=10, check=False,
        )

    def assert_help(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        for option in ('--submission', '--output', '--review', '--other-reserve-bytes'):
            self.assertIn(option, result.stdout)

    def assert_refusal(self, result, message):
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn(message, result.stderr)

    def test_current_descriptor_preserves_source_and_unqualified_manifests(self):
        descriptor = json.loads((ROOT / BINDINGS).read_text())
        self.assertEqual(descriptor['task_ids'], list(ENTRIES))
        self.assertIs(descriptor['execution_authority'], False)
        self.assertIs(descriptor['scientific_qualification'], False)
        self.assertEqual({row['path'] for row in descriptor['current_wrappers']},
                         {str(path) for path in ENTRIES.values()})
        for group in ('current_wrappers', 'historical_manifests', 'unchanged_shared_dependencies'):
            for pin in descriptor[group]:
                with self.subTest(group=group, path=pin['path']):
                    body = (ROOT / pin['path']).read_bytes()
                    self.assertEqual(len(body), pin['bytes'])
                    self.assertEqual(hashlib.sha256(body).hexdigest(), pin['sha256'])
        for pin in descriptor['historical_manifests']:
            manifest = json.loads((ROOT / pin['path']).read_text())
            self.assertIs(manifest['deployment_enabled'], False)
            self.assertTrue(all(value is False for value in manifest['admission'].values()))
            self.assertEqual(manifest['verification']['status'], 'not_run')

    def test_both_current_entries_reach_help_from_unrelated_directory(self):
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                self.assert_help(self.invoke(ROOT / relative, '--help'))

    def test_copied_layout_with_spaces_is_relocatable(self):
        root = self.copied_checkout()
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                self.assert_help(self.invoke(root / relative, '--help'))

    def test_renamed_entry_refuses_instead_of_guessing_a_root(self):
        root = self.copied_checkout()
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                wrong = (root / relative).with_name('renamed_score.py')
                shutil.copyfile(root / relative, wrong)
                self.assert_refusal(self.invoke(wrong, '--help'),
                                    'exact ordinary installed ZuCo entry required')

    def test_symlinked_entry_is_not_an_ordinary_installed_wrapper(self):
        root = self.copied_checkout()
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                entry = root / relative
                original = entry.with_name('original.py')
                entry.rename(original)
                entry.symlink_to(original)
                self.assert_refusal(self.invoke(entry, '--help'),
                                    'exact ordinary installed ZuCo entry required')

    def test_shared_directory_symlink_refuses(self):
        root = self.copied_checkout()
        directory = (root / SHARED).parent
        original = directory.with_name('original-shared')
        directory.rename(original)
        directory.symlink_to(original, target_is_directory=True)
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                self.assert_refusal(self.invoke(root / relative, '--help'),
                                    'ordinary shared score source required')

    def test_source_hardlink_still_refuses(self):
        root = self.copied_checkout()
        (self.base / 'source-link.py').hardlink_to(root / SHARED)
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                self.assert_refusal(self.invoke(root / relative, '--help'),
                                    'shared score source extent')

    def test_same_size_tamper_refuses_before_any_source_execution(self):
        root = self.copied_checkout()
        source = root / SHARED
        marker = self.base / 'should-not-be-created'
        replacement = ('open(' + repr(str(marker)) + ', "w").write("executed")\n').encode()
        source.write_bytes(replacement.ljust(source.stat().st_size, b' '))
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                self.assert_refusal(self.invoke(root / relative, '--help'),
                                    'shared score source identity')
                self.assertFalse(marker.exists())

    def test_extent_drift_still_refuses(self):
        root = self.copied_checkout()
        with (root / SHARED).open('ab') as stream:
            stream.write(b'\n')
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                self.assert_refusal(self.invoke(root / relative, '--help'),
                                    'shared score source extent')

    def test_required_protected_review_is_not_bypassed(self):
        root = self.copied_checkout()
        for task, relative in ENTRIES.items():
            with self.subTest(task=task):
                result = self.invoke(root / relative, '--submission', 'unused.json',
                                     '--output', 'unused-output')
                self.assertEqual(result.returncode, 2)
                self.assertIn('required: --review', result.stderr)
                self.assertFalse((self.cwd / 'unused-output').exists())

    def test_help_does_not_open_submission_or_review_and_reused_module_refuses(self):
        root = self.copied_checkout()
        sentinel = self.base / 'private-generated-sentinel.json'
        sentinel.write_text('generated test content, not a real reference\n')
        guarded = '''import pathlib, runpy, sys, types
entry, forbidden, mode = sys.argv[1:]
def no_input_open(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        name = args[0].decode() if isinstance(args[0], bytes) else args[0]
        if pathlib.Path(name).absolute() == pathlib.Path(forbidden):
            raise AssertionError('input sentinel was opened')
sys.addaudithook(no_input_open)
if mode == 'reused':
    sys.modules['zuco'] = types.ModuleType('zuco')
sys.argv = [entry, '--submission', forbidden, '--review', forbidden,
            '--output', forbidden + '.out', '--help']
runpy.run_path(entry, run_name='__main__')
'''
        for task, relative in ENTRIES.items():
            for mode in ('fresh', 'reused'):
                with self.subTest(task=task, mode=mode):
                    result = subprocess.run(
                        [sys.executable, '-I', '-S', '-B', '-c', guarded,
                         str(root / relative), str(sentinel), mode],
                        cwd=self.cwd, text=True, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, timeout=10, check=False,
                    )
                    if mode == 'fresh':
                        self.assert_help(result)
                    else:
                        self.assert_refusal(result, 'fresh ZuCo scorer interpreter required')
                    self.assertNotIn('input sentinel was opened', result.stderr)
                    self.assertFalse(Path(str(sentinel) + '.out').exists())


if __name__ == '__main__':
    unittest.main()
