"""Independent NEURAL-094 arithmetic from actual paired probabilities.

No IO, model, native imports, target loader, fit callback, or metric-valued callback.
The parent authenticates source/support/custody and the complete producer barrier
before supplying private targets. This module is not an authorization interface.
"""
from dataclasses import dataclass
import hashlib
import itertools
import json
import math
import numbers

CANONICAL_SHA256='27a86a0d3065c06f9d2b7b509bc0ee3b0775cf3b58b810a917c4aba37d7f2e66'
SEEDS=(2026110700,2026110701,2026110702,2026110703,2026110704)
CLASS_ORDER=('right','NoGo','left')
ABSOLUTE=('natural_log_loss','multiclass_Brier_mean_sum3','top1_accuracy')
REGIONAL_VIEWS=('common_context','candidate_left','candidate_right','regional_reference_left','regional_reference_right')
WHOLE_VIEWS=('candidate:context_wheel','candidate:context_wheel_neural','trusted:training_prior','trusted:selected_context','trusted:matched_context_logistic','trusted:matched_joint_logistic')
WHOLE_CONTRASTS={
 'primary_trusted_context_minus_candidate_joint':('trusted:selected_context','candidate:context_wheel_neural'),
 'candidate_context_minus_candidate_joint':('candidate:context_wheel','candidate:context_wheel_neural'),
 'matched_reference_context_minus_joint':('trusted:matched_context_logistic','trusted:matched_joint_logistic'),
 'trusted_selected_context_minus_matched_joint':('trusted:selected_context','trusted:matched_joint_logistic')}


def need(ok,reason):
    if not ok: raise ValueError(reason)


def extended(value):
    if math.isnan(value): return {'status':'undefined','value':None}
    if math.isinf(value): return {'status':'positive_infinity' if value>0 else 'negative_infinity','value':None}
    return {'status':'finite','value':float(value)}


def number(value):
    need(type(value)is dict and set(value)=={'status','value'},'exact extended scalar')
    if value['status']=='finite':
        need(type(value['value'])in(int,float) and math.isfinite(value['value']),'finite extended scalar'); return float(value['value'])
    need(value['value'] is None and value['status'] in ('undefined','positive_infinity','negative_infinity'),'typed nonfinite scalar')
    return {'undefined':math.nan,'positive_infinity':math.inf,'negative_infinity':-math.inf}[value['status']]


def assert_engineering_equivalent(left,right):
    """Independent-bank check only; never a scientific improvement threshold.

    Support and status checks belong to their exact schemas. Finite values must
    have exactly the same sign, including exact zero, before abs+rel1e-12 is used.
    """
    x,y=number(left),number(right)
    need(left['status']==right['status'],'exact nonfinite/status agreement')
    if left['status']=='finite':
        need((x>0)-(x<0)==(y>0)-(y<0),'exact effect sign and zero agreement')
        need(math.isclose(x,y,rel_tol=1e-12,abs_tol=1e-12),'finite engineering agreement')
    return True


class _Mean:
    """Finite floating expansion plus exact nonfinite-state propagation.

    Retain nonoverlapping finite partials rather than a single compensated sum,
    so large cancellation cannot erase a smaller signed trial contribution.
    """
    def __init__(self): self.n=0;self.partials=[];self.nan=False;self.pos=False;self.neg=False;self.causes=set()
    def add(self,value,causes=()):
        self.n+=1
        if math.isnan(value): self.nan=True;self.causes.update(causes or ('undefined_required_operand',))
        elif math.isinf(value):
            if value>0:self.pos=True
            else:self.neg=True
        else:
            x=value;index=0
            for y in self.partials:
                if abs(x)<abs(y):x,y=y,x
                hi=x+y;lo=y-(hi-x)
                if lo:self.partials[index]=lo;index+=1
                x=hi
            self.partials[index:]=[x]
    def reasons(self):
        return sorted(self.causes | ({'mixed_signed_infinities'} if self.pos and self.neg else set()))
    def value(self):
        if not self.n or self.nan or (self.pos and self.neg):return math.nan
        if self.pos:return math.inf
        if self.neg:return -math.inf
        return math.fsum(self.partials)/self.n


