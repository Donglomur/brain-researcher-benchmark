"""Exact frozen full-fit bootstrap span; return bundle is observational."""
from model_operation import configure_model_runtime, initialize_model, observed_source_split, require

def initialize_fit(arrays, meta, morphology_prefix):
    import numpy as np
    configure_model_runtime()
    import jax.numpy as jnp
    from jax import tree_map
    import tensorflow as tf
    from tensorflow.data import Dataset
    import optax
    from jaxley.optimize import TypeOptimizer
    from jaxley.optimize.utils import l2_norm

    opt, states, predict, gradient, _ = initialize_model(arrays, meta, morphology_prefix)
    tf.random.set_seed(0)
    rng = observed_source_split(meta)
    train_ids = np.asarray(meta["splits"]["train"], dtype=np.int64)
    val_ids = np.asarray(meta["splits"]["val"], dtype=np.int64)
    tf.random.set_seed(1)
    dataloader = Dataset.from_tensor_slices((arrays["images"][train_ids], arrays["currents"][train_ids],
                                            arrays["train_targets"], arrays["mask"][train_ids]))
    dataloader = dataloader.shuffle(dataloader.cardinality()).batch(256)
    val_loader = Dataset.from_tensor_slices((arrays["images"][val_ids], arrays["currents"][val_ids],
                                           arrays["val_targets"], arrays["mask"][val_ids])).batch(1024)
    require(int(dataloader.cardinality()) == 48, "source batch count")
    scheduler = optax.piecewise_constant_schedule(init_value=0.01, boundaries_and_scales={350: 0.1, 700: 0.1})
    optimizer_params = TypeOptimizer(lambda lr: optax.chain(optax.clip(10.0), optax.sgd(scheduler, momentum=0.5)),
                                    {"w_bc_to_rgc": 0.01, "axial_resistivity": 0.01, "radius": 0.01}, opt_params=opt[0])
    optimizer_basal = TypeOptimizer(lambda lr: optax.chain(optax.clip(10.0), optax.sgd(scheduler, momentum=0.5)),
                                   {k: 0.01 for k in ("Na_gNa", "K_gK", "Leak_gLeak", "KA_gKA", "Ca_gCa", "KCa_gKCa")}, opt[1])
    optimizer_somatic = optax.sgd(scheduler, momentum=0.5)
    optimizers = (optimizer_params, optimizer_basal, optimizer_somatic)
    optimizer_states = tuple(optimizer.init(group) for optimizer, group in zip(optimizers, opt))
    tf.random.set_seed(0)
    return {"opt": opt, "states": states, "predict": predict, "gradient": gradient, "static": _,
            "rng": rng, "train_ids": train_ids, "val_ids": val_ids, "dataloader": dataloader,
            "val_loader": val_loader, "optimizers": optimizers, "optimizer_states": optimizer_states}
