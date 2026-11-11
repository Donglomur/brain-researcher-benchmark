"""Protected native Bernoulli log loss and explicit paired descriptive summaries."""
import math
from .domain import need,real,tagged,CATEGORIES,PEOPLE,MODES,PANELS,cell_key,prediction

def bernoulli_row(probabilities,target):
    need(type(target) in (list,tuple) and len(target)==CATEGORIES and all(type(y) is int and y in (0,1) for y in target),'exact complete multilabel truth')
    losses=[]
    for p,y in zip(probabilities,target):
        need(0<=real(p)<=1,'finite Bernoulli probability')
        losses.append(math.inf if (y==1 and p==0) or (y==0 and p==1) else -math.log(p) if y else -math.log1p(-p))
    return sum(losses)/CATEGORIES

def score_cell(pred,query_ids,cell,fit_sha,category_sha,private_rows):
    prediction(pred,query_ids,cell,fit_sha);need(pred['category_schema_sha256']==category_sha,'same original taxonomy schema')
    need(type(private_rows) is list and [r['query_id'] for r in private_rows]==list(query_ids),'exact protected row order')
    by={};unsupported=[]
    for p,r in zip(pred['probabilities'],private_rows):
        if r['target'] is None:unsupported.append(r['query_id']);continue
        by.setdefault(r['concept_id'],[]).append(bernoulli_row(p,r['target']))
    need(bool(by),'supported query concepts exist; empty support refuses')
    concept={k:sum(v)/len(v) for k,v in sorted(by.items())}
    loss=sum(concept.values())/len(concept)
    return {'cell':cell,'loss':tagged(loss),'concept_loss':{k:tagged(v) for k,v in concept.items()},'scored_concepts':len(concept),'query_rows':len(query_ids),'unsupported_query_ids':unsupported,'categories':CATEGORIES,'unit':'nats_per_category','repeat_unit':'one 80-repeat mean per original query image'}

def finite_value(tag):
    need(tag['status']=='finite','finite paired uncertainty requires finite original losses')
    return tag['value']

def native_summary(scores):
    need(len(scores)==80 and len({cell_key(s['cell']) for s in scores})==80,'whole score collection')
    out=[]
    for mode in MODES:
        rows=[s for s in scores if s['cell']['mode']==mode and s['cell']['panel']=='LATE']
        need({r['cell']['person'] for r in rows}==set(PEOPLE),'ten equal-person primary losses')
        loss=math.inf if any(r['loss']['status']=='positive_infinity' for r in rows) else sum(finite_value(r['loss']) for r in rows)/10
        out.append({'mode':mode,'primary_loss':tagged(loss),'direction':'lower','unit':'nats_per_category','person_denominator':10,'category_denominator':53,'concept_denominators':{r['cell']['person']:r['scored_concepts'] for r in rows},'participant_BASE_not_a_reward_term':True})
    return out

def independent_comparisons(reference,candidate):
    ri={cell_key(s['cell']):s for s in reference};ci={cell_key(s['cell']):s for s in candidate}
    need(len(reference)==len(candidate)==len(ri)==len(ci)==80,'two independently complete fixed collections')
    out=[]
    for mode in MODES:
        for comparator in ('BASE','LATE'):
            rows=[]
            for p in PEOPLE:
                r=ri[f'{p}/{mode}/{comparator}'];c=ci[f'{p}/{mode}/LATE']
                need(set(r['concept_loss'])==set(c['concept_loss']) and r['unsupported_query_ids']==c['unsupported_query_ids'],'independent comparator has exact same scored support')
                rows.append((p,r,c))
            finite=all(s['loss']['status']=='finite' for _,r,c in rows for s in (r,c))
            out.append({'mode':mode,'candidate_panel':'LATE','independent_reference_panel':comparator,'status':'finite' if finite else 'nonfinite_loss','reference_minus_candidate':sum(finite_value(r['loss'])-finite_value(c['loss']) for _,r,c in rows)/10 if finite else None,'unit':'nats_per_category','people':10,'participant_BASE_used_as_reward':False})
    return out

def paired_summary(scores):
    need(len(scores)==80 and {cell_key(s['cell']) for s in scores}=={f'{p}/{m}/{x}' for p in PEOPLE for m in MODES for x in PANELS},'complete programme before reporting')
    index={cell_key(s['cell']):s for s in scores};out=[]
    for mode in MODES:
        rows=[];concepts=None
        for person in PEOPLE:
            b=index[f'{person}/{mode}/BASE'];a=index[f'{person}/{mode}/LATE']
            need(set(b['concept_loss'])==set(a['concept_loss']) and b['unsupported_query_ids']==a['unsupported_query_ids'],'matched same-person concept support')
            if concepts is None:concepts=set(b['concept_loss'])
            need(concepts==set(b['concept_loss']),'same concept support across all people')
            rows.append((person,b,a))
        if any(s['loss']['status']!='finite' for _,b,a in rows for s in (b,a)):
            out.append({'mode':mode,'status':'nonfinite_loss','gain':None,'uncertainty':None,'people':10,'reason':'retained exact infinite native losses; no clipping or finite surrogate'});continue
        gains=[finite_value(b['loss'])-finite_value(a['loss']) for _,b,a in rows]
        mean=sum(gains)/10;sem=math.sqrt(sum((v-mean)**2 for v in gains)/(9*10))
        cg={c:sum(finite_value(b['concept_loss'][c])-finite_value(a['concept_loss'][c]) for _,b,a in rows)/10 for c in sorted(concepts)}
        n=len(cg);csem=None if n<2 else math.sqrt(sum((v-mean)**2 for v in cg.values())/(n*(n-1)))
        out.append({'mode':mode,'status':'finite','gain_nats_per_category':mean,'person_gains':dict(zip(PEOPLE,gains)),'person_sem_ddof1':sem,'person_t9_descriptive_interval':[mean-2.2621571627409915*sem,mean+2.2621571627409915*sem],'concept_means':cg,'concept_sem_ddof1':csem,'people':10,'concepts':n,'categories':53,'interpretation':'paired descriptive predictive gain on fixed public corpus; crossed person/concept dependence retained, not causal inference'})
    return out
