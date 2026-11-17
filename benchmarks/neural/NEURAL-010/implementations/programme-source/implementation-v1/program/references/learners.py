"""Complete future support fits and frozen-state inference, never a data subset."""
import math
from common import need,finite,exact,integer,ID,SHA,GRID,records,authenticate_support,numpy,load_array,save_array,descriptor
from math_core import fsum,weighted_scaler,apply_scaler,logistic_fit,tree_fit,tree_node_bound,predict_state
from features import authenticate_cache
from contracts import check_context,normalize_worker
import event_protocol as event

CONDITIONS=('joint','matched_no_eeg','signal_reference','montage_only')

def family_for(condition):return 'strong' if condition in ('joint','matched_no_eeg') else condition

def training_weights(rows):
    """Pure metadata calculation of exact class counts and binary64 row weights."""
    counts={}
    for r in rows:
        positive=sum(b-a for a,b in r['events']);v=counts.setdefault(r['patient_id'],[0,0]);v[1]+=positive;v[0]+=r['duration_seconds']-positive
    need(all(a>0 and b>0 for a,b in counts.values()),'both full observed classes for every training person')
    m=len(counts);return counts,{p:[1./(2*m*c) for c in v] for p,v in sorted(counts.items())}

def dimensions(rows,vocab,condition,io):
    n=sum(r['duration_seconds'] for r in rows);d=33+len(vocab)+2
    need(n<=io.limits['max_rows'] and d<=min(721,io.limits['max_columns']),'all rows and columns must fit admitted geometry')
    # These are prospective numeric-buffer bounds, not measured Python heap/RSS.
    required=2*n*d*8+n*128+(d+1)**2*32
    need(required<=io.limits['max_design_bytes'],'whole matrix and numerical workspace admission; no subsampling')
    return n,d,required

def matrix(rows,vocab,condition,io,identity):
    np=numpy();n,d,_=dimensions(rows,vocab,condition,io);x=np.zeros((n,d),dtype=np.float64);index={m:i for i,m in enumerate(vocab)};start=0
    for row in rows:
        end=start+row['duration_seconds']
        if condition=='joint':
            desc=authenticate_cache(io,row,condition,identity);a=load_array(io,desc,(row['duration_seconds'],33),'float64');x[start:end,:33]=a;del a
        else:need(condition=='matched_no_eeg' and 'feature_receipt' not in row and 'eeg_features' not in row and 'signal_features' not in row,'no EEG read/hash/statistic authority')
        x[start:end,33+index.get(row['montage_id'],len(vocab))]=1.;x[start:end,-1]=math.log1p(row['channel_count']);start=end
    need(start==n and bool(np.isfinite(x).all()),'complete matrix rows');return x

def fit_strong(rows,condition,grid,support,io,identity):
    np=numpy();vocab=sorted({r['montage_id'] for r in rows});n,d,required=dimensions(rows,vocab,condition,io)
    cfg=GRID[grid]
    if cfg['kind']=='trees':
        bound=tree_node_bound(n,cfg['depth'],cfg['min_leaf']);need(bound<=io.limits['max_nodes'] and bound*512+65536<=io.limits['max_model_bytes'],'all256 tree structure resource admission')
    counts,person_weights=training_weights(rows);x=matrix(rows,vocab,condition,io,identity);y=np.zeros(n,dtype=np.uint8);w=np.empty(n,dtype=np.float64);start=0
    for row in rows:
        end=start+row['duration_seconds']
        for a,b in row['events']:y[start+a:start+b]=1
        negative,positive=person_weights[row['patient_id']];w[start:end]=np.where(y[start:end]==1,positive,negative);start=end
    active=[condition=='joint']*33+[True]*(d-33);scaler=weighted_scaler(x,w,active);u=apply_scaler(x,scaler);del x
    state=logistic_fit(u,y,w,cfg['lambda']) if cfg['kind']=='logistic' else tree_fit(u,y,w,grid,support,io.limits['max_nodes'],active)
    return {'vocabulary':vocab,'columns':d,'scaler':scaler,'state':state,'class_counts':counts,'person_class_weights':person_weights,'rows':n,'numeric_buffer_admission_bytes':required,'configuration':cfg}

