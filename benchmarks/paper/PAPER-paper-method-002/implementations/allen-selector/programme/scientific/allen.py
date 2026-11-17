"""Complete four-cell Allen GD/IBEA family, original source versus paper profiles.

All imports with numerical/native effects occur only inside future run functions.
The missing historical figure-assembly notebook is not recreated by assumption.
"""
from .technical_support.contracts import admit,require,complete,ALLEN,emit,bounded_extents
from .allen_source_selector import bind_job,publish

def schedule():
 rows=[]
 for specimen in ALLEN:
  rows.extend([{'specimen':specimen,'algorithm':'GD','budget':'high','seed':0,'particles':1000,'steps':50},
               {'specimen':specimen,'algorithm':'GA','budget':'high','seed':0,'particles':1000,'steps':50},
               {'specimen':specimen,'algorithm':'GD','budget':'low','seed':42,'particles':10,'steps':10}])
  rows.extend({'specimen':specimen,'algorithm':'GA','budget':'low','seed':seed,'particles':10,'steps':10}for seed in range(10))
 return rows

def preprocess(time,stimulus,response,t_max):
 """Literal source sampling/junction/epoch projection from safe arrays, no pickle."""
 import numpy as np
 require(time.ndim==stimulus.ndim==response.ndim==1 and time.shape==stimulus.shape==response.shape,'original three-array ephys support')
 require(len(time)>1 and np.all(np.diff(time)>0),'original monotonic seconds clock')
 dt_stim=np.mean(np.diff(time));stride=int(.025/dt_stim/1000)
 require(stride>=1,'source stride rounds to zero')
 st=stimulus[::stride];rec=response[::stride]-14.;clock=time[::stride]
 onset=np.where(st>.05)[0];offset=np.where(st<.05)[0];offset=offset[offset>20000]
 require(len(onset)>0 and len(offset)>0,'source stimulus onset/offset unavailable')
 start=int(onset[0]-50/.025);end=int(offset[0]+150/.025);cut=int((t_max+.05)/.025)
 require(0<=start<end<=len(st)and cut<=end-start,'full selected Allen epoch unavailable; no negative indexing/truncation')
 amplitude=float(np.max(st[start:end]));clock=clock[start:end]*1000;clock-=clock[0]
 return clock[:cut],rec[start:end][:cut],amplitude,{'stride':stride,'start':start,'end':end,'cutoff':cut,'dt_seconds_observed':float(dt_stim),'junction_mV':-14.}

def loss_factory(observed,predict,penalty):
 import jax,jax.numpy as jnp
 from .technical_support.allen_loss import soft_dtw_distance,window_reduce
 reduced=window_reduce(observed,jnp.max,stride=30,window_size=50)
 lo=jnp.min(reduced);hi=jnp.max(reduced)
 require(bool(hi>lo),'flat observed window scale is undefined')
 target=(reduced-lo)/(hi-lo)
 require(penalty in('source_normalized_index','paper_unscaled_index'),'explicit unresolved source/paper time penalty')
 cost=lambda x,y:jnp.abs(x-y)
 distance=lambda rows,cols:jnp.abs(rows-cols)/(target.shape[0]if penalty=='source_normalized_index'else 1.)
 self_target=soft_dtw_distance(target,target,gamma=.1,cost_fn=cost,penalty_fn=distance)
 def trace_loss(trace):
  value=window_reduce(trace,jnp.max,stride=30,window_size=50);value=(value-lo)/(hi-lo)
  a=soft_dtw_distance(value,target,gamma=.1,cost_fn=cost,penalty_fn=distance)
  b=soft_dtw_distance(value,value,gamma=.1,cost_fn=cost,penalty_fn=distance)
  return (a-.5*b-.5*self_target)/.05
 return jax.jit(lambda params:trace_loss(predict(params)))

