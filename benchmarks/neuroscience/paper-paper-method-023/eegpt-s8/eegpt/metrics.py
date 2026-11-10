"""Protected numerical reductions. Source construction never calls these.

Every observation is a full original event; biological clusters, folds and
three repeated fits remain distinct. Scientific workers run under the same
selected original resource observation as other producers.
"""
import math
import random
import sqlite3
from pathlib import Path
from .protocol import HandleCustody,boundary,guard,need,integer,finite,fields,identity,digest
from .scope import DATASETS,FOLDS,CONTROLS

MONITOR={d:('cohen_kappa' if d in ('BCIC-2A','Sleep-EDFx','TUEV') else 'auroc') for d in DATASETS}


class BinaryRankStore:
    """Disk-backed complete weighted binary ranking, no observation thinning."""
    def __init__(self,path):
        need(not Path(path).exists(),'fresh private numerical scratch database')
        self.connection=None
        with HandleCustody('original_rank_store_acquisition') as owned:
            connection=owned.own(sqlite3.connect(str(path)),'connection');connection.execute('PRAGMA journal_mode=DELETE');connection.execute('PRAGMA temp_store=FILE');connection.execute('PRAGMA cache_size=-8192')
            connection.execute('CREATE TABLE scores(p REAL NOT NULL, y INTEGER NOT NULL, w INTEGER NOT NULL)');self.count=0;self.connection=owned.release(connection)
    def add(self,p,y,w):self.connection.execute('INSERT INTO scores VALUES(?,?,?)',(p,y,w));self.count+=1
    def auc(self):
        self.connection.commit();positive=negative=0
        for y,w in self.connection.execute('SELECT y,SUM(w) FROM scores GROUP BY y'):
            if y==1:positive=w
            else:negative=w
        if not positive or not negative:return None
        before=0;numerator=0.
        for _,neg,pos in self.connection.execute('SELECT p,SUM(CASE WHEN y=0 THEN w ELSE 0 END),SUM(CASE WHEN y=1 THEN w ELSE 0 END) FROM scores GROUP BY p ORDER BY p'):
            numerator+=pos*(before+.5*neg);before+=neg
        return numerator/(positive*negative)
    def close(self):
        connection=self.connection;self.connection=None
        if connection is not None:connection.close()


def classify(rows,classes,*,rank_store=None):
    """rows=(semantic label, probabilities, integer cluster multiplicity)."""
    integer(classes,'fixed class count',2);matrix=[[0]*classes for _ in range(classes)];n=0;raw_n=0;loss=0.;brier=0.
    need((classes==2)==(rank_store is not None),'binary fullcase AUROC has concrete full ranking storage')
    for label,probability,weight in rows:
        integer(label,'semantic class',0,classes-1);integer(weight,'whole cluster multiplicity');need(len(probability)==classes,'full fixed semantic class vector')
        need(all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=1 for v in probability) and abs(math.fsum(probability)-1)<=1e-6,'validated full probability row')
        raw_n+=1
        if not weight:continue
        predicted=max(range(classes),key=lambda k:probability[k]);matrix[label][predicted]+=weight;n+=weight
        loss-=weight*math.log(max(1e-15,probability[label]));brier+=weight*math.fsum((p-(k==label))**2 for k,p in enumerate(probability))
        if rank_store is not None:rank_store.add(probability[1],label,weight)
    need(raw_n>0,'complete original nonempty case')
    support=[sum(row) for row in matrix];predicted_support=[sum(matrix[i][j] for i in range(classes)) for j in range(classes)];all_classes=all(support)
    if n:
        po=sum(matrix[k][k] for k in range(classes))/n;pe=sum(support[k]*predicted_support[k] for k in range(classes))/(n*n)
        kappa=None if pe==1 else (po-pe)/(1-pe)
        bac=sum(matrix[k][k]/support[k] for k in range(classes))/classes if all_classes else None
        f1=sum(support[k]*(2*matrix[k][k]/(support[k]+predicted_support[k]) if support[k]+predicted_support[k] else 0) for k in range(classes))/n
    else:po=kappa=bac=f1=None
    return {'rows':raw_n,'weighted_rows':n,'class_support':support,'predicted_support':predicted_support,'all_fixed_classes_present':all_classes,'confusion':matrix,'accuracy':po,'balanced_accuracy':bac,'cohen_kappa':kappa,'weighted_f1':f1,'auroc':None if rank_store is None else rank_store.auc(),'log_loss':loss/n if n else None,'brier':brier/n if n else None,'undefined_reason':None if n and all_classes else 'empty resample or absent fixed class; no completed-only or present-class replacement'}