def fit_signal(rows,io,identity):
    np=numpy();need(len({r['patient_id'] for r in rows})==22,'historical signal all22 training people');n=sum(r['duration_seconds'] for r in rows)
    need(n<=io.limits['max_rows'] and n*24<=io.limits['max_design_bytes'],'all historical signal rows allocation')
    groups={}
    for row in rows:
        desc=authenticate_cache(io,row,'signal_reference',identity);x=load_array(io,desc,(row['duration_seconds'],),'float64');keep=np.ones(row['duration_seconds'],dtype=bool)
        for a,b in row['events']:keep[a:b]=False
        groups.setdefault(row['patient_id'],[]).append(x[keep]);del x
    quantiles=[]
    for pid in sorted(groups):
        values=np.concatenate(groups[pid]);need(len(values)>0,'nonictal observed support per training person');q=float(np.quantile(values,.995,method='linear'));need(finite(q),'finite historical quantile');quantiles.append({'patient_id':pid,'quantile_995':q,'nonictal_seconds':len(values)})
    threshold=float(np.median([r['quantile_995'] for r in quantiles]));need(finite(threshold),'finite historical threshold')
    return {'kind':'signal_reference','threshold':threshold,'person_quantiles':quantiles,'rows':n,'method':'original_numpy_quantile995_linear_then_median22'}

def fit_montage(rows):
    per_montage={};per_person={}
    for row in rows:
        pid,mid=row['patient_id'],row['montage_id'];ictal=sum(b-a for a,b in row['events'])
        for slot in (per_montage.setdefault(mid,{}).setdefault(pid,[0,0]),per_person.setdefault(pid,[0,0])):slot[0]+=ictal;slot[1]+=row['duration_seconds']
    need(all(v[0]>0 for v in per_person.values()),'original complete source event support for every training person')
    def balanced(groups):return math.fsum(groups[p][0]/groups[p][1] for p in sorted(groups))/len(groups)
    return {'kind':'montage_only','prevalence_by_montage':{m:balanced(g) for m,g in sorted(per_montage.items())},'fallback_prevalence':balanced(per_person),'training_people':len(per_person),'rows':sum(r['duration_seconds'] for r in rows)}

def check_selection(doc,request,people,identity):
    from selection import validate_selection
    validate_selection(doc)
    need(doc['source_identity']==identity and doc['condition']==request['condition'] and doc['family']==request['family'] and doc['context']==request['context'] and doc['expected_validation_people']==people,'exact selected final context and complete22people')
    need(doc['grid_index']==request['grid_index'],'chosen grid only may receive final refit')
    return doc['threshold']

def fit(request,io,out,identity):
    condition=request['condition'];need(condition in CONDITIONS and request['family']==family_for(condition),'exact family/condition');people=check_context(request['context'])
    need(request['expected_people']==len(people),'context-consistent complete fit support')
    inner=request['context']['inner_person'];grid=request['grid_index'];strong=request['family']=='strong'
    need((integer(grid,0,8) if strong else grid is None),'fixed grid index')
    need(condition!='signal_reference' or inner is None,'historical signal has final fits only')
    normalized,training_manifest,normalization=normalize_worker(io,request['records'],request['feature_bindings'],'train',condition,request['context'],out,identity)
    rows=records(normalized,'train',condition);actual=authenticate_support(io,rows,request['support'],request['support_sha256'],request['expected_people']);need(actual==people,'all and only context training people')
    threshold=None;selection=None
    if inner is None and condition!='signal_reference':
        selection=io.json(request['selection']);threshold=check_selection(selection,request,people,identity)
    else:need(request['selection'] is None,'no selection operand in inner/signal fit')
    if strong:state=fit_strong(rows,condition,grid,request['support_sha256'],io,identity)
    elif condition=='signal_reference':state=fit_signal(rows,io,identity);threshold=state['threshold']
    else:state=fit_montage(rows)
    model={'schema':'neural010-reference-model-v1','source_identity':identity,'family':request['family'],'condition':condition,'grid_index':grid,'context':request['context'],'training_people':people,'training_records':[{'patient_id':r['patient_id'],'recording_id':r['recording_id'],'duration_seconds':r['duration_seconds']} for r in rows],'training_manifest':training_manifest,'prepared_training_view':request['records'],'normalization':normalization,'support':request['support'],'support_sha256':request['support_sha256'],'selection':request['selection'],'selection_threshold':threshold,'state':state,'native_numerics':{'numpy':'2.2.6','h5py':'3.14.0','reduction':'binary64_math_fsum_canonical_rows_v1'},'qualification':False}
    validate_model(model,identity,io);model_pin=io.write_json(out/'model.json',model,io.limits['max_model_bytes'])
    receipt={'schema':'neural010-fit-receipt-v1','source_identity':identity,'model':model_pin,'request':request,'complete_training_rows':sum(r['duration_seconds'] for r in rows),'training_people':people,'support_sha256':request['support_sha256'],'context':request['context'],'family':request['family'],'condition':condition,'grid_index':grid,'selection':request['selection'],'selection_threshold':threshold,'training_manifest':training_manifest,'prepared_training_view':request['records'],'normalization':normalization,'qualified':False}
    return io.write_json(out/'FIT.json',receipt)

