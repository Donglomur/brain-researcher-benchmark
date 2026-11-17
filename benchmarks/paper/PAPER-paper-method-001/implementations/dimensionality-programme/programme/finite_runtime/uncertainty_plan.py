"""Concrete presealed uncertainty-provider metadata, never scientific execution."""
from __future__ import annotations
import hashlib
import json
from .common import require, identity

DESIGNS = {'F10': 'finite_integer_pseudopop_calibrated_v1',
           'F11': 'crossed_known_ratio_mask_pairs_v1'}
RNG = 'numpy.PCG64.SeedSequence-axis-domain-v1'
RULES = {'U01_FIELLER', 'U02_LOG_DELTA', 'U03_TWO_AXIS_PERCENTILE'}


def materialize_seeds(recipe):
    """Exact expansion of presealed metadata; bounded to 999 uint64 integers."""
    seed_key = bytes.fromhex(recipe['master_seed_hex'])
    require(len(seed_key) == 32, 'ISSUER_SEED_MUST_BE_256_BIT_HEX')
    context = json.dumps(recipe['context'], separators=(',', ':')).encode()
    seeds = [int.from_bytes(hashlib.sha256(b'finite-S2-resample\0' + seed_key +
             context + b'\0' + str(i).encode()).digest()[:8], 'big') for i in range(999)]
    require(len(set(seeds)) == 999, 'PRESEALED_SEED_COLLISION')
    return {'seeds': seeds, 'seeds_sha256': hashlib.sha256(
        json.dumps(seeds, separators=(',', ':')).encode()).hexdigest()}


def build(contracts, cases_by_key, *, source_sha256, qualification_id,
          numpy_version, master_seed_hex, base_protocol):
    """Freeze before reference fit/calibration. The seed is issuer-selected.

    `cases_by_key` contains the complete admitted development/calibration/evaluation
    case descriptors; it is trusted metadata, never a participant request. A
    source-qualified RNG dependency and G14 certificate are supplied by the issuer.
    The fixed source algorithm, not an arbitrary callback recipe, creates jobs.
    """
    require(len(source_sha256) == 64 and qualification_id and numpy_version,
            'PROVIDER_SOURCE_ENVIRONMENT_NOT_QUALIFIED')
    require(type(master_seed_hex) is str and len(master_seed_hex) == 64,
            'ISSUER_SEED_MUST_BE_256_BIT_HEX')
    try:
        seed_key = bytes.fromhex(master_seed_hex)
    except ValueError:
        require(False, 'ISSUER_SEED_MUST_BE_256_BIT_HEX')
    require(set(cases_by_key) == set(contracts.keys), 'INCOMPLETE_PROVIDER_CASE_KEYS')
    definitions, plan = {}, {}
    for key_id, key in contracts.keys.items():
        cases = cases_by_key[key_id]
        require(len({x['case_id'] for x in cases}) == len(cases), 'DUPLICATE_PROVIDER_CASE')
        # Exactly 240 calibration + 1200 evaluation cases; development residuals
        # use the point estimator and do not require U01--03 providers.
        require(len(cases) == 1440, 'INCOMPLETE_PROVIDER_CASE_CENSUS')
        by_split = {stage: [x for x in cases if x['split'] == stage]
                    for stage in ('calibration', 'evaluation')}
        require(len(by_split['calibration']) == 240 and len(by_split['evaluation']) == 1200,
                'PROVIDER_SPLIT_CENSUS_CHANGED')
        for variant in contracts.variants(key_id):
            rules = sorted({ci['rule'] for ci in contracts.uncertainty_variants(key_id)
                            if ci['reference_id'] == variant['reference_id'] and
                            ci['variant'] == variant['variant']} & RULES)
            design = DESIGNS.get(key['family'], 'crossed_iid_rows_columns_aligned_trials')
            definition = provider_definition(key, source_sha256=source_sha256,
                qualification_id=qualification_id, numpy_version=numpy_version)
            definitions[variant['id']] = {rule: dict(definition) for rule in rules}
            for case in cases:
                job = case_job(key,variant,case,definition=definition,
                    master_seed_hex=master_seed_hex,base_protocol=base_protocol)
                plan[variant['id'] + '::' + case['case_id']] = {rule: dict(job) for rule in rules}
    return {'provider_definitions': definitions, 'provider_plan': plan,
            'provider_plan_sha256': identity(plan), 'source_sha256': source_sha256,
            'issuer_seed_commitment': hashlib.sha256(seed_key).hexdigest(),
            'qualification_pending_until_issuer_certificate': True}


def provider_definition(key, *, source_sha256, qualification_id, numpy_version):
    return {'operation': 'uncertainty.resample', 'source_sha256': source_sha256,
        'qualification_id': qualification_id,
        'algorithm': DESIGNS.get(key['family'], 'crossed_iid_rows_columns_aligned_trials'),
        'rng_source': {'algorithm': RNG, 'numpy_version': numpy_version},
        'resamples': 999, 'seed_derivation': 'sha256-source-variant-case-input-v1',
        'point_state_binding': 'actual frozen state injected and ancestry-bound by References.bundle'}


def case_job(key, variant, case, *, definition, master_seed_hex, base_protocol):
    """The actual per-case constructor used by the complete plan, no arrays."""
    source_sha256=definition['source_sha256'];qualification_id=definition['qualification_id']
    protocol={**base_protocol,**case['scientific_protocol'],
        'primary_key':key['id'],'family':key['family'],'target':key['target_class'],
        'protocol_id':key['protocol'],'trial_view':key['trial_view'],
        'reference_definition_presealed':True,'input_identity':case['input_sha256'],
        'resampling_design':definition['algorithm'],
        'resampling_qualification_id':qualification_id}
    parameters={'point_request':{**case['reference_parameters'],
        'reference_id':variant['reference_id'],'variant':variant['variant']},
        'seed_recipe':{'master_seed_hex':master_seed_hex,
            'context':[source_sha256,variant['id'],case['case_id'],case['input_sha256']]},
        'rng_source':definition['rng_source']}
    return {'point_id':variant['id'],'input_identity':case['input_sha256'],
        'definition_sha256':identity(definition),'operation':'uncertainty.resample',
        'qualification_id':qualification_id,'protocol':protocol,'parameters':parameters}
