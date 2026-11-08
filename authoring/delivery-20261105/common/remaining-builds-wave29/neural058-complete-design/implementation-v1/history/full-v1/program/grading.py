"""Late independently admitted protected grading; complete outputs precede truth."""
from pathlib import Path
from core import need,capture,parse,pin,encoded,publish,fresh,finite
from arrays import read_json,read_array
from journal import decode
from admission import admit
from scores import animal_score,macro,paired_contrast
from schedule import panels


def predictions(product,row,view,root,budget,limits):
    import numpy as np
    members={x['path']:x['pin'] for x in product['derived']['members']}
    for key in ('values','offsets'):need(members.get(row[key]['path'])==row[key]['pin'],'prediction belongs to closed producer')
    value,_=read_array(product['root'],row['values'],budget,limits['array_bytes'],limits['expanded_bytes'])
    offset,_=read_array(product['root'],row['offsets'],budget,limits['array_bytes'],limits['expanded_bytes'])
    original,_=read_array(root,view['common']['time_offsets'],budget,limits['array_bytes'],limits['expanded_bytes'])
    expected=[w['query'] for w in view['windows']]
    need(row['queries']==expected and np.array_equal(offset,original),'all original query occurrences/timestamps, no subset')
    need(value.shape==(int(original[-1]),2) and np.isfinite(value).all(),'complete finite two-head output')
    return value,offset


def reduce(values,targets,views,roster):
    animals={}
    for animal in roster['eval_animals']:
        sessions=[]
        for sid in sorted(s for s,r in roster['evaluation'].items() if r['animal']==animal):
            y,offset=targets[sid];p=values[sid];windows=[]
            for a,b in zip(offset[:-1],offset[1:]):windows.append((y[a:b],p[a:b]))
            sessions.append(windows)
        animals[animal]=animal_score(sessions)
    return macro(animals,roster['eval_animals'])


