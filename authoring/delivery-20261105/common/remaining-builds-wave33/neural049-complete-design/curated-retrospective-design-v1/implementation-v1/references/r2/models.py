"""Complete scientific one-fit/assigned-batch API for independent bank R2."""
import math
from types import MappingProxyType
from .budget import require
from .contracts import (numpy, scope_check, batch_check, labels_check, project,
                        environment_check)
from .features import (channel_moments, column_moments, scalar_moments,
                       feature_matrix, apply_columns)
from .estimators import ridge, boost, boost_predict


def candidate_specs():
    configs = []
    for exponent in range(-6, 3):
        configs.append({'family': 'R', 'lambda': 10.**exponent})
    for leaves in (4, 16):
        for penalty in (1, 10):
            for trees in (100, 300):
                configs.append({'family': 'B', 'leaves': leaves, 'l2': penalty, 'trees': trees})
    for width in (16, 32):
        for decay in (.001, .1):
            for epochs in (80, 240):
                configs.append({'family': 'T', 'width': width, 'decay': decay, 'epochs': epochs})
    return tuple(MappingProxyType(x) for x in configs)


def check_config(configuration):
    require(type(configuration) is dict, 'configuration dictionary')
    require(any(set(configuration) == set(c) and all(type(configuration[k]) is type(c[k])
                and configuration[k] == c[k] for k in c) for c in candidate_specs()), 'one of full 25 configurations')
    return dict(configuration)


def full_reservation(n, c, configuration, env, budget):
    p = 6+(48 if configuration['family'] == 'T' else 165)*c
    base = n*c*5000*48 + n*p*64 + p*128 + 1000000
    if configuration['family'] == 'R':
        m = min(n, p)
        extra = 8*(6*n*p+6*(n+p)*m+12*m*m+8*p+8*n)
    elif configuration['family'] == 'B':
        extra = (n*configuration['leaves']+configuration['trees']*configuration['leaves']*p*64)*64+n*p*32
    else:
        from .temporal import tensor_bound
        extra = tensor_bound(n, c, configuration['width'], env['native_workspace_bytes'])
    budget.workspace(base+extra+env['native_workspace_bytes'], 'complete fit/predict source-level live reservation')


