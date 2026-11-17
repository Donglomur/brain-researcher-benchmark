"""Trusted original request admission, finite providers and shared token custody.

The only dispatch callable is the source-owned NativeProviders attached to an
original native phase. Candidate code supplies data, never a process command.
"""
import base64
import os
import re
import uuid
from pathlib import Path
from .native_providers import ProviderCustody
from .common import require,keys,parse,encoded,sha,capture,pin,FailureCarrier,stamp,diagnostic_type
from .registry import token
from .seals import file_identity

REQUEST_FIELDS=('schema','lease','cell','phase','sequence','parent_response_sha256','source_sha256','provider','operation','payload')
TOOL_OPERATIONS={'FIT':('development_report','training_predictions'),
                 'INFER':('development_report','candidate_predictions','query_scores')}

class TokenLedger:
    def __init__(self,limits,budget):
        keys(limits,('global_input','global_output','cell_input','cell_output','cell_calls'))
        require(all(type(x)is int and x>0 for x in limits.values()),'finite positive original token caps')
        require(budget.token_ledger is None,'one original campaign token ledger')
        self.limits=limits;self.budget=budget;self.records=[];self.cells={};self.used={'input':0,'output':0};budget.token_ledger=self
    def reserve(self,cell,maximum_input,maximum_output):
        key=token(cell);row=self.cells.setdefault(key,{'input':0,'output':0,'calls':0})
        require(row['calls']<self.limits['cell_calls'],'same FIT+INFER call cap')
        for k,n in (('input',maximum_input),('output',maximum_output)):
            require(type(n)is int and n>0,'fixed maximum token reservation')
            require(self.used[k]+n<=self.limits['global_'+k] and row[k]+n<=self.limits['cell_'+k],'original global and full-cell token cap')
        require(self.budget.model_calls+1<=self.budget.limits['model_calls'],'original model-call allowance before effect')
        rec={'cell':cell,'maximum_input':maximum_input,'maximum_output':maximum_output,'status':'reserved_before_dispatch','usage':None}
        self.records.append(rec);row['calls']+=1;self.budget.model_calls+=1
        for k,n in (('input',maximum_input),('output',maximum_output)):row[k]+=n;self.used[k]+=n
        return rec
    def reserve_external(self,maximum_input,maximum_output):
        for k,n in (('input',maximum_input),('output',maximum_output)):
            require(type(n)is int and n>0 and self.used[k]+n<=self.limits['global_'+k],'postscore uses original remaining global tokens')
        record={'scope':'current_postscore_operation','maximum_input':maximum_input,'maximum_output':maximum_output,'status':'reserved_before_dispatch','usage':None}
        self.records.append(record)
        for k,n in (('input',maximum_input),('output',maximum_output)):self.used[k]+=n
        return record
    def settle_external(self,record,usage):
        require(record['scope']=='current_postscore_operation'and record['status']=='reserved_before_dispatch','one original external token settlement')
        keys(usage,('input_tokens','output_tokens'))
        values={k:usage[k+'_tokens']for k in('input','output')}
        require(all(type(n)is int and 0<=n<=record['maximum_'+k]for k,n in values.items()),'known original external token usage within reservation')
        for k,n in values.items():self.used[k]-=record['maximum_'+k]-n
        record.update(status='actual_qualified_adapter_usage',usage=values)
    def settle(self,record,usage):
        require(record['status']=='reserved_before_dispatch','one original token settlement')
        values={k:usage[k+'_tokens'] for k in ('input','output')}
        require(all(type(n)is int and 0<=n<=record['maximum_'+k] for k,n in values.items()),'actual qualified adapter usage inside reservation')
        row=self.cells[token(record['cell'])]
        for k,n in values.items():
            delta=record['maximum_'+k]-n;self.used[k]-=delta;row[k]-=delta
        record.update(status='actual_qualified_adapter_usage',usage=values)
    def uncertain(self,record,cause):
        if record is not None and record['status']=='reserved_before_dispatch':
            record.update(status='unknown_original_usage_reservation_retained',error_type=diagnostic_type(cause))
            self.budget.unknown.append({'operation':'broker-model-'+str(self.records.index(record)),'quantity':'actual_model_tokens','reservation_retained':True})

