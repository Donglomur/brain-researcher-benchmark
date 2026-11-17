"""Complete trusted report reductions; numerical routines require separate qualification."""
import itertools
import math
from .errors import require
from .objects import fields,canonical,digest
from . import metrics
from .reporting import source_aggregate

SOURCE_TABLES={2:('primary',('TUAB','TUEV','PhysioNet-MI','BCIC-IV-2a','FACED','ISRUC','Mumtaz2016','MentalArithmetic','BCIC2020-3')),
 4:('linear_probe',('Mumtaz2016','MentalArithmetic','TUAB','PhysioNet-MI','BCIC-IV-2a','ISRUC','HMC','BCIC2020-3','TUEV','FACED')),
 18:('masking',('Mumtaz2016','TUAB','ISRUC','HMC','BCIC2020-3','TUEV','PhysioNet-MI','FACED')),
 19:('position_and_mask_components',('PhysioNet-MI','MentalArithmetic')),
 20:('activation_normalization',('BCIC-IV-2a','TUEV','PhysioNet-MI'))}
PROTECTED_METRICS=('balanced_accuracy','cohen_kappa','weighted_f1','auroc','average_precision','pr_trapezoid','brier','negative_log_likelihood','clipped_target_probabilities')

def validate_reduction_plan(plan,scope):
    r=plan['scientific_reductions']
    fields(r,('schema','bootstrap_seed','auc_pr_profiles','soup_studies','direct_AB'))
    require(r['schema']=='reve-complete-reduction-plan-v2' and type(r['bootstrap_seed'])is int,'selected reduction recipe')
    require(set(r['auc_pr_profiles'])=={'R-paper','R-native'},'explicit original AUC-PR ABI dispositions')
    for profile in r['auc_pr_profiles'].values():
        fields(profile,('metric','qualification'))
        require(profile['metric'] in (None,'average_precision','pr_trapezoid'),'named AUC-PR identity')
        require(profile['metric'] is None or profile['qualification'],'source AUC-PR convention qualification')
    expected={k for k,v in plan['required_products'].items() if v['kind']=='soup'}
    require({x['product'] for x in r['soup_studies']}==expected and len(r['soup_studies'])==len(expected) and expected,'every mandatory soup study')
    from .scientific_identity import soup_union
    actual=set();programmes={p['id']:p for p in plan['programmes']}
    for row in r['soup_studies']:
        fields(row,('product','programme','dataset','size','purpose','run','soup_group','member_groups','validation_groups','validation_target','test_target','selection_metric','selection_rule','recipe','arm'))
        product=plan['required_products'][row['product']]
        require(row['size'] in ('Small','Base','Large') and row['programme']==product['programme'],'soup programme/model size')
        n=product['member_count']
        key=(row['programme'],row['arm'],row['purpose'],row['dataset'],row['size'],row['run'],n,row['recipe'])
        require(key not in actual and row['arm']==programmes[row['programme']]['arm'],'unique soup study arm identity')
        actual.add(key)
        require(product.get('soup_study')==list(key),'soup producer full scientific identity')
        require(n==5 or (n==10 and row['dataset']=='TUEV' and row['size']=='Base'),'five for all studies and additional Base/TUEV ten')
        require(len(row['member_groups'])==len(row['validation_groups'])==n and len(set(row['member_groups']))==n and len(set(row['validation_groups']))==n,'every member query/validation prediction')
        require(row['selection_rule']=='validation_only_first_chronological' and row['selection_metric']=='balanced_accuracy','precommitted single-best policy')
        for gid in [row['soup_group'],*row['member_groups'],*row['validation_groups']]:
            g=plan['prediction_groups'][gid]
            require(g['programme']==row['programme'] and g['dataset']==row['dataset'] and g['run']==row['run'] and g['purpose']==row['purpose'],'soup scientific group identity')
        require(plan['prediction_groups'][row['soup_group']]['members'],'actual soup query group')
    require(actual==soup_union(plan,scope),'exact full soup study union; missing studies cannot vanish')
    cells={(d['id'],c) for d in scope.panel['datasets'] for c in scope.panel['prospective_conditions']}
    require(len(r['direct_AB'])==20 and {(x['dataset'],x['condition']) for x in r['direct_AB']}==cells,'all20 exploratory A/B cells')
    comparisons=next(j for j in plan['jobs'] if j['stage']=='S20')['payload']['comparisons']
    for row in r['direct_AB']:
        fields(row,('dataset','condition','target','bootstrap_seed','alias_joint_manifest'))
        require(type(row['bootstrap_seed'])is int and row['alias_joint_manifest'],'precommitted A/B seed and biological aliases')
        selected=[c for c in comparisons if c['dataset']==row['dataset'] and c['condition']==row['condition']]
        require(len(selected)==8 and all(c['target']==row['target'] for c in selected),'same A/B biological target')
        for arm in ('A','B'):
            routes=[[p['candidate'] for p in c['runs']] for c in selected if c['arm']==arm]
            require(len(routes)==4 and all(x==routes[0] for x in routes),'same candidate per cell across all4 references')
    return True