def fit_cost_bounds(n, c, configuration, scope):
    """Conservative source-operation ceiling; native physical work stays external.

    Includes repeated full features/validations, all configured rounds/epochs,
    explicit lowering/backward and full-roster SHA serialization per draw. These
    intentionally generous constants never license truncating a fit to meet a cap.
    """
    p = 6+165*c
    alloc = n*c*5000*512+n*p*256+1000000
    work = n*c*5000*2048+n*p*128+1000000
    serialized = 1000000
    if configuration['family'] == 'R':
        m = min(n,p)
        alloc += 8*(8*n*p+8*(n+p)*m+16*m*m+16*p+16*n)
        work += 64*(n*p*m+m**3+p*m)
    elif configuration['family'] == 'B':
        leaves, trees = configuration['leaves'], configuration['trees']
        alloc += trees*(n*leaves+p*64*leaves*2+n*128)*256+n*p*64
        work += trees*leaves*p*(n*32+64*64)+p*n*128
        serialized += trees*leaves*4096+p*64*128
    else:
        from .temporal import parameter_shapes, tensor_bound
        width, epochs = configuration['width'], configuration['epochs']
        params = sum(math.prod(shape) for _,shape in parameter_shapes(c,width))
        steps = epochs*((n+min(32,n)-1)//min(32,n))
        graph = tensor_bound(n,c,width,scope['environment']['native_workspace_bytes'])
        draws = params + epochs*n*(3*width*1000+width+1)
        tuple_bound = 4096+12*sum(len(e)+2 for e in scope['training_ids'])+64*len(scope['training_days'])+12*len(scope['base_generation'])
        serialized += draws*tuple_bound + epochs*n*4096
        alloc += steps*graph*16+params*256+epochs*n*4096
        work += epochs*n*(2*c*25*5000*width+6*width*width*9*1000)*32
        work += draws*(4096+128*n)+steps*params*512
    return {'allocation_bytes': alloc, 'elements': alloc, 'work': work, 'serialized_bytes': serialized}


def fit(scope, batch, labels, configuration, budget):
    scope_check(scope)
    config = check_config(configuration)
    environment_check(scope['environment'], numerical=True)
    n, c = batch_check(batch, scope['view'], budget)
    require(n > 0 and scope['training_ids'] == batch['ids'] and scope['axis'] == batch['axis'],
            'exact full training support')
    budget.preflight(fit_cost_bounds(n,c,config,scope), 'complete selected fit schedule')
    labels_check(labels, n, scope['endpoint'], budget)
    full_reservation(n, c, config, scope['environment'], budget)
    channel = channel_moments(batch, scope['view'], budget)
    features = feature_matrix(batch, scope['view'], channel, budget, scalar_only=config['family'] == 'T')
    feature_stats = column_moments(features, budget)
    z = apply_columns(features, *feature_stats, budget)
    budget.ops(n*8, 'training-only target moments')
    _, target_mean, target_sd = scalar_moments(labels)
    target_scale = target_sd if target_sd > 0 else 1.
    np = numpy()
    budget.arrays(n*16, 'standardized scalar training targets')
    y = (labels-target_mean)/target_scale
    arrays = dict(zip(('channel_mean', 'channel_scale', 'channel_active'), channel))
    arrays.update(dict(zip(('feature_mean', 'feature_scale', 'feature_active'), feature_stats)))
    meta = {'scope': scope, 'configuration': config, 'target_mean': target_mean,
            'target_scale': target_scale, 'channels': c, 'features': z.shape[1],
            'training_rows': n, 'feature_order': 'timing;channel/window/band+early-baseline;channel/window/mask-stat',
            'tensor_bin_order': 'time-bin-major: mean[W],max[W]',
            'intercept_standardized': 0., 'disposition': 'complete', 'actual_iterative_steps': 0}
    if bool((labels == labels[0]).all()):
        model = {'kind': 'constant', 'value': float(labels[0])}
        meta['disposition'] = 'constant_label_analytic_fit'
    elif config['family'] == 'R':
        beta, singular = ridge(z, y, config['lambda'], budget)
        arrays['beta'], arrays['singular_values'] = beta, singular
        model = {'kind': 'R', 'solve': 'full_nontruncated_svd', 'singular_directions': min(n, z.shape[1])}
    elif config['family'] == 'B':
        model = {'kind': 'B', **boost(z, y, config, budget)}
        meta['actual_iterative_steps'] = config['trees']
    else:
        from .temporal import train
        network, work = train(scope, batch, channel, z, y, config, budget)
        arrays.update(network)
        model = {'kind': 'T', **work}
        meta['actual_iterative_steps'] = work['steps']
    budget.tick('fit complete before state handoff')
    return {'schema': 'neural049_r2_state_v1', 'meta': meta, 'arrays': arrays,
            'model': model, 'work': budget.snapshot()}


def predict(state, batch, budget):
    require(type(state) is dict and state.get('schema') == 'neural049_r2_state_v1', 'R2 safe state')
    meta, arrays, model = state['meta'], state['arrays'], state['model']
    scope = meta['scope']
    scope_check(scope)
    config = check_config(meta['configuration'])
    environment_check(scope['environment'], numerical=True)
    n, c = batch_check(batch, scope['view'], budget)
    require(batch['axis'] == scope['axis'] and c == meta['channels'], 'unchanged complete channel axis')
    full_reservation(n, c, config, scope['environment'], budget)
    np = numpy()
    if n == 0:
        budget.arrays(0, 'explicit empty assigned batch')
        raw = np.empty(0, dtype=np.float64)
    elif model['kind'] == 'constant':
        budget.arrays(n*8, 'constant analytic predictions')
        raw = np.full(n, model['value'], dtype=np.float64)
    else:
        require(model['kind'] == config['family'], 'state family join')
        channel = tuple(arrays[k] for k in ('channel_mean', 'channel_scale', 'channel_active'))
        values = feature_matrix(batch, scope['view'], channel, budget, scalar_only=config['family'] == 'T')
        stats = tuple(arrays[k] for k in ('feature_mean', 'feature_scale', 'feature_active'))
        require(values.shape[1] == meta['features'] and all(v.shape == (values.shape[1],) for v in stats), 'feature state shape')
        z = apply_columns(values, *stats, budget)
        if model['kind'] == 'R':
            require(arrays['beta'].shape == (z.shape[1],), 'full ridge coefficient shape')
            budget.arrays(n*16, 'ridge prediction and inversion')
            budget.ops(n*z.shape[1]*2, 'complete ridge prediction')
            value = z @ arrays['beta'] + meta['intercept_standardized']
        elif model['kind'] == 'B':
            require(len(model['trees']) == config['trees'], 'complete boost state')
            value = boost_predict(model, z, budget)
        else:
            from .temporal import infer
            require(model['epochs'] == config['epochs'], 'full temporal epoch state')
            value = infer(scope, batch, channel, z, config, arrays, budget)
        budget.arrays(n*16, 'inverse target scaling')
        raw = np.asarray(value*meta['target_scale']+meta['target_mean'], dtype=np.float64)
    require(raw.shape == (n,) and bool(np.isfinite(raw).all()), 'complete finite raw output')
    projected = project(raw, scope['endpoint'], budget)
    budget.arrays(n*c*5000+n*8, 'complete zero-neural-support flags', live=batch['mask'].nbytes*3+n*64)
    zero_support = ~batch['mask'].reshape(n, c*5000).any(axis=1)
    budget.tick('complete immutable prediction')
    return {'schema': 'neural049_r2_predictions_v1', 'ids': list(batch['ids']),
            'raw': raw, 'projected': projected, 'zero_neural_support': zero_support,
            'rows': n, 'empty_assigned_batch': n == 0, 'work': budget.snapshot()}
