"""Concrete provider containers owned by the original native phase controller."""
import os
from pathlib import Path
from .common import require,parse,encoded,pin,diagnostic_type

class ProviderCustody:
    """Caller-owned exact provider record, bound before producer effects."""
    __slots__=('original',)
    def __init__(self):self.original=None
    def bind(self,original):
        require(type(original) is dict and self.original is None,'one exact original provider custody')
        self.original=original

class ProviderFailure(Exception):
    def __init__(self,original,cause):
        self.original=original;self.cause=cause
        super().__init__('original native provider unavailable')

class NativeProviders:
    def __init__(self,host,observed,scope,parent,actor_deadline,command,record,retire,argv_for,admit):
        self.host=host;self.observed=observed;self.scope=scope;self.parent=parent;self.actor_deadline=actor_deadline
        self.command=command;self.record=record;self.retire=retire;self.argv_for=argv_for;self.admit=admit;self.originals=[]
    def sample(self,deadline):
        require(deadline<=self.actor_deadline,'same original provider action deadline')
        budget=self.host.budget;budget.check('original provider poll',deadline);cpu=self.scope.sample()
        require(budget.cpu+budget.own_cpu()+cpu<=budget.limits['cpu_seconds'],'whole original actor holder provider CPU')
    def execute(self,lease,provider,invocation,custody=None):
        from .native import one,full_id
        budget=self.host.budget;journal=self.host.journal;record=None;first=None;body=None;initial=None;final=None
        result={'schema':'neural055-original-native-provider-v3','lease':lease.id,'sequence':lease.sequence,
                'provider':provider['id'],'request_sha256':invocation['request_sha256'],'original_phase':self.observed.id,
                'resource':None,'commands':[],'status':'owned_before_dispatch','scope_interval':None,
                'physical_cpu_owner':self.observed.id,'interval_is_not_extra_physical_charge':True,'errors':[]}
        if custody is not None:
            require(type(custody) is ProviderCustody,'exact caller-owned provider custody')
            custody.bind(result)
        self.originals.append(result);before=len(self.observed.commands)
        try:
            self.sample(self.actor_deadline);initial=self.scope.sample()
            base=lease.base/('provider-'+str(lease.sequence));base.mkdir(mode=0o700)
            request=base/'REQUEST.json';config=base/'CONFIG.json'
            journal.write(str(request.relative_to(journal.root)),encoded(invocation));os.chmod(request,0o444)
            journal.write(str(config.relative_to(journal.root)),encoded(provider['config']));os.chmod(config,0o444)
            source=lease.registry.source.actor_current()
            binds={'/request.json':(request,False),'/config.json':(config,False),'/runtime':(source,False)}
            if provider['kind']=='local_transformers_text_v1':
                binds['/model']=(provider['model'],False);entry='/runtime/model_provider_entry.py'
            else:
                require(lease.bank is not None,'only same original R2 bank')
                binds['/bank']=(Path(lease.bank['directory']),False);binds['/input']=(lease.view,False);entry='/runtime/tool_provider_entry.py'
            for path,_ in binds.values():
                require(path.is_absolute() and not any(x.is_symlink() for x in (path,*path.parents)) and not any(c in str(path) for c in ',\n\r\0'),'literal qualified provider mounts')
            record=self.record('container',self.observed.id+'-provider-'+str(lease.sequence));result['resource']=record
            args=['-I','-B',entry,'--request','/request.json','--config','/config.json']
            record.update(attempted=True,closed=False,disposition='creation_pending');result['status']='original_create_attempted'
            record['id']=full_id(self.command(self.argv_for(record,binds,None,args),4096,self.actor_deadline).decode().strip());record['acknowledged']=True
            value=one(parse(self.command(['container','inspect',record['id']],end=self.actor_deadline)))
            self.admit(value,record,self.host.profile,self.parent,binds,None,None,args)
            # Attached stdout is the original provider transport. ProcessRunner
            # retains prefixes and waits its original client; container wait and
            # ID-preserving removal remain independently required below.
            body=self.command(['container','start','--attach',record['id']],8388608+131072,self.actor_deadline,poll_service=self.sample)
            value=one(parse(self.command(['container','inspect',record['id']],end=self.actor_deadline)))
            require(value['Id']==record['id'] and value['Config']['Labels'].get('org.neurobench.n055')==record['owner'],'same actual provider instance')
            state=value['State'];record['natural_state']=dict(state)
            require(state['Status']=='exited' and state['Pid']==0 and not state['Running'] and not state['Dead'] and not state['OOMKilled'] and not state['Error'] and state['ExitCode']==0,'original provider natural zero')
            require(len(body)<=8388608,'bounded actual provider stdout');result['stdout']=pin(body)
            final=self.scope.sample();result['scope_interval']={'before_cpu_seconds':initial,'after_cpu_seconds':final,'includes_concurrent_original_actor_and_holder':True}
            self.sample(self.actor_deadline)
        except BaseException as exc:
            first=exc;journal.carrier.fail(exc,'native-provider');result['errors'].append({'type':diagnostic_type(exc)})
        finally:
            if record is not None:
                try:
                    if not self.retire(record):
                        error=ValueError('original provider retirement unresolved');journal.carrier.fail(error,'provider-retirement');result['errors'].append({'type':diagnostic_type(error)})
                        if first is None:first=error
                except BaseException as exc:
                    journal.carrier.fail(exc,'provider-retirement-or-publication');result['errors'].append({'type':diagnostic_type(exc)})
                    if first is None:first=exc
            result['commands']=[x.document() for x in self.observed.commands[before:]]
            result['status']='complete_original' if first is None else 'failed_original'
            try:journal.json(self.observed.id+'-PROVIDER-'+str(lease.sequence)+'.json',result)
            except BaseException as exc:
                journal.carrier.fail(exc,'provider-publication');result['errors'].append({'type':diagnostic_type(exc)})
                if first is None:first=exc
        if first is not None:raise ProviderFailure(result,first) from first
        try:value=parse(body)
        except BaseException as exc:raise ProviderFailure(result,exc) from exc
        return value,result
