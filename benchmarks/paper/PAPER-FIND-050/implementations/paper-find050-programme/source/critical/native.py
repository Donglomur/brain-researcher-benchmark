"""Concrete author-kernel consumers. No function is executed during construction.

Use only in the independently qualified reference image and its exact offline
input namespace. Authenticated source does not authorize its imports or I/O.
"""
from pathlib import Path
import importlib.util,sys
from .core import *
from .programme import contract,catalogue
ROOT=Path(__file__).absolute().parents[1]
def source_module(path,authority,cost):
 authority.require("native_source_import",authority.source_sha256)
 # The live worker captures the whole admitted author import closure before
 # dispatch. Execute those bytes, including transitive author imports; never
 # discard a hash check and then ask a path/bytecode loader to reread the file.
 from .native_worker import NativeWorkerLease
 need(type(authority.lease) is NativeWorkerLease,'source-owned native worker lease')
 return authority.lease.load_author_module(path)
def original_call(operation,bindings,authority,cost):
 from .native_producer import NativeProducer
 producer=getattr(authority.native_context,'active_producer',None)
 need(type(producer) is NativeProducer and producer.active and producer.host is authority and producer.operation==operation,'actual selected source worker before native dispatch')
 spec=catalogue()[operation];authority.require("native_operation:"+operation,authority.source_sha256)
 need(bindings["operation"]==operation and bindings["complete_population_admitted"] is True,"operator-bound complete operation")
 need(bindings["source_method_label"] in ("literal_author_kernel","reconstructed_author_orchestration"),"explicit source semantics")
 handlers={"dense_covariance":dense_reference,"empirical_dynamics":empirical_dynamics,"simulated_dynamics":simulated_dynamics}
 if operation in handlers:return handlers[operation](bindings,authority,cost)
 routes={
 "distribution_robustness":("simulations.py","random_probs_sim"),
 "temporal_binning":("simulations.py","tbin_analysis"),
 "noise_estimators":("simulations.py","random_uniform_sim_sizes"),
 "near_criticality":("simulations.py","enorm_sweep"),
 "near_critical_examples":("simulations.py","sims_fig2"),
 "empirical_spectra":("fig2/analysis.py","neural_powerlaws"),
 "ephys_regions":("fig2/analysis.py","ephys_areas"),
 "ephys_bins":("fig2/analysis.py","ephys_tbins"),
 "running_state":("fig2/analysis.py","running"),
 "gcamp_comparison":("fig2/analysis.py","gcamp_subsample"),
 "sparse_connectivity":("fig4/sparse_clustered_local_sims.py","sparse_evals"),
 "clustered_connectivity":("fig4/sparse_clustered_local_sims.py","clustered_evals"),
 "local_connectivity":("fig4/sparse_clustered_local_sims.py","local_evals"),
 "neural_strong_pairs":("fig4/analysis.py","neural_strong_pairs"),
 "external_achilles":("fig3/other_datasets.py","grosmark_hippo"),
 "external_plitt":("fig3/other_datasets.py","plitt_hippo"),
 "external_zhong":("fig3/other_datasets.py","zhong_visual"),
 "external_maze":("fig3/other_datasets.py","mc_maze"),
 "external_rtt":("fig3/other_datasets.py","mc_rtt"),
 "external_area2":("fig3/other_datasets.py","area2_bump"),
 "memory_binary":("fig5/fig5.py","run_multishot"),
 "memory_zeroshot":("fig5/fig5.py","run_zeroshot"),
 "memory_aligned":("fig5/fig5.py","run_zeroshot")}
 need(operation in routes,"complete explicit producer route")
 path,name=routes[operation];module=source_module(path,authority,cost)
 # The live native issuer supplies typed, already-admitted arguments and
 # validates exact original rosters, parameter grids and output geometry.
 # JSON 'complete_population_admitted' is a join, not issuance of that authority.
 args,kwargs=authority.native_context.bind_original_arguments(operation,bindings,module)
 need(authority.native_context.plans[operation]['function']==name,'exact selected source function')
 authority.require("immediately_before_kernel:"+operation,authority.source_sha256)
 result=authority.native_context.invoke(operation,bindings,module,name,args,kwargs)
 return authority.native_context.capture_original_result(operation,result,bindings)
