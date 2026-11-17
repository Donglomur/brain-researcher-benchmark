"""Tiny real file-format/custody checks, inert Engine double, no native execution."""
from pathlib import Path
import ast,hashlib,importlib.abc,importlib.util,json,os,shutil,stat,sys,tempfile,tracemalloc,types
I=Path(__file__).resolve().parents[1];mp={'bytes':5990,'sha256':'321b9418d96c280f007972ff268c36113712fbd10791022710c78a9069e11bdc'}
b=(I/'RUNTIME_SOURCE_V2.json').read_bytes();assert len(b)==mp['bytes'] and hashlib.sha256(b).hexdigest()==mp['sha256'];manifest=json.loads(b)
bodies={};source_reads=len(b)
for name,row in manifest['files'].items():
 p=I/name;b=p.read_bytes();assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256'];source_reads+=len(b);bodies[Path(name).stem]=b
class Loader(importlib.abc.MetaPathFinder,importlib.abc.Loader):
 def find_spec(self,name,path=None,target=None):
  if name in bodies:return importlib.util.spec_from_loader(name,self)
 def create_module(self,spec):return None
 def exec_module(self,m):exec(compile(bodies[m.__name__],m.__name__+'.py','exec'),m.__dict__)
sys.meta_path.insert(0,Loader())
import core,bundle,runtime
DUMPS=json.dumps;WRITE=os.write;json_bytes=0;write_bytes=0;calls=0;events=[];passed=[];retained=0
tracemalloc.start()
def dumps(*a,**k):
 global json_bytes,calls
 assert json_bytes+65536<=1<<20
 s=DUMPS(*a,**k);n=len(s.encode());assert n<=65536;json_bytes+=n;calls+=1;return s
json.dumps=dumps
def write(fd,data):
 global write_bytes
 assert write_bytes+len(data)<=262144
 n=WRITE(fd,data);write_bytes+=n;return n
os.write=write
class Clock:
 origin=1.;deadline=1000.;read_bytes=0;write_bytes=0
 def tick(self,cutoff=None):assert self.origin<2.<min(self.deadline,cutoff or self.deadline);return 2.
 def reserve_read(self,n):self.read_bytes+=n;assert self.read_bytes<=8<<20
 def reserve_write(self,n):self.write_bytes+=n;assert self.write_bytes<=8<<20
 def record(self):return {'read':self.read_bytes,'write':self.write_bytes}
limits={'members':8,'member_bytes':4096,'metadata_bytes':8192,'bundle_bytes':32768}
base=Path(tempfile.mkdtemp(prefix='transport-v2-',dir=I/'controls')).resolve()
def retained_check(*values):
 global retained
 # All retained control values are bounded metadata; no arrays/model bodies.
 n=sum(len(json.dumps(x,sort_keys=True).encode()) for x in values);retained=max(retained,n)
 assert retained<=524288 and tracemalloc.get_traced_memory()[1]<=8388608

def refuses(fn,text):
 try:fn()
 except Exception as e:assert text in str(e),(text,type(e).__name__,str(e));return
 raise AssertionError('expected '+text)
