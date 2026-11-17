"""Invented-source controls only. Never imports task arrays, Docker or a candidate."""
import ast,base64,hashlib,json,os,sys,tempfile,time,types
from pathlib import Path
HERE=Path(__file__).resolve().parent/'runtime'

def pin(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def load():
 b=(HERE/'bootstrap.py').read_bytes();m=types.ModuleType('_control_bootstrap');exec(compile(b,str(HERE/'bootstrap.py'),'exec'),m.__dict__);raw=(HERE/'SOURCE_MANIFEST.json').read_bytes();return m.load(HERE,pin(raw)['sha256'])
def refuse(fn):
 try:fn()
 except (ValueError,TimeoutError):return
 raise AssertionError('expected refusal')

def run_controls():
 loader,bodies,manifest,source=load();c=loader('coordinator');com=loader('common');p=loader('phases');cap=loader('capture');results=[]
 def mark(name):results.append({'control':name,'passed':True})
 for name,b in bodies.items():
  if name.endswith('.py'):ast.parse(b,name)
 mark('all frozen modules parse; captured source loader resolves fixed modules')
 assert len(com.KEYS)==len(set(com.KEYS))==650 and com.PRED==24*2**20 and 650*com.PRED==16_357_785_600
 assert c.whole_seconds(3600)==650*(3600+840)+7320;mark('all650 complete ordered domain and unchanged output capacity')
 oldcap=c.capture;c.capture=lambda *_a,**_k:(_ for _ in()).throw(AssertionError('disabled selection read operand'))
 refuse(lambda:c.validate_selection({'execution_selected':False},source,bodies));c.capture=oldcap;mark('disabled selection refuses before any program or qualification read')


 review={'schema':'neural076_program_procedural_review_v1','program':pin(b'fixture program'),'source':source,'training_only_transforms':True,'pointwise_query_prediction':True,'no_cross_context_state':True,'max_voxels_per_unit':316,'reviewed':True,'input_dependence_empirically_proven':False}
 qual={'schema':'neural076_full650_runtime_qualification_v1','source':source,'image':'sha256:'+'b'*64,'python':'3.11.13','dependencies':json.loads(bodies['LOCK.json'])['expected_dependencies'],'host_python':str(Path(sys.executable).resolve()),'docker_binary':'/__INVENTED_DOCKER_BINARY__','docker_socket':'/__INVENTED_DOCKER_SOCKET__','source_directory':str(HERE),'candidate_seconds':10,'candidate_memory_bytes':512*2**20,'staging_candidate_collection_capabilities_qualified':True,'scientific_performance_qualified':False,'exclusive_operator_owned_source_collection_output':True,'same_filesystem_no_concurrent_writers':True,'candidate_has_no_host_or_socket_access':True}
 rawreview=com.encode(review);rawqual=com.encode(qual);s={'schema':'neural076_full650_selection_v1','execution_selected':True,'task_id':'NEURAL-076','source':source,'collection':'/__INVENTED_COLLECTION__','output':'/__INVENTED_OUTPUT__','program':{'path':'/__INVENTED_PROGRAM__',**pin(b'fixture program')},'program_review':{'path':'/__INVENTED_REVIEW__',**pin(rawreview)},'runtime_qualification':{'path':'/__INVENTED_QUALIFICATION__',**pin(rawqual)},'image':qual['image'],'docker_binary':qual['docker_binary'],'docker_socket':qual['docker_socket'],'candidate_seconds':10,'memory_bytes':512*2**20,'other_future_bytes':0,'whole_seconds':c.whole_seconds(10),'retained_bytes':com.RETAIN+com.MIB,'managed_reads':com.READS,'managed_writes':com.WRITES}
 saved=c.capture;c.capture=lambda name,*_a,**_k:(rawreview,pin(rawreview))if name=='/__INVENTED_REVIEW__'else(rawqual,pin(rawqual))
 c.validate_selection(s,source,bodies)
 for name,value in(('docker_binary','/__OTHER_BINARY__'),('docker_socket','/__OTHER_SOCKET__'),('memory_bytes',1024*2**20)):
  refuse(lambda name=name,value=value:c.validate_selection({**s,name:value},source,bodies))
 refuse(lambda:c.validate_selection({**s,'candidate_seconds':11,'whole_seconds':c.whole_seconds(11)},source,bodies))
 qual['source_directory']='/__OTHER_SOURCE__';rawqual=com.encode(qual);s['runtime_qualification'].update(pin(rawqual));refuse(lambda:c.validate_selection(s,source,bodies));c.capture=saved
 mark('runtime qualification replay fails for different Docker binary/socket, candidate limits or source directory')

 class RamPath:
  def __init__(self,x):self.x=str(x)
  def __str__(self):return self.x
  def __fspath__(self):return self.x
  def __truediv__(self,x):return RamPath(self.x+'/'+str(x))
  def __eq__(self,x):return isinstance(x,RamPath)and self.x==x.x
  def __hash__(self):return hash(self.x)
  @property
  def parent(self):return RamPath(self.x.rsplit('/',1)[0])
  @property
  def parents(self):return tuple(RamPath(str(p))for p in Path(self.x).parents)
  def is_dir(self):return True
  def iterdir(self):return iter(())
 class RamBudget:
  def __init__(self,root,other,end):self.root=root;self.end=end;self.docs={};budgets.append(self)
  def check(self,*_):pass
  def mkdir(self,*_):pass
  def save(self,path,value,cap):
   raw=com.encode(value);assert len(raw)<=cap;self.docs[str(path)]=value;return pin(raw)
  def tick(self):pass
  def record(self):return {'fixture_only':True}
 old={name:getattr(c,name)for name in('validate_selection','path','Budget','freeze','phase','move_prediction','retire_view','capture')}
 c.validate_selection=lambda *_:{'source_design_sha256':'a'*64};c.path=lambda x:RamPath(x);c.Budget=RamBudget
 c.capture=lambda _p,_cap,pin,**_k:(None,pin)
 def experiment(failure=None,bad_collect=False):
  nonlocal_events=[];closedkeys=[];commit=pin(b'invented commit');pred=pin(b'invented opaque byte stream');s={'output':'/__RAM_NEURAL076_OUTPUT_ONLY__','collection':'/__RAM_NEURAL076_COLLECTION_ONLY__','other_future_bytes':0,'whole_seconds':10000}
  def freeze(*_):nonlocal_events.append(('freeze',None));return commit
  def phase(mode,key,*_):
   assert nonlocal_events and nonlocal_events[0][0]=='freeze';nonlocal_events.append((mode,key))
   if failure==(mode,key):raise ValueError('invented phase refusal')
   if mode=='stage':return {'binding':{'key':key}},{}
   if mode=='candidate':return {'input':{'key':key}},{}
   assert mode=='collect'and len(closedkeys)==650
   parts=[{'key':x,'path':x.replace('/','__')+'.npz','prediction':pred}for x in closedkeys]
   if bad_collect:parts[0]['prediction']=pin(b'wrong closed pin')
   return {'source_design_sha256':'a'*64,'gold_opened':False,'scientific_scoring':False,'parts':parts},{}
  def move(key,*_):closedkeys.append(key);return {'key':key,'path':key.replace('/','__')+'.npz','prediction':pred}
  c.freeze=freeze;c.phase=phase;c.move_prediction=move;c.retire_view=lambda *_:{}
  t=time.monotonic()
  if failure or bad_collect:refuse(lambda:c.run(s,source,loader,bodies,t,t+9999))
  else:c.run(s,source,loader,bodies,t,t+9999)
  return nonlocal_events,closedkeys,budgets[-1].docs
 budgets=[]
 events,keys,docs=experiment();assert events==[('freeze',None)]+[(m,k)for k in com.KEYS for m in('stage','candidate')]+[('collect',None)];assert keys==list(com.KEYS)
 complete=docs['/__RAM_NEURAL076_OUTPUT_ONLY__/COMPLETE.json'];assert complete['context_count']==650 and complete['scientific_scoring']is complete['runtime_qualified']is complete['scientific_qualified']is False
 mark('production controller full650 orchestration, freeze first, collector only after1300 phases, no score or qualification')
 events,keys,docs=experiment(('stage',com.KEYS[648]));assert len(keys)==648 and not any(m=='collect'for m,_ in events)and not any(k.endswith('/COMPLETE.json')for k in docs);assert docs['/__RAM_NEURAL076_OUTPUT_ONLY__/FAILURE.json']['completed_contexts']==648
 mark('late stage failure stops cohort and preserves incomplete count; no collector or complete receipt')
 events,keys,docs=experiment(bad_collect=True);assert len(keys)==650 and not any(k.endswith('/submission.json')or k.endswith('/COMPLETE.json')for k in docs)
 mark('collector altered pin refuses after full650; no accepted submission')
 for k,v in old.items():setattr(c,k,v)

 with tempfile.TemporaryDirectory(prefix='neural076-invented-source-only-')as td:
  td=Path(td).resolve();view=td/'view';view.mkdir();ctx={'schema':'neural076_matched_hierarchy_v1','key':com.KEYS[0],'source_design_sha256':'56ff1e67bb824b9ad6ab9005db82a11349581bb634a0725f4a1cca81019a6026','max_selected_voxels':316}
  fs={name:pin(b'invented opaque fixture')for name in('training.npz','queries.npz','bank.npz')}
  for name in fs:(view/name).write_bytes(b'invented opaque fixture')
  raw=com.encode(ctx);(view/'context.json').write_bytes(raw);fs['context.json']=pin(raw);(view/'COMPLETE.json').write_bytes(com.encode({'schema':'neural076_prepared_v1','files':fs}))
  binding=p.stage_binding(view,com.KEYS[0],lambda:None);assert set(binding['files'])==com.FILES
  (view/'extra').write_bytes(b'x');refuse(lambda:p.stage_binding(view,com.KEYS[0],lambda:None));(view/'extra').unlink()
  (view/'queries.npz').write_bytes(b'invented mutated query fixture');refuse(lambda:p.stage_binding(view,com.KEYS[0],lambda:None))
  mark('opaque stage binding admits five fixed files, rejects extra and changed bytes without decoding arrays')
  src=td/'phase';src.mkdir();dest=td/'out';dest.mkdir();(dest/'submission').mkdir();(dest/'moves').mkdir();raw=b'invented prediction';(src/'predictions.npz').write_bytes(raw);budget=RamBudget(dest,0,time.monotonic()+100);cp=pin(b'commit');result={'key':com.KEYS[0],'commit':cp,'all_resources_closed':True,'producer_removed_before_capture':True,'prediction':pin(raw)}
  ino=(src/'predictions.npz').stat().st_ino;out=c.move_prediction(com.KEYS[0],result,{'folder':str(src)},dest,source,cp,budget);target=dest/'submission'/out['path'];assert target.stat().st_ino==ino and target.read_bytes()==raw and not(src/'predictions.npz').exists()
  (src/'predictions.npz').write_bytes(raw);refuse(lambda:c.move_prediction(com.KEYS[0],result,{'folder':str(src)},dest,source,cp,budget));assert(src/'predictions.npz').exists()
  mark('production output custody move preserves inode, removes source and refuses existing destination')

 raw=b'invented prediction';idx={'schema':'neural076_output_index_v1',**pin(raw)};chunk={'schema':'neural076_output_chunk_v1','offset':0,'total_bytes':len(raw),**pin(raw),'base64':base64.b64encode(raw).decode()};w=types.SimpleNamespace(pending=None)
 r=types.SimpleNamespace(parse=com.decode,call=lambda _d,a,*_args:com.encode(idx if 'index'in a else chunk));got=cap.capture_output(types.SimpleNamespace(r=r),None,{'id':'invented'},time.monotonic()+10,None,w);assert got=={'predictions.npz':pin(raw)}and w.pending==raw
 idx['unapproved']=1;refuse(lambda:cap.capture_output(types.SimpleNamespace(r=r),None,{'id':'invented'},time.monotonic()+10,None,w));mark('opaque holder capture only stages bytes in RAM and rejects extra index fields')
 good={'natural_exit':True,'exit_code':0,'process_reaped':True,'process_group_absent':True,'streams_closed':True,'streams_eof':True,'timed_out':False,'error_type':None}
 c.child_closed(good)
 for field in('natural_exit','process_reaped','process_group_absent','streams_closed','streams_eof'):refuse(lambda field=field:c.child_closed({**good,field:False}))
 refuse(lambda:c.child_closed({**good,'timer_restore_error':'invented'}));mark('outer closure needs natural zero, reaping, affirmative group absence, EOF and clean timer restoration')
 return {'schema':'neural076_full650_source_controls_v1','passed':True,'groups':len(results),'source':source,'results':results,'actual_source_process_run':False,'native_execution':False,'candidate_execution':False,'authentic_arrays_or_pool_read':False,'gold_or_key_read':False,'model_or_scorer_execution':False,'runtime_qualification':False,'scientific_qualification':False,'fixture_files':'small invented opaque bytes in a fresh temporary directory; removed on exit, spent costs retained','scope':'Production controller loop exercised with in-memory phase services; actual stage, Docker, scientific artifact validator and whole observer process were not executed.'}

if __name__=='__main__':
 r=run_controls();print(json.dumps(r,indent=2))