def run(request,budget,frozen):
    import numpy as np
    need(request.get('schema')=='neural058_late_grading_selection_v1' and request.get('task')=='NEURAL-058'
         and request.get('selected') is True and request['source']==frozen['pin'],'new exact root-selected grading operation')
    raw,_=capture(request['root_outer_closure']['path'],request['root_outer_closure']['pin'],262144,budget,readonly=True)
    root_fact=parse(raw)
    need(root_fact.get('schema')=='neural058_root_observed_outer_v1' and root_fact.get('source')==frozen['pin']
         and root_fact.get('natural_exit') is True and type(root_fact.get('exit_code'))is int and root_fact['exit_code']==0
         and root_fact.get('stdout_eof') is True and root_fact.get('stderr_eof') is True
         and root_fact['observation']==request['observation']['pin'],'root-observed natural outer exit/EOF, not a provisional file')
    need(finite(root_fact['observed_end'])<=budget.origin,'fresh grading origin does not reset/extend production clocks')
    raw,_=capture(request['observation']['path'],request['observation']['pin'],request['metadata_bytes'],budget,readonly=True)
    observation=parse(raw)
    need(observation.get('schema')=='neural058_external_observation_v1' and observation['source']==frozen['pin']
         and observation['protected_targets_read'] is False,'exact independent public-only observation')
    raw,_=capture(observation['production']['path'],observation['production']['pin'],4<<20,budget,readonly=True);selection=parse(raw)
    from core import disjoint
    need(request['private_root']==selection['roots']['private'],'exact original protected target namespace')
    need(all(disjoint(request['output_root'],r) for r in selection['roots'].values()),'fresh separate grading output namespace')
    root=Path(selection['roots']['output'])
    raw,_=capture(root/'COMPLETE.json',observation['complete'],selection['limits']['complete_metadata_bytes'],budget,readonly=True);complete=parse(raw)
    raw,_=capture(root/'JOURNAL.jsonl',observation['journal'],selection['limits']['journal_bytes'],budget,readonly=True)
    events,chain=decode(raw,event_cap=selection['limits']['journal_event_bytes'])
    graph=admit(complete,events,selection,frozen['pin'])
    need(graph==observation['graph'] and chain==observation['chain'],'unchanged public admission at late grading')
    proof_raw,_=capture(request['qualification']['path'],request['qualification']['pin'],262144,budget,readonly=True);proof=parse(proof_raw)
    binding=pin(encoded({k:v for k,v in request.items() if k!='qualification'}))
    need(proof.get('schema')=='neural058_late_grading_qualification_v1' and proof.get('independent_operator') is True
         and proof.get('source')==frozen['pin'] and proof.get('selection')==binding
         and proof.get('production')==complete['selection'] and proof.get('observation')==request['observation']['pin'], 'exact independent late authority')
    for key in ('actual_program_semantics_and_exposure','original_units_sign_support','reference_parity_and_source_lineage',
                'whole_operation_resources_and_custody','protected_target_membership'):
        need(proof.get(key) is True,'missing actual independent qualification: '+key)
    need(proof.get('method_graph')==pin(encoded({'methods':complete['methods'],'transcripts':complete['author_transcripts']})),
         'review binds all168 actual programs and full isolated transcripts')
    need(budget.origin<=finite(proof['observed'])<=budget.tick() and budget.tick()<finite(proof['valid_until'])<=budget.deadline,
         'fresh independent grade qualification under this operation clock')
    limits=selection['data_limits'];prepared=Path(selection['roots']['prepared'])
    top=read_json(prepared,selection['prepared'],budget,limits['metadata_bytes']);views={}
    for item in top['evaluation']:
        doc=read_json(prepared,item,budget,limits['metadata_bytes']);views[doc['session']]=doc
    need(set(views)==set(complete['roster']['evaluation']) and len(views)==29,'full protected study support')
    candidates={};references={};offsets={}
    # Every actual candidate and reference prediction body is captured and its
    # complete original output axis admitted before opening any target member.
    for key,operation in complete['candidate_outputs'].items():
        product=complete['products'][operation];row=product['result'];sid=row['session']
        value,offset=predictions(product,row,views[sid],prepared/sid,budget,limits)
        panel=row['panel'];candidates.setdefault(panel,{})[sid]=value;offsets[sid]=offset
    for key,operation in complete['reference_predictions'].items():
        product=complete['products'][operation];need(len(product['result']['predictions'])==1,'one reference session result')
        row=product['result']['predictions'][0];sid=row['session']
        value,offset=predictions(product,row,views[sid],prepared/sid,budget,limits)
        references[key]=value;need(np.array_equal(offset,offsets[sid]),'candidate/reference identical source axes')
    need(set(candidates)=={p['id'] for p in panels()} and all(set(v)==set(views) for v in candidates.values()),'all24 complete candidate panels')
    need(len(references)==complete['counts']['reference_session_predictions'],'all independent reference output panels')
    from native_reader import versions
    versions({'numpy':'2.2.6','torch':'2.10.0','torchmetrics':'1.9.0'})
    # This is the sole target-entry boundary. No target body was read above.
    budget.tick();targets={};private_joins={};need(set(request['target_joins'])==set(views),'all29 protected target joins')
    for sid in sorted(views):
        join=read_json(request['private_root'],request['target_joins'][sid],budget,limits['metadata_bytes'])
        need(join['opaque_session']==sid and join['opaque_animal']==views[sid]['animal']
             and join['label_root_role']=='private' and [r['query'] for r in join['joins']]==[w['query'] for w in views[sid]['windows']],
             'source-derived exact private/public query membership')
        y,_=read_array(Path(request['private_root'])/sid,join['labels'],budget,limits['array_bytes'],limits['expanded_bytes'])
        need(y.shape==(int(offsets[sid][-1]),2) and np.isfinite(y).all()
             and np.array_equal(y[:,1],np.abs(y[:,0])),'complete signed/absolute native-converted targets')
        targets[sid]=(y,offsets[sid])
        private_joins[sid]=join['joins']
    budget.tick()
    candidate_scores={p:reduce(v,targets,views,complete['roster']) for p,v in candidates.items()}
    from native_diagnostic import session as native_session,seed_aggregate
    native_scores={}
    for panel,values in candidates.items():
        native_scores[panel]={}
        for sid,pred in values.items():
            budget.tick();y,offset=targets[sid]
            native_scores[panel][sid]=native_session(y,pred,offset,private_joins[sid]);budget.tick()
    native_aggregates={}
    for mode in ('F','I'):
        for role in ('C','J'):
            for tool in ('T0','T1'):
                key='/'.join((mode,role,tool))
                native_aggregates[key]=seed_aggregate([native_scores[key+'/r'+str(r)] for r in (1,2,3)],sorted(views))
    reference_scores={};native_reference_scores={};selected=complete['reference_selection']
    for role in ('C','J'):
        for family in ('ridge','forest','set','strongest'):
            combined={}
            for sid in views:
                columns=[]
                for h,head in enumerate(('velocity','speed')):
                    config=selected['strongest'][role+'/'+head]['config'] if family=='strongest' else selected['choices'][role+'/'+family+'/'+head]
                    columns.append(references[role+'/'+config+'/'+sid][:,h])
                combined[sid]=np.column_stack(columns)
            reference_scores[role+'/'+family]=reduce(combined,targets,views,complete['roster'])
            native_reference_scores[role+'/'+family]={}
            for sid,pred in combined.items():
                budget.tick();y,offset=targets[sid]
                native_reference_scores[role+'/'+family][sid]=native_session(y,pred,offset,private_joins[sid]);budget.tick()
    contrasts={};animals=complete['roster']['eval_animals']
    for axis in ('neural','tool','workflow'):
        others=(('F','I'),('T0','T1')) if axis=='neural' else ((('F','I'),('C','J')) if axis=='tool' else (('C','J'),('T0','T1')))
        for a in others[0]:
            for b in others[1]:
                left,right=(('J','C') if axis=='neural' else ('T1','T0') if axis=='tool' else ('I','F'))
                def panel(value,rep):
                    parts=(a,value,b) if axis=='neural' else (a,b,value) if axis=='tool' else (value,a,b)
                    return '/'.join(parts)+'/r'+str(rep)
                for h,head in enumerate(('velocity','speed')):
                    l={animal:[candidate_scores[panel(left,r)]['animals'][animal]['r2'][h] for r in (1,2,3)] for animal in animals}
                    r={animal:[candidate_scores[panel(right,n)]['animals'][animal]['r2'][h] for n in (1,2,3)] for animal in animals}
                    contrasts['/'.join((axis,a,b,head))]=paired_contrast(l,r,animals)
    result={'schema':'neural058_protected_scores_v1','task':'NEURAL-058','source':frozen['pin'],
            'production':complete['selection'],'observation':request['observation']['pin'],
            'grade_authority':binding,'candidate':candidate_scores,'references':reference_scores,'contrasts':contrasts,
            'native_session_speed_convention_diagnostic':native_scores,
            'native_reference_session_speed_convention_diagnostic':native_reference_scores,
            'native_clipped_session_seed_aggregation_diagnostic':native_aggregates,
            'inference':'descriptive paired animal intervals conditional on source-trained references and realized policies; no SOTA/causal/native-understanding claim',
            'budget_before_publication':budget.record()}
    out=fresh(request['output_root'],budget);body=encoded(result)
    need(len(body)<=request['metadata_bytes'],'complete protected score metadata')
    d=publish(out/'SCORES.json',body,budget,readonly=True);budget.tick()
    return {'scores':d,'root':str(out),'root_observed_natural_grade_closure_still_required':True}
