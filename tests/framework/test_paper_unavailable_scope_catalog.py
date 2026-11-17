"""Generated full-roster checks for neutral, incomplete primary-pairing markers."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('neutral_scope_catalog_fixture',
                                             ROOT / 'tests/framework/test_paper_outcomes_catalog.py')
fixture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_module)
binding, catalog, cli = fixture_module.binding, fixture_module.catalog, fixture_module.cli


class UnavailableScopeCatalogTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.PaperOutcomesCatalogTests('test_distinct_task_counts_four_unknown_cells_and_preserved_lineage')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.identifier = 'PAPER-002'
        self.before = catalog.discover(self.root)
        self.scope = {'schema_version': binding.SCOPE_VERSION,
                      'entries': {identifier: self.entry(identifier, neutral=False) for identifier in binding.SCOPE_IDS}}
        self.markers = {}
        self.adopt(self.identifier, neutral=True, proposal=True)

    def entry(self, identifier, *, neutral):
        result = {
            'task_id': identifier, 'primary_goal': 'Recreate the complete generated original primary panel.',
            'primary_scope': 'Generated original population [all units] and required companion controls.',
            'retained_secondary_scope': ('The retained contract declares the original target for the documented subset; complete paired coverage is unresolved.'
                                         if neutral else 'A distinct generated secondary prediction is retained.'),
            'remaining_source_limits': ['No complete primary pairing or original-data qualification is supplied.'],
            'primary_same_task_improvement': 'unavailable_until_independently_justified',
            'paired_bundle_status': ('unavailable_complete_primary_pairing' if neutral
                                     else 'unavailable_primary_secondary_scope_mismatch'),
            'scientific_outcome': 'unknown',
        }
        if neutral:
            result['adoption_route'] = 'full_primary_pairing_unavailable'
        return result

    def adopt(self, identifier, *, neutral, proposal=False):
        self.markers[identifier] = neutral, proposal
        self.scope['entries'][identifier] = self.entry(identifier, neutral=neutral)
        registry = self.fixture.registry()
        scope_pin = self.fixture.write(binding.SCOPE_PATH, self.scope)
        registry['paper_outcomes']['scope_decisions'] = scope_pin
        for task_id, (is_neutral, has_proposal) in self.markers.items():
            row = self.fixture.row(registry, task_id)
            home = row['task_directory']
            old = json.loads((self.root / row['paper_outcomes']['previous_specification']['path']).read_bytes())
            improvement = json.loads((self.root / row['specification_revision']['improvement_contract']['path']).read_bytes())
            entry = self.scope['entries'][task_id]
            projected = binding.project_task(old, self.fixture.previous_rows[task_id], improvement, entry)
            row['specification'] = self.fixture.write(home + '/task.json', projected)
            marker = {
                'schema_version': binding.UNAVAILABLE, 'task_id': task_id,
                'original_task_sha256': row['specification']['sha256'], 'status': 'unavailable',
                'reason_code': ('full_primary_pairing_unavailable' if is_neutral else 'primary_secondary_scope_mismatch'),
                'reason': ('Complete original-result pairing is unresolved.' if is_neutral else 'The generated primary and secondary targets differ.'),
                'primary_scope': entry['primary_scope'],
                'retained_secondary_improvement': {
                    'path': 'improvement.v1.json',
                    'raw_sha256': row['specification_revision']['improvement_contract']['sha256'],
                    'contract_digest': fixture_module.engine.contract_digest(improvement),
                    'scope_description': entry['retained_secondary_scope']},
                'root_scope_decision': {'path': binding.SCOPE_PATH, 'raw_sha256': scope_pin['sha256'],
                                        'task_entry_id': task_id},
            }
            if has_proposal:
                reproduction = fixture_module.unresolved_contract(improvement)
                reproduction['same_task']['target']['description'] = entry['primary_scope']
                pin = self.fixture.write(home + '/reproduction.v1.json', reproduction)
                row['paper_outcomes']['reproduction_contract'] = pin
                marker['reproduction_proposal'] = {'path': 'reproduction.v1.json', 'raw_sha256': pin['sha256'],
                                                   'contract_digest': fixture_module.engine.contract_digest(reproduction)}
            else:
                row['paper_outcomes'].pop('reproduction_contract', None)
            row['paper_outcomes']['outcomes'] = self.fixture.write(home + '/outcomes.v1.json', marker)
        self.fixture.save_registry(registry)

    def test_neutral_view_reports_exact_coverage_without_secondary_claim(self):
        discovered = catalog.discover(self.root)
        row = self.fixture.row(discovered, self.identifier)
        self.assertEqual(discovered['counts'], self.before['counts'])
        self.assertEqual(discovered['paper_outcome_counts']['covered'], 117)
        self.assertEqual(discovered['paper_outcome_counts']['primary_unavailable'], 1)
        self.assertTrue(all(cell['scientific_outcome'] == 'unknown' and cell['receipt'] is None
                            and cell['endpoint_eligible'] is False and cell['condition_available'] is False
                            for cell in row['paper_outcomes']['cells']))
        page = catalog.render_tracks(discovered)[row['task_directory'] + '/README.md'].decode()
        self.assertIn('Retained improvement contract coverage', page)
        self.assertIn(catalog.markdown_text(self.scope['entries'][self.identifier]['retained_secondary_scope']), page)
        self.assertIn('## Retained improvement contract', page)
        self.assertIn('Primary outcome pairing decision', page)
        self.assertNotIn('secondary policy', page)
        self.assertNotIn('different or narrower scientific question', page)
        counts = catalog.paper_count_text(discovered)
        self.assertIn('Complete primary-outcome pairing is unavailable for **1 tasks**', counts)
        self.assertNotIn('explicit scientific scope mismatch', counts)
        self.assertNotIn('retained secondary', counts)

    def test_old_marker_rendering_remains_distinct_in_mixed_catalog(self):
        self.adopt('PAPER-003', neutral=False)
        discovered = catalog.discover(self.root)
        row = self.fixture.row(discovered, 'PAPER-003')
        page = catalog.render_tracks(discovered)[row['task_directory'] + '/README.md'].decode()
        self.assertIn('**Retained secondary policy:**', page)
        self.assertIn('## Retained secondary improvement policy', page)
        self.assertIn('different or narrower scientific question', page)
        self.assertIn('Primary and retained secondary scope decision', page)
        counts = catalog.paper_count_text(discovered)
        self.assertIn('**1 tasks** with an explicit scientific scope mismatch', counts)
        self.assertIn('Complete primary-outcome pairing is unavailable for **1 tasks**', counts)
        self.assertEqual(discovered['paper_outcome_counts']['primary_unavailable'], 2)
        self.assertEqual(discovered['counts']['total'], 235)

    def test_cli_inspection_stays_unknown_and_primary_admission_refuses_before_receipt(self):
        with patch.object(cli.subprocess, 'run', side_effect=AssertionError('unexpected execution')):
            report = cli.paper_outcomes(self.identifier, self.root)
            self.assertEqual(report['summary']['reason_code'], 'full_primary_pairing_unavailable')
            self.assertEqual(report['summary']['scientific_outcomes'], {'reproduction': 'unknown', 'improvement': 'unknown'})
            self.assertEqual(cli.paper_contract(self.identifier, self.root, outcome='reproduction')['eligibility'], 'source_unresolved')
            with patch.object(cli, '_outcome_receipt', side_effect=AssertionError('unexpected receipt read')):
                for command in (lambda: cli.paper_contract(self.identifier, self.root),
                                lambda: cli.compare_paper(self.identifier, self.root / 'missing.json', self.root),
                                lambda: cli.check_paper_outcome(self.identifier, self.root / 'missing.json', self.root)):
                    with self.assertRaisesRegex(ValueError, 'Current .* admission is unavailable'):
                        command()

    def test_actual_marker_cannot_exchange_status_reason_mapping(self):
        registry = self.fixture.registry()
        row = self.fixture.row(registry, self.identifier)
        relative = row['paper_outcomes']['outcomes']['path']
        marker = json.loads((self.root / relative).read_bytes())
        marker['reason_code'] = 'primary_secondary_scope_mismatch'
        row['paper_outcomes']['outcomes'] = self.fixture.write(relative, marker)
        self.fixture.save_registry(registry)
        with self.assertRaisesRegex(ValueError, 'Unavailable marker does not bind'):
            catalog.discover(self.root)

    def test_supplied_neutral_view_must_match_source_identity_and_full_summary(self):
        original = catalog.discover(self.root)
        mutations = [
            lambda row: row.update(title='Invented replacement title'),
            lambda row: row['specification'].update(sha256='0' * 64),
            lambda row: row['paper_outcomes'].update(reason='Invented source decision'),
            lambda row: row['paper_outcomes'].update(primary_scope='Invented reduced panel'),
            lambda row: row['paper_outcomes']['retained_secondary_improvement'].update(scope_description='Claimed full qualified result'),
            lambda row: row['paper_outcomes']['root_scope_decision'].update(raw_sha256='0' * 64),
            lambda row: row['paper_outcomes']['cells'][0].update(receipt=False),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(original)
            mutate(self.fixture.row(changed, self.identifier))
            with self.subTest(mutate=mutate), patch.object(catalog, 'render', side_effect=AssertionError('unexpected render')):
                with self.assertRaises(ValueError):
                    catalog.generate(self.root, catalog=changed)
        self.adopt('PAPER-003', neutral=False)
        changed = catalog.discover(self.root)
        self.fixture.row(changed, 'PAPER-003')['paper_outcomes']['reason_code'] = 'full_primary_pairing_unavailable'
        with self.assertRaisesRegex(ValueError, 'Unavailable outcome reason differs from authenticated source route'):
            catalog.generate(self.root, catalog=changed)

    def test_source_neutral_route_cannot_be_relabelled_or_omitted(self):
        original = catalog.discover(self.root)
        mutations = [
            lambda row: row['paper_outcomes'].update(reason_code='primary_secondary_scope_mismatch'),
            lambda row: row['paper_outcomes'].update(availability='available'),
            lambda row: row['paper_outcomes'].pop('reason_code'),
            lambda row: row.pop('paper_outcomes'),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(original)
            mutate(self.fixture.row(changed, self.identifier))
            changed['paper_outcome_counts'] = catalog.paper_outcome_counts(changed['tasks'])
            with self.subTest(mutate=mutate), self.assertRaisesRegex(ValueError, 'Neutral unavailable source classification'):
                catalog.validate(changed, self.root)
        for remove_task in (False, True):
            changed = copy.deepcopy(original)
            if remove_task:
                changed['tasks'] = [row for row in changed['tasks'] if row['id'] != self.identifier]
            else:
                for row in changed['tasks']:
                    row.pop('paper_outcomes', None)
            changed['counts'].update(catalog.counts(changed['tasks']))
            changed['paper_outcome_counts'] = catalog.paper_outcome_counts(changed['tasks'])
            changed['paper_improvement_counts'] = catalog.improvement_counts(changed['tasks'])
            with self.subTest(remove_task=remove_task), self.assertRaisesRegex(ValueError, 'Neutral unavailable source'):
                catalog.validate(changed, self.root)

    def test_validation_authenticates_callbacks_and_preserves_cumulative_bound(self):
        self.adopt('PAPER-004', neutral=True, proposal=False)
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
        with patch.object(catalog, 'READ_LIMIT', discovery_reader.bytes - 1):
            with self.assertRaisesRegex(ValueError, 'metadata read limit exceeded'):
                catalog.discover(self.root)
        supplied_readers = []
        for _ in range(2):
            observed.clear()
            with patch.object(catalog.Reader, 'read', observe):
                catalog.validate(discovered, self.root)
            paths = [path for _, path in observed]
            self.assertEqual(paths.count(catalog.REGISTRY), 1)
            self.assertEqual(paths.count(binding.SNAPSHOT), 1)
            self.assertEqual(paths.count(binding.SCOPE_PATH), 2)
            self.assertEqual(len(paths), len(set(paths)) + 1)
            supplied_readers.append(observed[0][0])
        self.assertIsNot(supplied_readers[0], supplied_readers[1])
        print(json.dumps({'generated_neutral_tasks': 2, 'validation_added_read_bytes': supplied_readers[0].bytes,
                          'validation_reads': len(paths), 'validation_unique_paths': len(set(paths)),
                          'cumulative_discovery_read_bytes': discovery_reader.bytes}))
        path = self.root / binding.SCOPE_PATH
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'pin mismatch'):
            catalog.validate(discovered, self.root)

    def test_scope_mutation_within_validation_is_reauthenticated(self):
        discovered = catalog.discover(self.root)
        original_read = catalog.Reader.read
        scope_path = self.root / binding.SCOPE_PATH
        scope_reads = []

        def mutate_after_read(reader, path):
            result = original_read(reader, path)
            if path == scope_path:
                scope_reads.append(path)
                if len(scope_reads) == 1:
                    path.write_bytes(path.read_bytes() + b' ')
            return result

        with patch.object(catalog.Reader, 'read', mutate_after_read), \
             patch.object(catalog, 'render', side_effect=AssertionError('unexpected output generation')):
            with self.assertRaisesRegex(ValueError, 'pin mismatch'):
                catalog.generate(self.root, catalog=discovered)
        self.assertEqual(len(scope_reads), 2)


if __name__ == '__main__':
    unittest.main()