def equal_fold_repetition(values,dataset,metric):
    need(set(values)==set(range(FOLDS[dataset])),'all original folds, including repeated Kaggle query people')
    need(all(set(row)=={0,1,2} for row in values.values()),'all3 original repetitions per fold')
    runs=[]
    for r in range(3):
        cells=[values[f][r][metric] for f in range(FOLDS[dataset])]
        if any(v is None for v in cells):runs.append(None)
        else:runs.append(math.fsum(finite(v,'complete case metric') for v in cells)/len(cells))
    if any(v is None for v in runs):return {'mean':None,'run_values':runs,'run_sd':None,'status':'unavailable','reason':'at least one original fold/run endpoint undefined'}
    mean=math.fsum(runs)/3;sd=math.sqrt(math.fsum((v-mean)**2 for v in runs)/2)
    return {'mean':mean,'run_values':runs,'run_sd':sd,'status':'complete','aggregation':'equal original folds within repetition, then equal three repetitions; sample SD ddof=1'}


def selected_reference(records,method_order=CONTROLS):
    """Same S_df mathematical rule; receipt/support admission is independent."""
    need(tuple(method_order)==CONTROLS and set(records)==set(CONTROLS),'all four fixed controls in prespecified tie order')
    means={}
    for method in CONTROLS:
        need(len(records[method])==3,'all three same-fold validation values')
        if any(v is None for v in records[method]):return {'status':'unavailable','selected':None,'means':None,'reason':'one original validation endpoint undefined'}
        means[method]=math.fsum(finite(v,'validation monitor') for v in records[method])/3
    selected=max(CONTROLS,key=lambda k:means[k]);return {'status':'selected','selected':selected,'means':means,'assessment_used':False,'tie_rule':list(CONTROLS)}


def percentile(values,q):
    need(values and 0<=q<=1,'nonempty valid bootstrap population');v=sorted(values);position=(len(v)-1)*q;lo=int(math.floor(position));hi=int(math.ceil(position));return v[lo]+(v[hi]-v[lo])*(position-lo)


def clustered_interval(people,evaluate,*,seed,replicates=2000,budget=None):
    """Resample whole person identities jointly across all their case blocks.

    evaluate is an internal closed scientific reducer bound to already captured
    matrices, not an accepted participant callback. The grader below supplies
    that closure. It never fits, selects S_df or calls participant code.
    """
    need(people and len(people)==len(set(people)) and replicates==2000,'full original person cluster set and2000 declared resamples');rng=random.Random(seed);values=[];invalid=0
    for _ in range(replicates):
        weights={p:0 for p in people}
        for _ in people:weights[people[rng.randrange(len(people))]]+=1
        result=boundary(budget, 'nested_evaluate', evaluate, weights, None)
        if result is None:invalid+=1
        else:values.append(finite(result,'paired bootstrap effect'))
    enough=len(values)/replicates>=.95
    return {'status':'complete' if enough else 'unavailable','interval':[percentile(values,.025),percentile(values,.975)] if enough else None,'valid':len(values),'invalid':invalid,'replicates':replicates,'unit':'whole person across all folds/repetitions/methods/arms','conditional_on_fitted_states_and_sealed_selections':True,'retraining_uncertainty':False,'seed':seed}


def method_swap(people,evaluate,observed,*,seed,qualification,budget=None):
    fields(qualification,('exchangeability_qualified','evidence','alternative'),'selected inferential assumptions')
    need(qualification['alternative']=='greater','prespecified one-sided improvement alternative')
    if not qualification['exchangeability_qualified'] or not qualification['evidence']:return {'status':'unavailable','p':None,'reason':'paired whole-person exchangeability is not independently qualified'}
    digest(qualification['evidence']);need(people and len(people)==len(set(people)),'full unique biological clusters')
    if observed is None:return {'status':'unavailable','p':None,'reason':'original paired endpoint undefined'}
    rng=random.Random(seed);n=len(people);exact=n<=16;count=(1<<n) if exact else 9999;exceed=0;invalid=0
    for i in range(count):
        swaps={p:bool((i>>j)&1) if exact else bool(rng.getrandbits(1)) for j,p in enumerate(people)}
        value=boundary(budget, 'nested_evaluate', evaluate, {p: 1 for p in people}, swaps)
        if value is None:invalid+=1
        elif value>=observed:exceed+=1
    if invalid:return {'status':'unavailable','p':None,'invalid':invalid,'reason':'fixed-family randomization contains undefined endpoint; no selective denominator'}
    return {'status':'complete','p':exceed/count if exact else (1+exceed)/(count+1),'enumerated':count,'exact':exact,'seed':seed,'observed_included':True,'unit':'whole person joint swap across original repeated support','qualification':qualification['evidence'],'fixed_selected_states_not_refitted':True}


