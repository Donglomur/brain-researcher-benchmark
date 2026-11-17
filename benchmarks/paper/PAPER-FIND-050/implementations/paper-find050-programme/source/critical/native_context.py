"""Concrete native binding/capture API, supplied only by a qualified live operator.

Plans and pins are descriptions, never grants. All imports, input decoding and
output arrays are native work. This source phase does not instantiate this class.
Unknown original notebook configuration cannot be filled from convenient defaults.
"""
from pathlib import Path
from .core import *
from .programme import catalogue
from . import tensors
from .lifecycle import Custody
class NativeContext:
 def __init__(self,authority,plans,input_root,output_root,cost,device):
  authority.require('native_context_issuance',authority.source_sha256)
  need(set(plans)==set(catalogue()),'all original operation bindings, no narrow native subset')
  self.authority=authority;self.plans=plans;self.input_root=ordinary(input_root);self.output_root=ordinary(output_root);self.cost=cost;self.device=device
  authority.native_context=self
 def plan(self,operation,bindings):
  self.authority.require('native_plan:'+operation,self.authority.source_sha256)
  p=self.plans[operation]
  need(bindings['native_plan_sha256']==pin(encode(p))['sha256'],'same selected complete native plan')
  need(p['population']==catalogue()[operation]['population'],'all published/source population dimensions')
  need(p['science_review_status']=='independently_qualified','native scientific binding still unqualified')
  # The status is only a join: the live issuer must independently enforce the
  # actual review and whole native input closure in its require() implementation.
  self.authority.require('actual_scientific_binding:'+operation,self.authority.source_sha256)
  return p
 def value(self,x):
  if type(x) is dict and set(x)=={'admitted_input_path'}:
   relative(x['admitted_input_path']);p=self.input_root/x['admitted_input_path']
   self.authority.require('open_input:'+x['admitted_input_path'],self.authority.source_sha256)
   return ordinary(p)
  if type(x) is dict and set(x)=={'native_device'}:
   need(x['native_device'] is True,'native device selector');return self.device
  if type(x) is dict and set(x)=={'array_literal'}:
   import numpy as np
   need(type(x['array_literal']) is list and len(x['array_literal'])<=10000,'bounded parameter array')
   return np.asarray(x['array_literal'])
  if type(x) is dict:return {k:self.value(v) for k,v in x.items()}
  if type(x) is list:return [self.value(v) for v in x]
  need(x is None or type(x) in (str,int,float,bool),'ordinary argument literal')
  return x
 def bind_original_arguments(self,operation,bindings,module):
  import inspect
  p=self.plan(operation,bindings);args=self.value(p['args']);kwargs=self.value(p['kwargs'])
  name=p['function'];sig=inspect.signature(getattr(module,name));bound=sig.bind(*args,**kwargs);bound.apply_defaults()
  # Full-source dimensions are enforced where these are actual API parameters.
  for key,value in [('nn',10000),('NN',10000),('n_sim',10),('ncl',500)]:
   if key in bound.arguments:need(bound.arguments[key]==value,'no budget-sized replacement of '+key)
  if operation.startswith('memory_'):
   need(bound.arguments['niter']==20 and bound.arguments['nstim']*bound.arguments['nd']==2000,'original memory network/trial denominator')
   need(bound.arguments['dt']==2 and bound.arguments['tau']==20 and bound.arguments['magi']==2.5,'source memory dynamics')
   need(bound.arguments['mode']==('aligned' if operation=='memory_aligned' else 'independent'),'selected memory family')
  return args,kwargs
 def invoke(self,operation,bindings,module,name,args,kwargs):
  p=self.plan(operation,bindings);saved={};old_save=None
  if operation in ('noise_estimators','near_critical_examples','gcamp_comparison'):
   self.authority.require('exact_deconvolution_no_fallback:'+operation,self.authority.source_sha256)
  expected=p.get('saved_outputs',[])
  if expected:
   need(type(expected) is list and len(expected)==len(set(expected)) and len(expected)<=16,'finite literal saved-result names')
   old_save=module.np.save
   def capture(file,value,*extra,**kwargs0):
    name0=str(file);need(name0 in expected and name0 not in saved,'no unselected/repeated native save')
    need(not extra and set(kwargs0)<=set(('allow_pickle','fix_imports')),'original np.save API')
    # Source writes object dictionaries. Capture their actual values in the
    # already isolated worker instead of creating a pickle and loading it back.
    saved[name0]=value
   module.np.save=capture
  lifecycle=Custody('native_invoke:'+operation);result=None;returned=None
  try:
   result=getattr(module,name)(*args,**kwargs)
   if expected:
    need(result is None and set(saved)==set(expected),'complete original side-effect outputs')
    returned=saved
   else:returned=result
  except BaseException as exc:lifecycle.capture(exc,'original_kernel')
  if old_save is not None:lifecycle.attempt('restore_original_save',lambda:setattr(module.np,'save',old_save))
  self.last_saved_prefix=saved;self.last_invoke_custody=lifecycle
  lifecycle.raise_first();return returned
 def capture_original_result(self,operation,result,bindings):
  from .native_producer import NativeProducer
  producer=getattr(self,'active_producer',None)
  need(type(producer) is NativeProducer and producer.active and producer.operation==operation,'capture requires actual active source producer before any numerical work')
  p=self.plan(operation,bindings)
  from .derived import augment,fixed_bindings
  result=augment(operation,result)
  # Explicit selectors reference the literal returned tuple/dict. Every scored
  # scientific estimand must be mapped; ignored example artwork is separately listed.
  selected=p['outputs'];expected=catalogue()[operation]['estimands']
  need(set(selected)==set(expected),'all scientific estimands have output consumers')
  for estimand,parts in fixed_bindings(operation).items():need(selected[estimand]==parts,'exact selected original derived-output join: '+estimand)
  outputs={}
  for estimand,parts in selected.items():
   need(type(parts) is list and len(parts)>0,'nonempty estimand source selectors')
   for i,part in enumerate(parts):
    exact(part,('selector','shape','kind','spectrum') if part['kind']=='complex_pairs' else ('selector','shape','kind'),'output binding');value=result
    for key in part['selector']:value=value[key]
    import numpy as np
    a=value.detach().cpu().numpy() if hasattr(value,'detach') else np.asarray(value)
    if part['kind']=='complex_pairs':a=np.stack((a.real,a.imag),axis=-1)
    elif np.iscomplexobj(a):raise Refusal('complex source cannot be relabeled as ordered real values')
    if a.ndim==0:a=a.reshape(1)
    need(list(a.shape)==part['shape'],'complete original output geometry')
    name=estimand if len(parts)==1 else estimand+'/%04d'%i
    if operation=='dense_covariance' and estimand=='connectivity_eigenvalues':
     from .spectral import connectivity_name,connectivity_spec
     need(len(parts)==40 and part['selector']==['raw',i,'connectivity_eigenvalues'],'full original dense-network axis and exact raw eigenvalues')
     name=connectivity_name(i);need({k:part[k] for k in ('shape','kind','spectrum')}==connectivity_spec(i),'all forty exact 10000-mode geometries')
    outputs[name]=tensors.store_array(a,operation+'/'+estimand+'/%04d'%i,self.output_root,self.cost)
  from .reference_assembly import source_row
  row=source_row(operation,bindings,outputs)
  row['method_lineage']['derived_consumer']={'module':'critical/derived.py','operation':operation,'fixed_estimands':list(fixed_bindings(operation)),'semantics':'original raw outputs retained; explicitly transcribed figure consumers; covariance/timescale theory applies only to symmetric networks'}
  return producer.seal_capture(self,operation,row)
 def bind_dense(self,bindings):
  p=self.plan('dense_covariance',bindings);cfg=p['dense_config']
  need(set(cfg['seeds'])==set(map(str,(0,1/3,2/3,1))) and all(len(v)==10 for v in cfg['seeds'].values()),'complete declared seed lineage')
  return {**cfg,'device':self.device}
 def bind_dynamics(self,bindings):
  p=self.plan('simulated_dynamics',bindings);cfg=p['dynamics_config']
  need(cfg['seed']==0 and cfg['stream_policy']=='one_continuing_source_stream','literal Fig3 seed-0 lineage')
  return {**cfg,'device':self.device}
 def admitted_empirical_records(self,bindings):
  self.plan('empirical_dynamics',bindings)
  # The concrete legacy loader is retained, but authentic pickle/header access
  # and full geometry must be admitted by the actual data owner before use.
  from .empirical import records
  return records(self)
