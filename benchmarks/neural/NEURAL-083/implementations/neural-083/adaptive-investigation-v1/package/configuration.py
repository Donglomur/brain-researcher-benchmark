"""Source/configuration commitments and genuine external admission operands."""
import math


FIELDS=('schema','preparation_complete','preparation_closure','preparation_review','method_review',
        'entrant','tool_mode','provider_configuration','prompt','frozen_program','preparation_costs',
        'output','limits','other_future_bytes','docker_binary','docker_socket','image','memory_bytes',
        'fit_seconds','infer_seconds','query_seconds','max_model_calls_per_query','max_tool_calls_per_query',
        'model_input_token_budget','model_output_token_budget','model_request_budget',
        'model_cost_record_cap_bytes','completion_record_cap_bytes')


def configuration_pin(c,value):
    return c.pin(c.encoded({k:v for k,v in value.items() if k!='method_review'}))


def select(ctx,value,source,inherited_root,inherited_bodies,budget):
    c=ctx['c'];io=ctx['io'];bridge=ctx['bridge']
    c.need(type(value)is dict and set(value)==set(FIELDS)
        and value['schema']=='neural083_case_adaptive_selection_v1','closed complete configuration')
    c.need(value['entrant'] in ('frozen_program','case_adaptive_equal_inputs_tools_compute','decoder_alone')
        and value['tool_mode'] in ('generic_numerical','decoder_alone','agent_plus_decoder'),
        'explicit access mode and separate tool comparison')
    c.need((value['entrant']=='decoder_alone')==(value['tool_mode']=='decoder_alone'),
        'supplied decoder alone has no arbitrary programme or model call')
    for key in ('other_future_bytes','memory_bytes','fit_seconds','infer_seconds','query_seconds',
                'max_model_calls_per_query','max_tool_calls_per_query','model_input_token_budget',
                'model_output_token_budget','model_request_budget','model_cost_record_cap_bytes','completion_record_cap_bytes'):
        c.need(type(value[key])is int and value[key]>=0,'non-boolean resource integer: '+key)
    c.need(1<=value['max_tool_calls_per_query']<=16 and 1<=value['max_model_calls_per_query']<=8
        and 1<=value['fit_seconds']<=3600 and 1<=value['infer_seconds']<=3600
        and value['infer_seconds']>=value['max_tool_calls_per_query']
        and value['infer_seconds']<value['query_seconds']<=86400
        and value['memory_bytes']>=268435456,'explicit finite per-query/native policy')
    c.need(type(value['limits'])is dict and set(value['limits'])==
        {'reads','writes','retained','free_floor_bytes','whole_seconds','observer_seconds'},'whole programme resource profile')
    for key,number in value['limits'].items():
        c.need(type(number)is int and number>0,'positive whole resource bound: '+key)
    c.need(value['limits']['observer_seconds']>=30 and
        value['limits']['whole_seconds']>value['limits']['observer_seconds']+30,'original worker and owner reserve')
    joined=bridge.prepared_inputs(value['preparation_complete'],value['preparation_closure'],
        inherited_root,inherited_bodies,ctx['metadata_budget'])
    p=joined['value']
    def capture(spec,cap=262144):return c.parse(c.capture(spec['path'],cap,c.only_pin(spec),budget.tick,budget.read))
    preparation=capture(value['preparation_review'])
    c.need(preparation.get('schema')=='neural083_full_input_admission_v1'
        and preparation.get('canonical')==io.only_pin(p['canonical'])
        and preparation.get('projection_provenance')==p['projection_provenance'],
        'independent original full preparation admission')
    for flag in ('full108_original_provenance','source_channel_clock_label_order_verified','actual_values_and_support_verified'):
        c.need(preparation.get(flag)is True,'genuine independently admitted input: '+flag)
    method=capture(value['method_review'])
    c.need(method.get('schema')=='neural083_case_adaptive_method_admission_v1'
        and method.get('source')==source and method.get('configuration')==configuration_pin(c,value)
        and method.get('preparation_complete')==io.only_pin(value['preparation_complete']),
        'source-exact genuine independent mode/method review')
    for flag in ('execution_authorized','full_original_task_preserved','same_permitted_inputs_and_tool_policy',
                 'original_no_query_batch_adaptation_preserved','no_query_fitting_or_cross_query_state',
                 'dynamic_single_query_python_semantics_admitted','fixed_training_constructor_admitted',
                 'provider_and_native_resource_profile_admitted',
                 'matched_cost_accounting_and_preparation_costs_admitted'):
        c.need(method.get(flag)is True,'external method/provider prerequisite: '+flag)
    provider_config=None;prompt=''
    if value['entrant']=='case_adaptive_equal_inputs_tools_compute':
        c.need(method.get('provider_model_identity_and_stateless_request_contract_admitted')is True,
               'genuine independently admitted model identity and request isolation')
        provider_config=capture(value['provider_configuration'])
        c.need(set(provider_config)=={'study','frozen_study_config_sha256'}
            and provider_config['study']['provider_source_sha256']==c.pin(ctx['bodies']['local_chat_provider.py'])['sha256'],
            'captured provider implementation and frozen global configuration')
        ctx['provider']._config(dict(provider_config,owner={'condition_id':'configuration-check','query_id':'no-query'},
                                    request_id='configuration-check'))
        c.need(provider_config['study']['caps']['action_content_bytes']<=65536,
               'bounded complete dialogue and failure-custody action extent')
        prompt_body=c.capture(value['prompt']['path'],32768,c.only_pin(value['prompt']),budget.tick,budget.read)
        prompt=prompt_body.decode('utf-8');c.need(bool(prompt.strip()),'frozen nonempty task prompt')
    else:c.need(value['provider_configuration'] is None and value['prompt'] is None,
                'no fabricated model provider for non-model entrant')
    frozen=None
    if value['entrant']=='frozen_program':
        c.need(type(value['frozen_program'])is dict,'explicit frozen programme source')
        frozen=c.capture(value['frozen_program']['path'],65536,c.only_pin(value['frozen_program']),budget.tick,budget.read).decode('utf-8')
    else:c.need(value['frozen_program'] is None,'no invented frozen programme for adaptive actor')
    preparation_costs=capture(value['preparation_costs'])
    c.need(preparation_costs.get('schema')=='neural083_matched_preparation_costs_v1'
        and preparation_costs.get('configuration')==configuration_pin(c,{**value,'preparation_costs':None}),
        'explicit separately captured preparation/model construction costs')
    selection=dict(value,canonical=p['canonical'],canonical_root=p['canonical_root'],
        repository=str(inherited_root/'scientific-source'))
    output=c.path(value['output'])
    for protected in (c.path(p['canonical_root']),c.path(p['canonical']['path']).parent):
        c.need(output!=protected and output not in protected.parents and protected not in output.parents,
               'programme output disjoint from original records and protected products')
    queries=1296*100
    if value['entrant']=='case_adaptive_equal_inputs_tools_compute':
        c.need(provider_config['study']['actions']==ctx['actor'].actions(value['tool_mode']),
               'exact frozen action definitions')
        calls=queries*value['max_model_calls_per_query']
        c.need(value['model_request_budget']>=calls
            and value['model_input_token_budget']>=calls*provider_config['study']['caps']['reported_prompt_tokens']
            and value['model_output_token_budget']>=calls*provider_config['study']['generation']['max_output_tokens'],
            'full query model reservations, never a reduced diagnostic cohort')
    c.need(selection['model_cost_record_cap_bytes']>0 and selection['completion_record_cap_bytes']>0,
           'explicit full cost/publication caps')
    return selection,provider_config,prompt,frozen,joined
