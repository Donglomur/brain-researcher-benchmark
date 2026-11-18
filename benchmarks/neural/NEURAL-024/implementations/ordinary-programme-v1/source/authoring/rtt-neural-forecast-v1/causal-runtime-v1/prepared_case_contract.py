"""Fixed original remaining-case metadata/receipt contract; no data work at import."""
import hashlib
import json
import re

TASK = 'NEURAL-024'
OPERATION = 'prepare_original_remaining_case_v1'
PROTOCOL = 'NEURAL024-causal-v1'
CONFIG_PIN = {'bytes': 7560, 'sha256': '7eeae7e772a7c1e1ba16f34aedc17d2cf7b68e77abb479dae96aa41edfdff69a'}
GUARD_PIN = {'bytes': 37520, 'sha256': 'a769923f10ac991ef4012eb42eb7a266f64f07c989ed86d03516341125f944c6'}
QUALIFICATION_PIN = {'bytes': 2128, 'sha256': '58970a2999b5c59cfde6e2a25c974f7d6b02c7c567dffd1e71dd10d7e462822d'}
ROOT_BANK_RESULT_PIN = {'bytes': 3565, 'sha256': 'c12d719af55325b819b82314d78375b28092ea83c333a56a0f2b6fe076dd2c9a'}
PUBLIC_PINS = {'calibration_counts.npz': {'bytes': 1176540, 'sha256': '18bb1539bf601b23e4ff155e2d099d67875020a3415fbf8756e12ea4dab2bb7b'}, 'source_counts.npz': {'bytes': 7330940, 'sha256': '41b9e69c2f00fae8d32884be6bf5f9097ee0ba4afc62adcd192c02ac5f520e3d'}}
ORIGINAL_INPUT_PINS = {'calibration_counts': {'bytes': 1236872, 'sha256': '05f7e4535606d4057b48a00b74eb919078875ab7dbcb0f06639174a7216ccac3'}, 'source_counts': {'bytes': 7705272, 'sha256': '839f7bf5b5bde7feed560f0e2f5a6fe9b0fb3b75d8f92f1bbff9c78a789a2bb2'}, 'query_counts': {'bytes': 8752360, 'sha256': 'af0cb2d84945917009d059c2393ebb36e675ce6602f371507251a6f00347a1bb'}}
REFERENCE_PIN = {'bytes': 62575, 'sha256': 'b4ef446717393b63bd31afa584c79de826dbc9c9e66696ceb59c69774d542943'}
SOURCE_PINS = {'SCIENTIFIC_INPUTS.json': {'bytes': 7560, 'sha256': '7eeae7e772a7c1e1ba16f34aedc17d2cf7b68e77abb479dae96aa41edfdff69a'}, 'calibration_rate.py': {'bytes': 8890, 'sha256': 'fbce908631d1ae7a11ac8c8c94138af0e60cf0e53c4260783c8280aef2e3139b'}, 'calibration_rate_checks.py': {'bytes': 9572, 'sha256': 'dc602aea267c05b77813f4e3dd2cd98b3d0dbbef9c354f727a930cb88725cfed'}, 'generated_checks.py': {'bytes': 4667, 'sha256': 'a4a49f5ad4e6a14213b019430422035cddf4b3fc6587e299ea89c54b38ff215a'}, 'packet_core.py': {'bytes': 5257, 'sha256': 'e9f5b373b00766478a05de8890dfa72888261539ef203370c1e9b744eb59ff79'}, 'prepare.py': {'bytes': 10543, 'sha256': '17b13994fd6886f7df529e4604dd9b53c25f3b983d2b6113f89858ece7b99ca0'}}
CAPS = {'observations.jsonl': 45260800, 'schedule.json': 2000000, 'references.json': 256000, 'prepare_receipt.json': 128000}
ARMS = ['source_rate', 'calibration_rate', 'self_history_frozen', 'self_history_adapted', 'self_population_history_frozen', 'self_population_history_adapted']


def need(ok,message):
    if not ok: raise ValueError(message)


def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')


def digest(body):return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}


def strict(body,cap=128000):
    need(type(body)is bytes and 0<len(body)<=cap,'bounded metadata')
    def pairs(rows):
        value={}
        for key,item in rows:
            need(key not in value,'duplicate metadata key');value[key]=item
        return value
    return json.loads(body,object_pairs_hook=pairs,parse_constant=lambda x:need(False,'nonfinite metadata'))


def valid_pin(v,maximum=50000000):
    return (type(v)is dict and set(v)=={'bytes','sha256'} and type(v['bytes'])is int
        and 0<v['bytes']<=maximum and type(v['sha256'])is str and re.fullmatch('[a-f0-9]{64}',v['sha256']))


def spec():
    return {'task_id':TASK,'operation_id':OPERATION,'protocol':PROTOCOL,'config_pin':CONFIG_PIN,
        'guard_pin':GUARD_PIN,'qualification_pin':QUALIFICATION_PIN,'public_pins':PUBLIC_PINS,
        'original_input_pins':ORIGINAL_INPUT_PINS,'reference_pin':REFERENCE_PIN,'source_pins':SOURCE_PINS,
        'output_caps':CAPS,'support':{'source':18700,'calibration':3000,'query':22100,'channels':96,
            'warmup':10,'scored':22090,'first_target':3000,'last_target':25099},
        'clock_source':'actual qualified calibration edges; no nominal reconstruction',
        'no_original_bank_reprojection':True,'programme_seconds_unchanged':600,'new_fits':0}


