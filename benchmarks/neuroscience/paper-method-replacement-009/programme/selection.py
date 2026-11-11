"""Fixed trusted operator selection capture; metadata cannot issue qualification."""
from pathlib import Path
from .native.io import read,parse,identity,need,exact
from .native.observation import Observation
class OperatorSelection:
 def __init__(self):raise TypeError('fixed capture only')
 @classmethod
 def capture(cls,path,pin):
  o=Observation('trial_bootstrap');o.record={'read_limit':1048576,'write_limit':0,'scientific_execution':False}
  try:
   raw=read(path,1048576,pin);body=parse(raw)
   need(body['schema']=='trial-independent-deployment-v4','Trial deployment identity')
   need(body['enabled']is True,'BUILD ONLY deployment remains disabled')
   obj=object.__new__(cls);obj.path=Path(path);obj.pin=pin;obj.raw=raw;obj.body=body;obj.identity=identity(raw);obj.observation=o;obj.transferred=False;return obj
  except BaseException as exc:o.fail(exc,'fixed_selection');o.raise_failure()
 def revalidate(self):need(read(self.path,1048576,self.pin)==self.raw,'original operator selection stable')
 def transfer(self,owner):
  need(not self.transferred,'one bootstrap transfer');self.transferred=True;owner.children['bootstrap']=self.observation
  owner.record['bootstrap_bytes']=len(self.raw)
