"""Actual retinal model/training kernels; all native imports are call-local.

MIT author source: mackelab/jaxley_experiments@5e7a86282adb9d4603b5546ac5d8dad59aec7cc0.
Invocation requires the separately qualified original environment and assets.
"""
from .retina_inputs import require


def build_cell(ctx, morphology, soma_radius, platform):
    ctx.checkpoint()
    from jax import config
    config.update("jax_enable_x64", True)
    config.update("jax_platform_name", platform)
    import jaxley as jx
    from jaxley_mech.channels.fm97 import Na, K, Leak, KA, KCa, Ca, CaNernstReversal, CaPump
    cell = jx.read_swc(ctx.input_path(morphology), nseg=4, max_branch_len=300.0, min_radius=1.0, assign_groups=True)
    cell.set("axial_resistivity", 5000.0)
    for channel in (Na, K, Leak, KA, CaNernstReversal, CaPump, Ca, KCa):
        cell.insert(channel())
    cell.soma.set("Na_gNa", .15); cell.basal.set("Na_gNa", .05)
    cell.set("CaPump_taur", 100.0)
    cell.soma.set("radius", soma_radius); cell.soma.set("length", 2*soma_radius/4)
    cell.basal.set("radius", .2); cell.set("v", -69.0); cell.init_states()
    return cell


def kernel(time_vec, dt):
    import numpy as np
    import jax.numpy as jnp
    rise_time = np.arange(0, 5*5, dt); decay_time = np.arange(0, 3*100, dt)
    rise = 1 - np.exp(np.log(.5)/5*rise_time)
    decay = np.max(rise)*np.exp(np.log(.5)/100*decay_time)
    return jnp.asarray(np.concatenate([rise, decay])[:len(time_vec)])


def transforms():
    from jaxley import ParamTransform
    lower = {"Na_gNa":0.0,"K_gK":.01,"Leak_gLeak":1e-5,"KA_gKA":.01,"Ca_gCa":.002,"KCa_gKCa":.00002}
    upper = {"Na_gNa":.5,"K_gK":.1,"Leak_gLeak":1e-3,"KA_gKA":.1,"Ca_gCa":.003,"KCa_gKCa":.0002}
    soma = dict(lower); soma["Na_gNa"] = .05
    return (ParamTransform(lowers={"axial_resistivity":100,"radius":.1,"w_bc_to_rgc":0}, uppers={"axial_resistivity":10000,"radius":1.,"w_bc_to_rgc":.2}), ParamTransform(lowers=lower,uppers=upper), ParamTransform(lowers=soma,uppers=upper))


def initialize(ctx, cell, sites, connections, cfg, *, extra_voltage=False):
    ctx.checkpoint()
    import numpy as np
    import jax.numpy as jnp
    import jaxley as jx
    cell.delete_recordings(); cell.delete_stimuli(); cell.delete_trainables()
    for site in sites:
        cell.branch(site["branch"]).loc(site["comp"]).record("Cai", verbose=False)
    if extra_voltage:
        for site in sites:
            cell.branch(site["branch"]).loc(site["comp"]).record("v", verbose=False)
    basal = list(np.unique(cell.group_nodes["basal"]["branch_index"].to_numpy()))
    soma = list(np.unique(cell.group_nodes["soma"]["branch_index"].to_numpy()))
    _, states = jx.integrate(cell, t_max=5.0, return_states=True)
    cell.basal.branch("all").make_trainable("axial_resistivity")
    cell.basal.branch("all").make_trainable("radius")
    params = cell.get_parameters()
    t = cfg["training"]
    # Dedicated RandomState has the same MT19937 draw as source np.seed+rand;
    # no unrelated process-global RNG consumer may alter this explicit stream.
    rng = np.random.RandomState(t["seed_weights"] + t["seed_ruler"])
    params = [{"w_bc_to_rgc":.1*jnp.asarray(rng.rand(len(connections)))}] + params
    conductances = [{k:jnp.asarray(v)} for k,v in (("Na_gNa",.05),("K_gK",.05),("Leak_gLeak",1e-4),("KA_gKA",.036),("Ca_gCa",.0022),("KCa_gKCa",.00005))]
    transform = transforms()
    opt = (transform[0].inverse(params), transform[1].inverse(conductances), transform[2].inverse(conductances))
    time_vec = np.arange(0, 200+2*.025, .025)
    static = dict(cell=cell, dt=.025, t_max=200., time_vec=time_vec, num_truncations=4, output_scale=cfg["choices"]["output_scale"], output_offset=-1.3, kernel=kernel(time_vec,.025), basal_inds=basal, somatic_inds=soma, stim_branch_inds=[c["branch"] for c in connections], stim_comps=[c["comp"] for c in connections], transform=transform, n_sites=len(sites))
    return opt, states, static