def mean_sd(values,guard=None):
    """Missing runs stay in the required denominator; observed means are secondary."""
    if guard:guard()
    observed=[v for v in values if v is not None]
    require(all(type(v)in(int,float) and math.isfinite(v) for v in observed),'finite scalar endpoint')
    n=len(values);k=len(observed);mu=math.fsum(observed)/k if k else None
    complete=k==n and n>0
    ss=math.fsum((v-mu)**2 for v in observed) if k else None
    return {'required':n,'completed':k,'values':values,'mean':mu if complete else None,'population_sd':math.sqrt(ss/k) if complete else None,'sample_sd':math.sqrt(ss/(k-1)) if complete and k>1 else None,'conditional_observed_mean':mu,'complete':complete}

def scalar(result,metric,profile,purpose):
    if result['status']!='scored':return None
    key=profile[purpose]['metric'] if metric=='auc_pr' and purpose in profile else metric
    return result['metrics'].get(key) if key is not None else None

def run_reductions(controller,scoring):
    config=controller.plan['scientific_reductions'];cases={x['id']:x for x in controller.scope.panel['cases']}
    from .scientific_identity import validate_case_bindings
    validate_case_bindings(controller.plan,controller.scope)
    groups=controller.plan['prediction_groups'];by={x['prediction']:x for x in scoring}
    require(set(by)==set(groups) and len(by)==len(scoring),'every scored group remains in reduction input')
    units={}
    for gid,g in groups.items():
        controller.guard();key=(g['programme'],g['case_id'],g['purpose'])
        members=units.setdefault(key,{})
        require(g['run'] not in members,'duplicate programme/case/purpose/run group')
        members[g['run']]=(gid,by[gid])
    out=[]
    for (programme,case,purpose),members in sorted(units.items()):
        controller.guard();original=cases.get(case)
        required=['case_draw'] if original and original['family']=='few_shot' else controller.plan['run_rosters'][programme]
        require(set(members)==set(required),'complete selected run support before reduction')
        metrics_needed=set(original['metrics'] if original else ('balanced_accuracy',))
        if purpose in ('I-person','I-person-montage'):
            exemplar=groups[next(iter(members.values()))[0]]
            required_protected=set(PROTECTED_METRICS)
            if len(exemplar['classes'])!=2:required_protected-={'auroc','average_precision','pr_trapezoid'}
            metrics_needed.update(required_protected)
        rows=[]
        for run in required:
            gid,item=members[run];rows.append({'run':run,'prediction':gid,'result':item['result']})
        summaries={metric:mean_sd([scalar(r['result'],metric,config['auc_pr_profiles'],purpose) for r in rows],controller.guard) for metric in sorted(metrics_needed)}
        exemplar=groups[rows[0]['prediction']]
        out.append({'programme':programme,'case_id':case,'purpose':purpose,'dataset':exemplar['dataset'],'condition':exemplar['condition'],'method':exemplar['method'],'family':original['family'] if original else 'selected_auxiliary_product','configuration':original['configuration'] if original else {},'runs':rows,'metrics':summaries,'required_runs':required,'original_case':original is not None})
    return out

