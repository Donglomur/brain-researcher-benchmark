"""Bounded invented controls only. No scientific/native/provider/child operations."""
from pathlib import Path
import ast,contextlib,gc,hashlib,importlib.abc,importlib.util,json,os,stat,sys,time,tracemalloc,types
import numpy as np
I=Path(__file__).resolve().parents[1]
EXPECTED={'bytes':5699,'sha256':'dc4f4873bc9ceae6ac37cc16571cf61e2570b4425ebb7bdd4d7b7be7cddde6ff'}
raw=(I/'RUNTIME_SOURCE_V1.json').read_bytes()
assert len(raw)==EXPECTED['bytes'] and hashlib.sha256(raw).hexdigest()==EXPECTED['sha256']
manifest=json.loads(raw);bodies={};source_reads=len(raw)
for name,d in manifest['files'].items():
 p=I/name;fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  a=os.fstat(fd);assert stat.S_ISREG(a.st_mode) and a.st_nlink==1
  b=os.read(fd,d['bytes']+1);z=os.fstat(fd);q=os.stat(p,follow_symlinks=False)
  stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
  assert stamp(a)==stamp(z)==stamp(q) and len(b)==d['bytes'] and hashlib.sha256(b).hexdigest()==d['sha256']
 finally:os.close(fd)
 source_reads+=len(b);bodies[Path(name).stem]=b
class Loader(importlib.abc.MetaPathFinder,importlib.abc.Loader):
 def find_spec(self,fullname,path=None,target=None):
  if fullname in bodies:return importlib.util.spec_from_loader(fullname,self)
 def create_module(self,spec):return None
 def exec_module(self,m):exec(compile(bodies[m.__name__],m.__name__+'.py','exec'),m.__dict__)
sys.meta_path.insert(0,Loader())
import core,contracts,schedule,features,scores,reference_models,numeric_recipe,native_reader,preparation,provider,panel_budget,arrays,state_io,native_contract,authors,grading
# Import-time source only; numerical training below is tiny invented NumPy ridge.
DUMPS=json.dumps;encoded_total=0;encoding_calls=0;raw_observed=0;max_retained=0
CAP=6<<20;CALL=256<<10
tracemalloc.start()
def dumps(*a,**k):
 global encoded_total,encoding_calls
 assert encoded_total+CALL<=CAP,'prospective bounded canonical allowance'
 s=DUMPS(*a,**k);n=len(s.encode());assert n<=CALL,'single known small fixture encoding'
 encoded_total+=n;encoding_calls+=1;return s
json.dumps=dumps
# Every runtime json.dumps/pin call shares this interceptor. 4MiB additional
# raw/nonserialized scaffold and2MiB headroom are reserved within the12MiB batch.
def observed(x):
 global raw_observed
 raw_observed+=x.nbytes if isinstance(x,np.ndarray) else len(x)
 assert raw_observed<=4<<20
 return x

def retained(*objs):
 global max_retained
 seen=set()
 def size(x):
  if id(x) in seen:return 0
  seen.add(id(x))
  if isinstance(x,np.ndarray):return x.nbytes
  if isinstance(x,bytes):return len(x)
  if isinstance(x,str):return len(x.encode())
  if isinstance(x,dict):return sum(size(k)+size(v) for k,v in x.items())
  if isinstance(x,(list,tuple)):return sum(size(v) for v in x)
  return 16
 n=sum(size(x) for x in objs);max_retained=max(max_retained,n);assert n<=3<<20
 assert tracemalloc.get_traced_memory()[1]<=32<<20
 return n
@contextlib.contextmanager
def patch(obj,**changes):
 old={k:getattr(obj,k) for k in changes}
 for k,v in changes.items():setattr(obj,k,v)
 try:yield
 finally:
  for k,v in old.items():setattr(obj,k,v)
def refuses(fn,word):
 try:fn()
 except Exception as e:
  assert word in str(e),(type(e).__name__,str(e),word);return
 raise AssertionError('expected refusal '+word)
