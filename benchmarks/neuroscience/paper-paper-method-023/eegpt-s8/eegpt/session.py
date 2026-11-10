"""One real submitted-code API call with complete original evidence custody."""
import os
from pathlib import Path
from .execution import ProcessCustody
from .protocol import HandleCustody,Directory,fields,need,integer,descriptor,identity,encode,decode,persist,read_metadata,stream_capture,observation,Refusal

RESPONSE_FIELDS=('schema','request_id','status','artifacts','products','generated_source','selected_state','decision','diagnostics','method_declaration')


class Session:
    def __init__(self,root,issuer,budget,executor):
        self.root=Directory(str(root));self.issuer=issuer;self.budget=budget;self.executor=executor;self.calls=[]
    def call(self,episode,source,request,parents,*,repetition,reservation,inputs,query=False):
        request=decode(encode(request));parents=decode(encode(parents))
        self.budget.guard('before_original_call');call_id=os.urandom(24).hex();report_only=episode is None
        need(not report_only or request['call']=='INTERPRET','closed report-only source API')
        start=self.issuer.start_report(call_id,parents,source['identity'],request['scope']['access']) if report_only else self.issuer.start_process(episode,call_id,parents,call=request['call'],repetition=repetition,query=query,issued_request=request)
        owner=ProcessCustody(call_id);primary=None
        state={'call_id':call_id,'phase':'reserved','request_identity':identity(request),'source_identity':source['identity'],'original_process':owner.record,'capture_dispositions':[],'failures':[],'response':None,'response_member':None,'process_receipt':None,'capture_receipt':None};self.calls.append(state);output=None;captured=None
        try:
            need(request['source_identity']==source['identity'],'actual selected source is public request source')
            base=self.root.path/call_id;os.mkdir(base,0o700)
            for name in ('work','observer','capture','request'):os.mkdir(base/name,0o700)
            state['original_paths']={name:str(base/name) for name in ('work','observer','capture','request')};state['failed_output_disposition']='all original work files remain at original_paths.work; not accepted as complete products'
            output=Directory(str(base/'work'))
            with HandleCustody('original_request_publication') as owned:
                request_root=owned.own(Directory(str(base/'request')),'request')
                captured=Directory(str(base/'capture'))
                request_pin=persist(request_root,'REQUEST.json',encode(request),ledger=self.budget)
            bindings=[{'host':source['host_root'],'guest':'/source/method','identity':source['identity']},{'host':str(base/'request'),'guest':'/inputs/request','identity':request_pin['sha256']},*inputs]
            entry=[x.replace('/source/','/source/method/',1) if x.startswith('/source/') else x for x in source['manifest']['entrypoint']]
            job={'id':call_id,'reservation':reservation,'development':not query,'source_identity':source['identity'],'input_identity':identity(request)}
            original=self.executor.run(job,entry=entry,inputs=bindings,workspace=base/'work',observer_root=base/'observer',request='/inputs/request/REQUEST.json',response='/work/RESPONSE.json',custody=owner)
            state['original_process']=original;state['phase']='original_process_observed';process=(self.issuer.end_report(start,original) if report_only else self.issuer.end_process(start,original));state['process_receipt']=process
            need(original['original_budget_record']['status']=='completed','original source execution completed before response acceptance')
            # Capture response and every referenced artifact after descendant
            # closure; partial capture identities and prior dispositions persist.
            response_path=output.path/'RESPONSE.json';size=response_path.stat(follow_symlinks=False).st_size
            response_capture=stream_capture(output,'RESPONSE.json',size=size,cap=self.budget.limits['metadata_bytes'],ledger=self.budget,destination=captured,destination_name='RESPONSE.json');state['capture_dispositions'].append({'role':'response','status':'captured','original':response_capture})
            response=decode(read_metadata(captured,response_capture['captured'],cap=self.budget.limits['metadata_bytes'],ledger=self.budget));fields(response,RESPONSE_FIELDS,'complete participant response')
            need(response['schema']=='eegpt_science_response_v1' and response['request_id']==request['request_id'],'response matches actual blinded public request')
            need(response['status'] in ('ok','abstain','unsupported','failed'),'explicit source status');need(response['decision'] in ('continue','select','done','abstain','unsupported','failed'),'closed adaptive decision')
            need(type(response['artifacts']) is list and len({r['path'] for r in response['artifacts']})==len(response['artifacts']),'complete unique artifact inventory')
            manifest_paths=set()
            for member in response['artifacts']:
                descriptor(member);manifest_paths.add(member['path']);need(member['path']!='RESPONSE.json','response cannot self-reference its own future byte pin')
                parent=captured.path/Path(member['path']).parent;parent.mkdir(parents=True,exist_ok=True)
                try:
                    record=stream_capture(output,member['path'],expected=member,cap=self.budget.limits['per_file_bytes'],ledger=self.budget,destination=captured,destination_name=member['path']);state['capture_dispositions'].append({'role':'artifact','path':member['path'],'status':'captured','original':record})
                except BaseException as exc:
                    state['capture_dispositions'].append({'role':'artifact','path':member['path'],'status':'partial_or_failed_capture_original_retained','failure':observation(exc)});raise
            if response['generated_source'] is not None:
                if set(response['generated_source'])=={'reuse'}:
                    need(response['generated_source']['reuse']==source['identity'],'reuse names the actual current source, not any exposed hash')
                else:need({r['path'] for r in response['generated_source']['files']}<=manifest_paths,'all generated source files are actual observed artifacts')
            if response['selected_state'] is not None:need(set(response['selected_state']['files'])<=manifest_paths,'all opaque model-state files actually captured')
            for product in response['products']:
                if product['type']=='T02' and product['status']=='complete':
                    need(all(member in response['artifacts'] for member in product['body']['states']),'every opaque model file actually captured in the original producer')
                    need(response['selected_state'] is not None and {r['path'] for r in product['body']['states']}==set(response['selected_state']['files']),'full declared fitted-state artifact set')
                need(set(r['path'] for r in product['arrays'].values())<=manifest_paths,'all declared scientific product arrays actually captured')
                for member in product['arrays'].values():need(member in response['artifacts'],'exact original artifact pin, not only a matching filename')
            state['response']=response;state['response_member']=response_capture['captured'];state['capture_root']=str(captured.path);state['phase']='captured'
            capture_body={'request_identity':identity(request),'response_identity':identity(response),'response_member':response_capture['captured'],'artifacts':response['artifacts'],'capture_dispositions':state['capture_dispositions']}
            if report_only:
                need(response['generated_source'] is None and response['selected_state'] is None and all(p['type']=='T14' and not p['arrays'] for p in response['products']),'report-only products cannot create or alter any predictor or numerical score')
                state['capture_receipt']=self.issuer.capture_report(process,capture_body)
            else:state['capture_receipt']=self.issuer.publish_local(episode,'capture',[process],capture_body,repetition=repetition,query=query)
            self.budget.guard('before_original_session_return');return state
        except BaseException as exc:
            primary=exc
            state['failures'].append({'phase':state['phase'],**observation(exc)});state['phase']='failed'
            if state['process_receipt'] is None:
                # The strong owner exists before launch. Its original observation
                # survives executor accounting and serialization failures.
                original=owner.record;state['original_process']=original
                original['startup_or_call_failure']=observation(exc)
                try:state['process_receipt']=(self.issuer.end_report(start,original) if report_only else self.issuer.end_process(start,original))
                except BaseException as publication:state['failures'].append({'phase':'original_completion_publication','original':original,**observation(publication)})
            raise Refusal('original EEGPT participant call failed',observation=state) from exc
        finally:
            for label,handle in (('output',output),('capture',captured)):
                if handle is not None:
                    try:handle.close()
                    except BaseException as exc:state['failures'].append({'phase':label+'_close',**observation(exc)});state['phase']='failed'
            if primary is None and state['phase']=='failed' and state['response'] is not None:
                raise Refusal('original capture handle closure failed; no successful call admission',observation=state)
    def close(self):self.root.close()
