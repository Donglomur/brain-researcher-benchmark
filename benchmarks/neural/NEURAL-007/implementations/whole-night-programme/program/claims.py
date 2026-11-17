"""Typed claim arithmetic on already permitted views and captured probe evidence.

This verifies numbers and complete declared support only. A correctly recomputed
validation number does not prove unused labels, scientific reasoning, novelty,
method validity or causal interpretation; those remain independent admission.
"""
from pathlib import Path
import math
import struct
from .common import capture,decode,need,pin,npy_header,DecodingStream,relative
from .science import confusion,combine_confusions,person_macro
from .scorer import array_rows


def validation(claim,public,mounts,probes,meter):
    need(claim['support']=='validation' and claim['estimator']=='equal_person_fixed_five_macro_f1','Declared permitted validation estimator')
    evidence=claim['artifact'];need(type(evidence) is dict and set(evidence)=={'probe','manifest'} and type(evidence['probe']) is int,'Exact captured probe locator')
    result=probes[evidence['probe']];receipt=result['receipt'];root=Path(receipt['quarantine_root']);files=receipt['output_inventory']['files']
    name='artifacts/'+evidence['manifest'];need(name in files,'Evidence is an actual captured tool output')
    value=decode(capture(root/name,files[name],meter=meter));need(value['schema']=='neural007_predictions_v1','Complete typed prediction evidence')
    wanted={(r['person'],r['night']):r for r in public['nights'] if r['split_role']=='validation13'}
    need(len({k[0] for k in wanted})==13 and len(value['nights'])==len(wanted),'All grouped validation people/nights')
    matrices={};seen=set()
    for row in value['nights']:
        key=(row['person'],row['night']);need(key in wanted and key not in seen,'Exact validation evidence support');seen.add(key)
        expected=wanted[key];e=expected['epochs'];need(row['epochs']==e,'All-clock validation support')
        probability='artifacts/'+row['path'];need(probability in files,'Captured prediction body')
        p=list(array_rows({'path':str(root/probability),**files[probability]},e,5,'<f8',meter))
        directory='/view/'+expected['directory']
        operands=[]
        for name,dtype in [('stages.npy','|i1'),('mask.npy','|b1')]:
            m=mounts[directory+'/'+name];need(m['kind']=='file' and len(m['files'])==1,'One permitted training-target file')
            operands.append(list(array_rows({'path':m['path'],**next(iter(m['files'].values()))},e,0,dtype,meter)))
        y,mask=operands;need(mask==[x>=0 for x in y],'Permitted validation mask equality')
        matrices.setdefault(key[0],[]).append(confusion(p,y))
    need(seen==set(wanted),'Complete captured validation evidence')
    computed=person_macro({p:combine_confusions(x) for p,x in matrices.items()},13)['primary']
    need(type(claim['value']) in (float,int) and math.isfinite(claim['value']) and abs(computed-claim['value'])<=1e-12,'Independent validation-number parity')
    return {'kind':'validation_metric','computed':computed,'complete_people':13,'selection_exposed':True,
            'fit_support_independently_admitted':False,'scientific_claim_validity':False}


def signal_summary(claim,public,mounts,probe,meter):
    artifact=claim['artifact']; name='artifacts/'+relative(artifact['manifest'])
    receipt=probe['receipt']; files=receipt['output_inventory']['files']; need(name in files,'Actual captured signal evidence')
    evidence=decode(capture(Path(receipt['quarantine_root'])/name,files[name],meter=meter))
    need(evidence=={'schema':'neural007_signal_summary_evidence_v1','estimator':claim['estimator'],'channel':claim['channel'],'value':claim['value']},'Captured signal evidence exactly matches declared numeric claim')
    need(claim['model'] is None,'Raw signal summary has no fitted-model claim')
    need(claim['support']=='unlabeled_current_query' and claim['estimator']=='full_current_person_channel_mean_volts','Declared raw-signal summary only')
    channel=claim['channel'];need(type(channel) is int and channel in (0,1,2),'Typed channel')
    nights=[r for r in public['nights'] if r['split_role']=='current_query'];need(nights,'Current-person full nights')
    total=0;parts=[]
    for n in nights:
        need(channel in n['channels'],'No omitted-view signal access')
        mount=mounts['/view/'+n['directory']+f'/channel-{channel}.npy'];d=next(iter(mount['files'].values()))
        h=npy_header(mount['path'],d['bytes'],meter);need(h['dtype']=='<f8' and h['shape']==[n['epochs']*3000],'Complete current signal geometry')
        with DecodingStream(mount['path'],d,meter) as stream:
            stream.read(h['header_bytes']);left=n['epochs']*3000
            while left:
                count=min(left,4096);raw=stream.read(count*8);need(len(raw)==count*8,'Complete signal chunk')
                values=struct.unpack('<'+'d'*count,raw);need(all(math.isfinite(x) for x in values),'Finite current signal')
                parts.append(math.fsum(values));total+=count;left-=count
    computed=math.fsum(parts)/total
    need(type(claim['value']) in (int,float) and math.isfinite(claim['value']) and abs(computed-claim['value'])<=1e-12,'Independent raw-signal summary parity')
    return {'kind':'signal_summary','computed':computed,'full_samples':total,'label_access':False,'scientific_claim_validity':False}


def verify(claims,public,mounts,probes,meter):
    result=[]
    for claim in claims:
        if claim['kind']=='methodological':
            result.append({'kind':'methodological','independent_content_admission':'unresolved'});continue
        artifact=claim['artifact']
        need(type(artifact) is dict and set(artifact)=={'probe','manifest'} and type(artifact['probe']) is int and artifact['probe'] in probes,'Exact captured numeric evidence producer')
        relative(artifact['manifest']);producer=probes[artifact['probe']]
        need(claim['source']==producer['probe_source'],'Claim source belongs to the same captured evidence producer')
        need(claim['inputs']==pin(__import__('json').dumps(public,sort_keys=True,separators=(',',':')).encode()+b'\n'),'Claim exact permitted view binding')
        if claim['kind']=='validation_metric':
            model=claim['model']; need(type(model) is dict and set(model)=={'path','bytes','sha256'},'Captured fitted model operand for validation claim')
            name='artifacts/'+relative(model['path'])
            need(producer['receipt']['output_inventory']['files'].get(name)=={k:model[k] for k in ('bytes','sha256')},'Declared model belongs to same captured probe')
        if claim['kind']=='validation_metric':result.append(validation(claim,public,mounts,probes,meter))
        elif claim['kind']=='signal_summary':result.append(signal_summary(claim,public,mounts,producer,meter))
        else:raise ValueError('Unsupported scientific numeric assertion')
    return {'claims':result,'typed_numbers_verified':True,'fit_support_and_broad_scientific_reasoning_admitted':False}
