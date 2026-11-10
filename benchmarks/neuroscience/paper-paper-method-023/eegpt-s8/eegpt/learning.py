"""Fold-local arbitrary submitted learning procedures, not fixed model tuning.

The participant supplies executable source and may generate new source, choose
analyses, fit models, use eligible corpus resources and adapt from its own
validation. Only actual captured products and trusted reductions enter custody.
"""
import os
from pathlib import Path
from .protocol import HandleCustody,Directory,fields,need,digest,identity,encode,persist,observation,Refusal
from .scope import derived_seed
from .information import public_request,validate_source_manifest,capture_source


class LocalLearning:
    def __init__(self,issuer,session,projection,genesis,initial_sources,science_source,budget,policy):
        self.issuer=issuer;self.session=session;self.projection=projection;self.genesis=genesis;self.initial=initial_sources;self.science=science_source;self.budget=budget;self.policy=policy;self.episodes={}
    def create(self,plan,eligible_corpus,static_inputs):
        spec=plan['spec'];eid,context=self.issuer.create_episode(spec,eligible_corpus,context_identity=os.urandom(32).hex());self.episodes[eid]={'plan':plan,'context':context,'source':self.initial[spec['access']] if spec['actor_role']=='participant' else self.science,'attempts':{},'selected':{},'feedback':{},'query':{},'outputs':[],'failures':[],'development_close':None,'static_inputs':static_inputs,'analysis_specifications':{},'common_state_inputs':{},'single_diagnostic_producers':set(),'described':False};return eid
    def describe(self,eid):
        row=self.episodes[eid];need(not row['described'],'one initial fresh E description before any data call')
        actual=self._request(eid,0,row['source'],'DESCRIBE','declare_complete_local_method',[row['context']],{},None,{'products':[],'data_or_state_fitting_allowed':False});need(actual['response']['status']=='ok' and actual['response']['generated_source'] is None and actual['response']['selected_state'] is None,'A01 declares source, never fits or changes G0');row['outputs'].append(actual);row['described']=True;row['description']=actual
    def _templates(self,eid,repetition,call,parents):
        import copy
        out=[]
        for expected in self.episodes[eid]['plan']['diagnostics']:
            if expected['plan']['producer_call']!=call or expected['plan']['repetition'] not in (None,repetition):continue
            if expected['plan']['repetition'] is None and repetition not in (None,0):continue
            item=copy.deepcopy(expected);item['parents']=[r['record_sha256'] for r in parents];out.append(item)
        return out
    def pretrain(self,eid,prepared,eligible_specifications,exposure_evidence):
        row=self.episodes[eid]
        if not row['described']:self.describe(eid)
        need(row['plan']['spec']['dataset']=='CORPUS' and len(row['plan']['pretraining'])==1,'one actual complete original corpus parent')
        parent=row['plan']['pretraining'][0];parents=[row['context']]+[x['receipt'] for x in prepared.values()];inputs={k:{'host':v['host_root'],'guest':'/inputs/'+k,'identity':v['member']['sha256']} for k,v in prepared.items()};source=row['source']
        preparation=self._request(eid,0,source,'PREPARE','complete_corpus_preparation',parents,inputs,None,{'products':self._templates(eid,None,'PREPARE',parents)},seed_override=parent['seed']);row['outputs'].append(preparation);parents += [preparation['process_receipt'],preparation['capture_receipt']];inputs['prepared_context']={'host':preparation['capture_root'],'guest':'/state/prepared','identity':preparation['response_member']['sha256']}
        result=self._request(eid,0,source,'PRETRAIN','complete_selected_original_pretraining',parents,inputs,None,{'products':self._templates(eid,None,'PRETRAIN',parents),'recipe':parent,'all_five_corpora_required':True},seed_override=parent['seed']);need(result['response']['status']=='ok','actual complete original corpus learning')
        generated=self._generated(eid,0,result,parents);state=result['response']['selected_state'];need(state is not None and state['files'],'actual complete corpus state')
        receipt=self.issuer.publish_local(eid,'state',[generated['receipt'],result['process_receipt'],result['capture_receipt']],{'state_identity':identity(state),'state':state,'source_identity':generated['identity'],'original_call_id':result['call_id'],'complete_corpus_recipe':parent},repetition=0)
        analysis_inputs={**inputs,'fitted':{'host':result['capture_root'],'guest':'/state/fitted','identity':identity(state)}}
        self.freeze_analysis(eid,0,generated,[row['context'],receipt],analysis_inputs)
        closed=self.issuer.close_development(eid,{'actual_corpus_state':receipt,'actual_source':generated['receipt'],'all_parent_run_identities':parent},[row['context'],receipt,generated['receipt']]+list(row['analysis_specifications'].values()));row['development_close']=closed;row['outputs'].append(result);row['selected'][0]={'source':generated,'state':receipt,'state_root':result['capture_root'],'state_identity':identity(state),'state_files':state['files']}
        diagnostic_templates=self._templates(eid,None,'DIAGNOSE',[closed,receipt])
        if diagnostic_templates:
            diagnostic_result=self._request(eid,0,generated,'DIAGNOSE','complete_corpus_state_diagnostics',[closed,receipt],{'fitted':{'host':result['capture_root'],'guest':'/state/fitted','identity':identity(state)}},None,{'products':diagnostic_templates},seed_override=parent['seed']);row['outputs'].append(diagnostic_result)
        self.issuer.close_episode(eid,[p['product_id'] for output in row['outputs'] for p in output['response']['products']]);common=self.issuer.seal_completed_corpus(eid,receipt,generated['receipt'],eligible_specifications,exposure_evidence)
        return {'common_receipt':common,'state_receipt':receipt,'source_receipt':generated['receipt'],'host_root':result['capture_root'],'state_identity':identity(state),'original_result':result,'actual_parent':parent}
    def _request(self,eid,repetition,source,call,action,parents,inputs,feedback,output,seed_override=None):
        row=self.episodes[eid];spec=row['plan']['spec'];need(not set(row['static_inputs'])&set(inputs),'static eligible resources cannot replace a query/train/state capability');inputs={**({} if call=='DESCRIBE' else row['static_inputs']),**inputs};seed=derived_seed(self.genesis['seed_policy']['commitment'],repetition,identity({'matched_scientific_spec':{k:v for k,v in spec.items() if k!='access'},'call':call,'action':action,'attempt':len(row['attempts'].get(repetition,[]))}))
        if seed_override is not None:seed=seed_override
        public_inputs=[{'name':k,'guest_root':v['guest'],'public_identity':v['identity']} for k,v in inputs.items()]
        public_feedback=None if feedback is None else [{k:v for k,v in r.items() if k in ('attempt','status','decision','validation_summary')} for r in feedback]
        request=public_request(call=call,scope={k:spec[k] for k in ('mode','access','policy_id','dataset','outer_fold','method')}|{'repetition':repetition},request_id=os.urandom(16).hex(),source=source['identity'],parents=[p['record_sha256'] for p in parents],inputs=public_inputs,output_contract=output,resources=self.policy['job_reservation'],seed=seed,feedback=public_feedback,context=row['context']['record_sha256'],action=action)
        bindings=[{'host':v['host'],'guest':v['guest'],'identity':v['identity']} for v in inputs.values()]
        result=self.session.call(eid,source,request,parents,repetition=repetition,reservation=self.policy['job_reservation'],inputs=bindings,query=call in ('PREDICT','QUERY_TRANSFORM','DIAGNOSE') and row['development_close'] is not None)
        return result
    def _generated(self,eid,repetition,result,parents):
        response=result['response'];manifest=response['generated_source'];need(manifest is not None,'actual generated executable method source accompanies learned state')
        if set(manifest)=={'reuse'}:
            row=self.episodes[eid];existing=row['source'];need(manifest['reuse']==existing['identity'],'only actual original episode source reused; no cross-fold/hash alias')
            receipt=self.issuer.publish_local(eid,'generated',parents+[existing['receipt'],result['process_receipt'],result['capture_receipt']],{'source_identity':existing['identity'],'manifest':existing['manifest'],'actual_original_source_reuse':existing['receipt'],'original_call_id':result['call_id'],'promotion_to_global_common_allowed':False},repetition=repetition)
            return {**existing,'receipt':receipt}
        validate_source_manifest(manifest,genesis_environment=self.genesis['source_and_environment_identity'],allowed_resources=self.genesis['common_resources'])
        snapshot=Path(result['capture_root']).parent/'generated-source';os.mkdir(snapshot,0o700)
        with HandleCustody('generated_source_output') as owned:
            root=owned.own(Directory(result['capture_root']),'output')
            return capture_source(root,snapshot,manifest,self.issuer,eid,parents+[result['process_receipt'],result['capture_receipt']],self.budget,repetition=repetition,environment=self.genesis['source_and_environment_identity'],resources=self.genesis['common_resources'])
    def develop(self,eid,repetition,prepared,corpus_inputs):
        row=self.episodes[eid]
        if not row['described']:self.describe(eid)
        source=row['source'];parents=[row['context']]+[v['receipt'] for v in prepared.values()];inputs={k:{'host':v['host_root'],'guest':'/inputs/'+k,'identity':v['member']['sha256']} for k,v in prepared.items()};inputs.update(corpus_inputs);row['common_state_inputs']=dict(corpus_inputs);history=[];row['attempts'][repetition]=history
        # Actual participant PREPARE can learn a train-only transform. Its
        # captured state/context becomes an original local parent, never a
        # global preprocessing cache selected using another fold's feedback.
        prepare=self._request(eid,repetition,source,'PREPARE','prepare_local_method',parents,inputs,None,{'products':self._templates(eid,repetition,'PREPARE',parents),'may_generate_local_code':True});row['outputs'].append(prepare);parents += [prepare['process_receipt'],prepare['capture_receipt']]
        inputs['prepared_context']={'host':prepare['capture_root'],'guest':'/state/prepared','identity':prepare['response_member']['sha256']}
        for attempt in range(self.policy['maximum_development_attempts']):
            self.budget.guard('before_complete_local_development_attempt')
            actual=self._request(eid,repetition,source,'FIT','develop_and_fit',parents,inputs,history,{'products':self._templates(eid,repetition,'FIT',parents),'generated_source_required':True,'available_decisions':['continue','select','abstain','unsupported','failed']});response=actual['response'];history.append({'attempt':attempt,'original_call':actual['call_id'],'status':response['status'],'decision':response['decision'],'process':actual['process_receipt'],'capture':actual['capture_receipt']})
            if response['status']!='ok' or response['decision'] in ('abstain','unsupported','failed'):
                row['failures'].append({'repetition':repetition,'attempt':attempt,'status':response['status'],'diagnostics':response['diagnostics']});return None
            generated=self._generated(eid,repetition,actual,parents);state=response['selected_state'];fields(state,('files','initialization','train_support','recipe','rng','trainability','state_change','fit_kind'),'actual learned state declaration')
            need(state['files'] and set(state['files'])<={a['path'] for a in response['artifacts']},'actual captured opaque state files')
            need(state['fit_kind'] in ('new_fit','declared_eligible_reuse'),'no silent pretend independent fitting')
            state_receipt=self.issuer.publish_local(eid,'state',[generated['receipt'],actual['process_receipt'],actual['capture_receipt']],{'state_identity':identity(state),'state':state,'source_identity':generated['identity'],'original_call_id':actual['call_id'],'train_support':prepared['train']['public']['whole_support_identity'],'validation_support':prepared['validation']['public']['whole_support_identity']},repetition=repetition)
            validation_inputs={**row['common_state_inputs'],'validation':inputs['validation'],'fitted':{'host':actual['capture_root'],'guest':'/state/fitted','identity':actual['response_member']['sha256']}}
            predict=self._request(eid,repetition,generated,'VALIDATE','validation_predictions',[state_receipt,prepared['validation']['receipt']],validation_inputs,None,{'products':['T03'],'support_role':'validation','full_rows':prepared['validation']['public']['rows']})
            need(predict['response']['status']=='ok','actual complete validation prediction process')
            # The concrete trusted scientific source independently recomputes
            # metrics from observed probabilities and same-fold labels. Candidate
            # scores, including plausible forged metrics, are never selectors.
            reduce_inputs={**validation_inputs,'predictions':{'host':predict['capture_root'],'guest':'/inputs/predictions','identity':predict['response_member']['sha256']}}
            reduction=self._request(eid,repetition,self.science,'ANALYZE','reduce_validation',[predict['process_receipt'],predict['capture_receipt'],prepared['validation']['receipt']],reduce_inputs,None,{'products':['T11'],'monitor':self.policy['monitors'][row['plan']['spec']['dataset']],'original_fit_evidence':{'state_declaration':state,'state_identity':identity(state),'fit_call_id':actual['call_id'],'fit_request_identity':actual['request_identity'],'fit_response_identity':identity(actual['response']),'actual_generated_source_identity':generated['identity'],'attempt':attempt,'repetition':repetition,'train_support_identity':prepared['train']['public']['whole_support_identity'],'validation_support_identity':prepared['validation']['public']['whole_support_identity']}})
            need(reduction['response']['status']=='ok','trusted actual validation reduction');summary=reduction['response']['diagnostics'];fields(summary,('status','monitor','metrics','support_identity','all_person_metrics','all_configuration_metrics'),'complete durable validation selection evidence')
            need(summary['support_identity']==prepared['validation']['public']['whole_support_identity'],'all four controls and candidates use exact original same-fold validation support')
            feedback=self.issuer.publish_local(eid,'feedback',[reduction['process_receipt'],reduction['capture_receipt'],state_receipt],{**summary,'support_role':'validation','trusted_reducer_source':self.science['identity'],'full_summary_pin':reduction['response_member'],'actual_source':generated['identity'],'state':state_receipt},repetition=repetition)
            history[-1].update({'validation_summary':summary,'feedback_receipt':feedback,'generated_source':generated['receipt'],'state':state_receipt});row['feedback'][repetition]=feedback
            if response['decision']=='select':
                self.freeze_analysis(eid,repetition,generated,[state_receipt,feedback],{**inputs,'fitted':{'host':actual['capture_root'],'guest':'/state/fitted','identity':identity(state)}})
                selection={'source':generated,'state':state_receipt,'state_files':state['files'],'state_root':actual['capture_root'],'state_identity':identity(state),'feedback':feedback,'validation_summary':summary,'original_fit_call':actual['call_id'],'all_attempts':list(history)};row['selected'][repetition]=selection;return selection
            need(response['decision']=='continue','successful unsealed attempt explicitly continues or selects')
            parents += [generated['receipt'],state_receipt,feedback]
            inputs['previous_attempt']={'host':actual['capture_root'],'guest':'/state/previous','identity':actual['response_member']['sha256']}
            # Only same-E local history is returned. No global mutable API,
            # scheduler performance signal or other fold source can enter here.
        row['failures'].append({'repetition':repetition,'status':'budgeted_search_exhausted','attempts':len(history)});return None
    def freeze_analysis(self,eid,repetition,source,parents,inputs):
        row=self.episodes[eid];templates=self._templates(eid,repetition,'ANALYZE',parents)
        if not templates:return
        for expected in templates:
            if expected['type']=='T06':
                actual=self._request(eid,repetition,source,'ANALYZE','seal_complete_analysis_specification',parents,inputs,None,{'products':[expected],'assessment_metrics_available':False});need(actual['response']['status']=='ok','actual original pretarget A09 source completion')
                specs=actual['response']['diagnostics']['analysis_specifications'];need(set(specs)=={expected['product_id']} and specs[expected['product_id']]==expected['support']['analysis_specification'],'same full fixed formula and point graph, not a favorable selected subset')
                receipt=self.issuer.publish_local(eid,'analysis',[actual['process_receipt'],actual['capture_receipt']],{'analysis_specification':specs[expected['product_id']],'product_id':expected['product_id'],'frozen_program_artifacts':actual['response']['artifacts'],'raw_assessment_metrics_seen':False},repetition=repetition);row['analysis_specifications'][expected['product_id']]=receipt;row['outputs'].append(actual)
            elif expected['type']=='T04':
                actual=self._request(eid,repetition,source,'ANALYZE','reduce_pretraining_losses',parents,inputs,None,{'products':[expected]});row['outputs'].append(actual)
            else:raise Refusal('original full A09 obligation lacks its matching scientific reduction: '+expected['type'])
    def seal(self,eid):
        row=self.episodes[eid];parents=[row['context']]+[r['state'] for r in row['selected'].values()]+list(row['feedback'].values())+list(row['analysis_specifications'].values())
        selections={str(r):{'source':v['source']['receipt'],'state':v['state'],'feedback':v['feedback'],'all_attempts':v['all_attempts']} for r,v in row['selected'].items()}
        receipt=self.issuer.close_development(eid,{'selected':selections,'failures':row['failures'],'all_three_repetitions_selected':set(row['selected'])=={0,1,2}},parents);row['development_close']=receipt;return receipt
    def query(self,eid,repetition,prepared,products):
        row=self.episodes[eid];need(row['development_close'] is not None,'actual immutable full E selection before query')
        if repetition not in row['selected']:return None
        selected=row['selected'][repetition];parents=[row['development_close'],selected['state'],prepared['receipt']];inputs={**row['common_state_inputs'],'query':{'host':prepared['host_root'],'guest':'/inputs/query','identity':prepared['member']['sha256']},'fitted':{'host':selected['state_root'],'guest':'/state/fitted','identity':selected['state_identity']}}
        transduction=self.genesis['transductive_policy'];fields(transduction,('enabled_mode_policy_pairs','qualification'),'pre-exposure named transduction policy')
        if [row['plan']['spec']['mode'],row['plan']['spec']['policy_id']] in transduction['enabled_mode_policy_pairs']:
            digest(transduction['qualification']);transformed=self._request(eid,repetition,selected['source'],'QUERY_TRANSFORM','frozen_case_local_unlabeled_transform',parents,inputs,None,{'products':[],'full_original_query':prepared['public'],'metadata_or_target_changes_allowed':False});prepared=self.projection.register_query_transform(eid,repetition,prepared,transformed);row['outputs'].append(transformed);parents=[row['development_close'],selected['state'],prepared['receipt']];inputs['query']={'host':prepared['host_root'],'guest':'/inputs/query','identity':prepared['member']['sha256']}
            import copy
            products=copy.deepcopy(products)
            for product in products:product['parents']=[r['record_sha256'] for r in parents]
        result=self._request(eid,repetition,selected['source'],'PREDICT','predict_complete_frozen_query',parents,inputs,None,{'products':products,'query_rows':prepared['public']['rows'],'fit_or_selection_after_query':False});row['query'][repetition]={'preparation':prepared['receipt'],'inference':result};row['outputs'].append(result)
        diagnostics=self._templates(eid,repetition,'DIAGNOSE',parents)
        if diagnostics:
            diagnostic_result=self._request(eid,repetition,selected['source'],'DIAGNOSE','complete_frozen_query_diagnostics',parents,inputs,None,{'products':diagnostics,'query_rows':prepared['public']['rows']});row['outputs'].append(diagnostic_result)
        return result
