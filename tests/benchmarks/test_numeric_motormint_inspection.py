"""Generated source-only controls for explicit current MotorMINT inspection.

The complete pinned public closure is captured, but runtime modules, native
workers, protected review records, authentic datasets and campaigns are not run.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path('benchmarks/paper/PAPER-paper-method-011/implementations/paper-method-011/full-motormint-v1')
BINDING = Path('benchmarks/integrity/current-closures/numeric-motormint/CURRENT_INSPECTION.json')
SCORING = 'runtime/mintbench/scoring.py'


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


class MotorMintCurrentInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='motormint-current-inspection-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.unrelated = self.base / 'unrelated working directory'
        self.unrelated.mkdir()
        self.source = ROOT / PACKAGE
        self.binding = ROOT / BINDING
        self.binding_body = self.binding.read_bytes()
        self.selected = pin(self.binding_body)

    def invoke(self, *, command='inspect', extra=(), guard=None):
        operands = [str(self.source / 'run.py'), '--source-bytes', str(self.selected['bytes']),
                    '--source-sha256', self.selected['sha256'],
                    '--current-source-binding', str(self.binding), command, *extra]
        argv = [sys.executable, '-I', '-S', '-B']
        if guard is not None:
            argv += ['-c', guard]
        return subprocess.run(argv + operands, cwd=self.unrelated, capture_output=True,
                              text=True, timeout=15, check=False)

    def copied_source(self):
        original = json.loads((self.source / 'SOURCE_MANIFEST.json').read_bytes())
        destination = self.base / 'relocated package'
        for relative in ['SOURCE_MANIFEST.json', *original['files']]:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((self.source / relative).read_bytes())
        self.source = destination
        self.binding = self.base / 'external current binding.json'
        self.binding.write_bytes(self.binding_body)

    def rewrite_binding(self, value):
        self.binding_body = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
        self.binding.write_bytes(self.binding_body)
        self.selected = pin(self.binding_body)

    def assert_refused(self, result, text):
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn(text, result.stderr)

    def assert_report(self, process):
        self.assertEqual(process.returncode, 0, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report['task'], 'PAPER-paper-method-011')
        self.assertEqual(report['files'], 62)
        self.assertEqual(report['runtime_bodies'], 39)
        self.assertEqual(report['scope']['datasets'], 9)
        self.assertEqual(report['scope']['modules'], 17)
        self.assertEqual(report['scope']['original_gates'], 17)
        self.assertEqual(report['scope']['factorial_R2_cells'], 964)
        self.assertEqual(report['scope']['neuron_loss_group_R2_cells'], 14800)
        self.assertEqual(report['current_source_binding'], self.selected)
        self.assertEqual(report['source'], self.selected)
        self.assertEqual(report['source_kind'], 'current_inspection_binding')
        self.assertEqual(report['current_source_selection'], 'explicit_inspection_only')
        binding = json.loads(self.binding_body)
        self.assertEqual(report['historical_source_manifest'],
                         {key: binding['historical_manifest'][key] for key in ('bytes', 'sha256')})
        self.assertEqual(report['historical_runtime_manifest'],
                         pin((self.source / 'RUNTIME_MANIFEST.json').read_bytes()))
        self.assertEqual(report['current_runtime_overrides'],
                         [row for row in binding['overrides'] if row['path'] == SCORING])
        self.assertEqual(len(report['deferred_dependency_descriptors']), 10)
        for key in ('execution_authority', 'scientific_execution', 'qualified', 'deferred_bodies_opened'):
            self.assertFalse(report[key])
        routes = report['canonical_source_routes']
        self.assertEqual(routes['status'], 'not_selected_for_current_inspection')
        self.assertFalse(routes['qualification_or_runtime_admission'])
        self.assertFalse(routes['deferred_bodies_read'])

    def test_current_source_inspection_from_unrelated_working_directory(self):
        self.assert_report(self.invoke())

    def test_complete_source_membership_is_relocatable_with_explicit_binding(self):
        self.copied_source()
        self.assert_report(self.invoke())

    def test_prepare_and_run_refuse_before_protected_review_access(self):
        guard = '''import runpy, sys
entry = sys.argv[1]
def reject_review(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)) and 'must-not-read-review' in str(args[0]):
        raise AssertionError('protected review was opened')
sys.addaudithook(reject_review)
sys.argv = sys.argv[1:]
runpy.run_path(entry, run_name='__main__')
'''
        for command in ('prepare', 'run'):
            with self.subTest(command=command):
                result = self.invoke(command=command, guard=guard,
                                     extra=('--review', str(self.base / 'must-not-read-review'),))
                self.assert_refused(result, 'Current source binding is inspection only')
                self.assertNotIn('protected review was opened', result.stderr)
                self.assertNotIn('No such file or directory', result.stderr)

    def test_same_size_source_tamper_is_refused_before_runtime_execution(self):
        self.copied_source()
        source = self.source / SCORING
        body = source.read_bytes()
        source.write_bytes(b'#' + body[1:])
        self.assertEqual(source.stat().st_size, len(body))
        self.assert_refused(self.invoke(), 'changed bootstrap content')

    def test_same_size_descriptor_tamper_is_refused_by_selected_pin(self):
        self.copied_source()
        body = self.binding.read_bytes()
        changed = body.replace(b'"schema"', b'"schemA"', 1)
        self.assertNotEqual(changed, body)
        self.assertEqual(len(changed), len(body))
        self.binding.write_bytes(changed)
        self.assert_refused(self.invoke(), 'changed bootstrap content')

    def test_replacement_scope_cannot_add_traversal_or_deferred_member(self):
        self.copied_source()
        original = json.loads(self.binding_body)
        for name in ('../outside.py', 'runtime/mintbench/catalog.py',
                     'shared/docs/neuroscience-benchmarks/build/exposure_audit.json'):
            with self.subTest(name=name):
                value = json.loads(json.dumps(original))
                value['overrides'][0]['path'] = name
                self.rewrite_binding(value)
                self.assert_refused(self.invoke(), 'exact current inspection replacement members')

    def test_duplicate_replacement_and_wrong_historical_pin_are_refused(self):
        self.copied_source()
        original = json.loads(self.binding_body)
        duplicate = json.loads(json.dumps(original))
        duplicate['overrides'][1] = duplicate['overrides'][0]
        self.rewrite_binding(duplicate)
        self.assert_refused(self.invoke(), 'exact current inspection replacement members')
        wrong = json.loads(json.dumps(original))
        wrong['overrides'][0]['historical']['sha256'] = '0' * 64
        self.rewrite_binding(wrong)
        self.assert_refused(self.invoke(), 'historical replacement identity')

    def test_symlinked_binding_and_runtime_source_are_refused(self):
        self.copied_source()
        original_binding = self.binding.with_name('ordinary-binding.json')
        self.binding.rename(original_binding)
        self.binding.symlink_to(original_binding)
        self.assertNotEqual(self.invoke().returncode, 0)
        self.binding.unlink()
        original_binding.rename(self.binding)
        scorer = self.source / SCORING
        original_scorer = scorer.with_name('ordinary-scoring.py')
        scorer.rename(original_scorer)
        scorer.symlink_to(original_scorer)
        self.assertNotEqual(self.invoke().returncode, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
