"""Two independent full45/63-answer programs, captured native lineage, no gold."""
import os,stat
from pathlib import Path

def input_metadata(s,budget):
    public=c.parse(c.capture(s['public_manifest']['path'],packet.JSON_CAP,c.only_pin(s['public_manifest']),budget.tick,budget.read))
    plan=packet.admit(public);c.need({k:plan[k] for k in packet.PLAN_FIELDS}==s['plan'],'actual whole input plan')
    expected={'PUBLIC.json':c.only_pin(s['public_manifest'])}
    for row in public['rows']:
        expected[row['features']['path']]=c.only_pin(row['features'])
        if row['role']=='query':expected[row['permutation']['path']]=c.only_pin(row['permutation'])
    files,dirs,_=c.inventory(s['public_root'],packet.NEURAL_CAP+plan['permutation_bytes']+packet.JSON_CAP+4096*(plan['cases']+plan['query_count']+10),100020)
    c.need(set(files)==set(expected),'clean complete input tree only; no gold/keys/lineage')
    for name,(_,stamp) in files.items():c.need(stamp[4]==expected[name]['bytes'] and stat.S_IMODE(stamp[2])==0o444,'readonly prepared regular file')
    root=c.path(s['public_root']);c.need({d.relative_to(root).as_posix() for d in dirs}=={'.','arrays','permutations'} and all(stat.S_IMODE(d.lstat().st_mode)==0o555 for d in dirs),'exact clean readonly input directories')
    budget.tick();return public,plan,{name:stamp for name,(_,stamp) in files.items()}

def unchanged_inputs(s,plan,stamps,budget):
    files,_,_=c.inventory(s['public_root'],packet.NEURAL_CAP+plan['permutation_bytes']+packet.JSON_CAP+4096*(plan['cases']+plan['query_count']+10),100020)
    c.need({name:stamp for name,(_,stamp) in files.items()}==stamps,'original prepared source remained unchanged')
    c.capture(s['public_manifest']['path'],packet.JSON_CAP,c.only_pin(s['public_manifest']),budget.tick,budget.read)

