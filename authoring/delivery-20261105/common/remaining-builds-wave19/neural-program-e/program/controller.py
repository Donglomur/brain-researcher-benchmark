"""Concrete full90 controller; complete independent panels precede all gold access."""
import hashlib, os, stat

def authenticate_file(path,pin,budget):
    path=c.path(path);fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    try:
        a=os.fstat(fd);c.need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==pin['bytes'],'full original projected file extent')
        budget.read(a.st_size+1);h=hashlib.sha256();n=0
        while True:
            budget.tick();block=os.read(fd,min(1048576,a.st_size+1-n))
            if not block:break
            n+=len(block);c.need(n<=a.st_size,'no growing source');h.update(block)
        c.need(n==a.st_size and h.hexdigest()==pin['sha256'] and c.stamp(a)==c.stamp(os.fstat(fd))==c.stamp(path.lstat()),'stable full projected content identity')
    finally:os.close(fd)

def input_metadata(s,budget):
    root=c.path(s['public_root']);public=c.parse(c.capture(s['public_manifest']['path'],packet.JSON_CAP,c.only_pin(s['public_manifest']),budget.tick,budget.read));plan=packet.admit(public)
    c.need({k:plan[k] for k in packet.PLAN_FIELDS}==s['plan'],'same complete admitted plan')
    expected={'PUBLIC.json':c.only_pin(s['public_manifest']),'PROJECTION.json':public['projection_receipt'],**packet.source_files(public)}
    files,dirs,_=c.inventory(root,packet.NEURAL_CAP+plan['label_bytes']+2*packet.JSON_CAP+4096*1000,1000)
    c.need(set(files)==set(expected) and {d.relative_to(root).as_posix() for d in dirs}=={'.','arrays','labels'},'exact sanitized prepared tree; no gold or original provenance')
    for name,(_,stamp) in files.items():
        c.need(stamp[4]==expected[name]['bytes'] and stat.S_IMODE(stamp[2])==0o444,'readonly prepared inputs')
        authenticate_file(root/name,expected[name],budget)
    c.need(all(stat.S_IMODE(d.lstat().st_mode)==0o555 for d in dirs),'readonly prepared directories')
    receipt=c.parse(c.capture(root/'PROJECTION.json',packet.JSON_CAP,public['projection_receipt'],budget.tick,budget.read))
    c.need(receipt.get('schema')=='neural089-label-free-projection-v1' and receipt.get('original_source_lock')==public['original_source_lock'] and receipt.get('full_run_count')==90 and receipt.get('full_event_count')==plan['cases'] and receipt.get('query_count')==plan['query_count'] and receipt.get('query_labels_in_output')is False,'operator label-free lineage receipt')
    bindings=receipt.get('run_bindings');c.need(type(bindings)is list and len(bindings)==90,'complete original run bindings')
    for original,row,binding in zip(science.ORIGINAL_ASSETS['runs'],public['runs'],bindings):
        c.need(binding.get('run_key')==original['run_key'] and binding.get('source_recording')==original['recording'] and binding.get('source_events')==original['events'] and binding.get('group_id')==row['group_id'] and binding.get('windows')==row['windows'] and row['partition']==original['split'],'exact source run/order/partition/event identity')
    return public,plan,{name:stamp for name,(_,stamp) in files.items()}

def unchanged_inputs(s,plan,stamps,budget):
    files,_,_=c.inventory(s['public_root'],packet.NEURAL_CAP+plan['label_bytes']+2*packet.JSON_CAP+4096*1000,1000)
    c.need({name:stamp for name,(_,stamp) in files.items()}==stamps,'complete prepared inputs unchanged through campaign')
    budget.tick()

