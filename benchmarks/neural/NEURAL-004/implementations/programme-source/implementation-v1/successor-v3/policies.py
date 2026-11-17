"""Matched immutable authoring rules versus retained train-fitted revisions."""
from .common import GLOBAL_POLICIES,PREDICTION_POLICIES,fields,need,integer,pin,check_pin

LIMITS=('provider_calls','provider_input_tokens','provider_output_tokens','provider_cost_microunits',
    'tools','processes','source_bytes','state_bytes','view_bytes','output_bytes','request_bytes',
    'cumulative_read_bytes','cumulative_write_bytes','retained_bytes','live_bytes','cpu_ns','wall_ns')

def validate_policies(policies):
    fields(policies,GLOBAL_POLICIES);common=None
    for key,p in policies.items():
        fields(p,('schema','name','source','provider','wire_limits','runtime_pin','resource_profile_pin','limits','question','paper_exposure_pin','capabilities'))
        need(p['schema']=='neural004_global_policy_v1' and p['name']==key,'all ten exact global policies')
        fields(p['source'],('path','bytes','sha256'));check_pin({k:p['source'][k] for k in ('bytes','sha256')})
        for n in ('runtime_pin','resource_profile_pin','paper_exposure_pin'):check_pin(p[n])
        fields(p['limits'],LIMITS)
        for value in p['limits'].values():integer(value,1)
        fields(p['capabilities'],('text','images','general_analysis','generated_python','hmp_available'))
        need(p['capabilities']['text'] is True and p['capabilities']['general_analysis'] is True and p['capabilities']['generated_python'] is True,'substantive tool/analysis research interface')
        if key in PREDICTION_POLICIES:
            expected=key.split('/')[1] in ('H','EH');need(p['capabilities']['hmp_available'] is expected,'matched view-specific HMP availability')
            comparison={k:p[k] for k in ('provider','wire_limits','runtime_pin','resource_profile_pin','limits','question','paper_exposure_pin')}
            comparison['capabilities']={k:v for k,v in p['capabilities'].items() if k!='hmp_available'}
            if common is None:common=comparison
            need(comparison==common,'matched provider/tools/environment/resources across P/I and B/E/H/EH')
    return policies

class Commitments:
    def __init__(self,policies,authorities,ledger):
        self.policies=validate_policies(policies);self.authorities=authorities;self.ledger=ledger
        self.pin=pin(policies,4*1048576);self.opened=set();self.committed=None
    def commit(self,envelope,program_bodies):
        need(self.committed is None and not self.opened,'one commitment before any numeric view')
        from .common import body_pin
        fields(program_bodies,GLOBAL_POLICIES)
        for key,raw in program_bodies.items():
            need(body_pin(raw)=={k:self.policies[key]['source'][k] for k in ('bytes','sha256')},'actual immutable global source bodies')
        verified=self.authorities.verify(envelope,'operator','global_commitment',self.pin)
        fields(verified['facts'],('before_numeric_exposure','durable_source_inventory','authoring_history','context_isolation'))
        need(verified['facts']['before_numeric_exposure'] is True,'independent historical commitment chronology')
        for n in ('durable_source_inventory','authoring_history','context_isolation'):check_pin(verified['facts'][n])
        self.committed=verified;return verified
    def open(self,context,policy):
        need(self.committed is not None and context not in self.opened and policy in self.policies,'fresh postcommit source context')
        self.ledger.tick();self.opened.add(context);return self.policies[policy]

class History:
    def __init__(self,context,mode,view,policy_pin,training_pin,held_pin,ledger,limits):
        need(mode in ('P','I') and view in ('B','E','H','EH'),'prediction mode/view')
        self.context=context;self.mode=mode;self.view=view;self.policy_pin=policy_pin
        self.training_pin=training_pin;self.held_pin=held_pin;self.ledger=ledger;self.limits=limits
        self.actions=[];self.revisions=[];self.calls=0;self.tools=0;self.held_open=False;self.method_seal=None;self.prediction=None;self.state=None;self.current=None;self.closed=False
    def record(self,kind,payload):
        need(not self.closed,'closed actor history');self.ledger.tick()
        self.actions.append({'sequence':len(self.actions),'kind':kind,'payload':payload,'clock_ns':self.ledger.clock()})
    def provider_call(self):
        need(not (self.mode=='P' and self.held_open),'no post-held P authoring')
        need(self.calls<self.limits['provider_calls'],'per-context provider cap');self.calls+=1
        self.record('provider_attempt',{'number':self.calls})
    def revise(self,source_pin):
        need(not(self.mode=='P' and self.held_open),'P generated source frozen before held')
        check_pin(source_pin);parent=self.current;self.current=source_pin;self.state=None;self.prediction=None
        self.revisions.append({'source_pin':source_pin,'parent':parent,'after_held':self.held_open})
        self.record('generated_revision',self.revisions[-1])
    def tool(self,action):
        need(self.tools<self.limits['tools'],'per-context tool cap');self.tools+=1
        need(action in ('analyze','train','predict'),'fixed actual generated tool action')
        need(self.current is not None,'generated method exists')
        if self.mode=='P' and self.held_open:need(action=='predict','P held phase only sealed procedure inference')
        if action=='predict':need(self.state is not None and self.held_open,'fitted state before held inference')
        self.record('tool_attempt',{'action':action,'source_pin':self.current,'state_pin':None if self.state is None else self.state['pin']})
    def fitted(self,state_pin,execution_record):
        check_pin(state_pin);need(execution_record['outputs_closed'],'actual closed fitted-state artifact')
        self.state={'pin':state_pin,'source_pin':self.current,'training_pin':self.training_pin,
            'held_seen':self.held_open,'execution_pin':pin(execution_record)};self.prediction=None
        self.record('fitted_state',self.state)
    def seal_method(self):
        need(not self.held_open and self.state is not None and self.current==self.state['source_pin'],'complete pre-held P method/state')
        self.method_seal=pin({'source':self.current,'state':self.state,'training_pin':self.training_pin,'history':self.actions})
        self.record('method_seal',self.method_seal);return self.method_seal
    def open_held(self):
        need(not self.held_open and (self.mode=='I' or self.method_seal is not None),'P method seal before held')
        self.held_open=True;self.record('held_open',{'held_pin':self.held_pin})
    def seal_prediction(self,forecast_pin,execution_record):
        need(self.held_open and self.state is not None and self.state['source_pin']==self.current,'same sealed fitted source')
        self.prediction={'forecast_pin':forecast_pin,'source_pin':self.current,'state':self.state,'method_seal':self.method_seal,
            'query_pin':self.held_pin,'execution_pin':pin(execution_record),'history_pin':pin(self.actions,8*1048576)}
        self.record('prediction_seal',self.prediction);self.closed=True;return self.prediction
