"""Reviewed complete EG04/05/08 source-owned contrasts; no participant scores.

Parent qualification is frozen before G0. Actual issued process/state/common
ancestry and protected semantic support are checked after the global barrier.
Numerical functions below run only in a separately qualified scientific run.
"""
import math
from .protocol import boundary,need,fields,digest,identity,observation
from .scope import FOLDS
from .metrics import equal_fold_repetition,clustered_interval,MONITOR
METRICS=('balanced_accuracy','cohen_kappa','weighted_f1','auroc','log_loss','brier')
DEFINITIONS=[{'coefficients': {'A_no_LA': -1, 'D_full': 1}, 'datasets': ['BCIC-2A', 'BCIC-2B', 'KaggleERN'], 'family': 'EG-04', 'id': 'full_minus_A_no_LA', 'parent_policy': 'matched_ablation_recipe_parents'}, {'coefficients': {'B_no_waveform_LN': -1, 'D_full': 1}, 'datasets': ['BCIC-2A', 'BCIC-2B', 'KaggleERN'], 'family': 'EG-04', 'id': 'full_minus_B_no_waveform_LN', 'parent_policy': 'matched_ablation_recipe_parents'}, {'coefficients': {'C_no_skip': -1, 'D_full': 1}, 'datasets': ['BCIC-2A', 'BCIC-2B', 'KaggleERN'], 'family': 'EG-04', 'id': 'full_minus_C_no_skip', 'parent_policy': 'matched_ablation_recipe_parents'}, {'coefficients': {'ASF_LP': 1, 'noASF_LP': -1}, 'datasets': ['BCIC-2A', 'BCIC-2B', 'KaggleERN'], 'family': 'EG-05', 'id': 'ASF_within_LP', 'parent_policy': 'same_pretrained_parent'}, {'coefficients': {'ASF_FT': 1, 'noASF_FT': -1}, 'datasets': ['BCIC-2A', 'BCIC-2B', 'KaggleERN'], 'family': 'EG-05', 'id': 'ASF_within_FT', 'parent_policy': 'same_pretrained_parent'}, {'coefficients': {'ASF_FT': -1, 'ASF_LP': 1}, 'datasets': ['BCIC-2A', 'BCIC-2B', 'KaggleERN'], 'family': 'EG-05', 'id': 'LP_minus_FT_with_ASF', 'parent_policy': 'same_pretrained_parent'}, {'coefficients': {'noASF_FT': -1, 'noASF_LP': 1}, 'datasets': ['BCIC-2A', 'BCIC-2B', 'KaggleERN'], 'family': 'EG-05', 'id': 'LP_minus_FT_without_ASF', 'parent_policy': 'same_pretrained_parent'}, {'coefficients': {'ASF_FT': -1, 'ASF_LP': 1, 'noASF_FT': 1, 'noASF_LP': -1}, 'datasets': ['BCIC-2A', 'BCIC-2B', 'KaggleERN'], 'family': 'EG-05', 'id': 'ASF_by_LP_minus_FT_interaction', 'parent_policy': 'same_pretrained_parent'}, {'coefficients': {'pretrained': 1, 'random_initialized_trained': -1}, 'datasets': ['TUAB'], 'family': 'EG-08', 'id': 'pretrained_minus_random_initialized_trained', 'parent_policy': 'qualified_pretrained_vs_trained_random_initialization'}]


def graph(classifications):
    index={}
    for row in classifications:
        s=row['scope']; case=row['scientific_case']['case']; family=row['scientific_case']['family']
        if s['mode'] not in ('H','P') or family not in ('EG-04','EG-05','EG-08'):continue
        key=(s['mode'],s['access'],s['actor_role'],s['dataset'],family,s['method'],case['fold_slot'],case['seed_slot'])
        need(key not in index,'unique original contrast component');index[key]=row
    out={}
    for mode in ('H','P'):
      for access in ('A','B'):
       for actor in ('participant','reference'):
        for definition in DEFINITIONS:
         for dataset in definition['datasets']:
            scope={'mode':mode,'access':access,'actor_role':actor,'dataset':dataset,'family':definition['family'],'contrast':definition['id']}; key=identity(scope); components={}
            for method in definition['coefficients']:
                components[method]={}
                for fold in range(FOLDS[dataset]):
                    components[method][fold]={}
                    for rep in (0,1,2):
                        coordinate=(mode,access,actor,dataset,definition['family'],method,fold,rep)
                        need(coordinate in index,'all original full fold/run contrast components');components[method][fold][rep]=index[coordinate]['product_id']
            out[key]={'scope':scope,'coefficients':dict(definition['coefficients']),'parent_policy':definition['parent_policy'],'components':components}
    need(len(out)==200,'all200 source-owned contrasts');return out


