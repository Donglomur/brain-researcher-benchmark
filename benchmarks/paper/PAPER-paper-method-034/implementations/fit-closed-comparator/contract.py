"""Fixed MARBLE comparator contract. Source-only; no data/model work on import."""
import hashlib,json,math,os,stat
from pathlib import Path
METHODS=('marble','cebra-time','cebra-behavior')
RATS=('achilles','buddy','cicero','gatsby')
CONDITIONS=('clean','half')
DIMS=(3,32)
PROTOCOL='rat-four-animal-chronological-80-20-clean-even-neurons-v1'
def need(ok,message):
    if not ok:raise ValueError(message)
def encode(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def parse(raw):
    def pairs(rows):
        out={}
        for k,v in rows:need(k not in out,'duplicate JSON key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite JSON'))
def coordinate(method,condition,rat,dimension):
    need(method in METHODS and condition in CONDITIONS and rat in RATS and type(dimension)is int and dimension in DIMS,'complete fixed coordinate')
    return {'method':method,'condition':condition,'rat':rat,'dimension':dimension}
def key(c):return f"{c['method']}--{c['condition']}--{c['rat']}--d{c['dimension']}"
def schedule(spec):
    need(spec['protocol_id']==PROTOCOL and tuple(x['rat']for x in spec['rats'])==RATS and tuple(spec['conditions'])==CONDITIONS and tuple(spec['embedding_dimensions'])==DIMS,'fixed full protocol')
    return [coordinate(m,c,r,d)for m in METHODS for c in CONDITIONS for r in RATS for d in DIMS]
def recipe(c):
    d=c['dimension']
    if c['method']=='marble':
        return {'epochs':100,'order':1,'hidden_channels':[64],'out_channels':d,'inner_product_features':False,'emb_norm':True,'diffusion':False,'include_positions':True,'seed':0}
    behavior=c['method']=='cebra-behavior'
    return {'model_architecture':'offset10-model','batch_size':512,'learning_rate':3e-4,'temperature':1 if behavior else 1.12,'output_dimension':d,'max_iterations':10000 if d==32 else 15000,'distance':'cosine','conditional':'time_delta'if behavior else'time','device':'cuda_if_available','verbose':True,'time_offsets':10}
def filename(c,phase):
    return f"{c['condition']}-{c['rat']}-{'train'if phase=='fit'else'test'}-d{c['dimension']}.npy"
def ordinary(path):
    p=Path(path).absolute()
    need('..'not in p.parts and all(not x.is_symlink()for x in(p,*p.parents)),'ordinary path')
    return p
class Budget:
    """Logical adapter I/O; native/OS and allocator costs remain separate."""
    def __init__(self,reads,writes):
        need(type(reads)is type(writes)is int and reads>0 and writes>0,'explicit logical caps')
        self.read_cap=reads;self.write_cap=writes;self.reads=0;self.writes=0
    def charge(self,kind,n):
        need(type(n)is int and n>=0,'integer extent')
        attr='reads'if kind=='read'else'writes';cap=self.read_cap if kind=='read'else self.write_cap
        need(getattr(self,attr)+n<=cap,'logical '+kind+' reservation exhausted')
        setattr(self,attr,getattr(self,attr)+n)
    def read(self,path,cap,expected=None):
        self.charge('read',cap+1);p=ordinary(path);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            a=os.fstat(fd);need(stat.S_ISREG(a.st_mode)and a.st_nlink==1 and a.st_size<=cap,'bounded ordinary body')
            with os.fdopen(fd,'rb',closefd=False)as f:raw=f.read(cap+1)
            b=os.fstat(fd);n=p.lstat();fields=('st_dev','st_ino','st_size','st_nlink','st_mtime_ns','st_ctime_ns')
            need(len(raw)==a.st_size and all(getattr(a,k)==getattr(b,k)==getattr(n,k)for k in fields),'stable body')
            need(expected is None or pin(raw)==expected,'exact body pin')
            return raw
        finally:os.close(fd)
    def write(self,path,raw):
        self.charge('write',len(raw));p=ordinary(path)
        with p.open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
        return pin(raw)
def job_check(job,phase):
    need(set(job)=={'schema','coordinate','phase','protocol','source','input','input_shape','labels','closure','limits'},'exact job')
    need(job['schema']=='marble_closed_comparator_job_v1' and job['phase']==phase and phase in('fit','query'),'phase job')
    c=job['coordinate'];need(c==coordinate(**c),'coordinate')
    need(job['protocol']['id']==PROTOCOL,'protocol identity')
    shape=job['input_shape'];need(type(shape)is list and len(shape)==2 and all(type(v)is int and v>1 for v in shape),'complete input shape')
    need((job['labels']is not None)==(phase=='fit'and c['method']=='cebra-behavior'),'training label privilege only')
    need((job['closure']is None)==(phase=='fit'),'fit closure before query')
    need(set(job['limits'])=={'read_bytes','write_bytes','model_member_bytes','state_metadata_bytes','rng_member_bytes'},'explicit worker limits')
    for v in job['limits'].values():need(type(v)is int and v>0,'positive worker bound')
    return c

def closed_observation(value):
    need(value.get('success')is True and all(value.get(x)is True for x in('all_owned_absent','all_clients_closed','producer_natural_exit','producer_removed'))and value.get('producer_exit_code')==0 and value.get('producer_oom_killed')is False and value.get('producer_timed_out')is False,'natural complete actual phase closure')


def budgeted_capture_at(budget,directory_fd,name,limit):
    need(type(name)is str and Path(name).name==name and name not in('','.','..'),'flat capture member')
    fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory_fd)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size<=limit,'bounded ordinary interface body')
        size=before.st_size;budget.charge('read',size+1)
        with os.fdopen(fd,'rb',closefd=False)as f:raw=f.read(size+1)
        after=os.fstat(fd);named=os.stat(name,dir_fd=directory_fd,follow_symlinks=False)
        fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')
        need(len(raw)==size and all(getattr(before,k)==getattr(after,k)==getattr(named,k)for k in fields),'same bounded interface capture')
        return raw,hashlib.sha256(raw).hexdigest()
    finally:os.close(fd)
