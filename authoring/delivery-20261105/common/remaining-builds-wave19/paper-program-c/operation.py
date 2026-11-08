"""Prospective whole-study operation contract; supplies no fabricated run pins."""
import math
import re
from pathlib import Path
from core import TASK, BRANCHES, ROLES, need
from transport.contract import RESOURCE_KEYS
from transport.engine import descriptor

ACTIONS=('prepare_originals','prepare_fold','native_attempt','held_attempt','selection_evaluate','final_evaluate')


def positive(value,label,integer=True):
    need(type(value) is int if integer else type(value) in (int,float),label+' type')
    need(math.isfinite(value) and value>0,label+' positive finite')


def location(value):
    need(type(value) is dict and set(value)=={'path','pin'},'Exact located immutable descriptor')
    need(type(value['path']) is str and Path(value['path']).is_absolute(),'Absolute operator-selected path')
    descriptor(value['pin'])


def inner_limits(op):
    """Global grants are partitioned before launch, never extended for cleanup."""
    limits=dict(op['limits'])
    for field,outer in (('read_bytes','outer_read_bytes'),('write_bytes','outer_write_bytes'),('retained_bytes','outer_retained_bytes')):
        limits[field]-=op[outer]
        positive(limits[field],'Remaining controller '+field)
    return limits


def validate_operation(op):
    required={'schema','task_id','operation_id','scientific_execution_authorized','scientific_qualification',
        'exclusive_operator_custody','native_linux_host','limits','outer_cleanup_seconds','controller_grace_seconds',
        'controller_log_bytes','host_memory_bytes','host_python','docker','outer_read_bytes','outer_write_bytes',
        'outer_retained_bytes','boundary_metadata_bytes','observer_read_bytes','engine_source_pin','recovery_limits',
        'source_manifest','images','programs','boundaries','author_source_hashes','phase_resources','originals',
        'fold_budget','native_scripts','canonical_native_entry_sha256','reference_diagnostic_cap','native_scales',
        'assessment_limits','attempt_policy'}
    need(type(op) is dict and set(op)==required,'Complete exact whole-program operation; no implicit defaults')
    need(op['schema']=='osl_complete_program_operation_v1' and op['task_id']==TASK,'Selected OSL task')
    need(type(op['operation_id']) is str and re.fullmatch('[A-Za-z0-9_-]{1,96}',op['operation_id']),'Unique operation')
    need(op['scientific_execution_authorized'] is True and op['scientific_qualification'] is False,
         'Separate actual execution authorization, never inherited from source construction')
    need(op['exclusive_operator_custody'] is True and op['native_linux_host'] is True,'Qualified exclusive Linux custody required')
    need(set(op['limits'])=={'wall_seconds','read_bytes','write_bytes','retained_bytes'},'Original whole-study limits')
    for key,value in op['limits'].items():positive(value,key,key!='wall_seconds')
    for key in ('outer_cleanup_seconds','controller_grace_seconds','controller_log_bytes','host_memory_bytes',
                'outer_read_bytes','outer_write_bytes','outer_retained_bytes','boundary_metadata_bytes','observer_read_bytes','reference_diagnostic_cap'):
        positive(op[key],key)
    need(op['controller_grace_seconds']<op['outer_cleanup_seconds']<op['limits']['wall_seconds'],'Reserved original terminal window')
    need(op['outer_retained_bytes']<=op['outer_write_bytes'],'Outer retained subset')
    inner_limits(op);location(op['host_python']);descriptor(op['engine_source_pin'])
    need(set(op['docker'])=={'binary','socket','binary_pin'},'Exact local Docker executable/socket')
    descriptor(op['docker']['binary_pin'])
    need(all(type(op['docker'][k]) is str and Path(op['docker'][k]).is_absolute() for k in ('binary','socket')),'Absolute local transport')
    s=op['source_manifest'];need(set(s)=={'path','bytes','sha256'},'Exact executable source manifest')
    location({'path':s['path'],'pin':{k:s[k] for k in ('bytes','sha256')}})
    need(set(op['images'])=={'A','B','reference','operator'} and set(op['boundaries'])==set(op['images']),'Four isolated environments')
    for role,image in op['images'].items():
        need(type(image) is str and re.fullmatch('sha256:[a-f0-9]{64}',image),'Locally installed immutable image')
        b=op['boundaries'][role];need(set(b)=={'path','pin','source_rows','inventory_sha256'},'Full external exposure inventory')
        location({k:b[k] for k in ('path','pin')});location(b['source_rows'])
        need(re.fullmatch('[a-f0-9]{64}',b['inventory_sha256']),'External inventory pin')
    need(set(op['programs'])=={'A','B'},'Two independently committed candidate programs')
    for pair in op['programs'].values():
        need(set(pair)=={'native','held_hmm'},'Complete native and prospective candidate entry points')
        for item in pair.values():location(item)
    need(type(op['author_source_hashes']) is list and op['author_source_hashes'] and
         all(type(v) is str and re.fullmatch('[a-f0-9]{64}',v) for v in op['author_source_hashes']), 'Known author code exclusion hashes')
    need(set(op['phase_resources'])==set(ACTIONS),'Complete concrete phase resource profiles')
    for r in op['phase_resources'].values():
        need(set(r)==RESOURCE_KEYS,'Exact provider resource fields')
        for k,v in r.items():positive(v,k)
        need(r['memory_bytes']>=134217728 and r['scratch_bytes']%4096==r['max_output_bytes']%4096==0,'Enforced memory/tmpfs limits')
        need(r['manifest_bytes']<=r['max_file_bytes']<=r['max_output_bytes'] and r['inventory_bytes']>=4096,'Nested bounded outputs')
    need(set(op['native_scripts'])==set(BRANCHES) and set(op['native_scales'])==set(BRANCHES),'All six original scripts and precommitted score scales')
    for row in op['native_scripts'].values():
        need(set(row)=={'script','script_pin','wrapper_pin'} and Path(row['script']).is_absolute(),'Historical script source entry')
        descriptor(row['script_pin']);descriptor(row['wrapper_pin'])
    need(type(op['canonical_native_entry_sha256']) is str and re.fullmatch('[a-f0-9]{64}',op['canonical_native_entry_sha256']),'Exact trusted native source entry')
    need(set(op['recovery_limits'])=={'max_records','max_record_bytes','max_metadata_bytes','max_cli_calls','max_cli_bytes','source_read_bytes','host_write_bytes'},'Bounded independent recovery')
    for k,v in op['recovery_limits'].items():positive(v,k)
    need(set(op['attempt_policy'])=={'schema','task_id','limits','programs','provider_source_pin','provider_qualification_pin'},'Prospective attempt policy inputs only')
    need(set(op['attempt_policy']['programs'])==set(ROLES),'All role policies')
    return op
