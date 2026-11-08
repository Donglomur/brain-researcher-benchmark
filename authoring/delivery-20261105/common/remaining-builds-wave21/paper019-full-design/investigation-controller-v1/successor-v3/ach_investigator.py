"""Actual adaptive training-only provider/tool loop, disabled by deployment gates.

An inner diagnostic is explicitly adaptive. It does not estimate the generalization
of the whole investigator. Only the sealed bundle's untouched outer queries do.
"""
import math
from ach_util import need,pin,pin_bytes,encode,decode,exact_fields,finite,finish_owned
from ach_policy import InvestigationState
from ach_views import minimal_row
from ach_jobs import ToolExecutionFailure

TOOL_PARAMETERS={
 'analysis':{'source':'string'},
 'fit':{'source':'string','training_animals':'array'},
 'validate':{'fit_id':'string','validation_animals':'array'},
 'seal':{'fit_id':'string','selection_rationale':'string'}}

def tool_specs():
    descriptions={
      'analysis':'Run Python against this complete permitted outer-training view and common paper materials; return a summary and optional PNG/JPEG figures.',
      'fit':'Fit a generated Python four-head method using exactly the named training-animal aliases; source also implements predict. No held partition labels are mounted for this numeric fit.',
      'validate':'Run sealed predictions on named outer-training animals excluded from that fit; controller computes diagnostic error. Adaptive selection diagnostics only.',
      'seal':'Select one complete four-head fit trained on every outer-training animal; seal generated code/config/state before any outer query.'}
    return [{'type':'function','function':{'name':name,'description':descriptions[name],
        'parameters':{'type':'object','additionalProperties':False,'required':list(fields),
            'properties':{k:({'type':'array','items':{'type':'string'},'minItems':1,'uniqueItems':True}
                if t=='array' else {'type':'string'}) for k,t in fields.items()}}}} for name,fields in TOOL_PARAMETERS.items()]

class ProviderSession:
    def __init__(self,helpers,wire_policy,wire_limits,deployment_path,deployment_pin,ledger,authorization_header,journal):
        self.wire=helpers.get('investigator_wire');self.policy=wire_policy;self.limits=wire_limits
        self.path,self.deployment_pin,self.ledger=deployment_path,deployment_pin,ledger
        self.authorization=authorization_header;self.journal=journal
    def call(self,messages,specs,image_sources):
        request=self.wire.build_request(self.policy,messages,specs,self.limits,image_sources=image_sources)
        self.journal.append('provider_request',{'request_pin':request['request_pin'],'body':decode(request['body'],self.limits['max_request_bytes'])})
        try:
            result=self.wire.send_https(request,self.policy,self.path,self.deployment_pin,self.ledger,self.authorization)
            self.journal.append('provider_response',decode(result['raw_response'],self.limits['max_response_bytes']))
            return result
        except BaseException as error:
            if hasattr(error,'receipt'):
                receipt=dict(error.receipt);prefix=receipt.pop('response_prefix',b'')
                # Preserve exact failed-response bytes without interpreting them as
                # an accepted scientific result. No credential is serialized.
                import base64
                finish_owned([('provider failed-prefix journal',lambda:self.journal.append('provider_failed_prefix',
                    {'receipt':receipt,'prefix_base64':base64.b64encode(prefix).decode()},cutoff='closeout'))],error)
            raise

