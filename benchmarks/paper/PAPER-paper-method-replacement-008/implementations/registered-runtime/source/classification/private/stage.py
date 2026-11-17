"""One candidate information context; this does not enforce process/network isolation."""
import sys,hashlib,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from io_contract import capture,parse,put,fresh
from arrays import read_array,write_array
from protocol import digest,canonical
from design import validate_public,ARMS,MODELS,SOURCE_PROTOCOL_SHA
from prepare import bound_json,COUNTS,CAP

PUBLIC=('TASK.md','SUBMISSION.schema.json','arrays.py','io_contract.py','protocol.py','requirements.txt')

def source_root():
    root=Path(__file__).resolve().parents[1]
    return root/'source' if (root/'source').is_dir() else Path(__file__).parent/'source'


OFFICIAL_DESCRIPTOR_SHA256 = 'f8079f38e014f0254564a3bad94192b0ba8dc0a3ae0ee6f4fb642b15151fd2a6'


def approved_paper(paper_path):
    if paper_path is None:raise ValueError('Explicit operator paper path is required')
    protocol_body=capture(source_root()/'PROTOCOL.json')
    if hashlib.sha256(protocol_body).hexdigest()!=SOURCE_PROTOCOL_SHA:raise ValueError('Source protocol identity')
    protocol=parse(protocol_body);paper=capture(Path(paper_path),cap=3000000)
    if hashlib.sha256(paper).hexdigest()!=protocol['paper_sha256']:raise ValueError('Paper identity')
    return paper


def approved_sources(arm, *, official_source_root=None, paper_path=None):
    if arm not in ARMS:raise ValueError('Frozen information condition')
    # A branches before any official descriptor/source-root/notice access.
    selected=[('paper.html',approved_paper(paper_path))]
    if arm=='paper_and_data':return selected
    from source_provision import official_sources_for_arm
    src=source_root()
    official=official_sources_for_arm(arm, bundled_source_root=src,
        operator_root=official_source_root,
        descriptor_path=src/'OFFICIAL_SOURCE_ACCESS.json',
        expected_sha256=OFFICIAL_DESCRIPTOR_SHA256)
    return selected+[('official/'+name,body) for name,body in official]


def stage(pool_path,context_id,model,arm,out_path,max_output_bytes, *, official_source_root=None, paper_path=None):
    pool=parse(capture(pool_path,cap=32000000));pub=validate_public(pool['public'])
    if pool.get('pool_id')!=digest({k:v for k,v in pool.items() if k!='pool_id'}):raise ValueError('Private pool identity')
    if arm not in ARMS or model not in MODELS+('improved',):raise ValueError('Frozen information/model condition')
    if [x['id'] for x in pool['contexts']]!=[x['id'] for x in pub['contexts']]:raise ValueError('Complete private pool support')
    idx=next((i for i,x in enumerate(pub['contexts']) if x['id']==context_id),None)
    if idx is None:raise ValueError('Unknown required context')
    e=pub['contexts'][idx]
    if model=='improved' and e['protocol']!='chronological':raise ValueError('Improvement only on frozen chronological support')
    source_assets=approved_sources(arm,official_source_root=official_source_root,paper_path=paper_path) # Refuse missing official assets before creating output.
    d=bound_json(Path(pool_path).parent,pool['contexts'][idx]['metadata']);c=COUNTS[e['person']][0]
    if d.get('id')!=context_id or d.get('source_protocol_sha256')!=SOURCE_PROTOCOL_SHA or d.get('query_ids_sha256')!=e['query_ids_sha256']:raise ValueError('Bound single-context pool')
    if type(max_output_bytes) is not int or max_output_bytes<=0:raise ValueError('Explicit future output allowance')
    labels=read_array(Path(pool_path).parent,d['labels'],shape=(len(d['rows']),),cap=CAP)
    out=fresh(out_path);out.mkdir();used=0;copied={}
    def array(desc,shape):
        nonlocal used
        x=read_array(Path(pool_path).parent,desc,shape=shape,cap=CAP)
        # Output names contain no upstream content hash or original source index.
        if desc['sha256'] not in copied:
            if used+x.nbytes+4096>max_output_bytes:raise ValueError('Owned output cap')
            pin=write_array(out/f'input_{len(copied):06d}.npy',x,cap=CAP);used+=pin['bytes'];copied[desc['sha256']]=pin
        return copied[desc['sha256']]
    view={'schema':'barista_candidate_view_v1','task_id':pub['task_id'],'panel_id':pub['panel_id'],'context_id':context_id,'arm':arm,'model':model,'native_seed':d['native_seed'],'native_fold':d['native_fold'],'channels':d['channels'],'spatial_ids':array(d['spatial_ids'],(c,5)),'query_ids_sha256':e['query_ids_sha256'],'train':[],'validation':[],'query':[],'isolation_verified':False,'checkpoint_assets_supplied':False}
    for part in ('train','validation'):
        for i in d['partitions'][part]:view[part].append({'neural':array(d['rows'][i]['neural'],(c,6144)),'label':int(labels[i])})
    for q in d['query']:view['query'].append({'id':q['id'],'neural':array(d['rows'][q['index']]['neural'],(c,6144))})
    if digest([x['id'] for x in view['query']])!=e['query_ids_sha256'] or len(view['query'])!=e['query_count']:raise ValueError('Exact candidate query roster')
    for name in PUBLIC:source_assets.append((name,capture(Path(__file__).resolve().parents[1]/'public'/name)))
    for name,body in source_assets:
        if used+len(body)>max_output_bytes:raise ValueError('Owned output cap includes source')
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(body)
        used+=len(body)
    if used+len(canonical(view))+1>max_output_bytes:raise ValueError('Owned output cap includes view metadata')
    put(out/'VIEW.json',view);return view

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--pool',required=True);p.add_argument('--context',required=True);p.add_argument('--model',required=True);p.add_argument('--arm',required=True);p.add_argument('--out',required=True);p.add_argument('--max-output-bytes',required=True,type=int);p.add_argument('--official-source-root');p.add_argument('--paper',required=True);a=p.parse_args();stage(Path(a.pool),a.context,a.model,a.arm,Path(a.out),a.max_output_bytes,official_source_root=a.official_source_root,paper_path=a.paper)
