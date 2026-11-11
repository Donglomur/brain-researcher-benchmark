"""Complete J26--J31 scientific caller component, never executed in source build.

J27 owns training and publication of actual full fit state. All other groups
consume that captured parent; the common compiler owns native/capture authority.
"""
from .vision_inputs import (ACTIONS, RESET_GROUPS, PARAMETER_KEYS, require,
    identity, load, images, checkpoint_state)
from .vision_model import (Biophysical, encode, decode, baseline_init,
    baseline_logits, train_baseline)


def _bio(ctx, p, bundle):
    model = Biophysical(ctx, p['model_profile'])
    state = bundle['fits'][p['selected_biophysical_fit']]
    require(state['initial'] == encode(model.initial), 'same constructor/initial-state lineage')
    params = decode(state['selected'], model.initial)
    ctx.record('actual-fit-parent', {'fit': p['selected_biophysical_fit'],
        'bundle': identity(bundle), 'initial': identity(state['initial']),
        'selected': identity(state['selected'])})
    return model, params, state


def _flatten(params):
    import numpy as np
    return np.concatenate([np.asarray(next(iter(row.values()))).reshape(-1) for row in params])


def _logits_batches(ctx, fn, params, x, batch):
    import numpy as np
    chunks = []
    for start in range(0, len(x), batch):
        ctx.checkpoint()
        z = np.asarray(fn(params, x[start:start + batch]))
        require(z.shape == (min(batch, len(x) - start), 10), 'full ten-class batch logits')
        chunks.append(z)
    return np.concatenate(chunks)


def fit_all(ctx, p, c):
    import numpy as np
    require(p['model_profile'] == 'literal-training02', 'full training source02 profile')
    train_x, train_y = images(ctx, 'train', c)
    test_x, test_y = images(ctx, 'test', c)
    states, logits, histories = {}, [], {}
    for fit in p['fits']:
        ctx.checkpoint()
        if fit['kind'] == 'biophysical':
            model = Biophysical(ctx, p['model_profile'])
            state = model.train(train_x, train_y, test_x, test_y)
            params = decode(state['selected'], model.initial)
            z = model.evaluate(params, test_x, p['evaluation_batch_size'])
        else:
            state = train_baseline(ctx, fit['kind'], fit['seed'], p['baseline_recipe'], train_x, train_y)
            params = decode(state['selected'], baseline_init(fit['kind'], fit['seed']))
            z = _logits_batches(ctx, baseline_logits, params, test_x, p['evaluation_batch_size'])
        require(z.shape == (10000, 10), 'complete test denominator')
        states[fit['id']] = state; logits.append(z); histories[fit['id']] = state['history']
        ctx.record('completed-fit', {'id': fit['id'], 'kind': fit['kind'],
            'selected_identity': identity(state['selected']), 'full_test_count': 10000})
    bundle = {'schema': 'vision_full_fit_state_v1', 'cohort_sha256': p['cohort_sha256'],
        'model_profile': p['model_profile'], 'fit_roster': p['fits'], 'fits': states,
        'baseline_historical_equivalence': False, 'biophysical_test_selection_exposed': True}
    ctx.emit_numeric('full_test_logits', np.stack(logits))
    ctx.emit_numeric('image_labels', test_y)
    ctx.emit_json('fit_history', {'fit_order': [r['id'] for r in p['fits']], 'histories': histories,
        'all_updates_retained': True, 'failed_fit_policy': 'fail-complete-family'})
    # Full parameters are deliberately retained, not merely a digest claiming a
    # producer. This artifact is the actual input to all dependent analyses.
    ctx.emit_json('fit_parameter_identity', bundle)


def architecture(ctx, p, c, bundle):
    x, _ = images(ctx, 'test', c)
    model, params, _ = _bio(ctx, p, bundle)
    model.set_recording('all')
    trace = model.trace_batches(params, x[c['architecture_indices']], p['evaluation_batch_size'])
    require(trace.shape[:2] == (256, 858), 'full trained input/hidden/output somatic traces')
    ctx.emit_json('architecture_map', {'cells': {'input': [0, 784], 'hidden': [784, 848],
        'output': [848, 858]}, 'time_step_ms': .025, 'stimulus_duration_ms': 1.,
        'source_t_max_ms': 10.01, 'native_time_samples': int(trace.shape[-1]),
        'included_image_ids': [c['test_ids'][i] for i in c['architecture_indices']],
        'trained_parent': identity(bundle), 'full_somatic_traces_in_hidden_voltage_product': True})
    ctx.emit_numeric('full_logits', (trace[:, -10:, -1] + 65.) / 3.)
    ctx.emit_numeric('hidden_voltage', trace)
    ctx.emit_json('parameter_map', model.parameter_map())


