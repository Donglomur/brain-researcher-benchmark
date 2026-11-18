"""In-memory full-panel owner controls; no physical fixtures or native execution.

Exact Provider objects are allocated without their filesystem constructor.
Execution, observation and artifact publication are inert test-only seams. These
controls test owner admission/chronology, not Docker/GPU/runtime qualification.
"""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


b = load('generated_reve_dataset_boundary', HERE / 'boundary.py')
old_path = HERE.parent / 'opaque-submission-v1/tests/test_adapter.py'
assert hashlib.sha256(old_path.read_bytes()).hexdigest() == 'de716dd790fa9e6e9456e5e66dfd0ccf1a068813a17dde26fd7734095a1dbbcf'
old = load('generated_reve_boundary_fixture', old_path)
p, contract, bounds = b.a.transport_package()
v = b.views_module()
IMAGE = 'sha256:' + 'd'*64
ORIGIN, DEADLINE = 100.0, 1000.0


def resources(kind):
    result = old.resources()
    result['max_files'] = 4 if kind == 'development' else 2
    return result


def episode(role='A', *, episode_id=None, **updates):
    doc = old.DOCS[0 if role == 'A' else 1]
    kwargs = {'expected_materials_identity': doc['materials_identity'],
              'expected_panel_identity': old.PANEL['panel_identity'],
              'episode_id': episode_id or ('1'*64 if role == 'A' else '2'*64),
              'origin': ORIGIN, 'deadline': DEADLINE, 'profile': b.PROFILES[0],
              'declaration': {'uses_unlabeled_test_context': False, 'description': 'generated pointwise policy'},
              'development_resources': resources('development'), 'inference_resources': resources('inference')}
    kwargs.update(updates)
    return b.Episode(doc, **kwargs)


def inert_provider(label):
    provider = object.__new__(p.Provider)
    provider.control_root = Path('/generated-private/' + label + '/control')
    provider.quarantine_root = Path('/generated-private/' + label + '/quarantine')
    provider.binary = '/generated-no-docker'; provider.socket = '/generated-absent.sock'
    provider.read_limit = 100*1024**3; provider.write_limit = 100*1024**2
    provider.read_used = provider.write_used = 0
    provider.engine_pin = b.a.pin(b'generated inactive engine')
    provider.exposures = {}; provider.source_root = b.a.TRANSPORT
    return provider


def common_files():
    return {'encoder.safetensors': b.a.ENCODER, 'encoder-config.json': b.r.CONFIG_PIN,
            'ENCODER_ARCHITECTURE.json': b.r.ARCHITECTURE_PIN, 'MODEL_LICENSE.txt': b.r.LICENSE_PIN}


def data_mount(item, kind):
    view = item.development if kind == 'development' else item.test
    sizes = {row['signal']: row['shape'][0]*64*800*8+128 for row in view['records']}
    return v.data_mount(view, '/generated-data/' + kind, sizes)


def bundle(item, kind, *, phase_id=None, image=IMAGE):
    if kind == 'development':
        mounts = b.development_mounts(item.info, data_mount(item, kind), '/generated-assets/paper.pdf',
                                     '/generated-assets/common', common_files(),
                                     {'path': '/generated-source/develop.py', 'pin': b.a.pin(b'inert source')},
                                     '/generated-assets/official.tar.gz' if item.info['role'] == 'B' else None)
    else:
        mounts = b.inference_mounts(data_mount(item, kind), item.artifact)
    return b.phase_request(phase_id=phase_id or item.info['role']+'_'+kind, role=item.info['role'],
                           image=image, exposure=b.a.pin((item.id+kind).encode()), mounts=mounts, kind=kind,
                           origin=item.origin, deadline=item.deadline,
                           resources=item.development_resources if kind == 'development' else item.inference_resources)


def repack(item, value):
    request = value['request']
    return b.phase_request(phase_id=request['phase_id'], role=request['role'], image=request['image'],
                           exposure=request['exposure'], mounts=value['mounts'], kind=value['kind'],
                           origin=request['clock']['origin'], deadline=request['clock']['phase_deadline'],
                           resources=request['resources'])


