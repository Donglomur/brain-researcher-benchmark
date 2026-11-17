"""Generated fixed-selector controls; no task code or model assets execute."""
import copy
import hashlib
import json
from pathlib import Path
import runpy
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
base = runpy.run_path(str(ROOT / 'tests/maintenance/test_paper_smc_continuous_binding.py'))
SuccessorFixture = base['SuccessorFixture']
binder, binding = base['binder'], base['binding']
configure_continuous = base['configure_continuous']


def configure_official_assets(case):
    """Add an invented v2 layer to a generated, adopted continuous-v1 fixture."""
    module = case.module
    predecessor_raw = (case.root / case.task_path).read_bytes()
    predecessor = json.loads(predecessor_raw)
    decision = 'Invented exact official-assets policy; no genuine assets or execution.\n'
    for name, value in (
        ('OFFICIAL_ASSETS_ROOT', (len(decision.encode()), hashlib.sha256(decision.encode()).hexdigest())),
        ('retained_continuous_revision', mock.Mock(return_value=case.continuous['revision'])),
    ):
        patcher = mock.patch.object(module, name, value)
        patcher.start()
        case.addCleanup(patcher.stop)
    entry = case.put_pin(module.OFFICIAL_ASSETS_PACKAGE + 'benchmark.py',
                         b'raise AssertionError("Generated v2 task source must never execute")\n')
    patcher = mock.patch.object(module, 'official_assets_entrypoint', return_value=entry)
    patcher.start()
    case.addCleanup(patcher.stop)
    policy = {'schema': 'smc_continuous_official_assets_policy_v2', 'task_id': case.identifier,
              'root_adoption_sha256': module.OFFICIAL_ASSETS_ROOT[1],
              'conditions': ['paper_data', 'paper_data_author_code_and_weights'], 'tolerance': None}
    assets = {'schema': 'smc_official_asset_allowlist_v2', 'asset_count': 10,
              'files': [{'path': 'invented-model/asset-' + str(index), 'bytes': 1,
                         'sha256': hashlib.sha256(bytes([index])).hexdigest()} for index in range(10)]}
    policy_pin = binding.pin(module.OFFICIAL_ASSETS_PACKAGE + 'policy.json', binding.encode(policy))
    assets_pin = binding.pin(module.OFFICIAL_ASSETS_PACKAGE + 'asset_allowlist.json', binding.encode(assets))
    values = {pointer: 'Invented official-assets correction ' + pointer for pointer in module._OFFICIAL_ASSETS_FIELDS}
    values.update({
        '/admission': {'runnable': False, 'research_qualified': False, 'submission_ready': False},
        '/continuous_outcomes_v2': {'version': 2, 'policy_sha256': policy_pin['sha256']},
        '/evaluation/candidate_interface': {'role': 'continuous_official_assets_outcomes', 'policy': policy_pin,
            'asset_allowlist': assets_pin, 'delivery': entry, 'scorer': entry, 'scientific_outcome': 'not_attempted',
            'selection_limit': 'Invented assets are not loaded; access does not establish execution or scientific success.'},
        '/evaluation/contracts': {'reproduction': 'implementations/continuous-outcomes-v2/policy.json',
                                 'improvement': 'implementations/continuous-outcomes-v2/policy.json'},
        '/evaluation/historical_optional_information_condition': {
            'condition': 'paper_data_author_code', 'policy_path': 'implementations/continuous-outcomes-v1/policy.json',
            'policy_sha256': case.continuous['policy']['sha256'], 'role': 'separate_source_only_ablation_not_pooled_with_primary_pair'},
        '/evaluation/information_conditions': policy['conditions'],
        '/evaluation/operator_entrypoint': dict(entry, commands=['prepare', 'inspect', 'freeze', 'score']),
        '/evaluation/retained_continuous_v1_contracts': {
            'reproduction': 'implementations/continuous-outcomes-v1/policy.json',
            'improvement': 'implementations/continuous-outcomes-v1/policy.json'},
        '/evaluation/scorer_ref': entry['path'],
        '/holds': ['Invented exact assets and execution remain unattempted.'],
        '/provenance/continuous_policy': policy_pin,
        '/provenance/official_assets_policy_adoption_sha256': module.OFFICIAL_ASSETS_ROOT[1],
        '/provenance/official_assets_predecessor': binding.pin(module.OFFICIAL_ASSETS_PACKAGE + 'predecessor.task.json', predecessor_raw),
        '/resources/participant_access_budget': {'policy_sha256': policy_pin['sha256']},
        '/success_criteria': ['Invented official-assets continuous reporting; no binary threshold.'],
        '/title': 'Invented continuous official-assets current policy',
    })
    proposal = copy.deepcopy(predecessor)
    del proposal['continuous_outcomes_v1']
    for pointer, value in values.items():
        keys, target = pointer[1:].split('/'), proposal
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = copy.deepcopy(value)
    proposal_raw = (json.dumps(proposal, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode()
    documents = {'retained_task': predecessor_raw, 'source_predecessor': predecessor_raw,
                 'policy': binding.encode(policy), 'asset_allowlist': binding.encode(assets),
                 'amendment': binding.encode({'schema': 'smc_official_assets_task_amendment_proposal_v2',
                    'delete_by_json_pointer': ['/continuous_outcomes_v1'], 'set_by_json_pointer': values}),
                 'proposal': proposal_raw}
    table = {}
    for name, raw in documents.items():
        path = module._OFFICIAL_ASSETS_APPROVED[name][0]
        table[name] = (path, len(raw), hashlib.sha256(raw).hexdigest(), module._digest(json.loads(raw)))
        case.put(path, raw)
    patcher = mock.patch.object(module, '_OFFICIAL_ASSETS_APPROVED', table)
    patcher.start()
    case.addCleanup(patcher.stop)
    revision = case.put_pin(module.OFFICIAL_ASSETS_DESCRIPTOR, module.official_assets_descriptor(decision))
    registry = case.load(binding.REGISTRY)
    row = next(item for item in registry['tasks'] if item['id'] == case.identifier)
    row['paper_outcomes']['continuous_policy_revision'] = revision
    row['title'] = proposal['title']
    row['specification'] = case.put_pin(case.task_path, proposal_raw)
    case.put(binding.REGISTRY, registry)
    case.official_assets = {'revision': revision, 'policy': policy_pin, 'asset_allowlist': assets_pin,
                           'predecessor_raw': predecessor_raw, 'proposal_raw': proposal_raw}
    return case.official_assets


class OfficialAssetsBindingTests(SuccessorFixture):
    def setUp(self):
        super().setUp()
        self.adopt()
        configure_continuous(self)
        self.v1_snapshot = self.snapshot()
        configure_official_assets(self)

    def test_one_current_pair_with_explicit_historical_v1(self):
        row, context = self.context()
        public = binding.public_summary(row, context)
        self.assertNotIn('continuous_outcomes_v1', public)
        selected = public['continuous_outcomes_v2']
        self.assertEqual(selected['conditions'], ['paper_data', 'paper_data_author_code_and_weights'])
        self.assertEqual({cell['condition'] for cell in public['cells']}, set(selected['conditions']))
        self.assertEqual(public['reproduction_contract'], self.official_assets['policy'])
        self.assertEqual(public['improvement_contract'], self.official_assets['policy'])
        self.assertEqual(selected['asset_allowlist'], self.official_assets['asset_allowlist'])
        self.assertEqual(selected['retained_v1']['revision'], self.continuous['revision'])
        self.assertEqual(selected['retained_v1']['role'], 'historical_source_only_policy_not_active_primary')
        self.assertIsNone(selected['paired_protocol'])
        self.assertTrue(all(cell['result_status'] == 'not_attempted' and not cell['condition_available']
                            and cell['endpoint_eligible'] is None for cell in public['cells']))

    def test_binder_idempotence_preserves_every_old_metadata_byte(self):
        before = self.snapshot()
        self.assertEqual(binder.write_or_check(self.root, check=True)['changed_files'], 0)
        self.assertEqual(binder.write_or_check(self.root, write=True)['changed_files'], 0)
        self.assertEqual(self.snapshot(), before)
        for path, raw in self.v1_snapshot.items():
            if path not in (self.task_path, binding.REGISTRY):
                self.assertEqual(before[path], raw, path)
        self.assertEqual(before[self.module.OFFICIAL_ASSETS_ARCHIVE], self.official_assets['predecessor_raw'])

    def test_metadata_ownership_retains_both_revisions_without_component_duplicates(self):
        _, context = self.context()
        for path in (self.module.CONTINUOUS_ARCHIVE, self.module.CONTINUOUS_DESCRIPTOR,
                     self.module.OFFICIAL_ASSETS_ARCHIVE, self.module.OFFICIAL_ASSETS_DESCRIPTOR):
            self.assertIn(path, context['members'])
        self.assertFalse(any('/implementations/continuous-outcomes-' in path for path in context['members']))

    def test_v1_selector_cannot_downgrade_v2_current_task(self):
        registry = self.load(binding.REGISTRY)
        registry['tasks'][0]['paper_outcomes']['continuous_policy_revision'] = self.continuous['revision']
        self.put(binding.REGISTRY, registry)
        self.reject_without_writes()

    def test_unreviewed_version_and_foreign_task_selectors_are_rejected(self):
        row = copy.deepcopy(self.load(binding.REGISTRY)['tasks'][0])
        row['paper_outcomes']['continuous_policy_revision']['path'] = self.home + '/continuous-outcomes-binding.v3.json'
        with self.assertRaises(ValueError):
            binding.has_continuous_outcomes(row)
        row = copy.deepcopy(self.load(binding.REGISTRY)['tasks'][0])
        row['id'] = 'PAPER-INVENTED-OTHER'
        with self.assertRaises(ValueError):
            binding.has_continuous_outcomes(row)

    def test_changed_allowlist_policy_or_v1_archive_is_rejected(self):
        for path in (self.module.official_assets_pin('asset_allowlist')['path'],
                     self.module.official_assets_pin('policy')['path'], self.module.OFFICIAL_ASSETS_ARCHIVE,
                     self.module.CONTINUOUS_DESCRIPTOR):
            with self.subTest(path=path):
                raw = (self.root / path).read_bytes()
                self.put(path, raw + b' ')
                self.reject_without_writes()
                self.put(path, raw)

    def test_rehashed_current_cannot_change_title_or_reactivate_v1(self):
        original = self.load(self.task_path)
        for update in ({'title': 'Unreviewed title'}, {'continuous_outcomes_v1': {'version': 1}}):
            changed = dict(original, **update)
            registry = self.load(binding.REGISTRY)
            registry['tasks'][0]['title'] = changed['title']
            registry['tasks'][0]['specification'] = self.put_pin(self.task_path, changed)
            self.put(binding.REGISTRY, registry)
            self.reject_without_writes()

    def test_authenticated_v2_handle_is_immutable_and_snapshot_isolated(self):
        handles = []
        original = self.module.project_official_assets
        def capture(task, handle):
            handles.append(handle)
            return original(task, handle)
        with mock.patch.object(self.module, 'project_official_assets', side_effect=capture):
            self.context()
        handle = handles[0]
        with self.assertRaises(AttributeError):
            del handle._payload
        with self.assertRaises(AttributeError):
            handle._payload = '{}'
        snapshot = handle.snapshot()
        snapshot['documents']['asset_allowlist']['files'].clear()
        self.assertEqual(len(handle.snapshot()['documents']['asset_allowlist']['files']), 10)
        self.assertEqual(binding.encode(original(json.loads(self.official_assets['predecessor_raw']), handle)),
                         self.official_assets['proposal_raw'])


if __name__ == '__main__':
    unittest.main()
