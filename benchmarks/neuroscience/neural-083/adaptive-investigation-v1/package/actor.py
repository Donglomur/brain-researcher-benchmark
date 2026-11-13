"""Fresh single-query investigation with genuine model and native tool calls."""
import hashlib
import json
import math
from pathlib import Path


def actions(tool_mode):
    value={
      'python':{'type':'object','properties':{'code':{'type':'string','minLength':1,'maxLength':65536}},
                'required':['code'],'additionalProperties':False},
      'predict':{'type':'object','properties':{'p_right':{'type':'number','minimum':0,'maximum':1}},
                 'required':['p_right'],'additionalProperties':False},
      'abstain':{'type':'object','properties':{'reason':{'type':'string','minLength':1,'maxLength':256}},
                 'required':['reason'],'additionalProperties':False}}
    if tool_mode=='agent_plus_decoder':
        value['decoder']={'type':'object','properties':{},'required':[],'additionalProperties':False}
    return value


def probability(value):
    try:valid=type(value)in (int,float) and math.isfinite(value) and 0<=value<=1
    except OverflowError:valid=False
    if not valid:
        raise ValueError('one finite non-boolean probability')
    return float(value)


def outcome(action):
    if action['name']=='predict':
        if set(action['arguments'])!={'p_right'}:raise ValueError('exact own prediction')
        return {'status':'complete','p_right':probability(action['arguments']['p_right'])}
    if action['name']=='abstain':
        reason=action['arguments'].get('reason')
        if set(action['arguments'])!={'reason'} or type(reason)is not str or not 0<len(reason)<=256:
            raise ValueError('explicit bounded abstention')
        return {'status':'abstain','reason':reason}
    return None


def initial_messages(prompt,mode,metadata):
    identity={k:metadata[k] for k in ('generation','case','setting','arm')}
    return [{'role':'system','content':prompt},
        {'role':'user','content':json.dumps(dict(identity=identity,query=metadata['query'][0],
            allowed_tools=sorted(actions(mode)),input_policy={
            'python_globals':['np','training','training_metadata','query','query_metadata']+
                (['decoder_probability'] if mode=='agent_plus_decoder' else []),
            'query_shape':metadata['query_shape'],
            'training_is_immutable_and_condition_permitted':True,
            'no_other_query_or_evaluator_feedback':True,
            'no_fitting_on_query_or_cross_query_state':True,
            'python_must_assign_json_result':True,
            'prediction_is_your_own_probability_not_decoder_acceptance':True}),sort_keys=True)}]


def tool_message(name,query,result):
    return {'role':'user','content':json.dumps(dict(tool=name,query=query,result=result),
                                              sort_keys=True,allow_nan=False)}


def cost_summary(collector):
    if collector is None:return None
    if not hasattr(collector,'entries'):return {'fixture_only':True}
    return dict(request_count=len(collector.entries),
        charged_input_tokens=collector._charged_input_tokens,
        charged_output_tokens=collector._charged_output_tokens,
        full_ledger_retained_by_programme=True,observed_billing=None,observed_cpu=None)


