"""Closed vision family metadata and genuine JobContext input joins.

No authentic operands, native imports or RNG occur at module import. Metadata is
an input contract, never an issuer of scientific/native qualification.
"""
import hashlib
import json

MORPHOLOGIES = tuple(('n171 n174 n130 n400 n404 n140 n127 n122 n412 n125 '
    'n403 n420 n407 n417 n144 n141 n145 n410 n129 n416 n414 n408 n142 n406 '
    'n179 n177 n411 n181 n184 n402 n176 n409 n415 n422 n123 n121 n401 n128 '
    'n421 n418 n126 n172 n413 n170 n175 n178 n173 n405 n183 n143 n180 n419 '
    'n120 n423 n182').split())
PARAMETER_KEYS = ('Conns1_exc_gS', 'Conns1_inh_gS', 'Conns2_exc_gS',
    'Conns2_inh_gS', 'HH_gNa', 'HH_gK', 'HH_gLeak', 'axial_resistivity')
RESET_GROUPS = {'trained': (), 'first_layer': (0, 1), 'second_layer': (2, 3),
    'sodium': (4,), 'potassium': (5,), 'leak': (6,),
    'all_channels': (4, 5, 6), 'axial_resistivity': (7,)}
ACTIONS = {'J26': 'architecture', 'J27': 'fit_all', 'J28': 'reset_all',
    'J29': 'attack_all', 'J30': 'tuning_all', 'J31': 'parameters_all'}
PRODUCT_NAMES = {
    'J26': ('architecture_map', 'full_logits', 'hidden_voltage', 'parameter_map'),
    'J27': ('full_test_logits', 'image_labels', 'fit_history', 'fit_parameter_identity'),
    'J28': ('initial_parameters', 'trained_parameters', 'reset_parameters', 'reset_logits', 'reset_membership'),
    'J29': ('clean_images', 'attacked_images', 'target_labels', 'true_labels', 'attacked_logits', 'norm_curve', 'optimizer_history'),
    'J30': ('all64_tuning', 'stimulus_identity', 'full_response'),
    'J31': ('input_weights', 'mechanism_parameters', 'parameter_correlations')}


class VisionInputError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise VisionInputError(message)


def integer(x, name, minimum=0):
    require(type(x) is int and x >= minimum, name)
    return x


def pin(x, name):
    require(type(x) is str and len(x) == 64 and
            all(c in '0123456789abcdef' for c in x), name)
    return x


def identity(value):
    # Same bytes as runtime.strict.canonical_bytes / JobContext.emit_json.
    return hashlib.sha256((json.dumps(value, sort_keys=True, separators=(',', ':'),
        allow_nan=False) + '\n').encode()).hexdigest()