def simulate_split(params, basal, soma, currents, all_states, static):
    import numpy as np
    import jax.numpy as jnp
    from jax.lax import stop_gradient
    import jaxley as jx
    all_states = stop_gradient(all_states)
    input_currents = params[0]["w_bc_to_rgc"] * currents
    steps = jx.datapoint_to_step_currents(0, static["t_max"]/4, input_currents, static["dt"], static["t_max"]/4)
    stimuli = None
    for branch, comp, current in zip(static["stim_branch_inds"], static["stim_comps"], steps):
        stimuli = static["cell"].branch(branch).loc(comp).data_stimulate(current, data_stimuli=stimuli)
    state = None
    for indices, values in ((static["basal_inds"], basal), (static["somatic_inds"], soma)):
        for item in values:
            name = next(iter(item))
            state = static["cell"][indices].data_set(name, item[name], param_state=state)
    length = int(np.ceil(np.sqrt(len(static["time_vec"])/4)))
    return jx.integrate(static["cell"], params=params[1:], param_state=state, data_stimuli=stimuli, checkpoint_lengths=[length,length], all_states=all_states, return_states=True)


def simulate(params, basal, soma, currents, states, static):
    import jax.numpy as jnp
    recordings = []
    for _ in range(4):
        v, states = simulate_split(params, basal, soma, currents, states, static)
        recordings.append(v[:, 1:])
    return jnp.concatenate(recordings, axis=1)


def predict(params, basal, soma, currents, states, static):
    import jax.numpy as jnp
    values = simulate(params, basal, soma, currents, states, static)
    values = values[:static["n_sites"], :len(static["kernel"])]
    return jnp.mean(jnp.flip(static["kernel"])*values, axis=1)*static["output_scale"]+static["output_offset"]


def physical(opt, static):
    return tuple(t.forward(p) for t,p in zip(static["transform"], opt))


def predict_all(ctx, opt, states, static, currents):
    ctx.checkpoint()
    import numpy as np
    from jax import jit, vmap
    from functools import partial
    fn = jit(vmap(partial(predict, static=static), in_axes=(None,None,None,0,None)))
    params = physical(opt, static)
    batches = []
    for start in range(0, len(currents), 1024):
        ctx.checkpoint()
        batches.append(np.asarray(fn(*params, currents[start:start+1024], states)))
    return np.concatenate(batches, axis=0)


def metrics(predictions, labels, mask):
    import numpy as np
    rows = []
    for site in range(labels.shape[1]):
        keep = mask[:,site].astype(bool); x=labels[keep,site]; y=predictions[keep,site]
        defined = len(x)>1 and np.std(x)>0 and np.std(y)>0
        rows.append(dict(site=site, count=int(len(x)), pearson=float(np.corrcoef(x,y)[0,1]) if defined else None, mae=float(np.mean(np.abs(x-y))) if len(x) else None, mse=float(np.mean((x-y)**2)) if len(x) else None, undefined=None if defined else "insufficient-or-constant-support"))
    # Undefined sites are not silently removed from the all-site mean.
    mean = float(np.mean([r["pearson"] for r in rows])) if all(r["pearson"] is not None for r in rows) else None
    return dict(sites=rows, mean_pearson=mean)


