"""Complete source-owned dispatch. Deployment is explicitly unconfigured."""
from pathlib import Path
import copy,os,time
from .io import need,decode,digest,sha,capture,ordinary,Budget,encode
from .source import ROOT,SOURCE_LOCK,TASKS,FULL,paper,neural,inspect
from .plan import construct,paired_access
from .exposure import Ledger
from . import adapters,comparisons

def descriptor(value,budget,cap=8<<20):
    need(set(value)=={'path','bytes','sha256'},'exact input descriptor')
    return budget.read(value['path'],value,cap)

def event(ledger,setup,job,episode,role,animals):
    return ledger.append({'actor_lineage':job['actor_lineage'],'episode':episode,'canonical_task':setup['task'],
        'corpus_key':setup['corpus_key'],'source_assets_and_transforms':[setup['binding']['asset_manifest_sha256'],*setup['binding']['views'].values()],
        'visible_modalities':job['visible_modalities'],'time_ranges':job['time_ranges'],
        'paper_results_seen':role in ('paper_reproduction','paper_results'),'code_results_or_constants_seen':job.get('ordinary_author_code_seen',False),
        'role':role,'animals':sorted(set(animals)),'timestamp':time.time()})

def validate_jobs(setup,jobs):
    slots={s['id']:s for s in setup['slots']}
    need(set(jobs)==set(slots),'all default/named programme slots must be accounted for')
    for key,j in jobs.items():
        need(j['status'] in ('available','source_unavailable','structurally_inapplicable'),'job support status')
        intrinsic=slots[key].get('applicability','applicable')
        if intrinsic.startswith('structurally_inapplicable'):
            need(j['status']=='structurally_inapplicable','structural permission cannot be overridden')
        if j['status']!='available':
            need(isinstance(j.get('reason'),str) and j['reason'] and j.get('support_receipt_sha256'),'explicit missing-source obligation')
        else:
            need(intrinsic=='applicable','unavailable population cannot be invented')
            need(j['actor_lineage'] and j['claim_lane'] in ('exploratory','protected','confirmatory'),'trusted actor/claim binding')
    return slots