def reset_all(ctx, p, c, bundle):
    import numpy as np
    x, y = images(ctx, 'test', c)
    model, trained, state = _bio(ctx, p, bundle)
    initial = decode(state['initial'], model.initial)
    parameters, predictions, membership = [], [], []
    for name, groups in RESET_GROUPS.items():
        # New list, never mutate the selected trained checkpoint or initialize
        # new random values under the name 'reset to initial'.
        reset = [initial[k] if k in groups else trained[k] for k in range(8)]
        parameters.append(_flatten(reset))
        predictions.append(model.evaluate(reset, x[c['reset_indices']], p['evaluation_batch_size']))
        membership.append({'name': name, 'groups': list(groups), 'keys': [PARAMETER_KEYS[k] for k in groups],
            'state_identity': identity(encode(reset)), 'source': 'original-initial-values',
            'reinitialized_random_values': False})
    ctx.emit_numeric('initial_parameters', _flatten(initial))
    ctx.emit_numeric('trained_parameters', _flatten(trained))
    ctx.emit_numeric('reset_parameters', np.stack(parameters))
    ctx.emit_numeric('reset_logits', np.stack(predictions))
    ctx.emit_json('reset_membership', {'conditions': membership, 'image_indices': c['reset_indices'],
        'labels': y[c['reset_indices']].tolist(), 'parameter_map': model.parameter_map(),
        'trained_parent': identity(bundle), 'histogram_display_only_synapse_factor': 1000})


def literal_attack_membership(labels):
    """01 cell51 exact train support and wrong-label RNG; future native only."""
    import numpy as np
    rows = []
    for seed in range(1, 9):
        np.random.seed(seed)
        ix = np.arange((seed - 1) * 24, seed * 24)
        targets = np.random.randint(0, 10, 24)
        good = targets != labels[ix]
        chosen, wrong = ix[good][:16], targets[good][:16]
        require(len(chosen) == 16, 'source candidate pool lacks16 eligible attacks')
        rows.extend((int(i), int(t)) for i, t in zip(chosen, wrong))
    return rows


