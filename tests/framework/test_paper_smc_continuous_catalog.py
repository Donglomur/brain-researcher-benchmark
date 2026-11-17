"""Generated current SMC continuous-policy catalog and CLI controls.

The full generated roster and temporal fixture are reused, then one invented
continuous selection is authenticated. Source entrypoints are inert files; no
scientific implementation, participant prediction or evaluator is executed.
"""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), 'exec'), result.__dict__)
    return result


temporal = module('smc_continuous_catalog_temporal', ROOT / 'tests/framework/test_paper_primary_successor_catalog.py')
continuous = module('smc_continuous_catalog_binding', ROOT / 'tests/maintenance/test_paper_smc_continuous_binding.py')
catalog, cli, binding = temporal.catalog, temporal.cli, temporal.binding


class ContinuousCatalogTests(unittest.TestCase):
    def setUp(self):
        fixture = temporal.PrimarySuccessorCatalogTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture, self.case, self.root = fixture, fixture.case, fixture.root
        self.identifier = fixture.identifier
        self.preserved = {name: (self.root / (self.case.home + '/' + name)).read_bytes()
                          for name in ('improvement.v1.json', 'improvement.temporal-scope.v1.json',
                                       'reproduction.v1.json', 'outcomes.v1.json', 'primary-successor.v1.json')}
        self.selection = continuous.configure_continuous(self.case)

    def row(self, view, identifier=None):
        return self.fixture.row(view, identifier)

    def test_current_policy_is_shared_without_reclassifying_retained_lineage(self):
        view = catalog.discover(self.root)
        row = self.row(view)
        public = row['paper_outcomes']
        self.assertEqual(view['counts']['total'], 235)
        self.assertEqual(view['counts']['paper'], 117)
        self.assertEqual(view['counts']['canonical_specifications'], 200)
        for outcome in ('reproduction', 'improvement'):
            self.assertEqual(public[outcome + '_contract'], self.selection['policy'])
            self.assertEqual(catalog.primary_paper_disposition(row, outcome), 'continuous_measurement')
        self.assertEqual(view['paper_outcome_counts']['reproduction_eligibility']['continuous_measurement'], 1)
        self.assertEqual(view['paper_outcome_counts']['improvement_disposition']['continuous_measurement'], 1)
        self.assertIsNone(public['outcomes'])
        self.assertIsNone(public['reproduction_eligibility'])
        self.assertEqual(public['continuous_outcomes_v1']['result_status'], 'not_attempted')
        self.assertIsNone(public['continuous_outcomes_v1']['paired_protocol'])
        self.assertFalse(public['continuous_outcomes_v1']['construction_requires_AI_attempt'])
        self.assertEqual(public['primary_policy_revision'], self.selection['revision'])
        self.assertEqual(row['paper_improvement']['contract'], self.case.old_pin)
        self.assertEqual(row['paper_improvement']['role'], catalog.RETAINED_POLICY_ROLE)
        self.assertEqual(row['specification_revision'], self.case.prior_row['specification_revision'])
        self.assertEqual(row['original_specification'], self.case.prior_row['original_specification'])
        self.assertIsNone(row['runtime_manifest'])
        self.assertEqual(len(public['cells']), 4)
        for cell in public['cells']:
            self.assertIsNone(cell['eligibility'])
            self.assertIsNone(cell['endpoint_eligible'])
            self.assertFalse(cell['condition_available'])
            self.assertEqual(cell['pairing_status'], 'uninstantiated')
            self.assertEqual(cell['result_status'], 'not_attempted')
            self.assertEqual(cell['scientific_outcome'], 'unknown')
            self.assertIsNone(cell['receipt'])
        for name, raw in self.preserved.items():
            self.assertEqual((self.root / (self.case.home + '/' + name)).read_bytes(), raw)
        self.assertEqual((self.root / self.case.module.CONTINUOUS_ARCHIVE).read_bytes(), self.selection['temporal_raw'])

    def test_cli_exposes_current_policy_and_routes_without_a_binary_engine(self):
        policy = json.loads(self.selection['documents']['policy'])
        with patch.object(cli.subprocess, 'run', side_effect=AssertionError('Task source must not execute')):
            for outcome in ('reproduction', 'improvement'):
                self.assertEqual(cli.paper_contract(self.identifier, self.root, outcome=outcome), policy)
            result = cli.paper_outcomes(self.identifier, self.root)
        public = self.row(catalog.discover(self.root))['paper_outcomes']
        self.assertIsNone(result['descriptor'])
        self.assertEqual(result['summary']['task_count'], 1)
        self.assertEqual(result['summary']['continuous_outcomes_v1'], public['continuous_outcomes_v1'])
        self.assertEqual(result['summary']['candidate_interface'], public['candidate_interface'])
        self.assertEqual(result['binding']['continuous_outcomes_v1'], public['continuous_outcomes_v1'])
        self.assertEqual(result['binding']['reproduction_contract'], self.selection['policy'])
        self.assertEqual(result['binding']['improvement_contract'], self.selection['policy'])
        view = catalog.discover(self.root)
        selected = cli.public_summary(view)['selected_primary_policies']
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['continuous_outcomes_v1'], public['continuous_outcomes_v1'])
        self.assertEqual(selected[0]['candidate_interface']['delivery'], self.case.module.continuous_entrypoint())
        # Other paper selectors retain their ordinary policy behavior.
        self.assertEqual(cli.paper_contract('PAPER-001', self.root),
                         self.case.load('benchmarks/paper/PAPER-001/improvement.v1.json'))

    def test_both_legacy_admissions_refuse_before_supplied_input_reads(self):
        class UnreadableInput:
            def __fspath__(self):
                raise AssertionError('Caller input must not be inspected')
        with patch.object(cli, '_outcome_receipt', side_effect=AssertionError('Receipt must not be read')):
            with self.assertRaisesRegex(ValueError, 'Continuous measurements do not use legacy binary outcome admission'):
                cli.check_paper_outcome(self.identifier, UnreadableInput(), self.root)
        with self.assertRaisesRegex(ValueError, 'Continuous measurements do not use legacy binary comparison'):
            cli.compare_paper(self.identifier, UnreadableInput(), self.root)

    def test_rendering_links_current_operator_and_separately_retained_policies(self):
        view = catalog.discover(self.root)
        public = self.row(view)['paper_outcomes']
        page = catalog.render_tracks(view)[self.case.home + '/README.md'].decode()
        for text in ('Current continuous measurement policy', 'Continuous operator entrypoint',
                     '`prepare`, `inspect`, `freeze`, `score`', 'Retained pre-continuous policies',
                     'Retained original registration policy', 'Not instantiated', 'Not attempted',
                     'causal-proposal', 'noncausal-proposal'):
            self.assertIn(text, page)
        self.assertNotIn('Paired outcome protocols', page)
        self.assertNotIn('## Current paper-improvement objective', page)
        self.assertNotIn('Endpoint eligibility', page)
        self.assertNotIn('| None |', page)
        self.assertIn('without binary eligibility or pass thresholds', catalog.paper_count_text(view))
        self.assertIn('continuous_measurement', catalog.render(view)['paper.md'].decode())
        links = set(catalog.source_links(view))
        for field in ('policy', 'entrypoint', 'revision'):
            self.assertIn(public['continuous_outcomes_v1'][field]['path'], links)
        for field in ('task', 'reproduction', 'improvement', 'outcomes', 'revision'):
            self.assertIn(public['continuous_outcomes_v1']['retained_temporal'][field]['path'], links)

    def test_supplied_current_and_retained_forgeries_refuse_before_render(self):
        view = catalog.discover(self.root)
        mutations = [
            lambda public: public.pop('continuous_outcomes_v1'),
            lambda public: public.__setitem__('reproduction_contract', self.case.reproduction_pin),
            lambda public: public.__setitem__('improvement_contract', self.case.primary_pin),
            lambda public: public.__setitem__('outcomes', public['continuous_outcomes_v1']['retained_temporal']['outcomes']),
            lambda public: public['continuous_outcomes_v1'].__setitem__('paired_protocol', {}),
            lambda public: public['continuous_outcomes_v1'].__setitem__('result_status', 'completed'),
            lambda public: public['continuous_outcomes_v1']['entrypoint'].__setitem__('bytes',
                float(public['continuous_outcomes_v1']['entrypoint']['bytes'])),
            lambda public: public['continuous_outcomes_v1']['retained_temporal'].__setitem__('role', 'current'),
            lambda public: public['cells'][0].__setitem__('endpoint_eligible', True),
            lambda public: public['cells'][0].__setitem__('condition_available', True),
        ]
        for index, mutate in enumerate(mutations):
            changed = copy.deepcopy(view)
            mutate(self.row(changed)['paper_outcomes'])
            with self.subTest(index=index), patch.object(catalog, 'render_tracks', side_effect=AssertionError('Must refuse before render')):
                with self.assertRaises(ValueError):
                    catalog.generate(self.root, catalog=changed)

    def test_supplied_omission_relabel_and_foreign_continuous_claim_refuse(self):
        view = catalog.discover(self.root)
        for mode in ('row', 'binding', 'track', 'foreign'):
            changed = copy.deepcopy(view)
            row = self.row(changed)
            if mode == 'row':
                changed['tasks'].remove(row)
            elif mode == 'binding':
                row.pop('paper_outcomes')
                row['paper_improvement'].pop('role')
            elif mode == 'track':
                row['track'] = 'neural'
                row['task_directory'] = 'benchmarks/neural/' + self.identifier
            else:
                self.row(changed, 'PAPER-001')['paper_outcomes']['continuous_outcomes_v1'] = row['paper_outcomes']['continuous_outcomes_v1']
            self.fixture.recount(changed)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                catalog.validate(changed, self.root)

    def test_current_source_selector_cannot_fall_back_to_temporal_policy(self):
        registry = self.case.load(binding.REGISTRY)
        self.row(registry)['paper_outcomes'].pop('continuous_policy_revision')
        self.case.put(binding.REGISTRY, registry)
        with self.assertRaises(ValueError):
            cli.paper_contract(self.identifier, self.root)
        with self.assertRaises(ValueError):
            cli.paper_outcomes(self.identifier, self.root)

    def test_current_policy_freshness_and_cumulative_reader_accounting(self):
        view = catalog.discover(self.root)
        path = self.root / self.selection['policy']['path']
        raw = path.read_bytes()
        catalog.validate(view, self.root)
        path.write_bytes(raw + b' ')
        with self.assertRaises(ValueError):
            catalog.validate(view, self.root)
        path.write_bytes(raw)
        reader = catalog.Reader(self.root)
        read, seen = reader.read, []
        def record(relative):
            result = read(relative)
            seen.append(result[1])
            return result
        with patch.object(reader, 'read', side_effect=record):
            catalog.validate(view, self.root, _reader=reader)
        self.assertEqual(reader.bytes, sum(pin['bytes'] for pin in seen))
        paths = {pin['path'] for pin in seen}
        for relative in (self.selection['policy']['path'], self.selection['revision']['path'],
                         self.case.module.CONTINUOUS_ARCHIVE, self.case.primary_pin['path'], self.case.old_pin['path']):
            self.assertIn(relative, paths)
        with patch.object(catalog, 'READ_LIMIT', reader.bytes - 1), self.assertRaisesRegex(ValueError, 'read limit'):
            catalog.validate(view, self.root)


if __name__ == '__main__':
    unittest.main()
