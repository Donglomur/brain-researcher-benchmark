"""Generated catalog/CLI controls for the fixed SMC official-assets selection.

The existing full-roster v1 fixture remains intact as the predecessor. These
controls authenticate metadata and inert source selectors only; no asset,
checkpoint, model, participant prediction or scientific scorer is loaded.
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


previous = module('official_assets_catalog_previous', ROOT / 'tests/framework/test_paper_smc_continuous_catalog.py')
official = module('official_assets_catalog_binding', ROOT / 'tests/maintenance/test_paper_smc_official_assets_binding.py')
catalog, cli = previous.catalog, previous.cli


class OfficialAssetsCatalogTests(unittest.TestCase):
    def setUp(self):
        fixture = previous.ContinuousCatalogTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture, self.case, self.root = fixture, fixture.case, fixture.root
        self.identifier = fixture.identifier
        before = catalog.discover(self.root)
        self.v1_public = copy.deepcopy(self.row(before)['paper_outcomes'])
        self.v1_task = (self.root / self.case.task_path).read_bytes()
        self.preserved = {self.v1_public['continuous_outcomes_v1'][field]['path']:
                          (self.root / self.v1_public['continuous_outcomes_v1'][field]['path']).read_bytes()
                          for field in ('policy', 'entrypoint', 'revision')}
        official.configure_official_assets(self.case)
        self.view = catalog.discover(self.root)
        self.public = self.row(self.view)['paper_outcomes']
        self.selection = self.public['continuous_outcomes_v2']

    def row(self, view, identifier=None):
        return self.fixture.row(view, identifier)

    def test_exact_current_pair_preserves_one_task_and_source_only_history(self):
        self.assertNotIn('continuous_outcomes_v1', self.public)
        self.assertEqual(self.view['counts']['total'], 235)
        self.assertEqual(self.view['counts']['paper'], 117)
        self.assertEqual(self.view['counts']['canonical_specifications'], 200)
        self.assertEqual(self.selection['conditions'], ['paper_data', 'paper_data_author_code_and_weights'])
        self.assertEqual({(cell['outcome'], cell['condition']) for cell in self.public['cells']},
                         {(outcome, condition) for outcome in ('reproduction', 'improvement')
                          for condition in ('paper_data', 'paper_data_author_code_and_weights')})
        for outcome in ('reproduction', 'improvement'):
            self.assertEqual(self.public[outcome + '_contract'], self.selection['policy'])
            self.assertEqual(catalog.primary_paper_disposition(self.row(self.view), outcome), 'continuous_measurement')
        self.assertEqual(self.public['candidate_interface']['asset_allowlist'], self.selection['asset_allowlist'])
        self.assertEqual(self.public['primary_policy_provenance']['asset_allowlist'], self.selection['asset_allowlist'])
        self.assertEqual(self.selection['retained_v1']['role'], 'historical_source_only_policy_not_active_primary')
        self.assertEqual(self.selection['retained_v1']['policy'], self.v1_public['continuous_outcomes_v1']['policy'])
        self.assertEqual((self.root / self.selection['retained_v1']['task']['path']).read_bytes(), self.v1_task)
        for path, raw in self.preserved.items():
            self.assertEqual((self.root / path).read_bytes(), raw)
        self.assertEqual(self.selection['result_status'], 'not_attempted')
        self.assertIsNone(self.selection['paired_protocol'])
        self.assertIsNone(self.row(self.view)['runtime_manifest'])
        self.assertTrue(all(cell['result_status'] == 'not_attempted' and cell['receipt'] is None
                            and cell['endpoint_eligible'] is None and cell['condition_available'] is False
                            for cell in self.public['cells']))

    def test_cli_selects_v2_policy_and_forwards_only_current_version(self):
        policy = self.case.load(self.selection['policy']['path'])
        self.assertEqual(policy['schema'], 'smc_continuous_official_assets_policy_v2')
        with patch.object(cli.subprocess, 'run', side_effect=AssertionError('Task source must not execute')):
            for outcome in ('reproduction', 'improvement'):
                self.assertEqual(cli.paper_contract(self.identifier, self.root, outcome=outcome), policy)
            result = cli.paper_outcomes(self.identifier, self.root)
        self.assertIsNone(result['descriptor'])
        for location in (result['binding'], result['summary'], cli.public_summary(self.view)['selected_primary_policies'][0]):
            self.assertNotIn('continuous_outcomes_v1', location)
            self.assertEqual(location['continuous_outcomes_v2'], self.selection)
        self.assertEqual(result['summary']['candidate_interface']['delivery'], self.selection['entrypoint'])
        self.assertEqual(result['summary']['author_reproduction_routes'], self.public['author_reproduction_routes'])

    def test_legacy_binary_commands_refuse_before_caller_input_access(self):
        class UnreadableInput:
            def __fspath__(self):
                raise AssertionError('Caller input must not be inspected')
        with patch.object(cli, '_outcome_receipt', side_effect=AssertionError('Receipt must not be read')):
            with self.assertRaisesRegex(ValueError, 'Continuous measurements do not use legacy binary outcome admission'):
                cli.check_paper_outcome(self.identifier, UnreadableInput(), self.root)
        with self.assertRaisesRegex(ValueError, 'Continuous measurements do not use legacy binary comparison'):
            cli.compare_paper(self.identifier, UnreadableInput(), self.root)

    def test_rendering_separates_assisted_assets_and_historical_source_only_access(self):
        page = catalog.render_tracks(self.view)[self.case.home + '/README.md'].decode()
        for text in ('`paper_data` versus `paper_data_author_code_and_weights`',
                     'Only the assisted condition receives', 'ten pinned released-model assets',
                     'Exact official-asset allowlist', 'Retained source-only continuous policy',
                     'separate source-only ablation', 'does not establish independent training',
                     'Not attempted', '`prepare`, `inspect`, `freeze`, `score`'):
            self.assertIn(text, page)
        self.assertNotIn('Paired outcome protocols', page)
        self.assertNotIn('Endpoint eligibility', page)
        self.assertIn('paper+data+official-code-and-weights', catalog.paper_count_text(self.view))
        links = set(catalog.source_links(self.view))
        self.assertIn(self.selection['asset_allowlist']['path'], links)
        for field in ('task', 'policy', 'entrypoint', 'revision'):
            self.assertIn(self.selection['retained_v1'][field]['path'], links)
        self.assertIn('Paper data author code and weights', page)

    def test_supplied_versions_assets_and_result_forgeries_refuse_before_render(self):
        mutations = [
            lambda public: public.__setitem__('continuous_outcomes_v1', self.v1_public['continuous_outcomes_v1']),
            lambda public: public.pop('continuous_outcomes_v2'),
            lambda public: public['continuous_outcomes_v2']['asset_allowlist'].__setitem__('bytes',
                float(public['continuous_outcomes_v2']['asset_allowlist']['bytes'])),
            lambda public: public['continuous_outcomes_v2']['asset_allowlist'].__setitem__('sha256', '0' * 64),
            lambda public: public['continuous_outcomes_v2']['retained_v1'].__setitem__('role', 'active_primary'),
            lambda public: public['continuous_outcomes_v2'].__setitem__('result_status', 'completed'),
            lambda public: public['continuous_outcomes_v2'].__setitem__('paired_protocol', {}),
            lambda public: public['cells'][1].__setitem__('condition', 'paper_data_author_code'),
            lambda public: public['cells'][0].__setitem__('condition_available', True),
        ]
        for index, mutate in enumerate(mutations):
            changed = copy.deepcopy(self.view)
            mutate(self.row(changed)['paper_outcomes'])
            with self.subTest(index=index), patch.object(catalog, 'render_tracks', side_effect=AssertionError('Must refuse before render')):
                with self.assertRaises(ValueError):
                    catalog.generate(self.root, catalog=changed)
        both = copy.deepcopy(self.view)
        self.row(both)['paper_outcomes']['continuous_outcomes_v1'] = self.v1_public['continuous_outcomes_v1']
        with self.assertRaisesRegex(ValueError, 'one current continuous policy'):
            cli.public_summary(both)

    def test_stale_v1_or_foreign_selection_cannot_replace_current_source(self):
        for mode in ('downgrade', 'foreign', 'omit'):
            changed = copy.deepcopy(self.view)
            row = self.row(changed)
            if mode == 'downgrade':
                row['paper_outcomes'] = copy.deepcopy(self.v1_public)
            elif mode == 'foreign':
                self.row(changed, 'PAPER-001')['paper_outcomes']['continuous_outcomes_v2'] = copy.deepcopy(self.selection)
            else:
                changed['tasks'].remove(row)
            self.fixture.fixture.recount(changed)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                catalog.validate(changed, self.root)

    def test_allowlist_is_freshly_authenticated_with_bounded_read_accounting(self):
        path = self.root / self.selection['asset_allowlist']['path']
        raw = path.read_bytes()
        path.write_bytes(raw + b' ')
        with self.assertRaises(ValueError):
            catalog.validate(self.view, self.root)
        with self.assertRaises(ValueError):
            cli.paper_contract(self.identifier, self.root)
        path.write_bytes(raw)
        reader = catalog.Reader(self.root)
        read, seen = reader.read, []
        def record(relative):
            result = read(relative)
            seen.append(result[1])
            return result
        with patch.object(reader, 'read', side_effect=record):
            catalog.validate(self.view, self.root, _reader=reader)
        self.assertEqual(reader.bytes, sum(pin['bytes'] for pin in seen))
        paths = {pin['path'] for pin in seen}
        self.assertIn(self.selection['asset_allowlist']['path'], paths)
        self.assertIn(self.selection['retained_v1']['task']['path'], paths)
        self.assertIn(self.selection['retained_v1']['policy']['path'], paths)
        with patch.object(catalog, 'READ_LIMIT', reader.bytes - 1), self.assertRaisesRegex(ValueError, 'read limit'):
            catalog.validate(self.view, self.root)


if __name__ == '__main__':
    unittest.main()
