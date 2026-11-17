"""Owner-only metadata admission; no Docker, install, data or model execution."""
import json
import os
from pathlib import Path
import sys

import owner_package as owner


def admit(request):
    owner.need(type(request) is dict and set(request)=={'schema','configuration_anchor','source_anchor',
               'image_evidence','output'} and request['schema']=='nider_portable_runtime_admission_request_v1',
               'runtime_admission_request')
    cfg,_=owner.configuration(request['configuration_anchor'])
    modules,_=cfg.load_runtime(request['source_anchor']);c=modules['custody'];rp=modules['runtime_policy']
    evidence=c.decode(c.read_pin(request['image_evidence']))
    host=rp.host_observation()
    owner.need(host['system']=='Linux' and host['machine'] in ('aarch64','arm64') and
               host['docker_environment']=={},'runtime_admission_actual_linux_host')
    value={'schema':'nider_portable_runtime_policy_v1','uid':host['uid'],'gid':host['gid'],
           'image':evidence['image'],'platform':'linux/arm64','mapping':rp.MAPPING,
           'image_evidence':request['image_evidence']}
    rp.policy_shape(value);rp.image_evidence(request['image_evidence'],value['image'])
    entry=c.write_new(Path(request['output']),c.encoded(value))
    return {'runtime_policy':entry,'runtime_execution_selected':False,
            'scope':'Dependency provenance and actual local owner identity; live daemon/mount checks still required at dispatch.'}


def relocate_build_evidence(request):
    """Rebind seven local custody paths; never rewrite historical build facts."""
    owner.need(type(request) is dict and set(request)=={'schema','configuration_anchor','source_anchor',
               'artifact_root','artifact_manifest','output','receipt_output'} and
               request['schema']=='nider_dependency_evidence_relocation_request_v1','evidence_relocation_request')
    cfg,_=owner.configuration(request['configuration_anchor'])
    modules,_=cfg.load_runtime(request['source_anchor']);c=modules['custody'];rp=modules['runtime_policy']
    root=owner.plain(request['artifact_root'])
    manifest=c.decode(c.read_pin(request['artifact_manifest'],maximum=1048576))
    owner.need(manifest['schema']=='nider_dependency_artifact_v1' and manifest['image_ready'] is True,
               'complete_dependency_artifact_required')
    members=manifest['members'];index={x['relative_path']:x for x in members}
    owner.need(len(index)==len(members),'artifact_duplicate_paths')
    def original(relative,maximum):
        item=index[relative];p=owner.plain(root/relative)
        owner.need(p.is_relative_to(root) and not p.is_symlink(),'relocation_plain_member')
        entry={'path':str(p),'bytes':item['bytes'],'sha256':item['sha256']}
        return c.decode(c.read_pin(entry,maximum=maximum)),entry
    value,old_entry=original('evidence/setup/IMAGE_EVIDENCE.json',1048576)
    buildroot=Path(value['build_plan']['path']).parent
    names={'build_plan':'BUILD_PLAN.json','build_lifecycle':'BUILD_LIFECYCLE.json',
           'image_inspection':'IMAGE.json','runtime_inventory':'inventory/RUNTIME_INVENTORY.json',
           'filesystem_audit':'FILESYSTEM_AUDIT.json','base_image_inspection':'BASE_IMAGE.json',
           'image_history':'HISTORY.json'}
    derived=dict(value);joins=[]
    for key,relative in names.items():
        owner.need(value[key]['path']==str(buildroot/relative),'original_build_locator')
        _,entry=original('evidence/setup/'+relative,8388608 if key=='filesystem_audit' else 1048576)
        owner.need(entry['bytes']==value[key]['bytes'] and entry['sha256']==value[key]['sha256'],
                   'unchanged_original_evidence_body')
        derived[key]=entry;joins.append({'field':key,'original':value[key],'local':entry})
    out=c.write_new(Path(request['output']),c.encoded(derived))
    # An invalid candidate leaves the attempted derived metadata intact. It is
    # never accepted merely because a caller asserted the artifact was ready.
    rp.image_evidence(out,value['image'])
    receipt=c.write_new(Path(request['receipt_output']),c.encoded({
        'schema':'nider_dependency_evidence_relocation_v1','original_top_document':old_entry,
        'derived_top_document':out,'path_joins':joins,'historical_linked_bodies_unchanged':True,
        'old_build_lifecycle_rewritten':False,'image_loaded_or_live_observed':False,
        'scope':'Owner custody relocation only; a separately selected image load and fresh live admission remain required.'}))
    return {'image_evidence':out,'relocation_receipt':receipt,'runtime_execution_selected':False}


if __name__=='__main__':
    os.umask(0o077);owner.need(len(sys.argv)==3,'request_and_digest')
    p=owner.plain(sys.argv[1]);request=owner.decode(owner.read_pin({'path':str(p),'bytes':p.stat().st_size,'sha256':sys.argv[2]}))
    operation=relocate_build_evidence if request.get('schema')=='nider_dependency_evidence_relocation_request_v1' else admit
    print(json.dumps(operation(request),sort_keys=True))
