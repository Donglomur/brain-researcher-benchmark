"""Strict task-local source/runtime/packet selection for the reused owner."""
import hashlib
import os
import re
import stat
import time

import common as c
import docker_owner
import fold_runner

SCHEMA = 'abr_protected_fold_whole_run_v1'
RUNTIME = {'python':'3.12.8','numpy':'2.2.6','scipy':'1.15.3','scikit-learn':'1.6.1'}
LIMITS = {'active_seconds':7200,'whole_seconds':7320,'outer_seconds':7350,
          'per_fold_seconds':600,'container_memory_bytes':2147483648,
          'container_cpus':1,'host_rss_bytes':1073741824,
          'managed_read_bytes':21474836480,'retained_bytes':8589934592,
          'model_calls':0,'contexts':10}


def admit_manifest(raw, sha, attempt):
    c.need(type(sha) is str and hashlib.sha256(raw).hexdigest()==sha, 'selected manifest hash')
    c.need(type(attempt) is str and re.fullmatch('[a-z0-9][a-z0-9-]{0,63}',attempt), 'attempt identity')
    wrapper=c.decode(raw,65536)
    c.need(type(wrapper) is dict and set(wrapper)=={'schema','attempt_id','selection'} and
           wrapper['schema']==SCHEMA and wrapper['attempt_id']==attempt,'closed operation wrapper')
    s=wrapper['selection']
    c.need(type(s) is dict and set(s)=={'root_execution_selected','packet_root','completion','manifest','preparation',
           'programs','runtime_evidence','budget'},'closed operation selection')
    c.need(s['root_execution_selected'] is True and s['budget']==LIMITS,'explicit unchanged operation allocation')
    c.plain(s['packet_root'])
    fold_runner.entry_pin(s['completion'],1048576);fold_runner.entry_pin(s['manifest'],1048576)
    fold_runner.entry_pin(s['preparation'],1048576)
    c.need(type(s['programs']) is dict and set(s['programs'])==set(fold_runner.ROUTES),'two exact methods')
    for p in s['programs'].values():fold_runner.entry_pin(p,262144)
    e=s['runtime_evidence']
    c.need(type(e) is dict and set(e)=={'source_review','runtime_review','fresh_capacity'},'complete trusted admission')
    for pin in e.values():fold_runner.entry_pin(pin,1048576)
    return wrapper


def prepare(wrapper, modules, bodies, budget):
    cfg=c.decode(bodies['CONFIG.json'],65536);s=wrapper['selection']
    c.need(cfg['schema']=='abr_fold_owner_configuration_v1' and cfg['budget']==LIMITS and
           cfg['runtime_versions']==RUNTIME,'fixed ABR runtime contract')
    c.need(docker_owner.IMAGE==cfg['image'] and re.fullmatch('sha256:[0-9a-f]{64}',cfg['image']) and
           str(docker_owner.DAEMON_SOCKET)==cfg['daemon_socket'] and
           docker_owner.DAEMON_GUARD==cfg['daemon_guard'],'source-bound fresh daemon/image')
    # These are assertions by the trusted root operator supported by pinned
    # external reviews, not credentials, external authority or self-proving flags.
    expected={name:s[name] for name in ('packet_root','completion','manifest','preparation','programs')}
    c.need(expected==cfg['operands'],'exact predeclared packet and program operands')
    observed={}
    for name,p in s['runtime_evidence'].items():
        observed[name]=c.decode(c.read(p['path'],fold_runner.entry_pin(p,1048576),budget,cap=1048576))
    source=observed['source_review']
    bodypins={n:c.pin(b) for n,b in bodies.items()}
    c.need(source=={'schema':'abr_fold_source_review_v1','whole_source_accepted':True,
                   'members':bodypins},'exact whole generated-source review')
    runtime=observed['runtime_review']
    c.need(type(runtime) is dict and set(runtime)=={'schema','image','versions','whole_runtime_accepted',
            'no_protected_payload_in_image','independent_review'} and
            runtime['schema']=='abr_fold_runtime_review_v1' and runtime['image']==cfg['image'] and
            runtime['versions']==RUNTIME and runtime['whole_runtime_accepted'] is True and
            runtime['no_protected_payload_in_image'] is True,'accepted same native runtime and sterile image')
    c.admit_pin(runtime['independent_review'],1048576)
    cap=observed['fresh_capacity'];now=time.time()
    c.need(type(cap) is dict and set(cap)=={'schema','observed_unix','image','daemon_socket','daemon_guard',
       'pressure_samples','swap_used_growth_bytes','swapouts_growth','pageouts_growth',
       'potential_memory_bytes','selected_host_memory_bytes','disk_available_bytes','cpu_demand_plus_reserve',
       'vm_cpus','vm_memory_bytes','complete_observations'},'complete fresh capacity fields')
    c.need(cap['schema']=='abr_fold_capacity_v1' and type(cap['observed_unix']) in (int,float) and
           0<=now-cap['observed_unix']<=60 and cap['image']==cfg['image'] and
           cap['daemon_socket']==cfg['daemon_socket'] and cap['daemon_guard']==cfg['daemon_guard'],
           'fresh same transport/runtime capacity')
    for name in ('swap_used_growth_bytes','swapouts_growth','pageouts_growth','potential_memory_bytes',
                 'selected_host_memory_bytes','disk_available_bytes','vm_cpus','vm_memory_bytes'):
        c.need(type(cap[name]) is int,'integer capacity counter')
    c.need(cap['pressure_samples']==['NORMAL','NORMAL'] and
           all(cap[n]<=0 for n in ('swap_used_growth_bytes','swapouts_growth','pageouts_growth')) and
           cap['potential_memory_bytes']>=max(14*1024**3,cap['selected_host_memory_bytes']+4*1024**3) and
           cap['selected_host_memory_bytes']>=LIMITS['host_rss_bytes'] and
           cap['disk_available_bytes']>=10*1024**3 and
           type(cap['cpu_demand_plus_reserve']) in (int,float) and 0<=cap['cpu_demand_plus_reserve']<=14 and
           cap['vm_cpus']>=2 and cap['vm_memory_bytes']>=3*1024**3,'complete selected-host resource admission')
    c.admit_pin(cap['complete_observations'],1048576)
    return {'selection':s,'documents':{n:bodies[n] for n in fold_runner.DOCS},
            'admission':{'source':s['runtime_evidence']['source_review'],
                         'runtime':s['runtime_evidence']['runtime_review'],
                         'capacity':s['runtime_evidence']['fresh_capacity'],
                         'preparation':s['preparation']}}
