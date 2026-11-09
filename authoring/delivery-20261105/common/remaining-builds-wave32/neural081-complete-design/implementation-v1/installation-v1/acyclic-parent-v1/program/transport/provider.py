"""Bounded text-only provider transport with offline selected exact token framing.
No default qualified model/tokenizer, cache fetch, retry or operation on import.
"""
import base64,hashlib,http.client,ipaddress,json,os,re,socket,ssl,threading,time
from pathlib import Path
from .common import AdapterError,canonical,integer,need,positive,write_fresh,sync_directory,authenticate
ENDPOINT='https://api.openai.com/v1/chat/completions'

def parse_json(raw):
    def pairs(rows):
        result={}
        for key,value in rows:need(key not in result,'duplicate provider JSON key');result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite provider JSON'))

class TokenCounter:
    def __init__(self,contract,budget):
        keys={'schema','model','package_version','encoding_name','pattern','vocabulary','special_tokens','request_prefix_tokens','per_message_tokens','assistant_prefix_tokens','qualification'}
        need(type(contract)is dict and set(contract)==keys and contract['schema']=='neural081_plain_chat_tokenizer_contract_v1','exact selected tokenizer/framing contract')
        need(type(contract['model'])is str and type(contract['pattern'])is str and contract['pattern'],'source-selected tokenizer pattern/model')
        for k in ('request_prefix_tokens','per_message_tokens','assistant_prefix_tokens'):integer(contract[k],k)
        need(type(contract['qualification'])is dict and set(contract['qualification'])=={'path','bytes','sha256'},'independent framing qualification descriptor, admitted upstream')
        d=contract['vocabulary'];authenticate(d,budget);budget.charge('source_read',d['bytes']+1)
        with open(d['path'],'rb')as stream:raw=stream.read(d['bytes']+1)
        need(len(raw)==d['bytes']and hashlib.sha256(raw).hexdigest()==d['sha256'],'full pinned local vocabulary, no remote/cache fallback')
        ranks={};used=set()
        for line in raw.splitlines():
            fields=line.split();need(len(fields)==2,'exact tokenizer vocabulary line');token=base64.b64decode(fields[0],validate=True);rank=int(fields[1])
            need(token not in ranks and rank not in used and rank>=0,'unique vocabulary token/rank');ranks[token]=rank;used.add(rank)
        need(type(contract['special_tokens'])is dict and all(type(k)is str and type(v)is int and v>=0 for k,v in contract['special_tokens'].items()),'selected special-token table')
        import tiktoken
        need(tiktoken.__version__==contract['package_version'],'selected tokenizer package version; full installed source qualified independently')
        self.encoder=tiktoken.Encoding(name=contract['encoding_name'],pat_str=contract['pattern'],mergeable_ranks=ranks,special_tokens=contract['special_tokens']);self.contract=contract
    def count(self,messages):
        need(type(messages)is list and messages,'complete ordered conversation');n=self.contract['request_prefix_tokens']+self.contract['assistant_prefix_tokens']
        for m in messages:
            need(type(m)is dict and set(m)=={'role','content'}and m['role']in ('system','user','assistant')and type(m['content'])is str,'plain role/content only, no unmeasured function/image/name framing')
            n+=self.contract['per_message_tokens']+len(self.encoder.encode(m['role'],disallowed_special=()))+len(self.encoder.encode(m['content'],disallowed_special=()))
        return n

def parse_completion(body,expected_prompt):
    need(type(body)is dict and type(body.get('id'))is str,'provider response identity');usage=body.get('usage');need(type(usage)is dict,'actual complete provider usage')
    for k in ('prompt_tokens','completion_tokens','total_tokens'):integer(usage.get(k),'actual '+k)
    need(usage['prompt_tokens']==expected_prompt and usage['total_tokens']==usage['prompt_tokens']+usage['completion_tokens'],'actual usage matches exact selected token framing')
    choices=body.get('choices');need(type(choices)is list and len(choices)==1,'one complete response');choice=choices[0]
    need(type(choice.get('index'))is int and choice['index']==0 and choice.get('finish_reason')=='stop','natural complete response only')
    m=choice.get('message');need(type(m)is dict and m.get('role')=='assistant'and type(m.get('content'))is str and not m.get('refusal')and not m.get('tool_calls'),'plain completed JSON-action text')
    return {'role':'assistant','content':m['content']},'stop',usage