def validate_model(model,identity,io):
    exact(model,('schema','source_identity','family','condition','grid_index','context','training_people','training_records','training_manifest','prepared_training_view','normalization','support','support_sha256','selection','selection_threshold','state','native_numerics','qualification'))
    need(model['schema']=='neural010-reference-model-v1' and model['source_identity']==identity and model['qualification'] is False,'exact fitted source identity')
    condition=model['condition'];need(condition in CONDITIONS and model['family']==family_for(condition),'fitted family');people=check_context(model['context']);need(model['training_people']==people,'exact fitted training support')
    for field in ('training_manifest','prepared_training_view','normalization','support'):descriptor(model[field])
    need(model['support_sha256']==model['support']['sha256'],'fitted support identity')
    trs=model['training_records'];need(type(trs) is list and 0<len(trs)<=686,'complete training records');pairs=[]
    for r in trs:
        exact(r,('patient_id','recording_id','duration_seconds'));need(r['patient_id'] in people and type(r['recording_id']) is str and ID.fullmatch(r['recording_id']) and integer(r['duration_seconds'],1,86400),'training recording geometry');pairs.append((r['patient_id'],r['recording_id']))
    need(pairs==sorted(set(pairs)) and len({r['recording_id'] for r in trs})==len(trs) and sorted({r['patient_id'] for r in trs})==people,'all canonical fitted training records')
    n=sum(r['duration_seconds'] for r in trs);need(n<=10000000 and n<=io.limits['max_rows'],'full fitted extent');state=model['state'];need(type(state) is dict and state.get('rows')==n,'state/training row join')
    final=model['context']['inner_person'] is None;threshold=model['selection_threshold']
    need(model['native_numerics']=={'numpy':'2.2.6','h5py':'3.14.0','reduction':'binary64_math_fsum_canonical_rows_v1'},'frozen numerical identity')
    if condition=='signal_reference':
        need(final and model['selection'] is None and model['grid_index'] is None,'original signal final-only state');exact(state,('kind','threshold','person_quantiles','rows','method'));need(state['kind']==condition and finite(threshold) and threshold==state['threshold'] and state['method']=='original_numpy_quantile995_linear_then_median22','historical threshold state');need([r['patient_id'] for r in state['person_quantiles']]==people and all(finite(r['quantile_995']) and integer(r['nonictal_seconds'],1) for r in state['person_quantiles']),'all22 historical quantiles');return
    if final:descriptor(model['selection']);need(finite(threshold) and 0<=threshold<=1,'sealed final threshold')
    else:need(model['selection'] is None and threshold is None,'unthresholded inner state')
    if condition=='montage_only':
        exact(state,('kind','prevalence_by_montage','fallback_prevalence','training_people','rows'));need(model['grid_index'] is None and state['kind']==condition and state['training_people']==len(people),'historical montage state');need(type(state['prevalence_by_montage']) is dict and 0<len(state['prevalence_by_montage'])<=686 and all(type(k) is str and SHA.fullmatch(k) and finite(v) and 0<=v<=1 for k,v in state['prevalence_by_montage'].items()) and finite(state['fallback_prevalence']) and 0<=state['fallback_prevalence']<=1,'all finite original montage prevalences');return
    grid=model['grid_index'];need(integer(grid,0,8),'strong grid');exact(state,('vocabulary','columns','scaler','state','class_counts','person_class_weights','rows','numeric_buffer_admission_bytes','configuration'))
    vocab=state['vocabulary'];need(type(vocab) is list and 0<len(vocab)<=686 and vocab==sorted(set(vocab)) and all(type(x) is str and SHA.fullmatch(x) for x in vocab),'fixed training vocabulary');d=33+len(vocab)+2;need(state['columns']==d<=min(721,io.limits['max_columns']) and state['configuration']==GRID[grid],'fixed columns/configuration')
    sc=state['scaler'];exact(sc,('mean','scale','constant','active','weight_sum','reduction'));need(all(type(sc[k]) is list and len(sc[k])==d for k in ('mean','scale','constant','active')) and sc['active']==[condition=='joint']*33+[True]*(d-33),'same indexed matched design')
    need(finite(sc['weight_sum']) and sc['weight_sum']>0 and sc['reduction']=='binary64_math_fsum_canonical_rows_v1','normalized fitted moments')
    for j in range(d):
        need(type(sc['constant'][j]) is bool and type(sc['active'][j]) is bool,'boolean scaler state')
        if not sc['active'][j]:need(sc['mean'][j] is None and sc['scale'][j] is None and sc['constant'][j],'withheld EEG has no learned statistics')
        else:need(finite(sc['mean'][j]) and finite(sc['scale'][j]) and sc['scale'][j]>=0 and sc['constant'][j]==(sc['scale'][j]==0),'finite constant/scaled column')
    need(set(state['class_counts'])==set(people)==set(state['person_class_weights']),'all training class counts')
    for p in people:
        cnt=state['class_counts'][p];weights=state['person_class_weights'][p];need(type(cnt) is list and len(cnt)==2 and all(integer(x,1) for x in cnt) and sum(cnt)==sum(r['duration_seconds'] for r in trs if r['patient_id']==p) and weights==[1./(2*len(people)*v) for v in cnt],'full per-person class weights')
    ms=state['state']
    if GRID[grid]['kind']=='logistic':
        exact(ms,('kind','lambda','theta','steps','objective','gradient_infinity_norm','solve_history'));need(ms['kind']=='logistic' and ms['lambda']==GRID[grid]['lambda'] and len(ms['theta'])==d+1 and all(finite(x) for x in ms['theta']) and integer(ms['steps'],0,200) and finite(ms['objective']) and finite(ms['gradient_infinity_norm']) and 0<=ms['gradient_infinity_norm']<=1e-7 and len(ms['solve_history'])==ms['steps'],'converged full logistic state')
        for k,r in enumerate(ms['solve_history']):
            exact(r,('accepted_step','alpha','objective','backward_error'));need(r['accepted_step']==k+1 and r['alpha'] in [math.ldexp(1.,-i) for i in range(60)] and finite(r['objective']) and finite(r['backward_error']) and 0<=r['backward_error']<=1e-10,'all accepted solve diagnostics')
    else:
        exact(ms,('kind','grid_index','configuration','trees','node_count','rounded_endpoint_candidates','support_sha256'));need(ms['kind']=='trees' and ms['grid_index']==grid and ms['configuration']==GRID[grid] and ms['support_sha256']==model['support_sha256'] and type(ms['trees']) is list and len(ms['trees'])==256 and integer(ms['rounded_endpoint_candidates']),'all256 support-bound trees');total=0
        for nodes in ms['trees']:
            need(type(nodes) is list and len(nodes)>0,'complete tree');stack=[(0,0)];seen=set()
            while stack:
                idx,depth=stack.pop();need(integer(idx,0,len(nodes)-1) and idx not in seen and depth<=GRID[grid]['depth'],'acyclic complete finite tree');seen.add(idx);node=nodes[idx];leaf=node.get('feature') is None;exact(node,('feature','threshold','left','right','probability','rows','weight') if leaf else ('feature','threshold','left','right','probability','rows','weight','gain'))
                need(finite(node['probability']) and 0<=node['probability']<=1 and integer(node['rows'],1,n) and finite(node['weight']) and node['weight']>0,'finite tree node')
                if leaf:need(node['threshold'] is None and node['left'] is None and node['right'] is None,'terminal leaf')
                else:
                    need(integer(node['feature'],0,d-1) and sc['active'][node['feature']] and finite(node['threshold']) and finite(node['gain']) and node['gain']>0 and depth<GRID[grid]['depth'],'permitted positive split');stack.extend(((node['right'],depth+1),(node['left'],depth+1)))
            need(len(seen)==len(nodes) and nodes[0]['rows']==n,'all nodes reachable and all rows at root');total+=len(nodes)
        need(total==ms['node_count']<=io.limits['max_nodes'],'complete forest node accounting')