def validate_plan(group, action, p):
    require(group in ACTIONS and action == ACTIONS[group], 'closed vision action')
    require(type(p) is dict and p.get('schema') == 'jaxley_vision_plan_v1', 'vision plan')
    require(p.get('model_profile') in ('literal-training02', 'literal-forward01'),
            'paper constructor is not resolved by a profile label')
    require(p.get('historical_parity') is False, 'historical/native parity remains unqualified')
    pin(p.get('cohort_sha256'), 'bound cohort identity')
    require(p.get('reset_families') == list(RESET_GROUPS), 'complete eight reset conditions')
    require(p.get('hidden_ids') == list(range(64)), 'all64 hidden identities')
    require(p.get('morphology_order') == list(MORPHOLOGIES), 'source morphology order')
    fits = p.get('fits')
    require(type(fits) is list, 'complete fit roster')
    require(len({r['id'] for r in fits}) == len(fits), 'duplicate fit identity')
    for kind, count in (('linear', 50), ('mlp', 50), ('biophysical', 1)):
        rows = [r for r in fits if r['kind'] == kind]
        require(len(rows) == count, 'paper fifty/fifty/one complete fit roster')
        require(len({r['seed'] for r in rows}) == len(rows), 'distinct initialization seeds')
        for r in rows:
            require(type(r['id']) is str and r['id'], 'fit identity')
            integer(r['seed'], 'fit seed')
    require(all(r['kind'] in ('linear', 'mlp', 'biophysical') for r in fits), 'fit family')
    bio = next(r for r in fits if r['kind'] == 'biophysical')
    require(bio['seed'] == 0, 'source weight initialization seed0')
    require(p.get('selected_biophysical_fit') == bio['id'], 'same biophysical parent')
    require(p.get('selected_mlp_fit') in [r['id'] for r in fits if r['kind'] == 'mlp'],
            'bound comparison MLP')
    recipe = p.get('baseline_recipe')
    require(type(recipe) is dict and recipe.get('status') == 'explicit-reconstruction',
            'missing historical linear/MLP trainer cannot be inferred')
    pin(recipe.get('selection_sha256'), 'pre-exposure reconstruction selection')
    require(recipe.get('optimizer') in ('adam', 'sgd') and
            recipe.get('initializer') == 'jax-normal-fan-in' and
            recipe.get('selection') == 'final-epoch', 'explicit baseline implementation')
    integer(recipe.get('epochs'), 'baseline epochs', 1)
    integer(recipe.get('batch_size'), 'baseline batch', 1)
    require(type(recipe.get('learning_rate')) in (float, int) and
            0 < recipe['learning_rate'] < float('inf'), 'finite positive baseline LR')
    require(p.get('attack_profile') in ('literal-logit-train01', 'paper-pixel-test'),
            'distinct attack profile')
    require(p.get('attack_steps') == 30 and p.get('attack_lr') == 5.0,
            'full source30-step sweep; paper uses explicit source-derived horizon')
    require(p.get('nominal_sweep') == [5 * k for k in range(31)], 'unthinned nominal grid')
    require(p.get('zero_gradient') == 'fail-with-disposition', 'no undefined normalized update')
    integer(p.get('evaluation_batch_size'), 'bounded evaluation batch', 1)
    integer(p.get('required_working_bytes'), 'full declared native memory', 1)
    integer(p.get('native_trace_samples'), 'qualified native trace sample count', 1)
    integer(p.get('parameter_count'), 'qualified morphology-dependent parameter count', 50817)
    return p


def validate_cohort(p, c):
    require(identity(c) == p['cohort_sha256'], 'cohort must match selected complete identity')
    require(c.get('schema') == 'mnist_full_identity_v1', 'cohort schema')
    require(c.get('train_count') == 60000 and c.get('test_count') == 10000,
            'complete original MNIST population')
    for split, count in (('train', 60000), ('test', 10000)):
        ids = c.get(split + '_ids')
        require(type(ids) is list and len(ids) == count and len(set(ids)) == count,
                'unique full image roster')
    require(not set(c['train_ids']) & set(c['test_ids']), 'train/test identity collision')
    for name in ('architecture', 'reset', 'tuning'):
        rows = c.get(name + '_indices')
        require(type(rows) is list and rows and len(rows) == len(set(rows)), 'complete declared support')
        require(all(type(i) is int and 0 <= i < 10000 for i in rows), 'test support index')
    require(c.get('reset_indices') == list(range(1024)), 'literal reset first1024 support')
    require(c.get('architecture_indices') == list(range(256)), 'literal trace first256 support')
    # The before-training saved tuning cache has no selected producer. Its exact
    # membership must be independently supplied; no first256 historical assertion.
    pin(c.get('tuning_support_selection_sha256'), 'unresolved tuning membership selection')
    attacks = c.get('attacks')
    require(type(attacks) is list and len(attacks) == 128, 'all128 paired attacks')
    require(len({r['index'] for r in attacks}) == 128, 'attack membership duplicates')
    split = 'train' if p['attack_profile'] == 'literal-logit-train01' else 'test'
    for r in attacks:
        require(r.get('split') == split and type(r.get('index')) is int and
                0 <= r['index'] < c[split + '_count'], 'attack split/domain/index')
        require(type(r.get('target')) is int and 0 <= r['target'] < 10, 'wrong-target coordinate')
        require(r.get('image_id') == c[split + '_ids'][r['index']], 'attack original identity')
    pin(c.get('attack_selection_sha256'), 'actual attack membership/target producer')
    return c


