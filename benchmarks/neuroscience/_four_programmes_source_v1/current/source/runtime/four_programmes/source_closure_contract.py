"""Consume the adopted earlier H-owned full source-list capture.

The array is identity evidence only. Root/native/scientific prerequisites are
unchanged, and neither a decoded list nor an admission Pin grants authority.
"""
from .common import Store,need,same,bounded_size
from .backend_capture import CapturedRecord
from .precommit_records import validate_type

def require_prepared_source_closure_target(contract,outputs):
    from .development_contract import DevelopmentContract,ContractAdmissionHandle,_CONTRACT
    need(type(contract) is DevelopmentContract and contract._token is _CONTRACT,
         'actual same private admitted contract')
    owner=contract.owner;handle=getattr(owner.parent,'contract_admission',None)
    need(type(handle) is ContractAdmissionHandle and handle.contract is contract and
         handle.owner is owner and contract.admitted_open is handle.admitted_open and
         contract.admitted_open is not None and handle.raw_first is None,
         'both original admission captures completed before pair/state consumption')
    capture=contract.source_closure_capture
    need(type(capture) is CapturedRecord and capture is handle.source_closure_capture and
         capture.owner is owner and capture.kind=='PreparedSourceClosureArray' and
         capture._attempt.complete is capture and handle.source_closure_attempted,
         'actual earlier same-owner complete capture, not provisional bytes or a supplied descriptor')
    need(type(outputs) is Store and outputs is handle.outputs and outputs.meter is owner.host,
         'same original H publication Store for complete readback')
    bound=bounded_size(contract.policy['source_closure'])
    owner.host.charge('work_units',bound+len(capture.raw))
    owner.host.charge('retained_bytes',bound+len(capture.raw)+1)
    validate_type('PreparedSourceClosureArray',contract.policy['source_closure'])
    need(outputs.read(capture.pin,owner.plan['maximum_output_bytes'],metadata=True)==capture.raw and
         same(capture.body,contract.policy['source_closure']),
         'exact whole ordered authenticated policy array and original bytes at each consumer')
    return capture