try:
 c=Clock();source=core.fresh(base/'first',c)
 a=core.publish(source/'RESULT.json',core.encoded({'invented':'complete','value':7}),c,readonly=True)
 inner=core.fresh(source/'nested',c);core.publish(inner/'STATE.json',core.encoded({'safe':True}),c,readonly=True)
 bp=bundle.pack(source,base/'result.n058',c,limits)
 decoded=bundle.unpack(base/'result.n058',bp,base/'decoded',c,limits)
 assert [r['path'] for r in decoded['members']]==['RESULT.json','nested/STATE.json']
 assert (base/'decoded/RESULT.json').read_bytes()==core.encoded({'invented':'complete','value':7})
 retained_check(decoded);passed.append('real uncompressed complete metadata bundle roundtrip')
 bad=(base/'result.n058').read_bytes()+b'x';badpin=core.publish(base/'bad.n058',bad,c,readonly=True)
 refuses(lambda:bundle.unpack(base/'bad.n058',badpin,base/'bad-dest',c,limits),'trailing payload')
 assert not (base/'bad-dest').exists();passed.append('trailing bundle refused before derived namespace')
 class Engine:
  def __init__(self,bad=False):self.bad=bad;self.calls=0
  def execute(self,operation,argv,mounts,output,profile,cutoff,sourcepin,expected):
   self.calls+=1
   assert argv[0]=='/qualified/python' and argv[argv.index('--mode')+1]=='native' and set(expected)=={'RESULT.n058','TERMINAL.json'}
   request=next(r for r in mounts if r['destination']=='/inputs/request.json')
   raw=Path(request['source']).read_bytes();assert core.pin(raw)==request['pin'];envelope=core.parse(raw)
   result={'task':'NEURAL-058','request':core.pin(core.encoded(envelope['request'])),'invented_result':True}
   product=core.fresh(base/('producer-'+str(self.calls)+'-'+str(self.bad)),c)
   rp=core.publish(product/'RESULT.json',core.encoded(result),c,readonly=True)
   archive=bundle.pack(product,output/'RESULT.n058',c,limits)
   terminal={'schema':'neural058_native_terminal_v1','task':'NEURAL-058','request':request['pin'] if not self.bad else {'bytes':1,'sha256':'0'*64},
             'producer':envelope['producer'],'source':sourcepin,'bundle':archive,'result':{'path':'RESULT.json','pin':rp}}
   tp=core.publish(output/'TERMINAL.json',core.encoded(terminal),c,readonly=True)
   return {'artifacts':{'RESULT.n058':archive,'TERMINAL.json':tp}}
 def selection(out):
  roots={k:str(base/('protected-'+k)) for k in ('source','prepared','private','original','observation','operator','secrets')};roots['output']=str(out)
  roots['source']=str(I)
  return {'roots':roots,'source_manifest_path':str(I/'RUNTIME_SOURCE_V2.json'),'native_python':'/qualified/python','bundle_limits':limits}
 profile={'worker_read_bytes':1024,'worker_write_bytes':1024,'retirement_seconds':1.,'readback_seconds':1.}
 out=core.fresh(base/'runtime',c);sel=selection(out);engine=Engine();r=runtime.Runtime(sel,{'pin':mp,'manifest':manifest},c,engine,events.append,None)
 result=r.run('invented-operation','reference',{'output_root':'/scratch/result','limits':{'metadata_bytes':4096}},[],5.,profile)
 assert result['status']=='complete' and result['result']['invented_result'] and engine.calls==1
 assert events[-1]['kind']=='task_product' and result['request']==result['terminal']['request'];retained_check(result,events)
 passed.append('actual Runtime request/terminal/bundle/result joins with disclosed inert Engine')
 out2=core.fresh(base/'runtime-bad',c);badengine=Engine(True);r2=runtime.Runtime(selection(out2),{'pin':mp,'manifest':manifest},c,badengine,events.append,None)
 refuses(lambda:r2.run('invented-bad','reference',{'output_root':'/scratch/result','limits':{'metadata_bytes':4096}},[],5.,profile),'terminal request/source producer')
 assert r2.results['invented-bad']['status']=='failed' and badengine.calls==1
 passed.append('wrong returned terminal request fails with retained attempt')
 summary={'status':'pass','groups':passed,'manifest':mp,'source_reads':source_reads,'canonical_before_summary':json_bytes,'json_calls_before_summary':calls,
          'physical_fixture_writes':write_bytes,'retained_encoded_projection_max':retained,'trace_peak_after_imports':tracemalloc.get_traced_memory()[1],
          'conservative_fixture_charge':3145728,'actual_native_provider_model_or_scoring_calls':0}
 print(json.dumps(summary,sort_keys=True),flush=True)
except BaseException as e:
 print(json.dumps({'status':'failed','passes':passed,'error_type':type(e).__name__,'error':str(e)[:500],'canonical_before_summary':json_bytes,
                   'physical_writes':write_bytes,'trace_peak':tracemalloc.get_traced_memory()[1],'reserved_fixture_charge':3145728}),flush=True)
 raise
finally:
 os.write=WRITE;json.dumps=DUMPS
 # Only this freshly created, known-owned tiny fixture directory is retired.
 shutil.rmtree(base)