def difference(left,right):
    return left-right if left is not None and right is not None else None

def family_reductions(controller,run_rows):
    """Named table memberships, complete signed ablations and full sparse curves."""
    tables=[];effects=[];sparse=[]
    scopes=sorted({(r['programme'],r['purpose']) for r in run_rows})
    for programme,purpose in scopes:
        rows=[r for r in run_rows if r['programme']==programme and r['purpose']==purpose and r['original_case']]
        for table,(family,datasets) in SOURCE_TABLES.items():
            controller.guard();family_rows=[r for r in rows if r['family']==family]
            originals=[r for r in controller.scope.panel['cases'] if r['family']==family]
            signatures={canonical({'method':r['method'],'configuration':r['configuration']}).decode() for r in originals}
            if table==2:
                # The original common-method row union, not extra methods present in only one dataset.
                signatures=set.intersection(*[{canonical({'method':r['method'],'configuration':r['configuration']}).decode() for r in originals if r['dataset']==d} for d in datasets])
            for signature in sorted(signatures):
                selected=[r for r in family_rows if r['dataset'] in datasets and canonical({'method':r['method'],'configuration':r['configuration']}).decode()==signature]
                lookup={r['dataset']:r for r in selected}
                require(set(lookup)<=set(datasets) and len(selected)==len(lookup),'unique exact named source table membership')
                missing=[d for d in datasets if d not in lookup]
                values={d:lookup[d]['metrics']['balanced_accuracy']['mean'] if d in lookup else None for d in datasets}
                result=source_aggregate(values,table)
                tables.append({'programme':programme,'purpose':purpose,'condition':signature,'result':result,'cases':[lookup[d]['case_id'] if d in lookup else None for d in datasets],'missing_qualified_purpose_datasets':missing})
        original_rows={r['case_id']:r for r in rows}
        complete_rows=[]
        for case in controller.scope.panel['cases']:
            if case['family']=='few_shot':continue
            complete_rows.append(original_rows.get(case['id'],{'case_id':case['id'],'family':case['family'],'dataset':case['dataset'],'method':case['method'],'configuration':case['configuration'],'metrics':{'balanced_accuracy':{'mean':None,'complete':False}},'purpose_not_qualified_for_case':True}))
        for family in ('pretraining_and_freezing','linear_probe','secondary_loss','masking','position_and_mask_components','activation_normalization'):
            ds=sorted({r['dataset'] for r in complete_rows if r['family']==family})
            for dataset in ds:
                candidates=[r for r in complete_rows if r['family']==family and r['dataset']==dataset]
                for a,b in itertools.combinations(candidates,2):
                    controller.guard()
                    if family=='secondary_loss' and a['configuration']['adaptation']!=b['configuration']['adaptation']:continue
                    if family=='masking' and a['configuration']['adaptation']!=b['configuration']['adaptation']:continue
                    am=a['metrics']['balanced_accuracy']['mean'];bm=b['metrics']['balanced_accuracy']['mean']
                    effects.append({'programme':programme,'purpose':purpose,'family':family,'dataset':dataset,'left':a['case_id'],'right':b['case_id'],'left_minus_right':difference(am,bm),'left_configuration':a['configuration'],'right_configuration':b['configuration'],'status':'computed' if am is not None and bm is not None else 'unavailable','confirmatory':False,'method_and_budget_confounding_not_resolved':True})
        for dataset in sorted({r['dataset'] for r in complete_rows if r['family']=='sparse_channels'}):
            curve=sorted((r for r in complete_rows if r['family']=='sparse_channels' and r['dataset']==dataset),key=lambda r:r['configuration']['channels'],reverse=True)
            require(len(curve)==7,'all7 source sparse-channel conditions')
            full=curve[0]['metrics']['balanced_accuracy']['mean']
            sparse.append({'programme':programme,'purpose':purpose,'dataset':dataset,'points':[{'case_id':r['case_id'],'channels':r['configuration']['channels'],'metrics':r['metrics'],'minus_full_channel':difference(r['metrics']['balanced_accuracy']['mean'],full)} for r in curve],'full_channel_case':curve[0]['case_id'],'channel_names_geometry_training_exposure':'Bound by original preprocessing/state scientific audits; counts alone do not qualify.'})
    return {'source_tables':tables,'all_signed_source_effects':effects,'sparse_curves':sparse}