class Clock:
 def __init__(self):self.origin=1.;self.deadline=1000.;self.now=2.;self.read_bytes=self.write_bytes=0
 def tick(self,cutoff=None):
  assert self.origin<=self.now<min(self.deadline,cutoff or self.deadline),'clock'
  return self.now
 def reserve_read(self,n):self.tick();self.read_bytes+=n
 def reserve_write(self,n):self.tick();self.write_bytes+=n
 def record(self):return {'read_bytes':self.read_bytes,'write_bytes':self.write_bytes}
passed=[]
def group(name,fn):
 try:
  fn();gc.collect();retained();passed.append(name)
 except BaseException as error:
  print(json.dumps({'status':'failed','group':name,'previous_passes':passed,'error_type':type(error).__name__,'error':str(error)[:800],
                   'canonical_before_failure_summary':encoded_total,'known_raw_bytes':raw_observed,'retained_projection_max':max_retained,
                   'traced_peak_after_imports':tracemalloc.get_traced_memory()[1],'source_read_bytes':source_reads,'reserved_fixture_charge':12<<20}),flush=True)
  raise

def full_schedule():
 source={f's{i}':{'animal':f'a{i%126}'} for i in range(423)}
 evaluation={f'e{i}':{'animal':f'b{i%13}'} for i in range(29)}
 roster={'source':source,'evaluation':evaluation,'source_animals':[f'a{i}' for i in range(126)],
         'eval_animals':[f'b{i}' for i in range(13)],'folds':{f'a{i}':i%5 for i in range(126)}}
 assert schedule.required_counts(roster)=={'candidate_panels':24,'author_contexts':168,'candidate_session_predictions':696,'reference_selection_fits':160}
 choices={r+'/'+f+'/'+h:f+'-0' for r in ('C','J') for f in ('ridge','forest','set') for h in ('velocity','speed')}
 assert schedule.required_counts(roster,choices)['reference_session_predictions']==174
 for k in list(choices):
  if k.endswith('/speed'):choices[k]=choices[k][:-1]+'1'
 assert schedule.required_counts(roster,choices)['reference_session_predictions']==348
 rows=[{'id':s['id'],'train':len(s['training_sessions']),'val':len(s['validation_sessions'])} for s in schedule.reference_selection(roster)]
 assert all(x['train']+x['val']==423 for x in rows);json.dumps(rows);retained(roster,rows)
group('full423/29/126/13 schedules and6-12 exact reference reuse',full_schedule)

def makewindow():
 return {'support':np.array([0.,.04]),'times':np.array([0.,.02,.039]),'context':[0.,1.,None],
         'locations':np.array([[0.,1.,2.],[2.,3.,4.]]),'location_missing':np.zeros((2,3),bool),
         'regions':['X','Y'],'spike_times':np.array([.002,.021]),'spike_units':np.array([0,1]),
         'neural_domain':np.array([[0.,.01],[.02,.04]])}
def neural_exposure():
 w=makewindow();x,e,a=features.spike_features(w,2);observed(x);observed(e)
 assert e[0]==.01 and e[1]==.02 and np.all(e[2:]==0)
 assert np.allclose(x[[0,1],[0,1]],np.log1p([2.,1.]))
 bad=dict(w,spike_times=np.array([.015]),spike_units=np.array([0]))
 refuses(lambda:features.spike_features(bad,2),'neural-domain')
 representation={'regions':['<UNK>','<MISSING>','X','Y'],'categories':[[0.],[1.],[]],
                 'location_mean':np.zeros(3),'location_scale':np.ones(3)}
 j=features.encode(w,representation,'J');c=features.encode(w,representation,'C')
 expected=np.zeros((3,11));idx=np.floor(w['times']/.02).astype(int)
 for k,lag in enumerate(range(-5,6)):
  valid=(idx+lag>=0)&(idx+lag<50);expected[valid,k]=a[idx[valid]+lag]
 assert np.array_equal(j['tabular'][:,-11:],expected)
 assert c['unit'] is None and c['exposure'] is None
 w2=dict(w,spike_times=np.array([],float),spike_units=np.array([],int),neural_domain=np.array([[0.,.04]]))
 assert np.array_equal(c['tabular'],features.encode(w2,representation,'C')['tabular'])
 retained(w,j,c,expected)