def _avg(values):
    m=_Mean()
    for value in values:m.add(number(value))
    return extended(m.value())


@dataclass(frozen=True)
class Catalog:
    """Trusted immutable metadata; only canonical loader is production admission."""
    labels:tuple
    sessions:tuple  # (ordinal, session identity, mouse identity)
    mice:tuple
    source_sha256:str
    @property
    def pair_count(self):return len(self.labels)*(len(self.labels)-1)//2
    def pairs(self):return itertools.combinations(self.labels,2)


def catalog_from_canonical(raw):
    need(type(raw)is bytes and hashlib.sha256(raw).hexdigest()==CANONICAL_SHA256,'fixed canonical bytes')
    x=json.loads(raw)
    need(x['schema']=='neural094_pairwise_canonical_inventory_v1' and x['task']=='NEURAL-094' and x['original_whole_population_task_unchanged']is True,'canonical scope')
    labels=tuple(r['raw_label'] for r in x['labels']);sessions=tuple((s['ordinal'],s['session'],s['mouse']) for s in x['sessions']);mice=tuple(x['mice'])
    need(len(labels)==73 and labels==tuple(sorted(set(labels))) and len(sessions)==39 and len(mice)==10 and tuple(x['fixed_seeds'])==SEEDS,'full fixed scientific roster')
    need(tuple(s[0] for s in sessions)==tuple(range(1,40)) and len({s[1] for s in sessions})==39 and set(s[2] for s in sessions)==set(mice),'fixed nesting')
    return Catalog(labels,sessions,mice,CANONICAL_SHA256)


def _catalog_valid(c):
    need(type(c)is Catalog and type(c.labels)is tuple and type(c.sessions)is tuple and type(c.mice)is tuple and all(type(s)is tuple and len(s)==3 and type(s[0])is int and type(s[1])is str and type(s[2])is str for s in c.sessions) and len(c.labels)>=2 and c.labels==tuple(sorted(set(c.labels))) and len(c.sessions)>0 and c.mice==tuple(dict.fromkeys(s[2] for s in c.sessions)),'immutable ordered catalog')
    need(tuple(s[0] for s in c.sessions)==tuple(range(1,len(c.sessions)+1)) and len({s[1] for s in c.sessions})==len(c.sessions),'complete session identities')


def _probability(row):
    need(hasattr(row,'__len__') and len(row)==3,'three probability columns')
    need(all(isinstance(x,numbers.Real) and not isinstance(x,bool) for x in row),'numeric nonboolean probabilities')
    p=tuple(float(x) for x in row)
    need(all(math.isfinite(x) and 0<=x<=1 for x in p),'closed finite probability interval')
    total=sum(p);need(abs(total-1)<=1e-8,'inherited probability sum tolerance')
    return tuple(x/total for x in p)


def _contrast_specs(regional):
    if not regional:return {name:('natural_log_loss',left,right,1) for name,(left,right) in WHOLE_CONTRASTS.items()}
    out={}
    for side in ('left','right'):
        for reference,view in (('common_context','common_context'),('own_regional_reference','regional_reference_'+side)):
            for metric in ABSOLUTE:
                # Loss/Brier smaller is better; accuracy larger is better.
                out[side+'_gain_over_'+reference+'__'+metric]=(metric,view,'candidate_'+side,-1 if metric=='top1_accuracy' else 1)
    out['direct_right_minus_left_natural_log_loss']=('natural_log_loss','candidate_right','candidate_left',1)
    return out


def _empty_pack(view_names,specs):
    return {'absolute':{v:{metric:extended(math.nan) for metric in ABSOLUTE} for v in view_names},'contrasts':{name:extended(math.nan) for name in specs},'undefined_causes':{**{f'absolute/{v}/{m}':['required_execution_failure'] for v in view_names for m in ABSOLUTE},**{f'contrasts/{name}':['required_execution_failure'] for name in specs}}}


