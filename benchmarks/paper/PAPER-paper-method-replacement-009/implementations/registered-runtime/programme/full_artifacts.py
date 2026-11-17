"""Strong capture occurrences and stopped-output/target barrier."""
from pathlib import Path
from dataclasses import dataclass
from .native.io import read,write_new,load,canonical,identity,relative,need,tree
from .native.observation import Observation
_TOKEN=object()
@dataclass(frozen=True)
class Capture:
 owner:object
 ordinal:int
 path:str
 pin:dict
 token:object
class Artifacts:
 def __init__(self,root,cap,observation,host):
  self.root=Path(root);self.cap=cap;self.host=host;self.observation=observation;self.captures=[];self.by_path={};self.bytes=0;self.read_bytes=0;self.attempted_bytes=0
  need(not self.root.exists(),'fresh original artifact owner');self.root.mkdir(parents=True,mode=0o700)
 def put(self,path,body):
  relative(path);need(path not in self.by_path,'one source capture per path')
  need(len(self.captures)<self.cap['files']and self.attempted_bytes+len(body)<=self.cap['cumulative_write_bytes'],'pre-effect total source reservation')
  need(len(body)<=self.cap['member_bytes'],'artifact member cap');self.attempted_bytes+=len(body)
  slot={'path':path,'body_bytes':len(body),'state':'attempted','pin':None};self.observation.publications[path]=slot
  try:
   pin=self.host.write(self.root/path,body,self.cap['member_bytes']);actual=self.host.read(self.root/path,pin['bytes'],pin)
   need(actual==body,'actual completed output readback');self.bytes+=len(body)
   c=Capture(self,len(self.captures),path,pin,_TOKEN);self.captures.append(c);self.by_path[path]=c;slot.update(state='durable',pin=pin);return c
  except BaseException as exc:slot['state']='failed_unknown_prefix';slot['error']=exc;self.observation.fail(exc,'capture:'+path);raise
 def json(self,path,value):return self.put(path,canonical(value)+b'\n')
 def require(self,c):
  need(type(c)is Capture and c.token is _TOKEN and c.owner is self and self.by_path.get(c.path)is c and self.captures[c.ordinal]is c,'same actual source capture')
  return c
 def read(self,c):
  self.require(c);self.read_bytes+=c.pin['bytes'];need(self.read_bytes<=self.cap['input_bytes'],'total artifact read reservation')
  return self.host.read(self.root/c.path,c.pin['bytes'],c.pin)
 def document(self,c):
  from .native.io import parse
  return parse(self.read(c))
 def collect(self,source,expected,prefix):
  actual=self.host.tree(source,total=self.cap['retained_bytes'],member=self.cap['member_bytes'],files=self.cap['files'])
  need(actual==expected,'same stopped process output tree')
  rows=[]
  for row in actual['files']:
   cap=self.put(prefix+'/'+relative(row['path']),self.host.read(Path(source)/row['path'],row['bytes'],row));rows.append(cap)
  return rows

class CapturedJob:
 def __init__(self,owner,job,observation,files,manifest):
  self.owner=owner;self.job=job;self.observation=observation;self.files=tuple(files);self.manifest=manifest
 def require(self):
  need(self.owner.results.get(self.job['id'])is self,'actual full driver job occurrence')
  need(self.observation.first_error is None and self.observation.record['natural_completion'],'original stopped process success')
  for c in self.files:self.owner.artifacts.require(c)
  self.owner.artifacts.require(self.manifest);return self

class TargetBarrier:
 def __init__(self,owner):self.owner=owner;self.sealed=False;self.opened=False;self.predictions={}
 def seal(self):
  need(not self.sealed and not self.opened,'one capture barrier')
  jobs=[j for j in self.owner.study['jobs']if j['role']!='panel']
  # Failed/unavailable jobs remain explicit denominators. All attempts must settle
  # before scoring; missing intended support forbids a complete-primary win.
  need(all(self.owner.states[j['id']]in('complete','failed','unavailable','not_attempted_after_fatal_owner')for j in jobs),'all candidate/reference attempts settled before target access')
  for j in jobs:
   if self.owner.states[j['id']]!='complete':continue
   result=self.owner.results[j['id']].require();doc=self.owner.artifacts.document(result.manifest)
   need(doc['job']==j['id']and doc['cases']==j['cases']and doc['arm']==j['arm'],'original job output inverse')
   self.predictions[j['id']]=result
  self.sealed=True
 def open(self):
  need(self.sealed and not self.opened,'all outputs captured before target opening');self.opened=True
  return self.owner.targets
