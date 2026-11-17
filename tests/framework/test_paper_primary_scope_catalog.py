"""Generated full-roster controls for declared, unqualified primary corrections."""
from contextlib import redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('primary_scope_catalog_fixture',
                                             ROOT / 'tests/framework/test_paper_outcomes_catalog.py')
fixture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_module)
binding, catalog, cli = fixture_module.binding, fixture_module.catalog, fixture_module.cli


class PrimaryScopeCatalogTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.PaperOutcomesCatalogTests('test_distinct_task_counts_four_unknown_cells_and_preserved_lineage')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.identifier = 'PAPER-002'
        self.before = catalog.discover(self.root)
        registry = self.fixture.registry()
        row = self.fixture.row(registry, self.identifier)
        home = row['task_directory']
        self.old_task_bytes = (self.root / row['paper_outcomes']['previous_specification']['path']).read_bytes()
        self.old_improvement_bytes = (self.root / row['specification_revision']['improvement_contract']['path']).read_bytes()
        self.correction = {
            'task_id': self.identifier, 'disposition': 'same_primary_unqualified',
            'primary_goal': 'Recreate the generated full primary panel and separately improve its same-task result.',
            'primary_scope': 'Generated primary panel [all units] with paired controls.',
            'remaining_source_limits': ['Full-panel source parameters remain unresolved.',
                                        'No original-data execution is supplied.'],
            'retained_secondary_scope': 'A partial aggregate is retained as source context only.',
            'retained_source_roles': {'partial_component': {'role': 'source_only', 'scientific_outcome': 'unknown',
                                                           'supports_primary': False, 'source_version': 1},
                                      'future_work': ['prospective extension only']},
            'paired_bundle_status': 'same_primary_unqualified', 'scientific_outcome': 'unknown',
        }
        self.scope = {'schema_version': binding.SCOPE_VERSION, 'entries': {
            task: {'task_id': task, 'primary_goal': 'Generated primary empirical finding',
                   'primary_scope': 'Generated primary finding panel',
                   'retained_secondary_scope': 'Generated separate secondary prediction',
                   'remaining_source_limits': ['Generated unresolved source fixture'],
                   'primary_same_task_improvement': 'unavailable_until_independently_justified',
                   'paired_bundle_status': 'unavailable_primary_secondary_scope_mismatch',
                   'scientific_outcome': 'unknown'} for task in binding.SCOPE_IDS},
            'same_primary_corrections': {self.identifier: self.correction}}
        registry['paper_outcomes']['scope_decisions'] = self.fixture.write(binding.SCOPE_PATH, self.scope)
        old = json.loads(self.old_task_bytes)
        improvement = json.loads(self.old_improvement_bytes)
        projected = binding.project_task(old, self.fixture.previous_rows[self.identifier], improvement,
                                         primary_correction=self.correction)
        row['specification'] = self.fixture.write(home + '/task.json', projected)
        descriptor_path = row['paper_outcomes']['outcomes']['path']
        descriptor = json.loads((self.root / descriptor_path).read_bytes())
        descriptor['original_task_sha256'] = row['specification']['sha256']
        row['paper_outcomes']['outcomes'] = self.fixture.write(descriptor_path, descriptor)
        self.fixture.save_registry(registry)

    def test_discovery_keeps_normal_bundle_and_distinct_task_counts(self):
        discovered = catalog.discover(self.root)
        row = self.fixture.row(discovered, self.identifier)
        outcomes = row['paper_outcomes']
        self.assertEqual(outcomes['availability'], 'available')
        self.assertEqual(outcomes['reproduction_eligibility'], 'source_unresolved')
        self.assertEqual(discovered['counts'], self.before['counts'])
        self.assertEqual(discovered['paper_outcome_counts'], self.before['paper_outcome_counts'])
        self.assertEqual(discovered['paper_outcome_counts']['primary_unavailable'], 0)
        self.assertEqual(outcomes['primary_scope_correction']['disposition'], 'same_primary_unqualified')
        self.assertEqual(outcomes['primary_scope_correction']['scientific_outcome'], 'unknown')
        self.assertTrue(all(cell['scientific_outcome'] == 'unknown' and cell['receipt'] is None
                            and cell['endpoint_eligible'] is False for cell in outcomes['cells']))
        self.assertEqual((self.root / outcomes['previous_specification']['path']).read_bytes(), self.old_task_bytes)
        self.assertEqual((self.root / outcomes['improvement_contract']['path']).read_bytes(), self.old_improvement_bytes)

    def test_task_page_and_links_show_exact_scope_limits_and_retained_roles(self):
        discovered = catalog.discover(self.root)
        page = catalog.render_tracks(discovered)['benchmarks/paper/' + self.identifier + '/README.md'].decode()
        self.assertIn('Corrected primary scope; outcomes remain unqualified.', page)
        self.assertIn(catalog.markdown_text(self.correction['primary_scope']), page)
        self.assertIn(self.correction['primary_goal'], page)
        for limit in self.correction['remaining_source_limits']:
            self.assertIn(limit, page)
        self.assertIn(self.correction['retained_secondary_scope'], page)
        self.assertIn('Partial component / Role', page)
        self.assertIn('Source only', page)
        self.assertIn('Prospective extension only', page)
        self.assertIn('Reviewed primary scope correction', page)
        self.assertNotIn('Primary reproduction and improvement outcomes are unavailable', page)
        self.assertNotIn('Reproduction proposal (inspection only)', page)
        self.assertIn(binding.SCOPE_PATH, set(catalog.source_links(discovered)))

    def test_cli_json_preserves_correction_without_executing_or_changing_contracts(self):
        with patch.object(cli.subprocess, 'run', side_effect=AssertionError('unexpected scientific execution')):
            report = cli.paper_outcomes(self.identifier, self.root)
            correction = report['summary']['primary_scope_correction']
            self.assertEqual(correction['primary_scope'], self.correction['primary_scope'])
            self.assertEqual(correction['scientific_outcome'], 'unknown')
            shown = cli.public_metadata_command('show', self.root, task_id=self.identifier)
            listed = cli.public_metadata_command('list', self.root, track='paper')
            implementations = cli.public_metadata_command('implementations', self.root, task_id=self.identifier)
            self.assertEqual(shown['catalog_entry']['paper_outcomes']['primary_scope_correction'], correction)
            self.assertEqual(next(row for row in listed if row['id'] == self.identifier)['paper_outcomes']['primary_scope_correction'], correction)
            self.assertEqual(implementations['paper_outcomes']['primary_scope_correction'], correction)
            self.assertEqual(cli.paper_contract(self.identifier, self.root), json.loads(self.old_improvement_bytes))
            self.assertEqual(cli.paper_contract(self.identifier, self.root, outcome='reproduction')['eligibility'], 'source_unresolved')

    def test_normal_receipt_route_refuses_unresolved_protocol_without_promoting_science(self):
        receipt = fixture_module.examples.receipt_for(self.fixture.outcomes, self.fixture.result)
        output = io.StringIO()
        with patch.object(cli.subprocess, 'run', side_effect=AssertionError('unexpected execution')), redirect_stdout(output):
            code = cli.main(['check-paper-outcome', self.identifier, '--receipt',
                             str(self.fixture.receipt_file(receipt))], root=self.root)
        response = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertFalse(response['metadata_admitted'])
        self.assertIsNone(response['criterion_satisfied'])
        self.assertEqual(response['scientific_outcome'], 'unknown')
        self.assertIn('paired protocol is unresolved', response['errors'])

    def test_generated_catalog_cannot_promote_or_misroute_correction(self):
        original = catalog.discover(self.root)
        mutations = [
            lambda row: row['paper_outcomes']['primary_scope_correction'].update(scientific_outcome='reproduced'),
            lambda row: row['paper_outcomes']['primary_scope_correction'].update(disposition='qualified'),
            lambda row: row['paper_outcomes']['primary_scope_correction']['root_scope_decision'].update(task_entry_id='PAPER-003'),
            lambda row: row['paper_outcomes'].update(reproduction_eligibility='eligible'),
            lambda row: row['paper_improvement'].update(disposition='improvement_ready'),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(original)
            mutate(self.fixture.row(changed, self.identifier))
            changed['paper_outcome_counts'] = catalog.paper_outcome_counts(changed['tasks'])
            changed['paper_improvement_counts'] = catalog.improvement_counts(changed['tasks'])
            with self.subTest(mutate=mutate), patch.object(catalog, 'render', side_effect=AssertionError('unexpected output generation')):
                with self.assertRaisesRegex(ValueError, 'Primary scope correction cannot qualify'):
                    catalog.generate(self.root, catalog=changed)

    def test_stale_scope_bytes_refuse_before_public_display(self):
        path = self.root / binding.SCOPE_PATH
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'pin mismatch'):
            cli.paper_outcomes(self.identifier, self.root)

    def test_supplied_view_cannot_replace_authenticated_scope_claims(self):
        original = catalog.discover(self.root)
        mutations = [
            lambda value: value.update(primary_goal='Invented replacement goal'),
            lambda value: value.update(primary_scope='Invented easier panel'),
            lambda value: value.update(retained_source_roles={'partial_component': 'claimed complete primary result'}),
            lambda value: value.update(retained_scope_notes='Invented source endorsement'),
            lambda value: value.update(remaining_source_limits=[]),
            lambda value: value['root_scope_decision'].update(raw_sha256='0' * 64),
            lambda value: value['retained_source_roles']['partial_component'].update(supports_primary=0),
            lambda value: value['retained_source_roles']['partial_component'].update(source_version=True),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(original)
            mutate(self.fixture.row(changed, self.identifier)['paper_outcomes']['primary_scope_correction'])
            with self.subTest(mutate=mutate), patch.object(catalog, 'render', side_effect=AssertionError('unexpected output generation')):
                with self.assertRaisesRegex(ValueError, 'Primary scope correction'):
                    catalog.generate(self.root, catalog=changed)
        changed = copy.deepcopy(original)
        self.fixture.row(changed, self.identifier)['specification']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Primary scope correction differs from the current registered task'):
            catalog.validate(changed, self.root)

    def test_correction_authentication_has_fresh_reads_and_cumulative_discovery_budget(self):
        original_read = catalog.Reader.read
        observed = []

        def observe(reader, path):
            result = original_read(reader, path)
            observed.append((reader, path.relative_to(reader.root).as_posix()))
            return result

        with patch.object(catalog.Reader, 'read', observe):
            discovered = catalog.discover(self.root)
        readers = {id(reader): reader for reader, _ in observed}
        self.assertEqual(len(readers), 1)
        discovery_reader = next(iter(readers.values()))
        paths = [path for _, path in observed]
        self.assertEqual(paths.count(catalog.REGISTRY), 2)
        self.assertEqual(paths.count(binding.SCOPE_PATH), 2)
        with patch.object(catalog, 'READ_LIMIT', discovery_reader.bytes - 1):
            with self.assertRaisesRegex(ValueError, 'metadata read limit exceeded'):
                catalog.discover(self.root)
        supplied_readers = []
        for _ in range(2):
            observed.clear()
            with patch.object(catalog.Reader, 'read', observe):
                catalog.validate(discovered, self.root)
            self.assertEqual([path for _, path in observed], [catalog.REGISTRY, binding.SCOPE_PATH])
            reader = observed[0][0]
            self.assertTrue(all(current is reader for current, _ in observed))
            self.assertIsNot(reader, discovery_reader)
            supplied_readers.append(reader)
        self.assertIsNot(supplied_readers[0], supplied_readers[1])

    def test_null_optional_notes_and_list_roles_remain_valid(self):
        registry = self.fixture.registry()
        self.correction['retained_secondary_scope'] = None
        self.correction['retained_source_roles'] = [{'component': 'partial source', 'role': 'unqualified context'}]
        registry['paper_outcomes']['scope_decisions'] = self.fixture.write(binding.SCOPE_PATH, self.scope)
        row = self.fixture.row(registry, self.identifier)
        projected = binding.project_task(json.loads(self.old_task_bytes), self.fixture.previous_rows[self.identifier],
                                         json.loads(self.old_improvement_bytes), primary_correction=self.correction)
        row['specification'] = self.fixture.write(row['specification']['path'], projected)
        descriptor_path = row['paper_outcomes']['outcomes']['path']
        descriptor = json.loads((self.root / descriptor_path).read_bytes())
        descriptor['original_task_sha256'] = row['specification']['sha256']
        row['paper_outcomes']['outcomes'] = self.fixture.write(descriptor_path, descriptor)
        self.fixture.save_registry(registry)
        discovered = catalog.discover(self.root)
        page = catalog.render_tracks(discovered)['benchmarks/paper/' + self.identifier + '/README.md'].decode()
        self.assertIn('Unqualified context', page)
        self.assertNotIn('**Retained source scope:**', page)
        self.assertNotIn('None', page)


if __name__ == '__main__':
    unittest.main()
