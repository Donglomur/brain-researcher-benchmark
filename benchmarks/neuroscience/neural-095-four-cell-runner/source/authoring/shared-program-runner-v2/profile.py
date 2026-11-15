"""Trusted profile loader; currently only the sevenfold NEURAL034 adapter."""
from pathlib import Path
import hashlib,json,re
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]


def need(ok,text):
    if not ok:raise ValueError(text)


def unique(pairs):
    value={}
    for k,v in pairs:need(k not in value,'Duplicate JSON key');value[k]=v
    return value


def decode(body):return json.loads(body,object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in()).throw(ValueError('Nonfinite JSON')))


def source_path(relative):
    need(type(relative)is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/+-]*',relative)is not None,'Literal repository path')
    p=ROOT/relative;need('..'not in Path(relative).parts and all(not q.is_symlink()for q in(p,*p.parents)),'No traversal or linked source');return p


def load(task='NEURAL-034'):
    need(task=='NEURAL-034','Only reviewed glial profile is implemented')
    p=HERE/'profiles'/(task+'.json');v=decode(p.read_bytes())
    need(v['id']==task and v['operator_only_profile']is True,'Exact profile')
    units=v['schedule']['units'];need(len(units)==7,'Seven fixed units')
    for i,unit in enumerate(units):
        need(unit['unit_id']==f'fold-{i:02d}'and unit['expected_query_count']==20 and len(unit['public_inputs'])==1,'Fixed unit order/support')
        asset=unit['public_inputs'][0];source_path(asset['path'])
        need(asset['mount_destination']=='/input/public.npz'and asset['read_only']is True and type(asset['bytes'])is int and asset['bytes']==4371604 and re.fullmatch('[a-f0-9]{64}',asset['sha256'])is not None,'Exact bounded public fold pin')
        need(asset['path']==f'artifacts-build/glial-context-002/fold-{i:02d}/public.npz','One matching fold only')
        need(unit['output_filename']=='probabilities.json'and unit['max_output_bytes']==100000,'Fixed output cap')
    public=ROOT/'benchmarks/neuroscience/neural-034/public/cases.json'
    need(hashlib.sha256(public.read_bytes()).hexdigest()=='0434344482bf833d27cd1c385daea0449032e6c62920557ffa2b7c665294e0c2','Frozen public panel')
    rows=decode(public.read_bytes())['cases'];need(len(rows)==140 and len({(x['fold'],x['query_id'])for x in rows})==140,'Complete unique public cases')
    for i,unit in enumerate(units):
        ids=[x['query_id']for x in rows if x['fold']==i]
        need(len(ids)==20 and all(type(x)is str and re.fullmatch('[a-f0-9]{24}',x)is not None for x in ids),'Fixed opaque query IDs')
        unit['expected_ids']=ids;unit['fold']=i
    return v


def runtime(unit):return {'public_destinations':tuple(x['mount_destination']for x in unit['public_inputs']),'output_name':unit['output_filename'],'max_output_bytes':unit['max_output_bytes']}
