"""Full per-replicate complex support and admitted exact assignment matching."""
from .core import *
SYMMETRIES=('symmetric','one_third','two_thirds','nonsymmetric')
def connectivity_name(index):
 need(type(index) is int and 0<=index<40,'all forty dense networks')
 return 'connectivity_eigenvalues/'+SYMMETRIES[index//10]+'/network_%02d'%(index%10)
def connectivity_spec(index):
 return {'shape':[10000,2],'kind':'complex_pairs','spectrum':{'family':'dense_connectivity','unit_id':connectivity_name(index),'complete_eigenvalues':10000,'source_n_comps':None}}
def check_spec(operation,name,spec):
 exact(spec,('shape','kind','spectrum'),'complex spectral geometry')
 s=spec['spectrum'];exact(s,('family','unit_id','complete_eigenvalues','source_n_comps'),'complete spectrum identity')
 n=s['complete_eigenvalues'];need(type(n) is int and spec['shape']==[n,2] and spec['kind']=='complex_pairs','one complete spectrum per descriptor')
 if s['family']=='dense_connectivity':
  need(operation=='dense_covariance' and name in [connectivity_name(i) for i in range(40)],'declared dense replicate')
  need(s['unit_id']==name and n==10000 and s['source_n_comps'] is None,'all actual 10000 connectivity modes')
 else:
  need(s['family']=='dmd' and operation in ('empirical_dynamics','simulated_dynamics','running_state','external_achilles','external_plitt','external_zhong','external_maze','external_rtt','external_area2'),'explicit DMD family')
  need(0<n<=1000 and s['source_n_comps']==1000 and type(s['unit_id']) is str and bool(s['unit_id']),'full admitted reduced DMD basis, not a connectivity truncation')
 return n
def check_population(operation,outputs):
 if operation=='dense_covariance':
  required={connectivity_name(i) for i in range(40)}
  actual={k for k in outputs if k=='connectivity_eigenvalues' or k.startswith('connectivity_eigenvalues/')}
  need(actual==required,'all four symmetries times ten independent dense networks')
  for name in required:check_spec(operation,name,outputs[name])
def workload(operation,name,spec):
 n=check_spec(operation,name,spec)
 return {'schema':'critical_init_full_assignment_workload_v1','operation':operation,'spectrum':name,'eigenvalues_each':n,'matched_pairs':n,
  'metric':'minimum_total_bijective_Euclidean_assignment_complex_plane','distance_dtype':'float64','distance_shape':[n,n],
  'distance_matrix_bytes':8*n*n,'two_float64_input_pair_arrays_bytes':32*n,'row_temporary_bytes':8*n,
  'additional_peak_bytes':'UNKNOWN: Python/array conversion, SciPy assignment workspace/copies, allocator and concurrent resident inputs require measured admission',
  'algorithm_time':'UNKNOWN; exact dense assignment, not nearest-neighbour or ordering substitution',
  'native_feasibility_proven':False,'replicate_policy':'one complete spectrum at a time; all declared replicas retained'}
class MatchingTransaction:
 """Own one actual admission and close it even when an inert/native leaf fails."""
 def __init__(self,plan,backend):self.plan=plan;self.backend=backend;self.owner=None;self.report=None
 def run(self,left,right):
  first=None;answer=None;cleanup=None
  try:
   self.owner=self.backend.acquire(self.plan)
   # No input conversion or NxN allocation occurs before actual acquisition.
   answer=self.backend.compute(self.owner,left,right,self.plan)
  except BaseException as exc:first=exc
  if self.owner is not None:
   try:self.backend.close(self.owner)
   except BaseException as exc:cleanup=exc
  self.report={'status':'failed' if first or cleanup else 'complete','first_error':None if not(first or cleanup) else str(first if first else cleanup),'cleanup_error':None if cleanup is None else str(cleanup),'workspace_returned_to_transaction':self.owner is not None,'acquisition_effects_if_no_grant_returned':'UNKNOWN; never inferred zero','native_feasibility_granted_by_source':False}
  if first is not None:raise first
  if cleanup is not None:raise cleanup
  return answer
class NativeMatching:
 def __init__(self,run):
  from .sandbox import actual_closed
  actual_closed(run);self.run=run
 def acquire(self,plan):
  host=self.run.owner;host.require('full_complex_assignment_workspace',host.source_sha256)
  # The live issuer must include a measured additional-allocation envelope.
  # The stated 800 MB matrix lower bound is NOT a sufficient resource grant.
  grant=host.lease.acquire_scientific_workspace(plan)
  try:
   need(not isinstance(grant,(dict,str,bytes)) and callable(getattr(grant,'require',None)) and callable(getattr(grant,'close',None)),'actual scientific workspace owner')
   grant.require(plan,'before_any_numeric_import_or_allocation')
  except BaseException as first:
   try:
    close=getattr(grant,'close',None)
    need(callable(close),'returned workspace has no close method; effects unknown')
    close()
   except BaseException as cleanup:
    try:first.add_note('Workspace close also failed: '+str(cleanup))
    except BaseException:pass
   raise
  return grant
 def compute(self,grant,left,right,plan):
  grant.require(plan,'immediately_before_NxN_workspace')
  import numpy as np
  from scipy.optimize import linear_sum_assignment
  n=plan['eigenvalues_each'];x=np.asarray(left(),dtype=np.float64).reshape((n,2));y=np.asarray(right(),dtype=np.float64).reshape((n,2))
  need(np.isfinite(x).all() and np.isfinite(y).all(),'all complete spectral inputs finite')
  d=np.empty((n,n),dtype=np.float64)
  # Rowwise construction avoids the old broadcast pairwise x2 intermediate;
  # assignment and library costs still require measured native admission.
  for i in range(n):
   np.subtract(y[:,0],x[i,0],out=d[i]);dy=y[:,1]-x[i,1];np.hypot(d[i],dy,out=d[i])
  need(np.isfinite(d).all(),'finite full assignment distances')
  i,j=linear_sum_assignment(d);need(len(i)==len(j)==n,'every mode matched once, preserving multiplicity')
  return {'mae':float(d[i,j].mean()),'max_error':float(d[i,j].max()),'count':n,'metric':plan['metric']}
 def close(self,grant):grant.close()
