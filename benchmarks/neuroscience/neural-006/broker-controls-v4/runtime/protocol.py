"""NEURAL006 source contract. Definitions only; no data access or execution on import."""
import hashlib
import json
import math
import random

TRAIN = ('223','207','209','234','231','228','240','239','245','206','212','224','204','233','211','217','202','222','237','219','238','215','241','230','229','203')
DEV = ('221','213','225','214','232','205','244')
RESERVE = ('226','227','216','201','208','220','210','236')
ACTIVE = tuple(sorted(TRAIN + DEV))
SOURCE = tuple(sorted(ACTIVE + RESERVE))
TARGETS = ('FRN_N2_offer', 'P3b_offer')
PRIMITIVES = ('offer','rp','exp_valence','ep_valence','exp_arousal','ep_arousal')
FEATURES = PRIMITIVES + ('trialLocal','trialGlobal','abs_R','abs_V','abs_A')
ARMS = ('mean','N','R','V','J')
INPUTS = {
    'BEH_ug.csv': (4953755, '7de05b2018db423ecf4af3a24f978dd3925108695b2ed4328e389b851acb1bd0'),
    'df_FRN_N2_offer.csv': (245958, '96567c3927505281abcf015c517c83dda4a2d7a0fc6e6830cd2b0f195cc8fce5'),
    'df_P3b_offer.csv': (243104, 'bdcce68dec42e2aa4e9c16bfc59f7647abf650beaa64ddf3ec842ab2e83413cc'),
}

class Refusal(ValueError):
    pass

def need(ok, reason):
    if not ok:
        raise Refusal(reason)

def exact_keys(value, names, reason):
    need(type(value) is dict and set(value) == set(names), reason)

def finite(value):
    return type(value) in (int, float) and math.isfinite(value)