def investigate(*,c,provider,provider_config,cost_collector,prompt,mode,entrant,
                frozen_program,metadata,view,model,folder,ordinal,native,budget,
                deadline,max_model_calls,max_tool_calls,query_budget):
    """No caller transcript/cache is accepted or returned for another query."""
    query=metadata['query'][0]
    identity={k:metadata[k] for k in ('generation','case','setting','arm')}
    owner={'condition_id':hashlib.sha256(c.encoded(dict(identity=identity,mode=mode,entrant=entrant))).hexdigest(),
           'query_id':query}
    request_prefix=hashlib.sha256(c.encoded(owner)).hexdigest()
    folder=Path(folder);folder.mkdir(mode=0o700)
    transcript=[];model_records=[];tool_records=[];answer=None
    def save(name,value,cap=1048576):return c.save(folder/name,c.encoded(value),cap,budget.tick,budget.write)
    def tool(action,code=''):
        if len(tool_records)>=max_tool_calls:raise ValueError('original per-query numerical-call allowance')
        if action=='decoder' and mode=='generic_numerical':raise ValueError('generic condition has no supplied decoder')
        grant=query_budget.reserve()
        result,record=native.query(view,model,folder/('tool%02d'%len(tool_records)),ordinal,mode,action,code,grant=grant)
        c.need(result['identity']==identity and result['query']==query,'exact current-query tool owner')
        tool_records.append(record)
        return result['result']
    try:
        if mode=='decoder_alone':
            c.need(entrant=='decoder_alone','decoder-only comparison has no agent or arbitrary programme')
            value=tool('decoder')
            c.need(type(value)is dict and set(value)in ({'p_right'},{'abstain'}),'exact supplied decoder result')
            answer=(outcome({'name':'predict','arguments':value}) if 'p_right'in value else
                    outcome({'name':'abstain','arguments':{'reason':value['abstain']}}))
        elif entrant=='frozen_program':
            c.need(type(frozen_program)is str and 0<len(frozen_program.encode())<=65536,
                   'one externally frozen pointwise programme')
            value=tool('frozen_program',frozen_program)
            c.need(type(value)is dict and set(value)in ({'p_right'},{'abstain'}),'frozen prediction or explicit abstention')
            answer=outcome({'name':'predict','arguments':value}) if 'p_right' in value else outcome(
                {'name':'abstain','arguments':{'reason':value['abstain']}})
        else:
            c.need(entrant=='case_adaptive_equal_inputs_tools_compute','selected adaptive entrant')
            c.need(provider_config['study']['actions']==actions(mode),'exact frozen action policy for tool comparison')
            # Every query starts here. No previous query response, tool artifact,
            # output, token cache or transcript is an input to this function.
            transcript=initial_messages(prompt,mode,metadata)
            for turn in range(max_model_calls):
                budget.tick();query_budget.tick()
                config=dict(provider_config,owner=owner,request_id=request_prefix+'-'+str(turn))
                caps=provider_config['study']['caps']
                capture_reservation=budget.reserve_capture(caps['capture_bytes'])
                budget.read(caps['request_bytes']+caps['response_bytes']+caps['header_bytes']+262144)
                model_folder=folder/('model%02d'%turn);model_folder.mkdir(mode=0o700)
                sink=provider.DirectoryCaptureSink(model_folder,
                    max_bytes=caps['capture_bytes'])
                primary=None;response=None
                try:response=provider.complete(transcript,config,query_budget.deadline,sink,cost_collector)
                except BaseException as error:primary=error;raise
                finally:
                    try:sink.close()
                    except BaseException as error:
                        if primary is not None:
                            primary.provider_capture_close_error={'type':type(error).__name__,'message':str(error)[:2048]}
                            primary.add_note('Provider capture close failed: '+type(error).__name__)
                        else:
                            if response is not None:error.provider_actual_receipt=response['receipt']
                            raise
                model_records.append(response['receipt'])
                budget.settle_capture(capture_reservation,model_folder,
                    list(response['receipt']['captures'].values())+[response['receipt']['receipt_capture']])
                transcript.append(response['message'])
                action=response['action'];answer=outcome(action)
                if answer is not None:break
                c.need(action['name'] in ('python','decoder'),'declared numerical tool action')
                code=action['arguments']['code'] if action['name']=='python' else ''
                value=tool(action['name'],code)
                transcript.append(tool_message(action['name'],query,value))
            c.need(answer is not None,'explicit prediction or abstention before original model-call cap')
        budget.tick();query_budget.tick()
        # The model is free to disagree with decoder probabilities. The result
        # is validated, never replaced with an automatic decoder answer.
        record=dict(schema='neural083_single_query_actor_v1',owner=owner,identity=identity,
            query=query,entrant=entrant,tool_mode=mode,outcome=answer,
            model_records=model_records,tool_records=tool_records,query_budget=query_budget.snapshot(),
            query_started=query_budget.started,query_deadline=query_budget.deadline,
            transcript=transcript,other_queries_exposed=False,feedback_exposed=False,
            semantic_no_adaptation_requires_independent_method_review=True)
        pin=save('ACTOR.json',record)
        return answer,pin
    except BaseException as error:
        failure=dict(schema='neural083_single_query_actor_failure_v1',owner=owner,identity=identity,
            query=query,error_type=type(error).__name__,error=str(error)[:2048],
            model_records=model_records,tool_records=tool_records,transcript=transcript,
            costs=cost_summary(cost_collector),
            provider_actual_receipt=getattr(error,'receipt',getattr(error,'provider_actual_receipt',None)),
            provider_capture_close_error=getattr(error,'provider_capture_close_error',None),
            query_budget=query_budget.snapshot(),
            automatic_retry=False)
        error.adaptive_actual_failure=failure
        try:save('FAILURE.json',failure)
        except BaseException as secondary:error.add_note('Actor failure publication failed: '+type(secondary).__name__)
        raise