def dense_reference(bindings,authority,cost):
 import numpy as np
 import torch
 from scipy.linalg import solve_continuous_lyapunov
 sim=source_module("simulations.py",authority,cost);power=source_module("powerlaw.py",authority,cost)
 cfg=authority.native_context.bind_dense(bindings);need(cfg["nn"]==10000 and cfg["networks"]==10,"complete dense population")
 out=[]
 for symmetry in (0,1/3,2/3,1):
  for repetition in range(10):
   authority.require("dense_network",authority.source_sha256)
   sim.set_seed(cfg["seeds"][str(symmetry)][repetition],cfg["device"])
   A,X,e=sim.simulate_random(nn=10000,nonsym=symmetry,device=cfg["device"])
   spectrum,_=power.zscore_and_compute_evals(X.clone())
   a=A.cpu().numpy();d=a-np.eye(len(a));cov=solve_continuous_lyapunov(d,-np.eye(len(a)))
   residual=d@cov+cov@d.T+np.eye(len(a))
   out.append({"symmetry":symmetry,"network":repetition,"eigenspectrum":spectrum,"connectivity_eigenvalues":e.cpu().numpy(),
               "stationary_covariance_spectrum":np.linalg.eigvalsh(cov)[::-1],"lyapunov_residual":np.linalg.norm(residual),
               "exponent":power.fit_powerlaw_exp(spectrum,np.arange(10,500))[0]})
 return authority.native_context.capture_original_result("dense_covariance",out,bindings)
def empirical_dynamics(bindings,authority,cost):
 lyapun=source_module("lyapun.py",authority,cost)
 records=authority.native_context.admitted_empirical_records(bindings)
 expected=contract("COHORT.json")["fig3_order"];need([r.session_id for r in records]==expected,"complete exact Fig3 order")
 out=[]
 for record in records:
  from .lifecycle import Custody
  lifecycle=Custody('empirical_record:'+record.session_id)
  # This producer owns the authenticated complete input/geometry and performs
  # source preprocessing. Its actual implementation and resources are G01-03.
  try:
   authority.require("empirical_session:"+record.session_id,authority.source_sha256)
   x,xpos,ypos=record.open_full_fig3()
   z=lyapun.zscore(x,axis=-1);is_ephys=record.modality=="ephys"
   e=lyapun.dmd(z,lam=.1 if is_ephys else .01,delta=5,device=record.device)[1]
   acg=lyapun.pc_timescales(z,xpos,ypos,sig=2 if is_ephys else 0,device=record.device)
   out.append({"session_id":record.session_id,"e":e,"acg":acg})
  except BaseException as exc:lifecycle.capture(exc,'empirical_record_body')
  lifecycle.attempt('empirical_record_close',record.close)
  lifecycle.raise_first()
 return authority.native_context.capture_original_result("empirical_dynamics",out,bindings)
def simulated_dynamics(bindings,authority,cost):
 import numpy as np
 sim=source_module("simulations.py",authority,cost);lyapun=source_module("lyapun.py",authority,cost)
 cfg=authority.native_context.bind_dynamics(bindings);out=[]
 # Literal Fig3 driver starts one seed-0 stream before both nested loops.
 sim.set_seed(0,cfg['device'])
 for symmetry in (0,1):
  for repetition in range(4):
   authority.require("simulated_dynamics_network",authority.source_sha256)
   A,X,e=sim.simulate_random(nn=10000,nonsym=symmetry,device=cfg["device"])
   data=X.cpu().numpy();xpos=1000*np.random.rand(10000);ypos=1000*np.random.rand(10000)
   modes=lyapun.dmd(data,lam=.01,delta=5,device=cfg["device"],nt=2434)[1]
   acg=lyapun.pc_timescales(data,xpos,ypos,device=cfg["device"])
   out.append({"symmetry":symmetry,"network":repetition,"e":modes,"acg":acg})
 return authority.native_context.capture_original_result("simulated_dynamics",out,bindings)
