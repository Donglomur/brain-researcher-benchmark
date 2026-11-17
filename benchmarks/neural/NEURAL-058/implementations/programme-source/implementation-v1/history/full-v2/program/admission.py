"""Independent complete producer/role/state/clock graph admission before truth."""
from core import need,encoded,pin,finite,integer
from schedule import panels,author_contexts,candidate_sessions,reference_selection,final_models,final_reference_sessions,required_counts
from journal import closure
from ordering import sessions


def authenticate_product(product):
    members=product['derived']['members']
    names=[r['path'] for r in members]
    need(len(names)==len(set(names)) and names.count('RESULT.json')==1,'unique complete derived RESULT.json')
    result=next(r['pin'] for r in members if r['path']=='RESULT.json')
    need(result==product['result_pin']==pin(encoded(product['result'])), 'embedded result exact canonical closed bytes')
    need(product['native']['artifacts']['TERMINAL.json']==pin(encoded(product['terminal'])),
         'embedded terminal exact canonical closed bytes')
    need(product['terminal']['result']=={'path':'RESULT.json','pin':result},'terminal result belongs to unique closed member')
    return True


def admit(complete,events,selection,source):
    need(complete.get('schema')=='neural058_production_complete_v1' and complete.get('task')=='NEURAL-058', 'complete task source result')
    need(complete['selection']==pin(encoded(selection)) and complete['source']==source
         and complete['prepared']==selection['prepared'],'exact source/selection/packet chain')
    need(complete['protected_targets_read'] is False and complete['scientifically_qualified'] is False,
         'production is public-only and not self-qualified science')
    for product in complete['products'].values():authenticate_product(product)
    roster=complete['roster'];choices=complete['reference_selection']['choices']
    counts=required_counts(roster,choices);need(complete['counts']==counts,'actual full task counts')
    expected_panels={p['id'] for p in panels()}
    need(set(complete['completed_panels'])==expected_panels and len(complete['completed_panels'])==24,'all24 exactly once')
    methods={a['id']:a for p in panels() for a in author_contexts(roster,p)}
    outputs={r['panel']+'/'+r['session']:r for p in panels() for r in candidate_sessions(roster,p)}
    cv={s['role']+'/'+s['config']['id']+'/'+str(s['fold']):s for s in reference_selection(roster)}
    models={s['role']+'/'+s['config']['id']:s for s in final_models(choices)}
    reference_outputs={s['role']+'/'+s['model'].split('/')[-1]+'/'+s['session']:s for s in final_reference_sessions(roster,choices)}
    for name,expected in (('methods',methods),('candidate_fits',methods),('candidate_outputs',outputs),
                          ('reference_cv',cv),('reference_models',models),('reference_predictions',reference_outputs)):
        need(set(complete[name])==set(expected),'complete exact '+name+' membership')
    products=complete['products'];need(products and all(p['status']=='complete' for p in products.values()),'no failed/unknown producer hidden')
    # Reuse the proven event-chain checks, supplying actual donor phase/episode
    # sets as empty because task-specific graph membership is checked here.
    closed=closure(events,[],[],selection['origin'],selection['deadline'])
    intents={};finished={};task_products={};method_events={};scopes={};panel_finishes={};source_selection=[]
    for i,e in enumerate(events):
        k=e['kind']
        if k=='native_intent': need(e['operation'] not in intents,'one intention');intents[e['operation']]=(i,e)
        elif k=='native_completed':need(e['operation'] not in finished,'one native completion');finished[e['operation']]=(i,e)
        elif k=='task_product':need(e['operation'] not in task_products,'one derived product');task_products[e['operation']]=(i,e)
        elif k=='method_sealed':need(e['identity'] not in method_events,'one sealed method');method_events[e['identity']]=(i,e)
        elif k=='scope_started':need(e['identity'] not in scopes,'one whole-panel scope');scopes[e['identity']]=e
        elif k=='panel_completed':need(e['panel']['id'] not in panel_finishes,'one whole-panel completion');panel_finishes[e['panel']['id']]=e
        elif k=='source_reference_selection':source_selection.append((i,e))
        elif k in ('campaign_failed','scope_failed','panel_failed'):raise ValueError('failed whole graph')
    need(set(intents)==set(finished)==set(task_products)==set(products),'every actual operation naturally closed and derived once')
    need(set(method_events)==set(methods) and set(scopes)==set(panel_finishes)==expected_panels,'all author and whole-panel scope evidence')
    need(len(source_selection)==1 and source_selection[0][1]['selection']==complete['reference_selection'],'one exact source-only selection')
    from reference_selection import choose
    replay={}
    for key,spec in cv.items():
        r=products[complete['reference_cv'][key]]['result']
        expected_animals={roster['source'][sid]['animal'] for sid in spec['validation_sessions']}
        need(set(r['animals'])==expected_animals and [x['session'] for x in r['predictions']]==spec['validation_sessions'],
             'all and only complete source-fold animal/output scores')
        replay[(spec['role'],spec['config']['id'],spec['fold'])]=r
    need(choose(replay,roster['source_animals'])==complete['reference_selection'],'independent deterministic source-only selection replay')
    for operation,product in products.items():
        _,intent=intents[operation];_,done=finished[operation];_,derived=task_products[operation]
        need(product['native']==done and product['request']==derived['request']
             and product['result_pin']==derived['result'],'closed actual producer/result identity')
        need(product['envelope']['source']==source and product['envelope']['origin']==selection['origin'], 'same original native source clock')
        need(product['result']['request']==pin(encoded(product['envelope']['request'])),'exact inner result request')
        need(product['request']==pin(encoded(product['envelope']))
             and product['terminal']['request']==product['request']
             and product['terminal']['source']==source and product['terminal']['producer']==product['envelope']['producer']
             and product['terminal']['result']=={'path':'RESULT.json','pin':product['result_pin']}
             and product['derived']['members']==derived['derived_members']
             and done['config']==intent['config'] and done['source']==source,'exact closed envelope/result/source chain')
        need(done['natural_exit'] is True and type(done['exit_code'])is int and done['exit_code']==0,'ordinary natural zero exit')
        scope=intent['candidate_scope']
        enclosing=selection['deadline'] if scope is None else scopes[scope]['cutoff']
        retirement=done['retirement'];limit=min(enclosing,intent['cutoff']+finite(intent['limits']['retirement_seconds']))
        need(retirement.get('removed') is True and retirement.get('absence_confirmed') is True
             and retirement.get('successful_clock_custody') is True and not retirement.get('unknown_state',False), 'complete native custody')
        need(retirement['cutoff']==limit and selection['origin']<=intent['started']<=done['observed_end']<intent['cutoff']
             and done['observed_end']<=done['retired_at']<limit,'exact execution/retirement order and original limits')
        cpu=integer(done['cpu_ns']);need(cpu<=integer(intent['limits']['cpu_ns'],1),'final actual CPU allowance')
        need(set(done['artifacts'])=={'RESULT.n058','TERMINAL.json'},'exact fixed native result transport')
        need(product['terminal']['bundle']==done['artifacts']['RESULT.n058']
             and product['derived']['source_bundle']==done['artifacts']['RESULT.n058'],'native/decoded bundle identity')
        need(intents[operation][0]<finished[operation][0]<task_products[operation][0],'natural then derived order')
    for key,spec in cv.items():
        op=complete['reference_cv'][key];p=products[op];r=p['envelope']['request']
        need(op==spec['id'] and p['envelope']['producer']=='reference' and r['operation']=='fit'
             and r['role']==spec['role'] and r['fold']==spec['fold'] and r['config']==spec['config'],'exact full CV schedule')
        need([x['session'] for x in r['training']]==spec['training_sessions']
             and [x['session'] for x in r['validation']]==spec['validation_sessions'],'all source training/OOF sessions')
        need(task_products[op][0]<source_selection[0][0],'all OOF results before source selection')
    for key,spec in models.items():
        op=complete['reference_models'][key];p=products[op];r=p['envelope']['request']
        need(op==spec['id'] and r['operation']=='fit' and r['fold']=='full' and r['config']==spec['config']
             and r['role']==spec['role'] and [x['session'] for x in r['training']]==sessions(roster,'source'), 'complete selected full-source refit')
        need(source_selection[0][0]<intents[op][0],'source selection precedes final fit')
    for key,spec in reference_outputs.items():
        op=complete['reference_predictions'][key];p=products[op];r=p['envelope']['request'];model_key=spec['role']+'/'+spec['model'].split('/')[-1]
        model=products[complete['reference_models'][model_key]]
        need(op==spec['id'] and r['operation']=='predict' and r['model']==model['result']['model']
             and r['role']==spec['role'] and [x['session'] for x in r['evaluation']]==[spec['session']], 'exact independently trained reference prediction')
    from optional_admission import treatment,analysis as admit_analysis,features as admit_features,numeric_bridge
    numeric_keys=[]
    need(set(complete['numeric_slots'])=={r['id'] for r in outputs.values()},'every inference has an explicit numeric-slot ledger')
    for identity,spec in methods.items():
        record=complete['methods'][identity];event=method_events[identity][1]
        need(all(event[k]==v for k,v in record.items()),'sealed method body and transcript binding')
        need(set(complete['author_transcripts'])==set(methods)
             and pin(encoded(complete['author_transcripts'][identity]))==record['transcript'], 'complete actual isolated author transcript')
        op=complete['candidate_fits'][identity];p=products[op];r=p['envelope']['request']
        need(r['stage']=='fit' and r['program']['pin']==record['program']['pin']
             and r['panel']==spec['panel'] and r['animal']==spec['animal']
             and r['mode']==spec['panel'].split('/')[0] and r['role']==spec['panel'].split('/')[1]
             and r['tool']==spec['panel'].split('/')[2],'own actual sealed-method fit')
        treatment(r,spec['panel'],spec['animal'])
        need(r['recipe']==record['recipe'],'actual own sealed fit recipe')
        need(method_events[identity][0]<intents[op][0],'seal precedes final fit')
        need([x['session'] for x in r['training']]==sessions(roster,'source'),'all candidate source training sessions')
        expected=[] if spec['animal']=='global' else spec['evaluation_sessions']
        need([x['session'] for x in r['evaluation']]==expected,'author-specific held-input boundary')
    for key,spec in outputs.items():
        op=complete['candidate_outputs'][key];p=products[op];r=p['envelope']['request']
        method=complete['methods'][spec['author']];fit=products[complete['candidate_fits'][spec['author']]]
        need(op==spec['id'] and r['stage']=='infer' and r['panel']==spec['panel']
             and r['current_session']==spec['session'] and r['animal']==spec['animal']
             and r['mode']==spec['panel'].split('/')[0] and r['role']==spec['panel'].split('/')[1]
             and r['tool']==spec['panel'].split('/')[2],'complete candidate output schedule')
        need(r['program']['pin']==method['program']['pin'] and r['state']==fit['result']['state']
             and not r['training'],'sealed own-context state, retired training mount')
        expected=sessions(roster,'evaluation',spec['animal'])
        need([x['session'] for x in r['evaluation']]==expected,'all and only current-animal views')
        need(task_products[fit['operation']][0]<intents[op][0],'own fit before inference')
        need(len(r['provider_values'])==len(method['recipe']['numeric_slots']),'exact frozen numerical provider slots')
        need(r['recipe']==method['recipe'],'same sealed inference recipe')
        if method['recipe']['numeric_slots']:
            need(op+'/features' in products,'mandatory actual numeric feature producer')
            feature=products[op+'/features']
            numeric_keys.extend(numeric_bridge(op,feature,r,complete['numeric_slots'][op],method,closed['providers'],selection))
            for bridge in complete['numeric_slots'][op]:
                matching=[(i,e) for i,e in enumerate(events) if e['kind']=='numeric_slot_completed' and e.get('operation')==op and e.get('slot')==bridge['slot']]
                need(len(matching)==1 and all(matching[0][1][k]==v for k,v in bridge.items())
                     and task_products[op+'/features'][0]<matching[0][0]<intents[op][0],'exact feature/provider/inference event order')
        else:need(complete['numeric_slots'][op]==[] and r['provider_values']==[],'no undeclared numeric provider inputs')
    mandatory=set(complete['reference_cv'].values())|set(complete['reference_models'].values())|set(complete['reference_predictions'].values())
    mandatory|=set(complete['candidate_fits'].values())|set(complete['candidate_outputs'].values())
    for op in set(products)-mandatory:
        p=products[op];r=p['envelope']['request']
        if '/analysis/' in op:
            identity,ordinal=op.rsplit('/analysis/',1)
            need(identity in methods and ordinal.isdigit() and int(ordinal)>0 and r['stage']=='analysis','only actual declared author analyses')
            spec=methods[identity]
            admit_analysis(r,spec,roster)
            need(r['panel']==spec['panel'] and r['animal']==spec['animal']
                 and [x['session'] for x in r['training']]==sessions(roster,'source'), 'full own-context analysis inputs')
            need([x['session'] for x in r['evaluation']]==([] if spec['animal']=='global' else spec['evaluation_sessions']), 'no cross-condition/query-before-F-seal analysis')
            need(task_products[op][0]<method_events[identity][0], 'analysis finishes before its method seal')
        elif op.endswith('/features'):
            inference=op[:-9];matching=[s for s in outputs.values() if s['id']==inference]
            need(len(matching)==1 and r['stage']=='numeric_features','only one declared prediction feature stage')
            spec=matching[0];method=complete['methods'][spec['author']];fit=products[complete['candidate_fits'][spec['author']]]
            admit_features(r,spec,roster,method,fit)
            need(method['recipe']['numeric_slots'] and r['program']['pin']==method['program']['pin']
                 and r['state']==fit['result']['state'] and r['current_session']==spec['session'], 'frozen own-method numeric feature producer')
            need(method_events[spec['author']][0]<intents[op][0]<task_products[op][0]<intents[inference][0], 'features between method seal and its final inference')
        else:raise ValueError('undeclared native producer cannot enter complete graph')
    actual_numeric={k for k,row in closed['providers'].items() if set(row['complete']['action'])=={'values'}}
    need(len(numeric_keys)==len(set(numeric_keys)) and set(numeric_keys)==actual_numeric,'every numeric reply has exactly one declared consumer')
    need(sum(e['kind']=='numeric_slot_completed' for e in events)==len(numeric_keys),'no extra numeric bridges')
    for panel in panels():
        scope=scopes[panel['id']];end=panel_finishes[panel['id']]['accounting'];profile=selection['panel_limits'][panel['id']]
        need(end['final_event_encoding_and_publication_reservation_included']==2*selection['limits']['journal_event_bytes'],
             'final panel encoding/publication reservation included before original-clock close')
        need(end['closed'] is True and end['read_reserved_bytes']<=profile['read_bytes']
             and end['write_reserved_bytes']<=profile['write_bytes'] and end['provider_tokens_observed']<=profile['tokens']
             and end['provider_calls']<=profile['provider_calls'] and end['provider_money_reserved']<=profile['money'], 'one complete matched panel ledger')
        need(scope['cpu_cap']==profile['native_cpu_ns'] and scope['gpu_cap']==profile['gpu_device_seconds'], 'actual native whole-panel caps')
        need(end['native_scope']['cpu_reserved']<=scope['cpu_cap'] and end['native_scope']['gpu_reserved']<=scope['gpu_cap'],'complete native reservations')
    return {'schema':'neural058_public_graph_admission_v1','task':'NEURAL-058','counts':counts,
            'complete':pin(encoded(complete)),'source':source,'selection':complete['selection'],
            'all_public_producers_admitted':True,'protected_targets_read':False,
            'semantic_and_physical_qualification_still_required':True}
