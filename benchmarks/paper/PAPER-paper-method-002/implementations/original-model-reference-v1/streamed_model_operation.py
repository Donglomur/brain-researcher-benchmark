"""Versioned portable full-fit route with source-defined singleton accumulation.

The four model/author modules and streamed_batch.py are unchanged donors.
Only original training and validation scheduling is replaced. Final TEST
prediction remains the original 128-row vectorized call. No numerical, memory,
wall-time or full-fit qualification is claimed by this source component.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import time

COMPONENT = "jaxley-original-model-reference-streamed-v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def new_streaming_statistics():
    return {"training_singletons_completed": 0, "validation_singletons_completed": 0,
            "completed_original_gradient_batches": 0, "completed_original_validation_batches": 0,
            "last_training_batch_completed_rows": 0, "last_validation_batch_completed_rows": 0,
            "last_global_mean_denominator": 0}


def fit_source_defaults_streamed_v1(arrays, meta, morphology_prefix, out, *, checkpoint=None):
    """Run all 1008 updates and 21 validations on an already validated packet.

    checkpoint(stage) is optional observation/cancellation supplied by a caller;
    its default is a no-op and does not establish a time or memory limit.
    The source helper supports exactly287 current columns, training153/256 and
    validation999/1024. No TEST targets are accepted by the original packet.
    """
    require(tuple(arrays["currents"].shape) == (15360, 287), "streamed-v1 current support")
    if checkpoint is None:
        checkpoint = lambda stage: None
    require(callable(checkpoint), "checkpoint must be callable")
    stats = new_streaming_statistics()
    result = _fit_source_defaults_streamed(arrays, meta, morphology_prefix, out, checkpoint, stats)
    require(stats["training_singletons_completed"] == 255885
            and stats["validation_singletons_completed"] == 63987
            and stats["completed_original_gradient_batches"] == 1008
            and stats["completed_original_validation_batches"] == 63,
            "complete source streaming workload")
    result.update({"status": "FRESH_SOURCE_DEFAULT_STREAMED_FIT_COMPLETE", "component": COMPONENT,
                   "streaming_statistics": stats, "floating_point_equivalence_qualified": False,
                   "resource_and_full_fit_qualification_from_source": False,
                   "final_test_prediction_schedule": "unchanged vectorized128; memory unqualified"})
    return result


def _fit_source_defaults_streamed(arrays, meta, morphology_prefix, out, checkpoint, stats):
    """1008 updates and 21 epoch-end validations; final test prediction only."""
    from model_operation import (configure_model_runtime, initialize_model, observed_source_split,
                                 masked_pearson, save_tree)
    from streamed_batch import streamed_gradient, streamed_prediction
    import numpy as np
    configure_model_runtime()
    import jax.numpy as jnp
    from jax import tree_map, tree_util
    import tensorflow as tf
    from tensorflow.data import Dataset
    import optax
    from jaxley.optimize import TypeOptimizer
    from jaxley.optimize.utils import l2_norm

    opt, states, predict, gradient, _ = initialize_model(arrays, meta, morphology_prefix)

    def predict_validation(optimum, currents):
        stats["last_validation_batch_completed_rows"] = 0
        return streamed_prediction(predict, optimum, currents, np=np, check=checkpoint, stats=stats)

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
            stats["last_training_batch_completed_rows"] = 0
            loss, gradients = streamed_gradient(gradient, opt, batch[1].numpy(), batch[2].numpy(),
                                                 batch[3].numpy(), states, np=np, jnp=jnp,
                                                 tree_util=tree_util, check=checkpoint, stats=stats)
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
        val_predictions = np.concatenate([predict_validation(opt, batch[1].numpy()) for batch in val_loader], axis=0)
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


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fit-source-defaults-streamed-v1",), required=True)
    parser.add_argument("--arrays", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--morphology-prefix", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def run_prepared(args, out, *, loader, fit):
    """Actual CLI invocation seam; production supplies the original loader/fit.

    The explicit two callables permit data-free routing controls. They do not
    authenticate files, qualify packages or provide an input-memory sandbox.
    """
    require(args.mode == "fit-source-defaults-streamed-v1", "selected portable mode")
    arrays, metadata = loader(args.arrays, args.metadata)
    return fit(arrays, metadata, args.morphology_prefix, out)


def main(argv=None):
    args = parse_args(argv)
    os.umask(0o077)
    out = Path(args.output)
    out.mkdir(mode=0o700, exist_ok=False)
    start = time.monotonic()
    status = {"status": "STARTED", "mode": args.mode, "component": COMPONENT}
    try:
        from model_operation import load_packet
        status = run_prepared(args, out, loader=load_packet, fit=fit_source_defaults_streamed_v1)
    except BaseException as exc:
        status = {"status": "FAILED", "mode": args.mode, "component": COMPONENT,
                  "exception_type": type(exc).__name__, "message": str(exc)}
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
