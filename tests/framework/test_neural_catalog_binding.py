"""Independent catalog/CLI controls for versioned neural source definitions.

The scientific validator is a small stub here: these tests exercise registry,
history and current-definition binding without substituting synthetic science
for the dedicated neural contract validator's own tests.
"""
from contextlib import redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
VERSION = 'neural-understanding/v1'
OBJECTIVE = 'infer_neural_or_behavioral_targets_from_permitted_observations'
SNAPSHOT = 'docs/provenance/registrations/neural-pre-understanding-v1.json'
HISTORY = 'historical/task.pre-understanding.v1.json'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


fixture = module('neural_catalog_public_fixture', ROOT / 'tests/framework/test_catalog.py')
catalog, cli = fixture.catalog, fixture.cli


def pin(path, raw):
    return {'path': path, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def put(root, path, value):
    raw = (json.dumps(value, sort_keys=True) + '\n').encode()
    destination = root / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    return pin(path, raw)


def contract(identifier):
    modes = {}
    for name in ('direct_observation', 'typed_viewer', 'tool_assisted', 'frozen_program'):
        modes[name] = {
            'status': 'source_available' if name == 'frozen_program' else 'not_delivered',
            'representation': 'Permitted observations only.',
            'boundary': 'Targets stay with the evaluator.',
            'missing': ['Current transport and native qualification.'],
        }
    return {'schema_version': VERSION, 'task_id': identifier, 'objective': OBJECTIVE,
            'disposition': 'partial_delivery',
            'disposition_reason': 'A source programme does not deliver every condition.',
            'primary_target': 'Infer the prespecified held-out observation target.',
            'access_modes': modes}


def validate_contract(document, task_id=None):
    expected = {'schema_version': VERSION, 'objective': OBJECTIVE, 'task_id': task_id}
    return ['wrong contract identity'] if any(document.get(key) != value
                                              for key, value in expected.items()) else []


class NeuralCatalogBindingTests(unittest.TestCase):
    @fixture.pre_endpoint_selection_fixture
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        fixture.fixture(self.root)
        self.original_registry = (self.root / catalog.REGISTRY).read_bytes()
        registry = json.loads(self.original_registry)
        destination = self.root / SNAPSHOT
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.original_registry)
        self.original_tasks = {}
        for row in registry['tasks']:
            if row['track'] != 'neural':
                continue
            original = (self.root / row['specification']['path']).read_bytes()
            self.original_tasks[row['id']] = original
            historical_path = row['task_directory'] + '/' + HISTORY
            (self.root / historical_path).parent.mkdir(parents=True)
            (self.root / historical_path).write_bytes(original)
            previous = pin(historical_path, original)
            current_contract = put(self.root, row['task_directory'] + '/understanding.v1.json',
                                   contract(row['id']))
            document = json.loads(original)
            document.update(objective=OBJECTIVE, track='neural', status='specification_only')
            document['evaluation'] = {'neural_understanding': {
                'schema_version': VERSION, 'objective': OBJECTIVE,
                'contract_path': 'understanding.v1.json',
                'contract_sha256': current_contract['sha256'],
                'original_definition_path': HISTORY,
                'original_definition_sha256': previous['sha256'],
            }}
            row['specification'] = put(self.root, row['specification']['path'], document)
            row.update(declared_specification_status='specification_only',
                       specification_revision={'version': VERSION, 'previous_specification': previous,
                                               'understanding_contract': current_contract})
        registry['neural_understanding'] = {
            'schema_version': VERSION, 'objective': OBJECTIVE, 'coverage_required': True,
            'registered_count': 118, 'pre_understanding_registry': pin(SNAPSHOT, self.original_registry),
        }
        self.save_registry(registry)
        original_companion = catalog.companion_module
        engine = SimpleNamespace(validate_contract=validate_contract, summary=copy.deepcopy)
        patcher = patch.object(catalog, 'companion_module',
                               side_effect=lambda name: engine if name == 'neural_understanding'
                               else original_companion(name))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.object(cli, 'public_catalog_module', return_value=catalog)
        patcher.start()
        self.addCleanup(patcher.stop)

    def registry(self):
        return json.loads((self.root / catalog.REGISTRY).read_bytes())

    def save_registry(self, value):
        put(self.root, catalog.REGISTRY, value)

    def row(self, registry, identifier='NEURAL-001'):
        return next(row for row in registry['tasks'] if row['id'] == identifier)

    def edit_task(self, registry, mutate, identifier='NEURAL-001'):
        row = self.row(registry, identifier)
        doc = json.loads((self.root / row['specification']['path']).read_bytes())
        mutate(doc)
        row['specification'] = put(self.root, row['specification']['path'], doc)
        self.save_registry(registry)

    def test_complete_coverage_preserves_history_and_separates_access_from_readiness(self):
        result = catalog.discover(self.root)
        self.assertEqual(result['neural_understanding_counts']['covered'], 118)
        self.assertEqual(result['neural_understanding_counts']['dispositions'], {'partial_delivery': 118})
        self.assertEqual(result['scientific_readiness'], 'unknown')
        self.assertEqual(result['submission_readiness'], 'unknown')
        self.assertEqual(sum(row['specification_alias'] for row in result['tasks']), 3)
        self.assertEqual((self.root / SNAPSHOT).read_bytes(), self.original_registry)
        self.assertFalse((self.root / catalog.OUTPUT).exists())
        for row in result['tasks']:
            if row['track'] != 'neural':
                self.assertNotIn('neural_understanding', row)
                continue
            self.assertEqual((self.root / row['neural_understanding']['historical_specification']['path']).read_bytes(),
                             self.original_tasks[row['id']])
            self.assertEqual(row['scientific_readiness'], 'unknown')
            self.assertEqual(row['submission_readiness'], 'unknown')
            self.assertIsNone(row['local_program_runner_verified'])
            modes = row['neural_understanding']['access_modes']
            self.assertEqual(modes['frozen_program']['status'], 'source_available')
            self.assertEqual(modes['direct_observation']['status'], 'not_delivered')

    def test_current_contract_cli_returns_bound_definition_without_execution(self):
        with patch.object(cli.subprocess, 'run', side_effect=AssertionError('candidate execution')):
            direct = cli.neural_contract('NEURAL-001', self.root)
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(cli.main(['neural-contract', 'NEURAL-001'], root=self.root), 0)
        self.assertEqual(json.loads(output.getvalue()), direct)
        self.assertEqual(direct, contract('NEURAL-001'))
        for identifier in ('PAPER-001', 'UNKNOWN-001'):
            with self.subTest(identifier=identifier), self.assertRaisesRegex(ValueError, 'registered neural task'):
                cli.neural_contract(identifier, self.root)

    def test_navigation_shows_target_modes_and_history_without_qualification(self):
        result = catalog.generate(self.root)
        row = next(row for row in result['tasks'] if row['id'] == 'NEURAL-001')
        text = (self.root / row['task_directory'] / 'README.md').read_text()
        self.assertIn('Infer the prespecified held-out observation target.', text)
        for mode in ('Direct observation', 'Typed viewer', 'Tool assisted', 'Frozen program'):
            self.assertIn(mode, text)
        self.assertIn('Source availability does not establish a qualified runtime.', text)
        self.assertIn('programme score cannot be reported', text)
        links = set(catalog.source_links(result))
        self.assertIn(row['neural_understanding']['contract']['path'], links)
        self.assertIn(row['neural_understanding']['historical_specification']['path'], links)
        self.assertEqual(catalog.generate(self.root, check=True), result)

    def test_coverage_metadata_cannot_be_removed_or_weakened(self):
        original = self.registry()
        mutations = [lambda d: d.pop('neural_understanding'),
                     lambda d: d['neural_understanding'].pop('coverage_required'),
                     lambda d: d['neural_understanding'].update(coverage_required=False),
                     lambda d: d['neural_understanding'].update(registered_count=True),
                     lambda d: d['neural_understanding'].update(registered_count=117),
                     lambda d: d['neural_understanding'].update(objective='fit_any_programme'),
                     lambda d: d['neural_understanding'].update(schema_version='neural-understanding/v0')]
        for index, mutate in enumerate(mutations):
            current = copy.deepcopy(original)
            mutate(current)
            self.save_registry(current)
            with self.subTest(index=index), self.assertRaises(ValueError):
                catalog.discover(self.root)

    def test_every_neural_requires_revision_and_pinned_contract(self):
        current = self.registry()
        row = self.row(current)
        revision = row.pop('specification_revision')
        self.save_registry(current)
        with self.assertRaisesRegex(ValueError, 'requires every neural contract'):
            catalog.discover(self.root)
        row['specification_revision'] = revision
        self.save_registry(current)
        (self.root / revision['understanding_contract']['path']).unlink()
        with self.assertRaisesRegex(ValueError, 'Missing public source'):
            catalog.discover(self.root)

    def test_exact_binding_refuses_rehashed_task_edits(self):
        original = self.registry()
        row = self.row(original)
        body = (self.root / row['specification']['path']).read_bytes()
        mutations = [lambda d: d.update(objective='infer_any_target'),
                     lambda d: d['evaluation']['neural_understanding'].update(contract_sha256='a' * 64),
                     lambda d: d['evaluation']['neural_understanding'].update(original_definition_sha256='a' * 64),
                     lambda d: d['evaluation']['neural_understanding'].update(contract_path='../other.json'),
                     lambda d: d['evaluation']['neural_understanding'].update(extra_claim='qualified'),
                     lambda d: d['evaluation'].pop('neural_understanding')]
        for index, mutate in enumerate(mutations):
            (self.root / row['specification']['path']).write_bytes(body)
            self.edit_task(copy.deepcopy(original), mutate)
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'not bound'):
                catalog.discover(self.root)

    def test_rehashed_contract_identity_is_scientifically_validated(self):
        current = self.registry()
        row = self.row(current)
        contract_pin = row['specification_revision']['understanding_contract']
        changed = contract('NEURAL-002')
        replacement = put(self.root, contract_pin['path'], changed)
        row['specification_revision']['understanding_contract'] = replacement
        self.edit_task(current, lambda d: d['evaluation']['neural_understanding'].update(
            contract_sha256=replacement['sha256']))
        with self.assertRaisesRegex(ValueError, 'Invalid neural understanding contract'):
            catalog.discover(self.root)

    def test_history_cannot_be_replaced_by_repinning_only_current_registry(self):
        current = self.registry()
        row = self.row(current)
        previous = row['specification_revision']['previous_specification']
        replacement = pin(previous['path'], (self.root / previous['path']).read_bytes() + b' ')
        (self.root / previous['path']).write_bytes(self.original_tasks[row['id']] + b' ')
        row['specification_revision']['previous_specification'] = replacement
        row['original_specification'].update(bytes=replacement['bytes'], sha256=replacement['sha256'])
        self.edit_task(current, lambda d: d['evaluation']['neural_understanding'].update(
            original_definition_sha256=replacement['sha256']))
        with self.assertRaisesRegex(ValueError, 'lineage differs'):
            catalog.discover(self.root)

    def test_rehashed_snapshot_cannot_change_roster_or_original_identity(self):
        original = self.registry()
        mutations = [lambda d: d['tasks'].remove(self.row(d)),
                     lambda d: self.row(d)['original_specification'].update(sha256='f' * 64),
                     lambda d: self.row(d).update(specification_id='OTHER-ID')]
        for index, mutate in enumerate(mutations):
            snapshot = json.loads(self.original_registry)
            mutate(snapshot)
            current = copy.deepcopy(original)
            current['neural_understanding']['pre_understanding_registry'] = put(self.root, SNAPSHOT, snapshot)
            self.save_registry(current)
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'roster|lineage differs'):
                catalog.discover(self.root)

    def test_history_and_contract_paths_cannot_redirect_to_private_or_other_task(self):
        original = self.registry()
        mutations = [lambda r: r['specification_revision']['previous_specification'].update(path='/private/task.json'),
                     lambda r: r['specification_revision']['understanding_contract'].update(
                         path='benchmarks/neural/NEURAL-002/understanding.v1.json'),
                     lambda r: r['specification_revision'].update(version='paper-improvement/v1')]
        for index, mutate in enumerate(mutations):
            current = copy.deepcopy(original)
            mutate(self.row(current))
            self.save_registry(current)
            with self.subTest(index=index), self.assertRaises(ValueError):
                catalog.discover(self.root)

    def test_unrelated_later_paper_registration_preserves_neural_history(self):
        current = self.registry()
        row = copy.deepcopy(self.row(current, 'PAPER-EXP-0-0'))
        doc = json.loads((self.root / row['specification']['path']).read_bytes())
        row['id'] = row['specification_id'] = doc['id'] = 'PAPER-NEW-001'
        row['task_directory'] = 'benchmarks/paper/PAPER-NEW-001'
        row['specification'] = put(self.root, row['task_directory'] + '/task.json', doc)
        row['original_specification'] = {**row['specification'], 'path': 'former-source/PAPER-NEW-001.json'}
        current['tasks'].append(row)
        for key in ('paper', 'total', 'expansion_drafts'):
            current['source_counts'][key] += 1
        self.save_registry(current)
        result = catalog.discover(self.root)
        self.assertEqual(result['counts']['paper'], 117)
        self.assertEqual(result['neural_understanding_counts']['covered'], 118)
        self.assertEqual((self.root / SNAPSHOT).read_bytes(), self.original_registry)

    def test_paper_run_and_score_require_explicit_calibration_after_neural_revision(self):
        current = self.registry()
        paper = self.row(current, 'PAPER-001')
        with self.assertRaisesRegex(ValueError, 'same-task source-paper superiority'):
            cli.require_paper_role(paper, calibration=False)
        self.assertIsNone(cli.require_paper_role(paper, calibration=True))
        self.assertIsNone(cli.require_paper_role(self.row(current), calibration=False))

    def test_dispatch_specifications_validate_neural_binding_without_paper_revision(self):
        current = self.registry()
        self.assertNotIn('paper_improvement', current)
        self.edit_task(current, lambda d: d['evaluation']['neural_understanding'].update(
            contract_sha256='f' * 64))
        with self.assertRaisesRegex(ValueError, 'not bound'):
            cli.specifications(self.root)


if __name__ == '__main__':
    unittest.main()
