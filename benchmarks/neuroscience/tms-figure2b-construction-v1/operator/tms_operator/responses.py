"""Fixed Responses investigation loop; no hosted tools, retries or provider defaults.

Disclosed adaptation of N017 openai_transport/openai_protocol, not its executor.
The synchronous HTTP operation stays inside the host's owned Linux cgroup. A
terminal provider response is required; local cancellation proves no remote fact.
"""
from __future__ import annotations
import copy,hashlib,http.client,os,ssl,stat,time
from pathlib import Path
from .schema import *

ENDPOINT={'scheme':'https','host':'api.openai.com','port':443,'path':'/v1/responses'}
CREDENTIAL_KEYS={'path','device','inode','uid','mode','bytes','mtime_ns','ctime_ns'}

def credential(value,budget):
    keys(value,CREDENTIAL_KEYS)
    require(type(value['path']) is str and Path(value['path']).is_absolute(),'explicit private credential path')
    for name in CREDENTIAL_KEYS-{'path'}:integer(value[name],0)
    integer(value['bytes'],1,16384);require(value['mode']==0o600,'owner-only credential')
    fd=os.open(value['path'],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);body=bytearray()
    try:
        a=os.fstat(fd)
        actual=(a.st_dev,a.st_ino,a.st_uid,stat.S_IMODE(a.st_mode),a.st_size,a.st_mtime_ns,a.st_ctime_ns)
        expected=tuple(value[k] for k in ('device','inode','uid','mode','bytes','mtime_ns','ctime_ns'))
        require(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and actual==expected and a.st_uid==os.getuid(),'private credential identity')
        budget.charge(read=a.st_size,write=a.st_size)
        while len(body)<a.st_size:
            part=os.read(fd,min(4096,a.st_size-len(body)));require(bool(part),'credential short read');body.extend(part)
        b=os.fstat(fd);require((a.st_size,a.st_mtime_ns,a.st_ctime_ns)==(b.st_size,b.st_mtime_ns,b.st_ctime_ns),'credential changed')
        require(body and all(x in b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-' for x in body),'opaque credential format')
        budget.charge(read=2*len(body),write=2*len(body))
        return bytes(body).decode('ascii')
    except BaseException:
        raise Refusal('private credential admission failed; no secret-valued diagnostic') from None
    finally:
        for i in range(len(body)):body[i]=0
        os.close(fd)

class TransportFailure(Refusal):
    def __init__(self,raw,observation,error):
        self.raw=raw;self.observation=observation;self.original_error=error;self.original_error_type=type(error).__name__
        super().__init__('provider attempt failed; finite original prefix and status retained')

def post_once(request,key,cap,timeout,budget):
    """Actual one-shot HTTPS implementation. No injected production transport."""
    integer(cap,1,8*2**20);positive(timeout);exact_budget(budget)
    # Reserve the complete cap-plus-probe and immutable failure copy before dispatch.
    # Cleanup must preserve the first transport failure even if its budget expired.
    budget.charge(read=len(request)+cap+1,write=3*(cap+1))
    conn=response=None;raw=bytearray();failure=None
    obs={'endpoint':ENDPOINT,'attempted':False,'request_bytes':len(request),'request_complete':False,
         'http_status':None,'response_bytes':0,'response_eof':False,'response_closed':False,
         'connection_closed':False,'retries':0,'scope':'application bodies; no physical-network or remote-cancellation claim'}
    def remaining():
        budget.charge();return min(timeout,budget.deadline-time.monotonic())
    try:
        conn=http.client.HTTPSConnection(ENDPOINT['host'],ENDPOINT['port'],timeout=remaining(),context=ssl.create_default_context())
        obs['attempted']=True
        conn.request('POST',ENDPOINT['path'],body=request,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Accept':'application/json'})
        obs['request_complete']=True;response=conn.getresponse();obs['http_status']=response.status
        length=response.getheader('content-length')
        if length is not None:require(length.isdecimal() and int(length)<=cap,'response Content-Length cap')
        while True:
            t=remaining()
            if conn.sock is not None:conn.sock.settimeout(t)
            n=min(65536,cap-len(raw)+1);require(n>0,'response extent')
            block=response.read(n);require(type(block) is bytes,'response bytes')
            raw.extend(block);obs['response_bytes']=len(raw)
            require(len(raw)<=cap,'response exceeds cap')
            if not block:obs['response_eof']=True;break
        require(response.status==200,'non-success HTTP; no redirect or retry')
    except BaseException as error:failure=error
    finally:
        key=None
        for obj,flag in ((response,'response_closed'),(conn,'connection_closed')):
            if obj is not None:
                try:obj.close();obs[flag]=True
                except BaseException as error:
                    if failure is None:failure=error
        body=bytes(raw)  # Immutable prefix copy was reserved before any network action.
    if failure is not None:raise TransportFailure(body,obs,failure) from failure
    return body,obs

class InvestigationFailure(Refusal):
    """Strong original failure and state; never a successful agent receipt."""
    def __init__(self,first,state,secondary,transport,receipt_durable,raw_frame,prefix_descriptor):
        self.first=first;self.state=state;self.secondary=list(secondary)
        self.transport=transport;self.receipt_durable=receipt_durable
        self.raw_frame=raw_frame;self.prefix_descriptor=prefix_descriptor
        super().__init__('investigation failed; original and publication failures retained separately')
    def metadata(self):
        return {'schema':'tms_investigation_failure_v1','first_error_type':type(self.first).__name__,
            'first_transport_error_type':None if self.transport is None else self.transport.original_error_type,
            'secondary_publication_errors':[{'stage':stage,'error_type':type(error).__name__} for stage,error in self.secondary],
            'original_prefix_in_memory':self.raw_frame is not None,
            'original_prefix_bytes':None if self.raw_frame is None else len(self.raw_frame),
            'original_prefix_durable':self.prefix_descriptor is not None,
            'original_prefix_descriptor':self.prefix_descriptor,
            'agent_result_durable':self.receipt_durable,'outcome':'failed',
            'missing_durable_evidence_is_explicit_failure':True}

def usage(value):
    keys(value,{'input_tokens','output_tokens','total_tokens','input_tokens_details','output_tokens_details'})
    for k in ('input_tokens','output_tokens','total_tokens'):integer(value[k],0)
    i,o=value['input_tokens_details'],value['output_tokens_details']
    require(type(i) is dict and set(i) in ({'cached_tokens'},{'cached_tokens','cache_write_tokens'}),'known input token classes')
    keys(o,{'reasoning_tokens'})
    for n in i.values():integer(n,0);require(n<=value['input_tokens'],'input subset')
    integer(o['reasoning_tokens'],0)
    require(o['reasoning_tokens']<=value['output_tokens'] and value['total_tokens']==value['input_tokens']+value['output_tokens'],'usage arithmetic')
    return copy.deepcopy(value)

def tools(policy):
    return [{'type':'function','name':'terminal','description':'Execute a command only inside the isolated task container; no host execution.',
        'strict':True,'parameters':{'type':'object','properties':{
        'command':{'type':'string','minLength':1,'maxLength':65536},
        'timeout_seconds':{'type':'number','exclusiveMinimum':0,'maximum':policy['terminal_seconds']},
        'max_output_bytes':{'type':'integer','minimum':1,'maximum':policy['terminal_output_bytes']}},
        'required':['command','timeout_seconds','max_output_bytes'],'additionalProperties':False}}]

def terminal_arguments(a,policy):
    keys(a,{'command','timeout_seconds','max_output_bytes'})
    require(type(a['command']) is str and 0<len(a['command'])<=65536 and '\0' not in a['command'],'bounded terminal command')
    positive(a['timeout_seconds']);integer(a['max_output_bytes'])
    require(a['timeout_seconds']<=policy['terminal_seconds'] and a['max_output_bytes']<=policy['terminal_output_bytes'],'selected terminal policy')
    return a

def response(value,model,policy,max_items,seen):
    require(type(value) is dict and value.get('object')=='response' and type(value.get('id')) is str and value['id'],'Responses identity')
    require(value.get('model')==model,'returned exact model; no alias guessing')
    u=usage(value.get('usage'));status=value.get('status')
    require(status in ('completed','incomplete','failed','cancelled'),'unknown or pending provider outcome')
    items=value.get('output');require(type(items) is list and len(items)<=max_items,'complete finite output')
    calls=[];ids=set()
    for item in items:
        require(type(item) is dict,'output item');kind=item.get('type')
        if 'id' in item:
            require(type(item['id']) is str and item['id'] not in ids,'unique output identity');ids.add(item['id'])
        if kind=='reasoning':require(type(item.get('encrypted_content')) is str and item['encrypted_content'],'complete stateless reasoning item')
        elif kind=='message':
            require(item.get('role')=='assistant' and item.get('status')=='completed' and type(item.get('content')) is list,'completed assistant message')
            for block in item['content']:
                require(type(block) is dict and block.get('type')=='output_text' and type(block.get('text')) is str,'no unsupported/refusal content')
        elif kind=='function_call':
            require(item.get('name')=='terminal' and item.get('status','completed')=='completed' and item.get('async',False) is False and item.get('caller') in (None,{'type':'direct'}) and item.get('namespace') is None,'only synchronous local terminal tool')
            cid=item.get('call_id');require(type(cid) is str and cid and cid not in seen,'unique global call ID');seen.add(cid)
            require(type(item.get('arguments')) is str,'exact function argument bytes')
            a=terminal_arguments(json_body(item['arguments'].encode()),policy);calls.append((cid,a))
        else:raise Refusal('unsupported output type or hosted tool')
    return u,status,items,calls

def write_body(path,body,budget,cap):
    require(type(body) is bytes and len(body)<=cap,'finite private body')
    budget.charge(write=len(body));fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb',closefd=False) as stream:stream.write(body);stream.flush();os.fsync(fd)
    finally:os.close(fd)
    # Empty failure prefixes are legal here, not inherited scientific body pins.
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def initial_history(configuration):
    return [{'role':'system','content':configuration['instruction']},
        {'role':'user','content':'Reproduce the complete Figure2B output contract using all supplied inputs in /inputs. Write exactly OUTPUT.json and its 36 binary fields in /output. All task science and output instructions are supplied in /inputs/NUMERICAL_CONTRACT.md and /inputs/OUTPUT_SCHEMA.json.'}]

def request_document(configuration,policy,history):
    require(len(history)<=configuration['max_items'],'complete stateless history extent')
    return {'model':configuration['model'],'input':history,'store':False,'stream':False,'include':['reasoning.encrypted_content'],
        'truncation':'disabled','tools':tools(policy),'tool_choice':'auto','parallel_tool_calls':False,**configuration['parameters']}

def admit_result(receipt,configuration,policy,binding,journal,budget):
    """Reconstruct every actual request/history/tool join from pinned private bodies.

    This authenticates source/report consistency, not remote-provider truth absent
    the separately selected transport qualification. Host lifecycle is separate.
    """
    capsule(configuration);limits(policy);exact_budget(budget);root=directory(journal)
    keys(receipt,{'schema','binding','calls','reserved_input_tokens','reserved_output_tokens','observed_input_tokens','observed_output_tokens','terminal_calls','outcome','unknown_provider_outcome','failure_type'})
    require(receipt['schema']=='tms_figure2b_responses_agent_v1' and receipt['binding']==binding,'agent receipt binding')
    require(receipt['outcome']=='completed' and receipt['unknown_provider_outcome'] is False and receipt['failure_type'] is None,'actual provider completion required')
    calls=receipt['calls'];require(type(calls) is list and 1<=len(calls)<=policy['model_calls'],'complete attempt census')
    ri=configuration['model_input_reservation'];ro=configuration['parameters']['max_output_tokens']
    require(len(calls)*ri<=policy['model_input_tokens'] and len(calls)*ro<=policy['model_output_tokens'],'matched reservation ceilings')
    observed_i=observed_o=terminal_count=0;history=initial_history(configuration);seen=set()
    for n,record in enumerate(calls):
        keys(record,{'number','request','reserved_input_tokens','reserved_output_tokens','response','transport','usage','provider_status','tools'})
        require(type(record['number']) is int and record['number']==n and type(record['reserved_input_tokens']) is int and record['reserved_input_tokens']==ri and type(record['reserved_output_tokens']) is int and record['reserved_output_tokens']==ro,'exact attempt reservations')
        pin(record['request']);require(record['request']['bytes']<=configuration['max_request_bytes'],'original request byte cap')
        original=read_pinned(root/(str(n)+'.request.json'),record['request'],budget)
        expected=bounded_json(request_document(configuration,policy,history),configuration['max_request_bytes'])
        budget.charge(read=len(expected),write=len(expected));require(original==expected,'complete original request/history equality')
        require(record['response']['bytes']<=configuration['max_response_bytes'],'selected response cap')
        raw_body=read_pinned(root/(str(n)+'.response.json'),record['response'],budget)
        budget.charge(read=len(raw_body),write=len(raw_body));raw=json_body(raw_body)
        u,status,items,toolcalls=response(raw,configuration['model'],policy,configuration['max_items'],seen)
        require(status=='completed' and record['provider_status']==status and record['usage']==u,'terminal raw provider status and usage')
        require(u['input_tokens']<=ri and u['output_tokens']<=ro,'actual usage within selected reservations')
        observed_i+=u['input_tokens'];observed_o+=u['output_tokens']
        obs=record['transport'];keys(obs,{'endpoint','attempted','request_bytes','request_complete','http_status','response_bytes','response_eof','response_closed','connection_closed','retries','scope'})
        require(obs['endpoint']==ENDPOINT and all(obs[k] is True for k in ('attempted','request_complete','response_eof','response_closed','connection_closed')),'complete concrete transport observations')
        require(type(obs['http_status']) is int and obs['http_status']==200 and type(obs['retries']) is int and obs['retries']==0 and type(obs['request_bytes']) is int and obs['request_bytes']==record['request']['bytes'] and type(obs['response_bytes']) is int and obs['response_bytes']==record['response']['bytes'],'observed HTTP body/status joins')
        rows=record['tools'];require(type(rows) is list and len(rows)==len(toolcalls),'complete tool execution census')
        require(bool(toolcalls)==(n<len(calls)-1),'only final completed response finishes investigation')
        history.extend(copy.deepcopy(items))
        for j,((cid,args),tool) in enumerate(zip(toolcalls,rows)):
            keys(tool,{'call_id','arguments','result'});require(tool['call_id']==cid and tool['arguments']==args,'exact tool ancestry')
            cap=policy['terminal_output_bytes']*6+4096;require(tool['result']['bytes']<=cap,'finite tool response')
            body=read_pinned(root/(str(n)+'.tool-'+str(j)+'.json'),tool['result'],budget)
            budget.charge(read=2*len(body),write=2*len(body));json_body(body)
            history.append({'type':'function_call_output','call_id':cid,'output':body.decode('utf-8')});terminal_count+=1
    for name,value in [('reserved_input_tokens',len(calls)*ri),('reserved_output_tokens',len(calls)*ro),('observed_input_tokens',observed_i),('observed_output_tokens',observed_o),('terminal_calls',terminal_count)]:
        require(type(receipt[name]) is int and receipt[name]==value,'actual cumulative usage/call join')
    require(terminal_count<=policy['terminal_calls'],'terminal ceiling')
    return receipt

async def investigate(*,environment,configuration,policy,credential_selection,output,binding,budget,receipt_budget):
    """Concrete closed investigation path. terminal.run_terminal is fixed source."""
    from .terminal import run_terminal
    capsule(configuration);limits(policy);exact_budget(budget);exact_budget(receipt_budget)
    require(receipt_budget is not budget and receipt_budget.deadline>=budget.deadline,'independently precharged receipt budget and closure deadline')
    root=directory(output)
    keys(binding,{'execution_plan_sha256','arm','trial_id'});require(binding['arm'] in ('A','B'),'arm binding');slug(binding['trial_id'])
    state={'schema':'tms_figure2b_responses_agent_v1','binding':binding,'calls':[],
        'reserved_input_tokens':0,'reserved_output_tokens':0,'observed_input_tokens':0,'observed_output_tokens':0,
        'terminal_calls':0,'outcome':'unfinished','unknown_provider_outcome':False,'failure_type':None}
    history=initial_history(configuration)
    seen=set();key=None;first=None;secondary=[];transport_failure=None;receipt_durable=False
    last_body=None;prefix_descriptor=None
    try:
        key=credential(credential_selection,budget)
        while True:
            last_body=None
            integer(len(state['calls'])+1,1,policy['model_calls'])
            ri=configuration['model_input_reservation'];ro=configuration['parameters']['max_output_tokens']
            require(state['reserved_input_tokens']+ri<=policy['model_input_tokens'] and state['reserved_output_tokens']+ro<=policy['model_output_tokens'],'no-refund reservation ceilings')
            req=request_document(configuration,policy,history)
            raw=bounded_json(req,configuration['max_request_bytes'])
            budget.charge(read=len(raw),write=len(raw));n=len(state['calls']);request_pin=write_body(root/(str(n)+'.request.json'),raw,budget,configuration['max_request_bytes'])
            record={'number':n,'request':request_pin,'reserved_input_tokens':ri,'reserved_output_tokens':ro,'response':None,'transport':None,'usage':None,'provider_status':None,'tools':[]}
            state['calls'].append(record);state['reserved_input_tokens']+=ri;state['reserved_output_tokens']+=ro
            # Reservation precedes dispatch; failures receive no refund.
            save(root/(str(n)+'.reservation.json'),record,budget)
            try:body,observation=post_once(raw,key,configuration['max_response_bytes'],configuration['http_timeout_seconds'],budget)
            except TransportFailure as error:
                # Keep the actual provider error/prefix before any fallible publication.
                transport_failure=error;last_body=error.raw;record['transport']=error.observation
                state['unknown_provider_outcome']=True
                raise
            last_body=body;record['transport']=observation
            record['response']=write_body(root/(str(n)+'.response.json'),body,budget,configuration['max_response_bytes'])
            budget.charge(read=len(body),write=len(body));value=json_body(body)
            # Record authentic available usage/status before later content refusals.
            record['usage']=usage(value.get('usage'));record['provider_status']=value.get('status')
            state['observed_input_tokens']+=record['usage']['input_tokens'];state['observed_output_tokens']+=record['usage']['output_tokens']
            u,status,items,calls=response(value,configuration['model'],policy,configuration['max_items'],seen)
            require(status=='completed','incomplete/failed/cancelled attempt aborts grading')
            require(u['input_tokens']<=ri and u['output_tokens']<=ro,'observed usage exceeds reservation; retained and refused')
            require(observation['response_eof'] and observation['response_closed'] and observation['connection_closed'],'complete local transport closure')
            history.extend(copy.deepcopy(items)) # preserve every original response item
            if not calls:
                state['outcome']='completed';break
            for cid,a in calls:
                require(state['terminal_calls']<policy['terminal_calls'],'terminal call ceiling')
                state['terminal_calls']+=1
                result=await run_terminal(environment,a['command'],a['timeout_seconds'],a['max_output_bytes'],budget)
                result_body=bounded_json(result,policy['terminal_output_bytes']*6+4096)
                budget.charge(read=len(result_body),write=len(result_body))
                tool_pin=write_body(root/(str(n)+'.tool-'+str(len(record['tools']))+'.json'),result_body,budget,policy['terminal_output_bytes']*6+4096)
                record['tools'].append({'call_id':cid,'arguments':a,'result':tool_pin})
                history.append({'type':'function_call_output','call_id':cid,'output':result_body.decode('utf-8')})
            save(root/(str(n)+'.complete.json'),record,budget)
    except BaseException as error:
        first=error;state['outcome']='failed';state['failure_type']=type(error).__name__
        # Unknown/absent usage is never represented as a successful zero cost.
        if state['calls'] and state['calls'][-1]['provider_status'] not in ('completed','incomplete','failed','cancelled'):state['unknown_provider_outcome']=True
    finally:
        key=None
        if first is not None and last_body is not None:
            try:
                location=root/'FAILED_RESPONSE_PREFIX.raw'
                prefix_descriptor={'path':str(location),**write_body(location,last_body,receipt_budget,configuration['max_response_bytes']+1)}
            except BaseException as publication:secondary.append(('response-prefix',publication))
        # The selected child-receipt reserve was charged before actor activation;
        # it retains the original deadline and is never created/refunded here.
        try:save(root/'AGENT_RESULT.json',state,receipt_budget);receipt_durable=True
        except BaseException as publication:
            secondary.append(('agent-result',publication))
            if first is None:first=publication
            state['outcome']='failed';state['failure_type']=type(first).__name__
    if first is not None:
        raise InvestigationFailure(first,state,secondary,transport_failure,receipt_durable,last_body,prefix_descriptor) from first
    return state