def admission(value,pins):
    need(type(value)is dict and set(value)=={'schema','execution_authorized','spec','source_pins','root_decision_pin'},'closed remaining-case admission')
    need(value['schema']=='neural024-remaining-case-admission/v1' and value['execution_authorized']is True
        and canonical(value['spec'])==canonical(spec()) and value['source_pins']==pins
        and set(pins)=={'prepare_remaining_case.py','case_contract.py','bank_operator.py'}
        and pins['bank_operator.py']==GUARD_PIN and all(valid_pin(x,65536) for x in pins.values())
        and valid_pin(value['root_decision_pin'],16384),'exact selected case/source contract')


def root_decision(value,pins):
    expected={'schema':'neural024-remaining-case-root-decision/v1','task_id':TASK,'operation_id':OPERATION,
        'spec_sha256':digest(canonical(spec()))['sha256'],'source_pins':pins,'execution_authorized':True,
        'runtime_profile_selected':True,'new_case_qualification_observed':False,'max_attempts':1}
    need(type(value)is dict and canonical(value)==canonical(expected),'exact separately selected root decision')


def prior_qualification(value):
    need(value.get('schema')=='neural024-two-bank-result/v1' and value.get('status')=='two_bank_projection_qualified_only'
        and value.get('task_id')==TASK and value.get('files_before_receipt')==PUBLIC_PINS
        and value.get('input_identity_pins')=={k:ORIGINAL_INPUT_PINS[k] for k in ('source_counts','calibration_counts')}
        and value.get('source_origin')=='NEURAL-023' and value.get('qualification_inherited')is False
        and value.get('native_clock_edges_modified')is False and value.get('incomplete_extent')is False
        and value.get('error_type')is None and value.get('writer_completed_before_receipt')==2,
        'exact qualified banks and original provenance')
    c=value.get('counters',{})
    for key,want in {'recording_reads_attempted':2,'recording_reads_completed':2,'recording_bytes_read':8942144,
        'count_arrays_decoded':2,'clock_arrays_decoded':2,'projection_roundtrips':2,
        'projection_count_arrays_decoded':2,'projection_clock_arrays_decoded':2,
        'scientific_fits':0,'candidate_invocations':0,'behavior_arrays_decoded':0}.items():
        need(type(c.get(key))is int and c[key]==want,'exact prior bank counters')


def config(value):
    need(value.get('candidate_id')==TASK and value.get('protocol')==PROTOCOL
        and {k:{z:v[z] for z in ('bytes','sha256')} for k,v in value['data'].items()}==ORIGINAL_INPUT_PINS
        and {k:value['reference_scores'][k] for k in ('bytes','sha256')}==REFERENCE_PIN
        and value['reference_arms']==ARMS,'original scientific configuration')


def counters_complete(c):
    exact={'recording_reads_attempted':1,'recording_reads_completed':1,'recording_bytes_read':8752360,
        'count_arrays_decoded':1,'clock_arrays_decoded':1,'projection_roundtrips':0,
        'projection_count_arrays_decoded':0,'projection_clock_arrays_decoded':0,
        'observation_rows_encoded':22100,'schedule_intervals':22100,'reference_json_reads_attempted':1,
        'reference_json_reads_completed':1,'scientific_fits':0,'candidate_invocations':0,
        'behavior_arrays_decoded':0,'generated_packet_controls':0,'generated_candidate_controls':0,
        'reused_calibration_reads_attempted':1,'reused_calibration_reads_completed':1,
        'reused_calibration_bytes_read':1176540,'reused_calibration_clock_arrays_decoded':1,
        'reused_calibration_count_arrays_decoded':0}
    need(type(c)is dict and set(c)==set(exact),'closed truthful split-stage counters')
    need(all(type(c[k])is int and c[k]==v for k,v in exact.items()),'complete query/calibration-clock/reference extent')


def receipt(value,files,config_sha,admission_sha,decision_pin,pins):
    need(value.get('status')=='rtt_neural_causal_packet_prepared' and value.get('complete')is True
        and value.get('candidate_id')==TASK and value.get('protocol')==PROTOCOL
        and value.get('inputs_sha256')==config_sha and value.get('files')=={**PUBLIC_PINS,**files}
        and set(files)=={'observations.jsonl','schedule.json','references.json'}
        and files['references.json']==REFERENCE_PIN and value.get('reference_scores_pin')==REFERENCE_PIN
        and value.get('input_identity_pins')==ORIGINAL_INPUT_PINS and value.get('error')is None
        and value.get('native_clock_edges_modified')is False and value.get('benchmark_ready')is False
        and value.get('private_future_rows')==22100 and value.get('warmup_rows')==10 and value.get('scored_rows')==22090,
        'complete original grader-compatible receipt')
    need(value.get('stage_provenance')=={'operation_id':OPERATION,'prior_bank_qualification':QUALIFICATION_PIN,
        'public_banks_reused_in_place':True,'public_banks_copied_or_reprojected':False,
        'admission_sha256':admission_sha,'root_decision_pin':decision_pin,'source_pins':pins,
        'generated_controls_run_this_stage':False},'exact composed stage provenance')
    counters_complete(value.get('counters'))
