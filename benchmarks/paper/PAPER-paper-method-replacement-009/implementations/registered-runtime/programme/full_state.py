"""Concrete empirical-state prior producers and separately named reconstruction.
The released source remains untouched; inference is offline whole-sequence.
"""
from pathlib import Path
from .domain import Refusal,MissingDefinition
from .full_plan import need

def source_module(path,expected):
 import importlib.util,hashlib
 from .native.io import read
 p=Path(path);raw=read(p,expected['bytes'],expected);need(len(raw)==expected['bytes']and hashlib.sha256(raw).hexdigest()==expected['sha256'],'exact original state module')
 spec=importlib.util.spec_from_file_location('trial_selected_state_'+expected['sha256'][:12],p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def original_fitted_prior(trials,definition,work):
 # All three literal source APIs are supported, but a future original target
 # recipe must explicitly select one; no block/probabilityLeft substitution.
 import pandas as pd,numpy as np
 from behavior_models.utils import format_data,format_input
 from behavior_models.models import ActionKernel,StimulusKernel
 need(definition['source_revision']is not None and definition['target_identity_source']is not None,'original prior source/version/target mapping')
 frame=pd.DataFrame(trials);side,stim,act,_=format_data(frame)
 if definition['model']=='optBay':
  module=source_module(definition['module_path'],definition['module_pin']);return np.asarray(module.optimal_Bayesian(act,side)).reshape(-1)
 need(definition['model']in('actKernel','stimKernel'),'fixed fitted prior family')
 root=Path(work);need(not root.exists(),'fresh prior fit output: no imported fitted state');root.mkdir(parents=True)
 stimuli,actions,sides=format_input([stim],[act],[side]);cls=ActionKernel if definition['model']=='actKernel'else StimulusKernel
 model=cls(path_to_results=root,session_uuids=definition['session'],mouse_name=definition['animal'],actions=actions,stimuli=stimuli,stim_side=sides,single_zeta=True)
 model.load_or_train(remove_old=False)
 signal=model.compute_signal(signal='prior',act=actions,stim=stimuli,side=sides)['prior']
 return np.asarray(signal).reshape(-1)

def empirical_bmm(training_sequences,config):
 import numpy as np,pymc3 as pm
 from hmmlearn.vhmm import VariationalCategoricalHMM
 need(training_sequences and all(s['session']!=config['target_session']for s in training_sequences),'non-target sessions only')
 labels=[1-np.asarray(s['truth'],dtype=int).reshape(-1)for s in training_sequences];ds=[np.asarray(s['decoder'],dtype=float).reshape(-1)for s in training_sequences]
 need(all(len(y)==len(d)and len(y)>1 for y,d in zip(labels,ds)),'matched full training sequences')
 # Separate lengths prevent fictitious transitions across recording boundaries.
 hmm=VariationalCategoricalHMM(n_components=3,n_iter=config['hmm_iterations'],tol=config['tolerance'],random_state=config['seed'])
 hmm.fit(np.concatenate(labels).reshape(-1,1),lengths=[len(y)for y in labels])
 need(hmm.monitor_.converged,'empirical HMM convergence')
 with pm.Model()as model:
  hyper=config['rate_hyperprior'];need(hyper['original_source']is not None,'hierarchical rate hyperprior is an original completing definition')
  if hyper['family']=='HalfNormal':
   rate_a=pm.HalfNormal('nu_a',sigma=hyper['scale'],shape=2);rate_b=pm.HalfNormal('nu_b',sigma=hyper['scale'],shape=2)
  elif hyper['family']=='Exponential':
   rate_a=pm.Exponential('nu_a',lam=hyper['rate'],shape=2);rate_b=pm.Exponential('nu_b',lam=hyper['rate'],shape=2)
  else:raise MissingDefinition('unrecovered original hierarchical rate hyperprior family')
  alpha=pm.Exponential('alpha',lam=rate_a,shape=(len(ds),2));beta=pm.Exponential('beta',lam=rate_b,shape=(len(ds),2))
  for i,(y,d)in enumerate(zip(labels,ds)):
   need(np.all((d>0)&(d<1)),'BMM decoder interior probability domain; no hidden clipping')
   pm.Beta('decoder_'+str(i),alpha=alpha[i,y],beta=beta[i,y],observed=d)
  trace=pm.sample(config['draws'],tune=config['tune'],chains=config['chains'],random_seed=config['seed'],return_inferencedata=False)
 return {'pi':hmm.startprob_posterior_.copy(),'a':hmm.transmat_posterior_.copy(),'phi':hmm.emissionprob_posterior_.copy(),
 'beta_a':trace.get_values('nu_a').mean(axis=0),'beta_b':trace.get_values('nu_b').mean(axis=0),
 'training_sessions':[s['session']for s in training_sequences],'sequence_lengths':[len(y)for y in labels],
 'recipe':'paper-method hierarchical prior reconstruction; hyperprior must be source-selected; numerical equivalence unqualified'}

def corrected_bmm_class(module):
 import numpy as np
 from scipy import stats
 class Corrected(module.Constrained_BMM_HMM):
  def bmm_neg_loglike(self,params):
   original=super().bmm_neg_loglike(params)
   lp=stats.dirichlet.logpdf(np.exp(list(self.pi.values())),self.pi_prior)
   for h in self.states:
    lp+=stats.dirichlet.logpdf(np.exp(list(self.a[h].values())),self.a_prior[h]);lp+=stats.dirichlet.logpdf(np.exp(list(self.phi[h].values())),self.phi_prior[h])
   lp+=stats.expon.logpdf(params[0],scale=1/self.beta_a_prior[0])+stats.expon.logpdf(params[3],scale=1/self.beta_b_prior[1])
   return original-2*lp
 return Corrected

def integer_keys(value):
 # JSON object keys are strings. Preserve the source's ordered numeric state
 # indices explicitly; no learned value is rewritten or inferred here.
 if isinstance(value,list):return [integer_keys(x)for x in value]
 if isinstance(value,dict):
  need(all(str(k).isdigit()for k in value),'explicit numeric state indices')
  return {int(k):integer_keys(v)for k,v in value.items()}
 return value

def bmm_fit(module,decoder,configuration,prior=None,recipe='paper_method_reconstruction'):
 import numpy as np
 d=np.asarray(decoder,dtype=float).reshape(-1);need(np.all((d>0)&(d<1)),'BMM interior probabilities')
 args=dict(configuration['initial_parameters']);args['d']=d
 for key in('init_pi','init_a','init_phi'):args[key]=integer_keys(args[key])
 if prior is None:model=module.BMM_HMM(**args)
 else:
  args.update(pi_prior=prior['pi'],a_prior=prior['a'],phi_prior=prior['phi'],beta_a_prior=prior['beta_a'],beta_b_prior=prior['beta_b'])
  cls=module.Constrained_BMM_HMM if recipe=='released_code'else corrected_bmm_class(module);model=cls(**args)
 model.update(d,cutoff=configuration['convergence_cutoff']);label,probability=module.posterior_inference(model,d)
 return np.asarray(probability).reshape(-1,1),model

def empirical_lg(training_sequences,configuration):
 import numpy as np,pymc3 as pm
 need(training_sequences and all(s['session']!=configuration['target_session']for s in training_sequences),'LG prior held-session exclusion')
 # Variable-length sequences remain distinct; no truncation to shortest session.
 with pm.Model()as model:
  rho=pm.Normal('rho',mu=0.,sigma=1.);xi=pm.HalfNormal('xi',sigma=1.);theta=pm.Normal('theta',mu=1.,sigma=1.);mu=pm.Normal('mu',mu=0.,sigma=1.);eps=pm.HalfNormal('eps',sigma=1.)
  for i,s in enumerate(training_sequences):
   y=np.asarray(s['truth']).reshape(-1);d=np.asarray(s['decoder']).reshape(-1);need(len(y)==len(d),'LG training coordinate')
   pm.AR1('behavior_'+str(i),k=rho,tau_e=1/xi,observed=y)
   pm.Normal('decoder_'+str(i),mu=mu+theta*y,sigma=eps,observed=d)
  trace=pm.sample(configuration['draws'],tune=configuration['tune'],chains=configuration['chains'],random_seed=configuration['seed'],return_inferencedata=False)
 return {k:float(trace.get_values(k).mean())for k in('rho','xi','theta','mu','eps')}

def lg_fit(decoder,configuration,prior=None):
 import numpy as np,pymc3 as pm
 d=np.asarray(decoder).reshape(-1)
 with pm.Model()as model:
  if prior is None:
   rho=pm.Normal('rho',0.,1.);xi=pm.HalfNormal('xi',1.);theta=pm.Normal('theta',1.,1.);mu=pm.Normal('mu',0.,1.);eps=pm.HalfNormal('eps',1.)
  else:rho,xi,theta,mu,eps=[prior[k]for k in('rho','xi','theta','mu','eps')]
  state=pm.AR1('state',k=rho,tau_e=1/xi,shape=len(d))
  pm.Normal('obs',mu=mu+theta*state,sigma=eps,observed=d)
  trace=pm.sample(configuration['draws'],tune=configuration['tune'],chains=configuration['chains'],random_seed=configuration['seed'],return_inferencedata=False)
  pred=pm.sample_posterior_predictive(trace,var_names=['obs'],random_seed=configuration['seed'])
 return np.asarray(pred['obs']).mean(axis=0).reshape(-1,1),trace

def oracle_bmm(module,truth,decoder,configuration):
 import numpy as np
 from scipy.stats import beta
 labels=(1-np.asarray(truth,dtype=int).reshape(-1));d=np.asarray(decoder,dtype=float).reshape(-1)
 need(len(labels)==len(d)and np.all((d>0)&(d<1)),'oracle complete conditional beta support')
 hmm=module.HMM(integer_keys(configuration['hmm_initial_log_probabilities']));hmm.update(labels.tolist(),configuration['convergence_cutoff'])
 pars=[]
 for z in(0,1):
  values=d[labels==z];need(len(values)>1,'oracle both mixture components')
  a,b,_,_=beta.fit(values,floc=0,fscale=1);pars.append((a,b))
 model=module.Oracle_BMM_HMM(d,hmm.pi,hmm.a,hmm.b,[p[0]for p in pars],[p[1]for p in pars])
 # Oracle parameters stay fixed; the original posterior routine only infers
 # latent states/choice probabilities from the actual decoder sequence.
 _,probability=module.posterior_inference(model,d)
 return np.asarray(probability).reshape(-1,1),{'pi':list(hmm.pi.values()),'a':[list(v.values())for v in hmm.a.values()],
  'phi':[list(v.values())for v in hmm.b.values()],'beta_a':[p[0]for p in pars],'beta_b':[p[1]for p in pars]}