def attack_all(ctx, p, c, bundle):
    import numpy as np
    import jax
    import jax.numpy as jnp
    from jax.scipy.special import logsumexp
    from jax.nn import sigmoid
    split = 'train' if p['attack_profile'] == 'literal-logit-train01' else 'test'
    x, y = images(ctx, split, c)
    roster = c['attacks']; ix = [r['index'] for r in roster]
    target = np.asarray([r['target'] for r in roster]); true = y[ix]
    require((target != true).all(), 'every target must differ from actual label')
    if split == 'train':
        require(list(zip(ix, target.tolist())) == literal_attack_membership(y),
                'literal eight-seed candidate selection must match actual labels')
    clean = x[ix]
    bio, bio_params, _ = _bio(ctx, p, bundle); bio.set_recording('output')
    mf = next(r for r in p['fits'] if r['id'] == p['selected_mlp_fit'])
    ms = bundle['fits'][mf['id']]
    mp = decode(ms['selected'], baseline_init('mlp', mf['seed']))
    all_images, all_logits, curves, records = [], [], [], []
    for kind, params in (('biophysical', bio_params), ('mlp', mp)):
        ctx.checkpoint()
        latent = p['attack_profile'] == 'literal-logit-train01'
        pixel0 = jnp.asarray(np.where(clean == 0., .01, np.where(clean == 1., .99, clean))) if latent else jnp.asarray(clean)
        variable = jnp.log(pixel0 / (1 - pixel0)) if latent else pixel0
        def pixels(v):
            return sigmoid(v) if latent else v
        def predict(v):
            z = pixels(v)
            return bio.logits(params, z) if kind == 'biophysical' else baseline_logits(params, z)
        def objective(v):
            z = predict(v)
            return jnp.sum(logsumexp(z, axis=1) - z[jnp.arange(128), target])
        loss_gradient = jax.jit(jax.value_and_grad(objective))
        pixel_path, logits_path, raw_path, trace_path, literal_raw_traces = [], [], [], [], []
        losses, norm_path, cumulative, previous = [], [], np.zeros(128), np.asarray(pixel0)
        variable_cumulative = np.zeros(128)
        for step in range(31):
            ctx.checkpoint()
            current = np.asarray(pixels(variable)); z = np.asarray(predict(variable))
            require(z.shape == (128, 10), 'complete paired attack logits')
            pixel_path.append(current); logits_path.append(z); raw_path.append(np.asarray(variable))
            cumulative += np.linalg.norm(current - previous, axis=1)
            norm_path.append({'step': step, 'nominal_5_times_step': 5 * step,
                'pixel_displacement_l2': np.linalg.norm(current - clean, axis=1).tolist(),
                'pixel_path_length': cumulative.tolist(),
                'variable_path_length': variable_cumulative.tolist()})
            if kind == 'biophysical':
                # Recompute correctly transformed full traces. The original
                # per-step cache used raw logits as currents (01 cell50); that
                # contradictory cache is recorded separately below, not treated
                # as the voltage underlying transformed predictions.
                trace_path.append(np.asarray(bio.batch_simulate(params, current)))
                if latent and step < 30:
                    literal_raw_traces.append(np.asarray(bio.batch_simulate(params, variable)))
            if step == 30:
                break
            value, gradient = loss_gradient(variable)
            g = np.asarray(gradient); norm = np.linalg.norm(g, axis=1)
            require(np.isfinite(value) and np.isfinite(g).all() and (norm > 0).all(),
                    'undefined normalized gradient: failed full attack, no epsilon invention')
            losses.append(np.asarray(logsumexp(jnp.asarray(z), axis=1) -
                                      jnp.asarray(z)[jnp.arange(128), target]).tolist())
            next_variable = variable - 5. * gradient / jnp.asarray(norm[:, None])
            if not latent:
                next_variable = jnp.clip(next_variable, 0., 1.)
            variable_cumulative += np.linalg.norm(np.asarray(next_variable - variable), axis=1)
            previous = current; variable = next_variable
        logits_path = np.stack(logits_path)
        curve = [[step * 5, float(np.mean(row.argmax(1) == true)),
                  float(np.mean(row.argmax(1) == target)),
                  float(np.mean(norm_path[step]['pixel_displacement_l2'])),
                  float(np.mean(norm_path[step]['pixel_path_length']))]
                 for step, row in enumerate(logits_path)]
        records.append({'model': kind, 'losses': losses, 'all_norms': norm_path,
            'optimization_variables': np.stack(raw_path).tolist(),
            'full_transformed_biophysical_traces': np.stack(trace_path).tolist() if trace_path else None,
            'literal_raw_variable_trace_cache': np.stack(literal_raw_traces).tolist() if literal_raw_traces else None,
            'source_raw_variable_trace_cache_not_prediction_trace': latent,
            'mlp_attack_historical_producer': 'not recovered; matched explicit reconstruction',
            'norm_axis_convention': 'nominal source steps plus actual L2 displacement/path, all31 entries'})
        all_images.append(np.stack(pixel_path)); all_logits.append(logits_path); curves.append(curve)
    ctx.emit_numeric('clean_images', clean)
    ctx.emit_numeric('attacked_images', np.stack(all_images))
    ctx.emit_numeric('target_labels', target); ctx.emit_numeric('true_labels', true)
    ctx.emit_numeric('attacked_logits', np.stack(all_logits))
    ctx.emit_numeric('norm_curve', np.asarray(curves))
    ctx.emit_json('optimizer_history', {'models': ['biophysical', 'mlp'], 'records': records,
        'attacks': roster, 'profile': p['attack_profile'], 'fit_parent': identity(bundle),
        'literal_figure_first20_only': 'presentation subset; full31 retained',
        'paper_attack_step_count': 'not independently specified; source30 selected explicitly'})


