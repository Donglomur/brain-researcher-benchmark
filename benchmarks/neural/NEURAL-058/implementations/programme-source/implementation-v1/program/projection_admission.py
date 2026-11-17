"""Independent exact permitted-view and trained-state mount-set reconstruction."""
from pathlib import Path
from core import need,pin,encoded,capture
from arrays import read_json
from corpus import projected_document
from authority import forbid_protected_mounts


def verify(complete,events,selection,frozen,budget):
    root=Path(selection['roots']['prepared']);limits=selection['data_limits']
    top=read_json(root,selection['prepared'],budget,limits['metadata_bytes'])
    from contracts import COHORT_PIN
    need(top['cohort']==COHORT_PIN and top['authority']==selection['prepared_authority'],'independent canonical prepared chain')
    docs={};projections={};ordinal_rows={}
    for role in ('source','evaluation'):
        need(len(top[role])==(423 if role=='source' else 29),'complete projection corpus')
        for item in top[role]:
            doc=read_json(root,item,budget,limits['metadata_bytes']);sid=doc['session']
            need(sid not in docs and doc['role']==role,'unique source-side session roles')
            row=complete['roster'][role][sid]
            need(row['animal']==doc['animal'] and row['fold']==doc['fold'],'exact source-side biological/fold view')
            ordinal_rows[sid]={'eid':sid,'animal':doc['animal'],'role':role,'fold':doc['fold'],
                               'session_ordinal':doc['session_ordinal'],'animal_ordinal':doc['animal_ordinal']}
            docs[sid]=doc
            for access in ('C','J'): projections[(access,sid)]=projected_document(doc,access,role=='source')
    from ordering import roster as ordered_roster
    need(ordered_roster(ordinal_rows)==complete['roster'],'independent full stable source/animal order')
    need(complete['roster']['source_order']==top['source_order'] and complete['roster']['evaluation_order']==top['evaluation_order']
         and complete['roster']['source_animals']==top['source_animal_order']
         and complete['roster']['eval_animals']==top['evaluation_animal_order'],'exact authenticated preparation order arrays')
    native_intents={e['operation']:e for e in events if e['kind']=='native_intent'}
    scopes={e['identity']:e for e in events if e['kind']=='scope_started'}
    checked=[]
    for operation,product in complete['products'].items():
        budget.tick();inner=product['envelope']['request'];role=inner['role'];expected={}
        for name,d in frozen['manifest']['files'].items():expected['/inputs/source/'+name]=d
        expected['/inputs/source/RUNTIME_SOURCE.json']=frozen['pin'];expected['/inputs/request.json']=product['request']
        for kind in ('training','validation','evaluation'):
            for row in inner.get(kind,[]):
                sid=row['session'];proj=projections[(role,sid)]
                need(row['animal']==docs[sid]['animal'],'exact assigned animal projection')
                need(row['view']=={'path':sid+'/VIEW.json','pin':pin(encoded(proj))},'role and all source-derived query metadata')
                expected['/inputs/corpus/'+sid+'/VIEW.json']=row['view']['pin']
                for d in proj['arrays'].values():expected['/inputs/corpus/'+sid+'/'+d['path']]=d['pin']
        def state(model,prefix):
            for d in [model['metadata']]+model['arrays']:expected[prefix+'/'+d['path']]=d['pin']
        if product['envelope']['producer']=='reference':
            if inner['operation']=='predict':state(inner['model'],'/inputs/model')
        else:
            expected['/inputs/method.py']=inner['program']['pin']
            if inner['stage'] in ('numeric_features','infer'):state(inner['state'],'/inputs/state')
            if inner['tool']=='T0':need(inner['tools']=={},'T0 has no trained state')
            else:
                need(inner['tool']=='T1' and set(inner['tools'])=={'velocity','speed'},'role-matched strongest T1 heads')
                for head,row in inner['tools'].items():
                    selected=complete['reference_selection']['strongest'][role+'/'+head]
                    model_op=complete['reference_models'][role+'/'+selected['config']]
                    model=complete['products'][model_op]['result']['model']
                    need(row['selected_config']==selected['config'] and row['model']==model
                         and row['producer']==model_op,'exact strongest source-only tool lineage')
                    state(model,'/inputs/tools/'+selected['config'])
        from native_contract import verify as verify_contract
        verify_contract(native_intents[operation],product,selection,frozen,scopes)
        mounts=native_intents[operation]['mounts']
        forbid_protected_mounts(mounts,selection)
        actual={r['destination']:r['pin'] for r in mounts}
        need(len(actual)==len(mounts) and actual==expected,'exact whole permitted file mount set; no hidden canonical store')
        for row in mounts:capture(row['source'],row['pin'],row['bytes_cap'],budget,retain=False,readonly=True)
        checked.append({'operation':operation,'mounts':len(mounts),'projection_complete':True})
    return {'schema':'neural058_independent_projection_admission_v1','operations':checked,
            'protected_targets_read':False,'original_physical_input_qualification_separate':True}
