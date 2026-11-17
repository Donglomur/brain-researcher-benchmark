"""Installed six-operation physical subdivision, never native qualification.

The immutable expectation independently selects every CPU/wall value. Its
existing five-case qualifier supplies the original whole-hold enforcement;
these six rows are a prospective subdivision, not six observed executions.
"""
import hashlib
from .common import need
from .backend_json import canonical
from .operator_records import _layout

OPERATIONS=('base','server_executable','model_gguf','template','tokenizer_source','renderer_source')
_TOKEN=object()
_FIELDS={'schema','deployment_id','environment','source_admission','installed_closure',
    'context_policy','backend_profile','artifact_selection','recipe_source','driver_source',
    'control_selection','control_observation','enforcer_source','rows'}
_PINS=('environment','source_admission','installed_closure','context_policy','backend_profile',
       'artifact_selection','recipe_source','driver_source','control_observation','enforcer_source')

def validate_initialization_profile_v4(expectation,control,observation_pin,physical):
    """Closed selected data plus actual earlier control-evidence inverse."""
    wrapper=expectation['initialization_physical_profile']
    need(type(wrapper)is dict and set(wrapper)=={'descriptor','body'},'complete independently installed profile wrapper')
    _layout('Pin',wrapper['descriptor']);p=wrapper['body']
    need(type(p)is dict and set(p)==_FIELDS and p['schema']=='four_worker_initialization_physical_profile_v1',
         'closed six-operation installed physical selection')
    raw=canonical(p,65536)
    need(wrapper['descriptor']['bytes']==len(raw) and wrapper['descriptor']['sha256']==hashlib.sha256(raw).hexdigest(),
         'exact independently installed physical-profile identity')
    for key in _PINS:_layout('Pin',p[key])
    for key in ('deployment_id','environment','source_admission','installed_closure','control_selection'):
        need(p[key]==expectation[key],'same independently selected initialization '+key)
    need(p['context_policy']==physical.descriptor['context_policy'] and
         p['control_observation']==observation_pin and p['enforcer_source']==control['enforcer_source'] and
         control['source_admission']==p['source_admission'],
         'original inherited policy and complete earlier control-enforcer evidence')
    loaded={r['module']:r for r in expectation['loaded_sources']}
    for field,module in (('recipe_source','worker_initialization_recipe_v4'),('driver_source','worker_main_native_v4')):
        need(loaded[__package__+'.'+module]['source']==p[field] and
             p[field]in expectation['entry_configuration']['source_closure'],
             'exact actual loaded recipe/driver in the qualified complete entry closure')
    rows=p['rows'];need(type(rows)is list and len(rows)==len(OPERATIONS),'all six original initialization operations')
    totals={'cpu_ns':0,'wall_ns':0}
    for ordinal,(operation,row)in enumerate(zip(OPERATIONS,rows)):
        need(type(row)is dict and set(row)=={'ordinal','operation','site','stage','cpu_ns','wall_ns'} and
             type(row['ordinal'])is int and row['ordinal']==ordinal and row['operation']==operation and
             row['site']==('local_parse'if ordinal==0 else'artifact_read') and row['stage']=='initialization',
             'fixed complete source operation/site/stage order')
        for key in totals:
            value=row[key];need(type(value)is int and 0<value<=9007199254740991,'positive selected physical value, no default')
            totals[key]+=value
    reservation=physical.descriptor['reservation_body']['arm_reserved']
    for key,value in totals.items():
        need(control['arm_limits'][key]==control['arm_limit_readback'][key]==reservation[key] and
             value<=reservation[key], 'six physical selections inside actual qualified original control arm hold')
    return raw

class WorkerInitializationPhysicalProfileV4:
    """Same pre-Hello admission; no participant setter or ambient profile."""
    __slots__=('admission','raw','pin','body','rows')
    def __init__(self,token,admission):
        need(token is _TOKEN,'fixed installed expectation producer only')
        self.admission=admission
        wrapper=admission.expected['initialization_physical_profile']
        self.body=wrapper['body'];self.pin=dict(wrapper['descriptor'])
        self.raw=canonical(self.body,65536)
        self.rows=tuple((r['ordinal'],r['operation'],r['site'],r['stage'],r['cpu_ns'],r['wall_ns'])for r in self.body['rows'])
    @classmethod
    def from_prehello_v4(cls,admission):
        from . import worker_installed_expectation_v1 as entry
        need(type(admission)is entry.WorkerPreHelloAdmissionV3 and entry._attempt is admission and
             admission.physical.prehello_admission is admission and not admission.complete and
             admission.initialization_profile is None and admission.loaded and admission.raw_first is None,
             'actual earlier validated once-only installed expectation attempt')
        return cls(_TOKEN,admission)
    def require_original(self,context):
        from .worker_context_v3 import WorkerContextProxy
        from .backend_linux_worker_channel import WorkerNativeChannelEndpoint
        a=self.admission;a.require_original()
        need(type(context)is WorkerContextProxy and type(context.channel.endpoint)is WorkerNativeChannelEndpoint and
             context.channel.endpoint.admission is a and a.endpoint is context.channel.endpoint and
             a.initialization_profile is self and context.activated and not context.poisoned and
             context.local_raw_first is None,'same original installed profile and active context custody')
        context.require_active()
        wrapper=a.expected['initialization_physical_profile']
        need(self.body is wrapper['body'] and self.pin==wrapper['descriptor'] and canonical(self.body,65536)==self.raw and
             self.rows==tuple((r['ordinal'],r['operation'],r['site'],r['stage'],r['cpu_ns'],r['wall_ns'])for r in self.body['rows']),
             'complete immutable physical recipe selection unchanged')
        p=self.body
        need(context.context_identity['source_admission']==p['source_admission'] and
             context.bootstrap('NativeContextPolicyV2').pin==p['context_policy'] and
             context.bootstrap('LocalBackendProfile').pin==p['backend_profile'] and
             context.bootstrap('LocalArtifactSelection').pin==p['artifact_selection'],
             'same actual delivered original policy/backend/artifact profile')
        profile=context.bootstrap('NativeDevelopmentProfileV3').body
        need(all(profile[k]==p['control_selection'][k]for k in ('whole_envelope','worker_envelope')),
             'same qualified whole and worker envelope selection')
        reservation=context.bootstrap('ChannelBudgetReservationV1').body
        need(reservation==a.physical.descriptor['reservation_body'] and
             all(sum(r[4+i]for r in self.rows)<=reservation['arm_reserved'][key]
                 for i,key in enumerate(('cpu_ns','wall_ns'))), 'same complete delivered original control hold')
        return self