class Investigator:
    def __init__(self,jobs,session,journal,ledger):
        self.jobs,self.session,self.journal,self.ledger=jobs,session,journal,ledger
    def fit(self,policy,spec,training,materials):
        state=InvestigationState(policy,spec,pin(training));fits={};images={};messages=[];training_failures=0
        tools=tool_specs()
        need(policy['tool_specs']=={x['function']['name']:pin(x) for x in tools},'immutable exact scientific tool definitions')
        need(self.session.policy['policy_pin']==pin(policy),'provider call bound to same immutable global policy')
        need(self.session.policy['model']==policy['model']['model'] and
             policy['model']['parameters']=={k:self.session.policy[k] for k in ('temperature','seed')} and
             policy['randomization']['seed']==self.session.policy['seed'],
             'actual provider model and inference parameters match the sealed policy')
        # Global max_calls is the whole-program ledger ceiling. This fresh state
        # additionally enforces its per-bundle ceiling; the global ledger is never reset.
        need(self.session.limits['max_calls']==self.ledger.limits['provider_calls'],'whole-program provider ceiling')
        animals=sorted({r['animal'] for r in training['rows']})
        need(animals and training['inner_metric_interpretation']=='adaptive_selection_diagnostics','complete outer-training realm')
        protocol={'method_interface':'ach_generated_four_head_program_v1',
            'argv':['INPUT.json','OUTPUT_DIRECTORY'],'result_file':'RESULT.json',
            'fit_result':{'kind':'fit','heads':{s:['MODEL_FILE'] for s in training['strata']},'method_description':'text'},
            'predict_result':{'kind':'predict','id':'same query.id','log_seconds':'finite natural-log seconds'},
            'analysis_result':{'kind':'analysis','summary':'text','images':{'FILE.png':'image/png'}},
            'model_files':'predict input maps filenames to immutable absolute paths',
            'training_animals':animals,'training_rows':len(training['rows']),
            'query_labels':'never present','inner_metrics':'adaptive selection diagnostics, not unbiased evaluation'}
        messages=[{'role':'system','content':policy['system_prompt']},
            {'role':'user','content':policy['task_prompt']+'\n'+encode(protocol).decode()}]
        try:
            while state.sealed is None:
                self.ledger.tick();conversation=encode(messages)
                state.reserve({'conversation_bytes':len(conversation),'provider_calls':1,
                    'input_tokens':self.session.limits['max_input_tokens'],
                    'output_tokens':self.session.limits['max_output_tokens']},'provider request reservation')
                answer=self.session.call(messages,tools,images)
                state.record({'kind':'provider','request_pin':answer['request_pin'],'response_pin':answer['response_pin'],'usage':answer['usage']})
                need(answer['actions'],'provider must continue investigation or explicitly seal; no answer-only success')
                assistant={'role':'assistant','content':answer['analysis'],'tool_calls':[
                    {'id':a['id'],'type':'function','function':{'name':a['name'],'arguments':encode(a['arguments']).decode()}}
                    for a in answer['actions']]}
                messages.append(assistant)
                for action in answer['actions']:
                    name,args=action['name'],action['arguments']
                    exact_fields(args,TOOL_PARAMETERS[name],'exact declared tool arguments')
                    need(state.sealed is None,'no work after seal in same response')
                    if name in ('analysis','fit'):
                        need(type(args['source']) is str,'literal generated Python source');source=args['source'].encode()
                        state.reserve({'generated_code_bytes':len(source)},name+'/source')
                        revision=pin_bytes(source);state.revisions[revision['sha256']]=revision
                    try:
                        if name=='analysis':
                            state.reserve({'analysis_processes':1,'result_bytes':self.jobs.limits['result_bytes'],
                                'model_bytes':self.jobs.limits['model_bytes']},name+'/preventive full output reservation')
                            outcome=self.jobs.run('analysis',source,{'kind':'analysis','training':training},materials)
                            result=outcome['result'];exact_fields(result,('kind','summary','images'),'analysis result')
                            need(result['kind']=='analysis' and type(result['summary']) is str and type(result['images']) is dict,'actual analysis text/image metadata')
                            need(set(result['images'])==set(outcome['files']),'every analysis artifact is an explicitly typed figure')
                            image_parts=[]
                            for file,mime in result['images'].items():
                                image_pin=pin_bytes(outcome['files'][file])
                                metadata=self.session.wire.image_part(outcome['files'][file],mime,image_pin,self.session.limits)
                                images[image_pin['sha256']]={'source_pin':image_pin,'provenance_pin':outcome['closure_pin']}
                                image_parts.append(metadata['part'])
                            feedback={'summary':result['summary'],'source_pin':revision,'closure_pin':outcome['closure_pin']}
                        elif name=='fit':
                            requested=args['training_animals'];need(type(requested) is list and requested and len(requested)==len(set(requested))
                                and set(requested)<=set(animals),'exact specified numeric fitting animals')
                            selected={**training,'rows':[r for r in training['rows'] if r['animal'] in requested]}
                            state.reserve({'fit_processes':1,'result_bytes':self.jobs.limits['result_bytes'],
                                'model_bytes':self.jobs.limits['model_bytes']},name+'/preventive full output reservation')
                            fitted=self.jobs.candidate_fit(source,selected,materials)
                            fit_id='fit_'+str(len(fits));fits[fit_id]={**fitted,'training_animals':sorted(requested),'training_view_pin':pin(selected)}
                            feedback={'fit_id':fit_id,'training_animals':sorted(requested),'source_pin':revision,
                                'model_pin':fitted['state_pin'],'head_manifest_pin':fitted['head_manifest_pin']}
                        elif name=='validate':
                            need(args['fit_id'] in fits,'actual earlier fit');fit=fits[args['fit_id']]
                            held=args['validation_animals'];need(type(held) is list and held and len(held)==len(set(held)) and
                                set(held)<=set(animals)-set(fit['training_animals']),'validation animals excluded from own numeric fit')
                            values={};predictions={}
                            for row in training['rows']:
                                if row['animal'] not in held:continue
                                query={k:v for k,v in row.items() if k not in ('animal','session','seconds')}
                                state.reserve({'validation_processes':1,'result_bytes':self.jobs.limits['result_bytes']},name+'/prediction')
                                predicted,outcome=self.jobs.candidate_predict(fit,query,materials)
                                error=finite(predicted-math.log(row['seconds']));squared=finite(error*error)
                                need(squared!=0 or error==0,'diagnostic square underflow')
                                values.setdefault((row['animal'],row['stratum'],row['session']),[]).append(squared)
                                predictions[row['id']]={'log_seconds':predicted,'closure_pin':outcome['closure_pin']}
                            diagnostic={}
                            for animal in held:
                                diagnostic[animal]={}
                                for stratum in training['strata']:
                                    groups=[xs for (a,s,_),xs in values.items() if (a,s)==(animal,stratum)]
                                    need(groups,'complete validation stratum support')
                                    diagnostic[animal][stratum]=finite(math.fsum(math.fsum(xs)/len(xs) for xs in groups)/len(groups))
                            feedback={'fit_id':args['fit_id'],'squared_log_error_by_animal_stratum':diagnostic,
                                'interpretation':'adaptive_selection_diagnostics_only','predictions_pin':pin(predictions)}
                            self.journal.append('candidate_inner_predictions',predictions)
                        else:
                            need(args['fit_id'] in fits and type(args['selection_rationale']) is str,'actual selection and rationale')
                            fit=fits[args['fit_id']];need(fit['training_animals']==animals,'final fit includes every original outer-training animal')
                            selection={'fit_id':args['fit_id'],'rationale':args['selection_rationale'],'events_pin':pin(state.events),
                                'interpretation':'adaptive_outer_training_selection','source_pin':pin_bytes(fit['source'])}
                            seal=state.seal({'bundle_key':state.key,'policy_pin':pin(policy),'training_view_pin':pin(training),
                                'revision_pin':pin_bytes(fit['source']),'model_pin':fit['state_pin'],'selection_pin':pin(selection),
                                'head_manifest_pin':fit['head_manifest_pin']})
                            receipt=self.journal.append('candidate_final_seal',{'seal':seal,'selection':selection,
                                'fit_closure_pin':fit['closure_pin'],'model_files':{k:pin_bytes(v) for k,v in fit['files'].items()}})
                            return {'fit':fit,'selection':selection,'seal':seal,'seal_receipt':receipt,
                                'method_admission':{'method_conformance_evidence':fit['closure_pin'],
                                    'fit_search_ledger_pin':pin(state.events),'source_state_lineage_pin':pin(seal)}}
                        state.reserve({'result_bytes':len(encode(feedback))},name+'/feedback')
                        state.record({'kind':name,'arguments_pin':pin(args),'result':feedback})
                        messages.append({'role':'tool','tool_call_id':action['id'],'content':encode(feedback).decode()})
                        if name=='analysis' and image_parts:
                            # Provider image capability/role policy is independently
                            # admitted. A figure is never silently dropped or OCR-guessed.
                            messages.append({'role':'user','content':[{'type':'text','text':'Figures from the preceding training-only analysis.'}]+image_parts})
                    except ToolExecutionFailure as error:
                        if getattr(error,'ach_secondary_errors',[]):raise
                        training_failures+=1
                        failure={'kind':'ordinary_training_program_failure','attempt':training_failures,
                            'tool':name,'receipt':error.receipt,'literal_arguments_pin':action['literal_arguments_pin']}
                        state.record(failure);self.journal.append('investigator_retryable_training_failure',failure)
                        need(training_failures<=policy['randomization']['retries'],
                             'sealed training-failure retry ceiling; no free additional attempts')
                        feedback={'status':'generated_program_failed','exit_code':error.receipt['execution']['actual_child_exit_code'],
                            'stderr_excerpt':error.receipt['execution']['stderr_excerpt'],
                            'closure_pin':error.receipt['closure_pin'],'scientific_result':None}
                        state.reserve({'result_bytes':len(encode(feedback))},'training failure feedback')
                        messages.append({'role':'tool','tool_call_id':action['id'],'content':encode(feedback).decode()})
        except BaseException as error:
            state.fail(error);self.ledger.fail('investigation '+state.key,error)
            try:self.journal.append('investigation_failure',{'key':state.key,'events':state.events,'used':state.used,
                'generated_revisions':state.revisions,'error_type':type(error).__name__},cutoff='closeout')
            except BaseException as secondary:setattr(error,'investigation_failure_journal_error',type(secondary).__name__)
            raise
