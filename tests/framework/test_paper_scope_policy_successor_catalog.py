"""Generated fixed-case policy selection views with no runtime routes.

The 234-task synthetic source roster gains four initial fixture registrations
before adoption. Adoption preserves all 238 identities and the original history;
these invented source declarations never add real benchmark tasks or results.
"""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


ordinary = module('scope_policy_ordinary_catalog', ROOT / 'tests/framework/test_paper_outcomes_catalog.py')
support = module('scope_policy_binding_fixture', ROOT / 'tests/maintenance/test_paper_scope_policy_successor_binding.py')
catalog, cli = ordinary.catalog, ordinary.cli
binding, binder = support.binding, support.binder


class ScopePolicySuccessorCatalogTests(unittest.TestCase):
    def setUp(self):
        full = ordinary.initial.fixtures.PaperCatalogBindingTests()
        full.setUp()
        self.addCleanup(full.doCleanups)
        case = support.ScopePolicyFixture()
        case.setUp()
        self.addCleanup(case.doCleanups)
        self.root, self.case = full.root, case
        self.ids, self.identifier = case.ids, case.ids[0]
        registry = full.registry()
        for identifier, item in case.docs.items():
            home = 'benchmarks/paper/' + identifier
            shutil.copytree(case.root / home, self.root / home)
            initial_pin = item['row']['specification_revision']['initial_registration']
            (self.root / initial_pin['path']).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(case.root / initial_pin['path'], self.root / initial_pin['path'])
            registry['tasks'].append(copy.deepcopy(item['row']))
            registry['historical_registries'].append(copy.deepcopy(initial_pin))
        shutil.copyfile(case.root / binding.SCOPE_PATH, self.root / binding.SCOPE_PATH)
        registry['paper_improvement']['registered_count'] += len(self.ids)
        for field in ('paper', 'total', 'expansion_drafts'):
            registry['source_counts'][field] += len(self.ids)
        case.root = self.root
        case.put(binding.REGISTRY, registry)
        self.preserved = {path: (self.root / path).read_bytes() for path in
                          (ordinary.builder.SNAPSHOT,
                           *(item['row']['specification_revision']['initial_registration']['path'] for item in case.docs.values()),
                           *(item['pins']['previous_improvement']['path'] for item in case.docs.values()))}
        self.before = catalog.discover(self.root)
        for row in registry['tasks']:
            if row['track'] != 'paper' or row['id'] in self.ids:
                continue
            home = row['task_directory']
            improvement = case.load(home + '/improvement.v1.json')
            reproduction = ordinary.unresolved_contract(improvement)
            projected = binding.project_task(case.load(home + '/task.json'), row, improvement)
            descriptor = {
                'schema_version': 'paper-outcomes/v1', 'task_id': row['id'],
                'original_task_sha256': binding.pin(home + '/task.json', binding.encode(projected))['sha256'],
                'contracts': {'reproduction': binding.engine().contract_digest(reproduction),
                              'improvement': binding.engine().contract_digest(improvement)},
                'pairing': {name: {'status': 'unresolved', 'rationale': 'Invented source protocol gap.', 'protocol': None}
                            for name in ('reproduction', 'improvement')},
            }
            case.put(home + '/reproduction.v1.json', reproduction)
            case.put(home + '/outcomes.v1.json', descriptor)
        with patch.object(binder.checker, 'PAPER_PRE_IMPROVEMENT_COUNT', 116):
            case.adopt()

    def row(self, document, identifier=None):
        return next(row for row in document['tasks'] if row['id'] == (identifier or self.identifier))

    def discover(self):
        return catalog.discover(self.root)

    def recount(self, view):
        view['counts'].update(catalog.counts(view['tasks']))
        view['paper_improvement_counts'] = catalog.improvement_counts(view['tasks'])
        view['paper_outcome_counts'] = catalog.paper_outcome_counts(view['tasks'])
        view['neural_understanding_counts'] = catalog.understanding_counts(view['tasks'])

    def test_all_four_current_policies_preserve_identity_and_retained_history(self):
        view = self.discover()
        self.assertEqual(view['counts'], self.before['counts'])
        self.assertEqual(view['counts']['total'], 238)
        self.assertEqual(view['counts']['canonical_specifications'], 200)
        self.assertEqual(view['paper_outcome_counts']['covered'], 120)
        for identifier, item in self.case.docs.items():
            row = self.row(view, identifier)
            selected = row['paper_outcomes']
            self.assertEqual(row['original_specification'], item['row']['original_specification'])
            self.assertEqual(row['specification_revision'], item['row']['specification_revision'])
            self.assertIsNone(row['paper_improvement']['historical_specification'])
            self.assertEqual(row['paper_improvement']['contract'], item['pins']['previous_improvement'])
            self.assertEqual(selected['improvement_contract'], item['pins']['primary_improvement'])
            self.assertEqual(selected['retained_improvement_contract'], item['pins']['previous_improvement'])
            self.assertEqual(selected['primary_policy_provenance'], {'scope_decision': self.case.scope_pin})
            self.assertIsNone(selected['candidate_interface'])
            self.assertIsNone(selected['author_reproduction_routes'])
            self.assertEqual(selected['primary_scope_correction']['primary_goal'],
                             self.case.scope['same_primary_corrections'][identifier]['primary_goal'])
            self.assertEqual(self.case.load(selected['previous_specification']['path']), item['documents']['previous_task'])
            self.assertTrue(all(cell['scientific_outcome'] == 'unknown' and cell['receipt'] is None for cell in selected['cells']))
        for path, raw in self.preserved.items():
            self.assertEqual((self.root / path).read_bytes(), raw)

    def test_all_four_cli_commands_select_current_policy_and_forward_null_routes(self):
        with patch.object(cli.subprocess, 'run', side_effect=AssertionError('No task source may execute')):
            for identifier, item in self.case.docs.items():
                with self.subTest(task=identifier):
                    selected = cli.paper_contract(identifier, self.root)
                    self.assertEqual(selected, item['documents']['primary_improvement'])
                    self.assertNotEqual(selected['episode']['candidate_freeze'], item['documents']['previous_improvement']['episode']['candidate_freeze'])
                    self.assertEqual(cli.paper_contract(identifier, self.root, outcome='reproduction'), item['documents']['reproduction'])
                    report = cli.paper_outcomes(identifier, self.root)
                    self.assertEqual(report['binding']['improvement_contract'], item['pins']['primary_improvement'])
                    self.assertEqual(report['binding']['retained_improvement_contract'], item['pins']['previous_improvement'])
                    self.assertEqual(report['binding']['primary_policy_provenance'], {'scope_decision': self.case.scope_pin})
                    self.assertIsNone(report['summary']['candidate_interface'])
                    self.assertIsNone(report['summary']['author_reproduction_routes'])
            status = cli.public_summary(self.discover())
            self.assertEqual({row['task_id'] for row in status['selected_primary_policies']}, set(self.ids))

    def test_pages_link_selected_scope_and_retained_policy_without_invented_executors(self):
        view = self.discover()
        pages, links = catalog.render_tracks(view), set(catalog.source_links(view))
        for identifier, item in self.case.docs.items():
            page = pages['benchmarks/paper/' + identifier + '/README.md'].decode()
            self.assertIn('Reviewed primary scope decision', page)
            self.assertIn('Retained predecessor improvement policy', page)
            self.assertIn('Runtime routes are not declared by this policy metadata', page)
            for absent in ('35-bin', 'offline candidate', 'causal-proposal', 'Author source | Selector',
                           'Candidate source | Selector', 'Retained author-source policy'):
                self.assertNotIn(absent, page)
            self.assertIn(item['pins']['primary_improvement']['path'], links)
            self.assertIn(item['pins']['previous_improvement']['path'], links)
            self.assertIn(item['pins']['descriptor']['path'], links)
        self.assertIn(self.case.scope_pin['path'], links)
        counts = catalog.paper_count_text(view)
        self.assertIn('reviewed scope-policy selections', counts)
        self.assertNotIn('revised SMC task', counts)

    def test_missing_actual_selectors_never_fall_back_even_with_equal_scientific_anchors(self):
        registry = self.case.load(binding.REGISTRY)
        for identifier in self.ids:
            for field in binding.PRIMARY_SUCCESSOR_FIELDS:
                changed = copy.deepcopy(registry)
                self.row(changed, identifier)['paper_outcomes'].pop(field)
                self.case.put(binding.REGISTRY, changed)
                with self.subTest(task=identifier, field=field), self.assertRaises(ValueError):
                    cli.paper_contract(identifier, self.root)
        self.case.put(binding.REGISTRY, registry)
        fc = self.case.docs['PAPER-paper-method-add-010']['documents']
        self.assertEqual(fc['previous_improvement']['same_task'], fc['primary_improvement']['same_task'])

    def test_supplied_view_cannot_omit_relabel_or_claim_an_unreviewed_successor(self):
        view = self.discover()
        for identifier in self.ids:
            for variant in ('row', 'summary', 'selection'):
                changed = copy.deepcopy(view)
                row = self.row(changed, identifier)
                if variant == 'row':
                    changed['tasks'].remove(row)
                elif variant == 'summary':
                    row.pop('paper_outcomes')
                    row['paper_improvement'].pop('role')
                else:
                    row['paper_outcomes'].pop('primary_policy_revision')
                self.recount(changed)
                with self.subTest(task=identifier, variant=variant), self.assertRaises(ValueError):
                    catalog.validate(changed, self.root)
        changed = copy.deepcopy(view)
        self.row(changed, 'PAPER-001')['paper_outcomes']['primary_policy_revision'] = self.row(changed)['paper_outcomes']['primary_policy_revision']
        with self.assertRaises(ValueError):
            catalog.validate(changed, self.root)

    def test_forged_current_retained_scope_or_runtime_claims_refuse_before_render(self):
        view = self.discover()
        mutations = [
            lambda row: row['paper_outcomes'].__setitem__('improvement_contract', row['paper_improvement']['contract']),
            lambda row: row['paper_outcomes'].__setitem__('retained_improvement_contract', row['paper_outcomes']['improvement_contract']),
            lambda row: row['paper_outcomes']['primary_policy_provenance']['scope_decision'].__setitem__('sha256', '0' * 64),
            lambda row: row['paper_outcomes']['primary_policy_provenance']['scope_decision'].__setitem__('bytes', float(row['paper_outcomes']['primary_policy_provenance']['scope_decision']['bytes'])),
            lambda row: row['paper_outcomes'].__setitem__('candidate_interface', {'role': 'primary_offline_candidate'}),
            lambda row: row['paper_outcomes'].__setitem__('author_reproduction_routes', {'recipes': ['causal-proposal']}),
            lambda row: row['paper_outcomes']['primary_scope_correction'].__setitem__('primary_goal', 'Forged primary scope'),
            lambda row: row['paper_improvement'].__setitem__('disposition_reason', 'Forged predecessor policy'),
            lambda row: row.__setitem__('title', 'Forged unchanged source title'),
        ]
        for index, mutate in enumerate(mutations):
            changed = copy.deepcopy(view)
            mutate(self.row(changed))
            with self.subTest(index=index), patch.object(catalog, 'render_tracks', side_effect=AssertionError('Refuse before render')):
                with self.assertRaises(ValueError):
                    catalog.generate(self.root, catalog=changed)

    def test_changed_current_policy_or_scope_refuses_new_calls(self):
        view = self.discover()
        for relative in (self.case.scope_pin['path'], self.case.docs[self.identifier]['pins']['primary_improvement']['path']):
            path = self.root / relative
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            for operation in (lambda: catalog.validate(view, self.root),
                              lambda: cli.paper_contract(self.identifier, self.root),
                              lambda: cli.paper_outcomes(self.identifier, self.root)):
                with self.subTest(path=relative, operation=operation), self.assertRaises(ValueError):
                    operation()
            path.write_bytes(original)
        catalog.validate(view, self.root)

    def test_midcall_change_and_all_four_context_reads_preserve_cumulative_bound(self):
        view = self.discover()
        policy_path = self.root / self.case.docs[self.identifier]['pins']['primary_improvement']['path']
        original = policy_path.read_bytes()
        reader = catalog.Reader(self.root)
        read = reader.read
        def mutate(member):
            result = read(member)
            if member == self.root / binding.REGISTRY:
                policy_path.write_bytes(original + b' ')
            return result
        with patch.object(reader, 'read', side_effect=mutate), self.assertRaises(ValueError):
            catalog.validate(view, self.root, _reader=reader)
        policy_path.write_bytes(original)
        reader = catalog.Reader(self.root)
        read, sizes, paths = reader.read, [], []
        def account(member):
            result = read(member)
            sizes.append(result[1]['bytes'])
            paths.append(result[1]['path'])
            return result
        with patch.object(reader, 'read', side_effect=account):
            catalog.validate(view, self.root, _reader=reader)
        self.assertEqual(reader.bytes, sum(sizes))
        for item in self.case.docs.values():
            self.assertIn(item['pins']['primary_improvement']['path'], paths)
            self.assertIn(item['pins']['previous_improvement']['path'], paths)
            self.assertIn(item['pins']['descriptor']['path'], paths)
        self.assertEqual(paths.count(binding.SCOPE_PATH), 6)
        with patch.object(catalog, 'READ_LIMIT', reader.bytes - 1), self.assertRaisesRegex(ValueError, 'read limit'):
            catalog.validate(view, self.root)
        print('generated four-policy validation bytes:', reader.bytes, 'reads:', len(paths))


if __name__ == '__main__':
    unittest.main()