def _mean_packs(packs,view_names,specs):
    need(len(packs)>0,'nonempty structural denominator'); causes={}
    def avg(path,values):
        acc=_Mean()
        for p,value in zip(packs,values,strict=True):acc.add(number(value),p['undefined_causes'].get(path,()))
        if acc.reasons():causes[path]=acc.reasons()
        return extended(acc.value())
    absolute={view:{metric:avg(f'absolute/{view}/{metric}',[p['absolute'][view][metric] for p in packs]) for metric in ABSOLUTE} for view in view_names}
    contrasts={name:avg(f'contrasts/{name}',[p['contrasts'][name] for p in packs]) for name in specs}
    return {'absolute':absolute,'contrasts':contrasts,'undefined_causes':causes}


def _trial_key(tokens,targets):
    h=hashlib.sha256()
    for token,target in zip(tokens,targets,strict=True):
        raw=token.encode('utf-8');h.update(len(raw).to_bytes(8,'big'));h.update(raw);h.update(bytes((int(target),)))
    return h.hexdigest()


def paired_trial_metrics(tokens,targets,views,*,regional=True):
    """Real numerical bank; every view carries identical ordered trial identities.

    views[name] = {'tokens': sequence, 'probabilities': sequence of three-column
    rows}. Target column semantics have already been established by private
    admission; they are not inferred from stimulus or wheel here.
    """
    required=REGIONAL_VIEWS if regional else WHOLE_VIEWS
    need(type(views)is dict and set(views)==set(required),'complete exact probability views')
    tokens=tuple(tokens);need(tokens and len(set(tokens))==len(tokens) and all(type(t)is str and t for t in tokens),'complete unique paired trial identities')
    need(len(targets)==len(tokens) and all(isinstance(y,numbers.Integral) and not isinstance(y,bool) and 0<=int(y)<3 for y in targets),'final right NoGo left targets')
    for view in required:
        v=views[view];need(type(v)is dict and set(v)=={'tokens','probabilities'} and tuple(v['tokens'])==tokens and len(v['probabilities'])==len(tokens),'exact same-trial view alignment')
    names=required if regional else required+('analytic:uniform',)
    specs=_contrast_specs(regional)
    acc={v:{m:_Mean() for m in ABSOLUTE} for v in names};delta={k:_Mean() for k in specs}
    diagnostics={v:{'confusion_true_rows_predicted_columns':[[0]*3 for _ in range(3)],'zero_true_class_probability_rows':0} for v in names};counts=[0,0,0]
    for i,target in enumerate(targets):
        y=int(target);counts[y]+=1;values={}
        for name in names:
            p=(1/3,1/3,1/3) if name=='analytic:uniform' else _probability(views[name]['probabilities'][i])
            chosen=p[y];loss=math.inf if chosen==0 else -math.log(chosen)
            predicted=max(range(3),key=lambda j:p[j])
            metric={'natural_log_loss':loss,'multiclass_Brier_mean_sum3':sum((p[j]-(j==y))**2 for j in range(3)),'top1_accuracy':float(predicted==y)}
            values[name]=metric
            for key,value in metric.items():acc[name][key].add(value)
            diagnostics[name]['confusion_true_rows_predicted_columns'][y][predicted]+=1
            diagnostics[name]['zero_true_class_probability_rows']+=int(chosen==0)
        for name,(metric,left,right,sign) in specs.items():delta[name].add(sign*(values[left][metric]-values[right][metric]),('paired_inf_minus_inf',))
    for name in names:
        confusion=diagnostics[name]['confusion_true_rows_predicted_columns']
        recalls=[confusion[j][j]/counts[j] if counts[j] else None for j in range(3)]
        diagnostics[name]['class_recall']=recalls
        diagnostics[name]['macro_recall']=extended(sum(recalls)/3) if all(counts) else {'status':'undefined_missing_query_class','value':None}
    pack={'absolute':{v:{m:extended(acc[v][m].value()) for m in ABSOLUTE} for v in names},'contrasts':{k:extended(delta[k].value()) for k in specs},'undefined_causes':{f'contrasts/{k}':delta[k].reasons() for k in specs if delta[k].reasons()}}
    if not regional:pack['absolute']['analytic:uniform']['natural_log_loss']=extended(math.log(3.))
    return {'query_rows':len(tokens),'class_order':list(CLASS_ORDER),'class_counts':counts,'metrics':pack,'diagnostics':diagnostics,'tie_break':'first class in right,NoGo,left order','paired_trial_differences_before_averaging':True,'averaged_probabilities_across_seeds':False}