class BrokerRegistry:
    def __init__(self,profile,operator_root,source,authority,journal,budget):
        self.profile=profile;self.root=Path(operator_root);self.source=source;self.journal=journal;self.budget=budget
        self.providers={};self.originals=[];self.ledger=TokenLedger(profile['model_token_limits'],budget)
        specs=profile['model_providers'];require(type(specs)is list and bool(specs),'complete fixed provider registry')
        for spec in specs:
            keys(spec,('id','kind','config','qualification','model_directory','model_manifest'))
            ident=spec['id'];require(type(ident)is str and re.fullmatch('[a-z][a-z0-9_]{0,47}',ident) and ident not in self.providers,'unique literal provider ID')
            require(spec['kind'] in ('local_transformers_text_v1','fixed_r2_scientific_v1'),'source-owned actual provider adapter')
            config=parse(capture(self.root,spec['config'],budget,1048576))
            common=('schema','kind','source_identity','request_bytes')
            extra=('seed','system_prompt','maximum_input_tokens','maximum_output_tokens') if spec['kind']=='local_transformers_text_v1' else ()
            keys(config,common+extra)
            require(config['schema']=='neural055-provider-configuration-v3' and config['kind']==spec['kind'],'exact provider config role')
            require(config['source_identity']==source.identity and config['request_bytes']==1048576,'qualified source/config bound')
            model=None;manifest=None;stamps={}
            if spec['kind']=='local_transformers_text_v1':
                require(type(config['seed'])is int and type(config['system_prompt'])is str,'fixed model initialization')
                require(all(type(config[k])is int and config[k]>0 for k in ('maximum_input_tokens','maximum_output_tokens')),'fixed adapter token bounds')
                model=Path(spec['model_directory']);require(model.is_absolute() and not any(x.is_symlink() for x in (model,*model.parents)),'literal preexisting local model root')
                manifest=parse(capture(self.root,spec['model_manifest'],budget,16777216));keys(manifest,('schema','files'))
                require(manifest['schema']=='neural055-qualified-local-model-files-v3' and type(manifest['files'])is list and bool(manifest['files']),'finite complete local checkpoint/tokenizer identity')
                expected=set()
                for d in manifest['files']:
                    keys(d,('path','bytes','sha256'));name=d['path']
                    require(type(name)is str and name and not Path(name).is_absolute() and '..' not in Path(name).parts and name not in expected,'finite model relative member')
                    expected.add(name);path=model/name
                    require(not any(x.is_symlink() for x in (path,*path.parents)),'no model link route')
                    require(file_identity(path,budget,d['bytes'])=={'bytes':d['bytes'],'sha256':d['sha256']},'actual entire qualified checkpoint/tokenizer member')
                    stamps[name]=stamp(path.lstat())
                actual=set()
                for directory,dirs,files in os.walk(model,followlinks=False):
                    require(not any((Path(directory)/n).is_symlink() for n in dirs),'no model directory links')
                    actual.update(str((Path(directory)/n).relative_to(model)) for n in files)
                    require(len(actual)<=len(expected),'no undeclared local model members')
                require(actual==expected,'complete fixed model namespace')
            else:require(spec['model_directory'] is None and spec['model_manifest'] is None,'fixed R2 only original bank')
            subject={'source':source.identity,'provider':spec['id'],'kind':spec['kind'],'config':spec['config'],'model_manifest':spec['model_manifest'],'native_profile':profile['deployment_identity'],'resource_policy':budget.resource_policy,'same_original_cgroup':True}
            qualification=authority.verify(spec['qualification'],'trusted_provider_source_and_runtime',subject)
            self.providers[ident]={'id':ident,'kind':spec['kind'],'config':config,'model':model,'manifest':manifest,'stamps':stamps,'qualification':qualification}
        self.subject={'schema':'neural055-original-broker-registry-v4','resource_policy':budget.resource_policy,'source':source.identity,'specifications':specs,'token_limits':profile['model_token_limits']}
        self.journal.json('BROKER_REGISTRY.json',self.subject)
    def unchanged(self,provider):
        if provider['model'] is not None:
            for d in provider['manifest']['files']:
                p=provider['model']/d['path'];require(stamp(p.lstat())==provider['stamps'][d['path']],'same actual preexisting model member')
                require(file_identity(p,self.budget,d['bytes'])=={'bytes':d['bytes'],'sha256':d['sha256']},'full actual model recheck before dispatch')
        self.source.current();self.budget.check('after fixed provider revalidation')
    def lease(self,cell,phase,context,view,bank,seal,deadline):
        lease=BrokerLease(self,cell,phase,context,view,bank,seal,deadline);self.originals.append(lease);return lease