def gd(ctx,job,predict,observed,lower,upper,transform,inverse):
 import jax,jax.numpy as jnp,numpy as np,optax
 from .technical_support.observations import measure
 seed=job['seed'];n=job['particles'];steps=job['steps']
 loss=loss_factory(observed,lambda z:predict(inverse(z)),ctx.config['time_penalty'])
 init,_=jax.random.split(jax.random.PRNGKey(seed))
 params=jax.vmap(lambda key:transform(jax.random.uniform(key,shape=lower.shape,minval=lower,maxval=upper)))(jax.random.split(init,n))
 require(bool(jnp.all(jnp.isfinite(params))),'uniform boundary creates nonfinite normal transform')
 initial=params;best=params;best_loss=jnp.full((n,),1e10)
 optimizer=optax.inject_hyperparams(optax.sgd)(learning_rate=.05,momentum=0.)
 state=jax.vmap(optimizer.init)(params);vg=jax.jit(jax.vmap(jax.value_and_grad(loss)))
 history=[];resources=[]
 for epoch in range(steps):
  (values,grad),obs=measure(ctx,vg,params);resources.append({'epoch':epoch,**obs})
  ctx.record('completed_operation',{'kind':'trajectory_gradient','count':n,'coordinate':[job['specimen'],job['algorithm'],job['budget'],job['seed'],epoch]})
  require(bool(jnp.all(jnp.isfinite(values)))and bool(jnp.all(jnp.isfinite(grad))),'nonfinite GD values retain failed attempt')
  improved=values<best_loss;best_loss=jnp.where(improved,values,best_loss);best=jnp.where(improved[:,None],params,best)
  norms=jnp.sqrt(jnp.sum(grad*grad,axis=1))
  require(bool(jnp.all(norms>0)),'literal GD zero norm is undefined; no silent epsilon')
  normalized=grad/norms[:,None]**.99
  state.hyperparams['learning_rate']=values*.0005
  updates,state=jax.vmap(optimizer.update)(normalized,state)
  history.append({'epoch':epoch,'parameters':np.asarray(inverse(params)).tolist(),'loss':np.asarray(values).tolist(),'best_loss':np.asarray(best_loss).tolist(),'gradient_norm':np.asarray(norms).tolist(),'updates_untransformed':np.asarray(updates).tolist()})
  params=jax.vmap(optax.apply_updates)(params,updates)
 # Terminal evaluation is additional complete-output evidence, not an original
 # best-selection update. Source best excludes the final post-update state.
 final_loss=jax.vmap(loss)(params)
 ctx.record('completed_operation',{'kind':'trajectory_forward','count':n,'coordinate':[job['specimen'],job['algorithm'],job['budget'],job['seed'],'terminal_loss']})
 candidates=jnp.concatenate([inverse(best),inverse(params)],axis=0)
 lineage={'initial_untransformed':np.asarray(initial).tolist(),'best_indices':list(range(n)),
          'terminal_indices':list(range(n,2*n)),'best_loss':np.asarray(best_loss).tolist(),'terminal_loss':np.asarray(final_loss).tolist(),
          'low_budget_source_named_median_index':int(jnp.argmin(best_loss))if job['budget']=='low'else None,
          'source_named_median_is_actual_argmin':job['budget']=='low','history':history}
 return candidates,lineage,resources

def ga(ctx,job,predict,observed,names,lower,upper):
 import jax,jax.numpy as jnp,numpy as np,bluepyopt as bpopt
 from bluepyopt.parameters import Parameter
 from .technical_support.observations import measure
 loss=loss_factory(observed,predict,ctx.config['time_penalty']);evaluations=[];resources=[]
 batch=jax.jit(jax.vmap(loss))
 class Evaluator(bpopt.evaluators.Evaluator):
  def __init__(self):super().__init__(objectives=['loss'],params=[Parameter(n,bounds=[float(l),float(u)])for n,l,u in zip(names,lower,upper)])
  def init_simulator_and_evaluate_with_lists(self,parameter_list):
   values,obs=measure(ctx,batch,jnp.asarray(parameter_list));resources.append(obs)
   ctx.record('completed_operation',{'kind':'trajectory_forward','count':len(parameter_list),'coordinate':[job['specimen'],job['algorithm'],job['budget'],job['seed'],len(evaluations)]})
   require(bool(jnp.all(jnp.isfinite(values))),'nonfinite GA objective')
   evaluations.append({'evaluation':len(evaluations),'parameters':np.asarray(parameter_list).tolist(),'loss':np.asarray(values).tolist()})
   return values[:,None].tolist()
 def batch_map(evaluate,parameters):return evaluate(list(parameters))
 optimizer=bpopt.deapext.optimisations.IBEADEAPOptimisation(Evaluator(),offspring_size=job['particles'],map_function=batch_map,seed=job['seed'],eta=10,mutpb=1.,cxpb=1.)
 final,hof,log,history=optimizer.run(max_ngen=job['steps'])
 final=jnp.asarray(final);hof=jnp.asarray(hof)
 require(final.shape==(job['particles'],25)and hof.ndim==2 and hof.shape[1]==25,'complete final population and HOF')
 # Retain every returned HOF member; original posthoc slice selects at most10.
 candidates=jnp.concatenate([final,hof]);n=len(final)
 lineage={'final_indices':list(range(n)),'hof_indices':list(range(n,len(candidates))),
          'source_posthoc_indices':list(range(max(0,len(candidates)-n-10),len(candidates))),
          'genealogy_tree':{str(k):list(v)for k,v in getattr(history,'genealogy_tree',{}).items()},
          'genealogy_history':{str(k):list(map(float,v))for k,v in getattr(history,'genealogy_history',{}).items()},
          'generation_log':[dict(x)for x in log],'evaluations':evaluations}
 require(lineage['evaluations']and lineage['generation_log'],'complete GA lineage unavailable')
 return candidates,lineage,resources

