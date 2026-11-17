"""Changed full54 orchestration in RAM; no files, arrays, model fit or native run."""
import ast,hashlib,json,types
from pathlib import Path,PurePosixPath
HERE=Path(__file__).absolute().parent
CAP=2097152 # prospective transferred remainder; separate full-join charge retained
charged=0

def size(v):
 if v is None:return 4
 if type(v)is bool:return 4 if v else 5
 if type(v)is int:return len(str(v))
 if type(v)is str:return 2+sum(2 if ch in '\\"\b\f\n\r\t' else 6 if ord(ch)<32 or 127<=ord(ch)<=65535 else 12 if ord(ch)>65535 else 1 for ch in v)
 if type(v)in(list,tuple):return 2+sum(map(size,v))+max(0,len(v)-1)
 if type(v)is dict:return 2+sum(size(k)+1+size(x) for k,x in v.items())+max(0,len(v)-1)
 raise TypeError('fixture type')
def enc(v):
 global charged
 n=size(v)+1
 if charged+n>CAP:raise RuntimeError('preventive cumulative canonical allowance')
 charged+=n;b=(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii');assert len(b)==n;return b
def pin(b):return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def need(v,m):
 if not v:raise ValueError(m)

def run_case(fail=False):
 files={};dirs={'/ram'};events=[];calls=[];verifies=[];models=[];retired=[]
 class P(PurePosixPath):
  def mkdir(self,**kw):need(not self.exists(),'fresh');dirs.add(str(self))
  def exists(self):return str(self)in dirs or str(self)in files
  def is_dir(self):return str(self)in dirs
  def lstat(self):need(self.exists(),'existing');return (str(self),files.get(str(self)))
 def save(p,b,cap,*args):need(type(b)is bytes and 0<len(b)<=cap and str(p)not in files,'exclusive body');files[str(p)]=b;events.append(('save',str(p)));return pin(b)
 def capture(p,cap,expected=None,*a):
  b=files[str(p)];need(len(b)<=cap and (expected is None or pin(b)==expected),'same captured bytes');return b
 class Budget:
  def __init__(self,root,*a):self.root=root;self.limits={};self.reads=0;self.phases=[]
  def tick(self):pass
  def capacity(self,*a):pass
  def write(self,n):pass
  def read(self,n):self.reads+=n
  def native(self,k,i):self.phases.append((k,i))
  def record(self):return dict(reads=self.reads,phases=self.phases)
 c=types.SimpleNamespace(path=P,need=need,Budget=Budget,sync_dir=lambda *a:None,capture=capture,save=save,pin=pin,parse=json.loads,encoded=enc,only_pin=lambda d:{k:d[k] for k in ('bytes','sha256')},readable=lambda *a:None,stamp=lambda v:(1,2,3,1,len(v[1]),4,5,6,7))
 program=b'pass\n';source=pin(b'source');files['/source/program.py']=program;files['/repo/score.py']=program
 s=dict(output='/ram/out',repository='/repo',other_future_bytes=0,program=dict(path='/source/program.py',**pin(program)),pool=dict(path='/canonical/pool.json',**pin(b'pool')),preparation=pin(b'prep'),plan=dict(canonical_total_bytes=350000000),limits=dict(whole_seconds=1000,observer_seconds=10))
 class Store:
  def load(self,s,b):need('/ram/out/COMMITMENT.json'in files,'commit before canonical labels');return dict(canonical_bytes=350000000)
  def stage(self,canonical,p,k,current,b,training=None):
   need(not current.exists(),'only one view');need(not any(x.endswith('/model.bin') for x in files) if k=='fit' else True,'no prior-fold model accumulation')
   if k=='query':need('/ram/out/phases/fold%03d/TRAIN_RETIRED.json'%p in files,'durable training retirement before queries')
   current.mkdir();names=('train.json','training.json','training.npy') if k=='fit' else ('fold.json','queries.npy')
   expected={n:save(current/n,b'x',10) for n in names};events.append(('stage',p,k))
   return expected,dict(fold='fold%03d'%p)
  def verify(self,current,expected,b):
   need(set(x.rsplit('/',1)[1] for x in files if x.startswith(str(current)+'/'))==set(expected),'exact split mounts');verifies.append(1);return len(verifies)
  def retire(self,current,expected,stamp,b):
   need(stamp==len(verifies),'last validation before retirement')
   for n in expected:del files[str(current/n)]
   dirs.remove(str(current));events.append(('retire',len(verifies)))
  def seal_model(self,old,new,pin,b):
   need(str(new)not in files and capture(old,100,pin)==b'opaque','one source model');files[str(new)]=files.pop(str(old));models.append(str(new));return c.stamp(new.lstat())
  def retire_model(self,p,pin,stamp,b):
   need(c.stamp(p.lstat())==stamp,'same sealed model');need(str(p.parent/'QUERY_RETIRED.json')in files,'query retired before model')
   if fail and 'fold054' in str(p):raise ValueError('invented final retirement failure')
   del files[str(p)];retired.append(str(p))
  def unchanged(self,*a):pass
 store=Store()
 def phase(s,trusted,current,program,model,attempt,kind,i,source,b,end):
  calls.append((kind,i));names={x.rsplit('/',1)[1] for x in files if x.startswith(str(current)+'/')}
  need(names==({'train.json','training.json','training.npy'} if kind=='fit' else {'fold.json','queries.npy'}),'no held features during fit or training labels during infer')
  need((model is not None)==(kind=='infer'),'sealed model only to candidate inference')
  if kind=='infer':need(model.exists() and str(model.parent/'TRAIN_RETIRED.json')in files,'seal and durable train retirement')
  need('/canonical' not in str(current),'canonical backing never mounted')
  body=b'opaque' if kind=='fit' else enc(dict(fold='fold%03d'%(i+1),kind=kind))
  out=save(attempt/('model.bin' if kind=='fit' else 'predictions.json'),body,262144)
  save(attempt/'NATIVE.json',enc(dict(invented=True)),262144)
  return dict(status='captured',all_native_resources_closed=True,output=out)
 bodies={n:program for n in ('holder.py','candidate_entry.py','reference_program.py')};bodies['BINDING.json']=enc(dict(sources={'score.py':dict(path='score.py',**pin(program))}))
 raw=(HERE/'program/controller.py').read_bytes();tree=ast.parse(raw)
 ns=dict(c=c,store=store,contracts=types.SimpleNamespace(prediction=lambda raw,fold:need(json.loads(raw)['fold']==fold['fold'],'exact fold')),policy=types.SimpleNamespace(MODES=('candidate','cca','constant','frequency-permuted'),reviews=lambda *a:None),native=types.SimpleNamespace(phase=phase),os=types.SimpleNamespace(path=types.SimpleNamespace(lexists=lambda p:P(p).exists()),chmod=lambda *a:None))
 exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'actual_controller.py','exec'),ns)
 try:result=ns['run'](s,source,bodies,0,990)
 except ValueError:
  if not fail:raise
  need('/ram/out/COMPLETE.json'not in files and '/ram/out/submission.json'not in files and '/ram/out/FAILURE.json'in files,'late retirement refuses terminal');need('/ram/out/phases/fold054/model.bin'in files,'failed owned model retained')
 else:
  need(not fail and result['query_count']==21600,'whole query result')
  need(calls==[(k,i) for i in range(54) for k in ('fit','infer','cca','constant','frequency-permuted')],'all270 native phases')
  need(models==retired and len(models)==54 and not any(x.endswith('/model.bin') for x in files),'all models retired')
  need(not P('/ram/out/current').exists(),'no retained split')
  need(len([x for x in files if x.startswith('/ram/out/predictions/')])==216,'all216 scorer files')
  done=json.loads(files['/ram/out/COMPLETE.json']);need(done['labels_opened_for_trusted_staging']is True and done['canonical_store_or_private_gold_candidate_mounted']is False and done['private_scoring_performed']is False,'truthful access flags')
 retained=sum(map(len,files.values()));need(retained<3145728,'retained canonical RAM fixture cap')
 return dict(case='late_retirement' if fail else 'full54',phases=len(calls),retained_bytes=retained)
if __name__=='__main__':
 rows=[run_case(),run_case(True)];print(json.dumps(dict(groups=2,results=rows,canonical_precharged_bytes=charged,physical_fixture_writes=0,actual_model_or_native_runs=0),sort_keys=True))