group('disjoint neural exposure and explicit11 lag masks with C isolation',neural_exposure)

def constants():
 x=np.column_stack((np.full(7,.1),np.array([.1]*6+[np.nextafter(.1,1.)])))
 w=np.array([1,2,3,4,5,6,7],float);w/=w.sum();sc=features.weighted_scaler(x,w)
 assert sc['constant'].tolist()==[True,False] and sc['mean'][0]==.1
 assert np.all(features.standardized(x,sc)[:,0]==0)
 sessions=[[(np.full((3,2),.1),np.full((3,2),.1)),(np.full((7,2),.1),np.full((7,2),.2))],
           [(np.full((11,2),.1),np.zeros((11,2)))]]
 result=scores.animal_score(sessions);assert result['sst']==[0.,0.] and result['r2']==[None,None]
 near=np.column_stack(([.1,np.nextafter(.1,1.),.1],[.2,.3,.4]))
 result=scores.animal_score([[(near,near.copy())]]);assert result['r2']==[1.,1.] and result['sst'][0]>0
 negative=scores.animal_score([[(np.array([[0.,0.],[1.,1.]]),np.full((2,2),100.))]])
 assert all(v<0 for v in negative['r2']);retained(x,w,sc,sessions,result,negative)
group('exact positive constants and genuinely near-constant ragged scores',constants)

def tiny_ridge():
 sessions=[]
 for i in range(3):
  w=makewindow();w['times']=np.array([0.,.01,.02,.03]);w['labels']=np.column_stack((np.arange(4.)+i-1.5,np.arange(4.)*.3+i+.1))
  sessions.append({'session':'tiny'+str(i),'animal':'a'+str(i%2),'regions':w['regions'],
                   'locations':w['locations'],'location_missing':w['location_missing'],'windows':[w]})
 config={'id':'ridge-0','family':'ridge','alpha':.01};clock=Clock()
 state=reference_models.fit(config,'C',0,sessions,clock)
 rep,windows,x,y,weight,xs,ys=reference_models.training_rows(sessions,'C',clock)
 z=features.standardized(x,xs);t=features.standardized(y,ys)
 expected=np.linalg.solve(z.T@(weight[:,None]*z)+.01*np.eye(z.shape[1]),z.T@(weight[:,None]*t))
 assert np.allclose(state['coef'],expected,rtol=1e-12,atol=1e-12)
 pred=reference_models.predict(state,sessions[0]['windows'][0],clock)
 encoded=features.encode(sessions[0]['windows'][0],rep,'C')['tabular']
 direct=(features.standardized(encoded,xs)@expected)*ys['scale']+ys['mean']
 assert np.allclose(pred,direct,rtol=1e-12,atol=1e-12)
 for a in (state['coef'],x,y,weight,z,t,expected,pred):observed(a)
 retained(sessions,state,x,y,weight,expected,pred)
group('actual tiny NumPy two-head normalized ridge and safe prediction formula',tiny_ridge)

