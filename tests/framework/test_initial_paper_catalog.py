"""Initial paper definitions must add source scope without inventing a predecessor."""
from contextlib import redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
IDENTIFIER = 'PAPER-NEW-001'
DIRECTORY = 'benchmarks/paper/' + IDENTIFIER
INITIAL = 'paper-improvement/initial-v1'
REGISTRATION = 'docs/provenance/registrations/paper-initial/' + IDENTIFIER + '.json'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


fixtures = module('initial_paper_catalog_fixtures', ROOT / 'tests/framework/test_paper_catalog_binding.py')
catalog, cli = fixtures.catalog, fixtures.cli
builder, engine = fixtures.builder, fixtures.engine
put = fixtures.binding_fixture.put


class InitialPaperCatalogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        fixtures.catalog_fixture.fixture(self.root)
        self.original_registry = (self.root / builder.REGISTRY).read_bytes()
        registry = json.loads(self.original_registry)
        for row in registry['tasks']:
            if row['track'] == 'paper':
                put(self.root, row['task_directory'] + '/improvement.v1.json',
                    fixtures.binding_fixture.contract(row['id']))
        builder.write_or_check(self.root, validator=engine.contract_validate)
        self.legacy_ids = {row['id'] for row in registry['tasks'] if row['track'] == 'paper'}
        contract = fixtures.binding_fixture.contract(IDENTIFIER)
        contract['legacy'] = {'role': 'no_predecessor', 'original_task': None,
                              'notes': 'Initial task; no earlier benchmark definition existed.'}
        contract_pin = self.write_pin(DIRECTORY + '/improvement.v1.json', contract)
        document = {'schema_version': 1, 'id': IDENTIFIER, 'track': 'paper',
                    'title': 'New source-paper improvement fixture', 'status': 'source_unresolved',
                    'objective': builder.OBJECTIVE, 'input_assets': {},
                    'evaluation': {'objective': builder.OBJECTIVE, 'contract': contract_pin,
                                   'disposition': 'source_unresolved', 'reproduction_role': 'not_applicable'},
                    'admission': {'runnable': False, 'research_qualified': False, 'submission_ready': False}}
        specification = self.write_pin(DIRECTORY + '/task.json', document)
        initial_pin = self.write_pin(REGISTRATION, {
            'schema_version': INITIAL, 'task_id': IDENTIFIER, 'source_commit': 'a' * 40,
            'specification': specification, 'improvement_contract': contract_pin})
        registry = self.registry()
        row = catalog.task_row(IDENTIFIER, document['title'], 'paper', specification,
                               'registered_construction_draft', REGISTRATION, document)
        row.update(registration_class='expansion', original_specification=specification,
                   specification_revision={'version': INITIAL, 'improvement_contract': contract_pin,
                                           'initial_registration': initial_pin},
                   scientific_readiness='source_unresolved', submission_readiness='not_qualified_by_binding')
        registry['tasks'].append(row)
        registry['historical_registries'].append(initial_pin)
        registry['paper_improvement']['registered_count'] += 1
        for key in ('paper', 'total', 'expansion_drafts'):
            registry['source_counts'][key] += 1
        self.save_registry(registry)
        self.saved = {path: (self.root / path).read_bytes() for path in
                      (builder.REGISTRY, builder.SNAPSHOT, DIRECTORY + '/task.json',
                       DIRECTORY + '/improvement.v1.json', REGISTRATION)}

    def write_pin(self, path, value):
        return builder.pin(path, put(self.root, path, value))

    def registry(self):
        return json.loads((self.root / builder.REGISTRY).read_bytes())

    def save_registry(self, value):
        put(self.root, builder.REGISTRY, value)

    def row(self, registry, identifier=IDENTIFIER):
        return next(row for row in registry['tasks'] if row['id'] == identifier)

    def restore(self):
        for path, body in self.saved.items():
            put(self.root, path, body)

    def rebind(self, *, task_mutation=None, contract_mutation=None, snapshot_mutation=None):
        """Repin all initial metadata so tests reach semantic checks, not stale hashes."""
        registry = self.registry()
        row = self.row(registry)
        document = json.loads((self.root / DIRECTORY / 'task.json').read_bytes())
        contract = json.loads((self.root / DIRECTORY / 'improvement.v1.json').read_bytes())
        if contract_mutation:
            contract_mutation(contract)
        contract_pin = self.write_pin(DIRECTORY + '/improvement.v1.json', contract)
        document['evaluation']['contract'] = contract_pin
        if task_mutation:
            task_mutation(document)
        specification = self.write_pin(DIRECTORY + '/task.json', document)
        row['specification'] = row['original_specification'] = specification
        row['declared_specification_status'] = document['status']
        row['specification_revision']['improvement_contract'] = contract_pin
        snapshot = {'schema_version': INITIAL, 'task_id': IDENTIFIER, 'source_commit': 'a' * 40,
                    'specification': copy.deepcopy(specification), 'improvement_contract': copy.deepcopy(contract_pin)}
        if snapshot_mutation:
            snapshot_mutation(snapshot)
        initial_pin = self.write_pin(REGISTRATION, snapshot)
        row['specification_revision']['initial_registration'] = initial_pin
        registry['historical_registries'] = [initial_pin if item['path'] == REGISTRATION else item
                                            for item in registry['historical_registries']]
        self.save_registry(registry)

    def mutate_previous_snapshot(self, mutate):
        registry = self.registry()
        snapshot = json.loads((self.root / builder.SNAPSHOT).read_bytes())
        mutate(snapshot)
        registry['paper_improvement']['pre_improvement_registry'] = self.write_pin(builder.SNAPSHOT, snapshot)
        self.save_registry(registry)

    def test_117th_paper_preserves_original_116_and_canonical_100(self):
        result = catalog.discover(self.root)
        self.assertEqual(result['counts']['paper'], 117)
        self.assertEqual(result['counts']['total'], 235)
        self.assertEqual(result['counts']['canonical_specifications'], 200)
        self.assertEqual(sum(row['track'] == 'paper' and row['registration_class'] == 'canonical'
                             for row in result['tasks']), 100)
        self.assertEqual(result['paper_improvement_counts']['registered'], 117)
        self.assertEqual(result['paper_improvement_counts']['covered'], 117)
        self.assertEqual(result['paper_improvement_counts']['improvement_ready'], 0)
        self.assertEqual((self.root / builder.SNAPSHOT).read_bytes(), self.original_registry)
        self.assertEqual({row['id'] for row in result['tasks'] if row['track'] == 'paper'
                          and row['paper_improvement']['historical_specification']}, self.legacy_ids)
        new = self.row(result)
        self.assertIsNone(new['paper_improvement']['historical_specification'])
        self.assertFalse((self.root / DIRECTORY / 'historical').exists())
        self.assertEqual(new['scientific_readiness'], 'unknown')

    def test_initial_navigation_links_snapshot_without_fabricating_history(self):
        result = catalog.generate(self.root)
        links = set(catalog.source_links(result))
        self.assertIn(REGISTRATION, links)
        self.assertIn(DIRECTORY + '/improvement.v1.json', links)
        self.assertNotIn(DIRECTORY + '/' + builder.HISTORY, links)
        page = (self.root / DIRECTORY / 'README.md').read_text()
        self.assertIn('Initial source-paper task registration (no predecessor)', page)
        self.assertNotIn('historical/task.pre-improvement', page)
        self.assertEqual(catalog.generate(self.root, check=True), result)

    def test_initial_cli_contract_keeps_same_task_guard_and_construction_role(self):
        with patch.object(cli.subprocess, 'run', side_effect=AssertionError('unexpected execution')):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(cli.main(['paper-contract', IDENTIFIER], root=self.root), 0)
            contract = json.loads(output.getvalue())
            self.assertEqual(contract['legacy']['role'], 'no_predecessor')
            self.assertEqual(engine.validate_contract(contract, task_id=IDENTIFIER), [])
            sources = cli.public_metadata_command('implementations', self.root, task_id=IDENTIFIER)
        self.assertEqual(sources['evaluation_role'], 'same_task_improvement_construction')
        with self.assertRaisesRegex(ValueError, 'same-task source-paper superiority'):
            cli.require_paper_role(self.row(self.registry()), calibration=False)

    def test_initial_roster_requires_correct_typed_registered_count(self):
        original = self.registry()
        for count in (116, 117.0, True):
            current = copy.deepcopy(original)
            current['paper_improvement']['registered_count'] = count
            self.save_registry(current)
            with self.subTest(count=count), self.assertRaises(ValueError):
                catalog.discover(self.root)

    def test_old_task_cannot_be_removed_or_relabelled_as_initial(self):
        current = self.registry()
        old = self.row(current, 'PAPER-EXP-0-0')
        current['tasks'].remove(old)
        for key in ('paper', 'total', 'expansion_drafts'):
            current['source_counts'][key] -= 1
        current['paper_improvement']['registered_count'] -= 1
        self.save_registry(current)
        def remove_and_recount(snapshot):
            snapshot['tasks'].remove(self.row(snapshot, old['id']))
            for key in ('paper', 'total', 'expansion_drafts'):
                snapshot['source_counts'][key] -= 1
        self.mutate_previous_snapshot(remove_and_recount)
        with self.assertRaisesRegex(ValueError, 'original paper registrations|roster counts'):
            catalog.discover(self.root)
        self.restore()
        current = self.registry()
        old = self.row(current, 'PAPER-EXP-0-0')
        old['specification_revision'] = copy.deepcopy(self.row(current)['specification_revision'])
        self.save_registry(current)
        with self.assertRaisesRegex(ValueError, 'original registration roster|historical task'):
            catalog.discover(self.root)

    def test_prior_snapshot_counts_are_complete_exact_integers(self):
        mutations = [lambda d: d.update(schema_version=True),
                     lambda d: d['source_counts'].update(paper=116.0),
                     lambda d: d['source_counts'].pop('neural'),
                     lambda d: d['source_counts'].update(total=True),
                     lambda d: d['source_counts'].update(canonical_specifications=199),
                     lambda d: d['source_counts'].update(expansion_drafts=33)]
        for index, mutate in enumerate(mutations):
            self.restore()
            self.mutate_previous_snapshot(mutate)
            with self.subTest(index=index), self.assertRaises(ValueError):
                catalog.discover(self.root)

    def test_initial_snapshot_rehashed_semantic_forgery_refuses(self):
        mutations = [lambda d: d.update(task_id='PAPER-001'),
                     lambda d: d.update(schema_version='paper-improvement/v1'),
                     lambda d: d.update(source_commit='not-a-commit'),
                     lambda d: d.update(previous_specification={'path': 'invented-history.json'}),
                     lambda d: d['specification'].update(sha256='f' * 64),
                     lambda d: d['improvement_contract'].update(bytes=0)]
        for index, mutate in enumerate(mutations):
            self.restore()
            self.rebind(snapshot_mutation=mutate)
            with self.subTest(index=index), self.assertRaises(ValueError):
                catalog.discover(self.root)

    def test_unpinned_snapshot_or_contract_bytes_refuse(self):
        for path in (REGISTRATION, DIRECTORY + '/improvement.v1.json'):
            self.restore()
            (self.root / path).write_bytes((self.root / path).read_bytes() + b' ')
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'pin mismatch'):
                cli.paper_contract(IDENTIFIER, self.root)

    def test_initial_task_cannot_claim_execution_or_scientific_admission(self):
        for key in ('runnable', 'research_qualified', 'submission_ready'):
            self.restore()
            self.rebind(task_mutation=lambda d: d['admission'].update({key: True}))
            with self.subTest(key=key), self.assertRaises(ValueError):
                catalog.discover(self.root)

    def test_initial_contract_cannot_fabricate_history_or_admission(self):
        mutations = [lambda d: d['legacy'].update(role='calibration_only', original_task=builder.HISTORY),
                     lambda d: d['legacy'].update(original_task=builder.HISTORY),
                     lambda d: d.update(task_id='PAPER-001'),
                     lambda d: d.update(disposition='improvement_ready'),
                     lambda d: d.update(exposure={'final_targets_allowed_for_training': True})]
        for index, mutate in enumerate(mutations):
            self.restore()
            self.rebind(contract_mutation=mutate)
            with self.subTest(index=index), self.assertRaises(ValueError):
                catalog.discover(self.root)

    def test_initial_current_evaluation_has_exact_noncalibration_binding(self):
        mutations = [lambda d: d['evaluation'].update(reproduction_role='calibration_only'),
                     lambda d: d['evaluation'].update(calibration={'historical_task': 'invented.json'}),
                     lambda d: d['evaluation'].update(disposition='design_ready'),
                     lambda d: d.update(objective='reproduce_source_paper'),
                     lambda d: d.update(status='improvement_ready')]
        for index, mutate in enumerate(mutations):
            self.restore()
            self.rebind(task_mutation=mutate)
            with self.subTest(index=index), self.assertRaises(ValueError):
                catalog.discover(self.root)

    def test_initial_snapshot_must_be_enrolled_and_identity_must_be_new(self):
        original = self.registry()
        mutations = [lambda d: d.update(historical_registries=[p for p in d['historical_registries']
                                                              if p['path'] != REGISTRATION]),
                     lambda d: self.row(d).update(specification_alias=True),
                     lambda d: self.row(d).update(registration_class='canonical'),
                     lambda d: self.row(d)['original_specification'].update(path='retired/fake-source.json')]
        for index, mutate in enumerate(mutations):
            current = copy.deepcopy(original)
            mutate(current)
            self.save_registry(current)
            with self.subTest(index=index), self.assertRaises(ValueError):
                catalog.discover(self.root)

    def test_initial_task_requires_explicit_id_and_track(self):
        mutations = [lambda d: d.update(candidate_id=d.pop('id')),
                     lambda d: d.pop('track')]
        for index, mutate in enumerate(mutations):
            self.restore()
            self.rebind(task_mutation=mutate)
            with self.subTest(index=index), self.assertRaises(ValueError):
                catalog.discover(self.root)

    def test_initial_snapshot_pin_is_closed_and_exactly_enrolled(self):
        original = self.registry()
        current = copy.deepcopy(original)
        self.row(current)['specification_revision']['initial_registration']['extra_claim'] = 'qualified'
        self.save_registry(current)
        with self.assertRaises(ValueError):
            catalog.discover(self.root)
        current = copy.deepcopy(original)
        next(pin for pin in current['historical_registries'] if pin['path'] == REGISTRATION)['extra_claim'] = 'qualified'
        self.save_registry(current)
        with self.assertRaises(ValueError):
            catalog.discover(self.root)

    def test_initial_contract_pin_cannot_gain_unchecked_fields(self):
        current = self.registry()
        row = self.row(current)
        pin = row['specification_revision']['improvement_contract']
        pin['extra_claim'] = 'qualified'
        document = json.loads((self.root / DIRECTORY / 'task.json').read_bytes())
        document['evaluation']['contract'] = pin
        row['specification'] = row['original_specification'] = self.write_pin(DIRECTORY + '/task.json', document)
        registration = json.loads((self.root / REGISTRATION).read_bytes())
        registration.update(specification=row['specification'], improvement_contract=pin)
        initial_pin = self.write_pin(REGISTRATION, registration)
        row['specification_revision']['initial_registration'] = initial_pin
        current['historical_registries'] = [initial_pin if item['path'] == REGISTRATION else item
                                            for item in current['historical_registries']]
        self.save_registry(current)
        with self.assertRaises(ValueError):
            catalog.discover(self.root)

    def test_historical_contract_cannot_adopt_new_no_predecessor_profile(self):
        current = self.registry()
        row = self.row(current, 'PAPER-001')
        contract_path = row['specification_revision']['improvement_contract']['path']
        contract = json.loads((self.root / contract_path).read_bytes())
        contract['legacy'] = {'role': 'no_predecessor', 'original_task': None,
                              'notes': 'This is not valid for a preserved historical task.'}
        contract_pin = self.write_pin(contract_path, contract)
        row['specification_revision']['improvement_contract'] = contract_pin
        document = json.loads((self.root / row['specification']['path']).read_bytes())
        document['evaluation']['contract'] = contract_pin
        row['specification'] = self.write_pin(row['specification']['path'], document)
        self.save_registry(current)
        with self.assertRaises(ValueError):
            catalog.discover(self.root)


if __name__ == '__main__':
    unittest.main()
