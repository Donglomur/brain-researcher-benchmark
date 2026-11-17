"""Bind a complete audited native segment panel. No filtering, labels, fits or scores invented."""
import sys,hashlib,hmac
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
import numpy as np
from io_contract import capture,parse,put,fresh,ordinary
from arrays import read_array,write_array
from protocol import digest,canonical
from design import contexts,hexhash,TASK_ID,SOURCE_PROTOCOL_SHA,RECORDINGS
from intervals import validate_segments

# Table9, not the unmodified PopT clean-channel counts.
COUNTS={1:(91,25,6),2:(100,25,8),3:(91,20,4),4:(151,36,9),5:(109,25,6),6:(134,30,6),7:(205,47,9),8:(121,29,7),9:(72,19,5),10:(173,42,8)}
CAP=12000000


def bound_json(base,d):
    if not isinstance(d,dict) or set(d)!={'path','bytes','sha256'} or not isinstance(d['path'],str) or Path(d['path']).name!=d['path'] or '\\' in d['path'] or not d['path'].endswith('.json') or type(d['bytes']) is not int or not 0<d['bytes']<=32000000 or not hexhash(d['sha256']):raise ValueError('Bound source metadata descriptor')
    body=capture(Path(base)/d['path'],cap=32000000)
    if len(body)!=d['bytes'] or hashlib.sha256(body).hexdigest()!=d['sha256']:raise ValueError('Source metadata identity changed')
    return parse(body)


def check_context(d,e,source_protocol_sha256):
    if d.get('schema')!='barista_resolved_context_v1' or d.get('source_protocol_sha256')!=source_protocol_sha256 or any(d.get(k)!=v for k,v in e.items()):raise ValueError('Complete frozen source context identity')
    if d.get('recording')!=RECORDINGS[e['person']]:raise ValueError('Authentic paper session-to-trial mapping')
    c,npcl,nlobe=COUNTS[e['person']];channels=d.get('channels')
    if not isinstance(channels,list) or len(channels)!=c or any(not isinstance(x,str) or not x for x in channels) or len(set(channels))!=c:raise ValueError('Complete paper channel count and unique identities')
    if type(d.get('native_seed')) is not int or d['native_seed']!=e['seed']-1 or type(d.get('native_fold')) is not int:raise ValueError('Pinned actual source seed/fold mapping, not slot-as-RNG default')
    proof=d.get('provenance',{})
    required=('raw_recording','native_segment_producer','normalization','label_and_clock_audit','channel_and_atlas_join','split_indices','checkpoint_exposure')
    if set(proof)!=set(required) or any(not hexhash(proof[k]) for k in required):raise ValueError('Required upstream source audit identities')
    rows=d.get('rows');parts=d.get('partitions');support=validate_segments(rows,parts,force_nonoverlap=e['protocol']=='random_nonoverlap')
    if any(set(r)!={'id','start_sample','end_sample','neural'} for r in rows):raise ValueError('Exact normalized segment row schema')
    if len(rows)>200000:raise ValueError('Unqualified source support cap; never truncate')
    return support


def check_seed_support(d,e,seen):
    """Finetuning randomness may not change fixed source data/splits."""
    def identity(pin):return {k:pin[k] for k in ('bytes','sha256','shape','dtype')}
    signature={'recording':d['recording'],'native_fold':d['native_fold'],'channels':d['channels'],'spatial_ids':identity(d['spatial_ids']),'labels':identity(d['labels']),'partitions':d['partitions'],'rows':[dict(id=r['id'],start_sample=r['start_sample'],end_sample=r['end_sample'],neural=identity(r['neural'])) for r in d['rows']],'source_provenance':{k:v for k,v in d['provenance'].items() if k!='checkpoint_exposure'}}
    key=(e['protocol'],e['person'],e['task'],e['fold']);sha=digest(signature)
    if seen.setdefault(key,sha)!=sha:raise ValueError('Five finetuning seeds must use identical source rows, values, labels, spatial joins and partitions')
    return sha


