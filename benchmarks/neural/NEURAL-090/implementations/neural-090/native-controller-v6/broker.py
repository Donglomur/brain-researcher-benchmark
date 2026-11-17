"""Fixed per-invocation model/tool service with no cross-arm history."""
import base64,sys,time,os
from .common import need,fields,integer,encoded,parse,pin,save,Ledger,admit_placement
from .token_budget import text_input
from .cgroup import Cgroup
class Broker:
    def __init__(self,isolation):self.isolation=isolation;self.calls=[];self.tools=0;self.tokens=0
    def dispatch(self,action):
        iso=self.isolation;cfg=iso.owner.cfg['provider'];kind=action.get('kind')
        if kind=='tool':
            fields(action,('kind','command'));need(type(action['command'])is str and 0<len(action['command'].encode())<=32768 and '\0'not in action['command'],'bounded tool command')
            need(self.tools<iso.limits['tool_calls'],'preselected tool call ceiling');self.tools+=1
            # The command runs only in a new container belonging to this invocation.
            rec=iso.container_step(['/bin/sh','-c',action['command']],tool=True)
            result={'kind':'tool_result','stdout_base64':rec['stdout_base64'],'stderr_base64':rec['stderr_base64'],'exit_code':rec['exit_code']}
            self.calls.append({'kind':'tool','action':action,'result':result});return result
        fields(action,('kind','input'));need(kind=='model'and type(action['input'])is list,'closed model request')
        admission=text_input(action['input'],cfg['input_contract'],iso.actor,cfg['input_tokens'],cfg['model'])
        need(sum(x['kind']=='model'for x in self.calls)<cfg['max_calls'],'preselected model call ceiling')
        reservation=cfg['input_tokens']+cfg['output_tokens'];need(self.tokens+reservation<=iso.limits['model_tokens'],'preselected combined input/output token reservation')
        self.tokens+=reservation # Failure or unknown outcome never refunds.
        row={'kind':'model','reservation':reservation,'input':action['input'],'result':None,'input_admission':admission};self.calls.append(row)
        request={**cfg,'input':action['input'],'deadline':iso.normal_end};request.pop('max_calls',None);request.pop('input_contract',None)
        location=iso.root/('provider-'+str(len(self.calls))+'.json');save(location,encoded(request),iso.budget,0o600)
        # Credential is available only to trusted host child; container has no network/socket/key.
        iso.actor.read(cfg['request_bytes']+cfg['response_bytes']+1);iso.actor.write(2*(cfg['response_bytes']+1))
        group=Cgroup(iso.cgroup.path,'provider-'+str(len(self.calls)),iso.budget,iso.limits);errors=Ledger();rec=None
        iso.budget.read(8193);iso.budget.write(16384+32) # placement readback/record/PID writes, before dispatch
        save(iso.root/('PROVIDER-'+str(len(self.calls))+'.json'),encoded({'token':iso.token,'name':group.path.name,'call':len(self.calls)}),iso.budget)
        try:
            group.create(branch=False)
            placement=iso.root/('PLACEMENT-'+str(len(self.calls))+'.json')
            argv=[sys.executable,'-I','-S','-B',str(iso.owner.root/'trusted-place.py'),str(group.path),str(group.identity[0]),str(group.identity[1]),str(placement),repr(iso.normal_end),'--',sys.executable,'-I','-S','-B',str(iso.owner.root/'trusted-provider.py'),str(location)]
            rec=iso.owner.command(argv,iso.normal_end,iso.cleanup_end,iso.budget,monitor=iso.cgroup.monitor)
            row['placement']=admit_placement(placement,group.path,group.identity,rec,iso.budget)
        except BaseException as error:errors.record('provider-call',error)
        finally:
            group.budget=iso.cleanup_budget
            if group.identity is not None:
                errors.attempt('provider-cgroup-kill',group.kill);errors.attempt('provider-cgroup-retire',group.finish)
        errors.raise_first({'request':row,'process':None if rec is None else rec})
        body=base64.b64decode(rec['stdout_base64'],validate=True);reply=parse(body);row['raw_transport']=reply
        fields(reply,('transport','raw_base64','first_error','secondary'))
        need(reply['first_error']is None and reply['secondary']==[],'complete provider process/transport')
        t=reply['transport'];need(t['attempted']is True and t['status']==200 and all(t[k]is True for k in('eof','response_closed','connection_closed'))and t['retries']==0,'actual terminal HTTP observations')
        raw=base64.b64decode(reply['raw_base64'],validate=True);value=parse(raw);row['response_pin']=pin(raw)
        need(value.get('model')==cfg['model']and value.get('status')=='completed'and value.get('object')=='response','exact completed model response')
        u=value.get('usage');need(type(u)is dict,'actual provider usage required')
        for k in('input_tokens','output_tokens','total_tokens'):integer(u.get(k))
        need(u['total_tokens']==u['input_tokens']+u['output_tokens']and u['input_tokens']<=cfg['input_tokens']and u['output_tokens']<=cfg['output_tokens'],'usage within preselected reservation')
        need(type(value.get('output'))is list and all(x.get('type')in('message','reasoning')for x in value['output']),'no hosted or unmetered tools')
        row['result']={'kind':'model_result','output':value['output'],'usage':u};return row['result']
    def receipt(self):return {'reserved_model_tokens':self.tokens,'tool_calls':self.tools,'calls':self.calls,'history_scope':'one invocation; every caller-supplied input and actual reply retained; no automatic previous response ID'}
