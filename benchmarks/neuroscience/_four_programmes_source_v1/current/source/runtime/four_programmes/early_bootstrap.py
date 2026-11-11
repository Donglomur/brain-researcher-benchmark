"""Capture the earlier seed and owner binding under the existing parent Share.

No constructor mints the missing independently qualified parent capability.
Every successful result preserves its actual Share, counters and active span.
"""
import time
from .common import Store,need,same,descriptor,bounded_size,parse,integer
from .precommit_records import validate_type
from .early_resources import ParentCustody,EarlyResources
from .early_failure import _store_view,_publish_complete,SelectionReadState,fail_v2

_OPEN=object()

class EarlyBootstrapResult:
    __slots__=('parent','owner','inputs','outputs','plan_pin','seed_pin','binding_pin','selection_state','_token')
    def __init__(self,token,**values):
        need(token is _OPEN,'actual complete seed/binding publication return')
        for key,value in values.items():setattr(self,key,value)
        self._token=token

def attach_seed_capture_v2(parent,seed,*,plan_pin,inputs,outputs):
    need(type(parent)is ParentCustody,'actual independently admitted earlier parent, not supplied metadata')
    need(not getattr(parent,'bootstrap_attempted',False),'one original bootstrap attempt including failed reads')
    parent.bootstrap_attempted=True
    state=None;owner=None;host_outputs=None
    try:
        need(parent.first_raw is None and parent.owner is None,'no bootstrap after prior failure or existing attachment')
        parent.assert_live()
        need(type(inputs)is Store and type(outputs)is Store and inputs.meter is parent.share and outputs.meter is parent.share,
             'actual earlier selected roots and already live parent Share')
        # Source-closed literal validation is charged before any input read.
        bound=bounded_size(seed);parent.share.charge('work_units',bound)
        parent.share.charge('retained_bytes',bound)
        validate_type('EarlyOwnerSeed',seed);descriptor(plan_pin)
        need(same(plan_pin,seed['construction_plan']),'exact earlier selected construction-plan descriptor')
        # The parent owns this read before the nested plan exists. Its existing
        # selected read/work/retained limits admit the full proposed extent;
        # later plan values cannot replenish that earlier consumed allowance.
        parent.share.charge('retained_bytes',16*plan_pin['bytes']+4096)
        raw=inputs.read(plan_pin,plan_pin['bytes']+1,metadata=True)
        plan=parse(raw,plan_pin['bytes']+1);validate_type('ConstructionPlan',plan)
        need(str(outputs.root)==plan['output_root'],'exact earlier actual private root matches complete plan')
        owner=EarlyResources.attach_seed_v2(parent,seed,plan)
        host_inputs=_store_view(inputs,owner.host);host_outputs=_store_view(outputs,owner.host)
        state=SelectionReadState(owner,path=seed['private_selection_path'],cap=seed['maximum_selection_bytes'])
        seed_pin=_publish_complete(host_outputs,'early_seed.json',seed,'EarlyOwnerSeed',cap=plan['maximum_output_bytes'])
        parent.seed_pin=seed_pin;parent.known_records.append(seed_pin)
        owner.check();now=time.monotonic_ns();integer(now)
        need(now<parent.original_deadline,'original binding publication cutoff')
        binding={'schema':'ci_earlyownerbinding_v2','seed':seed_pin,'construction_plan':dict(plan_pin),
                 'parent_owner_custody':parent.custody,'host_identity':parent.identity,'clock':parent.clock,
                 'early_reservation':parent.share.row,'owner_nonce':parent.nonce,'bound_ns':now,
                 'cost_prefix':owner.cost_prefix()}
        binding_pin=_publish_complete(host_outputs,'early_owner_binding.json',binding,'EarlyOwnerBinding',cap=plan['maximum_output_bytes'])
        parent.binding_pin=binding_pin;parent.known_records.append(binding_pin)
        # Binding cost_prefix is an earlier observation. The same live owner
        # continues to include its publication and every subsequent operation.
        return EarlyBootstrapResult(_OPEN,parent=parent,owner=owner,inputs=host_inputs,outputs=host_outputs,
            plan_pin=dict(plan_pin),seed_pin=seed_pin,binding_pin=binding_pin,selection_state=state)
    except BaseException as error:
        parent.retain(error,'seed_admission','identity_refusal','EarlyBootstrap.attach_seed_capture_v2')
        return fail_v2(parent,error,attempt=parent.nonce,phase='seed_admission',code='identity_refusal',
                       site='EarlyBootstrap.attach_seed_capture_v2',output_store=host_outputs,selection_state=state)
