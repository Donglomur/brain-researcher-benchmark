"""Concrete full J10 source/paper fitting profiles, implemented but not executed.

Numeric definition follows authenticated notebook cells 15,17,22,29–35,39.
Source SUM and paper MEAN are distinct; no threshold/step equivalence is claimed.
"""
from runtime.strict import require

PROFILES=('J10_SOURCE_SUM_5e7a862','J10_PAPER_MEAN_SEC18')

def support(config):
    require(config['profile']in PROFILES,'selected summary loss convention')
    require(config['conductance_unit']=='S/cm^2','main source conductance units; supplement conflict remains')
    require(config['gd_seeds']==list(range(42,52))and config['ga_seeds']==list(range(10)),'full literal ten-run rosters')
    require(config['random_seed']==1 and config['random_batches']==100 and config['random_batch_size']==100,'complete original random-search baseline')
    require(config['steps']==10 and config['generations']==10 and config['offspring']==10,'complete GD/GA workload')
    require(config['threshold_convention']=='source_sum_0.55_only','no transfer of literal threshold to a new scale')
    return config

def run(ctx):
    require(ctx.group=='J10'and ctx.action=='complete_reference','fixed synthetic reference action')
    cfg=support(ctx.config);ctx.checkpoint()
    import time
    from copy import deepcopy
    import numpy as np
    import jax
    import jax.numpy as jnp
    from jax.tree_util import tree_map
    import optax
    import bluepyopt as bpopt
    from bluepyopt.parameters import Parameter
    from .synthetic_model import build
    model=build(ctx.input_path('l5pc_morphology'))
    bounds=model['bounds'];order=model['parameter_order'];simulate=model['simulate'];many=model['simulate_many']
    require(tuple(cfg['parameter_order'])==order,'original ordered nineteen parameter identities')
    widths=jnp.asarray([bounds[k][1]-bounds[k][0]for k in order]);lowers=jnp.asarray([bounds[k][0]for k in order])
    transform=__import__('jaxley').ParamTransform(lowers={k:bounds[k][0]for k in order},uppers={k:bounds[k][1]for k in order})
    counts={'ground_truth':0,'random_search':0,'gd_gradient':0,'gd_best_trace':0,'ga_evaluations':0,'ga_selected_trace':0}
    ctx.checkpoint();ground=model['simulate_ground_truth']();counts['ground_truth']+=1
    require(ground.ndim==2 and ground.shape[0]==1 and ground.shape[1]==len(model['time']),'native complete voltage/time coordinate')
    windows=(slice(200,2200),slice(2200,3800));factors=jnp.asarray([8.,4.,8.,4.])
    def summaries(v):
        return jnp.stack(tuple(x for w in windows for x in(jnp.mean(v[0,w]),jnp.std(v[0,w]))))
    observed=summaries(ground)
    def source_error(v):return jnp.sum(jnp.abs((summaries(v)-observed)/factors))
    def objective(v):
        raw=source_error(v)
        return raw if cfg['profile']==PROFILES[0]else raw/4.
    def from_unconstrained(parameters):
        physical=transform.forward(parameters)
        return objective(simulate([list(p.values())[0]for p in physical]))
    gradient=jax.jit(jax.value_and_grad(from_unconstrained))
    error_many=jax.jit(jax.vmap(objective));source_many=jax.jit(jax.vmap(source_error))
    def physical_init(rng):
        return [{k:jnp.asarray(rng.rand(1)*(bounds[k][1]-bounds[k][0])+bounds[k][0])}for k in order]
    def flatten(parameters):return jnp.concatenate([jnp.atleast_1d(p[k])for p,k in zip(parameters,order)])
    random_params=[];random_traces=[];random_losses=[];random_source_losses=[]
    rng=np.random.RandomState(1)
    for batch in range(100):
        ctx.checkpoint();pars=jnp.stack([flatten(physical_init(rng))for _ in range(100)])
        traces=many(pars);counts['random_search']+=100
        random_params.append(pars);random_traces.append(traces);random_losses.append(error_many(traces));random_source_losses.append(source_many(traces))
    gd_params=[];gd_traces=[];gd_history=[];gd_initial=[]
    for seed in cfg['gd_seeds']:
        ctx.checkpoint();initial=physical_init(np.random.RandomState(seed));u=transform.inverse(initial);gd_initial.append(flatten(initial))
        optimizer=optax.inject_hyperparams(optax.sgd)(learning_rate=3.0);state=optimizer.init(u)
        best=None;best_value=float('inf');history=[]
        for epoch in range(10):
            ctx.checkpoint();value,g=gradient(u);counts['gd_gradient']+=1
            norm=jnp.sqrt(sum(jnp.sum(jnp.square(x))for x in jax.tree_util.tree_leaves(g)))
            require(bool(jnp.isfinite(value))and bool(jnp.isfinite(norm))and float(norm)>0,'native zero/nonfinite gradient has no selected continuation')
            history.append(float(value))
            if float(value)<best_value:best=deepcopy(u);best_value=float(value)
            normalized=tree_map(lambda x:x/norm**.8,g)
            state.hyperparams['learning_rate']=value/3.
            updates,state=optimizer.update(normalized,state);u=optax.apply_updates(u,updates)
        require(best is not None,'best GD state absent')
        physical=transform.forward(best);vector=flatten(physical);trace=simulate([p[k]for p,k in zip(physical,order)])
        counts['gd_best_trace']+=1;gd_params.append(vector);gd_traces.append(trace)
        gd_history.append({'seed':seed,'pre_update_losses':history,'best_loss':best_value,'best_includes_final_post_update':False,'source_plot_filter_loss_lt1':best_value<1.,'all_runs_retained':True})
    ga_params=[];ga_traces=[];ga_history=[]
    for seed in cfg['ga_seeds']:
        ctx.checkpoint();calls=[];all_candidates=[]
        class Evaluator(bpopt.evaluators.Evaluator):
            def __init__(self):super().__init__(objectives=['loss'],params=[Parameter(k,bounds=bounds[k])for k in order])
            def init_simulator_and_evaluate_with_lists(self,values):
                ctx.checkpoint();v=jnp.asarray(values);traces=many(v);losses=error_many(traces)
                counts['ga_evaluations']+=len(values)
                require(bool(jnp.isfinite(losses).all()),'native GA nonfinite objective')
                calls.append({'evaluations':len(values),'losses':np.asarray(losses).tolist()})
                all_candidates.extend(zip(np.asarray(losses).tolist(),np.asarray(v).tolist()))
                return np.asarray(losses)[:,None].tolist()
        def mapped(fn,values):return fn(values)
        optimizer=bpopt.deapext.optimisations.IBEADEAPOptimisation(Evaluator(),offspring_size=10,map_function=mapped,seed=seed,eta=10,mutpb=1.,cxpb=1.)
        ctx.checkpoint();final,hof,log,hist=optimizer.run(max_ngen=10)
        require(all_candidates,'GA returned no evaluations')
        best=min(all_candidates,key=lambda x:x[0]);vector=jnp.asarray(best[1]);trace=simulate(vector)
        counts['ga_selected_trace']+=1;ga_params.append(vector);ga_traces.append(trace)
        ga_history.append({'seed':seed,'complete_evaluation_calls':calls,'best_observed_loss':best[0],'selected_rule':'minimum of every actual evaluated individual; extra full-trace export, not original hall-of-fame claim','final_population':[list(map(float,p))for p in final],'hall_of_fame':[list(map(float,p))for p in hof]})
    ctx.checkpoint()
    parameters=jnp.concatenate((model['true_values'][None,:],jnp.concatenate(random_params),jnp.stack(gd_params),jnp.stack(ga_params)))
    traces=jnp.concatenate((ground[None,:,:],jnp.concatenate(random_traces),jnp.stack(gd_traces),jnp.stack(ga_traces)))
    require(parameters.shape[0]==10021 and traces.shape[0]==10021,'complete baseline and fit support')
    ctx.emit_numeric('full_voltage',traces);ctx.emit_numeric('parameters',parameters)
    ctx.emit_numeric('four_summaries',jax.vmap(summaries)(traces))
    ctx.emit_json('loss_trajectory',{'profile':cfg['profile'],'GD':gd_history,'GA':ga_history,'random_loss':np.asarray(jnp.concatenate(random_losses)).tolist(),'parameter_order':list(order),'ordering':'ground_truth;10000random source order;GDseeds42..51;GAseeds0..9'})
    ctx.emit_json('simulation_count',{'returned_known_calls':counts,'prior_compile_dispatch_and_failures':'original native observer remains required; these are not full cost measurements'})
    raw=jnp.concatenate(random_source_losses);success=int(jnp.sum(raw<.55))
    ctx.emit_json('time_to_055',{'source_sum_threshold':.55,'random_successes':success,'random_evaluations':10000,'expected_simulations':10000/success if success else None,'status':'known_descriptive_source_sum_only'if success else'unavailable_no_success','measured_time':None,'reason':'Notebook ratio is expected simulation count, not an observed time-to-threshold; hardware timing remains separately unqualified'})