def _support(catalog,row):
    """Freeze actual support_plan pair row before any outcome is supplied."""
    _catalog_valid(catalog)
    need(type(row)is dict and row['schema']=='neural094_pairwise_support_row_v1' and type(row['pair_index'])is int and 0<=row['pair_index']<catalog.pair_count,'source pair index')
    labels=next(itertools.islice(catalog.pairs(),row['pair_index'],None))
    need((row['left_literal_label'],row['right_literal_label'])==labels and row['orientation']=='right_log_loss_minus_left_log_loss; positive_favors_left_descriptive_only','exact literal pair and orientation')
    need(type(row['fixed_seeds'])is list and all(type(s)is int for s in row['fixed_seeds']) and tuple(row['fixed_seeds'])==SEEDS and row['execution_failures_may_change_support_denominator']is False and row['score_or_positive_effect_reward']is None,'fixed seed/support/no reward policy')
    sessions=row['session_roster'];mice=row['mouse_roster']
    need(len(sessions)==len(catalog.sessions) and len(mice)==len(catalog.mice),'all structural positions')
    ks=[];statuses=[]
    for expected,r in zip(catalog.sessions,sessions,strict=True):
        need((r['ordinal'],r['session'],r['mouse'])==expected and type(r['ordinal'])is int,'same ordered source session')
        left,right=r['left_QC2_QC3'],r['right_QC2_QC3']
        need(type(left)is list and type(right)is list and len(left)==len(right)==2 and all(type(x)is int and x>=0 for x in left+right),'frozen regional counts')
        nleft,nright=sum(left),sum(right);k=min(nleft,nright)
        status='supported_pending_execution' if k else 'unavailable_both_regions' if not(nleft or nright) else 'unavailable_left_region' if not nleft else 'unavailable_right_region'
        need(type(r['K'])is int and r['K']==k and r['structural_status']==status and r['same_original_trials_window_context_wheel_required']is True,'structural K and status')
        ks.append(k);statuses.append(status)
    mask=tuple(k>0 for k in ks)
    need(type(row['session_support_mask'])is list and all(type(x)is bool for x in row['session_support_mask']) and row['session_support_mask']==list(mask) and type(row['n_session'])is int and row['n_session']==sum(mask),'fixed session support denominator')
    mouse_mask=[]
    for name,r in zip(catalog.mice,mice,strict=True):
        planned=[s[0] for s,k in zip(catalog.sessions,ks,strict=True) if s[2]==name and k>0]
        need(r['mouse']==name and r['planned_session_ordinals']==planned and type(r['n_sessions'])is int and r['n_sessions']==len(planned) and r['structurally_supported']is bool(planned),'fixed mouse nesting')
        mouse_mask.append(bool(planned))
    need(type(row['mouse_support_mask'])is list and all(type(x)is bool for x in row['mouse_support_mask']) and row['mouse_support_mask']==mouse_mask and type(row['n_mouse'])is int and row['n_mouse']==sum(mouse_mask),'fixed mouse support denominator')
    return row['pair_index'],labels,tuple(ks),tuple(statuses)


