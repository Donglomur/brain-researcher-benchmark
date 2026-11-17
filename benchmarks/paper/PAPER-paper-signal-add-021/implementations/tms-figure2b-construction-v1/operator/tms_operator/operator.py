"""Actual staged-view -> owned-host -> complete-capture -> protected-pair caller."""
from __future__ import annotations
import os,stat
from pathlib import Path
from .schema import *
from .capture import capture_output,size_plan
from tms_figure import views,paired
from tms_figure.contract import open_pinned

def source_admission(root,expected,budget):
    root=directory(root);lock=load(root/'OPERATOR_LOCK.json',expected,budget)
    keys(lock,{'schema','files','inherited_source_commit'})
    require(lock['schema']=='tms_figure2b_operator_source_lock_v1' and lock['inherited_source_commit']=='33986480f8347ce2923bea79319749166e8ae1ae','exact inherited source selection')
    require(type(lock['files']) is dict and 15<len(lock['files'])<=2048,'complete finite source composition')
    actual=source_members(root,budget)-{'OPERATOR_LOCK.json'}
    require(actual==set(lock['files']),'closed source inventory')
    for rel,p in lock['files'].items():
        require(type(rel) is str and not Path(rel).is_absolute() and '..' not in Path(rel).parts,'relative source member')
        pin(p);require(p['bytes']<=1048576,'ordinary source member cap')
        body=ordinary_body(root/rel,p,budget);del body
    return lock

def source_paths(runtime,stage):
    require(type(runtime) is dict and runtime.get('stage_root')==str(stage),'frozen exact staging root')
    keys(runtime['arm_paths'],{'A','B'})
    roots=[]
    for arm in ('A','B'):
        p=runtime['arm_paths'][arm]
        keys(p,{'operator_root','view','task','private','work','output','logs'})
        require(all(type(v) is str and Path(v).is_absolute() for v in p.values()),'explicit absolute runtime locations')
        require(p['view']==str(stage/'views'/arm),'exact staged arm view')
        roots.extend(p[k] for k in ('task','private','work','output','logs'))
    require(runtime['arm_paths']['A']['operator_root']==runtime['arm_paths']['B']['operator_root'],'common fixed operator source')
    operator_root=Path(runtime['arm_paths']['A']['operator_root'])
    separate(roots+[stage/'views',stage/'captures',stage/'records',stage/'private-grade',operator_root])
    return operator_root

def stage_pair(*,stage_root,selections,capsule_path,capsule_pin,runtime_path,runtime_pin,
               qualification_path,qualification_pin,resource_limits,trials,
               absolute_tolerance,relative_tolerance,tolerance_justification,
               operator_lock_pin,source_lock_pin,budget):
    """Concrete future staging. Explicit original data custody remains caller-owned."""
    exact_budget(budget);stage=Path(stage_root).absolute();require(not stage.exists(),'fresh stage')
    cfg=load(capsule_path,capsule_pin,budget);capsule(cfg);runtime=load(runtime_path,runtime_pin,budget)
    qualification=load(qualification_path,qualification_pin,budget)
    root=source_paths(runtime,stage);source_admission(root,operator_lock_pin,budget)
    paired.source_lock(root/'SOURCE_LOCK.json',source_lock_pin,budget)
    limits(resource_limits);keys(trials,{'A','B'})
    for value in trials.values():slug(value)
    require(trials['A']!=trials['B'],'fresh independent trial identities')
    identity=views.admit_sources(selections,budget)
    # Data counts/bytes come from the full existing science contract, no arrays.
    extent=size_plan(identity,1048576,identity['source']['bytes'],copy_count=2)
    require(resource_limits['output_bytes']>=extent['binary_output_bytes_per_arm']+1048576,'full output storage including bounded manifest')
    fresh_directory(stage);fresh_directory(stage/'views');fresh_directory(stage/'records');fresh_directory(stage/'captures')
    # Preserve exact selected document bodies (not reserialized equivalents).
    for name,path,p in [('CAPSULE.json',capsule_path,capsule_pin),('RUNTIME.json',runtime_path,runtime_pin),('QUALIFICATION.json',qualification_path,qualification_pin)]:
        body=read_pinned(path,p,budget);budget.charge(write=len(body))
        fd=os.open(stage/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,'wb',closefd=False) as stream:stream.write(body);stream.flush();os.fsync(fd)
        finally:os.close(fd)
    vp=views.stage_pair(selections=selections,roots={a:stage/'views'/a for a in ('A','B')},budget=budget)
    plan={'schema':'tms_figure2b_execution_plan_v1','identity':identity,'trials':trials,'views':vp,
        'capsule':capsule_pin,'runtime':runtime_pin,'qualification':qualification_pin,'limits':resource_limits,
        'source_lock':source_lock_pin,'operator_lock':operator_lock_pin,'absolute_tolerance':absolute_tolerance,
        'relative_tolerance':relative_tolerance,'tolerance_justification':tolerance_justification}
    execution_plan(plan);pp=save(stage/'EXECUTION_PLAN.json',plan,budget)
    save(stage/'EXTENTS.json',extent,budget)
    # The selected unprivileged trusted host needs these exact public/runtime
    # operands. Private capture/grade/record trees retain root-owned0700.
    integer(runtime['host_gid'],0)
    for path in (stage,stage/'views'):
        os.chown(path,-1,runtime['host_gid']);path.chmod(0o710)
    for name in ('EXECUTION_PLAN.json','CAPSULE.json','RUNTIME.json','QUALIFICATION.json'):
        path=stage/name;os.chown(path,-1,runtime['host_gid']);path.chmod(0o440)
    return {'execution_plan':pp,'stage':str(stage),'state':'staged_not_executed'}