def holm_complete(effects,expected_keys,alpha=.05):
    need(set(effects)==set(expected_keys),'complete fixed multiplicity family; no posthoc available subset')
    # None is a nonrejection bookkeeping sentinel, never a measured p=1.
    ordered=sorted(expected_keys,key=lambda k:(effects[k]['p'] is None,1. if effects[k]['p'] is None else effects[k]['p'],str(k)))
    out={};running=0.;stop=False;m=len(ordered)
    for rank,key in enumerate(ordered):
        p=effects[key]['p'];need(p is None or (type(p) in (int,float) and math.isfinite(p) and 0<=p<=1),'actual p or explicit unavailable')
        if p is None:out[key]={'raw_p':None,'adjusted_p':None,'reject':False,'status':'unavailable_nonrejection','family_size':m};stop=True;continue
        running=max(running,min(1.,(m-rank)*p));threshold=alpha/(m-rank);reject=not stop and p<=threshold
        if not reject:stop=True
        out[key]={'raw_p':p,'adjusted_p':running,'reject':reject,'status':'complete','family_size':m}
    return out


def effects_report(case_metrics,selections,paired_evidence,*,budget=None):
    """All seven selected-policy and28 fixed-control effects; no SOTA label."""
    need(set(case_metrics)==set(DATASETS) and set(selections)==set(DATASETS),'complete original seven-dataset comparison')
    effects={};fixed={}
    for dataset in DATASETS:
        methods=case_metrics[dataset];need(set(methods)=={'participant',*CONTROLS},'candidate plus all four independent complete controls');monitor=MONITOR[dataset]
        summaries={m:boundary(budget, 'nested_equal_fold_repetition', equal_fold_repetition, v, dataset, monitor) for m,v in methods.items()};selected={}
        need(set(selections[dataset])==set(range(FOLDS[dataset])),'every original S_df choice')
        for fold,choice in selections[dataset].items():
            if choice['status']!='selected':selected[fold]={r:{monitor:None} for r in range(3)}
            else:need(choice['selected'] in CONTROLS,'actual selected eligible control');selected[fold]=methods[choice['selected']][fold]
        baseline=boundary(budget, 'nested_equal_fold_repetition', equal_fold_repetition, selected, dataset, monitor);candidate=summaries['participant']
        delta=None if candidate['mean'] is None or baseline['mean'] is None else candidate['mean']-baseline['mean']
        effects[dataset]={'candidate':candidate,'reference':baseline,'delta':delta,'monitor':monitor,'reference_policy':'same-fold sealed4x3 validation selection','selection':selections[dataset],**paired_evidence['selected'][dataset]}
        for method in CONTROLS:
            b=summaries[method];key=dataset+'::'+method
            fixed[key]={'candidate':candidate,'reference':b,'delta':None if candidate['mean'] is None or b['mean'] is None else candidate['mean']-b['mean'],'monitor':monitor,**paired_evidence['fixed'][key]}
    selected_holm=boundary(budget, 'nested_holm_complete', holm_complete, {k: {'p': v['swap']['p']} for k, v in effects.items()}, DATASETS)
    fixed_holm=boundary(budget, 'nested_holm_complete', holm_complete, {k: {'p': v['swap']['p']} for k, v in fixed.items()}, [d + '::' + m for d in DATASETS for m in CONTROLS])
    return {'selected_effects':effects,'fixed_effects':fixed,'holm_selected7':selected_holm,'holm_fixed28':fixed_holm,'native_signal_understanding_inference':False,'clinical_or_causal_inference':False,'scientifically_qualified':False}
