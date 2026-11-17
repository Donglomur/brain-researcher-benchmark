"""Concrete future-native operators derived from selected MNIST source cells.

Imports and computations occur only inside explicitly invoked scientific paths.
No pickle, notebook execution, cached accuracy or user-supplied callable is used.
Native dependency/version and original checkpoint correspondence remain gates.
"""
from .vision_inputs import MORPHOLOGIES, PARAMETER_KEYS, identity, require


def encode(parameters):
    import numpy as np
    result = []
    for row in parameters:
        require(type(row) is dict and len(row) == 1, 'one source parameter group')
        key, value = next(iter(row.items()))
        array = np.asarray(value, dtype=np.float64)
        require(np.isfinite(array).all(), 'finite full parameter state')
        result.append({'key': key, 'shape': list(array.shape), 'values': array.reshape(-1).tolist()})
    return result


def decode(rows, template):
    import jax.numpy as jnp
    import numpy as np
    require(type(rows) is list and len(rows) == len(template), 'full parameter group extent')
    out = []
    for row, original in zip(rows, template):
        key, value = next(iter(original.items()))
        require(row['key'] == key and row['shape'] == list(value.shape), 'parameter coordinate join')
        a = np.asarray(row['values'], dtype=np.float64)
        require(a.size == value.size and np.isfinite(a).all(), 'parameter values')
        out.append({key: jnp.asarray(a.reshape(value.shape))})
    return out