def run(setup,request,root,budget,ledger):
    """Dispatch every supplied full slot; no missing obligation is called success."""
    need(request['mode']=='engineering' and setup['binding']['synthetic'] is True,'source-only deployment: invented engineering only')
    slots=validate_jobs(setup,request['jobs']);results={};available=[]
    for key,slot in slots.items():
        j=request['jobs'][key]
        if j['status']!='available':results[key]={'status':j['status'],'reason':j['reason'],'required_unscorable':True};continue
        comparisons.resources(j,budget)
        if slot.get('kind')=='neural_numeric' and slot.get('mode')=='F':comparisons.terminal_resources(j,budget)
        available.append((key,dict(slot,task=setup['task']),j))
    if setup['task']==TASKS[0]:
        paired_access(request['paired_access'])
        need(request['scoring_source_lock_sha256']==sha(capture(ROOT/SOURCE_LOCK)),'actual registered scoring source')
        evaluation_banks=comparisons.paper_banks(setup,request,available)
        public_views={}
        for key,slot,j in available:
            view=decode(descriptor(j['public'],budget))
            need(view['engineering_only'] is True,'invented public inputs')
            need(view['access_contract_sha256']==digest(request['paired_access'][slot['arm']]),'actual public view binds paired access contract')
            comparisons.paper_public(view,evaluation_banks[slot['mode']])
            public_views[key]=view
        for key,slot,j in available:
            budget.guard(root);context=request['paired_access'][slot['arm']]
            need(j['claim_lane']=='exploratory','current public-paper corpus improvement/reproduction is exploratory')
            need(context['actor_lineage']==j['actor_lineage'],'paired actor lineage')
            need(j.get('ordinary_author_code_seen',False)==bool(context['ordinary_author_code']),'paired actual code-view declaration')
            ledger.check(j['actor_lineage'],setup['corpus_key'],j['animals'],j['claim_lane'],'paper_reproduction' if slot['mode']=='reproduction' else 'query_release')
            public=copy.deepcopy(public_views[key])
            need(public['access_contract_sha256']==digest(context),'actual public view binds paired access contract')
            comparisons.paper_public(public,evaluation_banks[slot['mode']])
            event(ledger,setup,j,key,'paper_reproduction' if slot['mode']=='reproduction' else 'query_release',j['animals'])
            if slot['mode']=='improvement':event(ledger,setup,j,key,'paper_results',j['animals'])
            output=root/sha(key.encode());output.mkdir()
            visible=[]
            # Captured public bytes are actually staged. A has no author-code
            # files; B receives only exact ordinary source pins from the design.
            for group in ('paper_pins','data_pins','ordinary_author_code'):
                for i,p in enumerate(context[group]):
                    raw=descriptor(p,budget);dest=root/(sha(key.encode())+'-public')/group/str(i)
                    visible.append(dict(budget.write_raw(dest,raw),role=group))
            public=copy.deepcopy(public);public['staged_access_files']=visible
            def private_factory(j=j,key=key,slot=slot):
                event(ledger,setup,j,key,'query_target',j['animals'])
                value=comparisons.paper_private(decode(descriptor(j['private'],budget)),j,slot['mode'])
                population={a['id']:(c,a) for c,r in setup['condition_registry'].items() for a in r['animals']}
                if slot['mode']=='improvement':
                    expected=value['support_manifest']['source_inventory']['populations']['expected_animals_by_endpoint_condition']
                    need(set().union(*(set(v) for v in expected.values()))==set(population),'paper/neural shared biological population join')
                    for ep_cond,ids in expected.items():
                        ep,condition=ep_cond.split(':',1)
                        need(all(population[a][0]==condition for a in ids),'paper condition identity join')
                    for r in value['support_manifest']['records']:
                        need(r['behavior_only_designated']==(not population[r['animal_id']][1]['neural_designated']),'shared modality designation')
                else:
                    for r in value['reference']:
                        co=r.get('cohort_manifest',{})
                        if co.get('unit')=='animal':
                            need(all(m['unit_id'] in population and population[m['unit_id']][0]==m['condition'] for m in co['members']),
                                 'native/reproduced biological cohorts join the common registry')
                return value
            budget.reserve_time(j['timeout_seconds'])
            result=adapters.paper_engineering(j,slot,output,public,private_factory,j['source_commit'],request.get('engineering_bootstrap',20))
            results[key]=result;budget.guard(root)
    else:
        numerical=[x for x in available if x[1]['kind']=='neural_numeric'];packets=[x for x in available if x[1]['kind']=='packet']
        # No numerical model fits are authorized by this BUILD ONLY deployment.
        # Exact full fit/model families remain reachable in the accepted adapter
        # and are required for future qualified execution, never replaced by P.
        for key,slot,j in numerical:
            if setup['task']=='NEURAL-046':need(not neural('contracts').available_models(slot['cell_id']),'model fitting paused; full comparator remains required-unscorable')
        if numerical:
            candidate_numerical=list(numerical)
            extra,reference_obligations,reference_links=comparisons.references(numerical,budget)
            numerical=numerical+extra
            ids={key:'job_'+str(i) for i,(key,_,_) in enumerate(numerical)}
            plan={'synthetic':True,'jobs':list(ids.values()),'programs':{},'terminal_routines':{},'model_tools':{},'reference_jobs':{},'reference_roles':{}}
            for key,slot,j in numerical:
                body=descriptor(j['program'],budget,131072)
                plan['programs'][ids[key]]=sha(body) if slot['mode']=='F' else None
                if slot['mode']=='F':plan['terminal_routines'][ids[key]]=j['terminal_routine']
                if slot['tier']=='XM':plan['model_tools'][ids[key]]=j['model_tool']
            for candidate,families in reference_links.items():
                for family,reference in families.items():
                    plan['reference_roles'][ids[reference]]=family
                if 'R0' in families:plan['reference_jobs'][ids[candidate]]=ids[families['R0']]
            engine=adapters.Numerical(root/'numerical',plan) # F interpretation is copied here, before corpus/bank reads.
            staged={};cache={};prepared_jobs={}
            for key,slot,j in numerical:
                need(j['corpus']['sha256']==setup['binding']['views']['neural'],'same corpus neural export view')
                if j['corpus']['sha256'] not in cache:cache[j['corpus']['sha256']]=decode(descriptor(j['corpus'],budget))
                corpus=cache[j['corpus']['sha256']];need(corpus['synthetic'] is True,'invented neural export')
                registry={a['id']:(condition,a) for condition,r in setup['condition_registry'].items() for a in r['animals']}
                for a in corpus['animals']:
                    need(a['id'] in registry and registry[a['id']][0]==a['condition'] and
                         set(registry[a['id']][1]['aliases'])==set(a['aliases']),'shared biological source alias join')
                prepared=adapters.prepare_neural(corpus,slot,j.get('source_prior'),j.get('seed',0))
                prepared_jobs[key]=prepared
                if 'reference_registration' in j:
                    parent=key.rsplit('/reference/',1)[0]
                    comparisons.reference_join(prepared_jobs[parent],prepared)
                train=set(prepared['training_animals']);query={r['animal'] for r in prepared['private']}
                ledger.check(j['actor_lineage'],setup['corpus_key'],query,j['claim_lane'],'query_release')
                ledger.check_training_release(j['actor_lineage'],setup['corpus_key'],train,j['claim_lane'])
                event(ledger,setup,j,key,'training',train);event(ledger,setup,j,key,'query_release',query)
                engine.stage(ids[key],prepared['public'],prepared['private']);staged[key]=(query,j)
                budget.guard(root)
            for key,slot,j in numerical:
                budget.guard(root);budget.reserve_time(j['timeout_seconds']);need(engine.produce(ids[key],j['program']['path'],j['timeout_seconds'],j['output_cap_bytes'])=='sealed','original neural producer did not seal');budget.guard(root)
            # Persist target-exposure entries before the one-shot grader opens targets.
            for key,(query,j) in staged.items():event(ledger,setup,j,key,'query_target',query)
            closed=engine.close_and_grade();reports={}
            for key,slot,j in numerical:
                if slot['mode']=='I':
                    packet_path=engine.workflow.root/'interpretation_packets.json'
                    bank=decode(budget.read(packet_path));packet=bank[ids[key]]
                    folder=root/('I-report-'+ids[key]);folder.mkdir();budget.write(folder/'input.json',packet)
                    descriptor(j['interactive_report_program'],budget,131072)
                    budget.reserve_time(j['timeout_seconds'])
                    receipt=neural('workflow').run_engineering_producer(j['interactive_report_program']['path'],folder/'input.json',folder/'outputs',j['timeout_seconds'],j['output_cap_bytes'])
                    commitment={'source_sha256':j['interactive_report_program']['sha256'],'output_cap_bytes':j['output_cap_bytes']}
                    reports[ids[key]]=neural('terminal').collect_result(folder,receipt,commitment,packet)
            for key,slot,j in numerical:
                if slot['mode']=='F':
                    selected=comparisons.terminal_resources(j,budget)
                    actual=engine.workflow._state()['terminal_routines'][ids[key]]
                    need(all(actual[k]==v for k,v in selected.items() if k!='source_path'),'F terminal committed allowance changed')
            budget.reserve_time(sum(j['terminal_routine']['timeout_seconds'] for _,s,j in numerical if s['mode']=='F'))
            final=engine.finish(reports)
            for key,slot,j in candidate_numerical:
                results[key]={'status':'engineering_collected','closed_result':closed[ids[key]],'interpretation':final[ids[key]],'scientific_qualification':False}
                if setup['task']=='NEURAL-045':
                    results[key]['reference_comparison']=comparisons.reference_summary(key,closed,reference_links,ids,reference_obligations)
                    results[key]['required_primary_unscorable']=results[key]['reference_comparison']['primary_status']=='required_unscorable'
                    results[key]['required_reference_unscorable']=results[key]['reference_comparison']['any_mandatory_reference_unscorable']
        for key,slot,j in packets:
            budget.guard(root);ledger.check(j['actor_lineage'],setup['corpus_key'],j['animals'],j['claim_lane'],'closed_interpretation')
            initial=descriptor(j['policy'],budget,16384) if slot['mode']=='F' else None
            engine=adapters.PacketBank(root/sha(key.encode()),setup['task'],slot['cell_id'],j['bank_schema_id'],initial)
            packet_values=decode(descriptor(j['packets'],budget));event(ledger,setup,j,key,'closed_interpretation',j['animals']);engine.release(packet_values)
            if slot['mode']=='I':
                need(set(j['policies'])==set(engine.packets),'all interactive packet policies')
                for ident,p in j['policies'].items():engine.commit_I(ident,descriptor(p,budget,16384))
            def rubrics(j=j):return decode(descriptor(j['rubrics'],budget))
            results[key]={'status':'packet_interpretation_only','result':engine.grade_once(rubrics),'canonical_primary_complete':False};budget.guard(root)
    return {'schema':'reward_full_central_collection_v1','task':setup['task'],'condition':setup['condition'],
        'setup_digest':digest(setup),'results':results,'required_slots':len(slots),'accounted_slots':len(results),
        'available_slots':len(available),'source_unscorable_slots':sum(r.get('required_unscorable',False) for r in results.values()),
        'full_scientific_completion':False,'scientific_qualification':False,'submission_ready':False,'independent_corpora':1}

