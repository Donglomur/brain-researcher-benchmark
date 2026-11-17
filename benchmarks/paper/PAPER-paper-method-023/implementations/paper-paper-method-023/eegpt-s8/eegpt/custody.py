"""Host-issued chronological information ancestry for the complete G0/E policy.

No content hash, candidate declaration or administrative privilege can promote
an episode-derived artifact into a pre-exposure common resource. Receipts are
opaque compact references; original full records stay in the private journal.
"""
import hashlib,hmac,os
from .protocol import fields,need,digest,encode,decode,identity,persist,Refusal,observation

EPISODE_FIELDS=('mode','access','policy_id','actor_role','dataset','outer_fold','method')
LOCAL_KINDS=('context','source','prepared','state','prediction','diagnostic','analysis','feedback','development_close','generated','process','capture','failure')


def episode_spec(value):
    fields(value,EPISODE_FIELDS,'complete episode identity')
    need(value['mode'] in ('H','P','I') and value['access'] in ('A','B'),'original mode and access')
    need(value['actor_role'] in ('participant','reference'),'separate actual actor role')
    need(all(type(value[k]) is str and value[k] for k in ('policy_id','dataset','outer_fold','method')),'explicit original episode identity')
    return dict(value)


class Issuer:
    def __init__(self,journal,budget):
        self.key=os.urandom(32);self.journal=journal;self.budget=budget;self.sequence=0;self.records={};self.completion_pools={};self.genesis=None;self.episodes={};self.exposure_started=False;self.global_closed=False;self.targets_open=False;self.scoring_closed=False;self.release=None
    def reserve_completion(self,label):
        self.budget.guard('before_original_completion_reservation')
        cap=self.budget.limits['metadata_bytes'];self.budget.reserve('output_bytes',cap);self.budget.reserve_file()
        token=os.urandom(24).hex();self.completion_pools[token]={'label':label,'cap':cap,'used':False,'budget':self.budget};return token
    def _issue(self,kind,scope,parents,body,*,completion_pool=None):
        pool=None
        if completion_pool is None:self.budget.guard('before_original_issuance')
        else:
            need(kind=='process' and completion_pool in self.completion_pools,'actual original process evidence reserve')
            pool=self.completion_pools[completion_pool];need(not pool['used'],'one original completion publication, no retry refund');pool['used']=True
        for parent in parents:self.verify(parent)
        self.sequence+=1;record=decode(encode({'sequence':self.sequence,'kind':kind,'scope':scope,'parents':parents,'body':body}))
        token=hmac.new(self.key,encode(record),hashlib.sha256).hexdigest();need(token not in self.records,'fresh original receipt')
        raw=encode({'token':token,'original_record':record})
        need(len(raw)<=(self.budget.limits['metadata_bytes'] if pool is None else pool['cap']),'complete original receipt metadata limit')
        try:
            member=persist(self.journal,'receipt-'+str(self.sequence)+'.json',raw,ledger=self.budget if pool is None else None)
            if pool is not None:pool['budget'].observe('output_bytes',len(raw))
        except BaseException as exc:
            if pool is not None:
                prefix=(getattr(exc,'observation',None) or {}).get('known_written_prefix');pool['budget'].observe('output_bytes',None if prefix is None else prefix['bytes'])
            raise Refusal('original receipt publication failed',observation={'kind':kind,'scope':scope,'original_record':record,'original_record_identity':identity(record),'publication':observation(exc)}) from exc
        self.records[token]=record
        return {'token':token,'kind':kind,'ordinal':self.sequence,'record_sha256':identity(record),'journal':member}
    def verify(self,receipt,kind=None):
        fields(receipt,('token','kind','ordinal','record_sha256','journal'),'original issuer receipt');digest(receipt['token']);digest(receipt['record_sha256'])
        need(receipt['token'] in self.records,'same lifetime originally issued receipt');r=self.records[receipt['token']]
        need(receipt['kind']==r['kind'] and receipt['ordinal']==r['sequence'] and receipt['record_sha256']==identity(r),'exact original receipt binding')
        need(hmac.compare_digest(receipt['token'],hmac.new(self.key,encode(r),hashlib.sha256).hexdigest()),'original issuer MAC')
        if kind is not None:need(r['kind']==kind,'original receipt kind')
        return r
    def freeze_genesis(self,document,source_receipts,resource_receipts):
        need(self.genesis is None and not self.exposure_started and not self.episodes,'G0 before any campaign payload or feedback exposure')
        fields(document,('schema','campaign_id','scope_identity','scientific_policy','meta_algorithms','agent_policies','common_resources','pretraining_policy','selection_policy','seed_policy','budget_policy','retry_policy','scheduler_policy','release_policy','same_episode_repeat_sharing','transductive_policy','source_and_environment_identity','qualification'),'complete pre-exposure genesis')
        need(document['schema']=='eegpt_genesis_v1' and set(document['meta_algorithms'])=={'A','B'},'both pre-exposure method constructors')
        need(type(document['same_episode_repeat_sharing']) is bool,'declared local repeat dependence')
        # Source/resource receipts here are host admissions predating G0,
        # never future fitted states or caller-written evidence dictionaries.
        for receipt in source_receipts+resource_receipts:
            r=self.verify(receipt);need(r['kind'] in ('static_source','static_resource') and r['scope']=={'kind':'pre_exposure'},'only original admitted immutable static genesis parents')
        self.genesis=self._issue('genesis',{'kind':'genesis'},source_receipts+resource_receipts,document);return self.genesis
    def admit_static(self,kind,body):
        need(self.genesis is None and not self.exposure_started,'no static source/resource admission after pre-exposure seal')
        need(kind in ('static_source','static_resource'),'closed pre-exposure kinds');return self._issue(kind,{'kind':'pre_exposure'},[],body)
    def create_episode(self,spec,eligible_corpus,*,context_identity):
        need(self.genesis is not None and not self.global_closed and not self.targets_open,'new original episode before global closure')
        spec=episode_spec(spec);key=identity({'genesis':self.genesis['record_sha256'],'episode_spec':spec});need(key not in self.episodes,'fresh independent episode, no state reset')
        for receipt in eligible_corpus:
            r=self.verify(receipt,'corpus');need(identity(spec) in r['body']['eligible_episode_specifications'],'actual corpus eligibility for this exact descendant')
            need(r['body']['downstream_adaptive_ancestry'] is False,'corpus-only source/selection context')
        scope={'kind':'episode','episode_id':key,'spec':spec};row={'scope':scope,'status':'development','contexts':[],'active_processes':set(),'feedback':[],'attempts':0,'final_selection':None,'query_receipts':[],'original_failures':[]}
        self.episodes[key]=row
        receipt=self._issue('context',scope,[self.genesis]+eligible_corpus,{'fresh_context_identity':context_identity,'empty_adaptive_cache':True,'previous_episode_parent':None})
        row['contexts'].append(receipt);return key,receipt
    def publish_corpus(self,parents,body):
        need(self.genesis is not None and not self.global_closed,'qualified original common-corpus producer before global closure')
        fields(body,('source','state','producer','eligible_episode_specifications','downstream_adaptive_ancestry','recipe','exposure_evidence'),'original corpus product')
        need(body['downstream_adaptive_ancestry'] is False,'no common promotion of downstream-dependent pretraining')
        need(body['eligible_episode_specifications'] and len(set(body['eligible_episode_specifications']))==len(body['eligible_episode_specifications']),'explicit complete eligible descendant specifications')
        for p in parents:
            r=self.verify(p);need(r['scope']['kind'] in ('genesis','pre_exposure','corpus'),'no episode feedback/source/state parent in common corpus')
        return self._issue('corpus',{'kind':'corpus'},parents,body)
    def eligible(self,episode,parents,*,repetition=None):
        need(episode in self.episodes,'existing actual episode');row=self.episodes[episode];spec=row['scope']['spec']
        for p in parents:
            r=self.verify(p);scope=r['scope']
            if scope['kind']=='pre_exposure':
                need(p in self.verify(self.genesis,'genesis')['parents'],'actual admitted G0 ancestor, not a later byte-identical alias')
            elif scope['kind']=='genesis':need(p==self.genesis,'same campaign G0')
            elif scope['kind']=='corpus':need(identity(spec) in r['body']['eligible_episode_specifications'] and not r['body']['downstream_adaptive_ancestry'],'eligible corpus-only ancestry')
            else:
                need(scope['kind']=='episode' and scope['episode_id']==episode and scope['spec']==spec,'no cross-fold/dataset/mode/access/reference adaptive ancestry')
                prior=r['body'].get('repetition')
                if prior is not None and repetition is not None and prior!=repetition:need(self.verify(self.genesis,'genesis')['body']['same_episode_repeat_sharing'],'no undeclared local adaptive sharing across repetitions')
        return row
    def start_process(self,episode,call_id,parents,*,call,repetition,query=False,issued_request=None):
        row=self.eligible(episode,parents,repetition=repetition);need(not self.global_closed and not self.targets_open,'no producer launch after global close/targets')
        need(row['status']==('closed_development' if query else 'development'),'original local development/query phase')
        need(issued_request is not None,'actual host-issued request before original producer launch')
        request=decode(encode(issued_request));spec=row['scope']['spec']
        need(request['call']==call and request['scope']=={k:spec[k] for k in spec if k!='actor_role'}|{'repetition':repetition},'issued request matches actual full private episode and repetition')
        need(request['public_parent_identities']==[p['record_sha256'] for p in parents],'issued request original private parents')
        need(call_id not in row['active_processes'],'fresh active process');pool=self.reserve_completion(call_id)
        row['active_processes'].add(call_id);row['attempts']+=1;self.exposure_started=True
        return {'completion_pool':pool,'episode':episode,'call':call,'call_id':call_id,'repetition':repetition,'query':query,'parents':parents,'issued_request':request,'request_identity':identity(request)}
    def end_process(self,start,body):
        row=self.episodes[start['episode']];need(start['call_id'] in row['active_processes'],'actual original active process')
        # Removal requires an observed original reap/descendant closure. Failed
        # or unknown cleanup stays active and prevents global target admission.
        complete_cleanup=body['observation']['reaped'] is True and body['observation']['descendants_closed'] is True and body.get('launch_state') in ('never_attempted','observed_closed')
        if complete_cleanup:row['active_processes'].remove(start['call_id'])
        receipt=self._issue('process',row['scope'],start['parents'],{**body,'call':start['call'],'call_id':start['call_id'],'repetition':start['repetition'],'issued_request':start['issued_request'],'request_identity':start['request_identity']},completion_pool=start['completion_pool'])
        if body['original_budget_record']['status']!='completed':row['original_failures'].append(receipt)
        return receipt
    def publish_local(self,episode,kind,parents,body,*,repetition=None,query=False):
        need(kind in LOCAL_KINDS and kind not in ('process','development_close'),'host-owned local publication kind')
        row=self.eligible(episode,parents,repetition=repetition)
        need(not self.global_closed and not self.targets_open,'no new adaptive/predictive publication after closure')
        need(row['status']==('closed_development' if query else 'development'),'correct actual local phase')
        receipt=self._issue(kind,row['scope'],parents,{**body,'repetition':repetition})
        if kind=='feedback':row['feedback'].append(receipt)
        if query:row['query_receipts'].append(receipt)
        return receipt
    def close_development(self,episode,selections,parents):
        row=self.eligible(episode,parents);need(row['status']=='development' and not row['active_processes'],'all local producers reaped before immutable selection')
        receipt=self._issue('development_close',row['scope'],parents,{'selections':selections,'feedback':row['feedback'],'original_failed_attempts':row['original_failures'],'query_feedback_seen':False})
        row['status']='closed_development';row['final_selection']=receipt;return receipt
    def close_episode(self,episode,complete_slots,reason=None):
        row=self.episodes[episode];need(not row['active_processes'],'original descendant closure before episode finalization')
        need(row['status'] in ('development','closed_development'),'one episode closure; failures never reopen search')
        receipt=self._issue('episode_close',row['scope'],row['contexts']+row['query_receipts']+([row['final_selection']] if row['final_selection'] else []),{'complete_slots':complete_slots,'reason':reason,'original_failed_attempts':row['original_failures'],'development_was_sealed':row['final_selection'] is not None})
        row['status']='closed';row['close']=receipt;return receipt
    def select_reference(self,dataset,fold,mode,access,policy,records,method_order):
        need(not self.global_closed and not self.targets_open,'S_df before target or global closure')
        need(set(records)==set(method_order) and len(method_order)==4,'all four original controls')
        means=[];parents=[];support=None;reducer=None
        for method in method_order:
            need(set(records[method])=={0,1,2},'all3 original validation runs for each fixed control');values=[]
            for repetition,p in sorted(records[method].items()):
                r=self.verify(p,'feedback');spec=r['scope']['spec'];body=r['body']
                episode=self.episodes[r['scope']['episode_id']];need(episode['status']=='closed_development' and episode['final_selection'] is not None,'all reference development closed before S_df selection');sealed=self.verify(episode['final_selection'],'development_close')['body']['selections'];need(sealed['all_three_repetitions_selected'] is True and set(sealed['selected'])=={'0','1','2'} and sealed['selected'][str(repetition)]['feedback']==p and sealed['selected'][str(repetition)]['state']==body['state'],'each selector input belongs to the actually sealed selected predictor, not a discarded or failed attempt');self.verify(body['state'],'state')
                need(spec=={'mode':mode,'access':access,'policy_id':policy,'actor_role':'reference','dataset':dataset,'outer_fold':fold,'method':method},'same-fold independent reference validation ancestry only')
                need(body['repetition']==repetition and body['support_role']=='validation' and body['status']=='complete' and body['monitor'] is not None,'actual complete original validation monitor; no available-subset selector')
                from .protocol import finite
                digest(body['support_identity']);digest(body['trusted_reducer_source'])
                if support is None:support=body['support_identity'];reducer=body['trusted_reducer_source']
                need(body['support_identity']==support and body['trusted_reducer_source']==reducer,'all twelve same validation support and independent reducer source')
                actual=[self.verify(x,'process') for x in r['parents'] if x['kind']=='process'];need(len(actual)==1 and actual[0]['body']['call']=='ANALYZE' and actual[0]['body']['original_budget_record']['status']=='completed' and actual[0]['body']['source_identity']==body['trusted_reducer_source'],'original completed trusted numerical reduction, never participant-supplied score')
                values.append(finite(body['monitor'],'trusted validation monitor'));parents.append(p)
            means.append(sum(values)/3)
        # Listed order is the exact fixed tie rule.
        index=max(range(4),key=lambda i:means[i]);body={'dataset':dataset,'outer_fold':fold,'mode':mode,'access':access,'policy_id':policy,'method_order':method_order,'mean_validation_monitors':means,'selected_method':method_order[index],'assessment_used':False,'full_validation_support_identity':support,'trusted_reducer_source':reducer}
        return self._issue('reference_selection',{'kind':'selector','dataset':dataset,'outer_fold':fold,'mode':mode,'access':access,'policy_id':policy},parents,body)
    def close_global(self,required_episode_ids,collection,selectors):
        need(not self.global_closed and not self.targets_open and set(required_episode_ids)==set(self.episodes),'complete original episode set; no dropped fold')
        need(all(row['status']=='closed' and not row['active_processes'] for row in self.episodes.values()),'all H/P/I A/B branches and descendants closed')
        for p in selectors:self.verify(p,'reference_selection')
        receipt=self._issue('global_close',{'kind':'global_closed'},[self.genesis]+[self.episodes[e]['close'] for e in sorted(self.episodes)]+selectors,{'collection':collection,'required_episodes':sorted(required_episode_ids),'selector_receipts':selectors,'no_active_prediction_process':True})
        self.global_closed=True;return receipt
    def admit_targets(self,closure):
        self.verify(closure,'global_close');need(self.global_closed and not self.targets_open,'one irreversible original target admission')
        self.budget.guard('before_private_target_open');self.targets_open=True;return identity(closure)
    def close_scores(self,closure,report_identity):
        self.verify(closure,'global_close');need(self.targets_open and not self.scoring_closed,'original full scoring closure')
        self.budget.guard('after_all_private_scoring');receipt=self._issue('score_close',{'kind':'scores_closed'},[closure],{'report_identity':report_identity});self.scoring_closed=True;return receipt
    def authorize_report(self,score,aggregate_identity):
        self.verify(score,'score_close');need(self.scoring_closed and self.release is None,'one identical aggregate release after all prediction/scoring branches')
        self.release=self._issue('aggregate_release',{'kind':'report_only'},[score],{'aggregate_identity':aggregate_identity,'fresh_report_context_required':True,'prediction_backedge_allowed':False});return self.release