class Biophysical:
    def __init__(self, ctx, profile):
        import numpy as np
        import jax
        import jax.numpy as jnp
        import jaxley as jx
        from jaxley.channels import HH, Leak
        from jaxley.synapses import IonotropicSynapse
        from jaxley.connect import fully_connect
        require(jax.config.x64_enabled, 'source x64 environment must be selected before import')
        self.ctx, self.profile = ctx, profile
        self.dt, self.t_max, self.nseg = 0.025, 10.01, 4
        self.scale = 8.0 if profile == 'literal-training02' else 10.0
        levels = 2 if profile == 'literal-training02' else 3
        nt = len(np.arange(0, self.t_max + 2 * self.dt, self.dt))
        self.checkpoints = [int(np.ceil(nt ** (1 / levels)))] * levels
        branch = jx.Branch(jx.Compartment(), 4)
        cell = jx.Cell(branch, [-1])
        cell[0, 1:4].set('length', 40.0)
        cell[0, 1:4].set('radius', 1.0)
        cell[0, 0].set('length', 20.0)
        cell[0, 0].set('radius', 10.0)
        morphs = []
        for name in MORPHOLOGIES:
            ctx.checkpoint()
            path = ctx.input_path('morphology-' + name)
            if profile == 'literal-forward01':
                morphs.append(jx.read_swc(path, nseg=4, assign_groups=True))
            else:
                morphs.append(jx.read_swc(path, nseg=4))
        self.net = net = jx.Network([cell for _ in range(784)] +
            [morphs[i % len(morphs)] for i in range(64)] + [cell for _ in range(10)])
        # Preserve original global NumPy RNG sequencing inside an owned worker.
        np.random.seed(4)
        self.group_members = {}
        for layer, a, b in ((0, 0, 784), (1, 784, 848)):
            exc = np.random.choice(np.arange(a, b), int((b - a) * .75), replace=False)
            inh = np.setdiff1d(np.arange(a, b), exc)
            for suffix, indices in (('exc', exc), ('inh', inh)):
                name = 'layer%d_%s' % (layer, suffix)
                net.cell(indices.tolist()).add_to_group(name)
                self.group_members[name] = indices.tolist()
        for layer, a, b in ((0, 0, 784), (1, 784, 848), (2, 848, 858)):
            net.cell(list(range(a, b))).add_to_group('layer%d' % layer)
        net.layer0.insert(HH()); net.layer1.insert(HH()); net.layer2.insert(Leak())
        net.set('axial_resistivity', 100.0)
        np.random.seed(5)
        for name, pre, post in (('Conns1_exc', net.layer0_exc, net.layer1),
                ('Conns1_inh', net.layer0_inh, net.layer1),
                ('Conns2_exc', net.layer1_exc, net.layer2),
                ('Conns2_inh', net.layer1_inh, net.layer2)):
            fully_connect(pre.cell('all'), post.cell('all'), IonotropicSynapse().change_name(name))
        np.random.seed(0)
        for i, key in enumerate(PARAMETER_KEYS[:4]):
            group = getattr(net, key[:-3])
            w = np.random.randn(len(group.view)) / (784 if i < 2 else 64) / 25
            if i >= 2:
                w *= 4 / self.scale
            group('all').set(key, w)
            group('all').set(key[:-2] + 'k_minus', .25)
        lo = dict(zip(PARAMETER_KEYS, [-5/784/25, -5/784/25,
            -5/64/25*4/self.scale, -5/64/25*4/self.scale, .05, .01, .0001, 30.]))
        hi = dict(zip(PARAMETER_KEYS, [5/784/25, 5/784/25,
            5/64/25*4/self.scale, 5/64/25*4/self.scale, .5, .1, .001, 1000.]))
        self.transform = jx.ParamTransform(lowers=lo, uppers=hi)
        net.set('v', -65.0); net.init_states(); net.delete_trainables()
        for key in PARAMETER_KEYS[:4]:
            getattr(net, key[:-3])('all').make_trainable(key)
        for key in PARAMETER_KEYS[4:]:
            net.cell('all').branch('all').make_trainable(key)
        self.initial = net.get_parameters()
        require(tuple(next(iter(p)) for p in self.initial) == PARAMETER_KEYS, 'native parameter group ABI')
        require(sum(int(next(iter(p.values())).size) for p in self.initial) == ctx.config['parameter_count'],
                'actual morphology-dependent parameter count differs from admitted full contract')
        self.initial_identity = identity(encode(self.initial))
        self.recording = None
        self.set_recording('output')

    def set_recording(self, recording):
        import jax
        require(recording in ('all', 'output'), 'fixed recording topology')
        self.net.delete_recordings(); self.net.delete_stimuli()
        if recording == 'all':
            self.net[:, 0, 0].record()
        else:
            self.net[list(range(848, 858)), 0, 0].record()
        self.recording = recording
        # Rebuild the JIT closure after mutating recordings; never use an earlier
        # cached output-only closure to claim full hidden/input traces.
        def simulate(params, image):
            import jaxley as jx
            currents = jx.datapoint_to_step_currents(.1, 1., .4 * image, self.dt, self.t_max)
            stimuli = self.net[list(range(784)), 0, 3].data_stimulate(currents, None)
            # Source omits delta_t; environment must qualify the native default.
            return jx.integrate(self.net, params=params, data_stimuli=stimuli,
                                checkpoint_lengths=self.checkpoints)
        self.simulate = jax.jit(simulate)
        self.batch_simulate = jax.jit(jax.vmap(simulate, in_axes=(None, 0)))

    def logits(self, params, images):
        return (self.batch_simulate(params, images)[:, -10:, -1] + 65.) / 3.

    def trace_batches(self, params, images, batch_size):
        import numpy as np
        chunks = []
        for start in range(0, len(images), batch_size):
            self.ctx.checkpoint()
            chunks.append(np.asarray(self.batch_simulate(params, images[start:start + batch_size])))
        return np.concatenate(chunks, axis=0)

    def evaluate(self, params, images, batch_size):
        import numpy as np
        out = []
        for start in range(0, len(images), batch_size):
            self.ctx.checkpoint()
            out.append(np.asarray(self.logits(params, images[start:start + batch_size])))
        return np.concatenate(out, axis=0)

    def parameter_map(self):
        start, rows = 0, []
        for p in self.initial:
            key, a = next(iter(p.items()))
            rows.append({'key': key, 'shape': list(a.shape), 'start': start,
                         'stop': start + int(a.size), 'coordinate': 'native-get_parameters-order'})
            start += int(a.size)
        return {'groups': rows, 'exact_parameter_count': start,
            'branch_coordinate_authority': 'native-version/morphology qualification required',
            'group_members': self.group_members, 'morphology_order': list(MORPHOLOGIES),
            'hidden_morphology': [MORPHOLOGIES[i % 55] for i in range(64)],
            'initial_identity': self.initial_identity, 'profile': self.profile,
            'paper_segment_length_um': 10, 'source_segment_length_um': 40,
            'source_trains_axial_resistivity': True}

    def train(self, train_x, train_y, test_x, test_y):
        import numpy as np
        import jax
        import jax.numpy as jnp
        import optax
        import tensorflow as tf
        from jax.scipy.special import logsumexp
        require(self.profile == 'literal-training02', 'training uses02 source profile only')
        self.set_recording('output')
        opt_params = self.transform.inverse(self.initial)
        def loss(op, x, y):
            logits = self.logits(self.transform.forward(op), x)
            return jnp.mean(logsumexp(logits, axis=1) - logits[jnp.arange(len(y)), y])
        loss_grad = jax.jit(jax.value_and_grad(loss))
        steps = 60000 // 16
        warm = optax.constant_schedule(1e-3)
        decay = optax.warmup_cosine_decay_schedule(init_value=1e-5, peak_value=5e-3,
            warmup_steps=int(steps * .25), decay_steps=int(steps * 5 - steps * .25),
            end_value=1e-6, exponent=1.)
        def schedule(k):
            return jax.lax.cond(k < steps * 2, lambda: warm(k), lambda: decay(k - steps * 2))
        optimizer = optax.chain(optax.clip_by_global_norm(1.), optax.adam(schedule))
        state = optimizer.init(opt_params)
        np.random.seed(0); tf.random.set_seed(0)
        ds = tf.data.Dataset.from_tensor_slices((train_x, train_y))
        ds = ds.shuffle(ds.cardinality().numpy()).batch(16)
        history, candidates = [], []
        # The source selects by exposed first1024 test accuracy. Preserve that
        # explicitly; this is neither a hidden validation set nor a new protocol.
        for epoch in range(7):
            for batch, (bx, by) in enumerate(ds):
                self.ctx.checkpoint()
                value, grad = loss_grad(opt_params, bx.numpy(), by.numpy())
                require(bool(np.isfinite(value)), 'nonfinite training loss; no successful partial fit')
                updates, state = optimizer.update(grad, state)
                opt_params = optax.apply_updates(opt_params, updates)
                history.append([epoch, batch, float(value)])
                if batch % 300 == 0:
                    params = self.transform.forward(opt_params)
                    pred = self.evaluate(params, test_x[:1024], 16)
                    acc = float(np.mean(pred.argmax(1) == test_y[:1024]))
                    candidates.append({'epoch': epoch, 'batch': batch, 'test_accuracy': acc,
                                       'parameters': encode(params)})
            require(batch + 1 == steps, 'full3750 batches per epoch')
        final = self.transform.forward(opt_params)
        pred = self.evaluate(final, test_x[:1024], 16)
        candidates.append({'epoch': 6, 'batch': steps - 1,
            'test_accuracy': float(np.mean(pred.argmax(1) == test_y[:1024])), 'parameters': encode(final)})
        selected = max(range(len(candidates)), key=lambda k: candidates[k]['test_accuracy'])
        return {'initial': encode(self.initial), 'selected': candidates[selected]['parameters'],
            'final': encode(final), 'history': history, 'checkpoint_states': candidates,
            'selection_index': selected, 'selection_rule': 'first-max-exposed-first1024-test',
            'historical_checkpoint_filename_join': 'unresolved', 'parameter_map': self.parameter_map()}