def validate_pairing_policy(contrasts,policy,configuration):
    fields(policy,('schema','graph_identity','records'),'complete prior contrast pairing policy')
    need(policy['schema']=='eegpt_within_family_pairing_v1' and policy['graph_identity']==identity(contrasts),'exact source-owned full graph before exposure')
    need(set(policy['records'])==set(contrasts),'all200 original qualification records including unavailable')
    component_contracts={}
    for key,row in contrasts.items():
        p=policy['records'][key];fields(p,('status','qualification','scientific_compatibility','components'),'typed complete contrast qualification');need(p['status'] in ('qualified','unavailable'),'no assumed scientific matching');digest(p['qualification']);digest(p['scientific_compatibility'])
        ids={pid for f in row['components'].values() for r in f.values() for pid in r.values()};need(set(p['components'])==ids,'every expected actual component has predeclared ancestry obligations')
        for pid,c in p['components'].items():
            need(pid not in component_contracts or component_contracts[pid]==c,'same original scientific component has one consistent pre-exposure lineage qualification');component_contracts[pid]=c
            fields(c,('episode_spec','common_parent_keys','static_resource_names','state_policy','matched_training_policy','seed_hierarchy'),'pre-exposure source and parent qualification')
            coordinates=[(m,f,r) for m,folds in row['components'].items() for f,reps in folds.items() for r,p in reps.items() if p==pid];need(len(coordinates)==1,'unique component role in complete contrast');method,fold,rep=coordinates[0]
            need(all(c['episode_spec'][k]==row['scope'][k] for k in ('mode','access','actor_role','dataset')) and c['episode_spec']['method']==method and c['episode_spec']['outer_fold']=='f'+str(fold),'predeclared component binds actual source-owned method/fold/block')
            eid=identity(c['episode_spec']); need(c['common_parent_keys']==configuration['episode_parent_selection'].get(eid,[]) and c['static_resource_names']==configuration['static_episode_resources'].get(eid,[]),'selected exact common and static inputs before exposure')
            need(len(c['common_parent_keys'])<=1,'original one-parent downstream procedure')
            digest(c['matched_training_policy']);digest(c['seed_hierarchy']);fields(c['state_policy'],('initialization','recipe','trainability','fit_kind'),'qualified controlled recipe state declaration')
            need(c['state_policy']['fit_kind'] in ('new_fit','declared_eligible_reuse'),'qualified actual fitting lifecycle')
            for name in c['static_resource_names']:need(name in configuration['resources'],'selected actual original static resource')
    return contrasts