def load(ctx):
    p = validate_plan(ctx.group, ctx.action, ctx.config)
    require(p['required_working_bytes'] <= ctx.limits['array_memory_bytes'],
            'full intermediates not admitted; no silent thinning')
    require(ctx.inputs['vision-cohort']['sha256'] == p['cohort_sha256'],
            'selected canonical cohort bytes must match actual mounted input')
    c = validate_cohort(p, ctx.read_json('vision-cohort'))
    validate_outputs(ctx, p, c)
    ctx.record('vision-method', {'plan_sha256': identity(p), 'cohort_sha256': identity(c),
        'model_profile': p['model_profile'], 'attack_profile': p['attack_profile'],
        'historical_parity': False, 'cached_accuracy_literals_used': False})
    return p, c


def validate_outputs(ctx, p, c):
    """Finite pre-computation output extent join, with no array evaluation."""
    t, npar, n = p['native_trace_samples'], p['parameter_count'], len(c['tuning_indices'])
    shapes = {
        'J26': {'full_logits': [256, 10], 'hidden_voltage': [256, 858, t]},
        'J27': {'full_test_logits': [101, 10000, 10], 'image_labels': [10000]},
        'J28': {'initial_parameters': [npar], 'trained_parameters': [npar],
                'reset_parameters': [8, npar], 'reset_logits': [8, 1024, 10]},
        'J29': {'clean_images': [128, 784], 'attacked_images': [2, 31, 128, 784],
                'target_labels': [128], 'true_labels': [128],
                'attacked_logits': [2, 31, 128, 10], 'norm_curve': [2, 31, 5]},
        'J30': {'all64_tuning': [2, 64, 10], 'full_response': [2, n, 64, t]},
        'J31': {'input_weights': [2, 50816], 'mechanism_parameters': [2, npar - 50816]}}
    require(set(ctx.products) == set(PRODUCT_NAMES[ctx.group]), 'full closed group products')
    numeric_bytes = 0
    for name, row in ctx.products.items():
        if name not in shapes[ctx.group]:
            require(row['format'] == 'json', 'structured complete provenance product')
            continue
        expected = shapes[ctx.group][name]
        dtype = 'int64-le' if name in ('image_labels', 'target_labels', 'true_labels') else 'float64-le'
        require(row['format'] == 'jaxley-flat-numeric-v1' and row['shape'] == expected
                and row['dtype'] == dtype, 'full numeric product coordinate extent/dtype')
        extent = 8
        for axis in expected:
            extent *= axis
        require(extent <= ctx.limits['output_member_bytes'], 'full output member not admitted')
        numeric_bytes += extent
    # This is a proven lower bound, not a fabricated upper bound on JAX/XLA,
    # optimizer or morphology memory. Full host/native peak capacity is gated.
    require(numeric_bytes <= ctx.limits['output_bytes'] and
            numeric_bytes <= p['required_working_bytes'], 'full numeric output lower bound')
    ctx.record('output-capacity-lower-bound', {'numeric_bytes': numeric_bytes,
        'json_state_traces_and_native_workspace_additional': True,
        'physical_peak_known': False})


def images(ctx, split, c):
    import numpy as np
    x = ctx.read_array(split + '-images')
    y = ctx.read_array(split + '-labels')
    n = c[split + '_count']
    require(x.shape in ((n, 28, 28), (n, 28, 28, 1)) and x.dtype == np.uint8,
            'original complete uint8 MNIST images')
    require(y.shape == (n,) and y.dtype.kind in 'iu' and ((y >= 0) & (y < 10)).all(),
            'complete ten-class labels')
    return x.reshape(n, 784).astype(np.float64) / 255.0, y


def checkpoint_state(ctx, p):
    expected = p.get('fit_state_sha256')
    pin(expected, 'actual captured J27 fit-state identity')
    require(ctx.inputs['vision-fit-state']['sha256'] == expected,
            'actual mounted parent must be the selected captured artifact')
    bundle = ctx.read_json('vision-fit-state')
    require(identity(bundle) == expected, 'captured fit-state content join')
    require(bundle.get('schema') == 'vision_full_fit_state_v1' and
            bundle.get('cohort_sha256') == p['cohort_sha256'] and
            bundle.get('model_profile') == p['model_profile'], 'same input/model parent')
    require(bundle.get('fit_roster') == p['fits'], 'same complete fit roster')
    require(set(bundle.get('fits', {})) == {r['id'] for r in p['fits']}, 'complete captured fit states')
    # Outer compiler must bind this input to actual captured J27 output. A JSON
    # hash supplied without that parent relation is not an authority issuer.
    return bundle