def native_cast():
 class Interval:
  def __init__(self,a,b,ids=None):self.start=np.array(a,float);self.end=np.array(b,float);self.trial_index=np.array(ids or [7]*len(a))
  def __and__(self,other):return Interval([max(self.start[0],other.start[0])],[min(self.end[0],other.end[0])])
 class Units:
  location=np.zeros((2,3));region_beryl=['X','Y']
  def __len__(self):return 2
 domain=Interval([0.],[1.]);movement=Interval([0.],[1.],[7])
 def slice_(a,b):
  return types.SimpleNamespace(absolute_start=10.+a,domain=Interval([0.],[b-a]),
      wheel=types.SimpleNamespace(timestamps=np.array([0.,.02]),wheel_vel=np.array([.123456789,-.223456789],np.float64),wheel_speed=np.array([.123456789,.223456789],np.float64)),
      spikes=types.SimpleNamespace(timestamps=np.array([.01]),unit_index=np.array([0]),domain=Interval([0.],[b-a])))
 data=types.SimpleNamespace(absolute_start=10.,task_aligned_intervals=types.SimpleNamespace(domain=domain,movement_window=movement),
      wheel=types.SimpleNamespace(domain=domain),ts1_test_domain=Interval([.2],[.8]),units=Units(),slice=slice_,
      trials=types.SimpleNamespace(trial_index=np.array([7]),stimulus_side=np.array([1.]),stimulus_contrast=np.array([.5]),block_prior=np.array([.2])))
 module=types.ModuleType('torch_brain.samplers')
 def sampler(sampling_intervals,shuffle):
  q=sampling_intervals['fixed'];return [types.SimpleNamespace(start=q.start[0],end=q.end[0])]
 module.TrialSampler=sampler;old=sys.modules.get('torch_brain.samplers');sys.modules['torch_brain.samplers']=module
 try:rows=list(native_reader.iter_windows(data,'evaluation',{'units':2,'max_string_bytes':32,'windows':2,'timestamps':3,'spikes':3},Clock()))
 finally:
  if old is None:sys.modules.pop('torch_brain.samplers',None)
  else:sys.modules['torch_brain.samplers']=old
 assert len(rows)==1 and rows[0]['velocity'].dtype==np.float32 and rows[0]['speed'].dtype==np.float32
 assert np.allclose(rows[0]['times'],[.2,.22]) and rows[0]['native_target_origin']==10.2
 assert rows[0]['source_trial']==7 and rows[0]['A0']==10.;retained(rows)
group('real native reader target cast/A0 composition with disclosed interval/Data doubles',native_cast)

def false_gate():
 calls=[]
 with patch(preparation,cohort=lambda x:{},validate_authority=lambda a,r:{},versions=lambda x:calls.append('versions'),fresh=lambda *a:calls.append('fresh')):
  refuses(lambda:preparation.run({},None,Clock(),lambda *a:False),'explicit independent')
 assert calls==[]
 bad=core.encoded({'action':'python','code':'x','rationale':'r'})
 assert provider.action(bad)['code']=='x'
 refuses(lambda:provider.action(bad,'fixed_numeric'),'bounded frozen')
 assert provider.action(b'{"values":[1.5,-2]}','fixed_numeric')['values']==[1.5,-2.]
 assert provider.request_seed(('F/C/T0/r1','global'),1)==provider.request_seed(('I/J/T1/r1','b3'),99)
 assert provider.request_seed(('F/C/T0/r1','global'),1)!=provider.request_seed(('F/C/T0/r2','global'),1)
 retained(calls,bad)
group('false qualification before effects and distinct author/fixed numeric protocol',false_gate)

def persistent_budget():
 class Engine:
  def __init__(self,b):self.budget=b;self.scope=None
  def begin_scope(self,i,c,l):self.scope={'identity':i,'cutoff':c,'cpu_cap':l['native_cpu_ns'],'gpu_cap':l['gpu_device_seconds'],'cpu_reserved':0,'gpu_reserved':0}
  def end_scope(self,i):assert i==self.scope['identity'];r=self.scope;self.scope=None;return r
  def abort_scope(self):r=self.scope;self.scope=None;return r
 parent=Clock();engine=Engine(parent);profile={'wall_seconds':130.,'read_bytes':100,'write_bytes':100,'native_cpu_ns':10,'gpu_device_seconds':0.,'provider_calls':10,'tokens':100,'money':1.,'per_response_tokens':10,'request_bytes':1000,'response_bytes':1000}
 selection={'endpoint':'https://example.invalid/v1/chat/completions','wire_protocol':'neural058_chat_json_v1','seed_supported':True,'model':'invented'}
 pb=panel_budget.PanelBudget(parent,profile,'I/C/T0/r1',engine,selection,lambda x:None)
 assert pb.episode_cutoff(0,13)==12. and pb.episode_cutoff(12,13)==132.
 pb.reserve_read(60);refuses(lambda:pb.reserve_read(41),'whole-panel read cap');assert parent.read_bytes==60
 pb.provider.calls=3;pb.provider.tokens=7;pb.reserve_write(10)
 assert pb.snapshot()['provider_calls']==3 and pb.snapshot()['read_reserved_bytes']==60
 end=pb.finish();assert end['closed'] and end['provider_tokens_observed']==7 and engine.budget is parent
 refuses(lambda:pb.reserve_read(1),'panel close');retained(profile,end)