def component_lineage(grader,pid,policy):
    from .products import admit_producer
    issuer=grader.issuer; captured=grader.captured[pid]; expected=grader.collection.expected[pid]
    admit_producer(expected,captured['process'],issuer); proc=issuer.verify(captured['process'],'process')
    need(proc['scope']['spec']==policy['episode_spec'],'actual original full private component scope')
    states=[p for p in proc['parents'] if p['kind']=='state'];need(len(states)==1,'one actual frozen fitted state');state_ref=states[0];state=issuer.verify(state_ref,'state');body=state['body'];rep=expected['scope']['repetition']
    fits=[p for p in state['parents'] if p['kind']=='process'];generated=[p for p in state['parents'] if p['kind']=='generated'];need(len(fits)==len(generated)==1,'actual generated method and original FIT producer')
    fit=issuer.verify(fits[0],'process');gen=issuer.verify(generated[0],'generated');f=fit['body'];request=f['issued_request']
    need(fit['scope']==state['scope']==proc['scope'] and f['call']=='FIT' and f['repetition']==rep and body['repetition']==rep,'same actual fold/run FIT state and query')
    need(f['original_budget_record']['status']=='completed' and f['input_identity']==f['request_identity']==identity(request) and f['source_identity']==request['source_identity'],'actual successful source-bound original FIT request')
    need(body['original_call_id']==f['call_id'] and fits[0] in gen['parents'] and body['source_identity']==gen['body']['source_identity'],'exact actual generated source/FIT/state chain')
    prepared=[issuer.verify(p,'prepared') for p in fit['parents'] if p['kind']=='prepared']
    for role in ('train','validation'):
        selected=[r for r in prepared if r['body']['role']==role];need(len(selected)==1 and selected[0]['scope']==fit['scope'] and selected[0]['body']['support_identity']==body[role+'_support'],'host-issued actual FIT full '+role+' support')
    declaration=body['state'];need(identity(declaration)==body['state_identity'] and all(declaration[k]==v for k,v in policy['state_policy'].items()),'actual selected state follows qualified scientific recipe')
    need(declaration['files'] and declaration['state_change'],'actual captured state and qualified fitting-change declaration; semantic validity still requires scientific qualification')
    # Search original issuer ancestry, never caller-supplied or serialized aliases.
    seen=set(); contexts=[]
    def walk(receipt):
        if receipt['record_sha256'] in seen:return
        seen.add(receipt['record_sha256']);record=issuer.verify(receipt)
        if record['kind']=='context' and record['scope']==proc['scope']:contexts.append(record)
        for parent in record['parents']:walk(parent)
    walk(fits[0]);need(contexts,'actual context ancestry of selected FIT')
    common={p['record_sha256']:p for ctx in contexts for p in ctx['parents'] if p['kind']=='corpus'}
    selected=grader.lineage_context['common'];wanted=[]
    for key in policy['common_parent_keys']:
        need(key in selected,'all actual completed selected original corpus parents');wanted.append(selected[key]['common_receipt'])
    need(set(common)=={p['record_sha256'] for p in wanted},'exact actual corpus context parents, no missing/substituted ancestry')
    inputs={x['name']:x for x in request['inputs']};need(len(inputs)==len(request['inputs']),'unique actual FIT inputs')
    parent_identities=[];corpus_supports=[];recipes=[]
    for p in wanted:
        c=issuer.verify(p,'corpus');s=issuer.verify(c['body']['state'],'state');need(inputs.get('reference_parent',{}).get('public_identity')==s['body']['state_identity'],'actual mounted FIT parent equals original sealed corpus state')
        parent_identities.append(c['body']['state']['record_sha256']);recipe=s['body']['complete_corpus_recipe'];corpus_supports.append(recipe['corpus_support']);recipes.append(recipe['recipe'])
    if not wanted:need('reference_parent' not in inputs,'trained random initialization cannot receive pretrained common state')
    for name in policy['static_resource_names']:
        binding=grader.lineage_context['resource_bindings'][name];need(inputs.get(name,{}).get('public_identity')==binding['identity'],'actual FIT static resource identity')
    return {'state':state_ref,'fit':fits[0],'generated':generated[0],'query':grader.queries[pid],'source_identity':body['source_identity'],'parent_states':parent_identities,'corpus_supports':corpus_supports,'recipes':recipes,'train_support':body['train_support'],'validation_support':body['validation_support'],'matched_training_policy':policy['matched_training_policy'],'seed_hierarchy':policy['seed_hierarchy'],'state_policy':policy['state_policy'],'static_resource_names':policy['static_resource_names'],'static_resource_kinds':[issuer.verify(grader.lineage_context['resource_receipts'][n],'static_resource')['body']['kind'] for n in policy['static_resource_names']]}


