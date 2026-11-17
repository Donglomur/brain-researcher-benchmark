"""Exact operator configuration and independent admission; never candidate authority."""
import re
from pathlib import Path

FIELDS={'schema','source','image','docker_binary','docker_socket','programs','contexts',
        'canonical','reviews','output','memory_bytes','holder_memory_bytes','host_memory_bytes',
        'output_volume_bytes','producer_seconds','capture_seconds','native_reply_bytes',
        'limits','other_future_bytes'}
LIMITS={'reads','writes','retained','free_floor_bytes','native_response_bytes',
        'whole_seconds','observer_seconds','observer_reads'}
FLAGS={'full_original_preparation_and_support','both_authoring_freezes_before_any_input',
       'specification_context_excludes_oracle_and_control_feedback',
       'exact_images_modules_caches_helpers_and_prompts_reviewed',
       'training_only_fixed_method_reviewed','reference_source_and_competence_admitted',
       'native_host_resources_and_isolation_admitted'}

def descriptor(row,cap):
    c.need(type(row)is dict and set(row)=={'path','bytes','sha256'},'exact path descriptor')
    c.need(type(row['path'])is str and len(row['path'].encode('utf-8'))<=4096 and Path(row['path']).is_absolute(),'bounded absolute source path')
    c.path(row['path']);c.need(c.only_pin(row)['bytes']<=cap,'descriptor extent');return row

def configuration(s):return {k:v for k,v in s.items() if k!='reviews'}

def selection(s,source):
    c.need(type(s)is dict and set(s)==FIELDS and s['schema']=='neural026_matched_selection_v2','exact selection')
    c.need(s['source']==c.exact_pin(source),'selected source')
    c.need(type(s['image'])is str and re.fullmatch('sha256:[0-9a-f]{64}',s['image']),'immutable image')
    for key in ('docker_binary','docker_socket','output'):
        c.need(type(s[key])is str and len(s[key].encode('utf-8'))<=4096 and Path(s[key]).is_absolute(),'bounded absolute selected path');c.path(s[key])
    c.need(type(s['programs'])is dict and set(s['programs'])==set(contracts.PANELS[:2]),'two independent frozen programs')
    for d in s['programs'].values():descriptor(d,1048576)
    c.need(type(s['contexts'])is dict and set(s['contexts'])==set(contracts.PANELS),'three independent context records')
    for d in s['contexts'].values():descriptor(d,1048576)
    c.need(len({d['path'] for d in s['contexts'].values()})==3,'separate context artifacts')
    descriptor(s['canonical'],contracts.CATALOGUE_CAP);descriptor(s['reviews'],2097152)
    for key in ('memory_bytes','holder_memory_bytes','host_memory_bytes','output_volume_bytes',
                'producer_seconds','capture_seconds','native_reply_bytes','other_future_bytes'):
        c.need(type(s[key])is int and 0<=s[key]<=2**60,'typed resource maximum')
    c.need(s['memory_bytes']>=134217728 and s['holder_memory_bytes']>=1073741824
           and s['host_memory_bytes']>=1073741824,'declared whole memory ceilings')
    c.need(s['output_volume_bytes']>=138412032 and s['output_volume_bytes']%4096==0,'full output-volume allowance')
    c.need(s['producer_seconds']>0 and s['capture_seconds']>0,'positive selected phase clocks')
    c.need(s['native_reply_bytes']>=4*((contracts.FILE_CAP+2)//3)+8192,'full opaque output response')
    l=s['limits'];c.need(type(l)is dict and set(l)==LIMITS,'exact whole limits')
    for v in l.values():c.need(type(v)is int and 0<v<=2**60,'positive typed whole allowance')
    c.need(l['free_floor_bytes']>=2147483648 and l['observer_seconds']>=60,'physical floor and observer interval')
    c.need(l['native_response_bytes']>=s['native_reply_bytes']+64*131073,'whole phase native responses')
    c.need(l['whole_seconds']>l['observer_seconds']+150*(s['producer_seconds']+s['capture_seconds']+100),
           'full150 selected producer intervals plus staging/observer work')
    c.need(l['reads']>=150*l['native_response_bytes'],'all150 native reservations plus host read work')
    c.need(l['observer_reads']>=contracts.OBSERVER_READ_FLOOR,'preventive whole observer closure-read bound')
    return s

def reviews(value,s,reference):
    c.need(type(value)is dict and set(value)=={'schema','configuration','reference','flags','reviewer'},'exact operator review')
    c.need(value['schema']=='neural026_independent_admission_v2'
           and value['configuration']==configuration(s) and value['reference']==reference,'exact complete configuration/reference join')
    c.need(type(value['reviewer'])is str and 0<len(value['reviewer'].encode())<=512,'independent reviewer identity')
    c.need(type(value['flags'])is dict and set(value['flags'])==FLAGS and all(v is True for v in value['flags'].values()),'all explicit external admissions')
    return value

def context(value,panel,program,s):
    c.need(type(value)is dict and set(value)=={'schema','panel','context_id','program','image','documents','authoring_inventory','freeze_before_any_case_input'},'exact context receipt')
    c.need(value['schema']=='neural026_context_v2' and value['panel']==panel and value['program']==program
           and value['image']==s['image'] and value['freeze_before_any_case_input'] is True,'program/context/phase identity')
    c.need(type(value['context_id'])is str and 0<len(value['context_id'].encode())<=256,'bounded independent context identity')
    c.need(type(value['documents'])is dict,'exact document identity map')
    for pin in value['documents'].values():c.exact_pin(pin)
    descriptor(value['authoring_inventory'],2097152)
    return value
