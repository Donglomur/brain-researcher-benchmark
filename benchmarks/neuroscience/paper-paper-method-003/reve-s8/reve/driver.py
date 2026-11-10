"""Closed declarative action recipe; no eval/import/command strings from requests."""
from pathlib import Path
from .errors import require
from .objects import Reader,canonical,digest,fields
from .policy import Authority
from .deadline import Window
from .roster import Scope
from .controller import Controller


def run_selected(root,driver_pin,authority_pin,implementation_identity,window=None):
    if window is not None:window.check()
    reader=Reader(root,32*1024**2,128,guard=window.check if window is not None else None)
    selected=reader.json(authority_pin)
    window=window or Window(selected['valid_after'],selected['expires_at']);window.check();reader.guard=window.check
    require(window.original==(selected['valid_after'],selected['expires_at']),'same original CLI/driver authority window')
    d=reader.json(driver_pin)
    fields(d,('schema','plan','domains','environment','actions','mode'))
    require(d['schema']=='reve-complete-driver-v1' and d['mode']=='production','production driver requires explicit selected production authority')
    plan=reader.json(d['plan']);domains=reader.json(d['domains']);environment=reader.json(d['environment']);window.check();scope=Scope(guard=window.check);window.check()
    authority=Authority(root,authority_pin,digest(canonical(plan)),implementation_identity,'production',driver_pin['sha256'],window=window)
    window.check()
    controller=Controller(authority.selection['output_root'],scope,plan,authority,domains,environment,'production')
    sources={};materialized={};barrier_seen=False;grade_seen=False
    for action in d['actions']:
        authority.check_current()
        require(type(action) is dict and type(action.get('operation')) is str,'closed action')
        op=action['operation']
        if op=='admit_context':
            fields(action,('operation','id','domain','source_access','parents','qualification','prior_labels','prior_signals'))
            controller.exposure.admit_context(action['id'],action['domain'],action['source_access'],action['parents'],action['qualification'],action['prior_labels'],action['prior_signals'])
        elif op=='register_source':
            fields(action,('operation','name','context','source_root','manifest','entrypoint','interpreter','environment','role','parents'))
            require(action['name'] not in sources,'source handle replay')
            manifest=reader.json(action['manifest'])
            key,_=controller.register(action['context'],action['source_root'],manifest,action['entrypoint'],action['interpreter'],action['environment'],action['role'],action['parents'])
            sources[action['name']]=key
        elif op=='operator_product':
            fields(action,('operation','job','root','object'));controller.admit_operator_product(action['job'],action['object'],action['root'])
        elif op=='run_job':
            fields(action,('operation','job','source','input_root','input_manifest'))
            job=controller.jobs[action['job']]
            if action['input_manifest']=='produced':
                require(action['job'] in materialized,'missing actual produced view');input_root,manifest=materialized[action['job']]
                require(str(input_root)==action['input_root'],'produced view path')
            else:input_root=action['input_root'];manifest=reader.json(action['input_manifest'])
            controller.run_job(action['job'],sources[action['source']],input_root,manifest,job['payload'])
        elif op=='materialize_produced_input':
            fields(action,('operation','job'));require(action['job'] not in materialized,'view replay')
            materialized[action['job']]=controller.materialize_produced_input(action['job'])
        elif op=='freeze':
            fields(action,('operation','job','contexts'));controller.freeze(action['contexts'],action['job'])
        elif op=='case_child':
            fields(action,('operation','id','parent','domain','case'))
            case=reader.json(action['case']);controller.exposure.case_child(action['id'],action['parent'],action['domain'],case)
        elif op=='unavailable':
            fields(action,('operation','job','reason'));controller.terminal_unavailable(action['job'],action['reason'])
        elif op=='collect_banks':
            fields(action,('operation','job'));controller.collect_banks(action['job'])
        elif op=='barrier':
            fields(action,('operation','job'));require(not barrier_seen,'barrier action replay');controller.barrier(action['job']);barrier_seen=True
        elif op=='grade':
            fields(action,('operation','job','target_root','target_index'));require(barrier_seen and not grade_seen,'grade action ordering')
            controller.grade(action['job'],action['target_root'],action['target_index']);grade_seen=True
        elif op=='final_report':
            fields(action,('operation',));require(grade_seen,'report before grade');controller.final_report()
        else:raise ValueError('unknown driver operation')
        authority.check_current()
    require(controller.grading_results is not None and (controller.root/'REPORT.json').is_file(),'whole selected driver did not finish report')
    authority.check_current()
    return controller.public_status()
