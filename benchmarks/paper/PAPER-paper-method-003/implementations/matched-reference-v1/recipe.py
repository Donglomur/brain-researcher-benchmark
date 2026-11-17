"""Prospective released-profile REVE reference; not historical Table 12 parity.

Pure metadata/stage functions are executable without scientific dependencies.
Native execution remains under the existing closed installation gate.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
PREDECESSOR = HERE.parent / 'opaque-submission-v1/adapter.py'
PREDECESSOR_SHA = '5e57a4de3f5a0d0015f04e576a78d8a13fe18f5df475864e0f0f62a82c6b4bcf'
FLAT = 131584
COUNTS = {'train': 6300, 'val': 1734, 'test': 1803}
STAGES = ({'name': 'lp', 'epochs': 20, 'warmup_epochs': 5, 'patience': 5},
          {'name': 'ft', 'epochs': 5, 'warmup_epochs': 0, 'patience': 11})
SEEDS = (42, 43, 44, 45, 46)
PRIMARY_FILES = {'encoder.safetensors', 'encoder-config.json',
                 'ENCODER_ARCHITECTURE.json', 'MODEL_LICENSE.txt'}
CONFIG_PIN = {'bytes':428, 'sha256':'5b74a19202d1aaa5d1814b26b720e4184cd0047f28a672834d390318eed05945'}
LICENSE_PIN = {'bytes':17760, 'sha256':'cda77c38a1fcf002009678642608748f221458f83bc5ee3944f1e0c83939cd96'}
ARCHITECTURE_PIN = {'bytes':1394, 'sha256':'e04116c0986236bab99a624f1b0b5f67e5fa0bea31800925f0e080a6fc1eaeec'}


class Refusal(ValueError): pass


def need(ok, message):
    if not ok: raise Refusal(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def identity(value): return hashlib.sha256(encoded(value)).hexdigest()


def adapter():
    body = PREDECESSOR.read_bytes()
    need(hashlib.sha256(body).hexdigest() == PREDECESSOR_SHA, 'opaque composition dependency changed')
    module = ModuleType('_reve_matched_opaque'); module.__file__ = str(PREDECESSOR)
    exec(compile(body, str(PREDECESSOR), 'exec'), module.__dict__)
    return module


def encoder_shapes():
    """Exact native/HF common keys; no tensors allocated or checkpoint inspected."""
    shapes = {'to_patch_embedding.0.weight': [512, 200], 'to_patch_embedding.0.bias': [512],
              'mlp4d.0.weight': [512, 4], 'mlp4d.2.weight': [512], 'mlp4d.2.bias': [512],
              'ln.weight': [512], 'ln.bias': [512]}
    for layer in range(22):
        prefix = f'transformer.layers.{layer}.'
        shapes.update({prefix+'0.norm.weight': [512], prefix+'0.to_qkv.weight': [1536, 512],
                       prefix+'0.to_out.weight': [512, 512], prefix+'1.net.0.weight': [512],
                       prefix+'1.net.1.weight': [2722, 512], prefix+'1.net.3.weight': [512, 1361]})
    return shapes


def pretrained_shapes(): return {**encoder_shapes(), 'cls_query_token': [1, 1, 512]}


def classifier_shapes():
    return {**{'encoder.'+key: value for key, value in encoder_shapes().items()},
            'cls_query_token': [1, 1, 512], 'linear_head.1.weight': [FLAT],
            'linear_head.3.weight': [4, FLAT], 'linear_head.3.bias': [4]}


def validate_shapes(shapes, *, complete_classifier=False):
    expected = classifier_shapes() if complete_classifier else pretrained_shapes()
    need(type(shapes) is dict and shapes == expected, 'complete exact native tensor names/shapes required')
    return {'tensor_count': len(expected), 'parameters': sum(math.prod(s) for s in expected.values())}


def reference_spec(seed):
    need(type(seed) is int and seed in SEEDS, 'root-provisional reference seed roster required')
    result = {
        'schema': 'reve-matched-reference-recipe-v1', 'classification': 'prospective_released_reference',
        'historical_Table12_equivalent': False, 'scientific_execution_admitted': False,
        'source_commit': '06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7',
        'data_profile': 'released-06a7059-direct200', 'participants': 109, 'recordings': 654,
        'epochs': dict(COUNTS), 'batch_size': 32, 'drop_last': False, 'world_size': 1,
        'training_mode': 'lp+ft', 'stages': [dict(s) for s in STAGES],
        'stage_transition': 'final_or_early_stopped_LP_state_to_FT_without_reloading_LP_best',
        'LP_trainable': ['cls_query_token', 'linear_head.*'], 'FT_trainable': 'all_parameters',
        'dropout': 0.0, 'mixup': False, 'lora': False, 'soup': False, 'revin': False,
        'input': 'float64_microvolts_divide100_then_float32', 'patch_size': 200,
        'patch_stride': 180, 'patches_per_channel': 4, 'unused_final_samples': 60,
        'pooling': 'query_context_prepended_then_flatten', 'head_width': FLAT,
        'optimizer': {'name': 'pinned_native_StableAdamW', 'lr': 1e-4, 'weight_decay': 1e-2,
                      'betas': [0.92, 0.999], 'eps': 1e-9, 'fresh_per_stage': True},
        'scheduler': {'name': 'ReduceLROnPlateau', 'mode': 'max', 'factor': 0.5, 'patience': 5,
                      'metric': 'validation_accuracy', 'when': 'epoch_index > warmup_epochs'},
        'warmup': 'LambdaLR:(10**(step/(197*warmup_epochs))-1)/9; first_LP_update_lr0',
        'gradient_clip_norm': 2.0, 'autocast': 'cuda_float16', 'grad_scaler_enabled': False,
        'grad_scaler_reason': 'preserve_source_top_level_torch_dtype_lookup_default_fp32',
        'selection': 'strict_validation_BA_improvement_from0_per_stage; shared_best_replaced_on_FT_improvement',
        'no_FT_positive_BA': 'retain_saved_LP_best_if_any; record_selected_stage',
        'no_positive_BA_any_stage': 'refuse_missing_selected_checkpoint',
        'early_stop': 'consecutive_nonimprovements > stage_patience',
        'seed': seed, 'RNG': 'seed_Python_NumPy_Torch_CUDA_once_before_native_construction',
        'construction_RNG': 'native_encoder_then_classifier; no_transient_HF_AutoModel; no_historical_RNG_parity',
        'loader': {'num_workers': 0, 'train_generator_seed': seed, 'generator_persists_across_stages': True,
                   'validation_generator': None, 'test_loader_created_only_after_freeze': True},
        'loader_deviation': 'single_process_nonpersistent_instead_of_released8persistent_workers; actual_order_hashes_recorded',
        'position_noise': 'native_NumPy_normal0_std0.0025_same_channel_noise_across_batch_in_train_mode_including_LP',
        'inference': 'selected_complete_native_state; eval; cuda_fp16_autocast; no_position_noise; pointwise',
        'test_feedback_during_fit': 0, 'max_train_presentations': 157500,
        'max_optimizer_step_attempts': 4925, 'max_validation_panels': 25,
        'maximum_test_predictions_per_selected_fit': 1803,
        'scientific_budget_fields_required': required_budget_fields(),
    }
    result['recipe_identity'] = identity(result)
    return result


def required_budget_fields():
    return {name: None for name in (
        'physical_GPU_profile', 'immutable_scientific_image', 'qualified_provider_manifest',
        'accelerator_allocation_seconds', 'cpu_core_seconds', 'wall_seconds', 'cpu_threads',
        'ram_bytes', 'vram_bytes', 'cumulative_artifact_write_bytes', 'source_read_bytes',
        'complete_test_panel_inference_seconds', 'agent_model_revision_and_scaffold',
        'agent_input_tokens', 'agent_output_tokens', 'agent_requests', 'agent_wall_seconds',
        'agent_tool_calls', 'paired_uncertainty_and_acceptance_policy')}


def work_plan():
    """Root-provisional slots, not an admitted campaign or measured compute estimate."""
    fits = []
    for condition in ('paper_data', 'paper_data_code'):
        for kind, seeds in (('reconstruction', SEEDS), ('development', (142,)*10), ('confirmation', SEEDS)):
            for index, seed in enumerate(seeds):
                fits.append({'condition': condition, 'kind': kind, 'slot': index, 'seed': seed,
                             'train_presentation_cap': 157500, 'validation_panel_cap': 25,
                             'held_predictions_after_freeze': 0 if kind == 'development' else 1803})
    return {'status': 'root_provisional_source_design_not_execution_admission', 'fits': fits,
            'separate_operator_reference_seeds': list(SEEDS), 'primary_access': 'literal_repository_access_contrast',
            'hardware_and_agent_budgets': required_budget_fields(), 'original_scientific_contract_changed': False}


def phase_data(info, phase):
    """Expose no test records to a fit; preserve every original allowed training label."""
    need(phase in ('fit', 'predict'), 'explicit fit or predict phase required')
    rows = [r for r in info['records'] if (r['split'] != 'test') == (phase == 'fit')]
    totals = {split: sum(r['shape'][0] for r in rows if r['split'] == split) for split in COUNTS}
    need(totals == ({'train':6300, 'val':1734, 'test':0} if phase == 'fit' else {'train':0, 'val':0, 'test':1803}),
         'complete phase support required')
    if phase == 'predict':
        need(all(set(r) == {'split','shape','sha256','event_ids','signal'} for r in rows),
             'prediction input cannot contain labels or original identity')
    return rows


class StageController:
    """Source checkpoint/scheduler/stop decisions, independent of model implementation."""
    def __init__(self, stage):
        need(stage in ('lp', 'ft'), 'known stage required')
        self.spec = dict(STAGES[0 if stage == 'lp' else 1]); self.epoch = 0
        self.best = 0.0; self.patience = 0; self.stopped = False

    def observe(self, *, accuracy, balanced_accuracy):
        need(not self.stopped and self.epoch < self.spec['epochs'], 'stage already exhausted')
        need(all(type(v) in (int,float) and math.isfinite(v) and 0 <= v <= 1
                 for v in (accuracy, balanced_accuracy)), 'finite validation-only metrics required')
        improved = balanced_accuracy > self.best
        if improved: self.best = balanced_accuracy; self.patience = 0
        else: self.patience += 1
        step_scheduler = self.epoch > self.spec['warmup_epochs']
        epoch = self.epoch; self.epoch += 1
        self.stopped = self.patience > self.spec['patience'] or self.epoch == self.spec['epochs']
        return {'stage': self.spec['name'], 'epoch': epoch, 'save_best': improved,
                'step_scheduler': step_scheduler, 'scheduler_value': accuracy,
                'stop': self.stopped, 'patience': self.patience}


def drive_fit(backend):
    """Trusted algorithm core. Backend has only train/validation; never a test callback.

    Native dispatch is separately closed. Inert backends can validate the complete
    source call graph without importing a tensor package or claiming a fit.
    """
    history = []; selected = None
    for spec in STAGES:
        backend.begin_stage(dict(spec)); control = StageController(spec['name'])
        while not control.stopped:
            backend.train_epoch(control.epoch)
            metrics = backend.validation_metrics()
            need(set(metrics) == {'accuracy','balanced_accuracy'}, 'validation metrics only')
            decision = control.observe(**metrics)
            if decision['save_best']:
                backend.snapshot_selected(); selected = (spec['name'], decision['epoch'])
            if decision['step_scheduler']: backend.step_scheduler(metrics['accuracy'])
            history.append({**decision, **metrics})
    need(selected is not None, 'source never produced a positive-BA checkpoint')
    backend.restore_selected()
    return {'selected_stage': selected[0], 'selected_epoch': selected[1], 'history': history,
            'training_presentations': 6300*len(history), 'validation_panels': len(history),
            'historical_Table12_equivalent': False, 'held_predictions_generated': 0}


def primary_common(directory, files):
    """Primary asset ABI excludes all author executable encoder implementation."""
    a = adapter()
    need(type(files) is dict and set(files) == PRIMARY_FILES, 'literal primary asset allowlist required')
    for pin in files.values(): a.descriptor(pin)
    need(files['encoder.safetensors'] == a.ENCODER, 'exact same pretrained encoder weights required')
    need(files['encoder-config.json'] == CONFIG_PIN and files['MODEL_LICENSE.txt'] == LICENSE_PIN,
         'exact cached official config and license required; arbitrary embedded source is forbidden')
    architecture = (HERE/'ENCODER_ARCHITECTURE.json').read_bytes()
    need(a.pin(architecture) == ARCHITECTURE_PIN and files['ENCODER_ARCHITECTURE.json'] == ARCHITECTURE_PIN,
         'exact benchmark-owned nonexecutable architecture metadata')
    need(Path(directory).is_absolute(), 'absolute common asset root required')
    return {'path': str(directory), 'kind': 'directory', 'purpose': 'program', 'files': files}


def primary_requests(infos, packets, programs, common, *, phase_ids, image, exposure_pins, origin, deadline, resources):
    """Existing provider ABI; source construction only, not a new runner/authority."""
    a = adapter(); _, contract, _ = a.transport_package()
    need(common == primary_common(common['path'], common['files']), 'exact primary common assets')
    need(len(infos) == len(packets) == len(programs) == len(phase_ids) == len(exposure_pins) == 2,
         'exactly two primary access conditions')
    need([i['role'] for i in infos] == ['A','B'] and infos[0]['data_identity'] == infos[1]['data_identity'] and
         infos[0]['test_ids'] == infos[1]['test_ids'] and phase_ids[0] != phase_ids[1], 'same complete paired data required')
    result = []
    for info, packet, program, phase_id, exposure in zip(infos, packets, programs, phase_ids, exposure_pins):
        sizes = {r['signal']: packet['files'][r['signal']]['bytes'] for r in info['records']}
        need(packet == a.packet_mount(info, packet['path'], info['manifest_pin'], sizes), 'selected complete packet required')
        need(set(program) == {'path','kind','purpose','files'} and program['kind'] == 'directory' and
             program['purpose'] == 'program' and set(program['files']) == {'solution.py'}, 'one frozen candidate program')
        a.descriptor(program['files']['solution.py'])
        mounts = {'/input': packet, '/candidate': program, '/common': common}
        request = {'schema':'osl_owned_phase_request_v1','phase_id':phase_id,'action':'held_attempt','role':info['role'],
                   'image':image,'command':['/usr/local/bin/python','-I','-B','/candidate/solution.py'], 'workdir':'/work',
                   'source':a.pin(a.canonical(program['files'])),'exposure':a.descriptor(exposure),
                   'clock':{'origin':origin,'phase_deadline':deadline},'resources':dict(resources),
                   'output':{'kind':'generic','manifest':'OUTPUTS.json'}}
        contract.validate_request(request, mounts, deadline)
        minimum = 2*sum(p['bytes'] for mount in mounts.values() for p in mount['files'].values())
        need(resources['source_read_bytes'] > minimum and resources['max_files'] == 2 and
             resources['max_directories'] == 1 and resources['manifest_bytes'] <= 65536 and
             resources['max_file_bytes'] <= a.RESULT_CAP, 'complete hashing and bounded original result ABI')
        result.append({'request':request,'mounts':mounts,'materials_identity':info['materials_identity'],
                       'minimum_input_hash_reads':minimum,'runtime_qualified':False,
                       'scientific_budget_adopted':False,'protocol':'literal_primary_repository_access'})
    return result


def require_installation():
    adapter()._require_installation()


def validate_fit_receipt(document, info, expected_fit_identity):
    """Authenticate operator-selected metadata; this is not execution admission."""
    fields = {'selected_stage','selected_epoch','history','training_presentations','validation_panels',
              'historical_Table12_equivalent','held_predictions_generated','schema','recipe','materials_identity',
              'data_identity','checkpoint','audit','initial_rng','final_rng','attention_profile','runtime',
              'initial_head_identity','reuse_policy','historical_classifier_authenticated','scientific_qualification','identity'}
    need(type(document) is dict and set(document) == fields, 'closed complete operator fit receipt required')
    body = dict(document); claimed = body.pop('identity')
    need(type(expected_fit_identity) is str and len(expected_fit_identity) == 64 and
         expected_fit_identity == claimed == identity(body), 'independently selected fit identity differs')
    need(document['schema'] == 'reve-matched-fit-receipt-v1' and document['data_identity'] == info['data_identity'] and
         document['recipe'] == reference_spec(document['recipe'].get('seed')) and
         document['reuse_policy'] == 'operator_reference_only_same_data_identity_across_both_primary_conditions',
         'recipe/data/operator-reference reuse policy differs')
    need(all(document[name] is False for name in ('historical_Table12_equivalent','historical_classifier_authenticated','scientific_qualification')) and
         document['held_predictions_generated'] == 0, 'fit cannot claim historical qualification or test predictions')
    a = adapter(); a.descriptor(document['checkpoint'])
    for name in ('initial_rng','final_rng','initial_head_identity','materials_identity','data_identity'):
        need(isinstance(document[name],str) and a.HEX.fullmatch(document[name]), 'fixed fit identity required: '+name)
    need(document['attention_profile'] in ('native_flash_attn','native_sdpa_dispatch') and
         type(document['runtime']) is dict and set(document['runtime']) == {'torch','numpy','safetensors'} and
         all(isinstance(v,str) and 0 < len(v) < 128 for v in document['runtime'].values()), 'frozen observed runtime required')
    history = document['history']; audit = document['audit']
    need(type(history) is list and 0 < len(history) <= 25 and type(audit) is list and len(audit) == len(history), 'bounded complete fit trace')
    cursor = 0; selected = None
    for stage in ('lp','ft'):
        control = StageController(stage)
        while not control.stopped:
            need(cursor < len(history), 'incomplete stage trace')
            row = history[cursor]
            need(type(row) is dict and set(row) == {'stage','epoch','save_best','step_scheduler','scheduler_value','stop','patience','accuracy','balanced_accuracy'}, 'closed validation trace')
            decision = control.observe(accuracy=row['accuracy'], balanced_accuracy=row['balanced_accuracy'])
            need(row == {**decision,'accuracy':row['accuracy'],'balanced_accuracy':row['balanced_accuracy']}, 'source stage decisions differ')
            trace = audit[cursor]
            need(type(trace) is dict and set(trace) == {'stage','epoch','presentations','step_attempts','order_identity','initial_rng','final_rng'} and
                 trace['stage'] == stage and trace['epoch'] == decision['epoch'] and trace['presentations'] == 6300 and
                 trace['step_attempts'] == 197, 'complete original training pass trace required')
            need(all(isinstance(trace[k],str) and a.HEX.fullmatch(trace[k]) for k in ('order_identity','initial_rng','final_rng')), 'bounded RNG/order identities required')
            if decision['save_best']: selected = (stage,decision['epoch'])
            cursor += 1
    need(cursor == len(history) and selected == (document['selected_stage'],document['selected_epoch']) and
         document['training_presentations'] == 6300*cursor and document['validation_panels'] == cursor,
         'selected-state/horizon accounting differs')
    return document


if __name__ == '__main__':
    print(json.dumps({'reference': reference_spec(42), 'paired_plan': work_plan()}, indent=2))