def summaries(traces,observed,specimen,profile):
 import numpy as np
 from .technical_support.allen_spikes import find_spikes,spike_count,first_spike_time,second_spike_time,first_spike_amp,second_spike_amp
 threshold=-30. if specimen=='473601979'else-20.
 # Exact source observation-only jitter, retained as a named operation.
 jitter=np.random.RandomState(0).randn(len(observed))*.01
 def one(trace,mask_trace):
  mask=np.asarray(find_spikes(mask_trace,None,None,threshold))
  return {'count':int(spike_count(mask)),'times_ms':[float(first_spike_time(mask)),float(second_spike_time(mask))],
          'amplitudes_mV':[float(first_spike_amp(trace,mask)),float(second_spike_amp(trace,mask))],
          'all_spike_indices':np.where(mask)[0].tolist()}
 target=one(observed,observed+jitter);rows=[]
 weights=[5.,2.,2.,1.,1.]if profile=='source_literal'else[1.,1.,1.,1/3,1/3]
 t=np.asarray([target['count']]+target['times_ms']+target['amplitudes_mV'])
 for trace in traces:
  row=one(trace,trace);x=np.asarray([row['count']]+row['times_ms']+row['amplitudes_mV'])
  row['absolute_errors']=np.abs(x-t).tolist();row['weighted_error']=float(np.dot(np.abs(x-t),weights));rows.append(row)
 return target,rows,weights