class RegionalPair:
    """One pair/mode scalar reducer. Missing work cannot improve the denominator."""
    def __init__(self,catalog,support_row,mode):
        need(type(mode)is str and mode in ('F','I'),'selected candidate mode')
        self.catalog=catalog;self.mode=mode
        self.index,self.labels,self.ks,self.statuses=_support(catalog,support_row)
        self.results={};self.trial_keys={};self.closed=False
    def _slot(self,ordinal,seed):
        need(not self.closed and type(ordinal)is int and 1<=ordinal<=len(self.catalog.sessions) and self.ks[ordinal-1]>0,'planned supported session')
        need(type(seed)is int and seed in SEEDS and (ordinal,seed) not in self.results,'unique fixed seed slot')
        return ordinal,seed
    def add_seed(self,ordinal,seed,tokens,targets,views):
        slot=self._slot(ordinal,seed)
        # Actual arithmetic, not a caller supplied score or summary.
        result=paired_trial_metrics(tokens,targets,views,regional=True);key=_trial_key(tokens,targets)
        need(ordinal not in self.trial_keys or self.trial_keys[ordinal]==key,'identical original trials and targets across all seeds')
        self.trial_keys[ordinal]=key
        self.results[slot]={'seed':seed,'execution_status':'complete','failure_reason':None,**result}
    def fail_seed(self,ordinal,seed,reason):
        slot=self._slot(ordinal,seed);need(type(reason)is str and 0<len(reason)<=1000,'bounded explicit failure reason')
        self.results[slot]={'seed':seed,'execution_status':'failed','failure_reason':reason,'metrics':_empty_pack(REGIONAL_VIEWS,_contrast_specs(True))}
    def finish(self):
        need(not self.closed,'one finalized pair');self.closed=True
        specs=_contrast_specs(True);sessions=[]
        for (ordinal,name,mouse),k,status in zip(self.catalog.sessions,self.ks,self.statuses,strict=True):
            if not k:
                seeds=[{'seed':s,'execution_status':'structurally_unavailable','failure_reason':None} for s in SEEDS];pack=None;execution='not_applicable'
            else:
                seeds=[self.results.get((ordinal,s),{'seed':s,'execution_status':'missing_required_output','failure_reason':'planned seed was not supplied','metrics':_empty_pack(REGIONAL_VIEWS,specs)}) for s in SEEDS]
                pack=_mean_packs([s['metrics'] for s in seeds],REGIONAL_VIEWS,specs)
                execution='complete' if all(s['execution_status']=='complete' for s in seeds) else 'incomplete_required_execution'
                counts={s['query_rows'] for s in seeds if s['execution_status']=='complete'}
                need(len(counts)<=1,'same trial count across five seeds')
            sessions.append({'ordinal':ordinal,'session':name,'mouse':mouse,'K':k,'structural_status':status,'execution_status':execution,'planned_seed_count':5 if k else 0,'seed_status_positions':5,'seeds':seeds,'metrics':pack})
        mice=[]
        for mouse in self.catalog.mice:
            rows=[r for r in sessions if r['mouse']==mouse and r['K']>0]
            mice.append({'mouse':mouse,'structurally_supported':bool(rows),'planned_session_ordinals':[r['ordinal'] for r in rows],'n_sessions':len(rows),'execution_status':'structurally_unavailable' if not rows else 'complete' if all(r['execution_status']=='complete' for r in rows) else 'incomplete_required_execution','metrics':_mean_packs([r['metrics'] for r in rows],REGIONAL_VIEWS,specs) if rows else None})
        supported=[r for r in mice if r['structurally_supported']]
        return {'schema':'neural094_regional_pair_arithmetic_v1','mode':self.mode,'pair_index':self.index,'left_literal_label':self.labels[0],'right_literal_label':self.labels[1],'orientation':'right_log_loss_minus_left_log_loss; positive_favors_left_descriptive_only','session_records':sessions,'mouse_records':mice,'n_session':sum(k>0 for k in self.ks),'n_mouse':len(supported),'session_support_mask':[k>0 for k in self.ks],'mouse_support_mask':[r['structurally_supported'] for r in mice],'structural_status':'supported' if supported else 'structurally_unavailable_all_sessions','execution_status':'not_applicable' if not supported else 'complete' if all(r['execution_status']=='complete' for r in supported) else 'incomplete_required_execution','metrics':_mean_packs([r['metrics'] for r in supported],REGIONAL_VIEWS,specs) if supported else None,'fixed_seeds':list(SEEDS),'execution_failures_may_change_support_denominator':False,'probabilities_averaged_across_seeds':False,'score_or_positive_effect_reward':None,'uncertainty':{'status':'not_selected','bootstrap_performed':False,'significance_claim':False},'execution_authority':False,'scientific_qualification':False}


