"""Generated source controls. No real study, model, data or artifact execution."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('generated_study_controls', HERE / 'generated_examples.py')
examples = importlib.util.module_from_spec(spec)
spec.loader.exec_module(examples)
v = examples.validator


def seal(binding):
    """Reseal inline metadata to test joins independently of pin checking."""
    for manifest in binding['case_manifests']:
        raw = v.canonical(v.case_content(manifest))
        pin = binding['artifacts'][manifest['artifact']]['pin']
        pin.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        for row in binding['assignments']:
            if row['case_manifest_id'] == manifest['id']:
                row['case_manifest_sha256'] = pin['sha256']
    raw = v.canonical(binding['assignments'])
    binding['artifacts'][binding['pairing']['assignment_manifest_artifact']]['pin'].update(
        bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


class BindingTests(unittest.TestCase):
    def reject(self, mutate, reason, track='paper', reseal=False):
        binding = examples.make(track)
        mutate(binding)
        if reseal:
            seal(binding)
        with self.assertRaisesRegex(ValueError, reason):
            v.validate(binding)

    def test_complete_generated_paper_and_neural(self):
        for track, attempts, pairs, cases in [('paper', 24, 12, 12), ('neural', 32, 8, 8)]:
            with self.subTest(track=track):
                result = v.validate(examples.make(track))
                self.assertEqual(result['status'], 'description_consistent_not_qualified')
                self.assertEqual((result['assigned_attempts'], result['paired_blocks'], result['declared_cases']),
                                 (attempts, pairs, cases))
                self.assertEqual(result['referenced_artifacts_opened'], 0)
                for name in ('execution_authorized', 'scientific_qualification', 'submission_readiness',
                             'budgets_enforced', 'artifact_bytes_authenticated', 'declared_review_independence_verified'):
                    self.assertIs(result[name], False)

    def test_schema_export_exact(self):
        self.assertEqual(json.loads((HERE / 'binding.schema.json').read_text()), v.SCHEMA)

    def test_strict_tokens_reject_terminal_newlines(self):
        changes = [
            lambda b: b.__setitem__('study_id', b['study_id'] + '\n'),
            lambda b: b['artifacts']['analysis-code']['pin'].__setitem__('sha256', b['artifacts']['analysis-code']['pin']['sha256'] + '\n'),
            lambda b: b['budget_profiles'][0].__setitem__('currency', 'USD\n'),
            lambda b: b['budget_profiles'][0].__setitem__('pricing_timestamp', '2000-01-01T00:00:00Z\n'),
            lambda b: b['artifacts']['analysis-code']['pin'].__setitem__('locator', 'urn:generated-control:analysis-code\n'),
            lambda b: b['case_manifests'][0]['cases'][0].__setitem__('id', 'GENERATED-CASE-0\n'),
        ]
        for index, mutate in enumerate(changes):
            with self.subTest(index=index):
                self.reject(mutate, 'invalid text pattern|text extent', reseal=True)
        schema = json.loads((HERE / 'binding.schema.json').read_text())
        token_shapes = [
            (schema['properties']['study_id'], 'GENERATED-PAPER'),
            (schema['properties']['artifacts']['additionalProperties']['properties']['pin']['properties']['sha256'], 'a' * 64),
            (schema['properties']['budget_profiles']['items']['properties']['currency'], 'USD'),
        ]
        for shape, good in token_shapes:
            v.schema_check(good, shape)
            for suffix in ('\n', '\r\n', '\x00'):
                with self.subTest(good=good, suffix=repr(suffix)):
                    with self.assertRaises(ValueError): v.schema_check(good + suffix, shape)

    def test_endpoint_applicability_denominators_join_task_and_phase(self):
        for track in ('paper', 'neural'):
            binding = examples.make(track)
            for contrast in binding['contrasts']:
                self.assertEqual(contrast['estimand']['assigned_pairs'], 4)
                for scope in contrast['estimand']['endpoint_applicability'].values():
                    self.assertEqual(scope['assigned_pairs'], 2)
                    self.assertEqual(len(scope['assigned_pair_ids']), 2)
            def scope(b):
                return next(iter(b['contrasts'][0]['estimand']['endpoint_applicability'].values()))
            changes = [
                (lambda b: scope(b).__setitem__('task_id', b['tasks'][1]['id']), 'task/phase applicability'),
                (lambda b: scope(b).__setitem__('phase', 'not-the-contrast-phase'), 'task/phase applicability'),
                (lambda b: scope(b).__setitem__('assigned_pairs', 4), 'Endpoint failure denominator'),
                (lambda b: scope(b)['assigned_pair_ids'].pop(), 'Endpoint applicable pairs'),
                (lambda b: scope(b)['assigned_pair_ids'].append(scope(b)['assigned_pair_ids'][0]), 'Duplicate endpoint assigned pair'),
                (lambda b: b['contrasts'][0]['estimand']['endpoint_applicability'].pop(next(iter(b['contrasts'][0]['estimand']['endpoint_applicability']))), 'cover exactly'),
            ]
            for mutate, reason in changes:
                with self.subTest(track=track, reason=reason): self.reject(mutate, reason, track, reseal=True)
            def unrelated_task_pairs(b):
                phase = b['contrasts'][0]['phase']
                scope(b)['assigned_pair_ids'] = sorted({row['pair_id'] for row in b['assignments'] if row['phase'] == phase})
                scope(b)['assigned_pairs'] = len(scope(b)['assigned_pair_ids'])
            self.reject(unrelated_task_pairs, 'Endpoint applicable pairs', track, reseal=True)

    def test_duplicate_undirected_overlap_edge_rejected(self):
        for reverse in (False, True):
            def duplicate(b):
                edge = copy.deepcopy(b['corpus']['overlap_edges'][0])
                if reverse: edge['families'].reverse()
                b['corpus']['overlap_edges'].append(edge)
            with self.subTest(reverse=reverse): self.reject(duplicate, 'Duplicate undirected')

    def test_reject_unbound_draft_or_wrong_template(self):
        for key, value, reason in [('format', 'neurobench.paired-study-draft.v1', 'fixed policy'),
                                   ('state', 'DRAFT_UNBOUND_NOT_EXECUTABLE', 'fixed policy'),
                                   ('template_sha256', 'f' * 64, 'source template')]:
            with self.subTest(key=key):
                self.reject(lambda b: b.__setitem__(key, value), reason)
        with self.assertRaisesRegex(ValueError, 'missing required'):
            v.validate({'format': 'neurobench.paired-study-draft.v1'})

    def test_required_fields_placeholders_types_and_authority(self):
        changes = [
            (lambda b: b['corpus'].__setitem__('limitations', 'TBD'), 'placeholder'),
            (lambda b: b['analysis'].__setitem__('claim_scope', None), 'unknown option'),
            (lambda b: b.__setitem__('surprise', True), 'unexpected field'),
            (lambda b: b['budget_profiles'][0].__setitem__('wall_seconds', True), 'wrong type'),
            (lambda b: b['analysis']['paired_uncertainty'].__setitem__('level', float('nan')), 'finite number'),
            (lambda b: b['corpus'].pop('selection_artifact'), 'missing required'),
            (lambda b: b['authority'].__setitem__('scientific_qualification', True), 'fixed policy'),
        ]
        for mutate, reason in changes:
            with self.subTest(reason=reason): self.reject(mutate, reason)

    def test_duplicate_ids_and_unknown_artifacts(self):
        for field in ('tasks', 'case_manifests', 'arms', 'budget_profiles', 'model_scaffolds', 'contrasts'):
            with self.subTest(field=field):
                self.reject(lambda b: b[field][1 if len(b[field]) > 1 else 0].__setitem__('id', b[field][0]['id'])
                            if len(b[field]) > 1 else b[field].append(copy.deepcopy(b[field][0])), 'Duplicate')
        self.reject(lambda b: b['tasks'][0].__setitem__('revision_artifact', 'missing-artifact'), 'Unknown artifact')
        self.reject(lambda b: b['artifacts']['common-information']['review'].__setitem__('reviewer_id', 'GENERATED-AUTHOR'), 'self-review')

    def test_case_pins_and_complete_task_phase_join(self):
        self.reject(lambda b: b['case_manifests'][0]['cases'][0].__setitem__('id', 'changed'), 'metadata pin')
        self.reject(lambda b: b['case_manifests'].pop(), 'Incomplete task/phase')
        self.reject(lambda b: b['case_manifests'][0].__setitem__('task_revision_sha256', 'a' * 64), 'Case/task revision', reseal=True)
        self.reject(lambda b: b['case_manifests'][0]['cases'][1].__setitem__('id', b['case_manifests'][0]['cases'][0]['id']), 'Duplicate case', reseal=True)
        self.reject(lambda b: b['case_manifests'][0]['cases'][0].__setitem__('independent_unit_id', 'not-a-unit'), 'Unknown independent', reseal=True)

    def test_assignment_pins_and_revision_joins(self):
        self.reject(lambda b: b['assignments'][0].__setitem__('run_index', 1), 'assignments do not match')
        for field in ('task_revision_sha256', 'case_manifest_id'):
            with self.subTest(field=field):
                value = 'b' * 64 if field.endswith('sha256') else 'unknown-manifest'
                self.reject(lambda b: b['assignments'][0].__setitem__(field, value), 'revision join', reseal=True)
        self.reject(lambda b: b['assignments'].pop(), 'complete frozen matrix', reseal=True)

    def test_assignment_duplicates_pair_integrity_and_order(self):
        def semantic_duplicate(b):
            duplicate = copy.deepcopy(b['assignments'][0]); duplicate['id'] = 'different-id'
            b['assignments'][1] = duplicate
        self.reject(semantic_duplicate, 'Duplicate assignment cell', reseal=True)
        self.reject(lambda b: b['assignments'][0].__setitem__('pair_id', 'split-pair'), 'Incomplete or incompatible paired', reseal=True)
        self.reject(lambda b: b['assignments'][0].__setitem__('condition_order', 1), 'full permutation', reseal=True)
        self.reject(lambda b: b['assignments'][0].__setitem__('id', b['assignments'][1]['id']), 'Duplicate assignment', reseal=True)

    def test_matched_resources_and_paper_access(self):
        self.reject(lambda b: b['arms'][0]['budget_ids'].__setitem__('reproduction', ['budget-improvement_development']), 'resources must match')
        self.reject(lambda b: b['assignments'][0].__setitem__('budget_ids', ['budget-improvement_development']), 'overrides matched', reseal=True)
        self.reject(lambda b: b['arms'][1].__setitem__('common_information_artifact', 'sanitized-code'), 'Unmatched common')
        self.reject(lambda b: b['arms'][0].__setitem__('official_code_artifact', 'sanitized-code'), 'intervention is not bound')
        def aliased_code(b):
            b['artifacts']['sanitized-code']['pin'] = copy.deepcopy(b['artifacts']['common-information']['pin'])
        self.reject(aliased_code, 'same artifact')

    def test_neural_budget_and_mode_interventions(self):
        def llm_in_program(b):
            next(x for x in b['budget_profiles'] if x['id'] == 'numerical-common')['model_calls'] = 1
        self.reject(llm_in_program, 'Frozen assessment', 'neural')
        self.reject(lambda b: b['arms'][1]['budget_ids'].__setitem__('assessment', ['numerical-common', 'numerical-common']), 'Duplicate arm budget', 'neural')
        self.reject(lambda b: b['arms'][0].__setitem__('mode', 'case_investigation'), 'mode mismatch', 'neural')
        self.reject(lambda b: b['arms'][0].__setitem__('specialist_tool_artifact', 'specialist-checkpoint-interface'), 'Specialist access', 'neural')
        self.reject(lambda b: b['track_policy']['neural'].__setitem__('equal_total_expenditure_claim', True), 'no permitted shape', 'neural')

    def test_primary_estimand_and_failure_denominators(self):
        self.reject(lambda b: b['contrasts'][0]['estimand'].__setitem__('assigned_pairs', 3), 'failure denominator')
        self.reject(lambda b: b['failure_accounting'].__setitem__('assigned_attempt_count', 23), 'drops assigned')
        self.reject(lambda b: b['contrasts'][0]['estimand']['endpoint_ids'].pop(), 'every declared endpoint')
        self.reject(lambda b: b['contrasts'][0]['estimand'].__setitem__('missingness_policy_artifact', 'analysis-code'), 'missingness policies')
        self.reject(lambda b: b['analysis']['exploratory_contrast_ids'].append('official_code_reproduction'), 'partition incomplete')
        self.reject(lambda b: b['analysis']['multiplicity']['family'].append('official_code_end_to_end_improvement'), 'Multiplicity family')
        self.reject(lambda b: b['contrasts'][0].__setitem__('arms', ['paper_data', 'paper_data_code']), 'declared comparison')

    def test_primary_neural_mode_cannot_be_removed(self):
        def only_specialist(b):
            b['analysis']['primary_contrast_ids'] = ['specialist_given_program']
            b['analysis']['exploratory_contrast_ids'] = [c['id'] for c in b['contrasts'] if c['id'] != 'specialist_given_program']
        self.reject(only_specialist, 'mode effect must be primary', 'neural')

    def test_independence_and_dependence_contract(self):
        self.reject(lambda b: b['analysis'].__setitem__('repeats_are_independent_units', True), 'fixed policy')
        self.reject(lambda b: b['analysis']['dependence_groups'][0]['case_keys'].pop(), 'membership mismatch')
        self.reject(lambda b: b['analysis'].__setitem__('aggregation_order', ['case', 'task', 'independent_unit', 'source_family']), 'respect declared independence')

    def test_protected_exposure_and_retrospective_description(self):
        for track in ('paper', 'neural'):
            b = examples.make(track)
            final = b['case_manifests'][-1]['cases'][0]['exposure_unit_id']
            b['exposure']['unit_status'][final] = 'unresolved'
            with self.subTest(track=track):
                with self.assertRaisesRegex(ValueError, 'Exposure overlap/unresolved'): v.validate(b)
                b['exposure']['confirmation_claim'] = 'retrospective_development'
                self.assertEqual(v.validate(b)['status'], 'description_consistent_not_qualified')
        b = examples.make('neural')
        old = b['case_manifests'][-1]['cases'][0]['exposure_unit_id']
        b['case_manifests'][-1]['cases'][0]['exposure_unit_id'] = b['case_manifests'][0]['cases'][0]['exposure_unit_id']
        del b['exposure']['unit_status'][old]; seal(b)
        with self.assertRaisesRegex(ValueError, 'Exposure overlap/unresolved'): v.validate(b)

    def test_retry_and_outcome_selection_rejections(self):
        self.reject(lambda b: b['failure_accounting'].__setitem__('outcome_dependent_retry_or_drop', True), 'fixed policy')
        self.reject(lambda b: b['failure_accounting'].__setitem__('retry_limit', 1), 'lacks classes/budget')
        self.reject(lambda b: b['selection_and_stopping'].__setitem__('assessment_feedback_used', True), 'fixed policy')
        self.reject(lambda b: b['selection_and_stopping'].__setitem__('maximum_assigned_attempts', 23), 'assignment or budget mismatch')
        self.reject(lambda b: b['selection_and_stopping'].__setitem__('search_budget_id', 'budget-improvement_confirmation'), 'matched development budget')

    def test_sequential_rules_and_complete_primary_denominator(self):
        b = examples.make('paper'); s = b['selection_and_stopping']; s['design'] = 'sequential'
        with self.assertRaisesRegex(ValueError, 'lacks prespecified'): v.validate(b)
        s['sequential'] = {'rule_artifact': 'precision-rationale', 'validity_review_artifact': 'multiplicity-policy', 'look_after_pair_counts': [2, 4]}
        self.assertEqual(v.validate(b)['status'], 'description_consistent_not_qualified')
        for looks in ([2, 3], [2, 2, 4], [4, 2]):
            s['sequential']['look_after_pair_counts'] = looks
            with self.subTest(looks=looks):
                with self.assertRaisesRegex(ValueError, 'complete primary-pair'): v.validate(b)

    def test_cli_loads_only_the_supplied_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'binding.json'; binding = examples.make('paper')
            for artifact in binding['artifacts'].values():
                artifact['pin']['locator'] = 'file:///FORBIDDEN-PRIVATE-ARTIFACT'
                artifact['review']['evidence']['locator'] = 'https://invalid.example/NEVER-FETCH'
            path.write_bytes(v.canonical(binding))
            opened = []; real_open = os.open
            def guarded_open(name, *args, **kwargs):
                self.assertEqual(Path(name), path); opened.append(name)
                return real_open(name, *args, **kwargs)
            with mock.patch.object(v.os, 'open', side_effect=guarded_open), mock.patch('builtins.open', side_effect=AssertionError('unexpected open')), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(v.main([str(path)]), 0)
            self.assertEqual(len(opened), 1)
            self.assertEqual(json.loads(output.getvalue())['referenced_artifacts_opened'], 0)

    def test_loader_duplicate_keys_nonfinite_symlink_and_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.json'
            for raw, message in [(b'{"x":1,"x":2}', 'Duplicate JSON field'), (b'{"x":NaN}', 'Nonfinite JSON')]:
                path.write_bytes(raw)
                with self.subTest(message=message):
                    with self.assertRaisesRegex(ValueError, message): v.load_binding(path)
            link = Path(tmp) / 'link.json'; link.symlink_to(path)
            with self.assertRaises(OSError): v.load_binding(link)
            path.write_bytes(b'')
            with self.assertRaisesRegex(ValueError, 'ordinary nonempty'): v.load_binding(path)
            path.write_bytes(b'12345678')
            with mock.patch.object(v, 'INPUT_LIMIT', 4):
                with self.assertRaisesRegex(ValueError, 'ordinary nonempty'): v.load_binding(path)

    def test_end_to_end_generated_commands_and_rejected_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'generated'
            generator = subprocess.run([sys.executable, '-I', '-S', '-B', str(HERE / 'generated_examples.py'), '--output', str(out)], capture_output=True, text=True)
            self.assertEqual(generator.returncode, 0, generator.stderr)
            self.assertIs(json.loads(generator.stdout)['real_study_bound'], False)
            for track in ('paper', 'neural'):
                path = out / (track + '.generated.json')
                call = subprocess.run([sys.executable, '-I', '-S', '-B', str(HERE / 'validate_study.py'), str(path)], capture_output=True, text=True)
                self.assertEqual(call.returncode, 0, call.stderr)
                self.assertEqual(json.loads(call.stdout)['track'], track)
            bad = Path(tmp) / 'unbound.json'; bad.write_text('{"format":"draft"}')
            call = subprocess.run([sys.executable, '-I', '-S', '-B', str(HERE / 'validate_study.py'), str(bad)], capture_output=True, text=True)
            self.assertEqual(call.returncode, 2)
            self.assertEqual(json.loads(call.stderr)['status'], 'rejected_description')


if __name__ == '__main__':
    unittest.main()
