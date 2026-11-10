"""Fixed passive actor I/O; all arrays are admitted objects, never pickle."""
import hashlib,json,io,os
from pathlib import Path
from .catalog import need,canonical,identity

class ActorIO:
    def __init__(self,r):
        need(r['schema']=='reve-actor-request-v1' and r['mode']=='production','fixed actor needs selected production request')
        self.r=r;self.root=Path(r['input_root']);self.out=Path(r['output_root']);self.manifest={p['path']:p for p in r['input_manifest']};self.rows={};self.used=0;self.produced=[]
        need(len(self.manifest)==len(r['input_manifest']),'duplicate input object');need(self.root==Path('/input') and self.out==Path('/output'),'native protected mount ABI')
    def raw(self,name):
        need(name in self.manifest and '..' not in Path(name).parts and not Path(name).is_absolute(),'admitted relative input')
        p=self.root/name;need(p.is_file() and not p.is_symlink(),'regular input');b=p.read_bytes();pin=self.manifest[name]
        need(len(b)==pin['bytes'] and hashlib.sha256(b).hexdigest()==pin['sha256'],'actual input pin');return b
    def json(self,name):return json.loads(self.raw(name))
    def array(self,name):
        import numpy as np
        a=np.load(io.BytesIO(self.raw(name)),allow_pickle=False);need(a.dtype.kind in 'fiu' and np.isfinite(a).all(),'finite plain real array');return a
    def parent(self,name):
        need(name in self.r['parent_products'],'parent must be declared original product')
        d=self.json(hashlib.sha256(name.encode()).hexdigest()+'.json')
        need(d['schema']=='reve-produced-input-reference-v1' and d['identity']==self.r['parent_products'][name] and identity(d['product'])==d['identity'],'actual parent product identity')
        return d
    def parent_object(self,parent,pin):
        d=self.parent(parent);rows=[r for r in d['object_map'] if r['original']==pin];need(len(rows)==1,'unique parent object mapping');return rows[0]['materialized']
    def xft_parent(self,parent,calibrated):
        from .lineage import require_xft_parent
        return require_xft_parent(self.parent(parent),calibrated)
    def produced_view(self,parent):return ProducedView(self,parent)
    def write(self,name,b):
        need('..' not in Path(name).parts and not Path(name).is_absolute() and name not in self.rows,'new relative object')
        limit=self.r['resource_limits'];need(self.used+len(b)<=limit['output_bytes'] and len(self.rows)+1<=limit['output_files'],'actor output cap before writing')
        p=self.out/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(b)
        row={'path':name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()};self.rows[name]=row;self.used+=len(b);return row
    def write_array(self,name,a):
        import numpy as np
        b=io.BytesIO();a=np.asarray(a);need(a.dtype.kind in 'fiu' and np.isfinite(a).all(),'finite numerical output');np.save(b,a,allow_pickle=False);return self.write(name,b.getvalue())
    def write_state(self,name,tensors):
        from safetensors.torch import save
        return self.write(name,save({k:v.detach().cpu().contiguous() for k,v in tensors.items()}))
    def load_state(self,parent):
        from safetensors.torch import load
        d=self.parent(parent)['product'];need(d['kind']=='state' and d['details']['format']=='safetensors','passive state parent')
        out={}
        for row in d['details']['tensor_index']:
            x=load(self.raw(self.parent_object(parent,row['object'])));need(not set(out)&set(x),'duplicate tensors');out.update(x)
        return d['details'],out
    def emit(self,name,details,objects=()):
        s=self.r['expected_outputs'][name];row={'id':name,'kind':s['kind'],'objects':list(objects),'details':details,'source':self.r['source_id'],'request':identity(self.r),'parent_states':s['parent_states'],'objective_profile':s['objective_profile'],'exposure_context':self.r['context']};self.produced.append(row);return row
    def finish(self):
        need({x['id'] for x in self.produced}==set(self.r['expected_outputs']) and len(self.produced)==len(self.r['expected_outputs']),'all actual required products emitted')
        owned=[x['path'] for p in self.produced for x in p['objects']];need(len(owned)==len(set(owned)) and set(owned)==set(self.rows),'every output uniquely owned')
        self.write('products.json',canonical({'schema':'reve-process-product-index-v1','job_id':self.r['job_id'],'products':self.produced}))


class ProducedView:
    """Read only actually owned objects through the controller's parent map."""
    def __init__(self,io,parent):
        self.io=io;self.parent=parent;self.envelope=io.parent(parent)
        objects=self.envelope['product']['objects'];self.pins={x['path']:x for x in objects}
        need(len(self.pins)==len(objects),'unique parent-owned view objects')
    def path(self,name):
        need(name in self.pins,'view names an actual parent-owned object')
        return self.io.parent_object(self.parent,self.pins[name])
    def json(self,name):return self.io.json(self.path(name))
    def array(self,name):return self.io.array(self.path(name))

def data_view(vault,name,role,configuration):
    """Operator-signed support comes through the controller, not filenames or guesses."""
    m=vault.json(name);r=configuration['recipe'];required={'schema','role','dataset','sampling_hz','unit','signals','labels','events','people','positions','channel_ids','support','geometry_qualification'}
    need(set(m) in (required,required|{'source_dataset'},required|{'corpus_identity','normalization_qualification','pretraining_exclusion_qualification'}) and m['schema']=='reve-fixed-array-view-v1' and m['role']==role,'exact signal role manifest')
    if role=='pretrain':
        need(m['dataset']=='REVE-92-source-corpus' and m['sampling_hz']==200 and m['unit']=='session_zscore_clipped15','qualified full pretraining corpus projection')
        need(m.get('corpus_identity') and m.get('normalization_qualification') and m.get('pretraining_exclusion_qualification'),'actual92source corpus/statistic/exclusion qualification')
    else:need(m['dataset']==r['dataset'] and m['sampling_hz']==200 and m['unit']=='mV','physical input units/dataset')
    need(m['geometry_qualification']==configuration['geometry_qualification'],'qualified common Cartesian frame')
    need(bool(m['events']) and len(m['events'])==len(set(m['events'])) and m['support'],'exact event/support roster')
    need((m['labels'] is None)==(role in ('query','pretrain')),'query labels never enter predictor')
    x=vault.array(m['signals']);pos=vault.array(m['positions']);seq=1 if role=='pretrain' else r['sequence_length'];samples=2000 if role=='pretrain' else r['samples']
    need(x.ndim==(4 if seq==20 else 3) and x.shape[-1]==samples and (seq==1 or x.shape[1]==20),'complete epoch/20epoch sequence')
    need(len(m['events'])==len(x)*seq and len(m['people'])==len(x),'event and biological unit alignment')
    need(type(m['channel_ids'])is list and len(m['channel_ids'])==x.shape[-2] and len({str(k) for k in m['channel_ids']})==x.shape[-2],'complete unique channel identity order')
    need(pos.shape==(x.shape[-2],3) or (role=='pretrain' and pos.shape==(len(x),x.shape[-2],3)),'qualified whole-shard or per-window physical geometry')
    if 'channels' in configuration['ablation']:need(x.shape[-2]==configuration['ablation']['channels'],'exact sparse channel count and selected geometry')
    if role=='pretrain':
        import numpy as np
        need((np.abs(x)<=15).all(),'actual pretraining projection must obey declared clipping')
    y=None if m['labels'] is None else vault.array(m['labels'])
    if y is not None:
        import numpy as np
        need(y.shape==x.shape[:-2] and np.equal(y,np.floor(y)).all() and ((y>=0)&(y<r['classes'])).all(),'complete aligned labels')
    return m,x,pos,y