def run(ctx):
 c=admit(ctx);require(ctx.group=='J11','closed Allen group')
 require(c.get('compatibility')=='jaxley_0.8.2_dimensional_v1','root-selected explicit dimensional compatibility profile')
 require(c['time_penalty']=='source_normalized_index'if c['profile']=='source_literal'else c['time_penalty']in('source_normalized_index','paper_unscaled_index'),'selected time penalty')
 import jax,jax.numpy as jnp,numpy as np
 from .technical_model import api
 from .technical_support.allen_model import build
 from .technical_support.observations import measure
 api();require(jax.config.jax_enable_x64,'original Allen double precision must be selected before module initialization')
 roster=complete(ctx.read_json('allen_sources'),ALLEN,'specimen')
 fit_duration=199.5 if c['profile']=='source_literal'else 200.
 long_duration=1100. if c['profile']=='source_literal'else 1150.
 # Whole-family numeric storage floor, before any native fit. This excludes
 # Python/JSON and compiler allocator overhead, which the real parent must bound.
 trace_steps=int((fit_duration+.05)/.025)+int((long_duration+.05)/.025)
 minimum_candidates=sum(j['particles']*(2 if j['algorithm']=='GD'else 1)for j in schedule())
 bounded_extents(ctx,{'whole_family_trace_storage_floor':minimum_candidates*trace_steps*8})
 retained_trace_bytes=0;selector_retained_bytes=0
 full=[];losses=[];counts=[];times=[];amplitudes=[];lineages=[];resources=[]
 for job in schedule():
  ctx.checkpoint();specimen=job['specimen'];source=roster[specimen]
  raw_time=ctx.read_array(source['time']);stimulus=ctx.read_array(source['stimulus']);response=ctx.read_array(source['response'])
  fit_clock,fit_target,amp,fit_projection=preprocess(raw_time,stimulus,response,fit_duration)
  long_clock,long_target,amp2,long_projection=preprocess(raw_time,stimulus,response,long_duration)
  require(amp==amp2,'same full original stimulus amplitude')
  path=ctx.input_path(source['morphology']);cell,setup,names,lower,upper,transform_factory=build(specimen,path,amp)
  require(len(names)==25,'full19conductance/kinetic plus6global Allen parameter count')
  setup_sim=setup(cell,fit_duration);predict=jax.jit(lambda p:setup_sim(p)[0])
  require(jax.eval_shape(predict,lower).shape==fit_target.shape,'actual predicted clock versus observed support before fitting')
  transform,inverse=transform_factory(lower,upper)
  if job['algorithm']=='GD':candidates,lineage,observations=gd(ctx,job,predict,jnp.asarray(fit_target),lower,upper,transform,inverse)
  else:candidates,lineage,observations=ga(ctx,job,predict,jnp.asarray(fit_target),names,lower,upper)
  # Guard complete retained traces, not just the most favorable single trace.
  bounded_extents(ctx,{'full_short_long_traces':len(candidates)*(len(fit_clock)+len(long_clock))*8,'all_candidates':int(candidates.size)*8})
  retained_trace_bytes+=len(candidates)*(len(fit_clock)+len(long_clock))*8
  selector_retained_bytes+=len(candidates)*2048+16384
  bounded_extents(ctx,{'cumulative_full_family_trace_storage':retained_trace_bytes,'selector_retained_bound':selector_retained_bytes,
                       'selector_transient_bound':len(candidates)*2048+(len(fit_clock)+len(long_clock))*128+16384})
  short,short_obs=measure(ctx,jax.jit(jax.vmap(predict)),candidates)
  long_cell,long_setup,_,_,_,_=build(specimen,path,amp);long_sim=long_setup(long_cell,long_duration)
  long,post_obs=measure(ctx,jax.jit(jax.vmap(lambda p:long_sim(p)[0])),candidates)
  ctx.record('completed_operation',{'kind':'trajectory_forward','count':len(candidates)*2,'coordinate':[specimen,job['algorithm'],job['budget'],job['seed'],'complete_short_and_long']})
  require(short.shape==(len(candidates),len(fit_clock))and long.shape==(len(candidates),len(long_clock)),'full exact clock/trace join; incompatible library endpoint refuses')
  loss=loss_factory(jnp.asarray(fit_target),predict,c['time_penalty']);candidate_losses=jax.vmap(loss)(candidates)
  ctx.record('completed_operation',{'kind':'trajectory_forward','count':len(candidates),'coordinate':[specimen,job['algorithm'],job['budget'],job['seed'],'candidate_losses']})
  target,stats,weights=summaries(np.asarray(long),np.asarray(long_target),specimen,c['profile'])
  key={**job,'profile':c['profile']}
  full.append({**key,'fit_clock_ms':fit_clock.tolist(),'long_clock_ms':long_clock.tolist(),'fit_target':fit_target.tolist(),'long_target':long_target.tolist(),'fit_voltage':np.asarray(short).tolist(),'long_voltage':np.asarray(long).tolist()})
  losses.append({**key,'candidate_losses':np.asarray(candidate_losses).tolist(),'time_penalty':c['time_penalty'],'scale':.05,'gamma':.1})
  counts.append({**key,'target':target['count'],'candidates':[r['count']for r in stats]})
  times.append({**key,'target':target['times_ms'],'candidates':[r['times_ms']for r in stats],'all_candidate_spike_indices':[r['all_spike_indices']for r in stats]})
  amplitudes.append({**key,'target':target['amplitudes_mV'],'candidates':[r['amplitudes_mV']for r in stats]})
  lineages.append({**key,'names':names,'bounds':np.stack([np.asarray(lower),np.asarray(upper)],axis=1).tolist(),'candidates':np.asarray(candidates).tolist(),'fit_projection':fit_projection,'long_projection':long_projection,
                   'optimizer':lineage,'posthoc_errors':[r['absolute_errors']for r in stats],'posthoc_weighted_errors':[r['weighted_error']for r in stats],'posthoc_weights':weights,'posthoc_best_index':int(np.argmin([r['weighted_error']for r in stats]))})
  resources.append({**key,'iterations':observations,'complete_short':short_obs,'complete_long':post_obs})
  bind_job(ctx,source,dict(zip(('full_voltage','soft_DTW','spike_count','spike_times','spike_amplitudes','best_final_hof_lineage','resource_trajectory'),
                             (full[-1],losses[-1],counts[-1],times[-1],amplitudes[-1],lineages[-1],resources[-1]))))
 require(len(full)==52,'complete four-cell high/low GD and all ten low GA seeds')
 publish(ctx,dict((('full_voltage',full),('soft_DTW',losses),('spike_count',counts),('spike_times',times),('spike_amplitudes',amplitudes),('best_final_hof_lineage',lineages),('resource_trajectory',resources))),roster,schedule())
