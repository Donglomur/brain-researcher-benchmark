"""Prospectively selected complete-operation contract. No defaults start science."""
import math
from pathlib import Path
import re
from core import TASK, ROLES, PROFILES, BRANCHES, INPUTS, need, descriptor
from transport.contract import RESOURCE_KEYS

ACTIONS=('prepare_originals','prepare_views','fit','query','reconstruct','selection_evaluate','final_evaluate','report')


def file_ref(value):
    need(type(value) is dict and set(value)=={'path','bytes','sha256'},'Exact external file reference')
    need(type(value['path']) is str and Path(value['path']).is_absolute(),'Absolute operator-approved source')
    descriptor({k:value[k] for k in ('bytes','sha256')});return value


def source_tree(value):
    need(type(value) is dict and set(value)=={'root','files'} and type(value['root']) is str and Path(value['root']).is_absolute(),'Closed source tree')
    need(type(value['files']) is dict and value['files'],'Complete nonempty source inventory')
    from staging import validate_files
    validate_files(value['files']);return value


def validate_operation(op):
    keys={'schema','task','scientific_authorization','source_manifest','paper','author_source','native_source','originals','lineage','lineage_evidence','lineage_review','programs','images','phase_resources','attempt_limits','native_matlab','native_limits','native_seeds','global_limits','host','qualification'}
    need(type(op) is dict and set(op)==keys and op['schema']=='paper_i_operation_v1' and op['task']==TASK,'Exact complete operation')
    need(op['scientific_authorization'] is True,'Separate explicit actual operation authorization is required; source acceptance alone is insufficient')
    for k in ('source_manifest','paper','lineage','lineage_review','qualification'):file_ref(op[k])
    for k in ('author_source','native_source'):source_tree(op[k])
    need(type(op['lineage_evidence']) is list and op['lineage_evidence'],'Full scientific lineage evidence')
    for f in op['lineage_evidence']:file_ref(f)
    originals=op['originals'];need(type(originals) is dict and set(originals)=={'root','files'},'All original publisher objects')
    need(Path(originals['root']).is_absolute() and set(originals['files'])=={f['name'] for f in INPUTS},'All ten original input objects')
    for f in INPUTS:
        r=originals['files'][f['name']];need(type(r) is dict and set(r)=={'bytes','sha256','md5'} and r['bytes']==f['bytes'] and r['md5']==f['md5'],'Exact full publisher extent/MD5')
        descriptor({k:r[k] for k in ('bytes','sha256')})
    need(set(op['programs'])=={'A','B'},'Two independently precommitted arms')
    for role,p in op['programs'].items():
        need(type(p) is dict and set(p)=={'source','commands','configurations'},'Complete candidate interface and finite search')
        source_tree(p['source']);need(set(p['commands'])=={'fit','query','reconstruct'},'Real fit/query/reconstruction interfaces')
        for argv in p['commands'].values():
            need(type(argv) is list and 1<=len(argv)<=48 and all(type(s) is str and 0<len(s.encode())<=4096 and '\x00' not in s for s in argv) and argv[0].startswith('/'),'Fixed absolute argv, no shell expansion')
            need(any(s.startswith('/program/') for s in argv),'Precommitted source mounted under exact /program basename')
        need(set(p['configurations'])==set(PROFILES),'Every information/control profile')
        for profile,configs in p['configurations'].items():
            need(type(configs) is list and configs and len(configs)<=op['host']['max_configurations'],'Finite nonempty precommitted search')
            need(all(type(c) is dict and set(c)=={'id','parameters'} and type(c['id']) is str and c['id'] and type(c['parameters']) is dict for c in configs),'Exact configuration records')
            need(len({c['id'] for c in configs})==len(configs),'Unique configurations')
    need(set(op['images'])=={'A','B','reference','operator'},'All independently approved immutable image roles')
    for role,image in op['images'].items():
        need(type(image) is dict and set(image)=={'digest','inventory','boundary_audit'},'Complete image/source approval')
        need(type(image['digest']) is str and re.fullmatch('sha256:[0-9a-f]{64}',image['digest']),'Existing immutable image, no pull/install')
        file_ref(image['inventory']);file_ref(image['boundary_audit'])
    need(set(op['phase_resources'])==set(ACTIONS),'No unbudgeted phase kind')
    for r in op['phase_resources'].values():
        need(set(r)==RESOURCE_KEYS and all(type(n) is int and n>0 for n in r.values()),'Full explicit phase resource limits')
    limits=op['global_limits'];need(type(limits) is dict and set(limits)=={'wall_seconds','read_bytes','write_bytes','retained_bytes'} and all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in limits.values()),'Original whole-operation resource allocation')
    host=op['host'];need(type(host) is dict and set(host)=={'docker_binary','docker_socket','docker_binary_pin','python','memory_bytes','parent_memory_bytes','controller_memory_bytes','parent_limits','controller_limits','controller_grace_seconds','cleanup_seconds','max_phases','max_queries','max_configurations','max_metadata_bytes','max_array_bytes','max_events','log_bytes','source_read_bytes','host_write_bytes','recovery'},'Complete host and independent cleanup budget')
    for k,v in host.items():
        if k in ('docker_binary','docker_socket'):need(type(v) is str and Path(v).is_absolute(),'Exact local Docker endpoint')
        elif k not in ('recovery','docker_binary_pin','python','parent_limits','controller_limits'):need(type(v) is int and v>0,'Positive bounded host field '+k)
    need(host['cleanup_seconds']<limits['wall_seconds'],'Cleanup is inside the original whole-study deadline')
    need(type(host['recovery']) is dict and set(host['recovery'])=={'max_records','max_record_bytes','max_metadata_bytes','max_cli_calls','max_cli_bytes','source_read_bytes','host_write_bytes'} and all(type(v) is int and v>0 for v in host['recovery'].values()),'Bounded parent-owned recovery')
    file_ref(host['python']);descriptor(host['docker_binary_pin'])
    need(host['parent_memory_bytes']+host['controller_memory_bytes']<=host['memory_bytes'],'Partition host address-space limits, no doubled allowance')
    need(host['controller_grace_seconds']<host['cleanup_seconds'],'Grace inside reserved cleanup tail')
    for which in ('parent_limits','controller_limits'):
        need(type(host[which]) is dict and set(host[which])=={'read_bytes','write_bytes','retained_bytes'} and all(type(v) is int and v>0 for v in host[which].values()),'Explicit disjoint whole-study resource partition')
    need(all(host['parent_limits'][k]+host['controller_limits'][k]<=limits[k] for k in host['parent_limits']),'Parent and child shares remain inside global budget')
    need(type(op['native_matlab']) is str and Path(op['native_matlab']).is_absolute(),'Approved immutable-image MATLAB executable')
    need(type(op['native_limits']) is dict and set(op['native_limits'])=={'max_files','max_file_bytes','max_output_bytes','max_metadata_bytes','max_collection_items','max_native_elements'} and all(type(v) is int and v>0 for v in op['native_limits'].values()),'Explicit full native preparation expansion limits')
    need(type(op['native_seeds']) is dict and set(op['native_seeds'])==set(BRANCHES) and all(type(v) is int and 0<=v<2**32 for v in op['native_seeds'].values()),'Explicit matched prospective native starting RNG states')
    need(type(op['attempt_limits']) is dict and set(op['attempt_limits'])=={'encoding','reconstruction'},'Both complete producer-attempt envelopes')
    for row in op['attempt_limits'].values():
        need(type(row) is dict and set(row)=={'wall_seconds','read_bytes','write_bytes','memory_bytes'} and all(type(v) is int and v>0 for v in row.values()),'Complete nested attempt limits')
    return op