def admit_matched(grader,row,policy):
    need(policy['status']=='qualified','original scientific parent compatibility unavailable');lineages={};people=set()
    for fold in range(FOLDS[row['scope']['dataset']]):
      for rep in (0,1,2):
        matched={};support=None;targets=None;train=None;val=None;training_policy=None;seed_hierarchy=None
        for method,folds in row['components'].items():
            pid=folds[fold][rep];need(grader.results[pid]['status']=='adjudicated' and pid in grader.captured and pid in grader.queries,'every required original component adjudicated')
            actual=grader.captured[pid]['product'];t=grader.targets(pid);s={'row_ids':actual['body']['row_ids'],'class_ids':actual['body']['class_ids']}
            need(set(s['row_ids'])==set(t),'all original full semantic targets')
            if support is None:support=s;targets=t
            else:need(s==support and t==targets,'exact paired row/person/class/target support, no count-only matching')
            line=component_lineage(grader,pid,policy['components'][pid]);lineages[pid]=line;matched[method]=line;people.update(v['person'] for v in t.values())
            if train is None:train=line['train_support'];val=line['validation_support'];training_policy=line['matched_training_policy'];seed_hierarchy=line['seed_hierarchy']
            else:need(line['train_support']==train and line['validation_support']==val and line['matched_training_policy']==training_policy and line['seed_hierarchy']==seed_hierarchy,'matched complete original train/validation and qualified controlled recipe/seed policy')
        if row['scope']['family']=='EG-04':
            for method,line in matched.items():need(line['recipes']==['ablation:'+method[0]],'corresponding actual A/B/C/D pretraining recipe')
            need(len({identity(x['corpus_supports']) for x in matched.values()})==1,'same full original ablation corpus support')
        elif row['scope']['family']=='EG-05':
            need(all(len(x['parent_states'])==1 for x in matched.values()) and len({identity(x['parent_states']) for x in matched.values()})==1,'all factorial cells use exact same actual original pretrained parent')
        else:
            need(len(matched['pretrained']['parent_states'])==1 and not matched['random_initialized_trained']['parent_states'],'actual pretrained versus no-pretrained-input random initialization')
            random=matched['random_initialized_trained'];need(random['state_policy']['fit_kind']=='new_fit' and 'qualified_pretrained_state' not in random['static_resource_kinds'],'trained random comparator has actual original new FIT and no admitted pretrained-state resource')
    return lineages,sorted(people,key=str)


def paired_point(values,dataset,metric,coefficients,*,budget=None):
    reduced={m:boundary(budget, 'nested_equal_fold_repetition', equal_fold_repetition, folds, dataset, metric) for m,folds in values.items()};need(set(reduced)==set(coefficients),'all paired method cells')
    runs=[None if any(v['run_values'][r] is None for v in reduced.values()) else math.fsum(coefficients[m]*v['run_values'][r] for m,v in reduced.items()) for r in (0,1,2)]
    if any(v is None for v in runs):return {'status':'unavailable','mean':None,'run_values':runs,'run_sd':None,'reason':'at least one required full fold/run endpoint undefined'}
    mean=math.fsum(runs)/3
    return {'status':'complete','mean':mean,'run_values':runs,'run_sd':math.sqrt(math.fsum((v-mean)**2 for v in runs)/2),'run_sd_is_descriptive':True,'independent_pretraining_runs_claimed':False}