def train(ctx, cell, data, connections, cfg):
    """Source rounded full-epoch SGD; all evaluation/checkpoint lineage retained."""
    ctx.checkpoint()
    import math
    import numpy as np
    import jax.numpy as jnp
    import tensorflow as tf
    import optax
    from jax import jit, vmap, value_and_grad, tree_util
    from jaxley.optimize import TypeOptimizer
    from jaxley.optimize.utils import l2_norm
    opt, initial, static = initialize(ctx, cell, data["sites"], connections, cfg)
    t = cfg["training"]; n = len(data["labels"])
    require(t["test_num"]<n, "source test count")
    permutation = np.random.RandomState(t["seed_membrane"]+t["seed_ruler"]).permutation(np.arange(n))
    test_frac=t["test_num"]/n; val_frac=t["val_frac"]*(1-test_frac)
    num_train=int(n*(1-val_frac-test_frac))
    splits=dict(test=permutation[:t["test_num"]], train=permutation[t["test_num"]:t["test_num"]+num_train], val=permutation[t["test_num"]+num_train:])
    require(all(len(v)>0 for v in splits.values()), "nonempty splits")
    tf.random.set_seed(t["seed_tf_loader"]+t["seed_ruler"])
    tf.random.set_seed(1)  # original dataloader's overriding literal retained
    ds=tf.data.Dataset.from_tensor_slices((data["currents"][splits["train"]], data["labels"][splits["train"]], data["mask"][splits["train"]]))
    ds=ds.shuffle(len(splits["train"])).batch(t["batch_size"])
    batches=int(math.ceil(num_train/t["batch_size"])); epochs=int(math.ceil(t["iterations"]/batches))
    selected_epoch=cfg["choices"]["evaluation_checkpoint_epoch"]
    require(selected_epoch<=epochs, "evaluation checkpoint not produced by selected training")
    schedule=optax.piecewise_constant_schedule(t["lr"], {i*t["reduce_every"]:1/t["reduce_by"] for i in range(1,int(t["iterations"]/t["reduce_every"])+1)})
    factory=lambda _:optax.chain(optax.clip(10.0),optax.sgd(schedule,momentum=t["momentum"]))
    optimizers=(TypeOptimizer(factory,{"w_bc_to_rgc":t["lr"],"axial_resistivity":t["lr"],"radius":t["lr"]}),TypeOptimizer(factory,{k:t["lr"] for item in opt[1] for k in item}),optax.sgd(schedule,momentum=t["momentum"]))
    optimizer_states=tuple(o.init(p) for o,p in zip(optimizers,opt))
    def batch_loss(a,b,c,currents,labels,masks):
        pp=physical((a,b,c),static)
        p=vmap(lambda current:predict(*pp,current,initial,static))(currents)
        return jnp.mean(jnp.sum(masks*jnp.abs(p-labels),axis=1))
    gradient=jit(value_and_grad(batch_loss,argnums=(0,1,2)))
    tf.random.set_seed(t["seed_tf_loop"]+t["seed_ruler"])
    learning=[]; evaluations=[]; best_score=-1.; best=None; selected=None; step=0
    def evaluate(epoch, batch):
        nonlocal best_score,best
        result={}; preds={}
        for name in ("val","test","train"):
            inds=splits[name]; preds[name]=predict_all(ctx,opt,initial,static,data["currents"][inds])
            result[name]=metrics(preds[name],data["labels"][inds],data["mask"][inds])
        score=result["val"]["mean_pearson"]
        evaluations.append(dict(epoch=epoch,batch=batch,step=step,metrics=result))
        if score is not None and score>best_score:
            best_score=score; best=dict(opt=opt,metrics=result,predictions=preds,epoch=epoch,step=step)
    for epoch in range(epochs):
        if epoch==selected_epoch:selected=opt
        for batch, values in enumerate(ds):
            ctx.checkpoint(); current,label,mask=(v.numpy() for v in values)
            loss,grads=gradient(*opt,current,label,mask); gp,gb,gs=grads
            for i in range(3):
                norm=l2_norm(gp[i]); key=next(iter(gp[i])); count=len(gp[i][key])
                # No epsilon or guessed zero-gradient replacement.
                require(bool(np.asarray(norm)>0), "undefined source parameter gradient normalization")
                gp[i]=tree_util.tree_map(lambda x:x/norm**t["beta"]*count,gp[i])
            normalized=[gp]
            for g in (gb,gs):
                norm=l2_norm(g); require(bool(np.asarray(norm)>0), "undefined source channel gradient normalization")
                normalized.append(tree_util.tree_map(lambda x:x/norm**t["beta"]*6,g))
            new_params=[]; new_states=[]
            for optimizer,state,params,gradients in zip(optimizers,optimizer_states,opt,normalized):
                updates,state=optimizer.update(gradients,state);new_params.append(optax.apply_updates(params,updates));new_states.append(state)
            opt=tuple(new_params);optimizer_states=tuple(new_states);step+=1
            learning.append(dict(epoch=epoch,batch=batch,step=step,loss=float(loss)))
            if batch%t["eval_every"]==t["eval_every"]-1:evaluate(epoch,batch)
        evaluate(epoch,"epoch-end")
    if selected_epoch==epochs:selected=opt
    require(selected is not None and best is not None,"undefined checkpoint or best validation correlation")
    ctx.record("retina_training",dict(requested_iterations=t["iterations"],actual_steps=step,complete_epochs=epochs,selected_checkpoint_epoch=selected_epoch,best_validation_step=best["step"],split_counts={k:len(v) for k,v in splits.items()},loss="masked-L1-SUM-then-batch-MEAN",tf_loader_seed_override=1))
    return dict(selected=selected,final=opt,best=best,initial=initial,static=static,splits=splits,learning=learning,evaluations=evaluations)


def boundary_trajectory(ctx, opt, initial, static, currents):
    """Real state carry and derivative-reset witnesses at50/100/150ms."""
    ctx.checkpoint()
    import numpy as np
    import jax
    import jax.numpy as jnp
    from jax.flatten_util import ravel_pytree
    params=physical(opt,static); state=initial; traces=[];before=[];after=[];cuts=[];spec=[]
    for block in range(4):
        ctx.checkpoint()
        if block:
            flat,unravel=ravel_pytree(state)
            retained=jax.lax.stop_gradient(state); carried,_=ravel_pytree(retained)
            _,derivative=jax.jvp(lambda v:ravel_pytree(jax.lax.stop_gradient(unravel(v)))[0],(flat,),(jnp.ones_like(flat),))
            before.append(np.asarray(flat));after.append(np.asarray(carried));cuts.append(np.asarray(derivative))
            spec.append(dict(time_ms=50*block,tree=str(jax.tree_util.tree_structure(state)),leaves=[dict(shape=list(x.shape),dtype=str(x.dtype)) for x in jax.tree_util.tree_leaves(state)]))
        recorded,state=simulate_split(*params,currents,state,static);traces.append(np.asarray(recorded[:,1:]))
    ctx.record("retina_boundary_state_layout",spec)
    return np.stack(before),np.stack(after),np.stack(cuts),np.concatenate(traces,axis=1)
