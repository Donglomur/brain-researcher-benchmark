"""Programme error custody; software-prefix counters do not certify native resource use."""
import time
from contextlib import contextmanager
class Owner:
 def __init__(self,limits):
  self.limits=dict(limits);self.started=time.monotonic();self.first=None;self.secondary=[];self.events=[];self.used={'read_bytes':0,'write_bytes':0,'jobs':0};self.closed=False
 def retain(self,e,stage):
  if self.first is None:self.first=e
  elif e is not self.first:self.secondary.append(e)
  self.events.append({'stage':stage,'type':type(e).__name__})
 def charge(self,key,n):
  if type(n)is not int or n<0:raise ValueError('cost domain')
  if self.used[key]+n>self.limits[key]:raise ValueError('resource cap '+key)
  self.used[key]+=n
 def check(self):
  if self.closed:raise ValueError('owner closed')
  if self.first is not None:raise self.first
  if time.monotonic()-self.started>self.limits['wall_seconds']:raise TimeoutError('whole programme wall cap')
 @contextmanager
 def stage(self,name):
  try:
   self.check();self.events.append({'stage':name,'state':'entered'});yield
  except BaseException as e:self.retain(e,name);raise self.first
  else:self.events.append({'stage':name,'state':'returned'})
 def cleanup(self,name,fn):
  try:fn()
  except BaseException as e:self.retain(e,name)
 def snapshot(self):
  return {'first':None if self.first is None else type(self.first).__name__,'secondary':[type(e).__name__ for e in self.secondary],'events':list(self.events),'used':dict(self.used),'wall_seconds':time.monotonic()-self.started,'cost_domain':'reserved logical file stream extents and jobs; HDF5/NPY/native allocations and physical CPU/IO/RSS not measured','closed':self.closed}
 def close(self):self.closed=True