def fewshot_reductions(controller,run_rows):
    groups={};out=[]
    for r in run_rows:
        if r['family']=='few_shot':groups.setdefault((r['programme'],r['purpose']),[]).append(r)
    for (programme,purpose),rows in sorted(groups.items()):
        controller.guard()
        values=[]
        for row in rows:
            c=row['configuration'];values.append({'person':c['person_slot'],'shots':c['shots_per_class'],'draw':c['draw_slot'],'method':row['method'],'balanced_accuracy':row['metrics']['balanced_accuracy']['mean'],'case_id':row['case_id']})
        expected=set(itertools.product(range(1,10),(1,2,5,10,20),range(20),('REVE-Base-PT','REVE-Base-XFT')))
        actual={(r['person'],r['shots'],r['draw'],r['method']) for r in values}
        missing=sorted(expected-actual);undefined=[r['case_id'] for r in values if r['balanced_accuracy'] is None]
        require(len(actual)==len(values) and actual<=expected,'fewshot exact tuple identity')
        if missing or undefined:
            out.append({'programme':programme,'purpose':purpose,'status':'unavailable','required_cases':1800,'observed_cases':len(values),'missing_tuples':missing,'undefined_case_ids':undefined,'biological_N_required':9,'draws_per_person_required':20,'curves':None,'paired_effects':None});continue
        curves=metrics.fewshot_uncertainty(values,controller.plan['scientific_reductions']['bootstrap_seed'],guard=controller.guard)
        effects=metrics.fewshot_paired_uncertainty(values,controller.plan['scientific_reductions']['bootstrap_seed'],guard=controller.guard)
        out.append({'programme':programme,'purpose':purpose,'status':'computed_unqualified','required_cases':1800,'observed_cases':1800,'biological_N':9,'curves':curves,'paired_effects':effects})
    return out

def direct_ab(controller,grader):
    results=[];comparisons=next(j for j in controller.plan['jobs'] if j['stage']=='S20')['payload']['comparisons']
    for recipe in controller.plan['scientific_reductions']['direct_AB']:
        controller.guard();cell=[x for x in comparisons if x['dataset']==recipe['dataset'] and x['condition']==recipe['condition']]
        arm={a:next(x for x in cell if x['arm']==a)['runs'] for a in ('A','B')}
        require(len(arm['A'])==len(arm['B']),'complete paired A/B run counts')
        pairs=[(a['candidate'],b['candidate']) for a,b in zip(arm['A'],arm['B'])]
        unavailable=[g for pair in pairs for g in pair if not grader.available(g)]
        if unavailable:results.append({**recipe,'status':'unavailable','missing_prediction_groups':unavailable,'effect':None,'confirmatory':False});continue
        t=grader.target(recipe['target']);runs=[]
        for a,b in pairs:
            ga,pa=grader.prediction(a);gb,pb=grader.prediction(b)
            require(all(ga[k]==gb[k]==t[k] for k in ('events','classes','support')),'same A/B biological query support')
            runs.append({'labels':t['labels'],'candidate':pa,'reference':pb})
        effect=metrics.paired_cluster_bootstrap(t['people'],runs,len(t['classes']),recipe['bootstrap_seed'],guard=controller.guard)
        results.append({**recipe,'status':'computed_unqualified','effect':effect,'direction':'A minus B','confirmatory':False,'selected_run_pairs':pairs})
    require(len(results)==20,'all20 direct A/B effects retained')
    return results