class OwnerControls(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.clock = self.stack.enter_context(patch.object(b.time, 'monotonic', return_value=400.0))
        self.gate = self.stack.enter_context(patch.object(b.r, 'require_installation', return_value=None))
        self.left, self.right = episode('A'), episode('B')
        self.items = {'A': self.left, 'B': self.right}
        self.providers = {role: inert_provider(role) for role in self.items}
        self.campaign = b.CampaignBarrier({item.id: role for role, item in self.items.items()})
        for item in self.items.values(): self.campaign.register(item)
        self.executions = []
        def execute(provider, request, mounts, deadline, journal):
            self.executions.append((provider, deepcopy(request), deepcopy(mounts), deadline))
            provider.read_used += 100; provider.write_used += 200
            return {'inert': True}
        self.stack.enter_context(patch.object(p.Provider, 'execute_phase', execute))
        self.observe = self.stack.enter_context(patch.object(b, 'observe_capture', side_effect=self.capture))
        self.promote = self.stack.enter_context(patch.object(b, 'promote_selected', side_effect=self.publish))

    def capture(self, provider, selected, returned, deadline, *, output_names):
        item = self.items[selected['request']['role']]
        phase_id = selected['request']['phase_id']
        if selected['kind'] == 'development':
            files = {name: b.a.pin((item.id+name).encode()) for name in b.ARTIFACT_FILES}
            result = {'schema': 'reve-development-selection-v2', 'episode_id': item.id,
                      'development_identity': item.development['view_identity'], 'selected_files': deepcopy(files)}
            start, finish = 200.0, 300.0
        else:
            files = {}
            result = {'schema': 'reve-frozen-dataset-result-v1', 'artifact_identity': item.artifact['artifact_identity'],
                      'predictions': [{'event_id': eid, 'prediction': index % 4}
                                      for index, eid in enumerate(reversed(item.info['test_ids']))]}
            start, finish = 450.0, 480.0
        files['RESULT.json'] = b.pin_json(result)
        self.assertEqual(set(files), set(output_names))
        return {'result': result, 'files': files, 'root': str(provider.quarantine_root/phase_id),
                'receipt_pin': b.a.pin(phase_id.encode()), 'receipt_started': start, 'receipt_finished': finish,
                'retired_resources': [{'kind': kind, 'name': phase_id+'_'+name, 'closed': True,
                                       'absence_observed': True, 'creation_outcome_unknown': False}
                                      for kind, name in (('container', 'producer'), ('container', 'holder'), ('volume', 'output'))]}

    def publish(self, provider, capture, output, fields, deadline):
        # Deliberately inert promotion. The independent reviewer exercises the
        # concrete promotion's write/read/failure debit without this replacement.
        value = {'schema': 'reve-frozen-candidate-v2', **deepcopy(fields),
                 'files': {name: deepcopy(capture['files'][name]) for name in b.ARTIFACT_FILES}}
        value['artifact_identity'] = b.r.identity(value)
        provider.read_used += 11; provider.write_used += 22
        return {**value, 'root': str(output), 'manifest_pin': b.pin_json(value),
                'conservative_copy_read_charge_bytes': 11, 'conservative_copy_write_charge_bytes': 22}

    def freeze(self, role='A', selected=None):
        item = self.items[role]; provider = self.providers[role]
        selected = bundle(item, 'development') if selected is None else selected
        provider.exposures[selected['request']['exposure']['sha256']] = '/generated-exposure/'+role+'-development.json'
        return item.develop_and_freeze(provider, bundle=selected, journal=lambda *args: None,
                                       frozen_output='/generated-frozen/'+role)

    def freeze_pair(self):
        self.freeze('A'); self.freeze('B'); return self.campaign.seal()

    def inference_bundle(self, role='A'):
        item = self.items[role]; selected = bundle(item, 'inference')
        self.providers[role].exposures[selected['request']['exposure']['sha256']] = '/generated-exposure/'+role+'-inference.json'
        return selected

    def infer(self, role='A', selected=None, provider=None):
        self.clock.return_value = 500.0
        return self.items[role].run_inference(provider or self.providers[role],
               bundle=self.inference_bundle(role) if selected is None else selected, journal=lambda *args: None)

    def assert_failed(self, item):
        self.assertEqual(item.state, 'failed')
        self.assertIsNone(item.results)

    def test_full_two_condition_freeze_infer_release_and_no_early_feedback(self):
        sealed = self.freeze_pair()
        self.assertEqual(sealed['episodes_frozen'], 2); self.assertFalse(sealed['scores_released'])
        first = self.infer('A')
        self.assertEqual(set(first), {'predictions_collected', 'complete', 'scientific_qualification'})
        self.assertEqual(first['predictions_collected'], 1803); self.assertFalse(first['scientific_qualification'])
        with self.assertRaises(ValueError): self.left.complete_predictions()
        with self.assertRaises(ValueError): self.campaign.release()
        self.infer('B')
        self.assertEqual(self.campaign.release()['complete_episodes'], 2)
        result = self.left.complete_predictions()
        predictions, release = result['predictions'], result['release']
        self.assertEqual(len(predictions['predictions']), 1803)
        self.assertEqual({row['event_id'] for row in predictions['predictions']}, set(self.left.info['test_ids']))
        self.assertEqual(release['profile'], b.PROFILES[0])
        self.assertEqual(release['predictions_pin'], b.pin_json(predictions))
        self.assertFalse(release['scientific_qualification']); self.assertFalse(release['current_paper_win_qualified'])
        self.assertFalse(release['requires_separate_outcome_binding'])
        self.assertEqual(release['complete_test_epochs'], 1803)
        predictions['predictions'].clear()
        self.assertEqual(len(self.left.complete_predictions()['predictions']['predictions']), 1803)
        self.assertEqual(len(self.executions), 4)
        self.assertEqual(old.CREATED, 0)

    def test_closed_installation_gate_precedes_all_native_methods(self):
        # Restore the actual pinned gate for this control only.
        with patch.object(b.r, 'require_installation', side_effect=b.a._require_installation):
            with self.assertRaises(ValueError): self.freeze()
            with self.assertRaises(ValueError): self.left.run_inference(self.providers['A'], bundle={}, journal=None)
        self.assertEqual(self.executions, []); self.promote.assert_not_called(); self.observe.assert_not_called()

    def test_explicit_profile_and_bounded_declaration_required(self):
        for declaration in ({'uses_unlabeled_test_context': True, 'description': 'adapt'},
                            {'uses_unlabeled_test_context': 0, 'description': 'wrong type'},
                            {'uses_unlabeled_test_context': False, 'description': ''},
                            {'uses_unlabeled_test_context': False, 'description': 'x'*4097},
                            {'uses_unlabeled_test_context': False, 'description': 'x', 'extra': True}):
            with self.subTest(declaration=declaration), self.assertRaises(ValueError): episode(declaration=declaration)
        item = episode(profile=b.PROFILES[1], declaration={'uses_unlabeled_test_context': True, 'description': 'predeclared joint transform'})
        self.assertTrue(item.declaration['uses_unlabeled_test_context'])
        with self.assertRaises(ValueError): episode(profile='unreviewed')

    def test_original_clock_must_fit_both_phases(self):
        for changes in ({'origin': True}, {'deadline': float('inf')}, {'origin': 100.0, 'deadline': 118.0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): episode(**changes)

    def test_boolean_or_missing_resource_operand_refused(self):
        limits = resources('development'); limits['source_read_bytes'] = True
        with self.assertRaises(ValueError): episode(development_resources=limits)
        limits = resources('inference'); limits.pop('host_write_bytes')
        with self.assertRaises(ValueError): episode(inference_resources=limits)

    def test_roster_requires_both_roles_and_exact_known_episodes(self):
        for roster in ({self.left.id: 'A'}, {self.left.id: 'A', self.right.id: 'A'}, {'bad': 'A', self.right.id: 'B'}):
            with self.subTest(roster=roster), self.assertRaises(ValueError): b.CampaignBarrier(roster)
        with self.assertRaises(ValueError): self.campaign.register(self.left)
        with self.assertRaises(ValueError): self.campaign.register(episode('A', episode_id='3'*64))
        with self.assertRaises(ValueError): self.campaign.register(deepcopy(self.left))

    def test_all_declared_episodes_register_before_development(self):
        left, right = episode('A'), episode('B')
        campaign = b.CampaignBarrier({left.id: 'A', right.id: 'B'}); campaign.register(left)
        with self.assertRaises(ValueError):
            left.develop_and_freeze(self.providers['A'], bundle=bundle(left, 'development'), journal=None, frozen_output='/generated-frozen/A')
        self.assertEqual(self.executions, [])

    def test_unequal_paired_resource_caps_rejected_at_registration(self):
        limits = resources('inference'); limits['producer_seconds'] += 1
        right = episode('B', inference_resources=limits)
        campaign = b.CampaignBarrier({self.left.id: 'A', right.id: 'B'})
        left = episode('A'); campaign.register(left)
        with self.assertRaises(ValueError): campaign.register(right)

    def test_mismatched_scientific_profiles_rejected(self):
        left, right = episode('A'), episode('B', profile=b.PROFILES[1])
        campaign = b.CampaignBarrier({left.id: 'A', right.id: 'B'}); campaign.register(left)
        with self.assertRaises(ValueError): campaign.register(right)

    def test_roster_and_fixed_design_mutation_refused(self):
        self.campaign.roster['3'*64] = 'A'
        with self.assertRaises(ValueError): self.freeze()
        self.assertEqual(self.executions, [])
        self.campaign.roster.pop('3'*64); self.left.inference_resources['producer_seconds'] += 1
        with self.assertRaises(ValueError): self.freeze()
        self.assertEqual(self.executions, [])

    def test_declaration_is_detached_and_immutable_after_construction(self):
        declaration = {'uses_unlabeled_test_context': False, 'description': 'original'}
        item = episode(declaration=declaration); declaration['description'] = 'caller mutated'
        self.assertEqual(item.declaration['description'], 'original')
        self.left.declaration['description'] = 'changed after registration'
        with self.assertRaises(ValueError): self.freeze()

    def test_deadline_expiry_prevents_dispatch_and_terminates_episode(self):
        self.clock.return_value = DEADLINE
        with self.assertRaises(ValueError): self.freeze()
        self.assert_failed(self.left); self.assertEqual(self.executions, [])

    def test_wrong_role_clock_or_command_never_dispatches(self):
        for name in ('role', 'clock', 'command'):
            self.left.state = 'development'; self.left.phase_ids.clear()
            selected = bundle(self.left, 'development')
            if name == 'role': selected['request']['role'] = 'B'
            elif name == 'clock': selected['request']['clock']['phase_deadline'] += 1
            else: selected['request']['command'][-1] = '/candidate/other.py'
            with self.subTest(name=name), self.assertRaises(ValueError): self.freeze(selected=selected)
            self.assert_failed(self.left)
        self.assertEqual(self.executions, [])

    def test_bundle_hash_read_floor_and_budget_cannot_be_rewritten(self):
        for name in ('minimum', 'resource'):
            self.left.state = 'development'; self.left.phase_ids.clear()
            selected = bundle(self.left, 'development')
            if name == 'minimum': selected['minimum_hash_reads'] -= 1
            else: selected['request']['resources']['producer_seconds'] += 1
            with self.subTest(name=name), self.assertRaises(ValueError): self.freeze(selected=selected)
        self.assertEqual(self.executions, [])

    def test_development_cannot_mount_test_view_or_extra_private_files(self):
        selected = bundle(self.left, 'development'); selected['mounts']['/input'] = data_mount(self.left, 'inference')
        selected = repack(self.left, selected)
        with self.assertRaises(ValueError): self.freeze(selected=selected)
        self.assert_failed(self.left); self.assertEqual(self.executions, [])

    def test_paper_only_arm_cannot_receive_official_source(self):
        with self.assertRaises(ValueError):
            b.development_mounts(self.left.info, data_mount(self.left, 'development'), '/generated/paper.pdf',
                '/generated/common', common_files(), {'path': '/generated/develop.py', 'pin': b.a.pin(b'x')}, '/generated/code.tar.gz')
        selected = bundle(self.left, 'development')
        selected['mounts']['/private/join.json'] = b.file_mount('/generated/join.json', 'input', b.a.pin(b'private'))
        selected = repack(self.left, selected)
        with self.assertRaises(ValueError): self.freeze(selected=selected)
        self.assertEqual(self.executions, [])

    def test_code_arm_requires_exact_official_source(self):
        selected = bundle(self.right, 'development'); selected['mounts'].pop('/official/code.tar.gz')
        selected = repack(self.right, selected)
        with self.assertRaises(ValueError): self.freeze('B', selected)
        self.assert_failed(self.right); self.assertEqual(self.executions, [])

    def test_common_assets_cannot_add_author_encoder_runtime(self):
        selected = bundle(self.left, 'development')
        selected['mounts']['/common']['files']['encoder-runtime.py'] = b.a.pin(b'author implementation')
        selected = repack(self.left, selected)
        with self.assertRaises(ValueError): self.freeze(selected=selected)
        self.assert_failed(self.left); self.assertEqual(self.executions, [])

    def test_exact_provider_type_required_before_dispatch(self):
        with self.assertRaises(ValueError):
            self.left.develop_and_freeze(object(), bundle=bundle(self.left, 'development'), journal=None, frozen_output='/generated-frozen/A')
        self.assert_failed(self.left); self.assertEqual(self.executions, [])

    def test_capture_selection_binds_this_episode_and_captured_files(self):
        def changed(*args, **kwargs):
            capture = self.capture(*args, **kwargs); capture['result']['episode_id'] = self.right.id; return capture
        self.observe.side_effect = changed
        with self.assertRaises(ValueError): self.freeze()
        self.assert_failed(self.left); self.promote.assert_not_called()

    def test_promotion_failure_retains_charges_and_prevents_retry(self):
        def failed(provider, *args, **kwargs):
            provider.read_used += 11; provider.write_used += 22; raise ValueError('generated publication failure')
        self.promote.side_effect = failed
        with self.assertRaisesRegex(ValueError, 'generated publication failure'): self.freeze()
        self.assert_failed(self.left)
        self.assertEqual((self.providers['A'].read_used, self.providers['A'].write_used), (111, 222))
        with self.assertRaises(ValueError): self.freeze()
        self.assertEqual(len(self.executions), 1)

    def test_development_capture_finishes_before_freeze(self):
        def late(*args, **kwargs):
            capture = self.capture(*args, **kwargs); capture['receipt_finished'] = 401.0; return capture
        self.observe.side_effect = late
        with self.assertRaises(ValueError): self.freeze()
        self.assert_failed(self.left)

    def test_freeze_manifest_binds_full_design_and_actual_captured_artifacts(self):
        receipt = self.freeze()
        self.assertEqual(self.left.state, 'frozen'); self.assertFalse(receipt['runtime_qualified'])
        artifact = self.left.artifact
        for key, value in (('episode_id', self.left.id), ('role', 'A'), ('profile', self.left.profile),
                           ('design_identity', self.left.design_identity), ('declaration', self.left.declaration),
                           ('development_identity', self.left.development['view_identity']),
                           ('test_identity', self.left.test['view_identity']), ('inference_resources', self.left.inference_resources)):
            self.assertEqual(artifact[key], value)
        self.assertEqual(set(artifact['files']), {'selected.py', 'model.bin'})
        self.assertEqual((self.left.last_read_used, self.left.last_write_used), (111, 222))

    def test_every_method_freezes_before_campaign_seal_and_test(self):
        self.freeze()
        with self.assertRaises(ValueError): self.campaign.seal()
        with self.assertRaises(ValueError): self.infer()
        self.assertEqual(len(self.executions), 1)

    def test_shared_provider_cannot_seal_paired_campaign(self):
        self.providers['B'] = self.providers['A']
        self.freeze('A'); self.freeze('B')
        with self.assertRaises(ValueError): self.campaign.seal()

    def test_different_actual_images_cannot_seal_paired_campaign(self):
        self.freeze('A')
        selected = bundle(self.right, 'development', image='sha256:'+'e'*64)
        self.freeze('B', selected)
        with self.assertRaises(ValueError): self.campaign.seal()

    def test_equal_or_nested_cross_episode_roots_cannot_seal(self):
        for nested in (False, True):
            self.providers['B'].control_root = self.providers['A'].control_root / 'nested' if nested else self.providers['A'].control_root
            if self.left.state == 'development': self.freeze('A'); self.freeze('B')
            with self.subTest(nested=nested), self.assertRaises(ValueError): self.campaign.seal()

    def test_frozen_artifact_change_prevents_test_and_release(self):
        self.freeze_pair(); self.left.artifact['files']['model.bin']['sha256'] = '0'*64
        with self.assertRaises(ValueError): self.infer()
        with self.assertRaises(ValueError): self.campaign.release()
        self.assertEqual(len(self.executions), 2)

    def test_inference_cannot_reset_provider_cumulative_counters(self):
        self.freeze_pair(); self.providers['A'].read_used = 0
        with self.assertRaises(ValueError): self.infer()
        self.assert_failed(self.left); self.assertEqual(len(self.executions), 2)

    def test_inference_cannot_replace_provider_or_budget(self):
        self.freeze_pair()
        with self.assertRaises(ValueError): self.infer(provider=inert_provider('replacement'))
        self.assert_failed(self.left); self.assertEqual(len(self.executions), 2)

    def test_inference_cannot_replace_prior_exposure_registry_or_append_foreign_pin(self):
        self.freeze_pair(); selected = self.inference_bundle()
        old_pin = next(iter(self.left.exposures)); self.providers['A'].exposures[old_pin] = '/foreign/replaced.json'
        with self.assertRaises(ValueError): self.infer(selected=selected)
        self.assert_failed(self.left); self.assertEqual(len(self.executions), 2)

    def test_foreign_exposure_append_is_refused(self):
        self.freeze_pair(); selected = self.inference_bundle()
        self.providers['A'].exposures['f'*64] = '/foreign/extra.json'
        with self.assertRaises(ValueError): self.infer(selected=selected)
        self.assert_failed(self.left)

    def test_inference_image_cannot_change(self):
        self.freeze_pair(); selected = self.inference_bundle(); selected['request']['image'] = 'sha256:'+'e'*64
        selected = repack(self.left, selected)
        with self.assertRaises(ValueError): self.infer(selected=selected)
        self.assert_failed(self.left); self.assertEqual(len(self.executions), 2)

    def test_inference_cannot_substitute_frozen_model_mount(self):
        self.freeze_pair(); selected = self.inference_bundle()
        desc = selected['mounts']['/candidate/model.bin']; desc['files']['model.bin']['sha256'] = '0'*64
        selected = repack(self.left, selected)
        with self.assertRaises(ValueError): self.infer(selected=selected)
        self.assert_failed(self.left); self.assertEqual(len(self.executions), 2)

    def test_inference_excludes_development_common_assets_and_previous_outputs(self):
        self.freeze_pair(); selected = self.inference_bundle()
        selected['mounts']['/previous/RESULT.json'] = b.file_mount('/generated/RESULT.json', 'input', b.a.pin(b'previous output'))
        selected = repack(self.left, selected)
        with self.assertRaises(ValueError): self.infer(selected=selected)
        self.assert_failed(self.left); self.assertEqual(len(self.executions), 2)

    def test_inference_must_start_after_actual_freeze(self):
        self.freeze_pair()
        def earlier(*args, **kwargs):
            capture = self.capture(*args, **kwargs); capture['receipt_started'] = 399.0; return capture
        self.observe.side_effect = earlier
        with self.assertRaises(ValueError): self.infer()
        self.assert_failed(self.left)

    def test_retired_native_resource_names_cannot_recur(self):
        self.freeze_pair()
        def reused(*args, **kwargs):
            capture = self.capture(*args, **kwargs)
            capture['retired_resources'][0]['name'] = next(iter(self.left.closed_names)); return capture
        self.observe.side_effect = reused
        with self.assertRaises(ValueError): self.infer()
        self.assert_failed(self.left)

    def test_full_1803_prediction_coverage_required(self):
        self.freeze_pair()
        def partial(*args, **kwargs):
            capture = self.capture(*args, **kwargs); capture['result']['predictions'].pop(); return capture
        self.observe.side_effect = partial
        with self.assertRaises(ValueError): self.infer()
        self.assert_failed(self.left)
        with self.assertRaises(ValueError): self.right.complete_predictions()

    def test_duplicate_test_ids_refused(self):
        self.freeze_pair()
        def duplicate(*args, **kwargs):
            capture = self.capture(*args, **kwargs)
            capture['result']['predictions'][-1] = deepcopy(capture['result']['predictions'][0]); return capture
        self.observe.side_effect = duplicate
        with self.assertRaises(ValueError): self.infer()
        self.assert_failed(self.left)

    def test_nonfinite_four_class_scores_refused(self):
        self.freeze_pair()
        def nonfinite(*args, **kwargs):
            capture = self.capture(*args, **kwargs)
            row = capture['result']['predictions'][0]
            row.pop('prediction'); row['scores'] = [0.1, 0.2, float('inf'), 0.4]
            return capture
        self.observe.side_effect = nonfinite
        with self.assertRaises(ValueError): self.infer()
        self.assert_failed(self.left)

    def test_result_must_bind_actual_selected_artifact(self):
        self.freeze_pair()
        def substituted(*args, **kwargs):
            capture = self.capture(*args, **kwargs); capture['result']['artifact_identity'] = '0'*64; return capture
        self.observe.side_effect = substituted
        with self.assertRaises(ValueError): self.infer()
        self.assert_failed(self.left)

    def test_prospective_profile_remains_bound_in_complete_release(self):
        declaration = {'uses_unlabeled_test_context': True, 'description': 'generated declared joint normalization'}
        self.left, self.right = episode('A', profile=b.PROFILES[1], declaration=declaration), episode('B', profile=b.PROFILES[1], declaration=declaration)
        self.items = {'A': self.left, 'B': self.right}
        self.campaign = b.CampaignBarrier({item.id: role for role, item in self.items.items()})
        for item in self.items.values(): self.campaign.register(item)
        self.freeze_pair(); self.infer('A'); self.infer('B')
        released = self.left.complete_predictions(); receipt = released['release']
        self.assertEqual(receipt['profile'], b.PROFILES[1]); self.assertEqual(receipt['declaration'], declaration)
        self.assertTrue(receipt['requires_separate_outcome_binding'])
        self.assertFalse(receipt['current_paper_win_qualified']); self.assertFalse(receipt['scientific_qualification'])
        self.assertEqual(receipt['predictions_pin'], b.pin_json(released['predictions']))
        body = deepcopy(receipt); claimed = body.pop('release_identity')
        self.assertEqual(b.r.identity(body), claimed)
        body.pop('profile'); self.assertNotEqual(b.r.identity(body), claimed)

    def test_failed_episode_stops_other_test_exposure_and_feedback(self):
        self.freeze_pair(); self.left.state = 'failed'
        with self.assertRaises(ValueError): self.infer('B')
        with self.assertRaises(ValueError): self.campaign.release()
        self.assertEqual(len(self.executions), 2)

    def test_completed_inference_has_no_retry_or_redevelopment(self):
        self.freeze_pair(); self.infer()
        with self.assertRaises(ValueError): self.infer()
        with self.assertRaises(ValueError): self.freeze()
        self.assertEqual(len(self.executions), 3)

    def test_replayed_development_phase_id_refused_before_test_dispatch(self):
        self.freeze_pair(); selected = self.inference_bundle()
        selected['request']['phase_id'] = 'A_development'; selected = repack(self.left, selected)
        with self.assertRaises(ValueError): self.infer(selected=selected)
        self.assert_failed(self.left); self.assertEqual(len(self.executions), 2)

    def test_feasibility_is_dataset_phase_not_1803_processes(self):
        result = b.feasibility(279390224, 2)
        self.assertEqual(result['test_phases'], 2)
        self.assertEqual(result['complete_epochs_per_phase'], 1803)
        self.assertEqual(result['reference_batches_per_phase'], 57)
        self.assertEqual(result['artifact_hash_read_bytes'], 4*279390224)
        self.assertEqual(result['minimum_Docker_CLI_calls'], 80)
        self.assertIsNone(result['measured_runtime_seconds'])
        self.assertFalse(result['GPU_provider_qualified']); self.assertFalse(result['scientific_budget_adopted'])


if __name__ == '__main__':
    unittest.main()
