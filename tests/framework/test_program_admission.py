"""Synthetic metadata tests only; no candidate, scorer, Docker or science calls.

The fixture receipts are explicitly invented for validation tests. They are never
registered as qualification evidence in the real repository.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'neurobench.py'
spec = importlib.util.spec_from_file_location('neurobench_program_dispatch', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProgramMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        build = self.root / 'docs/neuroscience-benchmarks/build'
        for name, ident in [('paper_100.json', 'PAPER-X'), ('neural_100.json', 'NEURAL-095')]:
            self.write(build / name, {'tasks': [{'id': ident}]})
        self.write(build / 'implementation_status.json', {
            'packages': [], 'full_candidate_contracts_completed': 0,
            'research_qualified': 0, 'submission_ready': 0,
            'current_delivery': {'bounded_reference_ids': [], 'bounded_reference_candidate_ids': 0}})
        delivery = {key: {} for key in module.COMMON}
        delivery.update(schema_version=1, id='NEURAL-095', track='neural',
                        title='Synthetic metadata fixture', status='specification_only',
                        primary_outputs=['Synthetic fixture only'],
                        admission={'runnable': False, 'research_qualified': False})
        self.write(self.root / 'benchmarks/manifests/neural/NEURAL-095.json', delivery)
        self.manifest = self.root / 'benchmarks/neuroscience/neural-095/manifest.json'
        self.wrapper = self.root / 'authoring/fixture/execute_program.py'
        self.wrapper.parent.mkdir(parents=True)
        self.wrapper.write_text('raise AssertionError("fixture wrapper must never run")\n')
        self.helper = self.wrapper.with_name('helper.py')
        self.helper.write_text('# Frozen dependency fixture\n')
        self.freeze = self.wrapper.with_name('FREEZE.json')
        self.write(self.freeze, {'files': {self.rel(p): self.pin(p) for p in (self.wrapper, self.helper)}})
        self.qualification = self.wrapper.with_name('verification.json')
        self.write(self.qualification, {'candidate_id': 'NEURAL-095', 'status': 'passed',
                                       'controls': [{'name': 'positive_fixture', 'passed': True},
                                                    {'name': 'negative_fixture', 'passed': True}]})
        self.binding = self.wrapper.with_name('outer_started.json')
        self.write(self.binding, {'candidate_id': 'NEURAL-095',
                                 'source_freeze_sha256': self.sha(self.freeze)})
        self.receipt = self.wrapper.with_name('receipt.json')
        self.write(self.receipt, {'candidate_id': 'NEURAL-095', 'status': 'passed', 'returncode': 0,
                                 'verification_sha256': self.sha(self.qualification),
                                 'source_freeze_sha256': self.sha(self.freeze)})
        self.meta = {
            'entrypoint': {'argv': ['{python}', self.rel(self.wrapper), '--program', '{program}',
                                   '--out', '{output}'], 'sha256': self.sha(self.wrapper),
                           'working_directory': '.'},
            'source_freeze': {'path': self.rel(self.freeze), 'sha256': self.sha(self.freeze)},
            'verification': {'status': 'passed', 'receipt_path': self.rel(self.receipt),
                             'receipt_sha256': self.sha(self.receipt),
                             'qualification_path': self.rel(self.qualification),
                             'qualification_sha256': self.sha(self.qualification),
                             'source_binding_path': self.rel(self.binding),
                             'source_binding_sha256': self.sha(self.binding)}}
        self.doc = {'id': 'NEURAL-095', 'verification': {'status': 'not_qualified'},
                    'admission': {'runnable': False, 'research_qualified': False},
                    'program_execution': self.meta}
        self.save()
        self.program = self.root / 'literal candidate; $(touch NO).py'
        self.program.write_text('raise AssertionError("candidate must never be imported")\n')
        self.output = self.root / 'fresh output; literal'

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def rel(self, path):
        return path.relative_to(self.root).as_posix()

    def pin(self, path):
        return {'bytes': path.stat().st_size, 'sha256': self.sha(path)}

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def save(self):
        self.write(self.manifest, self.doc)

    def refresh_evidence_pin(self, kind, path):
        self.meta['verification'][kind + '_sha256'] = self.sha(path)
        self.save()

    def command(self):
        return module.run_command('NEURAL-095', self.program, self.output, self.root)

    def test_valid_command_is_literal_argv_and_executes_nothing(self):
        with patch.object(module.subprocess, 'run', side_effect=AssertionError('No process allowed')):
            command, cwd = self.command()
        self.assertEqual(command, [module.sys.executable, str(self.wrapper), '--program',
                                   str(self.program), '--out', str(self.output)])
        self.assertEqual(cwd, self.root)
        self.assertFalse(self.output.exists())

    def test_program_count_is_separate_from_score_and_research_counts(self):
        result = module.summary(self.root)
        self.assertEqual(result['local_program_runners_verified'], 1)
        self.assertEqual(result['program_runner_ids'], ['NEURAL-095'])
        self.assertEqual(result['local_score_adapters_verified'], 0)
        self.assertEqual(result['full_candidate_contracts_completed'], 0)
        self.assertEqual(result['research_qualified'], 0)

    def reviewed_entry(self):
        self.meta['entrypoint']['argv'] += ['--review', '{review}', '--other-reserve-bytes', '{other_reserve_bytes}']
        self.save()
        path = self.root / 'review; literal $(touch NO).json'
        self.write(path, {'decision': 'synthetic_pending_not_authority'})
        return path

    def test_reviewed_argv_is_literal_and_dry_construction_grants_no_authority(self):
        review = self.reviewed_entry()
        with patch.object(module.subprocess, 'run', side_effect=AssertionError('No process allowed')):
            command, _ = module.run_command('NEURAL-095', self.program, self.output, self.root,
                                            review=review, other_reserve_bytes=102000000)
        self.assertEqual(command[-4:], ['--review', str(review), '--other-reserve-bytes', '102000000'])
        self.assertFalse(self.output.exists())

    def test_reviewed_runner_requires_both_fresh_inputs(self):
        review = self.reviewed_entry()
        for path, reserve in [(None, None), (review, None), (None, 0), (review, -1), (review, True)]:
            with self.subTest(path=path, reserve=reserve), self.assertRaisesRegex(ValueError, 'requires --review'):
                module.run_command('NEURAL-095', self.program, self.output, self.root,
                                   review=path, other_reserve_bytes=reserve)

    def test_review_file_boundary_and_size(self):
        review = self.reviewed_entry()
        link = self.root / 'linked_review.json'; link.symlink_to(review)
        empty = self.root / 'empty_review.json'; empty.write_bytes(b'')
        huge = self.root / 'oversized_review.json'; huge.write_bytes(b' ' * 32769)
        for path in (link, empty, huge, self.root / '..' / 'outside_review.json', self.root):
            with self.subTest(path=path), self.assertRaises((ValueError, OSError)):
                module.run_command('NEURAL-095', self.program, self.output, self.root,
                                   review=path, other_reserve_bytes=0)

    def test_legacy_runner_does_not_silently_ignore_review_options(self):
        with self.assertRaisesRegex(ValueError, 'does not declare'):
            module.run_command('NEURAL-095', self.program, self.output, self.root,
                               review=self.wrapper, other_reserve_bytes=0)

    def test_review_placeholders_must_be_complete_unrepeated_and_unembedded(self):
        original = list(self.meta['entrypoint']['argv'])
        for suffix in (['{review}'], ['{other_reserve_bytes}'],
                       ['{review}', '{review}', '{other_reserve_bytes}'],
                       ['--review={review}', '{other_reserve_bytes}']):
            with self.subTest(suffix=suffix):
                self.meta['entrypoint']['argv'] = original + suffix; self.save()
                with self.assertRaisesRegex(ValueError, 'placeholder'):
                    module._program_entry(self.meta, self.root)

    def test_score_qualification_cannot_enable_program_execution(self):
        del self.doc['program_execution']
        self.doc['verification']['status'] = 'passed'
        self.doc['admission']['runnable'] = True
        self.save()
        with self.assertRaisesRegex(ValueError, 'separate passing qualification'):
            self.command()

    def test_unregistered_and_unknown_tasks_refuse(self):
        for task, text in [('PAPER-X', 'No local program runner'), ('NEURAL-unknown', 'Unknown canonical')]:
            with self.subTest(task=task), self.assertRaisesRegex(ValueError, text):
                module.run_command(task, self.program, self.output, self.root)

    def test_pending_program_verification_cannot_dispatch(self):
        self.meta['verification']['status'] = 'prepared_not_executed'
        self.save()
        with self.assertRaisesRegex(ValueError, 'separate passing qualification'):
            self.command()

    def test_pinned_but_failed_terminal_receipt_cannot_dispatch(self):
        value = json.loads(self.receipt.read_text())
        value['status'] = 'failed_preserved_no_retry'
        self.write(self.receipt, value)
        self.refresh_evidence_pin('receipt', self.receipt)
        with self.assertRaisesRegex(ValueError, 'passing terminal evidence'):
            self.command()

    def test_bool_is_not_a_successful_process_returncode(self):
        value = json.loads(self.receipt.read_text()); value['returncode'] = False
        self.write(self.receipt, value); self.refresh_evidence_pin('receipt', self.receipt)
        with self.assertRaisesRegex(ValueError, 'passing terminal evidence'):
            self.command()

    def test_candidate_identity_cannot_be_rebound_by_manifest(self):
        value = json.loads(self.binding.read_text()); value['candidate_id'] = 'NEURAL-007'
        self.write(self.binding, value); self.refresh_evidence_pin('source_binding', self.binding)
        with self.assertRaisesRegex(ValueError, 'candidate identity'):
            self.command()

    def test_terminal_must_hash_bind_control_receipt(self):
        value = json.loads(self.receipt.read_text()); value['verification_sha256'] = '0' * 64
        self.write(self.receipt, value); self.refresh_evidence_pin('receipt', self.receipt)
        with self.assertRaisesRegex(ValueError, 'bind the registered qualification'):
            self.command()

    def test_controls_must_be_nonempty_unique_and_explicitly_passed(self):
        original = json.loads(self.qualification.read_text())
        for controls in [[], [{'name': 'x', 'passed': 1}], [{'name': 'x', 'passed': False}],
                         [{'name': 'x', 'passed': True}, {'name': 'x', 'passed': True}], ['x']]:
            with self.subTest(controls=controls):
                value = copy.deepcopy(original); value['controls'] = controls
                self.write(self.qualification, value)
                self.meta['verification']['qualification_sha256'] = self.sha(self.qualification)
                terminal = json.loads(self.receipt.read_text())
                terminal['verification_sha256'] = self.sha(self.qualification)
                self.write(self.receipt, terminal); self.refresh_evidence_pin('receipt', self.receipt)
                with self.assertRaisesRegex(ValueError, 'uniquely named controls'):
                    self.command()

    def test_terminal_and_start_record_both_bind_source_freeze(self):
        for path, kind in [(self.receipt, 'receipt'), (self.binding, 'source_binding')]:
            original = path.read_text()
            with self.subTest(record=kind):
                value = json.loads(original); value['source_freeze_sha256'] = '0' * 64
                self.write(path, value); self.refresh_evidence_pin(kind, path)
                with self.assertRaisesRegex(ValueError, 'bind the registered source freeze'):
                    self.command()
                path.write_text(original); self.refresh_evidence_pin(kind, path)

    def test_dependency_drift_is_checked_even_when_wrapper_matches(self):
        self.helper.write_text('# Frozen dependency changed\n')
        with self.assertRaisesRegex(ValueError, 'size differs|changed program source'):
            self.command()

    def test_changed_receipt_bytes_fail_before_semantic_assertions(self):
        self.receipt.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'changed program source/evidence'):
            self.command()

    def test_wrapper_must_be_part_of_frozen_closure(self):
        value = json.loads(self.freeze.read_text()); del value['files'][self.rel(self.wrapper)]
        self.write(self.freeze, value)
        self.meta['source_freeze']['sha256'] = self.sha(self.freeze)
        for path, kind in [(self.receipt, 'receipt'), (self.binding, 'source_binding')]:
            value = json.loads(path.read_text()); value['source_freeze_sha256'] = self.sha(self.freeze)
            self.write(path, value); self.refresh_evidence_pin(kind, path)
        with self.assertRaisesRegex(ValueError, 'absent from the qualified source closure'):
            self.command()

    def test_shell_embedded_or_unknown_placeholders_and_repetitions_refuse(self):
        original = copy.deepcopy(self.meta['entrypoint'])
        variants = [
            ['sh', self.rel(self.wrapper), '{program}', '{output}'],
            ['python3', self.rel(self.wrapper), '--program={program}', '{output}'],
            ['python3', self.rel(self.wrapper), '{program}', '{output}', '{submission}'],
            ['python3', self.rel(self.wrapper), '{program}', '{program}', '{output}'],
            ['python3', self.rel(self.wrapper), '{program}', 'no-output-placeholder']]
        for argv in variants:
            with self.subTest(argv=argv):
                self.meta['entrypoint']['argv'] = argv; self.save()
                with self.assertRaises(ValueError):
                    self.command()
        self.meta['entrypoint'] = original

    def test_repository_escape_absolute_and_symlink_wrappers_refuse(self):
        link = self.wrapper.with_name('link.py'); link.symlink_to(self.wrapper)
        for relative in ['../outside.py', str(self.wrapper), self.rel(link)]:
            with self.subTest(path=relative):
                self.meta['entrypoint']['argv'][1] = relative; self.save()
                with self.assertRaisesRegex(ValueError, 'repository-relative|symlinks'):
                    self.command()

    def test_missing_nonfile_or_symlink_program_and_existing_output_refuse(self):
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, 'fresh output directory'):
            self.command()
        self.output.rmdir()
        for program in [self.root / 'missing', self.wrapper.parent]:
            with self.subTest(program=program), self.assertRaises((OSError, ValueError)):
                module.run_command('NEURAL-095', program, self.output, self.root)
        link = self.program.with_name('candidate_link.py'); link.symlink_to(self.program)
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            module.run_command('NEURAL-095', link, self.output, self.root)
        self.output.symlink_to(self.root / 'absent-target')
        with self.assertRaisesRegex(ValueError, 'fresh output directory'):
            self.command()

    def test_malformed_nested_metadata_refuses_without_attribute_errors(self):
        original = copy.deepcopy(self.doc)
        for field, value in [('program_execution', []), ('verification', []),
                             ('entrypoint', []), ('source_freeze', [])]:
            with self.subTest(field=field):
                self.doc = copy.deepcopy(original)
                if field == 'program_execution':
                    self.doc[field] = value
                else:
                    self.doc['program_execution'][field] = value
                self.save()
                with self.assertRaises(ValueError):
                    self.command()


if __name__ == '__main__':
    unittest.main()
