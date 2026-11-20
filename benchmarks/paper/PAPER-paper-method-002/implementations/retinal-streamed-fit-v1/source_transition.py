def source_transition(loss, gradients, opt, optimizer_states, optimizers, tree_map, l2_norm, optax):
    """Unchanged source normalization/update span; appended update capture is observational."""
    epoch_loss, updates = 0.0, 0
    captured_updates = []
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
        captured_updates.append(update)
        next_opt.append(optax.apply_updates(old_opt, update))
        next_states.append(new_state)
    opt, optimizer_states = tuple(next_opt), tuple(next_states)
    updates += 1
    return {"normalized": (grad_params, grad_basal, grad_somatic), "proposed_updates": tuple(captured_updates),
            "parameters": opt, "optimizer_states": optimizer_states, "updates": updates}

