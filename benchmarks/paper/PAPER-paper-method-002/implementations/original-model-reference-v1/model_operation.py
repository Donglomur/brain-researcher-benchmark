"""Fresh source-defined RGC operation. Prepared source; never executed here.

The three author_*.py siblings are byte-identical authenticated source. This
entry extracts the default scientific training path from train.body, preserves
its optimizer/loader/math, and omits RF/plot/train-test monitoring diagnostics.
It retains the actual validation-selected parameters and predictions. No test
targets enter this module. The enclosing existing owner authenticates inputs,
qualifies a concrete runtime, enforces caps and keeps results operator-private.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import time


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bound_model_packet(binding, averages, stimuli):
    """Operator-side handoff from input_binding.bind_model_arrays.

    Call after the exact BC producer/loader binding. Serialize arrays using
    np.savez, metadata as JSON. The owner authenticates whole output files.
    Source pandas objects never cross into the modern model runtime.
    """
    import numpy as np
    require(binding["schema"] == "jaxley-original-model-binding-v1", "binding schema")
    train = np.asarray(binding["splits"]["train"], dtype=np.int64)
    val = np.asarray(binding["splits"]["val"], dtype=np.int64)
    arrays = {
        "images": np.ascontiguousarray(binding["noise"]),
        "currents": np.ascontiguousarray(binding["currents"]),
        "mask": np.ascontiguousarray(binding["mask"]),
        "train_targets": np.ascontiguousarray(binding["labels"][train]),
        "val_targets": np.ascontiguousarray(binding["labels"][val]),
    }
    meta = {
        "schema": "jaxley-original-model-operation-input-v1",
        "cell_id": "20161028_1",
        "identity_sha256": binding["identity_sha256"],
        "sites": binding["sites"], "splits": binding["splits"],
        "site_comps": [float(x) for x in averages["comp"]],
        "connections": [{"bc_id": int(row.bc_id), "branch": int(row.branch_ind),
                         "comp": float(row.comp), "num_synapses_of_bc": int(row.num_synapses_of_bc)}
                        for row in stimuli.itertuples(index=False)],
        "arrays": {},
        "test_targets_included": False,
        "validation_access": "same authorized targets and 21 epoch-end feedback opportunities for both arms",
        "source_preprocessing": binding["preprocessing_access"],
    }
    for name, array in arrays.items():
        require(array.dtype.kind in "iuf" and bool(np.isfinite(array).all()), "finite numeric operands")
        meta["arrays"][name] = {"shape": list(array.shape), "dtype": array.dtype.str,
            "bytes": array.nbytes, "sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest()}
    validate_packet(arrays, meta)
    return arrays, meta


def validate_packet(arrays, meta):
    import numpy as np
    require(meta["schema"] == "jaxley-original-model-operation-input-v1", "model packet schema")
    require(meta["cell_id"] == "20161028_1" and meta["test_targets_included"] is False, "target/access contract")
    names = {"images", "currents", "mask", "train_targets", "val_targets"}
    require(set(arrays) == set(meta["arrays"]) == names, "no extra arrays or test targets")
    require(sum(a.nbytes for a in arrays.values()) <= 3 * 1024**3, "model packet numeric cap")
    for name, array in arrays.items():
        desc = meta["arrays"][name]
        require(type(array) is np.ndarray and array.dtype.kind in "iuf", "plain numeric array")
        require(array.flags.c_contiguous and list(array.shape) == desc["shape"], "shape/C-order")
        require(array.dtype.str == desc["dtype"] and array.nbytes == desc["bytes"], "dtype/extent")
        require(bool(np.isfinite(array).all()), "nonfinite model operand")
        require(hashlib.sha256(array.tobytes(order="C")).hexdigest() == desc["sha256"], "numeric crossing bytes")
    sites = meta["sites"]
    require(len(sites) == len(meta["site_comps"]) == 147, "147 recording sites")
    keys = [(s["field"], s["branch"], s["bin"]) for s in sites]
    require(len(set(keys)) == 147 and keys == sorted(keys), "site identities/order")
    raw_keys = [(s["field"], roi) for s in sites for roi in s["raw_roi_ids"]]
    require(len(raw_keys) == len(set(raw_keys)) == 232, "all original ROI constituents")
    require({s["field"] for s in sites} == set(range(1, 16)), "all fifteen source fields")
    require(all(0.0 <= x <= 1.0 for x in meta["site_comps"]), "continuous recording comp")
    identities = {"sites": sites, "splits": meta["splits"]}
    digest = hashlib.sha256(json.dumps(identities, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    require(digest == meta["identity_sha256"], "split/site identity")
    split = meta["splits"]
    require(set(split) == {"train", "val", "test"}, "split names")
    require([len(split[k]) for k in ("train", "val", "test")] == [12185, 3047, 128], "split extents")
    require(sorted(sum(split.values(), [])) == list(range(15360)), "full disjoint row support")
    require(arrays["images"].shape == (15360, 15, 20), "image support")
    require(arrays["currents"].shape == (15360, len(meta["connections"])), "connection columns")
    require(0 < len(meta["connections"]) <= 110 * 155, "bounded original connection roster")
    require(all(1 <= c["bc_id"] <= 110 and 0 <= c["branch"] < 155 and
                0 <= c["comp"] <= 1 and c["num_synapses_of_bc"] > 0
                for c in meta["connections"]), "source BC connection metadata")
    mask = arrays["mask"]
    require(mask.shape == (15360, 147) and mask.dtype == np.dtype("float64"), "source mask shape/dtype")
    expected = np.arange(15360)[:, None] // 1024 + 1 == np.asarray([s["field"] for s in sites])[None, :]
    require(np.array_equal(mask, expected) and int(mask.sum()) == 150528, "field-local observed support")
    for name, count in (("train", 12185), ("val", 3047)):
        targets = arrays[name + "_targets"]
        require(targets.shape == (count, 147) and targets.dtype == np.dtype("float64"), "source targets")
        require(bool((targets[mask[split[name]] == 0] == 0).all()), "source target placeholders")


def load_packet(array_path, metadata_path):
    """The owner must authenticate both named files before this inner command."""
    import numpy as np
    meta = json.loads(Path(metadata_path).read_text())
    with np.load(array_path, allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    validate_packet(arrays, meta)
    return arrays, meta


def configure_model_runtime():
    from jax import config
    config.update("jax_enable_x64", True)
    config.update("jax_platform_name", "cpu")
    os.environ["XLA_PYTHON_CLIENT_MEM_FRACTION"] = ".6"


def initialize_model(arrays, meta, morphology_prefix):
    # Exactly author train's CPU/x64 configuration, before model imports.
    configure_model_runtime()
    from functools import partial
    import numpy as np
    import jax.numpy as jnp
    from jax import jit, vmap, value_and_grad
    import jaxley as jx
    from author_model_utils import build_cell, build_kernel
    from author_transforms import transform_params, transform_basal, transform_somatic
    from author_simulate import loss_fn, predict

    dt, t_max, nseg, num_truncations = 0.025, 200.0, 4, 4
    time_vec = np.arange(0, t_max + 2 * dt, dt)
    cell = build_cell("20161028_1", nseg, 7.5, morphology_prefix)
    kernel = build_kernel(time_vec, dt)
    cell.delete_recordings()
    cell.delete_stimuli()
    for site, comp in zip(meta["sites"], meta["site_comps"]):
        cell.branch(site["branch"]).loc(comp).record("Cai", verbose=False)
    require(len(cell.recordings) == 147, "calcium-only recording roster")
    basal_inds = list(np.unique(cell.group_nodes["basal"]["branch_index"].to_numpy()))
    somatic_inds = list(np.unique(cell.group_nodes["soma"]["branch_index"].to_numpy()))
    # Deliberately preserve author integrate's omitted delta_t and default solver.
    # Their actual package defaults are a required runtime qualification.
    _, init_states = jx.integrate(cell, t_max=5.0, return_states=True)
    cell.delete_trainables()
    cell.basal.branch("all").make_trainable("axial_resistivity")
    cell.basal.branch("all").make_trainable("radius")
    parameters = cell.get_parameters()
    np.random.seed(1)
    parameters = [{"w_bc_to_rgc": 0.1 * jnp.asarray(np.random.rand(arrays["currents"].shape[1]))}] + parameters
    np.random.seed(0)
    basal_neuron_params = [
        {"Na_gNa": jnp.asarray(0.05)}, {"K_gK": jnp.asarray(0.05)},
        {"Leak_gLeak": jnp.asarray(1e-4)}, {"KA_gKA": jnp.asarray(36e-3)},
        {"Ca_gCa": jnp.asarray(2.2e-3)}, {"KCa_gKCa": jnp.asarray(0.05e-3)},
    ]
    somatic_neuron_params = [
        {"Na_gNa": jnp.asarray(0.05)}, {"K_gK": jnp.asarray(0.05)},
        {"Leak_gLeak": jnp.asarray(1e-4)}, {"KA_gKA": jnp.asarray(36e-3)},
        {"Ca_gCa": jnp.asarray(2.2e-3)}, {"KCa_gKCa": jnp.asarray(0.05e-3)},
    ]
    opt = (transform_params.inverse(parameters), transform_basal.inverse(basal_neuron_params),
           transform_somatic.inverse(somatic_neuron_params))
    static = {"cell": cell, "dt": dt, "t_max": t_max, "time_vec": time_vec,
              "num_truncations": num_truncations, "output_scale": jnp.asarray(40.0),
              "output_offset": jnp.asarray(-1.3), "kernel": kernel,
              "transform_params": transform_params, "transform_basal": transform_basal,
              "transform_somatic": transform_somatic, "somatic_inds": somatic_inds,
              "basal_inds": basal_inds,
              "stim_branch_inds": np.asarray([c["branch"] for c in meta["connections"]]),
              "stim_comps": np.asarray([c["comp"] for c in meta["connections"]])}
    vmapped_predict = jit(vmap(partial(predict, static=static), in_axes=(None, None, None, 0, None)))
    vmapped_loss = jit(vmap(partial(loss_fn, static=static), in_axes=(None, None, None, 0, 0, 0, None)))

    def batch_loss(opt_params, opt_basal, opt_somatic, currents, labels, weights, states):
        losses = vmapped_loss(transform_params.forward(opt_params), transform_basal.forward(opt_basal),
                              transform_somatic.forward(opt_somatic), currents, labels, weights, states)
        return jnp.mean(losses)

    def prediction(optimum, currents):
        return vmapped_predict(transform_params.forward(optimum[0]), transform_basal.forward(optimum[1]),
                               transform_somatic.forward(optimum[2]), currents, init_states)

    gradient = jit(value_and_grad(batch_loss, argnums=(0, 1, 2)))
    return opt, init_states, prediction, gradient, static


def observed_source_split(meta):
    """Observe the real global RNG call after inverse transforms; never assume it."""
    import numpy as np
    before = np.random.get_state()
    # Exact author arithmetic and call; source_tf seed is set first by full fit.
    test_frac = 128 / 15360
    val_frac = 0.2 * (1 - test_frac)
    num_train = int(15360 * (1 - val_frac - test_frac))
    indices = np.random.permutation(np.arange(15360))
    after = np.random.get_state()
    actual = {"test": indices[:128].tolist(), "train": indices[128:128+num_train].tolist(),
              "val": indices[128+num_train:].tolist()}
    require(actual == meta["splits"], "actual dependency/RNG sequence changed frozen split")

    def serial(state):
        return {"algorithm": state[0], "keys": state[1].tolist(), "position": state[2],
                "has_gauss": state[3], "cached_gaussian": state[4]}
    return {"before_permutation": serial(before), "after_permutation": serial(after)}


def masked_pearson(predictions, labels, mask):
    import numpy as np
    require(predictions.shape == labels.shape == mask.shape and labels.shape[1] == 147, "evaluation shape")
    rhos = []
    support = []
    for roi_id in range(147):
        measured = mask[:, roi_id].astype(bool)
        support.append(int(measured.sum()))
        require(support[-1] >= 2, "undefined per-site Pearson support")
        rho = np.corrcoef(labels[measured, roi_id], predictions[measured, roi_id])[0, 1]
        require(bool(np.isfinite(rho)), "undefined per-site Pearson; no site dropping")
        rhos.append(float(rho))
    return {"mean": float(np.mean(rhos)), "per_site": rhos, "support": support}


def save_tree(path, groups):
    """Numeric-only three parameter groups, with an explicit key/shape manifest."""
    import numpy as np
    leaves, layout = {}, []
    for group_index, group in enumerate(groups):
        group_layout = []
        for ordinal, parameter in enumerate(group):
            require(len(parameter) == 1, "single-key source parameter entry")
            name, value = next(iter(parameter.items()))
            storage_key = "g%d_p%d" % (group_index, ordinal)
            leaves[storage_key] = np.asarray(value)
            group_layout.append({"parameter": name, "array": storage_key,
                                 "shape": list(leaves[storage_key].shape)})
        layout.append(group_layout)
    np.savez(path, **leaves)
    Path(str(path) + ".json").write_text(json.dumps(layout, indent=2) + "\n")


def qualify_first_training_row(arrays, meta, morphology_prefix, out):
    """One original row, 147 output sites, value+gradient; zero optimizer updates."""
    import numpy as np
    configure_model_runtime()
    from jax import tree_util
    started = time.monotonic()
    opt, states, predict, gradient, static = initialize_model(arrays, meta, morphology_prefix)
    rng = observed_source_split(meta)
    row = meta["splits"]["train"][0]
    prediction = np.asarray(predict(opt, arrays["currents"][[row]]))
    loss, grad = gradient(*opt, arrays["currents"][[row]], arrays["train_targets"][:1], arrays["mask"][[row]], states)
    loss = float(np.asarray(loss))
    grad_values = [np.asarray(x) for x in tree_util.tree_leaves(grad)]
    require(prediction.shape == (1, 147) and bool(np.isfinite(prediction).all()), "finite full-site prediction")
    require(np.isfinite(loss) and all(bool(np.isfinite(x).all()) for x in grad_values), "finite loss/gradient")
    expected = float(np.sum(arrays["mask"][[row]] * np.abs(prediction - arrays["train_targets"][:1])))
    require(bool(np.isclose(loss, expected, rtol=1e-10, atol=1e-10)), "author masked L1 consistency")
    save_tree(out / "initial_parameters.npz", opt)
    save_tree(out / "initial_gradients.npz", grad)
    np.save(out / "training_row_prediction.npy", prediction, allow_pickle=False)
    (out / "rng.json").write_text(json.dumps(rng) + "\n")
    return {"status": "ONE_ORIGINAL_TRAIN_ROW_FORWARD_AND_GRADIENT_FINITE", "row_id": row,
            "optimizer_updates": 0, "site_count": 147, "observed_sites": int(arrays["mask"][row].sum()),
            "loss": loss, "gradient_leaves": len(grad_values), "elapsed_seconds": time.monotonic()-started,
            "time_vector_length": len(static["time_vec"]), "truncations": 4,
            "qualification_limit": "single-row CPU/x64 runtime feasibility only; no fit, baseline, score or full-batch cost inference"}


def fit_source_defaults(arrays, meta, morphology_prefix, out):
    """1008 updates and 21 epoch-end validations; final test prediction only."""
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
    best_mean, best_opt, best_epoch = -1.0, None, None
    updates, history = 0, []
    # ceil(1000/48) == 21; process all batches, including each final153-row batch.
    for epoch in range(21):
        epoch_loss = 0.0
        for batch_index, batch in enumerate(dataloader):
            loss, gradients = gradient(*opt, batch[1].numpy(), batch[2].numpy(), batch[3].numpy(), states)
            grad_params, grad_basal, grad_somatic = gradients
            for i in range(3):
                weight_norm = l2_norm(grad_params[i])
                key = list(grad_params[i].keys())[0]
                num_params = len(grad_params[i][key])
                grad_params[i] = tree_map(lambda x: x / weight_norm**0.99 * num_params, grad_params[i])
            grad_norm_basal = l2_norm(grad_basal)
            grad_basal = tree_map(lambda x: x / grad_norm_basal**0.99 * 6, grad_basal)
            grad_norm_somatic = l2_norm(grad_somatic)
            grad_somatic = tree_map(lambda x: x / grad_norm_somatic**0.99 * 6, grad_somatic)
            epoch_loss += loss
            next_opt, next_states = [], []
            for optimizer, old_opt, old_state, grad in zip(optimizers, opt, optimizer_states, (grad_params, grad_basal, grad_somatic)):
                update, new_state = optimizer.update(grad, old_state)
                next_opt.append(optax.apply_updates(old_opt, update))
                next_states.append(new_state)
            opt, optimizer_states = tuple(next_opt), tuple(next_states)
            updates += 1
            # No within-epoch evaluation: 48 < source eval_every_nth_batch=100.
        require(batch_index + 1 == 48, "source epoch extent")
        val_predictions = np.concatenate([np.asarray(predict(opt, batch[1].numpy())) for batch in val_loader], axis=0)
        metric = masked_pearson(val_predictions, arrays["val_targets"], arrays["mask"][val_ids])
        scalar_loss = float(np.asarray(epoch_loss))
        require(np.isfinite(scalar_loss), "nonfinite epoch loss")
        selected = metric["mean"] > best_mean
        if selected:
            best_mean, best_epoch = metric["mean"], epoch
            best_opt = tree_map(lambda x: jnp.asarray(np.asarray(x).copy()), opt)
            # These are exactly the state/predictions at the selecting check.
            save_tree(out / "validation_selected_parameters.npz", best_opt)
            np.save(out / "validation_selected_predictions.npy", val_predictions, allow_pickle=False)
        history.append({"epoch_zero_based": epoch, "updates": updates, "epoch_sum_of_batch_mean_L1": scalar_loss,
                        "validation": metric, "selected": selected})
        (out / "validation_history.json").write_text(json.dumps(history, indent=2, allow_nan=False) + "\n")
    require(updates == 1008 and len(history) == 21 and best_opt is not None, "full source budget and selected state")
    test_ids = np.asarray(meta["splits"]["test"], dtype=np.int64)
    test_predictions = np.asarray(predict(best_opt, arrays["currents"][test_ids]))
    require(test_predictions.shape == (128, 147) and bool(np.isfinite(test_predictions).all()), "finite held-out predictions")
    submission = {"schema": "jaxley-retinal-prediction-v1", "cell_id": "20161028_1",
                  "test_row_ids": test_ids.tolist(),
                  "site_keys": [[s["field"], s["branch"], s["bin"]] for s in meta["sites"]],
                  "predictions": test_predictions.tolist()}
    (out / "prediction.json").write_text(json.dumps(submission, allow_nan=False) + "\n")
    (out / "rng.json").write_text(json.dumps(rng) + "\n")
    return {"status": "FRESH_SOURCE_DEFAULT_FIT_COMPLETE", "optimizer_updates": updates,
            "validation_checks": 21, "selected_epoch_zero_based": best_epoch,
            "selected_completed_updates": 48 * (best_epoch + 1), "validation_mean_Pearson": best_mean,
            "test_targets_consumed": False, "test_score_computed": False,
            "historical_checkpoint_or_score_reproduction": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("qualify-first-training-row", "fit-source-defaults"), required=True)
    parser.add_argument("--arrays", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--morphology-prefix", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    out = Path(args.output)
    out.mkdir(mode=0o700, exist_ok=False)
    start = time.monotonic()
    status = {"status": "STARTED", "mode": args.mode}
    try:
        arrays, meta = load_packet(args.arrays, args.metadata)
        fn = qualify_first_training_row if args.mode == "qualify-first-training-row" else fit_source_defaults
        status = fn(arrays, meta, args.morphology_prefix, out)
    except BaseException as exc:
        status = {"status": "FAILED", "mode": args.mode, "exception_type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        status.update({"elapsed_seconds_including_failure": time.monotonic()-start,
                       "user_cpu_seconds": usage.ru_utime, "system_cpu_seconds": usage.ru_stime,
                       "maxrss_platform_units": usage.ru_maxrss,
                       "maxrss_unit_note": "Linux KiB; qualify on selected Linux runtime",
                       "owner_must_capture_external_kill_and_startup_failure": True})
        (out / "operation_result.json").write_text(json.dumps(status, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