def tuning_all(ctx, p, c, bundle):
    import numpy as np
    x, y = images(ctx, 'test', c)
    model, trained, state = _bio(ctx, p, bundle); model.set_recording('all')
    ix = c['tuning_indices']; labels = y[ix]
    counts = [int(np.sum(labels == k)) for k in range(10)]
    require(all(counts), 'undefined digit denominator; no available-class average')
    response, tuning = [], []
    for params in (decode(state['initial'], model.initial), trained):
        trace = model.trace_batches(params, x[ix], p['evaluation_batch_size'])[:, 784:848, :]
        require(trace.shape[:2] == (len(ix), 64), 'full tuning neuron/image extent')
        spikes = np.any(trace > 20., axis=2)
        tuning.append(np.stack([spikes[labels == k].mean(axis=0) for k in range(10)], axis=1))
        response.append(trace)
    ctx.emit_numeric('all64_tuning', np.stack(tuning))
    ctx.emit_numeric('full_response', np.stack(response))
    ctx.emit_json('stimulus_identity', {'indices': ix, 'ids': [c['test_ids'][i] for i in ix],
        'labels': labels.tolist(), 'digit_counts': counts, 'neuron_ids': list(range(64)),
        'threshold': 'any voltage >20mV', 'states': ['initial', 'trained'],
        'displayed_neurons': [13, 36], 'original_untrained_cache_membership': 'unqualified',
        'fit_parent': identity(bundle)})


def parameters_all(ctx, p, c, bundle):
    import numpy as np
    from scipy.stats import pearsonr
    model, trained, state = _bio(ctx, p, bundle)
    initial = decode(state['initial'], model.initial)
    syn = np.stack([np.concatenate([np.asarray(next(iter(v.values()))).reshape(-1) for v in pp[:4]])
                    for pp in (initial, trained)])
    mechanism = np.stack([np.concatenate([np.asarray(next(iter(v.values()))).reshape(-1) for v in pp[4:]])
                          for pp in (initial, trained)])
    rows = []
    for name, indices in (('first_layer', (0, 1)), ('second_layer', (2, 3))):
        a, b = [np.concatenate([np.asarray(next(iter(pp[k].values()))).reshape(-1) for k in indices])
                for pp in (initial, trained)]
        require(len(a) >= 3 and np.std(a) > 0 and np.std(b) > 0,
                'undefined full layer correlation; no favorable omission')
        r, probability = pearsonr(a, b)
        difference = np.abs(a - b)
        order = np.argsort(-difference, kind='stable')
        boundary_tie = bool(len(a) > 5 and difference[order[4]] == difference[order[5]])
        rows.append({'layer': name, 'n': len(a), 'r': float(r), 'two_sided_p': float(probability),
            'method': 'Pearson two-sided correlation; original implementation not recovered',
            'most_changed_five': None if boundary_tie else order[:5].tolist(), 'boundary_tie': boundary_tie,
            'all_at_least_as_changed_as_fifth': np.flatnonzero(difference >= difference[order[4]]).tolist(),
            'tie_rule': 'five-way selection unavailable if fifth/sixth tie; all tied coordinates retained',
            'original_tie_rule': 'unresolved'})
    ctx.emit_numeric('input_weights', syn)
    ctx.emit_numeric('mechanism_parameters', mechanism)
    ctx.emit_json('parameter_correlations', {'layers': rows, 'fit_parent': identity(bundle),
        'parameter_map': model.parameter_map(), 'states': ['initial', 'trained'],
        'statistical_unit': 'synapse within one trained network, not independent biological replicate',
        'native_historical_test_parity': False})


def run(ctx):
    """Fixed dispatcher; called only inside the owned native worker."""
    p, c = load(ctx)
    if ctx.group == 'J27':
        return fit_all(ctx, p, c)
    bundle = checkpoint_state(ctx, p)
    if ctx.group == 'J26':
        return architecture(ctx, p, c, bundle)
    if ctx.group == 'J28':
        return reset_all(ctx, p, c, bundle)
    if ctx.group == 'J29':
        return attack_all(ctx, p, c, bundle)
    if ctx.group == 'J30':
        return tuning_all(ctx, p, c, bundle)
    if ctx.group == 'J31':
        return parameters_all(ctx, p, c, bundle)
    raise AssertionError('validate_plan must reject every other group')
