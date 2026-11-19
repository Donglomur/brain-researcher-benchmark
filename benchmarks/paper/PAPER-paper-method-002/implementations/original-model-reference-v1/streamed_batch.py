"""Source-only singleton scheduling for the existing retinal gradient/predict calls.

This preserves the real-arithmetic batch objective. Sequential NumPy sums inside
the SAME worker/container change floating-point order/backend and do not prove
numerical equivalence. No native cache/allocator or wall/RAM bound is asserted.
"""

def require(condition, message):
    if not condition:
        raise ValueError(message)


def singleton_slices(rows, kind):
    allowed = (153, 256) if kind == "training" else (999, 1024) if kind == "validation" else ()
    require(type(rows) is int and rows in allowed, "selected original batch size/kind")
    return tuple((i, i + 1) for i in range(rows))


def training_shape_contract(current_shape, label_shape, mask_shape):
    require(len(current_shape) == 2 and current_shape[1] == 287, "original current columns")
    rows = current_shape[0]
    singleton_slices(rows, "training")
    require(tuple(label_shape) == tuple(mask_shape) == (rows, 147), "all147 sites and unchanged mask")
    return rows


def streamed_gradient(gradient, opt, currents, labels, mask, init_states, *, np, jnp, tree_util, check, stats):
    """One original batch mean; no optimizer, normalization or random operation.

    The existing singleton-capable JIT closure is supplied once by initialize_model.
    Every device result is copied synchronously to owned worker NumPy arrays before
    advancing. Only sum buffers, one row's host/device gradients, and fixed inputs
    are retained; no row gradient list/tape history or whole-loop JIT is created.
    Compiled executables, caches and native allocator residency remain unmeasured.
    """
    rows = training_shape_contract(currents.shape, labels.shape, mask.shape)
    loss_sum = None
    gradient_sums = None
    expected_structure = None
    expected_signatures = None
    for begin, end in singleton_slices(rows, "training"):
        check("streamed_gradient_before_singleton")
        # opt and init_states are identical objects for every row in this batch.
        loss_device, gradients_device = gradient(*opt, currents[begin:end], labels[begin:end], mask[begin:end], init_states)
        loss_host = np.asarray(loss_device).copy(order="C")
        require(loss_host.shape == () and loss_host.dtype.kind == "f", "scalar source loss dtype")
        device_leaves, structure = tree_util.tree_flatten(gradients_device)
        # np.asarray materializes each JAX result; copy detaches owned host buffers.
        host_leaves = [np.asarray(leaf).copy(order="C") for leaf in device_leaves]
        signatures = [(leaf.shape, leaf.dtype.str) for leaf in host_leaves]
        require(host_leaves and all(leaf.dtype.kind == "f" for leaf in host_leaves), "source gradient leaves")
        if gradient_sums is None:
            expected_structure, expected_signatures = structure, signatures
            loss_sum, gradient_sums = loss_host, host_leaves
        else:
            require(structure == expected_structure and signatures == expected_signatures,
                    "unchanged source gradient structure/dtype")
            require(loss_host.dtype == loss_sum.dtype, "unchanged loss dtype")
            np.add(loss_sum, loss_host, out=loss_sum)
            for accumulator, leaf in zip(gradient_sums, host_leaves):
                np.add(accumulator, leaf, out=accumulator)
            del accumulator, leaf
        # No previous JAX row outputs or temporary host leaf list survives to the next call.
        del loss_device, gradients_device, device_leaves, host_leaves, loss_host
        stats["training_singletons_completed"] += 1
        stats["last_training_batch_completed_rows"] = end
        check("streamed_gradient_after_materialized_singleton")
    # The denominator is actual original B, including153 tail; no site/support denominator.
    np.divide(loss_sum, rows, out=loss_sum)
    for accumulator in gradient_sums:
        np.divide(accumulator, rows, out=accumulator)
    loss = jnp.asarray(loss_sum)
    gradients = tree_util.tree_unflatten(expected_structure, [jnp.asarray(leaf) for leaf in gradient_sums])
    # Complete the one small mean-gradient return before the caller's original optimizer block.
    loss.block_until_ready()
    for leaf in tree_util.tree_leaves(gradients):
        leaf.block_until_ready()
    stats["completed_original_gradient_batches"] += 1
    stats["last_global_mean_denominator"] = rows
    return loss, gradients


def streamed_prediction(predict, opt, currents, *, np, check, stats):
    """Reassemble the original validation batch in row-major147-site order.

    No per-row/chunk correlation or score is computed. A later full-fit caller
    must retain its existing complete-validation global metric/selection logic.
    """
    require(len(currents.shape) == 2 and currents.shape[1] == 287, "original validation current columns")
    rows = currents.shape[0]
    schedule = singleton_slices(rows, "validation")
    result = None
    for begin, end in schedule:
        check("streamed_prediction_before_singleton")
        device_prediction = predict(opt, currents[begin:end])
        host_prediction = np.asarray(device_prediction).copy(order="C")
        require(host_prediction.shape == (1, 147) and host_prediction.dtype.kind == "f", "all147 singleton predictions")
        if result is None:
            result = np.empty((rows, 147), dtype=host_prediction.dtype)
        require(host_prediction.dtype == result.dtype, "unchanged prediction dtype")
        result[begin:end] = host_prediction
        # Each prediction is copied/synchronized and device output released before advancing.
        del device_prediction, host_prediction
        stats["validation_singletons_completed"] += 1
        stats["last_validation_batch_completed_rows"] = end
        check("streamed_prediction_after_materialized_singleton")
    stats["completed_original_validation_batches"] += 1
    return result