def run(s,source,bodies,origin,worker_end):
    c.need(worker_end==origin+s['limits']['whole_seconds']-s['limits']['observer_seconds'],'one inherited worker cutoff')
    root=c.path(s['output']);c.need(not root.exists() and root.parent.is_dir(),'fresh owned attempt')
    budget=c.Budget(root,s['other_future_bytes'],worker_end,s['limits']);budget.read(SOURCE_READ_CHARGE);budget.capacity(65536)
    root.mkdir(mode=0o700);c.sync_dir(root.parent,budget.tick)
    current=None;completed=0;entered=0;last=None;models={};native_reserved=False;native_phase_call_attempted=False
    try:
        reference=bodies['reference/reference_program.py'];c.need(0<len(reference)<=131072,'bounded independent reference')
        policy.reviews(s,source,c.pin(reference),lambda p,cap,pin:c.capture(p,cap,pin,budget.tick,budget.read))
        candidate=c.capture(s['candidate_program']['path'],131072,c.only_pin(s['candidate_program']),budget.tick,budget.read);candidate.decode('utf-8')
        programs={'candidate':candidate,'independent_reference':reference};pins={k:c.pin(v) for k,v in programs.items()}
        (root/'programs').mkdir(mode=0o700)
        for name,raw in programs.items():c.save(root/'programs'/f'{name}.py',raw,131072,budget.tick,budget.write);c.readable(root/'programs'/f'{name}.py',budget.tick)
        # Both sources captured before any numeric input authentication/exposure.
        public,plan,stamps=input_metadata(s,budget)
        commitment=dict(schema='neural089-commitment-v1',source=source,programs=pins,public_manifest=s['public_manifest'],image=s['image'],plan=s['plan'],limits=s['limits'],private_grading_authorized=False)
        cp=c.save(root/'COMMITMENT.json',c.encoded(commitment),65536,budget.tick,budget.write)
        trusted=root/'trusted';trusted.mkdir(mode=0o700)
        for name in ('holder.py','candidate_entry.py'):c.save(trusted/name,bodies['transport/'+name],100000,budget.tick,budget.write);c.readable(trusted/name,budget.tick)
        os.chmod(trusted,0o555);c.sync_dir(trusted,budget.tick)
        (root/'phases').mkdir(mode=0o700);(root/'models').mkdir(mode=0o700)
        values={name:{} for name in packet.PANELS}
        for phase in packet.phases(public,plan):
            last=phase;entered+=1;native_reserved=False;native_phase_call_attempted=False;budget.tick();d=root/'phases'/phase['phase_id'];d.mkdir(mode=0o700)
            model=None if phase['model_key']is None else models[phase['model_key']]
            if model is not None:c.need(c.stamp(model['path'].lstat())==model['stamp'],'same sealed model before exposure')
            if phase['kind']=='infer' and phase['arm']!='PRIOR':
                querypath=plan['query_by_id'][phase['case_id']]['run']['features']['path'];c.need(c.stamp((c.path(s['public_root'])/querypath).lstat())==stamps[querypath],'query source remains whole-file authenticated before extent access')
            current=root/'current';expected=packet.view(current,c.path(s['public_root']),public,phase,budget,plan);viewstamps=packet.verify_view(current,expected,budget)
            request=dict(schema='neural089-phase-request-v1',source=source,phase=phase,program=pins[phase['panel']],image=s['image'],seconds=s[phase['kind']+'_seconds'],model=None if model is None else model['pin'],input=expected['INPUT.json'],view_members=c.pin(c.encoded(expected)))
            rp=c.save(d/'REQUEST.json',c.encoded(request),65536,budget.tick,budget.write)
            budget.native(phase['kind'],phase['ordinal']);native_reserved=True
            native_phase_call_attempted=True
            result=native.phase(s,trusted,current,root/'programs'/f"{phase['panel']}.py",None if model is None else model['path'],d,phase['kind'],phase['ordinal'],source,budget,worker_end)
            c.need(result['status']=='captured' and result['all_native_resources_closed']is True,'full native closure before output')
            if model is not None:c.need(c.stamp(model['path'].lstat())==model['stamp'],'same sealed model after exposure')
            packet.retire(current,expected,viewstamps,budget);current=None
            npin=c.pin(c.capture(d/'NATIVE.json',packet.NATIVE_CAP,None,budget.tick,budget.read));created=None
            if phase['kind']=='fit':
                target=root/'models'/f"{phase['phase_id']}.bin";os.rename(d/'model.bin',target);c.readable(target,budget.tick)
                pin=result['output'];c.capture(target,packet.MODEL_CAP,pin,budget.tick,budget.read);stamp=c.stamp(target.lstat())
                models[phase['result_key']]=dict(path=target,pin=pin,stamp=stamp);created=dict(key=phase['result_key'],pin=pin)
                seal=dict(schema='neural089-model-seal-v1',source=source,phase=phase,program=pins[phase['panel']],input_model=request['model'],model=pin,native=npin,input=request['input'],view_retired=True)
                c.save(d/'MODEL_SEAL.json',c.encoded(seal),65536,budget.tick,budget.write)
            else:
                raw=c.capture(d/'prediction.json',packet.PRED_CAP,result['output'],budget.tick,budget.read);prob=outputs.prediction(raw,phase)
                ids=[q['id'] for q in plan['queries']] if phase['arm']=='PRIOR' else [phase['case_id']]
                for q in ids:values[phase['panel']][(phase['arm'],q)]=prob
            closed=dict(schema='neural089-phase-closed-v1',phase=phase,request=rp,native=npin,model=created,view_retired=True)
            c.save(d/'CLOSED.json',c.encoded(closed),65536,budget.tick,budget.write);completed+=1
        c.need(completed==s['limits']['phase_count'] and len(models)==6,'complete full scope')
        panelpins={}
        for panel in packet.PANELS:panelpins[panel]=c.save(root/f'{panel}.json',c.encoded(outputs.assemble(public,values[panel])),packet.OUTPUT_CAP,budget.tick,budget.write)
        for model in models.values():c.capture(model['path'],packet.MODEL_CAP,model['pin'],budget.tick,budget.read)
        unchanged_inputs(s,plan,stamps,budget)
        complete=dict(schema='neural089-complete-v1',status='complete_unqualified',source=source,commitment=cp,phase_count=completed,model_count=6,panels=panelpins,all_views_retired=True,private_targets_opened=False,scoring_performed=False,runtime_qualified=False,scientific_qualified=False,costs=budget.record())
        pin=c.save(root/'COMPLETE.json',c.encoded(complete),packet.JSON_CAP,budget.tick,budget.write);budget.tick()
        return dict(schema='neural089-worker-result-v1',status='complete_unqualified',source=source,complete=pin,phase_count=completed)
    except BaseException as exc:
        failure=dict(schema='neural089-failure-v1',source=source,last_phase=last,completed_phases=completed,expected_phases=s['limits']['phase_count'],entered_incomplete_phases=entered-completed,unentered_phases=s['limits']['phase_count']-entered,last_phase_native_reserved=native_reserved,last_phase_native_call_attempted=native_phase_call_attempted,phase_call_is_not_proof_of_created_native_resource=True,models_sealed=len(models),current_view_may_remain=current is not None,automatic_retry=False,native_recovery_may_be_required=True,error_type=type(exc).__name__,costs=budget.record())
        try:c.save(root/'FAILURE.json',c.encoded(failure),packet.JSON_CAP,budget.tick,budget.write)
        except BaseException:pass
        raise
