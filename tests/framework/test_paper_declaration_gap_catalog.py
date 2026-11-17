"""Generated full-roster views for absent reproduction declarations.

These metadata fixtures preserve a complete 235-task registration roster. Their
invented improvement results test routing only and establish no scientific run.
"""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


ordinary = module('declaration_gap_ordinary_catalog', ROOT / 'tests/framework/test_paper_outcomes_catalog.py')
support = module('declaration_gap_binding_fixture', ROOT / 'tests/maintenance/test_paper_declaration_gap_binding.py')
catalog, cli = ordinary.catalog, ordinary.cli
binder, binding, gaps = support.binder, support.binding, support.gaps
initial = ordinary.initial


class DeclarationGapCatalogTests(unittest.TestCase):
    def setUp(self):
        self.identifiers = sorted(gaps.TASK_IDS)
        self.identifier = self.identifiers[0]
        fixture = initial.InitialPaperCatalogTests()
        original_fixture = initial.fixtures.catalog_fixture.fixture

        def full_roster(root):
            original_fixture(root)
            registry = json.loads((root / binding.REGISTRY).read_bytes())
            for former, identifier in zip(('PAPER-099', 'PAPER-100'), self.identifiers):
                row = next(row for row in registry['tasks'] if row['id'] == former)
                old_home = root / row['task_directory']
                document = json.loads((root / row['specification']['path']).read_bytes())
                document.update(id=identifier, title='Invented original gap task ' + identifier)
                home = 'benchmarks/paper/' + identifier
                raw = binding.encode(document)
                (root / home).mkdir(parents=True)
                (root / home / 'task.json').write_bytes(raw)
                shutil.rmtree(old_home)
                row.update(id=identifier, title=document['title'], specification_id=identifier,
                           task_directory=home, specification=binding.pin(home + '/task.json', raw),
                           original_specification=binding.pin('former-source/' + identifier + '.json', raw))
            (root / binding.REGISTRY).write_bytes(binding.encode(registry))

        with patch.object(initial.fixtures.catalog_fixture, 'fixture', side_effect=full_roster):
            fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root, self.fixture = fixture.root, fixture
        self.comparisons = {}
        for identifier in self.identifiers:
            contract, result = initial.fixtures.admission_fixture.fixture()
            contract['task_id'] = result['task_id'] = identifier
            initial.fixtures.admission_fixture.refreeze(contract, result)
            self.write('benchmarks/paper/' + identifier + '/improvement.v1.json', contract)
            self.comparisons[identifier] = result
        initial.builder.write_or_check(self.root, validator=initial.engine.contract_validate)
        prior = self.registry()
        cases = {identifier: SimpleNamespace(prior_row=self.row(prior, identifier),
                        improvement=self.load('benchmarks/paper/' + identifier + '/improvement.v1.json'))
                 for identifier in self.identifiers}
        self.record = support.support['record'](cases)
        self.record_pin = self.write(gaps.PATH, self.record)
        self.preserved = {path: (self.root / path).read_bytes() for path in
                          (initial.builder.SNAPSHOT, initial.REGISTRATION,
                           *(self.row(prior, identifier)['specification_revision']['improvement_contract']['path']
                             for identifier in self.identifiers))}
        self.previous_tasks = {identifier: (self.root / self.row(prior, identifier)['specification']['path']).read_bytes()
                               for identifier in self.identifiers}
        self.previous_rows = {identifier: copy.deepcopy(self.row(prior, identifier)) for identifier in self.identifiers}
        for row in prior['tasks']:
            if row['track'] != 'paper' or row['id'] in self.identifiers:
                continue
            home = row['task_directory']
            improvement = self.load(home + '/improvement.v1.json')
            reproduction = ordinary.unresolved_contract(improvement)
            projected = binding.project_task(self.load(home + '/task.json'), row, improvement)
            descriptor = {
                'schema_version': 'paper-outcomes/v1', 'task_id': row['id'],
                'original_task_sha256': binding.pin(home + '/task.json', binding.encode(projected))['sha256'],
                'contracts': {'reproduction': binding.engine().contract_digest(reproduction),
                              'improvement': binding.engine().contract_digest(improvement)},
                'pairing': {name: {'status': 'unresolved', 'rationale': 'Generated absent protocol.', 'protocol': None}
                            for name in ('reproduction', 'improvement')},
            }
            self.write(home + '/reproduction.v1.json', reproduction)
            self.write(home + '/outcomes.v1.json', descriptor)
        with patch.object(binding, 'SOURCE_DECLARATION_GAP_PIN', copy.deepcopy(self.record_pin)):
            binder.write_or_check(self.root, write=True)

    def load(self, path):
        return json.loads((self.root / path).read_bytes())

    def write(self, path, value):
        raw = value if isinstance(value, bytes) else binding.encode(value)
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        return binding.pin(path, raw)

    def registry(self):
        return self.load(binding.REGISTRY)

    def row(self, document, identifier=None):
        return next(row for row in document['tasks'] if row['id'] == (identifier or self.identifier))

    def discover(self):
        return catalog.discover(self.root)

    def recount(self, view):
        view['counts'].update(catalog.counts(view['tasks']))
        view['paper_improvement_counts'] = catalog.improvement_counts(view['tasks'])
        view['paper_outcome_counts'] = catalog.paper_outcome_counts(view['tasks'])
        view['neural_understanding_counts'] = catalog.understanding_counts(view['tasks'])

    def test_two_gap_tasks_preserve_original_histories_and_independent_improvement(self):
        view = self.discover()
        self.assertEqual(view['counts']['total'], 235)
        self.assertEqual(view['counts']['paper'], 117)
        self.assertEqual(view['paper_outcome_counts']['covered'], 117)
        self.assertEqual(view['paper_outcome_counts']['primary_unavailable'], 0)
        self.assertEqual(view['paper_outcome_counts']['source_declaration_unavailable'], 2)
        self.assertEqual(view['paper_outcome_counts']['reproduction_eligibility']['source_declaration_unavailable'], 2)
        self.assertEqual(view['paper_outcome_counts']['improvement_disposition']['improvement_ready'], 2)
        for identifier in self.identifiers:
            row = self.row(view, identifier)
            summary = row['paper_outcomes']
            self.assertEqual(row['original_specification'], self.previous_rows[identifier]['original_specification'])
            self.assertEqual(row['specification_revision'], self.previous_rows[identifier]['specification_revision'])
            self.assertEqual((self.root / summary['previous_specification']['path']).read_bytes(), self.previous_tasks[identifier])
            self.assertIsNone(summary['reproduction_contract'])
            self.assertIsNone(summary['outcomes'])
            self.assertIsNone(summary['reproduction_eligibility'])
            self.assertEqual(summary['improvement_disposition'], 'improvement_ready')
            self.assertEqual(len(summary['cells']), 4)
            for cell in summary['cells']:
                self.assertEqual(set(cell), {'outcome', 'condition', 'pairing_status', 'metadata_admitted', 'scientific_outcome', 'receipt'})
                self.assertIs(cell['metadata_admitted'], False)
                self.assertIsNone(cell['receipt'])
                self.assertEqual(cell['scientific_outcome'], 'unknown')
            for name in (*binding.REPRODUCTION_FILES.values(), binding.OUTCOMES):
                self.assertFalse((self.root / row['task_directory'] / name).exists())
        for path, raw in self.preserved.items():
            self.assertEqual((self.root / path).read_bytes(), raw)

    def test_navigation_has_gap_records_without_phantom_protocol_or_eligibility(self):
        view = self.discover()
        links = set(catalog.source_links(view))
        self.assertIn(gaps.PATH, links)
        pages = catalog.render_tracks(view)
        for identifier in self.identifiers:
            row = self.row(view, identifier)
            home = row['task_directory']
            self.assertNotIn(home + '/reproduction.v1.json', links)
            self.assertNotIn(home + '/outcomes.v1.json', links)
            page = pages[home + '/README.md'].decode()
            self.assertIn('Source declaration gap record', page)
            self.assertIn('independently inspectable under its original criteria', page)
            self.assertIn('Not established | Unknown', page)
            for absent in ('Endpoint eligibility', 'Paired outcome protocols', 'Each uses matched',
                           'secondary policy', 'different or narrower scientific question'):
                self.assertNotIn(absent, page)
        counts = catalog.paper_count_text(view)
        self.assertIn('missing declarations do not establish paired protocols', counts)
        self.assertIn('**2 tasks**', counts)
        self.assertEqual(cli.public_summary(view)['paper_outcomes']['source_declaration_unavailable'], 2)

    def test_cli_keeps_improvement_comparison_and_refuses_pairing_before_receipt(self):
        with patch.object(cli.subprocess, 'run', side_effect=AssertionError('No task execution')):
            for identifier in self.identifiers:
                contract = self.load('benchmarks/paper/' + identifier + '/improvement.v1.json')
                self.assertEqual(cli.paper_contract(identifier, self.root), contract)
                result_path = self.root / ('result-' + identifier + '.json')
                result_path.write_bytes(binding.encode(self.comparisons[identifier]))
                self.assertEqual(cli.compare_paper(identifier, result_path, self.root),
                                 initial.engine.compare(contract, self.comparisons[identifier]))
                report = cli.paper_outcomes(identifier, self.root)
                self.assertIsNone(report['descriptor'])
                self.assertIsNone(report['binding']['outcomes'])
                self.assertEqual(report['binding']['source_declaration_gap'], self.record_pin)
                self.assertEqual(report['summary']['improvement_disposition'], 'improvement_ready')
                with self.assertRaisesRegex(ValueError, 'No source-grounded reproduction declaration'):
                    cli.paper_contract(identifier, self.root, outcome='reproduction')
                with patch.object(cli, '_outcome_receipt', side_effect=AssertionError('Must refuse before receipt I/O')):
                    with self.assertRaisesRegex(ValueError, 'Paired paper outcome admission is unavailable'):
                        cli.check_paper_outcome(identifier, self.root / 'never-opened.json', self.root)

    def test_forged_summary_identity_and_typed_cells_refuse_before_render(self):
        view = self.discover()
        mutations = [
            lambda row: row['paper_outcomes'].__setitem__('reason', 'Invented replacement reason'),
            lambda row: row['paper_outcomes'].__setitem__('reproduction_eligibility', 'ineligible'),
            lambda row: row['paper_outcomes'].__setitem__('improvement_disposition', 'ineligible'),
            lambda row: row['paper_outcomes'].__setitem__('scientific_ineligibility_inferred', 0),
            lambda row: row['paper_outcomes']['cells'][0].__setitem__('metadata_admitted', 0),
            lambda row: row['paper_outcomes']['cells'][0].__setitem__('endpoint_eligible', False),
            lambda row: row['paper_outcomes'].__setitem__('outcomes', row['specification']),
            lambda row: row['paper_outcomes']['original_task'].__setitem__('sha256', '0' * 64),
            lambda row: row.__setitem__('title', 'Forged source task'),
            lambda row: row['paper_improvement'].__setitem__('disposition_reason', 'Forged independent policy'),
        ]
        for index, mutate in enumerate(mutations):
            changed = copy.deepcopy(view)
            mutate(self.row(changed))
            self.recount(changed)
            with self.subTest(index=index), patch.object(catalog, 'render_tracks', side_effect=AssertionError('Refuse before render')):
                with self.assertRaises(ValueError):
                    catalog.generate(self.root, catalog=changed)

    def test_source_classification_cannot_be_omitted_relabelled_or_claimed_elsewhere(self):
        view = self.discover()
        for variant in ('row', 'summary', 'available', 'unavailable'):
            changed = copy.deepcopy(view)
            row = self.row(changed)
            if variant == 'row':
                changed['tasks'].remove(row)
            elif variant == 'summary':
                row.pop('paper_outcomes')
            else:
                row['paper_outcomes']['availability'] = variant
                row['paper_outcomes']['reproduction_eligibility'] = 'source_unresolved'
            self.recount(changed)
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                catalog.validate(changed, self.root)
        changed = copy.deepcopy(view)
        self.row(changed, 'PAPER-001')['paper_outcomes'] = copy.deepcopy(self.row(changed)['paper_outcomes'])
        self.recount(changed)
        with self.assertRaises(ValueError):
            catalog.validate(changed, self.root)

    def test_actual_registry_cannot_hide_original_gap_ids_or_remove_adoption(self):
        view, original = self.discover(), self.registry()
        for variant in ('drop_task', 'global_and_selectors'):
            changed = copy.deepcopy(original)
            if variant == 'drop_task':
                changed['tasks'].remove(self.row(changed))
                changed['source_counts']['paper'] -= 1
                changed['source_counts']['total'] -= 1
                changed['paper_outcomes']['registered_count'] -= 1
            else:
                changed.pop('paper_outcomes')
                for row in changed['tasks']:
                    row.pop('paper_outcomes', None)
            supplied = copy.deepcopy(view)
            supplied['registry'] = self.write(binding.REGISTRY, changed)
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                catalog.validate(supplied, self.root)
        self.write(binding.REGISTRY, original)

    def test_changed_record_or_archive_refuses_fresh_validation_and_cli(self):
        view = self.discover()
        paths = (gaps.PATH, self.row(view)['paper_outcomes']['previous_specification']['path'])
        for relative in paths:
            path = self.root / relative
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            for operation in (lambda: catalog.validate(view, self.root),
                              lambda: cli.paper_outcomes(self.identifier, self.root),
                              lambda: cli.paper_contract(self.identifier, self.root)):
                with self.subTest(path=relative, operation=operation), self.assertRaises(ValueError):
                    operation()
            path.write_bytes(original)
        catalog.validate(view, self.root)

    def test_midcall_source_change_refuses_and_counts_all_reader_bytes(self):
        view = self.discover()
        path = self.root / gaps.PATH
        original = path.read_bytes()
        reader = catalog.Reader(self.root)
        read, seen = reader.read, []
        def mutate_first_record(member):
            result = read(member)
            seen.append(member)
            if member == path and seen.count(path) == 1:
                path.write_bytes(original + b' ')
            return result
        with patch.object(reader, 'read', side_effect=mutate_first_record), self.assertRaises(ValueError):
            catalog.validate(view, self.root, _reader=reader)
        path.write_bytes(original)
        reader = catalog.Reader(self.root)
        read, sizes, members = reader.read, [], []
        def account(member):
            result = read(member)
            sizes.append(result[1]['bytes'])
            members.append(result[1]['path'])
            self.assertFalse('dual-outcomes/' in result[1]['path'], 'External documentary evidence must not be followed')
            return result
        with patch.object(reader, 'read', side_effect=account):
            catalog.validate(view, self.root, _reader=reader)
        self.assertEqual(reader.bytes, sum(sizes))
        self.assertEqual(members.count(gaps.PATH), 3)
        with patch.object(catalog, 'READ_LIMIT', reader.bytes - 1), self.assertRaisesRegex(ValueError, 'read limit'):
            catalog.validate(view, self.root)
        print('generated two-gap validation bytes:', reader.bytes, 'reads:', len(sizes))


if __name__ == '__main__':
    unittest.main()