class BoundHTTPS(http.client.HTTPSConnection):
    """Qualified literal IP, certificate/SNI original hostname, no runtime DNS."""
    def __init__(self,address,deadline):
        self.address=str(ipaddress.ip_address(address));self.deadline=deadline
        super().__init__('api.openai.com',timeout=max(.001,deadline-time.monotonic()))
    def connect(self):
        need(self._tunnel_host is None,'no proxy/tunnel or redirect capability')
        remaining=self.deadline-time.monotonic();need(remaining>0,'original endpoint before connect')
        family=socket.AF_INET6 if ':'in self.address else socket.AF_INET
        self.sock=socket.socket(family,socket.SOCK_STREAM);self.sock.settimeout(remaining)
        self.sock.connect((self.address,443))
        remaining=self.deadline-time.monotonic();need(remaining>0,'original endpoint before verified TLS')
        self.sock.settimeout(remaining);self.sock=self._context.wrap_socket(self.sock,server_hostname='api.openai.com')

class RequestWatchdog:
    def __init__(self,connection,endpoint):
        self.connection=connection;self.endpoint=endpoint;self.done=threading.Event();self.triggered=False;self.error=None
        self.thread=threading.Thread(target=self._watch,name='neural081-provider-owned-socket-deadline',daemon=False)
    def _watch(self):
        if self.done.wait(max(0,self.endpoint-time.monotonic())):return
        self.triggered=True
        try:
            sock=self.connection.sock
            if sock is not None:sock.shutdown(socket.SHUT_RDWR)
        except OSError as error:self.error=type(error).__name__
    def start(self):self.thread.start()
    def close(self):
        self.done.set();self.thread.join(max(0,self.endpoint+120-time.monotonic()))
        return {'triggered':self.triggered,'thread_joined':not self.thread.is_alive(),'owned_socket_only':True,'shutdown_error':self.error,'remote_request_cancelled':False}

