"""Concrete protected classification scorer and paired full-family reducer.

Only controller-owned captured artifacts and issuer-bound original query joins
are accepted. A submitted score, reference callback or paper percentage is not
an input to the scorer. No function is executed during source construction.
"""
import os,math
from pathlib import Path
from .protocol import HandleCustody,boundary,budget_method,Directory,need,fields,identity,digest,observation,Refusal
from .products import array_rows
from .scope import DATASETS,FOLDS,CONTROLS,CLASSES
from .metrics import BinaryRankStore,classify,equal_fold_repetition,MONITOR,clustered_interval,method_swap,effects_report


class ProtectedGrader:
    def __init__(self,issuer,projection,session,collection,schedule,query_receipts,budget,scratch,qualification,lineage_context):
        self.issuer=issuer;self.projection=projection;self.collection=collection;self.schedule=schedule;self.queries=query_receipts;self.budget=budget;self.scratch=Path(scratch);self.qualification=qualification;self.lineage_context=lineage_context;self.sequence=0;self.captured={};self.results={};self.target_cache={};self.failures=[];self.opened=False
        # This map is derived from original Session objects, not deserialized
        # caller paths or candidate-created receipts. Exact capture pins are
        # reauthenticated when a full matrix is read.
        for call in session.calls:
            if call['phase']!='captured' or call['response'] is None:continue
            for product in call['response']['products']:
                key=product['product_id'];selected=collection.members.get(key)
                if selected is None or selected.get('process')!=call['process_receipt']:continue
                need(key not in self.captured,'one selected original captured producer per scientific product')
                from .products import admit_producer
                admit_producer(collection.expected[key],call['process_receipt'],issuer)
                self.captured[key]={'root':call['capture_root'],'product':product,'process':call['process_receipt'],'capture':call['capture_receipt'],'artifact_pins':call['response']['artifacts']}
    def admit(self,closure):
        need(self.collection.closed and not self.opened,'full immutable collected obligations before protected target admission');self.issuer.admit_targets(closure);self.closure=closure;self.opened=True
    def targets(self,product_id):
        need(self.opened and self.issuer.targets_open,'targets never before full original closure')
        if product_id not in self.target_cache:
            need(product_id in self.queries,'actual original query preparation receipt');self.target_cache[product_id]=self.projection.private_targets(self.queries[product_id],self.closure)
        return self.target_cache[product_id]
    def _rows(self,product_id,weights,swap_partner=None,swaps=None):
        member=self.collection.members[product_id];need(member['status']=='complete' and product_id in self.captured,'actual completed full original classification product')
        captured=self.captured[product_id];product=captured['product'];need(product['type']=='T03' and product['status']=='complete','complete T03 numerical body');body=product['body'];targets=self.targets(product_id);need(set(body['row_ids'])==set(targets),'complete exact original protected target join')
        with HandleCustody('protected_paired_rows') as owned:
            root=owned.own(Directory(captured['root']),'candidate_root');other_root=None
            values=owned.own(array_rows(root,product['arrays'][body['probabilities']],[len(body['row_ids']),len(body['class_ids'])],self.budget,probabilities=True),'candidate_rows')
            if swap_partner is not None:
                other=self.captured[swap_partner];op=other['product'];ob=op['body'];need(ob['row_ids']==body['row_ids'] and ob['class_ids']==body['class_ids'],'same original person/event/class rows for paired comparison')
                other_targets=self.targets(swap_partner);need(other_targets==targets,'same full protected semantic targets, not just common row counts')
                other_root=owned.own(Directory(other['root']),'paired_root');ov=owned.own(array_rows(other_root,op['arrays'][ob['probabilities']],[len(ob['row_ids']),len(ob['class_ids'])],self.budget,probabilities=True),'paired_rows')
                for row_id,p,q in zip(body['row_ids'],values,ov,strict=True):
                    target=targets[row_id];person=target['person'];yield target['label'],q if swaps and swaps.get(person,False) else p,1 if weights is None else weights[person]
            else:
                for row_id,p in zip(body['row_ids'],values,strict=True):
                    target=targets[row_id];yield target['label'],p,1 if weights is None else weights[target['person']]
    def metric(self,product_id,*,weights=None,swap_partner=None,swaps=None):
        expected=self.collection.expected[product_id];classes=len(expected['support']['class_ids']);self.sequence+=1;store=None;rows=None;value=None
        with HandleCustody('protected_metric_resources') as owned:
            try:
                if classes==2:store=owned.own(BinaryRankStore(self.scratch/('rank-%09d.sqlite'%self.sequence)),'rank_store')
                rows=owned.own(self._rows(product_id,weights,swap_partner,swaps),'classification_rows')
                value=boundary(self.budget,'nested_classify',classify,rows,classes,rank_store=store)
            except BaseException as error:owned.retain_failure(error)
            finally:
                for handle in (rows,store):
                    if handle is not None:
                        try:owned.close_owned(handle)
                        except BaseException:pass  # Same owner already retained it.
                if store is not None:
                    for suffix in ('','-journal','-wal','-shm'):
                        path=self.scratch/('rank-%09d.sqlite'%self.sequence+suffix)
                        try:path.unlink()
                        except FileNotFoundError:pass
                        except BaseException as error:owned.retain_failure(error,new_occurrence=True)
        return value
    def original_source_auxiliary(self,pid):
        p=self.captured[pid]['product'];b=p['body']
        if b['source_auxiliary'] is None:return None
        need(b['source_auxiliary']['kind']=='bcic2b_original_four_logits','one qualified original auxiliary mapping');n=len(b['row_ids']);confusion=[[0]*4 for _ in range(4)];targets=self.targets(pid)
        with HandleCustody('original_source_auxiliary') as owned:
            root=owned.own(Directory(self.captured[pid]['root']),'capture')
            probabilities=owned.own(array_rows(root,p['arrays'][b['probabilities']],[n,2],self.budget,probabilities=True),'probabilities');logits=owned.own(array_rows(root,p['arrays'][b['logits']],[n,4],self.budget),'logits');argmax=owned.own(array_rows(root,p['arrays'][b['source_auxiliary']['original_argmax']],[n,1],self.budget),'argmax')
            for rid,prob,value,hard in zip(b['row_ids'],probabilities,logits,argmax,strict=True):
                maximum=max(value);exps=[math.exp(x-maximum) for x in value];positive=exps[1]/math.fsum(exps);native=max(range(4),key=lambda k:value[k]);need(abs(prob[1]-positive)<=1e-6 and abs(prob[0]-(1-positive))<=1e-6 and hard==(float(native),),'full original4-logit to semantic2-probability mapping and actual native argmax');confusion[targets[rid]['label']][native]+=1
            observed=sum(confusion[k][k] for k in range(4))/n;expected=math.fsum(sum(confusion[k])*sum(row[k] for row in confusion) for k in range(4))/(n*n)
            return {'kind':'bcic2b_original_four_logits','truth_by_native_prediction_4x4':confusion,'native_argmax_accuracy':observed,'native_argmax_kappa':None if expected==1 else (observed-expected)/(1-expected),'semantic_probability_mapping_verified':True,'replaces_primary_binary_metrics':False}
    def full_classification(self):
        need(self.opened,'private scoring after original full barrier')
        for expected in self.schedule.classifications:
            self.budget.guard('before_next_original_classification')
            pid=expected['product_id'];member=self.collection.members[pid]
            if member['status']!='complete':self.results[pid]={'status':'unavailable','reason':member.get('reason',member['status']),'metrics':None,'evidence':member.get('original_receipts',[])};continue
            try:
                metrics=boundary(self.budget,'original_metric',self.metric,pid);auxiliary=boundary(self.budget,'original_auxiliary',self.original_source_auxiliary,pid);self.results[pid]={'status':'adjudicated','metrics':metrics,'original_source_auxiliary':auxiliary,'evidence':[self.captured[pid]['process'],self.captured[pid]['capture'],self.queries[pid]],'science_kernel':'fullcase_classification_v1'}
            except BaseException as exc:
                failure={'product_id':pid,'phase':'original_classification_kernel',**observation(exc)};self.failures.append(failure);self.results[pid]={'status':'failed','reason':failure,'metrics':None,'evidence':[self.captured[pid]['process'],self.captured[pid]['capture']]}
        need(set(self.results)=={r['product_id'] for r in self.schedule.classifications},'every expected original classification outcome retained')
        return self.results
    def _index(self,access):
        index={d:{m:{f:{} for f in range(FOLDS[d])} for m in ('participant',*CONTROLS)} for d in DATASETS}
        for row in self.schedule.classifications:
            spec=row['scope'];case=row['scientific_case']['case']
            if spec['mode']!='I' or spec['access']!=access:continue
            method='participant' if spec['actor_role']=='participant' else spec['method'];index[spec['dataset']][method][case['fold_slot']][case['seed_slot']]=row['product_id']
        need(all(set(reps)=={0,1,2} for methods in index.values() for folds in methods.values() for reps in folds.values()),'all129 candidate and516 controls per arm')
        return index
    def _paired_evaluator(self,dataset,index,reference_choices):
        monitor=MONITOR[dataset]
        # This closure is internal, constructed only from original captured
        # products. No external callback or adaptive procedure can substitute.
        def evaluate(weights,swaps):
            left={f:{} for f in range(FOLDS[dataset])};right={f:{} for f in range(FOLDS[dataset])}
            for fold in range(FOLDS[dataset]):
                method=reference_choices[fold]
                if method is None:return None
                for rep in range(3):
                    a=index['participant'][fold][rep];b=index[method][fold][rep]
                    if self.results[a]['status']!='adjudicated' or self.results[b]['status']!='adjudicated':return None
                    left[fold][rep]=self.metric(a,weights=weights,swap_partner=b if swaps is not None else None,swaps=swaps)
                    right[fold][rep]=self.metric(b,weights=weights,swap_partner=a if swaps is not None else None,swaps=swaps)
            a=boundary(self.budget, 'nested_equal_fold_repetition', equal_fold_repetition, left, dataset, monitor)['mean'];b=boundary(self.budget, 'nested_equal_fold_repetition', equal_fold_repetition, right, dataset, monitor)['mean'];return None if a is None or b is None else a-b
        return evaluate
    def improvement(self,access,selector_records,*,seed):
        need(access in ('A','B'),'actual access arm');index=self._index(access);choices={d:{} for d in DATASETS};fullmetrics={d:{} for d in DATASETS};paired={'selected':{},'fixed':{}}
        for dataset in DATASETS:
            for fold in range(FOLDS[dataset]):
                record=selector_records[access+':'+dataset+':'+str(fold)]
                if record['status']=='selected':
                    original=self.issuer.verify(record['receipt'],'reference_selection');body=original['body'];need(body['dataset']==dataset and body['outer_fold']=='f'+str(fold) and body['access']==access,'actual original same-fold selector');choices[dataset][fold]={'status':'selected','selected':body['selected_method'],'original_receipt':record['receipt'],'all_twelve_validation_summaries':original['parents']}
                else:choices[dataset][fold]={'status':'unavailable','selected':None,'original_failure':record}
            for method,folds in index[dataset].items():
                fullmetrics[dataset][method]={f:{r:(self.results[pid]['metrics'] if self.results[pid]['metrics'] is not None else {MONITOR[dataset]:None}) for r,pid in reps.items()} for f,reps in folds.items()}
            complete_query_roster=all(pid in self.queries for reps in index[dataset]['participant'].values() for pid in reps.values())
            people=sorted({t['person'] for reps in index[dataset]['participant'].values() for pid in reps.values() if pid in self.queries for t in self.targets(pid).values()},key=str) if complete_query_roster else []
            plans=[('selected',dataset,{f:choices[dataset][f]['selected'] for f in range(FOLDS[dataset])})]+[('fixed',dataset+'::'+method,{f:method for f in range(FOLDS[dataset])}) for method in CONTROLS]
            for role,key,reference in plans:
                reducer=self._paired_evaluator(dataset,index[dataset],reference);effect_seed=int(identity({'seed':seed,'access':access,'effect':key,'role':role})[:8],16)
                try:
                    observed=reducer({p:1 for p in people},None) if complete_query_roster else None
                    interval=boundary(self.budget, 'nested_clustered_interval', clustered_interval, people, reducer, seed=effect_seed, budget=self.budget) if observed is not None else {'status':'unavailable','interval':None,'reason':'complete original paired endpoint unavailable'}
                    swap=boundary(self.budget, 'nested_method_swap', method_swap, people, reducer, observed, seed=effect_seed ^ 5362599, qualification=self.qualification['exchangeability'][dataset], budget=self.budget)
                    paired[role][key]={'interval':interval,'swap':swap,'biological_people':len(people),'conditional_fitted_states':True}
                except BaseException as exc:
                    failure={'phase':'original_whole_person_uncertainty','access':access,'effect':key,**observation(exc)};self.failures.append(failure);paired[role][key]={'interval':{'status':'failed','interval':None,'original_failure':failure},'swap':{'status':'failed','p':None,'original_failure':failure},'biological_people':len(people),'conditional_fitted_states':True}
        return boundary(self.budget, 'nested_effects_report', effects_report, fullmetrics, choices, paired, budget=self.budget)
    def access_effects(self,*,seed):
        """Matched B-minus-A full candidate support; descriptive, no new p family."""
        both={a:self._index(a) for a in ('A','B')};out={}
        for dataset in DATASETS:
            ids=[pid for a in ('A','B') for reps in both[a][dataset]['participant'].values() for pid in reps.values()];complete=all(pid in self.queries and self.results[pid]['status']=='adjudicated' for pid in ids)
            if not complete:
                out[dataset]={'status':'unavailable','difference':None,'interval':None,'reason':'complete original matched A/B candidate query/support unavailable'};continue
            people=sorted({row['person'] for pid in ids for row in self.targets(pid).values()},key=str);monitor=MONITOR[dataset]
            def evaluate(weights,swaps):
                values={a:{f:{} for f in range(FOLDS[dataset])} for a in ('A','B')}
                for fold in range(FOLDS[dataset]):
                    for rep in (0,1,2):
                        left=both['B'][dataset]['participant'][fold][rep];right=both['A'][dataset]['participant'][fold][rep];need(self.targets(left)==self.targets(right),'matched complete original person/event supports across access arms')
                        values['B'][fold][rep]=self.metric(left,weights=weights,swap_partner=right if swaps is not None else None,swaps=swaps);values['A'][fold][rep]=self.metric(right,weights=weights,swap_partner=left if swaps is not None else None,swaps=swaps)
                b=boundary(self.budget, 'nested_equal_fold_repetition', equal_fold_repetition, values['B'], dataset, monitor)['mean'];a=boundary(self.budget, 'nested_equal_fold_repetition', equal_fold_repetition, values['A'], dataset, monitor)['mean'];return None if b is None or a is None else b-a
            try:
                delta=evaluate({p:1 for p in people},None);interval=boundary(self.budget, 'nested_clustered_interval', clustered_interval, people, evaluate, seed=int(identity({'seed': seed, 'dataset': dataset, 'contrast': 'B_minus_A'})[:8], 16), budget=self.budget) if delta is not None else {'status':'unavailable','interval':None};out[dataset]={'status':'adjudicated','difference':delta,'interval':interval,'biological_people':len(people),'all_original_folds':FOLDS[dataset],'all_original_repetitions':3,'conditional_on_frozen_adaptive_procedures_and_states':True,'confirmatory_p_value':None,'scientific_interpretation':'code-access effect of these separately sealed procedures under matched support and seeds; not isolated intrinsic neural understanding'}
            except BaseException as exc:out[dataset]={'status':'failed','difference':None,'interval':None,'original_failure':observation(exc)};self.failures.append({'phase':'matched_access_effect','dataset':dataset,**observation(exc)})
        return out
    def reproduction_dataset_reductions(self):
        groups={};metadata={}
        for row in self.schedule.classifications:
            spec=row['scope'];scientific=row['scientific_case'];case=scientific['case']
            if spec['mode'] not in ('H','P'):continue
            key_fields={k:spec[k] for k in ('mode','access','actor_role','dataset','method')};key_fields['family']=scientific['family'];key=identity(key_fields);metadata[key]=key_fields;fold=case['fold_slot'];rep=case['seed_slot'];need(rep not in groups.setdefault(key,{}).setdefault(fold,{}),'one original case for each scientific fold/run');groups[key][fold][rep]=row['product_id']
        out={}
        for key,folds in groups.items():
            dataset=metadata[key]['dataset'];need(set(folds)==set(range(FOLDS[dataset])) and all(set(r)=={0,1,2} for r in folds.values()),'every original dataset/family/method fold and all three runs')
            full={f:{r:(self.results[pid]['metrics'] if self.results[pid]['status']=='adjudicated' else {m:None for m in ('balanced_accuracy','cohen_kappa','weighted_f1','auroc','log_loss','brier')}) for r,pid in reps.items()} for f,reps in folds.items()};metrics={m:boundary(self.budget, 'nested_equal_fold_repetition', equal_fold_repetition, full, dataset, m) for m in ('balanced_accuracy','cohen_kappa','weighted_f1','auroc','log_loss','brier')};out[key]={'scope':metadata[key],'metrics':metrics,'all_original_case_ids':folds,'complete_case_count':sum(self.results[pid]['status']=='adjudicated' for reps in folds.values() for pid in reps.values()),'expected_case_count':3*FOLDS[dataset],'same_people_across_folds_are_not_independent':True,'seed_SD_is_descriptive':True}
        return out
    def historical_comparisons(self):
        out={};lookup={}
        for row in self.schedule.classifications:
            spec=row['scope']
            if spec['mode'] not in ('H','P'):continue
            case=row['scientific_case']['case'];key=identity({'mode':spec['mode'],'access':spec['access'],'case':case['case_id']});lookup.setdefault(key,{})[spec['actor_role']]=row
        policy=self.qualification['historical'];need(set(policy)==set(lookup),'complete prior native/reconstruction tolerance policy for all7056 pairs')
        for key,pair in lookup.items():
            need(set(pair)=={'participant','reference'},'every paper row has its independent native/method counterpart');plan=policy[key];fields(plan,('qualification','native_parity_status','metric_tolerances','source_support_identity','documentary_rounding','original_run_provenance'),'complete original reconstruction qualification');digest(plan['qualification']);digest(plan['source_support_identity']);need(plan['native_parity_status'] in ('qualified','unavailable'),'no guessed original native parity')
            a=self.results[pair['participant']['product_id']];b=self.results[pair['reference']['product_id']];dataset=pair['participant']['scope']['dataset'];monitor=MONITOR[dataset];differences={}
            for metric,tolerance in plan['metric_tolerances'].items():
                need(metric in ('balanced_accuracy','cohen_kappa','weighted_f1','auroc','log_loss','brier') and type(tolerance) in (int,float) and math.isfinite(tolerance) and tolerance>=0,'fixed independently calibrated metric tolerance')
                av=None if a['metrics'] is None else a['metrics'][metric];bv=None if b['metrics'] is None else b['metrics'][metric];delta=None if av is None or bv is None else av-bv;differences[metric]={'signed_error':delta,'absolute_error':None if delta is None else abs(delta),'qualified_tolerance':tolerance,'within_tolerance':None if delta is None else abs(delta)<=tolerance}
            need(monitor in differences,'original dataset primary monitor always compared');available=all(r['signed_error'] is not None for r in differences.values());within=available and all(r['within_tolerance'] for r in differences.values())
            out[key]={'scope':pair['participant']['scope'],'candidate':a,'independent_reference':b,'monitor_difference':differences[monitor]['signed_error'],'complete_metric_differences':differences,'reconstruction_status':'unavailable' if not available else 'faithful_within_qualified_tolerances' if within else 'different_from_independent_reference','historical_parity_qualified':plan['native_parity_status']=='qualified','original_run_provenance':plan['original_run_provenance'],'documentary_rounded_summary':plan['documentary_rounding'],'published_mean_used_as_target':False,'favorable_scientific_result_required':False}
        need(len(out)==7056,'all3528 H and3528 P candidate/native comparisons across both arms');return out


for _name in ('admit','targets','_rows','metric','original_source_auxiliary','full_classification','_index','_paired_evaluator','improvement','access_effects','reproduction_dataset_reductions','historical_comparisons'):
    setattr(ProtectedGrader,_name,budget_method(getattr(ProtectedGrader,_name)))