def prepare(resolved_path,out_path,secret_path,max_output_bytes):
    resolved_path=ordinary(resolved_path);root=parse(capture(resolved_path,cap=32000000));expected=contexts()
    if root.get('schema')!='barista_resolved_panel_v1' or root.get('source_protocol_sha256')!=SOURCE_PROTOCOL_SHA or len(root.get('contexts',[]))!=len(expected):raise ValueError('All770 source contexts required')
    # Validate every metadata context/partition before opening neural arrays.
    seedmap={};foldmap={};support_by_case={}
    for rec,e in zip(root['contexts'],expected):
        if set(rec)!={'id','metadata'} or rec['id']!=e['id']:raise ValueError('Ordered complete source context descriptors')
        d=bound_json(resolved_path.parent,rec['metadata']);check_context(d,e,root['source_protocol_sha256']);check_seed_support(d,e,support_by_case)
        key=e['seed'];old=seedmap.setdefault(key,d['native_seed'])
        if old!=d['native_seed']:raise ValueError('Shared frozen five-seed mapping')
        key=(e['protocol'],e['fold']);old=foldmap.setdefault(key,d['native_fold'])
        if old!=d['native_fold']:raise ValueError('Shared frozen fold mapping')
    if len(set(seedmap.values()))!=5 or len({v for (p,f),v in foldmap.items() if p=='chronological'})!=5:raise ValueError('Five distinct source seeds/folds, no favorable repeats')
    secret=capture(secret_path,cap=32)
    if len(secret)!=32:raise ValueError('Exactly32 private blinding bytes')
    if type(max_output_bytes) is not int or max_output_bytes<=0:raise ValueError('Explicit future output allowance')
    out=fresh(out_path);out.mkdir();used=0;copied={};pool_contexts=[];public=[]
    def array(desc,shape,dtype=None):
        nonlocal used
        x=read_array(resolved_path.parent,desc,cap=CAP,shape=shape)
        if (dtype=='float' and x.dtype.kind!='f') or (dtype not in (None,'float') and x.dtype.str!=dtype):raise ValueError('Authentic normalized primitive dtype')
        if desc['sha256'] not in copied:
            if used+x.nbytes+4096>max_output_bytes:raise ValueError('Owned output allowance')
            pin=write_array(out/('a_'+desc['sha256']+'.npy'),x,cap=CAP);used+=pin['bytes'];copied[desc['sha256']]=pin
        return copied[desc['sha256']]
    for rec,e in zip(root['contexts'],expected):
        d=bound_json(resolved_path.parent,rec['metadata']);check_context(d,e,root['source_protocol_sha256']);c,p,l=COUNTS[e['person']]
        spatial=read_array(resolved_path.parent,d['spatial_ids'],shape=(c,5),cap=CAP)
        if spatial.dtype.str!='<i8' or (spatial<0).any() or (spatial[:,:3]>200).any() or len(np.unique(spatial[:,3]))!=p or len(np.unique(spatial[:,4]))!=l:raise ValueError('Complete coordinate/parcel/lobe source join')
        spatial_pin=array(d['spatial_ids'],(c,5),'<i8');labels=read_array(resolved_path.parent,d['labels'],shape=(len(d['rows']),),cap=CAP)
        if labels.dtype.str!='<i8' or not np.isin(labels,[0,1]).all():raise ValueError('Semantic binary source labels')
        label_pin=array(d['labels'],(len(labels),),'<i8');rows=[]
        for row in d['rows']:rows.append(dict(row,neural=array(row['neural'],(c,6144),'float')))
        query=[]
        for i in d['partitions']['query']:
            blind=hmac.new(secret,canonical([e['id'],d['rows'][i]['id']]),hashlib.sha256).hexdigest();query.append({'id':blind,'index':i})
        query.sort(key=lambda x:x['id']);qh=digest([r['id'] for r in query])
        item=dict(e,schema='barista_pool_context_v1',source_protocol_sha256=root['source_protocol_sha256'],channels=d['channels'],spatial_ids=spatial_pin,rows=rows,labels=label_pin,partitions=d['partitions'],query=query,query_ids_sha256=qh,native_seed=d['native_seed'],native_fold=d['native_fold'],provenance=d['provenance'])
        body=canonical(item)+b'\n'
        if used+len(body)>max_output_bytes:raise ValueError('Owned output allowance includes context metadata')
        name=e['id']+'.json';put(out/name,item);used+=len(body);pool_contexts.append({'id':e['id'],'metadata':{'path':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}})
        public.append(dict(e,query_count=len(query),query_ids_sha256=qh))
    pub={'schema':'barista_public_panel_v1','task_id':TASK_ID,'source_protocol_sha256':root['source_protocol_sha256'],'contexts':public,'generation_commitment':hmac.new(secret,canonical(root),hashlib.sha256).hexdigest()};pub['panel_id']=digest(pub)
    pool={'schema':'barista_private_pool_v1','public':pub,'contexts':pool_contexts,'native_seed_mapping':seedmap,'native_fold_mapping':{str(k):v for k,v in foldmap.items()},'provenance_verified':False,'scientific_execution':False};pool['pool_id']=digest(pool)
    final=sum(len(canonical(d))+1 for d in (pub,pool))
    if used+final>max_output_bytes:raise ValueError('Owned output allowance includes final metadata')
    put(out/'PUBLIC.json',pub);put(out/'POOL.json',pool)
    return {'prepared_contexts':770,'array_files':len(copied),'output_bytes':used+final,'panel_id':pub['panel_id'],'native_source_audit_verified':False,'models_or_scores_run':False}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--resolved',required=True);p.add_argument('--secret',required=True);p.add_argument('--out',required=True);p.add_argument('--max-output-bytes',type=int,required=True);a=p.parse_args();prepare(Path(a.resolved),Path(a.out),Path(a.secret),a.max_output_bytes)
