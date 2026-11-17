"""Selected native reference worker: actual fit and full prediction producers."""
from pathlib import Path
from core import need, capture, parse, fresh, encoded, pin
from corpus import load_session, weights_and_membership
from reference_models import fit, predict
from state_io import save, load
from arrays import write_array, write_json
from scores import animal_score


def sessions(request,kind,budget):
    rows=request[kind]; need(rows and len({r['session'] for r in rows})==len(rows),'complete unique worker input rows')
    result=[]
    training=kind in ('training','validation')
    for row in rows:
        session=load_session(request['input_root'],row['view'],request['role'],training,budget,request['limits'])
        need(session['session']==row['session'] and session['animal']==row['animal'],'exact source-owned view identity')
        result.append(session)
    return result


def predictions(state,data,output,budget,limits,device):
    import numpy as np
    rows=[]; source_scores={}
    for session in data:
        budget.tick(); values=[]; queries=[]; offsets=[0]; score_windows=[]
        for window in session['windows']:
            p=predict(state,window,budget,device)
            values.append(p); offsets.append(offsets[-1]+len(p)); queries.append(window['query'])
            if 'labels' in window: score_windows.append((window['labels'],p))
        ordinal=len(rows)
        arr=write_array(output,'prediction-'+str(ordinal)+'.npy',np.concatenate(values),budget,limits['expanded_bytes'])
        idx=write_array(output,'offsets-'+str(ordinal)+'.npy',np.array(offsets,dtype='<i8'),budget,limits['expanded_bytes'])
        rows.append({'session':session['session'],'animal':session['animal'],'queries':queries,
                     'view':session['source_view'],'values':arr,'offsets':idx})
        if score_windows: source_scores.setdefault(session['animal'],[]).append(score_windows)
    scores={a:animal_score(ss)['r2'] for a,ss in source_scores.items()}
    return rows,scores


def run(request,budget):
    """Entry bootstrap and independent external qualification are prerequisites.
    This function itself never accepts a finished fit/prediction callback.
    """
    need(request.get('schema')=='neural058_reference_request_v1' and request.get('task')=='NEURAL-058','task-native request')
    need(request['role'] in ('C','J') and request['operation'] in ('fit','predict'),'fixed reference operation')
    output=fresh(request['output_root'],budget); operation=request['operation']; device=request['device']
    if operation=='fit':
        training=sessions(request,'training',budget)
        train_animals=__import__('ordering').animals(training)
        need(train_animals==request['training_animals'],'complete selected training animals')
        need(not set(train_animals)&set(request['forbidden_animals']),'no target/held-fold animal fits')
        if request['fold']=='full': need(len(training)==423 and len(train_animals)==126,'full423/126 refit')
        else: need(all(s['fold']!=request['fold'] for s in training),'whole source-animal exclusion')
        state=fit(request['config'],request['role'],request['fold'],training,budget,device)
        model=save(output,state,budget,request['limits'])
        predicted=[]; scores={}
        if request['fold']!='full':
            validation=sessions(request,'validation',budget)
            need(all(s['fold']==request['fold'] for s in validation),'exact held source fold')
            need(not set(train_animals)&{s['animal'] for s in validation},'whole-animal OOF disjointness')
            predicted,scores=predictions(state,validation,output,budget,request['limits'],device)
        record={'model':model,'predictions':predicted,'animals':scores,'config':request['config'],
                'fold':request['fold'],'role':request['role'],'training_animals':train_animals,
                'training_sessions':[s['session'] for s in training]}
    else:
        state=load(request['model_root'],request['model']['metadata'],budget,request['limits'])
        need(state['role']==request['role'] and state['fold']=='full' and state['config']==request['config'],
             'exact independently selected full-source model state')
        evaluation=sessions(request,'evaluation',budget)
        need(not set(state['training_animals'])&{s['animal'] for s in evaluation},'strict evaluation-animal exclusion')
        predicted,scores=predictions(state,evaluation,output,budget,request['limits'],device)
        need(not scores,'no evaluation labels supplied to reference prediction')
        record={'model':request['model'],'predictions':predicted,'config':request['config'],
                'fold':'full','role':request['role']}
    record.update(schema='neural058_reference_result_v1',task='NEURAL-058',request=pin(encoded(request)),
                  budget_before_publication=budget.record(),actual_numerical_producer=True)
    result=write_json(output,'RESULT.json',record,budget,request['limits']['metadata_bytes'])
    budget.tick(); return result