def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def validate_plan(plan):
    exact_keys(plan, ('schema','stage','candidate_modes','recipe_sha256','source_sha256',
        'resampling','limits','reserve_authorization','development_tuning','candidate_seeds'), 'plan_fields')
    need(plan['schema'] == 'neural006-investigation-plan-v1', 'plan_schema')
    need(plan['stage'] in ('development_lopo33', 'reserved_frozen33_test8'), 'stage')
    need(plan['candidate_modes'] == ['frozen_program','adaptive_investigation'], 'matched_modes')
    exact_keys(plan['candidate_seeds'],('frozen_program','adaptive_investigation'),'candidate_seed_fields')
    need(all(type(v) is int and 0<=v<2**63 for v in plan['candidate_seeds'].values()),'prespecified_candidate_seeds')
    exact_keys(plan['development_tuning'],('used_dev7','selection_history','refitted_training_recipe'),'tuning_disclosure')
    need(type(plan['development_tuning']['used_dev7']) is bool,'tuning_boolean')
    for key in ('selection_history','refitted_training_recipe'):
        need(type(plan['development_tuning'][key]) is str and 0<len(plan['development_tuning'][key].encode())<=4096,'tuning_history')
    for name in ('recipe_sha256','source_sha256'):
        need(type(plan[name]) is str and len(plan[name]) == 64 and
             all(x in '0123456789abcdef' for x in plan[name]), name)
    limits = plan['limits']
    exact_keys(limits, ('wall_seconds','cleanup_seconds','cpu_seconds','memory_bytes',
        'retained_bytes','read_bytes','staged_write_bytes','per_file_bytes','model_artifact_bytes','tool_calls_per_case',
        'candidate_seconds_per_case','max_fit_calls','max_cases','max_files'), 'limit_fields')
    need(all(type(v) is int and v > 0 for v in limits.values()), 'finite_positive_limits')
    need(limits['cleanup_seconds'] < limits['wall_seconds'], 'cleanup_reservation')
    need(limits['per_file_bytes'] <= limits['retained_bytes'], 'file_reservation')
    need(4*((limits['model_artifact_bytes']+2)//3)+8192<=limits['per_file_bytes'],'model_artifact_transport_cap')
    exact_keys(plan['resampling'], ('bootstrap','trajectory_permutation'), 'resampling_fields')
    for kind, item in plan['resampling'].items():
        common=('replicates','seed','interpretation')
        specific=('unit','training_copies','held_exclusion','evaluation_weighting','transformations','failure_policy','quantiles') if kind=='bootstrap' else ('exchangeability_blocks','exchangeability_assumption','assumption_status')
        exact_keys(item, common+specific, 'replicate_fields')
        need(type(item['replicates']) is int and 0 <= item['replicates'] <= 2000, 'replicate_count')
        need(type(item['seed']) is int and 0 <= item['seed'] < 2**63, 'replicate_seed')
        expected = ('uncalibrated_participant_resampling_sensitivity' if kind == 'bootstrap'
                    else 'within_declared_block_participant_alignment_diagnostic')
        need(item['interpretation'] == expected, 'no_calibrated_or_causal_claim')
        if kind=='bootstrap':
            fixed={'unit':'paired_participant_180_trial_block','training_copies':'distinct_sampled_cluster_ids',
                'held_exclusion':'all_copies_of_original_held_person','evaluation_weighting':'multiplicity_over_33',
                'transformations':'refit_every_training_preprocess_model_and_selection',
                'failure_policy':'retain_every_failure_no_drop_no_retry_no_band'}
            need(all(item[key]==value for key,value in fixed.items()),'frozen_bootstrap_rules')
            q=item['quantiles'];need(type(q) is list and len(q)==2 and all(finite(x) for x in q) and 0<=q[0]<q[1]<=1,'explicit_sensitivity_quantiles')
        else:
            blocks=item['exchangeability_blocks'];need(type(blocks) is list and bool(blocks),'explicit_exchangeability_blocks')
            flat=[]
            for block in blocks:
                need(type(block) is list and len(block)>=2 and all(type(p) is str for p in block),'permutation_block')
                need(set(block)<=set(TRAIN) or set(block)<=set(DEV),'preserve_original26_7_roles')
                flat.extend(block)
            need(sorted(flat)==list(ACTIVE),'complete_disjoint_exchangeability_partition')
            need(item['assumption_status'] in ('declared_not_validated','unestablished'),'exchangeability_status')
            assumption=item['exchangeability_assumption']
            need(assumption is None or type(assumption) is str and 0<len(assumption.encode())<=4096,'exchangeability_assumption')
            need(assumption is not None or item['assumption_status']=='unestablished','no_fabricated_assumption')
    if plan['stage'] == 'development_lopo33':
        need(plan['reserve_authorization'] is None, 'reserve_not_in_development')
    else:
        grant = plan['reserve_authorization']
        exact_keys(grant, ('assessment_id','frozen_recipe_sha256','cross_family_release_record_sha256'), 'reserve_grant')
        need(type(grant['assessment_id']) is str and 0 < len(grant['assessment_id']) <= 128, 'assessment_id')
        need(grant['frozen_recipe_sha256'] == plan['recipe_sha256'], 'frozen_reserve_recipe')
        pin = grant['cross_family_release_record_sha256']
        need(type(pin) is str and len(pin) == 64 and all(c in '0123456789abcdef' for c in pin), 'cross_family_release_pin')
        # This route conditions on the33 frozen training people. Training-refit uncertainty is a different study.
        need(all(v['replicates'] == 0 for v in plan['resampling'].values()), 'reserved_resampling_unselected')
    return plan

def schedule(plan):
    """Explicit finite plan, generated before outcomes; repetitions are not independent cohorts."""
    validate_plan(plan)
    rows = [{'kind':'observed','replicate':0,'draw':list(ACTIVE),'permutation':list(ACTIVE)}]
    if plan['stage'] == 'development_lopo33':
        for kind in ('bootstrap','trajectory_permutation'):
            item = plan['resampling'][kind]
            rng = random.Random(item['seed'])
            for number in range(1, item['replicates'] + 1):
                draw = [rng.choice(ACTIVE) for _ in ACTIVE] if kind == 'bootstrap' else list(ACTIVE)
                permutation = list(ACTIVE)
                if kind == 'trajectory_permutation':
                    mapping={}
                    for block in item['exchangeability_blocks']:
                        moved=list(block);rng.shuffle(moved);mapping.update(zip(block,moved))
                    permutation=[mapping[p] for p in ACTIVE]
                rows.append({'kind':kind,'replicate':number,'draw':draw,'permutation':permutation})
    return rows

def case_roster(plan, replicate):
    held = ACTIVE if plan['stage'] == 'development_lopo33' else tuple(sorted(RESERVE))
    return [(person, replicate['draw'].count(person) if replicate['kind'] == 'bootstrap' else 1)
            for person in held]