class BrokerLease:
    def __init__(self,registry,cell,phase,context,view,bank,seal,deadline):
        self.registry=registry;self.cell=dict(cell);self.phase=phase;self.context=context;self.view=Path(view);self.bank=bank;self.seal=seal
        self.deadline=deadline;self.id='broker-'+uuid.uuid4().hex;self.sequence=0;self.parent=None;self.records=[];self.errors=FailureCarrier();self.closed=False;self.native=None
        self.base=registry.journal.root/self.id;self.base.mkdir(mode=0o700);self.replies=self.base/'replies';self.replies.mkdir(mode=0o555)
        services=context['policy']['services'];require(type(services)is list and len(set(services))==len(services) and set(services)<=set(registry.providers),'precommitted allowed provider IDs')
        self.allowed=set(services)
        self.actions=None
        if phase=='INFER':
            policy=seal.method['inference_action_policy'];require(policy.get('query_fit') is False,'same sealed no-query-fit method')
            actions=policy.get('broker_actions');require(type(actions)is list,'sealed explicit broker action set')
            self.actions=set()
            for a in actions:
                keys(a,('provider','operation'));require(a['provider'] in self.allowed,'sealed provider precommitted');self.actions.add((a['provider'],a['operation']))
        self.visible={'resource_policy':registry.budget.resource_policy,'schema':'neural055-visible-broker-lease-v3','lease':self.id,'cell':self.cell,'phase':phase,'source_sha256':context['source'],
                      'providers':sorted(self.allowed),'deadline':deadline-registry.profile['closure_reserve_seconds'],'requests':'/broker/requests','replies':'/broker/replies','request_bytes':1048576,'response_bytes':8388608}
        self.visible_path=self.base/'LEASE.json';registry.journal.write(str(self.visible_path.relative_to(registry.journal.root)),encoded(self.visible));os.chmod(self.visible_path,0o444)
        registry.journal.json(self.id+'-INTENT.json',{'visible':self.visible,'registry':registry.subject,'sealed_method':None if seal is None else seal.document['selected_method']})
    def admit(self,raw):
        require(not self.closed and len(raw)<=1048576,'live bounded original request')
        request=parse(raw);keys(request,REQUEST_FIELDS)
        require(request['schema']=='neural055-broker-request-v3' and request['lease']==self.id and request['cell']==self.cell and request['phase']==self.phase,'exact original lease/cell/phase')
        require(type(request['sequence'])is int and request['sequence']==self.sequence and request['parent_response_sha256']==self.parent,'no replay or crossed response ancestry')
        require(request['source_sha256']==self.context['source'],'actual original submitted-source commitment')
        ident=request['provider'];require(ident in self.allowed,'precommitted finite provider')
        provider=self.registry.providers[ident];op=request['operation'];payload=request['payload'];require(type(payload)is dict,'request data object')
        if self.actions is not None:require((ident,op) in self.actions,'same sealed INFER action set')
        if provider['kind']=='local_transformers_text_v1':
            require(self.cell['mode']=='I' and op=='generate','F and references cannot make investigator decisions')
            keys(payload,('messages','max_new_tokens'));require(type(payload['max_new_tokens'])is int and 0<payload['max_new_tokens']<=provider['config']['maximum_output_tokens'],'prospectively bounded generation')
            require(type(payload['messages'])is list and 0<len(payload['messages'])<=128,'bounded permitted conversation')
            for message in payload['messages']:
                keys(message,('role','content'));require(message['role'] in ('user','assistant') and type(message['content'])is str,'no caller-owned system prompt')
        else:
            require(self.cell['tool_setting']=='T1' and self.bank is not None and op in TOOL_OPERATIONS[self.phase],'T1 current-view scientific tool permission')
            keys(payload,('rows',) if op=='training_predictions' else ())
            if op=='training_predictions':
                rows=payload['rows'];require(type(rows)is list and 0<len(rows)<=200 and all(type(x)is int and 0<=x<16540 for x in rows) and len(rows)==len(set(rows)),'fixed bounded training rows')
        return request,provider
    def dispatch(self,raw,native):
        budget=self.registry.budget;journal=self.registry.journal;budget.check('before original broker admission',self.deadline)
        record={'sequence':self.sequence,'request_pin':pin(raw),'request':None,'provider':None,'status':'captured_before_admission','original':None,'reply':None,'errors':[]}
        self.records.append(record);self.native=native;reservation=None;first=None;value=None
        # Actual immutable request bytes exist before admission or any provider effect.
        journal.write(str((self.base/(str(len(self.records)-1)+'-REQUEST.json')).relative_to(journal.root)),raw)
        custody=ProviderCustody()
        try:
            request,provider=self.admit(raw);record['request']=request;record['provider']=provider['id']
            budget.admit('no uncertain earlier original broker costs',self.deadline)
            self.registry.unchanged(provider)
            if provider['kind']=='local_transformers_text_v1':reservation=self.registry.ledger.reserve(self.cell,provider['config']['maximum_input_tokens'],request['payload']['max_new_tokens'])
            record['status']='admitted_before_effect'
            invocation={'schema':'neural055-provider-request-v3','role':'investigator_decision' if reservation is not None else 'fixed_scientific_predictor',
                        'phase':self.phase,'cell':self.cell,'operation':request['operation'],'payload':request['payload'],'request_sha256':sha(raw),'deadline':native.actor_deadline}
            value,original=native.execute(self,provider,invocation,custody=custody)
            require(original is custody.original,'same producer-owned original provider record')
            record['original']=original
            keys(value,('schema','role','result','usage','request_sha256','source_identity'))
            require(value['schema']=='neural055-provider-result-v3' and value['request_sha256']==sha(raw) and value['source_identity']==self.registry.source.identity,'actual captured fixed provider result identity')
            require(value['role']==invocation['role'] and type(value['result'])is dict,'actual provider role/result')
            usage=value['usage'];require(usage['cpu_placement']=='same_original_native_cgroup','original physical accounting domain')
            if reservation is not None:
                keys(value['result'],('text',));require(type(value['result']['text'])is str,'actual investigator text')
                self.registry.ledger.settle(reservation,usage)
            else:require(usage['input_tokens']==usage['output_tokens']==0,'fixed scientific tool has no model tokens')
            record['status']='actual_captured_success'
            budget.check('after actual original provider',self.deadline)
        except BaseException as exc:
            first=exc;record['errors'].append(exc);record['status']='failed_original_request';self.errors.fail(exc,'request');journal.carrier.fail(exc,'broker-request:'+self.id)
            self.registry.ledger.uncertain(reservation,exc)
            original=custody.original
            if original is not None:record['original']=original
        reply={'schema':'neural055-broker-response-v3','lease':self.id,'cell':self.cell,'phase':self.phase,'sequence':self.sequence,
               'request_sha256':sha(raw),'status':'ok' if first is None else 'unavailable','result':None if first is not None else value['result'],
               'error':None if first is None else {'type':diagnostic_type(first)},'usage':None if value is None else value.get('usage'),
               'original_process':record['original']}
        body=encoded(reply);require(len(body)<=8388608,'complete bounded trusted reply')
        record['reply']=journal.write(str((self.base/(str(self.sequence)+'-RESPONSE.json')).relative_to(journal.root)),body)
        # A separate mount is readonly to the actor, and publication is atomic.
        os.chmod(self.replies,0o755)
        try:
            temp=self.replies/(str(self.sequence)+'.partial');journal.write(str(temp.relative_to(journal.root)),body);os.chmod(temp,0o444)
            temp.rename(self.replies/(f'{self.sequence:08d}.json'))
        finally:os.chmod(self.replies,0o555)
        self.parent=sha(body);self.sequence+=1
        if first is not None:raise first
        return reply
    def close(self,pending):
        require(not self.closed,'one original broker retirement');self.closed=True
        self.pending=pending
        require(pending.get('no_unprocessed_request') is True,'original pending/partial request blocks clean completion')
        require(self.errors.first is None,'original failed request retained')
        self.registry.journal.json(self.id+'-CLOSED.json',self.document())
    def document(self):
        return {'id':self.id,'cell':self.cell,'phase':self.phase,'closed':self.closed,'records':[{**r,'errors':[{'type':diagnostic_type(e)} for e in r['errors']]} for r in self.records],
                'pending':getattr(self,'pending',None),'errors':self.errors.document(),'candidate_self_reports_are_not_authority':True}
    def summary(self):
        return {'id':self.id,'cell':self.cell,'phase':self.phase,'closed':self.closed,'original_request_count':len(self.records),
                'sequence':self.sequence,'last_response_sha256':self.parent,'errors':self.errors.document(),
                'pending':getattr(self,'pending',None),'full_original_records_retained_in_host_and_journal':True}
