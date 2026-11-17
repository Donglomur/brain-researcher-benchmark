"""Capability-aware protected I/O with the unchanged accepted numerical kernels.

Accepted manifest/body/seal admission is called directly. The only relocated
comparison dispatch is the same four closed kinds; no user callback is accepted.
"""
from banc_runtime.codec import need,parse
from banc_runtime.collect import (Seal,validate_manifest,product_slots,admit_retained,seal_identity,digest)
from banc_runtime.metrics import numeric_error,adjusted_rand,embedding_distances
from .io import read
from .clock import guard

def capture_bundle(root,declared,contracts,*,program_identity,meter,cap=1048576):
    raw=read(root,declared,meter,cap);b=validate_manifest(raw,contracts,program_identity=program_identity,cap=cap)
    payloads=tuple((r['id'],None if r['state']=='required_unscorable' else read(root,r['payload'],meter,cap)) for r in b['panels'])
    products=tuple((slot[0],read(root,slot[3]['payload'],meter,cap)) for slot in product_slots(b))
    admit_retained(raw,payloads,products,contracts,program_identity=program_identity,cap=cap)
    guard(meter,'after_full_capability_capture')
    return Seal(program_identity,raw,payloads,seal_identity(raw,payloads,products),products)

def compare_sealed(candidate,reference_root,reference_descriptor,contracts,*,program_identity,meter,cap=1048576):
    need(type(candidate) is Seal,'fully admitted immutable candidate seal required');digest(program_identity)
    need(candidate.program_identity==program_identity,'candidate independently selected programme')
    admit_retained(candidate.manifest_bytes,candidate.payloads,candidate.products,contracts,program_identity=program_identity,cap=cap)
    need(seal_identity(candidate.manifest_bytes,candidate.payloads,candidate.products)==candidate.identity,'candidate seal identity')
    guard(meter,'after_candidate_before_reference')
    reference=capture_bundle(reference_root,reference_descriptor,contracts,program_identity=program_identity,meter=meter,cap=cap)
    results=[]
    for (name,craw),(_,rraw) in zip(candidate.payloads,reference.payloads):
        if craw is None or rraw is None:
            results.append({'id':name,'state':'required_unscorable','reason':'candidate or independent reference absent'});continue
        c=parse(craw);r=parse(rraw)
        need(c['kind']==r['kind'] and c['support']==r['support'] and c['estimand_identity']==r['estimand_identity'],'complete fixed estimand/support equality:'+name)
        if c['kind']=='numeric':
            cm=tuple(v is not None for v in c['values']);rm=tuple(v is not None for v in r['values'])
            need(cm==rm,'observed support mask equality:'+name)
            if not any(cm):results.append({'id':name,'state':'required_unscorable','reason':'no observed numeric support'});continue
            metric=numeric_error(tuple(v for v in c['values'] if v is not None),tuple(v for v in r['values'] if v is not None),meter)
        elif c['kind']=='cluster':metric={'adjusted_rand':adjusted_rand(tuple(c['values']),tuple(r['values']),meter)}
        elif c['kind']=='embedding':metric=numeric_error(embedding_distances(tuple(map(tuple,c['values'])),meter),embedding_distances(tuple(map(tuple,r['values'])),meter),meter)
        else:metric={'state':'requires_independent_scientific_review','automatic_credit':False}
        results.append({'id':name,'state':'compared_unqualified','metric':metric})
    guard(meter,'after_protected_comparison')
    return {'candidate_seal':candidate.identity,'reference_seal':reference.identity,'panels':results,'biological_units':1,
      'scientific_qualification':False,'reference_qualification_external_required':True,'success_threshold_selected':False,'whole_attempt_costs':meter.report()}