def reduce_all(grader,*,seed):
    need(grader.opened and grader.issuer.targets_open,'original global barrier before contrasts')
    rows=boundary(grader.budget,'complete_contrast_graph',graph,grader.schedule.classifications);policy=grader.qualification['within_family_pairing'];need(set(policy['records'])==set(rows),'complete fixed pre-exposure paired graph');out={}
    for key,row in rows.items():
        grader.budget.guard('before_next_original_contrast')
        qualification=policy['records'][key];ids={pid for folds in row['components'].values() for reps in folds.values() for pid in reps.values()};statuses={p:grader.results[p]['status'] for p in sorted(ids)}
        result={**row,'qualification':qualification['qualification'],'scientific_compatibility':qualification['scientific_compatibility'],'component_statuses':statuses,'metrics':{},'paired_support_status':'unavailable','descriptive_only':True,'confirmatory_p_value':None,'favorable_result_required':False,'conditional_on_realized_sources_states_and_selections':True,'interval_limitation':'Full-support LOSO bootstrap may be unavailable under original rule; G19 remains required.'}
        matched_row=row;matched_qualification=qualification
        if row['scope']['family']=='EG-05':
            fullkey=identity({**row['scope'],'contrast':'ASF_by_LP_minus_FT_interaction'});matched_row=rows[fullkey];matched_qualification=policy['records'][fullkey]
        matched_ids={pid for folds in matched_row['components'].values() for reps in folds.values() for pid in reps.values()}
        result['all_required_pairing_components']=matched_row['components'];result['all_required_pairing_statuses']={pid:grader.results[pid]['status'] for pid in sorted(matched_ids)}
        try:
            need(qualification['status']=='qualified','original individual contrast compatibility unavailable')
            lineages,people=admit_matched(grader,matched_row,matched_qualification);result.update(paired_support_status='admitted',lineage_evidence=lineages,biological_people=len(people))
        except BaseException as exc:
            result['original_failure']=observation(exc)
            result['metrics']={m:{'status':'unavailable','mean':None,'run_values':[None]*3,'run_sd':None,'interval':{'status':'unavailable','interval':None},'metric_orientation':'lower_is_better' if m in ('log_loss','brier') else 'higher_is_better','raw_signed_coefficients':dict(row['coefficients'])} for m in METRICS};out[key]=result;continue
        values={m:{f:{r:grader.results[pid]['metrics'] for r,pid in reps.items()} for f,reps in folds.items()} for m,folds in row['components'].items()};dataset=row['scope']['dataset'];draw_seed=int(identity({'seed':seed,**{k:v for k,v in row['scope'].items() if k!='contrast'}})[:8],16)
        for metric in METRICS:
            grader.budget.guard('before_next_original_contrast_metric')
            try:
                point=boundary(grader.budget,'contrast_point',paired_point,values,dataset,metric,row['coefficients'],budget=grader.budget)
                def evaluate(weights,swaps):
                    need(swaps is None,'descriptive fixed contrasts do not introduce new swap family')
                    full={m:{f:{r:grader.metric(pid,weights=weights) for r,pid in reps.items()} for f,reps in folds.items()} for m,folds in row['components'].items()}
                    return boundary(grader.budget,'nested_contrast_point',paired_point,full,dataset,metric,row['coefficients'],budget=grader.budget)['mean']
                interval=boundary(grader.budget,'contrast_interval',clustered_interval,people,evaluate,seed=draw_seed,budget=grader.budget) if point['mean'] is not None else {'status':'unavailable','interval':None,'reason':'complete point estimator undefined'}
                result['metrics'][metric]={**point,'interval':interval,'metric_orientation':'lower_is_better' if metric in ('log_loss','brier') else 'higher_is_better','raw_signed_coefficients':dict(row['coefficients'])}
            except BaseException as exc:
                failure=observation(exc);result['metrics'][metric]={'status':'failed','mean':None,'run_values':[None]*3,'run_sd':None,'interval':{'status':'failed','interval':None},'original_failure':failure};grader.failures.append({'phase':'within_family_contrast','contrast':key,'metric':metric,**failure})
        out[key]=result
    grader.budget.guard('after_all_original_contrasts');need(len(out)==200 and sum(len(x['metrics']) for x in out.values())==1200,'complete200/1200 report even after failures')
    return out


def completion_ready(records):
    need(type(records) is dict and len(records)==200,'full200 mandatory contrasts, no silent report omission')
    expected_keys={identity({'mode':mode,'access':access,'actor_role':actor,'dataset':dataset,'family':d['family'],'contrast':d['id']}) for mode in ('H','P') for access in ('A','B') for actor in ('participant','reference') for d in DEFINITIONS for dataset in d['datasets']}
    need(set(records)==expected_keys,'exact whole contrast census from source-owned definitions');keys=set()
    for key,row in records.items():
        need(key==identity(row['scope']) and set(row['metrics'])==set(METRICS),'exact contrast identity and allsix metrics');keys.add(key)
    # Invalid secondary AUC/kappa can be retained as unavailable. The original
    # dataset monitor and all paired lineage/support must remain available.
    return all(r['paired_support_status']=='admitted' and r['metrics'][MONITOR[r['scope']['dataset']]]['status']=='complete' and all(m['status'] in ('complete','unavailable') for m in r['metrics'].values()) for r in records.values())