def validation_best(scores,guard=None):
    if guard:guard()
    require(scores and all(type(x)in(int,float) and math.isfinite(x) for x in scores),'finite complete validation selection metric')
    return max(range(len(scores)),key=lambda i:scores[i])

def soup_reductions(controller,grader):
    output=[]
    for r in controller.plan['scientific_reductions']['soup_studies']:
        controller.guard();ids=[r['soup_group'],*r['member_groups'],*r['validation_groups']]
        unavailable=[g for g in ids if not grader.available(g)]
        if r['product'] not in controller.collector.products or unavailable:
            output.append({**r,'status':'unavailable','missing_groups':unavailable,'missing_product':r['product'] not in controller.collector.products,'effect':None});continue
        soup=controller.collector.products[r['product']]['product']['details']
        member_states=[]
        for g in r['member_groups']:
            detail,_=grader.prediction(g);member_states.append(detail['state'])
        soup_detail,_=grader.prediction(r['soup_group'])
        require(member_states==soup['members'] and soup_detail['state']==soup['state'],'actual soup/member query state lineage')
        validation=[]
        for gid,state in zip(r['validation_groups'],member_states):
            detail,_=grader.prediction(gid);require(detail['state']==state,'actual member validation state')
            v=grader.score(gid,r['validation_target'],r['purpose']);validation.append(v)
        scores=[x['metrics'].get('balanced_accuracy') if x['status']=='scored' else None for x in validation]
        member_results=[grader.score(g,r['test_target'],r['purpose']) for g in r['member_groups']]
        soup_result=grader.score(r['soup_group'],r['test_target'],r['purpose'])
        if any(x is None for x in scores):
            output.append({**r,'status':'unavailable','reason':'incomplete validation-only single-best selection','validation_results':validation,'member_results':member_results,'soup_result':soup_result});continue
        best=validation_best(scores,controller.guard)
        sm=soup_result['metrics'];member_metrics=[x['metrics'] for x in member_results]
        effects={m:{'versus_each_member':[difference(sm.get(m),x.get(m)) for x in member_metrics],'versus_validation_best':difference(sm.get(m),member_metrics[best].get(m))} for m in ('balanced_accuracy','cohen_kappa','weighted_f1','auroc','average_precision','pr_trapezoid')}
        output.append({**r,'status':'computed_unqualified','validation_results':validation,'single_best_index':best,'single_best_state':member_states[best],'member_results':member_results,'soup_result':soup_result,'signed_effects':effects,'query_values_used_for_selection':False,'public_69_6_percent_not_an_invented_run_target':True})
    return output

def complete_reductions(controller,grader,scoring,audits):
    controller.guard();validate_reduction_plan(controller.plan,controller.scope)
    runs=run_reductions(controller,scoring)
    result={'schema':'reve-complete-trusted-reductions-v2','case_run_reductions':runs,
      'family_reductions':family_reductions(controller,runs),'fewshot':fewshot_reductions(controller,runs),
      'soups':soup_reductions(controller,grader),'direct_A_B':direct_ab(controller,grader),
      'scientific_audits':audits,'missing_original_evidence_stays_unavailable':True,'scientifically_qualified':False}
    result['complete_required_outputs']=all(m['complete'] for row in runs for m in row['metrics'].values()) and all(x['result']['complete'] for x in result['family_reductions']['source_tables']) and all(x['status']=='computed_unqualified' for category in ('fewshot','soups','direct_A_B') for x in result[category])
    controller.guard();return result
