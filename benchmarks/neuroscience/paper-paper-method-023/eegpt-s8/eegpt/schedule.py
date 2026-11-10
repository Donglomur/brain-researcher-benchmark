"""Deterministic complete schedule constructed from original support metadata."""
from collections import defaultdict,Counter
from .protocol import fields,need,digest,integer,identity
from .scope import DATASETS,FOLDS,CONTROLS,CLASSES,REPETITIONS

PRETRAIN_RECIPES=tuple(['size:'+v for v in ('tiny1','tiny2','tiny3','little','base1','base2','base3','large')]+['ablation:'+v for v in ('A','B','C','D')]+['predictor:baseline','predictor:no_predictor']+['fraction:'+v for v in ('1','0.5','0.25','0.125')])


class Schedule:
    def __init__(self,scope,census,study,projection,policy):
        fields(study,('schema','scope_identity','historical_roster','pretraining_roster','diagnostic_roster','qualification','tolerances','scientific_reduction_policy'),'complete prior scientific study')
        need(study['schema']=='eegpt_complete_study_v1' and study['scope_identity']==scope.identity,'whole accepted programme, not caller chosen short route');digest(study['qualification'])
        self.scope=scope;self.census=census;self.study=study;self.projection=projection;self.policy=policy;self.episodes={};self.classifications=[];self.diagnostics=[];self.pretraining=[]
        for row in scope.classification():
            spec=scope.episode(row,policy);eid=identity(spec);case=row['case'];key=scope.classification_key(row);dataset=case['dataset'];fold=case['fold_slot'];repetition=case['seed_slot']
            if eid not in self.episodes:self.episodes[eid]={'spec':spec,'classification':[],'diagnostics':[],'pretraining':[],'original_scope_identity':eid}
            query_rows=projection.episode_rows(dataset,fold,row['mode'],'query');ids=[projection.alias(dataset+':id',r['id']) for r in query_rows]
            original={'product_id':key,'type':'T03','scope':{**spec,'repetition':repetition,'case_id':case['case_id']},'scientific_case':row,'support':{'row_ids':ids,'class_ids':list(range(CLASSES[dataset])),'mapping':study['scientific_reduction_policy']['class_mapping'][dataset][row['mode']],'source_auxiliary_allowed':row['access']=='B' and row['mode']=='H'},'arrays':{'probabilities':{'shape':[len(ids),CLASSES[dataset]],'kind':'probabilities'}},'parents':None}
            auxiliary=study['scientific_reduction_policy']['source_auxiliary_by_case'].get(case['case_id']) if row['mode']=='H' and row['access']=='B' else None
            need(auxiliary in (None,'bcic2b_original_four_logits'),'closed retained native auxiliary mapping')
            need(auxiliary is None or dataset=='BCIC-2B','native four-output binary classifier only on original2B source lane')
            original['support']['source_auxiliary']=auxiliary
            if auxiliary is not None:original['arrays'].update({'source_logits':{'shape':[len(ids),4],'kind':'raw_logits'},'source_argmax':{'shape':[len(ids),1],'kind':'native_auxiliary_class'}})
            original['support_identity']=identity(original['support']);self.classifications.append(original);self.episodes[eid]['classification'].append(original)
        need(len(self.classifications)==15402,'all original H/P independent banks and both I comparison arms')
        need(Counter(r['scientific_case']['mode'] for r in self.classifications)=={'H':7056,'P':7056,'I':1290},'full mode-specific original counts')
        # A roster selects authentic original q_v or the accepted explicitly
        # prospective one-parent plan. No implicit three pretraining repeats.
        for mode in ('H','P'):
            for access in ('A','B'):
                for actor in ('participant','reference'):
                    namespace=mode+':'+access+':'+actor;roster=study['pretraining_roster'][namespace]
                    need(set(roster)==set(PRETRAIN_RECIPES),'all18 selected pretraining family recipe roles')
                    for recipe in PRETRAIN_RECIPES:
                        need(type(roster[recipe]) is list and roster[recipe],'full original or explicit prospective parent multiplicity')
                        for parent in roster[recipe]:
                            fields(parent,('id','recipe','source_identity','corpus_support','seed','selection','reuse','qualification'),'complete original pretrain parent')
                            need(parent['recipe']==recipe and parent['reuse'] is None,'this conservative initial schedule retains each original recipe; no unqualified alias')
                            digest(parent['source_identity']);digest(parent['corpus_support']);digest(parent['qualification']);integer(parent['seed'],'fixed original pretrain seed',0,2**32-1)
                            spec={'mode':mode,'access':access,'policy_id':policy,'actor_role':actor,'dataset':'CORPUS','outer_fold':'corpus','method':recipe+':'+parent['id']};eid=identity(spec)
                            need(eid not in self.episodes,'unique full original corpus parent');job={'spec':spec,'classification':[],'diagnostics':[],'pretraining':[parent],'original_scope_identity':eid};self.episodes[eid]=job;self.pretraining.append(job)
        expected_names={m+':'+a+':'+r for m in ('H','P') for a in ('A','B') for r in ('participant','reference')}
        need(set(study['pretraining_roster'])==expected_names,'no absent or added speculative pretrain namespace')
        # Numerical diagnostic plans were selected before outcomes, with full
        # authentic axis/step/draw support. Their production is compulsory.
        roster=study['diagnostic_roster'];need(set(roster)==expected_names,'all original reproduction diagnostic banks')
        required={f['id']:set(f['products'])-{'T03','T11','T12','T13'} for f in scope.families}
        seen=[]
        for namespace in sorted(roster):
            mode,access,actor=namespace.split(':');need(set(roster[namespace])==set(required),'all eleven full scientific families')
            for family,products in roster[namespace].items():
                need(set(products)==required[family],'all original scientific products per family')
                for product_type,plans in products.items():
                    need(type(plans) is list and plans,'every qualified full scientific product plan')
                    for plan in plans:
                        fields(plan,('id','episode_spec','repetition','support','arrays','producer_call','recipe_identity','reference_pair','qualification'),'complete actual diagnostic production obligation')
                        spec=plan['episode_spec'];need(spec['mode']==mode and spec['access']==access and spec['actor_role']==actor and spec['policy_id']==policy,'diagnostic same original mode/access/role policy')
                        eid=identity(spec);need(eid in self.episodes,'diagnostic bound to actual full corpus or downstream episode')
                        need(plan['producer_call'] in ('PREPARE','PRETRAIN','FIT','DIAGNOSE','ANALYZE'),'actual scientific API producer, not display placeholder');digest(plan['recipe_identity']);digest(plan['qualification']);need(plan['repetition'] is None or plan['repetition'] in REPETITIONS,'actual original scientific repetition')
                        item={'product_id':plan['id'],'type':product_type,'scope':{**spec,'family':family,'repetition':plan['repetition']},'support':plan['support'],'support_identity':identity(plan['support']),'arrays':plan['arrays'],'parents':None,'plan':plan}
                        seen.append(plan['id']);self.diagnostics.append(item);self.episodes[eid]['diagnostics'].append(item)
        need(len(seen)==len(set(seen)) and not set(seen)&{r['product_id'] for r in self.classifications},'all numerical products unique, not double-counted cases')
        self.expected=self.classifications+self.diagnostics
        self.selection_groups={}
        for access in ('A','B'):
            for dataset in DATASETS:
                for fold in range(FOLDS[dataset]):
                    key=access+':'+dataset+':'+str(fold);members={}
                    for method in CONTROLS:
                        spec={'mode':'I','access':access,'policy_id':policy,'actor_role':'reference','dataset':dataset,'outer_fold':'f'+str(fold),'method':method};eid=identity(spec);need(eid in self.episodes,'all four independent actual reference episodes');members[method]=eid
                    self.selection_groups[key]={'access':access,'dataset':dataset,'fold':fold,'methods':members}
        need(len(self.selection_groups)==86,'all43 same-fold selectors per arm')
        self.identity=identity({'scope':scope.identity,'policy':policy,'study':study,'episodes':self.episodes,'selections':self.selection_groups})
    def summary(self):
        return {**self.scope.summary(),'whole_schedule_identity':self.identity,'actual_episodes':len(self.episodes),'classification_products':len(self.classifications),'nonclassification_products':len(self.diagnostics),'pretraining_parent_jobs':len(self.pretraining),'pretraining_count_is_not_original_seed_uncertainty':True,'reference_selection_groups':len(self.selection_groups),'aliases_applied':0,'scientific_runs_executed_by_construction':0}
