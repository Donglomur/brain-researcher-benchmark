"""Bounded, JSON-safe failure evidence retaining original primary exceptions."""
import base64
from .common import need,body_pin,Cleanup

def safe(value,cap,seen=None):
    """Preserve exact binary provider prefixes as bounded base64 plus identity."""
    if seen is None:seen=set()
    if type(value) is bytes:
        need(len(value)<=cap,'bounded retained failure bytes')
        return {'schema':'neural004_exact_failure_bytes_v1','pin':body_pin(value),'base64':base64.b64encode(value).decode('ascii')}
    if value is None or type(value) in (str,int,float,bool):return value
    need(id(value) not in seen,'acyclic failure evidence');seen.add(id(value))
    try:
        if type(value) is list:return [safe(x,cap,seen) for x in value]
        if type(value) is dict:
            need(all(type(k) is str for k in value),'string failure keys');return {k:safe(v,cap,seen) for k,v in value.items()}
        return {'unsupported_type':type(value).__name__}
    finally:seen.remove(id(value))

def describe(error,cap):
    receipt=getattr(error,'receipt',None)
    # The actual provider reader reserves and retains cap+1 bytes to prove an
    # overflow. Only that named producer field receives the sentinel allowance.
    if type(receipt) is dict and type(receipt.get('response_prefix')) is bytes:
        receipt=dict(receipt)
        receipt['response_prefix']=safe(receipt['response_prefix'],cap+1)
    result={'type':type(error).__name__,'message':str(error)[:1024],
        'provider_receipt':safe(receipt,cap),
        'cleanup_errors':safe(getattr(error,'ach_cleanup_errors',[]),cap)}
    return result

def retain_primary(bodies,name,payload,error,cap):
    cleanup=Cleanup(bodies.ledger)
    cleanup.defer('retain original failure and cost/prefix evidence',lambda:bodies.put_json(name,safe(payload,cap),cutoff='closeout'))
    cleanup.run(error)