def _seal_completed_corpus(self,episode,state_receipt,source_receipt,eligible_specifications,exposure_evidence):
    """Promote only a completed corpus-only lineage, never a downstream E.

    This is the one explicit bridge from actual corpus execution to common
    eligible parents. A content hash or caller assertion cannot use it.
    """
    need(episode in self.episodes and not self.targets_open and not self.global_closed,'actual original corpus producer before global closure');row=self.episodes[episode]
    need(row['scope']['spec']['dataset']=='CORPUS' and row['scope']['spec']['outer_fold']=='corpus' and row['status']=='closed' and not row['active_processes'],'entire original corpus-only producer closed')
    digest(exposure_evidence);need(eligible_specifications and len({identity(x) for x in eligible_specifications})==len(eligible_specifications),'complete distinct actual downstream eligibility set')
    origin=row['scope']['spec'];allowed=[]
    for spec in eligible_specifications:
        episode_spec(spec);need(all(spec[k]==origin[k] for k in ('mode','access','policy_id','actor_role')),'no candidate/reference/mode/access parent shortcut');allowed.append(identity(spec))
    seen=set()
    def walk(receipt):
        record=self.verify(receipt)
        if receipt['token'] in seen:return
        seen.add(receipt['token']);scope=record['scope']
        if scope['kind']=='episode':
            need(scope['episode_id']==episode and scope['spec']['dataset']=='CORPUS','no downstream-selected source/context/cache/state in common parent')
            if record['kind']=='prepared':need(record['body']['role'] in ('corpus_train','corpus_validation'),'actual only-corpus mounted information')
            if record['kind']=='process':
                need(record['body']['call'] in ('DESCRIBE','PREPARE','PRETRAIN','DIAGNOSE','ANALYZE'),'no downstream fitting/validation/query source in shared pretraining')
                need(record['body']['original_budget_record']['status']=='completed','every original actual common producer complete')
        else:need(scope['kind'] in ('genesis','pre_exposure','corpus'),'eligible original common-only ancestry')
        for parent in record['parents']:walk(parent)
    for parent in (state_receipt,source_receipt,row['close']):walk(parent)
    body={'source':source_receipt,'state':state_receipt,'producer':row['close'],'eligible_episode_specifications':allowed,'downstream_adaptive_ancestry':False,'recipe':origin['method'],'exposure_evidence':exposure_evidence,'actual_original_ancestry_receipts_checked':len(seen)}
    return self._issue('corpus',{'kind':'corpus','recipe_identity':identity(origin)},[state_receipt,source_receipt,row['close']],body)


