"""Complete forty-session/1,320-phase support and separate scientific summaries."""
import math,re
from common import *
ROLES=('A','B','operator')
PURPOSES=('native','improvement')
REFERENCES=('bnb','logistic','constant')
NULLS=100

def validate_prepared(v):
    need(v['schema']=='foraging_full40_prepared_v1' and v['task_id']==TASK and len(v['records'])==40,'complete original forty-session preparation')
    rows=v['records'];need(len({r['session_id'] for r in rows})==len({r['source_session_token'] for r in rows})==40,'unique source sessions, not just forty files')
    need(v['complete_native_support']is True and v['complete_nested3_support']is True,'complete native and stronger improvement support; no fallback')
    for r in rows:
        need(re.fullmatch('[a-f0-9]{24}',r['session_id']) and r['native_supported']is True and r['nested3_supported']is True,'authentic complete case support')
        need(all(type(r[k])is int and r[k]>0 for k in ('source_R','rows','features')) and r['source_R']>=r['rows'] and r['features']%40==0,'complete source observation/feature dimensions')
        need(set(r['prepared'])=={'X.npy','y.npy','source_rows.npy','fold_ids.npy'} and len(r['folds'])==5,'complete typed inputs and five folds')
        test=[]
        for f,fold in enumerate(r['folds'],1):
            need(fold['fold']==f,'ordered original outer folds')
            tr,te,order,query=[fold[k] for k in ('train_positions0','test_positions0','train_order0','query_order0')]
            need(all(type(x)is int and 0<=x<r['rows'] for x in tr+te+order+query),'integer source-row mappings')
            need(tr==sorted(set(tr)) and te==sorted(set(te)) and set(tr).isdisjoint(te) and set(tr)|set(te)==set(range(r['rows'])),'full complementary outer-fold support')
            need(sorted(order)==tr and sorted(query)==te and tr and te,'exact independently permuted training/query rows');test.extend(te)
        need(sorted(test)==list(range(r['rows'])),'every original HW row tested exactly once')
    return rows

def phases(records,model_cap):
    need(type(model_cap)is int and model_cap>0,'explicit complete model cap');result=[]
    for r in records:
        for role in ROLES:result.append({'session_id':r['session_id'],'kind':'native','purpose':'native','role':role,'fold':0,'rows':r['rows'],'columns':101,'output_bytes':8*r['rows']*101})
        for f in r['folds']:
            for kind in ('fit','predict'):
                for role in ROLES:
                    rows=len(f['train_order0'] if kind=='fit' else f['query_order0']);columns=3 if role=='operator' else 1
                    result.append({'session_id':r['session_id'],'kind':kind,'purpose':'improvement','role':role,'fold':f['fold'],'rows':rows,'columns':columns,'output_bytes':model_cap if kind=='fit' else 8*rows*columns})
    need(len(result)==1320,'all 1,320 producer phases')
    for i,row in enumerate(result):row['index']=i;row['id']=f'{i:04d}-{row["kind"]}-{row["role"]}-{row["session_id"]}-f{row["fold"]}'
    return result

def resources(records,model_cap):
    h=sum(r['rows'] for r in records)
    return {'raw_numeric_source_component':sum(8*r['source_R']*(r['features']+1) for r in records),'prepared_HW_numeric_component':sum(8*r['rows']*(r['features']+4) for r in records),'three_native_output_numeric_bytes':3*8*101*h,'five_improvement_output_numeric_bytes':5*8*h,'all_sealed_model_ceiling_bytes':600*model_cap,'native_source_algorithm_fit_count_three_roles':60600,'operator_improvement_BNB_fits':200,'operator_improvement_logistic_fits':3800,'producer_phases':1320,'additional':'original archive/MATs, headers, stage copies, source and full-paper material copies, sparse/dense workspaces, journals, metadata, process/environment overhead, outer capture and OTHER','measured_feasibility':False}

def equal_sessions(values,records):
    need(set(values)=={r['session_id'] for r in records} and len(records)==40,'all forty session metrics')
    need(all(type(x)in(int,float) and math.isfinite(x) for x in values.values()),'finite complete metric');return math.fsum(values.values())/40

def animal_description(values,records,mapping):
    if mapping is None:return {'available':False,'reason':'complete authenticated session-to-animal mapping absent','independent_animals_inferred':False}
    need(mapping['schema']=='foraging_authenticated_five_animal_mapping_v1' and mapping['independently_authenticated']is True and mapping['source_rows_are_not_animals']is True,'independent biological mapping required')
    m=mapping['sessions'];need(set(m)=={r['session_id'] for r in records} and len(set(m.values()))==5 and all(type(a)is str and a for a in m.values()),'every session mapped to five original animals')
    groups={}
    for sid,a in m.items():groups.setdefault(a,[]).append(values[sid])
    means={a:math.fsum(x)/len(x) for a,x in groups.items()};loo={a:math.fsum(v for key,v in means.items() if key!=a)/4 for a in means}
    return {'available':True,'animal_means':means,'equal_animal_descriptive_mean':math.fsum(means.values())/5,'leave_one_animal_out_equal_animal_means':loo,'descriptive_stability_range':[min(loo.values()),max(loo.values())],'population_confidence_interval':None,'biological_significance_claim':False}
