"""Concrete evaluator-owned full source preparation inside the native capsule."""
from pathlib import Path
from core import Budget,capture,parse,publish,encoded,pin,need
from preparation import run as prepare

def run(request):
    b=Budget(request['origin'],request['deadline'],request['limits']['read_bytes'],request['limits']['write_bytes'])
    values={};originals={}
    for name in('ROSTER.json','REVIEW.json'):
        raw,_=capture('/inputs/'+name,request['inputs'][name],request['limits']['metadata_bytes'],b,readonly=True);originals[name]=raw;values[name]=parse(raw)
    from roster import bind
    roster=bind(originals['ROSTER.json'],values['REVIEW.json'])
    raw,_=capture('/inputs/IDENTITY.key',request['inputs']['IDENTITY.key'],32,b,readonly=True)
    need(len(raw)==32,'independent private identity key, never actor-mounted')
    result=prepare(roster,values['REVIEW.json'],'/inputs/raw','/output/prepared',raw,b,request['preparation_limits'])
    private_raw,_=capture(result['path'],result['pin'],request['limits']['metadata_bytes'],b,readonly=True);private=parse(private_raw)
    outputs={'prepared/PRIVATE.json':result['pin']}
    outputs.update({'prepared/epochs/'+r['epoch']['path']:r['epoch']['pin'] for r in private['rows'] if r['eligibility']})
    receipt={'schema':'n041_preparation_receipt_v1','operation':request['operation'],'request':request['request_identity'],'source':request['source'],
        'origin':b.origin,'deadline':b.deadline,'observed_end':b.tick(),'outputs':outputs,'roster':request['inputs']['ROSTER.json'],
        'clinical_review':request['inputs']['REVIEW.json'],'private_targets':result['pin'],
        'logical_read_reserved':b.read_bytes,'logical_write_reserved':b.write_bytes,'physical_native_costs_external':True}
    publish('/output/RECEIPT.json',encoded(receipt),b);return receipt
