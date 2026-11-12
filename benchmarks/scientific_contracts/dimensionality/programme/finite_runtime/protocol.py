"""Complete participant wire ABI. No participant code is imported by the controller."""
from __future__ import annotations
from .common import require, identity, encode, decode, exact_keys, STATUSES, RESULT_LIMIT, content_descriptor

REQUIRED = {'schema','run_id','arm','lane','protocol_id','source_manifest_sha256',
            'plan_sha256','request_id','parent_receipt','payload'}
STAGES = {'describe','build','learn','calibrate','author_R','estimate','report'}

def request(*, run_id, arm, lane, protocol_id, source, plan, request_id, parent, stage, payload):
    require(stage in STAGES, 'UNKNOWN_PARTICIPANT_STAGE')
    value = {'schema':'finite_participant_v1','run_id':run_id,'arm':arm,'lane':lane,
             'protocol_id':protocol_id,'source_manifest_sha256':source,'plan_sha256':plan,
             'request_id':request_id,'parent_receipt':parent,
             'payload':{**payload,'stage':stage}}
    encode(value)
    return value

def validate_response(value, req):
    exact_keys(value, REQUIRED | {'request_sha256', 'artifacts'})
    require(value['request_sha256'] == identity(req), 'WRONG_REQUEST_RESPONSE')
    for key in REQUIRED-{'payload','parent_receipt'}:
        require(value[key] == req[key], 'RESPONSE_IDENTITY_MISMATCH', key)
    require(value['parent_receipt'] == req['parent_receipt'], 'RESPONSE_PARENT_MISMATCH')
    require(type(value['artifacts']) is list, 'ARTIFACT_LIST_REQUIRED')
    paths=[]
    for x in value['artifacts']:
        content_descriptor(x);paths.append(x['path'])
        require(x['producer'] == req['request_id'], 'OUTPUT_PRODUCER_MISMATCH')
    require(len(paths)==len(set(paths)), 'DUPLICATE_OUTPUT_PATH')
    stage=req['payload']['stage'];payload=value['payload']
    if stage=='describe':
        exact_keys(payload, {'method_id','assumptions','configurations','declared_dependencies',
                             'toolchain','entry_command','source_files','supported_protocols'})
        cfg=payload['configurations']
        require(type(cfg) is list and 1<=len(cfg)<=12, 'INVALID_CONFIGURATION_SEARCH_COUNT')
        require(len({x['id'] for x in cfg})==len(cfg), 'DUPLICATE_CONFIGURATION_ID')
    elif stage in {'build','learn','author_R'}:
        require(payload.get('status') in {'ok','no_fit','failed'}, 'INVALID_BUILD_OR_FIT_STATUS')
        require('state' in payload and 'attempts' in payload, 'ORIGINAL_ATTEMPT_LEDGER_REQUIRED')
    elif stage=='calibrate':
        exact_keys(payload, {'selected_state_sha256','selected_configuration','all_configuration_records',
                             'uncertainty_selection','selection_rule'})
    elif stage=='estimate':
        validate_estimate(payload, req)
    elif stage=='report':
        require(type(payload.get('obligations')) in (list,dict) and type(payload.get('claims')) is list,
                'COMPLETE_SCIENTIFIC_REPORT_REQUIRED')
    encode(value)
    return value

def validate_estimate(value, req):
    exact_keys(value, {'case_id','status','value','intervals','components','support','assumptions',
                      'state_sha256','input_sha256','selection_sha256','precision','moment_support'},
               {'diagnostics','artifact_fields'})
    require(value['status'] in STATUSES, 'INVALID_SCIENTIFIC_STATUS')
    if value['status']!='ok':
        require(value['value'] is None or type(value['value']) in (int,float), 'INVALID_FAILED_VALUE')
    else:require(type(value['value']) in (int,float,dict,list) or value.get('artifact_fields'),
                 'SCIENTIFIC_VALUE_REQUIRED')
    expected=req['payload']['case']
    for field in ['case_id','input_sha256','selection_sha256']:
        require(value[field]==expected[field], 'CASE_PRODUCT_SUBSTITUTION', field)
    require(value['state_sha256']==req['payload']['state_sha256'], 'PREDICTOR_STATE_SUBSTITUTION')
    if req['lane']=='R' and expected['requires_moments']:
        require(value['moment_support']=='provided' and set(value['components']) >= {'t1','t2','t3','t4','t5','A','B'},
                'REPRODUCTION_MOMENTS_REQUIRED')
    encode(value,RESULT_LIMIT)
