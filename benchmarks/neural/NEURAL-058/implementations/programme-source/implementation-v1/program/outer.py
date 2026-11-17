"""Independent original-stream observer and full public-artifact re-admission."""
from pathlib import Path
from core import need,capture,capture_new_protected,parse,pin,encoded,fresh,publish
from journal import decode
from admission import admit
from engine import Engine


def run(request,budget,frozen):
    need(request.get('schema')=='neural058_outer_selection_v1' and request.get('task')=='NEURAL-058'
         and request.get('selected') is True,'separately selected external caller')
    raw,_=capture(request['production']['path'],request['production']['pin'],4<<20,budget,readonly=True)
    selection=parse(raw)
    need(selection['origin']==budget.origin and selection['source']==frozen['pin']
         and selection['deadline']==request['normal_end']
         and budget.origin<selection['deadline']<request['cleanup_end']<budget.deadline,
         'same origin and original production/cleanup/readback cutoffs')
    need(request['observation_root']==selection['roots']['observation'],'exact disjoint observation namespace')
    bootstrap=frozen['manifest']['files']['program/bootstrap.py']
    argv=[request['python'],'-I',str(Path(selection['roots']['source'])/'program/entry.py'),
          '--mode','collect','--source-root',selection['roots']['source'],
          '--manifest',selection['source_manifest_path'],'--manifest-pin',encoded(frozen['pin']).decode(),
          '--bootstrap-pin',encoded(bootstrap).decode(),'--request',request['production']['path'],
          '--request-pin',encoded(request['production']['pin']).decode(),'--origin',str(selection['origin']),
          '--deadline',str(selection['deadline']),'--read-cap',str(selection['limits']['read_bytes']),
          '--write-cap',str(selection['limits']['write_bytes'])]
    need(argv==request['literal_collect_argv'],'qualified literal original child command')
    # Qualified root evidence binds this observer and its exact command/env/cwd
    # and whole metadata readback allowance, before any child is created.
    proof_raw,_=capture(request['qualification']['path'],request['qualification']['pin'],262144,budget,readonly=True)
    proof=parse(proof_raw)
    need(proof.get('schema')=='neural058_outer_qualification_v1' and proof.get('admitted') is True and proof.get('independent_operator') is True
         and proof.get('source')==frozen['pin'] and proof.get('selection')==pin(encoded({k:v for k,v in request.items() if k!='qualification'})),
         'independent exact original caller/environment/resource authority')
    need(budget.origin<=proof['observed']<=budget.tick()<proof['valid_until']<=budget.deadline,
         'fresh nonfuture observer qualification on the original operation clock')
    root=fresh(request['observation_root'],budget)
    from caller_observer import run as call,CAP,CHUNK
    budget.reserve_read(2*(CAP+CHUNK));budget.reserve_write(2*CAP)
    bundle=None;failure=None
    try:
        bundle=call(argv,request['normal_end'],request['cleanup_end'],request['environment'],request['cwd'])
        caller=bundle['record'];need(caller['successful_observation'] is True,'natural zero/EOF/group closure')
        stream_pins={k:publish(root/(k+'.bin'),bundle[k],budget,readonly=True) for k in ('stdout','stderr')}
        lines=bundle['stdout'].splitlines();need(len(lines)==1,'exact single final production terminal')
        terminal=parse(lines[0]);need(terminal.get('schema')=='neural058_entry_terminal_v1'
                 and terminal.get('status')=='complete' and terminal.get('mode')=='collect'
                 and terminal['source']==frozen['pin'],'exact actual entry completion')
        result=terminal['result'];need(result['output']==selection['roots']['output'],'same qualified output root')
        output=Path(result['output'])
        complete_raw,_=capture(output/'COMPLETE.json',result['complete'],selection['limits']['complete_metadata_bytes'],budget,readonly=True)
        complete=parse(complete_raw)
        journal_raw,journal_pin=capture_new_protected(output/'JOURNAL.jsonl',selection['limits']['journal_bytes'],budget)
        events,chain=decode(journal_raw,event_cap=selection['limits']['journal_event_bytes'])
        graph=admit(complete,events,selection,frozen['pin'])
        from projection_admission import verify
        projections=verify(complete,events,selection,frozen,budget)
        # Reauthenticate every actual artifact, including both original bundles
        # and extracted members. This duplication is charged, never treated free.
        inspected=[]
        checker=Engine(selection['engine'],budget,lambda e:None)
        for operation,product in complete['products'].items():
            budget.tick()
            native=product['native'];native_root=Path(native['output'])
            need(Path(selection['roots']['output']) in native_root.parents,'actual native output stays in selected namespace')
            for name,d in native['artifacts'].items():capture(native_root/name,d,d['bytes'],budget,retain=False,readonly=True)
            derived_root=Path(product['root'])
            need(Path(selection['roots']['output']) in derived_root.parents,'derived output stays in selected namespace')
            for row in product['derived']['members']:
                from core import relative
                capture(derived_root/relative(row['path']),row['pin'],row['pin']['bytes'],budget,retain=False,readonly=True)
            _,absence=checker.request('GET','/containers/'+checker.container_id(native['container'])+'/json',None,
                                     budget.deadline,statuses=(404,),limit=65536)
            inspected.append({'operation':operation,'container':native['container'],'absence_status':404,
                              'response':pin(absence),'observed':budget.tick()})
        observation={'schema':'neural058_external_observation_v1','task':'NEURAL-058','source':frozen['pin'],
                     'production':request['production'],'complete':result['complete'],'journal':journal_pin,
                     'stream_pins':stream_pins,'caller':caller,'graph':graph,'projection_admission':projections,'chain':chain,
                     'independent_container_absence':inspected,'protected_targets_read':False,
                     'semantic_qualification_pending':True,'actual_reference_competence_not_established':True,
                     'budget_before_publication':budget.record(),
                     'provisional_until_root_observes_this_observer_natural_zero_and_EOF':True}
        body=encoded(observation);need(len(body)<=request['observation_metadata_bytes'],'full external metadata cap')
        d=publish(root/'OBSERVATION.json',body,budget,readonly=True);budget.tick()
        return {'observation':d,'root':str(root),'provisional':True}
    except BaseException as error:
        if bundle is None:bundle=getattr(error,'bundle',None)
        failure={'task':'NEURAL-058','external_observation_complete':False,'first_failure_type':type(error).__name__,
                 'caller':None if bundle is None else bundle['record'],
                 'original_streams_observed':None if bundle is None else {k:len(bundle[k]) for k in ('stdout','stderr')},
                 'read_reserved_bytes':budget.read_bytes,'write_reserved_bytes':budget.write_bytes,
                 'persistent_streams_complete':False,'hold_release_eligible':False}
        if bundle is not None:
            try:
                # Separate failure filenames cannot replace successful originals.
                failure['stream_pins']={k:publish(root/('failure-'+k+'.bin'),bundle[k],budget,readonly=True) for k in ('stdout','stderr')}
                failure['persistent_streams_complete']=True
            except BaseException as later:
                failure['persistence_failure_type']=type(later).__name__
                combined=BaseExceptionGroup('observer first failure and stream persistence failure',[error,later])
                combined.failure_record=failure;raise combined from None
        error.failure_record=failure;raise