def execute(action,task,condition,request_path,output,review_path,reserve,expected,started=None,cpu=None,bootstrap_bytes=0):
    started=started or time.monotonic();review=decode(capture(review_path,cap=32768))
    need(review['schema']=='reward_central_execution_review_v1' and review['task']==task and review['source']==expected,'exact task/source review')
    budget=Budget(review['limits'],started,cpu);budget.reads+=bootstrap_bytes
    budget.read(review_path,cap=32768);source=inspect(expected,budget)
    request=decode(budget.read(request_path,review['request']));need(request['task']==task,'request task')
    need(review['condition']==(condition or FULL),'reviewed named/default condition')
    need(review['not_before']<=time.time()<review['expires'],'review time window')
    need(type(reserve) is int and reserve>=0,'external storage reservation')
    out=ordinary(output,False);need(not out.exists() and out.parent.is_dir() and str(out)==review['output'],'fresh exact approved output')
    need(request['mode']=='engineering' and review['engineering_only'] is True,'deployment unconfigured; no scientific execution')
    setup=construct(task,condition,request['registry'],request['binding']);need(setup['binding']['synthetic'] is True,'invented phase only')
    need(digest(setup)==review['setup_digest'],'full programme setup binding')
    policy=decode(capture(ROOT/'POLICY.json'));need(policy['scientific_execution_enabled'] is False,'source-only policy')
    disk=os.statvfs(out.parent);need(budget.limits['retained_bytes']+reserve<=disk.f_bavail*disk.f_frsize,'whole attempt storage reservation')
    out.mkdir(mode=0o700);rootid=(out.stat().st_dev,out.stat().st_ino);failure=None;result=None
    try:
        budget.write(out/'SETUP.json',setup);budget.write(out/'REVIEW.json',review)
        if action=='prepare':result={'status':'complete_source_setup','setup_digest':digest(setup),'execution_started':False}
        else:
            ledger=Ledger(review['exposure_ledger']['path'],review['exposure_ledger']['identity'])
            result=run(setup,request,out,budget,ledger)
        budget.guard(out);need((out.stat().st_dev,out.stat().st_ino)==rootid,'output generation preserved')
    except BaseException as e:
        failure={'type':type(e).__name__,'reason':str(e)}
    envelope={'source':expected,'task':task,'condition':condition or FULL,'result':result,'failure':failure,
        'cost':budget.snapshot(),'deployment':'unconfigured','scientific_qualification':False,'submission_ready':False}
    # Failure evidence is retained outside the ordinary budget claim if the cap
    # is already exhausted; no failed run is relabelled a pass by finalization.
    try:
        budget.write(out/'RESULT.json',envelope);budget.guard(out)
    except BaseException as final_error:
        if failure is None:envelope['failure']={'type':type(final_error).__name__,'reason':str(final_error)}
        envelope['finalization_failure']={'type':type(final_error).__name__,'reason':str(final_error)}
        path=out/'FINALIZATION_FAILURE.json'
        if not path.exists():path.write_bytes(encode(envelope))
    return envelope