class ChatCompletionTransport:
    def __init__(self,config,budget,evidence_root=None):
        expected={'resolved_ip','endpoint','model','api_key_env','max_completion_tokens','prompt_token_reservation','request_cap_bytes','response_cap_bytes','request_timeout_seconds','seed','tokenizer_contract','transcript_cap_bytes'}
        need(type(config)is dict and set(config)==expected and config['endpoint']==ENDPOINT,'exact provider configuration')
        need(type(config['resolved_ip'])is str and str(ipaddress.ip_address(config['resolved_ip']))==config['resolved_ip'],'independently selected canonical literal endpoint address; no DNS lookup')
        need(type(config['model'])is str and config['model']and re.fullmatch('[A-Z][A-Z0-9_]{1,127}',config['api_key_env'])is not None,'selected endpoint/model/credential name')
        for k in ('max_completion_tokens','prompt_token_reservation','request_cap_bytes','response_cap_bytes','transcript_cap_bytes'):integer(config[k],k,1)
        need(config['max_completion_tokens']<=4096 and config['prompt_token_reservation']==32768 and config['response_cap_bytes']<=2097152 and config['transcript_cap_bytes']<=16777216,'original token/HTTP/transcript caps')
        positive(config['request_timeout_seconds'],'request timeout');need(config['request_timeout_seconds']<=120,'original per-request interval')
        need(config['seed']is None or type(config['seed'])is int and 0<=config['seed']<2**31,'selected seed or unknown determinism')
        need(config['tokenizer_contract']['model']==config['model'],'exact tokenizer/model join');self.config=dict(config);self.budget=budget;self.records=[];self.reserved_trace=0
        self.counter=TokenCounter(config['tokenizer_contract'],budget);need(evidence_root is not None,'protected original transcript destination')
        self.root=Path(evidence_root);self.root.mkdir(mode=0o700);sync_directory(self.root);sync_directory(self.root.parent)
    def complete(self,messages,*,allow_tools):
        need(type(allow_tools)is bool,'explicit episode action policy');self.budget.check_clock();tokens=self.counter.count(messages)
        need(tokens<=32768,'context_budget_exceeded; no request/history truncation')
        payload={'model':self.config['model'],'messages':messages,'n':1,'store':False,'stream':False,'max_completion_tokens':self.config['max_completion_tokens']}
        if self.config['seed']is not None:payload['seed']=self.config['seed']
        request=canonical(payload);need(len(request)<=self.config['request_cap_bytes'],'full provider request byte cap')
        reservation=len(request)+self.config['response_cap_bytes']+1
        need(self.reserved_trace+reservation<=self.config['transcript_cap_bytes'],'prospective full transcript bound');self.reserved_trace+=reservation
        self.budget.charge('provider_calls');self.budget.charge('provider_tokens',32768+self.config['max_completion_tokens']);self.budget.charge('source_read',self.config['response_cap_bytes']+1);self.budget.charge('artifact_write',self.config['response_cap_bytes']+1)
        ordinal=len(self.records)+1;rp=write_fresh(self.root/('request-%04d.json'%ordinal),request,self.budget)
        record={'ordinal':ordinal,'status':'attempted','request_artifact':rp,'model':self.config['model'],'exact_input_tokens':tokens,'maximum_reserved_input_tokens':32768,'output_token_limit':self.config['max_completion_tokens'],'requested_seed':self.config['seed'],'determinism':'not established by seed','original_deadline':self.budget.deadline_monotonic,'remote_retirement_on_failure':'unknown; local close is not cancellation'};self.records.append(record)
        key=os.environ.get(self.config['api_key_env']);need(type(key)is str and key,'selected credential unavailable')
        start=time.monotonic();end=min(self.budget.deadline_monotonic,start+self.config['request_timeout_seconds']);record.update(started_monotonic=start,normal_deadline=end)
        connection=BoundHTTPS(self.config['resolved_ip'],end);response=None;raw=bytearray();answer=None;watchdog=RequestWatchdog(connection,end)
        record['resolved_ip']=self.config['resolved_ip'];record['tls_hostname']='api.openai.com';watchdog.start()
        try:
            connection.request('POST','/v1/chat/completions',body=request,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
            response=connection.getresponse();record['http_status']=response.status;record['provider_request_id']=response.getheader('x-request-id')
            need(response.getheader('content-encoding')in(None,'identity'),'uncompressed complete body only')
            while True:
                self.budget.check_clock();remaining=end-time.monotonic();need(remaining>0,'original provider request endpoint')
                if connection.sock is not None:connection.sock.settimeout(remaining)
                chunk=response.read(min(65536,self.config['response_cap_bytes']+1-len(raw)))
                if not chunk:break
                raw.extend(chunk);need(len(raw)<=self.config['response_cap_bytes'],'response byte cap')
            need(response.status==200,'HTTP failure retained, no retry');body=parse_json(raw);need(body.get('model')==self.config['model'],'actual provider model identity')
            message,finish,usage=parse_completion(body,tokens);need(usage['completion_tokens']<=self.config['max_completion_tokens'],'actual output token cap')
            record.update(status='completed',usage=usage,response_id=body['id'],system_fingerprint=body.get('system_fingerprint'));answer=(message,finish)
        except BaseException as error:
            record.update(status='failed',failure_type=type(error).__name__);raise AdapterError('provider failure; reservation retained without retry',dict(record))from error
        finally:
            persistence_error=None
            try:
                if response is not None:response.close()
                connection.close();record['response_stream_closed']=True
                path=self.root/('response-%04d.json'%ordinal)
                with path.open('xb')as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
                sync_directory(self.root);record['response_artifact']={'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
            except BaseException as error:
                record.update(status='failed',persistence_uncertain=True,persistence_error_type=type(error).__name__);persistence_error=error
            finally:
                record['watchdog']=watchdog.close();record['ended_monotonic']=time.monotonic();del key
            if persistence_error is not None:raise persistence_error
            if record['status']=='completed':
                if record['ended_monotonic']>end or record['watchdog']['triggered']or not record['watchdog']['thread_joined']:
                    record.update(status='failed',failure_type='OriginalProviderClosureDeadline');raise AdapterError('provider original deadline/owned-watchdog closure failed',dict(record))
                self.budget.check_clock()
        return answer
