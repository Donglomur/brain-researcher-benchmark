"""Whole immutable store custody, joined to actual phase outputs; no regrading."""
from pathlib import Path
import re

KINDS={'reproduction':336,'reference_fit':3528,'candidate_fit':7056,'prediction':10584,'native_capture_evidence':56}

def member_pins(root,manifest_pin,limits,reader):
    root=u.components(root);u.need(root.is_dir(),'exact immutable artifact directory')
    manifest,mp=reader.json(root/'result.json',limits['metadata'],manifest_pin)
    u.need(type(manifest)is dict and set(manifest)=={'schema','root','blobs'} and manifest['schema']=='paper020_wire_manifest_v1'
           and type(manifest['blobs'])is dict,'exact wire manifest required')
    result={'result.json':mp};total=0
    for key,p in manifest['blobs'].items():
        u.need(re.fullmatch('[0-9a-f]{64}',key) and type(p)is dict and set(p)=={'file','bytes','sha256'}
               and p['file']==key+'.bin' and p['sha256']==key,'exact immutable blob declaration')
        total+=u.only_pin(p)['bytes'];u.need(total<=limits['bytes'],'complete artifact blob extent')
        result[p['file']]=reader.file_pin(root/p['file'],u.only_pin(p))
    u.need({x.name for x in root.iterdir()}==set(result),'extra or missing immutable artifact members')
    return result

def capture(bound,reader):
    store=bound.runtime.store;d=bound.runtime.authority.document;out=[]
    for handle,record in sorted(store.handles.items()):
        u.need(re.fullmatch('[0-9a-f]{32}',handle) and len(record)==5,'exact immutable store handle')
        context,binding,kind,seal,fingerprint=record
        path=store.root/handle;mp={'bytes':(path/'result.json').lstat().st_size,'sha256':seal}
        members=member_pins(path,mp,d['wire_limits'],reader)
        out.append({'handle':handle,'context':context,'binding':binding,'kind':kind,'manifest_pin':mp,
                    'artifact_digest':fingerprint,'members':members})
    return {'schema':'paper020_complete_artifact_index_v1','store_root':str(store.root),'artifacts':out}

def validate(index,validated,document,reader):
    u.need(type(index)is dict and set(index)=={'schema','store_root','artifacts'}
           and index['schema']=='paper020_complete_artifact_index_v1' and index['store_root']==document['store_root'],
           'exact signed full artifact store required')
    rows=validated['rows'];by_binding={r['binding']:r for r in rows};by_handle={};by_phase={};counts={}
    for a in index['artifacts']:
        u.need(type(a)is dict and set(a)=={'handle','context','binding','kind','manifest_pin','artifact_digest','members'},'exact artifact descriptor')
        handle=a['handle'];u.need(type(handle)is str and re.fullmatch('[0-9a-f]{32}',handle) and handle not in by_handle,'unique actual artifact handle')
        u.need(a['binding']in by_binding and a['kind']in KINDS,'artifact must bind an actual scientific phase')
        p=by_binding[a['binding']]['phase'];pid=p['id'];by_phase.setdefault(pid,[]).append(a)
        members=member_pins(Path(index['store_root'])/handle,a['manifest_pin'],document['wire_limits'],reader)
        u.need(members==a['members'],'complete post-exit artifact bytes differ')
        u.only_pin({'bytes':0,'sha256':a['artifact_digest']})
        counts[a['kind']]=counts.get(a['kind'],0)+1;by_handle[handle]=a
    u.need(counts==KINDS,'all full native/prediction/fitted/native-capture artifacts required')
    for row in rows:
        phase=row['phase'];kind=phase['kind'];art=row['result']['artifact'];found=by_phase.get(phase['id'],[])
        if kind in ('predict','reproduction'):
            expected='prediction'if kind=='predict'else'reproduction'
            values=[x for x in found if x['kind']==expected]
            u.need(len(values)==1 and values[0]['handle']==art['handle'] and values[0]['context']==art['context']
                   and values[0]['artifact_digest']==art['artifact_digest'],'actual returned output/store join differs')
            literal=kind=='reproduction' and phase['actor']=='reference' and phase['requires_literal_matlab']
            u.need(len(found)==(2 if literal else 1),'unexpected scientific artifacts')
            if literal:u.need(sum(x['kind']=='native_capture_evidence'for x in found)==1,'full native workspace evidence required')
            if kind=='reproduction':
                context=validated['outputs'][phase['dependencies'][0]]['context']
            else:
                fit_id=phase['id'].replace('predict/','fit/',1);fits=by_phase.get(fit_id,[])
                u.need(len(fits)==1,'matching original fitted context required');context=fits[0]['context']
            u.need(all(x['context']==context for x in found),'output crossed actual native/prediction context')
        elif kind=='fit':
            expected='reference_fit'if phase['actor']=='reference'else'candidate_fit'
            u.need(len(found)==1 and found[0]['kind']==expected,'one actual immutable fit artifact per configuration')
            u.need(found[0]['context']==validated['outputs'][phase['dependencies'][0]]['context'],'fit crossed actual fresh training context')
        else:u.need(not found,'unplanned immutable scientific artifact')
    return {'artifact_count':len(by_handle),'kind_counts':counts,'index_digest':u.sha(u.canonical(index))}