def run(s,source,bodies,origin,worker_end):
    c.need(worker_end==origin+s['limits']['whole_seconds']-s['limits']['observer_seconds'],'inherited original worker cutoff')
    root=c.path(s['output']);c.need(not root.exists() and root.parent.is_dir(),'fresh owned attempt root')
    budget=c.Budget(root,s['other_future_bytes'],worker_end,s['limits']);budget.read(SOURCE_READ_CHARGE);budget.capacity(65536)
    root.mkdir(mode=0o700);c.sync_dir(root.parent,budget.tick)
    current=None;completed=0;last=None;models={}
    try:
        reference=bodies['reference/reference_program.py'];reference.decode('utf-8');c.need(0<len(reference)<=131072,'bounded independent reference source')
        policy.reviews(s,source,c.pin(reference),lambda p,cap,pin:c.capture(p,cap,pin,budget.tick,budget.read))
        candidate=c.capture(s['candidate_program']['path'],131072,c.only_pin(s['candidate_program']),budget.tick,budget.read);candidate.decode('utf-8')
        programs={'candidate':candidate,'independent_reference':reference};pins={name:c.pin(raw) for name,raw in programs.items()}
        (root/'programs').mkdir(mode=0o700)
        for name,raw in programs.items():c.save(root/'programs'/f'{name}.py',raw,131072,budget.tick,budget.write);c.readable(root/'programs'/f'{name}.py',budget.tick)
        public,plan,stamps=input_metadata(s,budget)
        commitment=dict(schema='neural014-commitment-v1',source=source,programs=pins,public_manifest=s['public_manifest'],image=s['image'],plan=s['plan'],limits=s['limits'],private_grading_authorized=False)
        cp=c.save(root/'COMMITMENT.json',c.encoded(commitment),65536,budget.tick,budget.write)
        trusted=root/'trusted';trusted.mkdir(mode=0o700)
        for name in ('holder.py','candidate_entry.py'):
            c.save(trusted/name,bodies['transport/'+name],100000,budget.tick,budget.write);c.readable(trusted/name,budget.tick)
        os.chmod(trusted,0o555);c.sync_dir(trusted,budget.tick)
        (root/'phases').mkdir(mode=0o700);(root/'models').mkdir(mode=0o700)
        values={name:{} for name in packet.PANELS};schedule=packet.phases(public,plan)
        for phase in schedule:
            last=phase;budget.tick();d=root/'phases'/phase['phase_id'];d.mkdir(mode=0o700)
            model=None if phase['model_key']is None else models[phase['model_key']]
            if model is not None:c.need(c.stamp(model['path'].lstat())==model['stamp'],'same sealed model before native exposure')
            current=root/'current';expected=packet.view(current,c.path(s['public_root']),public,phase,budget,plan);viewstamps=packet.verify_view(current,expected,budget)
            request=dict(schema='neural014-phase-request-v1',source=source,phase=phase,program=pins[phase['panel']],image=s['image'],seconds=s[phase['kind']+'_seconds'],model=None if model is None else model['pin'],input=expected['INPUT.json'],view_members=c.pin(c.encoded(expected)))
            rp=c.save(d/'REQUEST.json',c.encoded(request),65536,budget.tick,budget.write)
            budget.native(phase['kind'],phase['ordinal'])
            native_result=native.phase(s,trusted,current,root/'programs'/f"{phase['panel']}.py",None if model is None else model['path'],d,phase['kind'],phase['ordinal'],source,budget,worker_end)
            c.need(native_result['status']=='captured' and native_result['all_native_resources_closed']is True,'complete native phase closure')
            if model is not None:c.need(c.stamp(model['path'].lstat())==model['stamp'],'same sealed model after native exposure')
            packet.retire(current,expected,viewstamps,budget);current=None
            npin=c.pin(c.capture(d/'NATIVE.json',packet.NATIVE_CAP,None,budget.tick,budget.read));created=None
            if phase['kind']in('fit','adapt'):
                target=root/'models'/f"{phase['phase_id']}.bin";os.rename(d/'model.bin',target);c.readable(target,budget.tick)
                pin=native_result['output'];stamp=c.stamp(target.lstat());c.need(stamp[4]==pin['bytes'],'same captured model extent')
                c.capture(target,packet.MODEL_CAP,pin,budget.tick,budget.read)
                models[phase['result_key']]=dict(path=target,pin=pin,stamp=stamp)
                created=dict(key=phase['result_key'],pin=pin)
                seal=dict(schema='neural014-model-seal-v1',source=source,phase=phase,program=pins[phase['panel']],input_model=request['model'],model=pin,native=npin,input=request['input'],view_retired=True)
                c.save(d/'MODEL_SEAL.json',c.encoded(seal),65536,budget.tick,budget.write)
            else:
                raw=c.capture(d/'prediction.json',packet.PRED_CAP,native_result['output'],budget.tick,budget.read);tokens=outputs.prediction(raw,phase)
                ids=[r['id'] for r in plan['queries'] if r['session']==phase['session']] if phase['kind']=='prior' else [phase['case_id']]
                for i in ids:values[phase['panel']][(phase['session'],phase['arm'],i)]=tokens
            closed=dict(schema='neural014-phase-closed-v1',phase=phase,request=rp,native=npin,model=created,view_retired=True)
            c.save(d/'CLOSED.json',c.encoded(closed),65536,budget.tick,budget.write);completed+=1
        c.need(completed==s['limits']['phase_count'] and len(models)==38,'all full phase/model scope')
        panel_pins={}
        for panel in packet.PANELS:
            answers=outputs.assemble(public,values[panel]);panel_pins[panel]=c.save(root/f'{panel}.json',c.encoded(answers),packet.JSON_CAP,budget.tick,budget.write)
        for model in models.values():c.capture(model['path'],packet.MODEL_CAP,model['pin'],budget.tick,budget.read)
        unchanged_inputs(s,plan,stamps,budget)
        complete=dict(schema='neural014-complete-v1',status='complete_unqualified',source=source,commitment=cp,phase_count=completed,model_count=len(models),panels=panel_pins,all_views_retired=True,private_targets_opened=False,scoring_performed=False,runtime_qualified=False,scientific_qualified=False,costs=budget.record())
        pin=c.save(root/'COMPLETE.json',c.encoded(complete),packet.JSON_CAP,budget.tick,budget.write);budget.tick()
        return dict(schema='neural014-worker-result-v1',status='complete_unqualified',source=source,complete=pin,phase_count=completed)
    except BaseException as exc:
        failure=dict(schema='neural014-failure-v1',source=source,last_phase=last,completed_phases=completed,expected_phases=s['limits']['phase_count'],models_sealed=len(models),current_view_may_remain=current is not None,automatic_retry=False,native_recovery_may_be_required=True,error_type=type(exc).__name__,costs=budget.record())
        try:c.save(root/'FAILURE.json',c.encoded(failure),packet.JSON_CAP,budget.tick,budget.write)
        except BaseException:pass
        raise