def _load_stage(stage,expected,budget):
    stage=directory(stage);plan=execution_plan(load(stage/'EXECUTION_PLAN.json',expected,budget))
    runtime=load(stage/'RUNTIME.json',plan['runtime'],budget);root=source_paths(runtime,stage)
    source_admission(root,plan['operator_lock'],budget)
    load(stage/'QUALIFICATION.json',plan['qualification'],budget)
    capsule(load(stage/'CAPSULE.json',plan['capsule'],budget))
    # Exact complete views are rejoined before either arm can be launched.
    views_meta={}
    for arm in ('A','B'):
        view=stage/'views'/arm;v=load(view/'VIEW.json',plan['views'][arm],budget)
        keys(v,{'schema','arm','members'});require(v['schema']=='tms_figure2b_view_v1' and v['arm']==arm,'view identity')
        names=views.COMMON|(views.CODE if arm=='B' else set())
        require(type(v['members']) is dict and set(v['members'])==names and set(x.name for x in view.iterdir())==names|{'VIEW.json'},'complete exact arm exposure')
        for name,p in v['members'].items():
            if name in views.FIXED_SOURCES:require(p==views.FIXED_SOURCES[name],'exact selected view body')
            fd=open_pinned(view/name,p,budget);os.close(fd)
        views_meta[arm]=v
    require(all(views_meta['A']['members'][n]==views_meta['B']['members'][n] for n in views.COMMON),'same complete common inputs')
    return stage,plan,runtime