group('persistent whole-panel I budget and inherited episode deadlines',persistent_budget)

def primitive_shapes():
 import io
 a=np.arange(6,dtype='<f8').reshape(3,2);f=io.BytesIO();np.save(f,a,allow_pickle=False);raw=observed(f.getvalue())
 assert arrays.header(raw,48)['shape']==[3,2]
 refuses(lambda:arrays.header(raw,47),'expanded extent')
 refuses(lambda:arrays.header(raw+b'x',100),'expanded extent')
 h=b"{'descr': '|O', 'fortran_order': False, 'shape': (1,), }\n"
 raw2=observed(b'\x93NUMPY\x01\x00'+len(h).to_bytes(2,'little')+h)
 refuses(lambda:arrays.header(raw2,1000),'non-object')
 tree={'schema':'neural058_complete_state_v1','array_count':0,'tree':{'__array__':{'path':'x'}}}
 with patch(state_io,read_json=lambda *a:tree):
  refuses(lambda:state_io.load('/never',{},Clock(),{'metadata_bytes':100,'state_arrays':0}),'array read bound')
 retained(raw,raw2,tree)
group('actual primitive NPY headers and bounded safe-state refusal',primitive_shapes)

def literal_config():
 limits={'pids':4,'memory_bytes':1024,'cpu_rate_ns':1,'scratch_bytes':1024,'worker_read_bytes':1024,'worker_write_bytes':1024}
 engine={'study':'invented','image_id':'sha256:'+'a'*64,'uid_gid':'1:1','gpu_ids':[]}
 source={'bytes':1,'sha256':'b'*64};request={'bytes':2,'sha256':'c'*64}
 argv=native_contract.command('/qualified/python',source,source,request,1.,4.,limits)
 mounts=[{'source':'/invented/source','destination':'/inputs/source','pin':source,'bytes_cap':1}]
 expect=native_contract.config(engine,'op',source,argv,mounts,'/invented/out',limits)
 # Execute only literal assignment expressions from the frozen donor Engine,
 # never Engine.execute, an OS syscall or a native request.
 tree=ast.parse(bodies['engine']);method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='execute')
 assignments=[n for n in method.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('nonce','labels','config') for t in n.targets)]
 ns={'self':types.SimpleNamespace(selection=engine),'operation':'op','source_pin':source,'argv':argv,'limits':limits,
     'nano':1,'integer':core.integer,'encoded':core.encoded,'hashlib':hashlib,'bind':expect['HostConfig']['Mounts']}
 exec(compile(ast.Module(body=assignments,type_ignores=[]),'literal-only-config','exec'),ns)
 assert ns['config']==expect
 assert '--deadline' in argv and argv[argv.index('--deadline')+1]=='4.0';json.dumps(expect);retained(expect,argv,ns['config'])
group('independent native config matches exact frozen Engine assignment expressions',literal_config)

summary={'schema':'neural058_owner_invented_controls_v1','manifest':EXPECTED,'groups_passed':passed,'groups':len(passed),
         'source_read_bytes':source_reads,'canonical_bytes_before_summary':encoded_total,'encoding_calls_before_summary':encoding_calls,
         'known_raw_fixture_bytes':raw_observed,'retained_recursive_projection_max':max_retained,'traced_peak_bytes_after_imports':tracemalloc.get_traced_memory()[1],
         'physical_fixture_files':0,'retained_fixture_files':0,'fixture_charge_reserved_bytes':12<<20,
         'limits':{'canonical':6<<20,'raw_scaffold':4<<20,'headroom':2<<20,'retained':3<<20,'live':32<<20},
         'not_executed':['authentic data/header/model','native or child processes','providers/network','forest or torch fitting','native metric scoring','full controller/custody proof'],
         'numeric_scope':'tiny invented NumPy ridge/scaler/features only; installed full native version parity not claimed'}
print(json.dumps(summary,sort_keys=True))
