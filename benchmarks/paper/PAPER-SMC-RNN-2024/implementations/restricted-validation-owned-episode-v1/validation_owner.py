"""Portable preparation and exact commands for one protected VALID owner.

Preparation never launches a process. execute/custody replace this interpreter
with the exact retained-derived runner; there is no second process manager.
"""
from pathlib import Path
import argparse
import os
import re
import sys

sys.path.insert(0,str(Path(__file__).absolute().parent))
from validation_core import (need,path,body,read,pin,encode,decode,descriptor,checked,ref,
    write_new,load_module,source_identity,load_inputs,FACADE_PIN,VALIDATION_SOURCE_PIN,
    VALIDATION_CORE_PIN,GRADE_SOURCE_PIN)

HERE=Path(__file__).absolute().parent
AUTHOR_FILES={'validation_core.py','validation_episode.py','validation_overlay.py','validation_legacy.py','validation_owner.py'}
TRANSPORT_PIN={'bytes':997,'sha256':'bdeaf4d661115f8f605c572c6da4faaa088370cb1ab714c41f563767bff5fc9c'}
OWNER_REL=Path('benchmarks/paper/PAPER-SMC-RNN-2024/implementations/aggregate-owner-v1')


def author_sources(selected):
    raw=checked(selected);manifest=decode(raw);root=path(selected['path']).parent
    need(Path(selected['path']).name=='SOURCE.json' and set(manifest)=={'schema','files'}
         and manifest['schema']=='smc_validation_owned_author_source_v1'
         and set(manifest['files'])==AUTHOR_FILES,'Exact portable author source selection')
    bodies={name:body(root/name,expected) for name,expected in manifest['files'].items()}
    need(bodies['validation_owner.py']==body(Path(__file__).absolute()),'Selected preparation entry bytes')
    return root,manifest,bodies


def prepare(request_path,request_sha256):
    raw=body(request_path);need(pin(raw)['sha256']==request_sha256,'Exact selected preparation request')
    request=decode(raw)
    keys={'schema','author_source','repository_root','facade','validation_source','prepared_reference',
          'grade_source','transport_source','deployment_binding','runtime','outputs','max_source_bytes'}
    need(type(request) is dict and set(request)==keys and request['schema']=='smc_validation_owned_prepare_request_v1',
         'Exact explicit VALID owner preparation inputs')
    repository=path(request['repository_root']);author,manifest,bodies=author_sources(request['author_source'])
    for name in ('facade','validation_source','prepared_reference','grade_source','transport_source','deployment_binding','runtime'):
        descriptor(request[name])
    for name,expected in (('facade',FACADE_PIN),('validation_source',VALIDATION_SOURCE_PIN),
                          ('grade_source',GRADE_SOURCE_PIN),('transport_source',TRANSPORT_PIN)):
        need({k:request[name][k] for k in ('bytes','sha256')}==expected,'Fixed selected dependency: '+name)
        checked(request[name])
    previous_root=path(request['validation_source']['path']).parent
    previous=load_module('_smc_validation_prepare_reference',previous_root/'validation_reference.py',VALIDATION_CORE_PIN)
    previous.source_identity(previous_root,request['validation_source']['sha256'])
    prepared=decode(checked(request['prepared_reference']))
    need(prepared['component_source']==request['validation_source'],'Exact prepared predecessor component')
    job=decode(checked(prepared['execution']));profile=previous.validate_reference_profile(job['resource_profile'])
    deployment=checked(request['deployment_binding']);runtime=checked(request['runtime'])
    destinations=request['outputs']
    need(type(destinations) is dict and set(destinations)=={'component','overlay','protocol','prepared'},'Exact fresh output roster')
    paths={k:path(v) for k,v in destinations.items()}
    protect=(repository,author,previous_root,path(request['prepared_reference']['path']).parent,
             path(prepared['materials']['path']).parent,path(request['grade_source']['path']).parent,
             path(request['transport_source']['path']).parent)
    values=list(paths.values())
    need(all(not os.path.lexists(p) and p.parent.is_dir() for p in values)
         and all(not a.is_relative_to(b) and not b.is_relative_to(a) for i,a in enumerate(values) for b in values[i+1:])
         and all(not a.is_relative_to(b) and not b.is_relative_to(a) for a in values for b in protect),
         'Fresh disjoint external component/overlay/protocol/prepared roots')
    need(type(request['max_source_bytes']) is int and 0<request['max_source_bytes']<=1024**2,'Finite prospective source materialization cap')
    binding={'schema':'smc_validation_owned_bindings_v1',
        **{k:request[k] for k in ('facade','validation_source','prepared_reference','grade_source','transport_source')},'profile':profile}
    task={'schema':'smc_validation_owned_task_v1','route':'smc_validation_owned_reference_v1',
          'outcome':'restricted_validation_reference','phase_id':'validation_reference','role':'B','profile':profile,
          'packet_sha256':job['packet_sha256'],'declaration_sha256':prepared['declaration']['sha256'],
          'checkpoint_training_cohort':'unknown','resource_adequacy':False}
    selected={**bodies,'BINDINGS.json':encode(binding),'DEPLOYMENT_BINDING.json':deployment,'VALIDATION_TASK.json':encode(task)}
    component_manifest={'schema':'smc_validation_owned_component_v1','files':{k:pin(v) for k,v in selected.items()}}
    selected['SOURCE.json']=encode(component_manifest)
    need(sum(map(len,selected.values()))<=request['max_source_bytes'],'Complete component source precharged before writes')
    paths['component'].mkdir(mode=0o700)
    for name,data in selected.items():write_new(paths['component']/name,data,0o444)
    inputs=load_inputs(paths['component'])
    episode_module=load_module('_smc_validation_prepared_episode',paths['component']/'validation_episode.py',manifest['files']['validation_episode.py'])
    episode=episode_module.create_episode(repository,paths['component'])
    protocol=episode.instantiate(request['runtime']['path'],request['runtime']['sha256'],paths['protocol'])
    compiler=load_module('_smc_validation_prepare_overlay',paths['component']/'validation_overlay.py',manifest['files']['validation_overlay.py'])
    overlay=compiler.build_overlay(repository,paths['overlay'],max_bytes=request['max_source_bytes'])
    owner_root=paths['overlay']/OWNER_REL
    result={'schema':'smc_validation_owned_prepared_v1','request':{'path':str(path(request_path)),**pin(raw)},
        'author_source':request['author_source'],'repository_root':str(repository),
        'component_source':ref(paths['component']/'SOURCE.json'),'overlay_source':ref(owner_root/'SOURCE.json'),
        'owner_entry':ref(owner_root/'runner.py'),'protocol':protocol,'profile':profile,
        'transport_source':request['transport_source'],'preparation_launched_processes':False,
        'runtime_qualified_by_preparation':False,'resource_adequacy':False,'original_payloads_read':False,
        'required_actual_runtime':'New route/implementation/exact profile, same-boot cgroup and source-selected qualification; prior bootstrap cannot substitute.'}
    paths['prepared'].mkdir(mode=0o700);write_new(paths['prepared']/'PREPARED.json',encode(result))
    return ref(paths['prepared']/'PREPARED.json')