Issuer.seal_completed_corpus=_seal_completed_corpus


def _start_report(self,call_id,parents,source_identity,access):
    need(self.scoring_closed and self.release is not None and access in ('A','B'),'fresh report only after immutable score release')
    need(parents==[self.release]+[p for p in self.verify(self.genesis,'genesis')['parents'] if p['kind']=='static_source' and self.verify(p)['body'].get('role')==access],'report receives only identical aggregate release and its original pre-exposure source')
    need(self.verify(parents[1],'static_source')['body']['source_identity']==source_identity,'same actual sealed reporter source')
    if not hasattr(self,'report_processes'):self.report_processes={}
    need(access not in self.report_processes,'one fresh original report process per access arm; no retries or feedback')
    pool=self.reserve_completion(call_id);row={'call_id':call_id,'access':access,'parents':parents,'completion_pool':pool,'source_identity':source_identity,'active':True};self.report_processes[access]=row;return row


def _end_report(self,start,body):
    need(self.report_processes[start['access']] is start and start['active'],'original report child completion')
    if body['observation']['reaped'] is True and body['observation']['descendants_closed'] is True and body.get('launch_state') in ('never_attempted','observed_closed'):start['active']=False
    return self._issue('process',{'kind':'report_only','access':start['access']},start['parents'],{**body,'call':'INTERPRET','call_id':start['call_id'],'source_identity':start['source_identity'],'new_empty_context':True,'no_prediction_or_selection_backedge':True},completion_pool=start['completion_pool'])


def _capture_report(self,process,body):
    r=self.verify(process,'process');need(r['scope']['kind']=='report_only' and r['body']['call']=='INTERPRET' and r['body']['original_budget_record']['status']=='completed','actual completed report-only producer');need(not self.report_processes[r['scope']['access']]['active'],'all original report descendants reaped')
    return self._issue('capture',r['scope'],[process],body)

Issuer.start_report=_start_report
Issuer.end_report=_end_report
Issuer.capture_report=_capture_report
