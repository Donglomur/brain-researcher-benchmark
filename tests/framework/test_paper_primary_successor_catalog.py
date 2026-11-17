"""Generated full-roster controls for selected and retained SMC policy views.

The accepted identity table is replaced only inside the generated fixture.
Source selectors point to inert files which raise if executed. No scientific
result or authentic run is produced by these metadata controls.
"""
from contextlib import redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


ordinary = module('primary_successor_catalog_ordinary', ROOT / 'tests/framework/test_paper_outcomes_catalog.py')
successor = module('primary_successor_catalog_source', ROOT / 'tests/maintenance/test_paper_primary_successor_binding.py')
catalog, cli, binding, binder = ordinary.catalog, ordinary.cli, successor.binding, successor.binder


class PrimarySuccessorCatalogTests(unittest.TestCase):
    def setUp(self):
        full = ordinary.initial.InitialPaperCatalogTests()
        full.setUp()
        self.addCleanup(full.doCleanups)
        case = successor.SuccessorFixture()
        case.setUp()
        self.addCleanup(case.doCleanups)
        self.root, self.case = full.root, case
        self.identifier = case.identifier
        # Replace only the generated 117th initial task. The genuine fixture
        # cardinalities, original 116-paper snapshot and 118 neural rows remain.
        shutil.copytree(case.root / case.home, self.root / case.home)
        registration = case.registration_pin['path']
        (self.root / registration).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(case.root / registration, self.root / registration)
        registry = full.registry()
        registry['tasks'] = [copy.deepcopy(case.prior_row) if row['id'] == ordinary.initial.IDENTIFIER else row
                             for row in registry['tasks']]
        registry['historical_registries'] = [copy.deepcopy(case.registration_pin) if pin['path'] == ordinary.initial.REGISTRATION else pin
                                             for pin in registry['historical_registries']]
        shutil.rmtree(self.root / ordinary.initial.DIRECTORY)
        (self.root / ordinary.initial.REGISTRATION).unlink()
        case.root = self.root
        case.put(binding.REGISTRY, registry)
        self.preserved = {relative: (self.root / relative).read_bytes() for relative in
                          (ordinary.builder.SNAPSHOT, registration, case.old_pin['path'])}
        self.prior_task = (self.root / case.task_path).read_bytes()
        for row in registry['tasks']:
            if row['track'] != 'paper' or row['id'] == self.identifier:
                continue
            home = row['task_directory']
            improvement = case.load(home + '/improvement.v1.json')
            reproduction = ordinary.unresolved_contract(improvement)
            projected = binding.project_task(case.load(home + '/task.json'), row, improvement)
            outcomes = {
                'schema_version': 'paper-outcomes/v1', 'task_id': row['id'],
                'original_task_sha256': binding.pin(home + '/task.json', binding.encode(projected))['sha256'],
                'contracts': {'reproduction': binding.engine().contract_digest(reproduction),
                              'improvement': binding.engine().contract_digest(improvement)},
                'pairing': {name: {'status': 'unresolved', 'rationale': 'Generated source-only fixture.', 'protocol': None}
                            for name in ('reproduction', 'improvement')},
            }
            case.put(home + '/reproduction.v1.json', reproduction)
            case.put(home + '/outcomes.v1.json', outcomes)
        with patch.object(binder.checker, 'PAPER_PRE_IMPROVEMENT_COUNT', 116):
            case.adopt()

    def discover(self):
        return catalog.discover(self.root)

    def row(self, view, identifier=None):
        return next(row for row in view['tasks'] if row['id'] == (identifier or self.identifier))

    def recount(self, view):
        view['counts'] = catalog.counts(view['tasks'])
        view['paper_improvement_counts'] = catalog.improvement_counts(view['tasks'])
        view['paper_outcome_counts'] = catalog.paper_outcome_counts(view['tasks'])
        view['neural_understanding_counts'] = catalog.understanding_counts(view['tasks'])

    def test_full_roster_selects_current_policy_and_preserves_first_definition(self):
        view = self.discover()
        row = self.row(view)
        self.assertEqual(view['counts']['total'], 235)
        self.assertEqual(view['counts']['paper'], 117)
        self.assertEqual(view['counts']['canonical_specifications'], 200)
        self.assertEqual(view['paper_outcome_counts']['covered'], 117)
        self.assertEqual(row['paper_outcomes']['improvement_contract'], self.case.primary_pin)
        self.assertEqual(row['paper_improvement']['contract'], self.case.old_pin)
        self.assertEqual(row['paper_improvement']['role'], catalog.RETAINED_POLICY_ROLE)
        self.assertIsNone(row['paper_improvement']['historical_specification'])
        self.assertEqual(row['original_specification'], self.case.prior_row['original_specification'])
        self.assertEqual(row['specification_revision'], self.case.prior_row['specification_revision'])
        self.assertEqual((self.root / self.case.history).read_bytes(), self.prior_task)
        for relative, raw in self.preserved.items():
            self.assertEqual((self.root / relative).read_bytes(), raw)
        self.assertFalse((self.root / self.case.home / ordinary.builder.HISTORY).exists())
        self.assertEqual(row['paper_outcomes']['scientific_outcomes'], {'reproduction': 'unknown', 'improvement': 'unknown'})
        self.assertTrue(all(cell['receipt'] is None for cell in row['paper_outcomes']['cells']))

    def test_cli_selects_current_contract_and_comparison_without_task_execution(self):
        with patch.object(cli.subprocess, 'run', side_effect=AssertionError('Task source must not execute')):
            self.assertEqual(cli.paper_contract(self.identifier, self.root), self.case.primary)
            self.assertEqual(cli.paper_contract(self.identifier, self.root, outcome='reproduction'), self.case.reproduction)
            ordinary_contract = self.case.load('benchmarks/paper/PAPER-001/improvement.v1.json')
            self.assertEqual(cli.paper_contract('PAPER-001', self.root), ordinary_contract)
            engine = cli.public_catalog_module().improvement_module()
            result_path = self.root / 'invented-result.json'
            result_path.write_text('{}')
            with patch.object(cli, 'public_catalog_module', return_value=catalog), \
                    patch.object(catalog, 'improvement_module', return_value=engine), \
                    patch.object(engine, 'compare', return_value={'generated': 'not a scientific result'}) as comparison:
                self.assertEqual(cli.compare_paper(self.identifier, result_path, self.root),
                                 {'generated': 'not a scientific result'})
                comparison.assert_called_once_with(self.case.primary, {})
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(cli.main(['paper-contract', self.identifier], root=self.root), 0)
            self.assertEqual(json.loads(output.getvalue()), self.case.primary)

    def test_public_views_show_exact_selected_and_author_routes(self):
        view = self.discover()
        row = self.row(view)
        outcome = cli.paper_outcomes(self.identifier, self.root)
        self.assertEqual(outcome['binding']['improvement_contract'], self.case.primary_pin)
        self.assertEqual(outcome['binding']['retained_improvement_contract'], self.case.old_pin)
        for field in catalog.PRIMARY_SUCCESSOR_PUBLIC_FIELDS:
            self.assertEqual(outcome['summary'][field], row['paper_outcomes'][field])
        summary = cli.public_summary(view)
        self.assertEqual(len(summary['selected_primary_policies']), 1)
        self.assertEqual(summary['selected_primary_policies'][0]['improvement_contract'], self.case.primary_pin)
        page = catalog.render_tracks(view)[self.case.home + '/README.md'].decode()
        self.assertIn('full 35-bin panel', page)
        self.assertIn('causal-proposal', page)
        self.assertIn('noncausal-proposal', page)
        self.assertIn('Retained author-source policy', page)
        self.assertIn('retained author restrictions do not govern that candidate', page)
        self.assertNotIn('## Current paper-improvement objective', page)
        self.assertIn('Retained registration-policy audit', catalog.paper_count_text(view))
        links = set(catalog.source_links(view))
        for field in ('improvement_contract', 'retained_improvement_contract', 'primary_policy_revision'):
            self.assertIn(row['paper_outcomes'][field]['path'], links)
        for name, fields in (('candidate_interface', ('delivery', 'scorer', 'policy')),
                             ('author_reproduction_routes', ('delivery', 'scorer', 'protocol'))):
            for field in fields:
                self.assertIn(row['paper_outcomes'][name][field]['path'], links)

    def test_primary_disposition_is_independent_of_retained_audit(self):
        row = self.row(self.discover())
        row['paper_improvement']['disposition'] = 'improvement_ready'
        row['paper_outcomes']['improvement_disposition'] = 'source_unresolved'
        self.assertEqual(catalog.primary_paper_disposition(row, 'improvement'), 'source_unresolved')
        self.assertEqual(catalog.paper_outcome_counts([row])['improvement_disposition'], {'source_unresolved': 1})
        self.assertEqual(catalog.improvement_counts([row])['improvement_ready'], 1)

    def test_supplied_selection_route_and_provenance_forgeries_refuse_before_render(self):
        view = self.discover()
        mutations = [
            lambda row: row['paper_outcomes'].__setitem__('improvement_contract', self.case.old_pin),
            lambda row: row['paper_outcomes'].__setitem__('retained_improvement_contract', self.case.primary_pin),
            lambda row: row['paper_outcomes']['candidate_interface']['delivery'].__setitem__('sha256', '0' * 64),
            lambda row: row['paper_outcomes']['author_reproduction_routes'].__setitem__('recipes', ['noncausal-proposal']),
            lambda row: row['paper_outcomes']['primary_policy_provenance']['scientific_contract'].__setitem__('path', self.case.old_scientific_pin['path']),
            lambda row: row['paper_outcomes']['candidate_interface']['policy'].__setitem__('bytes', float(row['paper_outcomes']['candidate_interface']['policy']['bytes'])),
            lambda row: row.__setitem__('title', 'Forged current title'),
            lambda row: row['paper_improvement'].__setitem__('disposition_reason', 'Forged retained claim'),
            lambda row: row['original_specification'].__setitem__('sha256', '0' * 64),
        ]
        for index, mutate in enumerate(mutations):
            changed = copy.deepcopy(view)
            mutate(self.row(changed))
            self.recount(changed)
            with self.subTest(index=index), patch.object(catalog, 'render_tracks', side_effect=AssertionError('Must refuse before render')):
                with self.assertRaises(ValueError):
                    catalog.generate(self.root, catalog=changed)

    def test_supplied_omission_or_foreign_successor_cannot_hide_source_selection(self):
        view = self.discover()
        for field in ('primary_policy_revision', 'candidate_interface', 'improvement_disposition'):
            changed = copy.deepcopy(view)
            del self.row(changed)['paper_outcomes'][field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                catalog.validate(changed, self.root)
        for remove in ('outcomes', 'row'):
            changed = copy.deepcopy(view)
            if remove == 'row':
                changed['tasks'].remove(self.row(changed))
            else:
                self.row(changed).pop('paper_outcomes')
                self.row(changed)['paper_improvement'].pop('role')
            self.recount(changed)
            with self.subTest(remove=remove), self.assertRaises(ValueError):
                catalog.validate(changed, self.root)
        changed = copy.deepcopy(view)
        self.row(changed, 'PAPER-001')['paper_outcomes']['candidate_interface'] = self.row(changed)['paper_outcomes']['candidate_interface']
        with self.assertRaises(ValueError):
            catalog.validate(changed, self.root)

    def test_missing_source_selectors_refuse_legacy_fallback(self):
        registry = self.case.load(binding.REGISTRY)
        for field in ('primary_policy_revision', 'primary_improvement_contract'):
            changed = copy.deepcopy(registry)
            self.row(changed)['paper_outcomes'].pop(field)
            self.case.put(binding.REGISTRY, changed)
            with self.subTest(field=field), self.assertRaises(ValueError):
                cli.paper_contract(self.identifier, self.root)
        self.case.put(binding.REGISTRY, registry)

    def test_stale_source_is_reauthenticated_on_each_validation(self):
        view = self.discover()
        path = self.root / self.case.primary_pin['path']
        original = path.read_bytes()
        catalog.validate(view, self.root)
        path.write_bytes(original + b' ')
        with self.assertRaises(ValueError):
            catalog.validate(view, self.root)
        path.write_bytes(original)
        catalog.validate(view, self.root)

    def test_midcall_descriptor_mutation_refuses_and_reader_accounts_every_read(self):
        view = self.discover()
        reader = catalog.Reader(self.root)
        original = reader.read
        seen = []
        descriptor = self.root / self.case.revision_pin['path']
        raw = descriptor.read_bytes()
        def mutate_after_registry(relative, *args, **kwargs):
            result = original(relative, *args, **kwargs)
            seen.append(relative)
            if relative == self.root / binding.REGISTRY:
                descriptor.write_bytes(raw + b' ')
            return result
        with patch.object(reader, 'read', side_effect=mutate_after_registry), self.assertRaises(ValueError):
            catalog.validate(view, self.root, _reader=reader)
        descriptor.write_bytes(raw)
        counted = catalog.Reader(self.root)
        read = counted.read
        sizes = []
        def record(relative, *args, **kwargs):
            result = read(relative, *args, **kwargs)
            sizes.append(result[1]['bytes'])
            return result
        with patch.object(counted, 'read', side_effect=record):
            catalog.validate(view, self.root, _reader=counted)
        self.assertEqual(counted.bytes, sum(sizes))
        self.assertLess(counted.bytes, catalog.READ_LIMIT)
        print('generated SMC successor validate bytes:', counted.bytes, 'reads:', len(sizes))


if __name__ == '__main__':
    unittest.main()