def run_pair(*,stage,execution_plan_pin,budget):
    """Actual fixed host and collector paths; no injectable prediction/closure callback."""
    stage,plan,runtime=_load_stage(stage,execution_plan_pin,budget)
    from .host import run_arm,admit_closed
    results={};captures={};record_pins={}
    for arm in ('A','B'):
        paths=runtime['arm_paths'][arm]
        record=run_arm(plan,arm,paths,runtime,budget)
        admit_closed(record,plan,arm,paths,runtime,budget)
        record_pins[arm]=save(stage/'records'/(arm+'.host.json'),record,budget)
        # A closed host is necessary; scientific outputs may still be invalid.
        captures[arm]=capture_output(source=paths['output'],destination=stage/'captures'/arm,meta=plan['identity'],budget=budget)
        save(stage/'records'/(arm+'.capture.json'),captures[arm],budget)
        results[arm]=record
    # No protected reference is opened here. The authority is a separate input.
    policy={'schema':'tms_figure2b_actual_matched_policy_v1','execution_plan':execution_plan_pin,
        'execution_plan_sha256':digest(plan),'capsule':plan['capsule'],'runtime':plan['runtime'],
        'operator_lock':plan['operator_lock'],'limits':plan['limits'],'host_records':record_pins,
        'comparison':'same fixed agent and resources; only declared original-code exposure differs',
        'actual_usage':'complete per-arm provider/terminal records; equal ceilings do not imply equal realized use'}
    policy_pin=save(stage/'MATCHED_POLICY.json',policy,budget)
    final={'schema':'tms_figure2b_paired_plan_v1','identity':plan['identity'],'arms':{},
        'absolute_tolerance':plan['absolute_tolerance'],'relative_tolerance':plan['relative_tolerance'],
        'tolerance_justification':plan['tolerance_justification'],'matched_policy':policy_pin,'source_lock':plan['source_lock']}
    observations={}
    for arm in ('A','B'):
        row={'trial_id':plan['trials'][arm],'view':plan['views'][arm],'program':plan['capsule'],'output':captures[arm]['output']}
        final['arms'][arm]=row
        # These fields are emitted ONLY after the real fixed host admission and
        # complete stable scientific capture above, never from candidate flags.
        observations[arm]={'schema':'tms_figure2b_trusted_closure_v1','arm':arm,**row,
            'natural_exit':True,'returncode':0,'producer_closed':True,'capture_complete':True,
            'exclusive_custody':True,'isolation_qualified':True}
    paired.closed_pair(final,observations)
    request={'schema':'tms_figure2b_grade_request_v1','execution_plan':execution_plan_pin,'plan':final,
        'observations':observations,'host_records':record_pins,
        'captures':{a:str(stage/'captures'/a) for a in ('A','B')},'authorization':'external_operator_grant_required'}
    rp=save(stage/'GRADE_REQUEST.json',request,budget)
    return {'request':rp,'plan_sha256':digest(final),'observations_sha256':digest(observations),'state':'closed_ungraded'}

def grade_pair(*,stage,request_pin,authority_path,authority_pin,budget,metadata_read_reservation):
    """Actual call to unchanged V4 scorer after complete preplan/host/capture joins."""
    stage=directory(stage);request=load(stage/'GRADE_REQUEST.json',request_pin,budget)
    keys(request,{'schema','execution_plan','plan','observations','host_records','captures','authorization'})
    require(request['schema']=='tms_figure2b_grade_request_v1' and request['authorization']=='external_operator_grant_required','complete grade request')
    stage,pre,runtime=_load_stage(stage,request['execution_plan'],budget)
    from .host import admit_closed
    keys(request['host_records'],{'A','B'});keys(request['captures'],{'A','B'})
    final=request['plan'];paired.closed_pair(final,request['observations'])
    require(final['identity']==pre['identity'] and all(final[k]==pre[k] for k in ('source_lock','absolute_tolerance','relative_tolerance','tolerance_justification')),'final scientific plan unchanged')
    policy=load(stage/'MATCHED_POLICY.json',final['matched_policy'],budget)
    require(policy.get('execution_plan')==request['execution_plan'] and policy.get('execution_plan_sha256')==digest(pre) and policy.get('host_records')==request['host_records'] and policy.get('capsule')==pre['capsule'] and policy.get('runtime')==pre['runtime'] and policy.get('limits')==pre['limits'],'actual matched-policy join')
    for arm in ('A','B'):
        record=load(stage/'records'/(arm+'.host.json'),request['host_records'][arm],budget)
        admit_closed(record,pre,arm,runtime['arm_paths'][arm],runtime,budget)
        row=final['arms'][arm]
        require(row['trial_id']==pre['trials'][arm] and row['view']==pre['views'][arm] and row['program']==pre['capsule'],'same frozen pre-release treatment')
        require(request['captures'][arm]==str(stage/'captures'/arm),'fixed sealed capture path')
    root=Path(runtime['arm_paths']['A']['operator_root'])
    return paired.grade_pair(plan=final,observations=request['observations'],authority_path=authority_path,
        authority_pin=authority_pin,source_lock_path=root/'SOURCE_LOCK.json',captures=request['captures'],
        derivative_path=stage/'views'/'A'/'masterTFR_allsubs.mat',private_output=stage/'private-grade',
        budget=budget,metadata_read_reservation=metadata_read_reservation)