def iter_complete_pairs(catalog,reports,*,mode):
    """Streaming integrity check; caller keeps output private until exhaustion.

    Reports must originate from this arithmetic path and source-bound study.
    This structural iterator alone cannot authenticate their scientific origin.
    """
    _catalog_valid(catalog);need(type(mode)is str and mode in ('F','I'),'selected mode');iterator=iter(reports)
    for index,labels in enumerate(catalog.pairs()):
        try:r=next(iterator)
        except StopIteration as e:raise ValueError('missing required regional pair') from e
        need(r['schema']=='neural094_regional_pair_arithmetic_v1' and r['pair_index']==index and (r['left_literal_label'],r['right_literal_label'])==labels and r['mode']==mode,'complete ordered pair family')
        need([(x['ordinal'],x['session'],x['mouse']) for x in r['session_records']]==list(catalog.sessions) and [x['mouse'] for x in r['mouse_records']]==list(catalog.mice),'all session and mouse status positions')
        need(all(len(x['seeds'])==5 and [s['seed'] for s in x['seeds']]==list(SEEDS) for x in r['session_records']),'all seed status positions')
        yield r
    sentinel=object();need(next(iterator,sentinel)is sentinel,'extra regional pair refused')


class WholePrimary:
    """Independent check of original all39/10 primary; never a regional reward."""
    def __init__(self,catalog,mode):
        _catalog_valid(catalog);need(mode in ('F','I'),'selected mode');self.catalog=catalog;self.mode=mode;self.rows={};self.closed=False
    def _slot(self,ordinal):
        need(not self.closed and type(ordinal)is int and 1<=ordinal<=len(self.catalog.sessions) and ordinal not in self.rows,'one required whole session')
    def add_session(self,ordinal,tokens,targets,views):
        self._slot(ordinal);self.rows[ordinal]={'execution_status':'complete','failure_reason':None,**paired_trial_metrics(tokens,targets,views,regional=False)}
    def fail_session(self,ordinal,reason):
        self._slot(ordinal);need(type(reason)is str and 0<len(reason)<=1000,'explicit bounded whole failure');self.rows[ordinal]={'execution_status':'failed','failure_reason':reason,'metrics':_empty_pack(WHOLE_VIEWS+('analytic:uniform',),_contrast_specs(False))}
    def finish(self):
        need(not self.closed,'one whole result');self.closed=True;names=WHOLE_VIEWS+('analytic:uniform',);specs=_contrast_specs(False)
        sessions=[]
        for ordinal,session,mouse in self.catalog.sessions:
            r=self.rows.get(ordinal,{'execution_status':'missing_required_output','failure_reason':'planned whole session not supplied','metrics':_empty_pack(names,specs)})
            sessions.append({'ordinal':ordinal,'session':session,'mouse':mouse,**r})
        mice=[]
        for mouse in self.catalog.mice:
            rows=[r for r in sessions if r['mouse']==mouse]
            mice.append({'mouse':mouse,'n_sessions':len(rows),'session_ordinals':[r['ordinal'] for r in rows],'execution_status':'complete' if all(r['execution_status']=='complete' for r in rows) else 'incomplete_required_execution','metrics':_mean_packs([r['metrics'] for r in rows],names,specs)})
        return {'schema':'neural094_independent_whole_primary_arithmetic_v1','mode':self.mode,'session_records':sessions,'mouse_records':mice,'required_sessions':len(sessions),'required_mice':len(mice),'metrics':_mean_packs([r['metrics'] for r in mice],names,specs),'primary_contrast':'primary_trusted_context_minus_candidate_joint','execution_status':'complete' if all(r['execution_status']=='complete' for r in sessions) else 'incomplete_required_execution','subset_renormalization':False,'regional_substitution_for_primary':False,'uncertainty':{'status':'not_selected','bootstrap_performed':False,'significance_claim':False},'execution_authority':False,'scientific_qualification':False}
