"""Metadata/dispatch integrity tests. No neural arrays, fits, Docker or model calls."""
import copy
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / 'src/neurobench/cli.py'
spec = importlib.util.spec_from_file_location('neurobench_delivery', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.build = self.root / 'reviews'
        self.build.mkdir(parents=True)
        self.path = self.root / 'benchmarks/neural/NEURAL-001/task.json'
        self.registry = {'schema_version': 1, 'kind': 'neuroscience_benchmark_registry',
                         'source_counts': {'paper': 0, 'neural': 1, 'total': 1},
                         'tasks': [{'id': 'NEURAL-001', 'track': 'neural',
                                    'task_directory': 'benchmarks/neural/NEURAL-001',
                                    'specification_id': 'NEURAL-001', 'specification_alias': False,
                                    'registration_class': 'canonical', 'runtime_manifest': None,
                                    'runtime_package': None}]}
        self.doc = {k: {} for k in module.COMMON}
        self.doc.update(schema_version=1, id='NEURAL-001', track='neural', title='Measured signal task',
                        status='specification_only', primary_outputs=['Finite aligned neural predictions'],
                        admission={'runnable': False, 'research_qualified': False})
        self.write(self.path, self.doc)

    def write(self, path, obj):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj))
        if path == self.path or path == getattr(self, 'runtime_path', None):
            row = self.registry['tasks'][0]
            key = 'specification' if path == self.path else 'runtime_manifest'
            row[key] = {'path': path.relative_to(self.root).as_posix(),
                        'bytes': path.stat().st_size, 'sha256': module.digest(path)}
            if key == 'runtime_manifest':
                row['runtime_package'] = path.parent.relative_to(self.root).as_posix()
            self.save_registry()

    def save_registry(self):
        path = self.root / 'benchmarks/registry.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.registry))

    def runtime(self):
        package = self.path.parent / 'implementations/fixture-runtime'
        package.mkdir(parents=True)
        script = package / 'score.py'; script.write_text('# Fixture only: never executed.\n')
        receipt = package / 'receipt.json'; self.write(receipt, {'status': 'passed'})
        self.runtime_path = package / 'manifest.json'
        self.runtime_doc = {'id': 'NEURAL-001', 'admission': {'runnable': True},
                            'verification': {'status': 'passed', 'receipt_path': str(receipt.relative_to(self.root)),
                                             'receipt_sha256': module.digest(receipt)},
                            'entrypoints': {'score': {'argv': ['python3', str(script.relative_to(self.root)),
                                                              '--submission', '{submission}', '--output', '{output}'],
                                                     'working_directory': '.', 'sha256': module.digest(script)}}}
        self.write(self.runtime_path, self.runtime_doc)
        self.submission = self.root / 'candidate file; literal.json'; self.submission.write_text('{}')
        self.output = self.root / 'new output'
        return script, receipt

    def test_specification_alone_does_not_become_a_benchmark(self):
        specifications, registered = module.specifications(self.root, complete=True)
        self.assertEqual(set(specifications), {'NEURAL-001'})
        self.assertEqual(set(registered), {'NEURAL-001'})
        self.assertEqual(module.runtime_manifests(self.root), {})
        with self.assertRaisesRegex(ValueError, 'No local scoring adapter'):
            module.score_command('NEURAL-001', 'x', 'y', self.root)

    def test_source_admission_promotion_rejected(self):
        self.doc['admission']['runnable'] = True; self.write(self.path, self.doc)
        with self.assertRaisesRegex(ValueError, 'cannot promote'):
            module.specifications(self.root)

    def test_inconsistent_declared_roster_rejected(self):
        self.registry['source_counts']['total'] = 200
        self.save_registry()
        with self.assertRaisesRegex(ValueError, 'totals disagree'):
            module.specifications(self.root, complete=True)

    def test_duplicate_registered_ids_rejected(self):
        self.registry['tasks'].append(copy.deepcopy(self.registry['tasks'][0]))
        self.save_registry()
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            module.specifications(self.root)

    def test_registered_specification_identity_mismatch_rejected(self):
        self.doc['id'] = 'NEURAL-999'
        self.write(self.path, self.doc)
        with self.assertRaisesRegex(ValueError, 'identity differs'):
            module.specifications(self.root)

    def test_unregistered_files_do_not_create_tasks(self):
        other = copy.deepcopy(self.doc); other['id'] = 'NEURAL-999'
        self.write(self.path.with_name('unregistered.json'), other)
        self.assertEqual(set(module.specifications(self.root)[0]), {'NEURAL-001'})

    def test_task_definition_drift_is_not_implicitly_re_pinned(self):
        self.path.write_text(self.path.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'source/evidence|size differs'):
            module.specifications(self.root)

    def test_runtime_declaration_drift_is_not_implicitly_re_pinned(self):
        self.runtime()
        self.runtime_path.write_text(self.runtime_path.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'source/evidence|size differs'):
            module.runtime_manifests(self.root)

    def test_valid_dispatch_preserves_literal_argument_boundaries(self):
        self.runtime()
        command, cwd = module.score_command('NEURAL-001', self.submission, self.output, self.root)
        self.assertEqual(command[3], str(self.submission))
        self.assertEqual(command[5], str(self.output))
        self.assertEqual(cwd, self.root)

    def reviewed_entry(self):
        self.runtime()
        self.runtime_doc['entrypoints']['score']['argv'] += [
            '--review', '{review}', '--other-reserve-bytes', '{other_reserve_bytes}']
        self.write(self.runtime_path, self.runtime_doc)
        review = self.root / 'review; literal $(touch NO).json'
        self.write(review, {'decision': 'synthetic_pending_not_authority'})
        return review

    def reviewed_command(self, review, reserve):
        return module.score_command('NEURAL-001', self.submission, self.output, self.root,
                                    review=review, other_reserve_bytes=reserve)

    def test_reviewed_score_argv_is_literal_without_execution_or_approval(self):
        review = self.reviewed_entry()
        with patch.object(module.subprocess, 'run', side_effect=AssertionError('No process allowed')):
            command, cwd = self.reviewed_command(review, 102000000)
        self.assertEqual(command[-4:], ['--review', str(review), '--other-reserve-bytes', '102000000'])
        self.assertEqual(cwd, self.root)
        self.assertFalse(self.output.exists())
        self.assertEqual(json.loads(review.read_text())['decision'], 'synthetic_pending_not_authority')

    def test_reviewed_scorer_requires_both_inputs_and_strict_integer_reserve(self):
        review = self.reviewed_entry()
        for path, reserve in [(None, None), (review, None), (None, 0), (review, -1),
                              (review, True), (review, '0'), (review, 1.5)]:
            with self.subTest(path=path, reserve=reserve), self.assertRaisesRegex(ValueError, 'requires --review'):
                self.reviewed_command(path, reserve)
        command, _ = self.reviewed_command(review, 0)
        self.assertEqual(command[-1], '0')

    def test_score_review_requires_canonical_regular_unlinked_in_repo_file(self):
        review = self.reviewed_entry()
        linked = self.root / 'linked_review.json'; linked.symlink_to(review)
        directory_link = self.root / 'linked_directory'; directory_link.symlink_to(self.build)
        child_review = self.build / 'nested_review.json'; self.write(child_review, {})
        hardlink_source = self.root / 'hardlink_source.json'; self.write(hardlink_source, {})
        hardlink = self.root / 'hardlinked_review.json'; os.link(hardlink_source, hardlink)
        for path in [linked, directory_link / child_review.name, hardlink,
                     self.root, self.root / 'missing.json', self.root.parent / 'outside.json',
                     self.build / '..' / '..' / '..' / review.name]:
            with self.subTest(path=path), self.assertRaises((ValueError, OSError)):
                self.reviewed_command(path, 0)

    def test_score_review_nonempty_bounded_file_inclusive_limit(self):
        review = self.reviewed_entry()
        for size in [0, 32769]:
            review.write_bytes(b' ' * size)
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, '32768 bytes'):
                self.reviewed_command(review, 0)
        # The task scorer, not this CLI, validates the contents and authority.
        review.write_bytes(b' ' * 32768)
        self.assertEqual(self.reviewed_command(review, 0)[0][-3], str(review))

    def test_score_review_placeholders_must_be_paired_once_and_unembedded(self):
        self.runtime()
        original = list(self.runtime_doc['entrypoints']['score']['argv'])
        for suffix in [['{review}'], ['{other_reserve_bytes}'],
                       ['{review}', '{review}', '{other_reserve_bytes}'],
                       ['{review}', '{other_reserve_bytes}', '{other_reserve_bytes}'],
                       ['--review={review}', '{other_reserve_bytes}'],
                       ['{review}', '--reserve={other_reserve_bytes}'],
                       ['{review!s}', '{other_reserve_bytes}'],
                       ['{review.__class__}', '{other_reserve_bytes}']]:
            self.runtime_doc['entrypoints']['score']['argv'] = original + suffix
            self.write(self.runtime_path, self.runtime_doc)
            with self.subTest(suffix=suffix), self.assertRaisesRegex(ValueError, 'placeholder'):
                module.score_command('NEURAL-001', self.submission, self.output, self.root)

    def test_legacy_score_preserved_and_undeclared_review_options_refused(self):
        self.runtime()
        self.runtime_doc['entrypoints']['score']['argv'] = [
            'python3', self.runtime_doc['entrypoints']['score']['argv'][1],
            '--submission={submission}', '--output={output}', '--other-reserve-bytes', '147000000']
        self.write(self.runtime_path, self.runtime_doc)
        command, _ = module.score_command('NEURAL-001', self.submission, self.output, self.root)
        self.assertEqual(command[2:], ['--submission=' + str(self.submission),
                                      '--output=' + str(self.output), '--other-reserve-bytes', '147000000'])
        for review, reserve in [(self.submission, None), (None, 0), (self.submission, 0)]:
            with self.subTest(review=review, reserve=reserve), self.assertRaisesRegex(ValueError, 'does not declare'):
                self.reviewed_command(review, reserve)

    def test_score_cli_forwards_review_pair_but_dry_run_executes_nothing(self):
        review = self.reviewed_entry()
        command = ['python3', 'fixture_wrapper.py', '--review', str(review)]
        args = ['neurobench.py', 'score', 'NEURAL-001', '--submission', str(self.submission),
                '--output', str(self.output), '--review', str(review), '--other-reserve-bytes', '7', '--dry-run']
        stdout = io.StringIO()
        with patch.object(module.sys, 'argv', args), \
             patch.object(module, 'score_command', return_value=(command, self.root)) as dispatch, \
             patch.object(module.subprocess, 'run', side_effect=AssertionError('No process allowed')), \
             redirect_stdout(stdout):
            self.assertEqual(module.main(), 0)
        dispatch.assert_called_once_with('NEURAL-001', str(self.submission), str(self.output),
                                         review=str(review), other_reserve_bytes=7)
        self.assertEqual(json.loads(stdout.getvalue()),
                         {'argv': command, 'working_directory': str(self.root), 'executed': False})

    def test_score_cli_execution_uses_argv_without_shell(self):
        self.runtime()
        command = ['python3', 'fixture_wrapper.py', '--submission', str(self.submission)]
        args = ['neurobench.py', 'score', 'NEURAL-001', '--submission', str(self.submission),
                '--output', str(self.output)]
        with patch.object(module.sys, 'argv', args), \
             patch.object(module, 'score_command', return_value=(command, self.root)), \
             patch.object(module.subprocess, 'run') as execute:
            execute.return_value.returncode = 17
            self.assertEqual(module.main(), 17)
        execute.assert_called_once_with(command, cwd=self.root, check=False)

    def test_receipt_drift_blocks_dispatch(self):
        _, receipt = self.runtime(); receipt.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'verification receipt'):
            module.score_command('NEURAL-001', self.submission, self.output, self.root)

    def test_entrypoint_drift_blocks_status_and_dispatch(self):
        script, _ = self.runtime(); script.write_text('# changed')
        with self.assertRaisesRegex(ValueError, 'scoring entrypoint'):
            module.score_command('NEURAL-001', self.submission, self.output, self.root)

    def test_existing_results_are_not_overwritten(self):
        self.runtime(); self.output.mkdir()
        with self.assertRaisesRegex(ValueError, 'fresh output'):
            module.score_command('NEURAL-001', self.submission, self.output, self.root)

    def test_shell_and_outside_entrypoint_rejected(self):
        self.runtime(); self.runtime_doc['entrypoints']['score']['argv'][0] = 'sh'
        self.write(self.runtime_path, self.runtime_doc)
        with self.assertRaisesRegex(ValueError, 'trusted Python'):
            module.score_command('NEURAL-001', self.submission, self.output, self.root)
        self.runtime_doc['entrypoints']['score']['argv'][1] = '../escape.py'
        self.write(self.runtime_path, self.runtime_doc)
        with self.assertRaisesRegex(ValueError, 'escapes'):
            module.score_command('NEURAL-001', self.submission, self.output, self.root)


if __name__ == '__main__':
    unittest.main()