def baseline_init(kind, seed):
    import jax
    import jax.numpy as jnp
    dims = (784, 10) if kind == 'linear' else (784, 64, 10)
    keys = jax.random.split(jax.random.PRNGKey(seed), len(dims) - 1)
    out = []
    for i, (a, b) in enumerate(zip(dims, dims[1:])):
        out.extend([{'w%d' % i: jax.random.normal(keys[i], (a, b)) / jnp.sqrt(float(a))},
                    {'b%d' % i: jnp.zeros((b,))}])
    return out


def baseline_logits(params, x):
    import jax.numpy as jnp
    h = x
    for k in range(len(params) // 2):
        h = h @ params[2*k]['w%d' % k] + params[2*k+1]['b%d' % k]
        if k + 1 < len(params) // 2:
            h = jnp.maximum(h, 0.)
    return h


def train_baseline(ctx, kind, seed, recipe, x, y):
    """Concrete explicit reconstruction; no historical recipe is claimed."""
    import jax
    import jax.numpy as jnp
    import numpy as np
    import optax
    from jax.scipy.special import logsumexp
    params = baseline_init(kind, seed); initial = encode(params)
    optimizer = (optax.adam if recipe['optimizer'] == 'adam' else optax.sgd)(recipe['learning_rate'])
    state = optimizer.init(params)
    def loss(p, bx, by):
        z = baseline_logits(p, bx)
        return jnp.mean(logsumexp(z, axis=1) - z[jnp.arange(len(by)), by])
    grad = jax.jit(jax.value_and_grad(loss))
    key = jax.random.PRNGKey(seed); history = []
    for epoch in range(recipe['epochs']):
        key, sub = jax.random.split(key)
        indices = np.asarray(jax.random.permutation(sub, len(x)))
        for start in range(0, len(x), recipe['batch_size']):
            ctx.checkpoint(); ix = indices[start:start + recipe['batch_size']]
            value, g = grad(params, x[ix], y[ix])
            require(bool(np.isfinite(value)), 'nonfinite reconstructed baseline loss')
            updates, state = optimizer.update(g, state)
            params = optax.apply_updates(params, updates)
            history.append([epoch, start, float(value)])
    return {'initial': initial, 'selected': encode(params), 'final': encode(params),
            'history': history, 'selection_rule': 'final-epoch',
            'recipe': recipe, 'historical_trainer': 'not recovered'}