def infer(request,io,out,identity):
    # Fitted state/threshold read and authenticated before opening query metadata.
    need(request['model']['bytes']<=io.limits['max_model_bytes'],'whole model admission');model=io.json(request['model']);validate_model(model,identity,io);fit_receipt=io.json(request['fit_receipt'])
    exact(fit_receipt,('schema','source_identity','model','request','complete_training_rows','training_people','support_sha256','context','family','condition','grid_index','selection','selection_threshold','training_manifest','prepared_training_view','normalization','qualified'))
    need(fit_receipt['schema']=='neural010-fit-receipt-v1' and fit_receipt['model']==request['model'] and fit_receipt['source_identity']==identity and fit_receipt['qualified'] is False,'sealed exact fit receipt')
    for k in ('training_people','support_sha256','context','family','condition','grid_index','selection','selection_threshold','training_manifest','prepared_training_view','normalization'):need(fit_receipt[k]==model[k],'model/fit lineage '+k)
    need(fit_receipt['complete_training_rows']==model['state']['rows'],'all fitted rows')
    final=model['context']['inner_person'] is None;condition=model['condition'];threshold=model['selection_threshold']
    if condition=='signal_reference':need(request['threshold'] is None,'signal applies its fixed native amplitude threshold internally')
    elif final:need(type(request['threshold']) is float and request['threshold']==threshold,'only sealed selected final threshold')
    else:need(request['threshold'] is None,'inner inference emits raw probabilities only')
    normalized,query_manifest,normalization=normalize_worker(io,request['records'],request['feature_bindings'],'query',condition,model['context'],out,identity)
    rows=records(normalized,'query',condition);held=model['context']['outer_person'] if final else model['context']['inner_person'];need({r['patient_id'] for r in rows}=={held},'only frozen held person')
    trainids={r['recording_id'] for r in model['training_records']};need(not trainids.intersection(r['recording_id'] for r in rows),'disjoint full query records')
    if final:need(len(trainids)+len(rows)==686 and model['state']['rows']+sum(r['duration_seconds'] for r in rows)<=10000000,'complete original686 outer fold')
    np=numpy();n=sum(r['duration_seconds'] for r in rows);need(n<=io.limits['max_rows'],'complete query row admission');result=[]
    # Each record is storage only: frozen metadata vocabulary/scaler/state; no adaptation.
    for row in rows:
        d=row['duration_seconds']
        if model['family']=='strong':
            x=matrix([row],model['state']['vocabulary'],condition,io,identity);u=apply_scaler(x,model['state']['scaler']);del x;prob=predict_state(model['state']['state'],u);del u
        elif condition=='signal_reference':
            desc=authenticate_cache(io,row,condition,identity);a=load_array(io,desc,(d,),'float64');prob=(a>=threshold).astype(np.float64);del a
        else:prob=np.full(d,model['state']['prevalence_by_montage'].get(row['montage_id'],model['state']['fallback_prevalence']),dtype=np.float64)
        need(bool(np.isfinite(prob).all()) and bool(((prob>=0)&(prob<=1)).all()),'all complete finite probabilities')
        pp=save_array(io,out/(row['recording_id']+'.probabilities.npy'),prob);score=None;events=None
        if final:
            binary=(prob>=.5 if condition=='signal_reference' else prob>=threshold).astype(np.uint8);score=save_array(io,out/(row['recording_id']+'.scores.npy'),binary);events=event.from_scores([int(x) for x in binary],d)
        result.append({'recording_id':row['recording_id'],'patient_id':held,'duration_seconds':d,'probabilities':pp,'scores':score,'events':events})
    receipt={'schema':'neural010-predictions-v1','source_identity':identity,'model':request['model'],'fit_receipt':request['fit_receipt'],'query_manifest':query_manifest,'prepared_query_view':request['records'],'normalization':normalization,'context':model['context'],'family':model['family'],'condition':condition,'grid_index':model['grid_index'],'support_sha256':model['support_sha256'],'threshold':threshold if final else None,'threshold_kind':'amplitude' if condition=='signal_reference' else 'probability','records':result,'original_prediction_task_id':'NEURAL-009','qualification':False}
    return io.write_json(out/'PREDICTIONS.json',receipt)
