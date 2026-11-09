"""Metadata-only join between independent qualification and actual admission.

No asset file, model weight, native input or query target is opened here.
read_json must authenticate every descriptor on its same FD. The independent
runtime signature binds environment, asset manifests, reporter and probe report;
this validator joins that body to authorized parameters and signed ancestors.
"""
from __future__ import annotations
from .io import Artifact, ContractError
from runtime.contracts import profile, exact, digest

ASSETS = ('checkpoint', 'tokenizer', 'model_runtime')
RUNTIME_STAGES = {'D00','D01','Q00','Q01','Q02','Q03','N00','E00','E02'}


def qualified_selection(content, *, read_json, implementation, attempt, stage,
                        parameters, inputs, receipts, limits):
    env = read_json(content['environment'], roles={'qualified_environment'}, cap=4_000_000)
    exact(env, {'schema','attempt','implementation_sha256','runtime_profile','stage_devices',
                'checkpoint','tokenizer','model_runtime','report_generator'}, 'qualified environment')
    if (env['schema'] != 'neural063_qualified_environment_v2' or env['attempt'] != attempt or
            env['implementation_sha256'] != implementation.sha256):
        raise ContractError('qualified environment belongs to another source/attempt')
    p = profile(env['runtime_profile'])
    from .workflow import COMPONENT
    if set(env['stage_devices']) != set(COMPONENT) or any(not isinstance(v,dict) for v in env['stage_devices'].values()):
        raise ContractError('qualification must bind exact device/containment declarations for all28 stages')
    if env['stage_devices'][stage] != limits['device_manifest']:
        raise ContractError('selected trusted worker devices/containment differ from qualified environment')
    if stage in RUNTIME_STAGES and parameters.get('runtime_profile') != p:
        raise ContractError('selected runtime profile differs from independent qualification')
    if 'runtime_profile' in parameters and parameters['runtime_profile'] != p:
        raise ContractError('an unqualified runtime profile cannot be carried as stage parameters')
    for key in (*ASSETS,'report_generator'):
        Artifact.parse(content[key])
        if content[key] != env[key]:
            raise ContractError('qualification asset/report descriptor substitution: ' + key)
    bundles = {}
    files = []
    names = set()
    for key in ('checkpoint','tokenizer'):
        value = read_json(content[key], roles={key}, cap=4_000_000)
        exact(value, {'schema','files'}, 'qualified '+key+' manifest')
        if value['schema'] != 'neural063_local_asset_manifest_v1' or not isinstance(value['files'],list) or not value['files']:
            raise ContractError('complete qualified asset metadata required')
        for item in value['files']:
            exact(item, {'name','artifact'}, 'qualified asset file')
            name = item['name']; ref = Artifact.parse(item['artifact'])
            if (not isinstance(name,str) or '/' in name or '\\' in name or name.startswith('.') or name in names or
                    not name.endswith(('.json','.safetensors','.model','.txt')) or
                    ref.role != key+'_file' or ref.visibility != 'operator'):
                raise ContractError('ordinary uniquely named exact qualified asset descriptor required')
            names.add(name); files.append(item)
        bundles[key] = value
    if 'config.json' not in names or not any(n.endswith('.safetensors') for n in names):
        raise ContractError('complete qualified safetensors/config checkpoint metadata required')
    model = read_json(content['model_runtime'], roles={'model_runtime'}, cap=4_000_000)
    exact(model, {'schema','profile_sha256','checkpoint_sha256','tokenizer_sha256','versions','exposure_declaration'}, 'qualified model runtime')
    if (model['schema'] != 'neural063_local_model_runtime_v1' or model['profile_sha256'] != digest(p) or
            model['checkpoint_sha256'] != content['checkpoint']['sha256'] or model['tokenizer_sha256'] != content['tokenizer']['sha256']):
        raise ContractError('qualified model runtime/profile/asset identities differ')
    if set(model['versions']) != {'numeric','model','reference','validation','event_output'} or any(set(v) != {'python','numpy','torch','transformers'} for v in model['versions'].values()):
        raise ContractError('exact qualified five-operation interpreter/library declarations required')
    if not isinstance(model['exposure_declaration'],str) or not model['exposure_declaration']:
        raise ContractError('qualified checkpoint exposure declaration must retain unknowns')
    reporter = read_json(content['report_generator'], roles={'qualified_report_generator'}, cap=4_000_000)
    exact(reporter, {'schema','implementation_sha256','profile_sha256','checkpoint_sha256','tokenizer_sha256','model_runtime_sha256','report_recipe'}, 'qualified reporter')
    if (reporter['schema'] != 'neural063_qualified_report_generator_v2' or
            reporter['implementation_sha256'] != implementation.sha256 or reporter['profile_sha256'] != digest(p) or
            any(reporter[k+'_sha256'] != content[k]['sha256'] for k in ASSETS)):
        raise ContractError('report generator is not the qualified implementation/profile/assets')
    recipe_ref = Artifact.parse(reporter['report_recipe'])
    if recipe_ref.role != 'report_recipe' or recipe_ref.visibility != 'operator':
        raise ContractError('report generator must bind the exact operator report recipe')
    if stage in {'D00','N00'}:
        if any(inputs[k].object() != content[k] for k in ASSETS):
            raise ContractError('actual external runtime input differs from independently qualified assets')
    if stage == 'N00' and inputs['report_recipe'].object() != reporter['report_recipe']:
        raise ContractError('actual report recipe differs from qualified report generator')
    if 'D00' in receipts:
        ref = receipts['D00']['artifacts'].get('runtime_assets')
        if ref is None:raise ContractError('signed D00 runtime-assets inventory absent')
        assets = read_json(ref, roles={'runtime_assets'}, cap=4_000_000)
        if (assets.get('schema') != 'neural063_runtime_assets_v1' or assets.get('profile_sha256') != digest(p) or
                any(assets.get(k+'_sha256') != content[k]['sha256'] for k in ASSETS) or
                assets.get('report_generator_sha256') != content['report_generator']['sha256'] or
                assets.get('files') != files or assets.get('versions') != model['versions']):
            raise ContractError('signed predecessor runtime assets differ from current independent qualification')
        if 'runtime_assets' in inputs and inputs['runtime_assets'].object() != ref:
            raise ContractError('selected runtime assets are not exact signed qualified predecessor')
    return {'environment':content['environment'], 'runtime_profile_sha256':digest(p),
            **{k:content[k] for k in ASSETS}, 'report_generator':content['report_generator'],
            'report_recipe':reporter['report_recipe']}