def inspect_prepared(prepared_path,prepared_sha256):
    raw=body(prepared_path);need(pin(raw)['sha256']==prepared_sha256,'Exact selected owned preparation')
    value=decode(raw)
    need(value['schema']=='smc_validation_owned_prepared_v1'
         and value['preparation_launched_processes'] is False and value['runtime_qualified_by_preparation'] is False
         and value['resource_adequacy'] is False,'Preparation never stands in for native custody')
    _,manifest,_=author_sources(value['author_source'])
    component=path(value['component_source']['path']).parent
    need(source_identity(component)=={k:value['component_source'][k] for k in ('bytes','sha256')},'Exact bound component')
    compiler=load_module('_smc_validation_command_overlay',component/'validation_overlay.py',manifest['files']['validation_overlay.py'])
    owner_root=path(value['overlay_source']['path']).parent
    verified=compiler.verify_overlay(owner_root)
    need(verified['source']=={k:value['overlay_source'][k] for k in ('bytes','sha256')}
         and value['owner_entry']['path']==str(owner_root/'runner.py'),'Exact derived owner command')
    checked(value['owner_entry']);checked(value['protocol'])
    return value


def owner_command(prepared_path,prepared_sha256,*,action,output,owner,result_sha256=None,recovery_read_bytes=None,recovery_write_bytes=None):
    value=inspect_prepared(prepared_path,prepared_sha256)
    argv=[sys.executable,'-I','-B',value['owner_entry']['path'],action]
    if action=='execute':
        need(result_sha256 is None and type(recovery_read_bytes) is int and recovery_read_bytes>0
             and type(recovery_write_bytes) is int and recovery_write_bytes>0,'Explicit finite recovery allocation')
        argv+=['--protocol',value['protocol']['path'],'--protocol-sha256',value['protocol']['sha256'],
               '--output',str(path(output)),'--owner',str(path(owner)),
               '--recovery-read-bytes',str(recovery_read_bytes),'--recovery-write-bytes',str(recovery_write_bytes)]
    elif action=='custody':
        need(type(result_sha256) is str and re.fullmatch('[0-9a-f]{64}',result_sha256)
             and recovery_read_bytes is None and recovery_write_bytes is None,'Exact saved owner result for custody')
        argv+=['--owner',str(path(owner)),'--result-sha256',result_sha256,'--output',str(path(output))]
    else:need(False,'Only protected execute or post-closure custody')
    return {'schema':'smc_validation_owned_command_v1','argv':argv,'prepared_sha256':prepared_sha256,
        'execution_performed':False,'runtime_qualified':False,'resource_adequacy':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('prepare');p.add_argument('--request',required=True);p.add_argument('--sha256',required=True)
    for name in ('execute','custody','command'):
        p=sub.add_parser(name);p.add_argument('--prepared',required=True);p.add_argument('--sha256',required=True)
        p.add_argument('--output',required=True);p.add_argument('--owner',required=True)
        if name=='command':p.add_argument('--operation',choices=('execute','custody'),required=True)
        p.add_argument('--result-sha256');p.add_argument('--recovery-read-bytes',type=int);p.add_argument('--recovery-write-bytes',type=int)
    args=parser.parse_args(argv)
    if args.action=='prepare':result=prepare(args.request,args.sha256)
    else:
        action=args.operation if args.action=='command' else args.action
        result=owner_command(args.prepared,args.sha256,action=action,output=args.output,owner=args.owner,
            result_sha256=args.result_sha256,recovery_read_bytes=args.recovery_read_bytes,recovery_write_bytes=args.recovery_write_bytes)
        if args.action!='command':os.execv(sys.executable,result['argv'])
    print(encode(result).decode(),end='')


if __name__=='__main__':main()
