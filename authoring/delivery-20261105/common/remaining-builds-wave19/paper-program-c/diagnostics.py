"""Separately named prospective biological-unit sensitivities.

Literal native run-level inference and its different static/dynamic age splits
remain in the native capture. No function modifies those artifacts or chooses a
new scientific primary outcome. Undefined support makes a sensitivity unavailable.
"""
from core import finite, need, people, seed_for


def age_group(age, policy):
    need(finite(age) and 0 < age < 130, 'Authenticated age in years')
    if policy == 'native_dynamic_numeric':
        return 1 if age <= 34 else 2
    if policy == 'native_static_numeric':
        return 2 if age < 34 else 1
    need(policy == 'harmonized_young_le34', 'Named source or prospective age policy')
    return 'young' if age <= 34 else 'old'


def person_evoked(records):
    import numpy as np
    from core import validate_runs
    validate_runs(records, 'elekta_ae')
    lookup, shape = {}, None
    for r in records:
        need(set(r) == {'person', 'run', 'evoked'}, 'No selected outcomes or partial runs')
        x = np.asarray(r['evoked'], dtype='float64')
        need(x.ndim == 2 and x.shape[1] == 8 and x.size > 0 and np.isfinite(x).all()
             and (shape is None or shape == x.shape), 'Complete finite common time/state grid')
        shape = x.shape
        lookup[(r['person'], r['run'])] = x
    result = np.stack([sum(lookup[(p, r)] / 6 for r in range(1, 7)) for p in people('elekta_ae')])
    need(np.isfinite(result).all(), 'Representable equal-run participant means')
    return result


def subject_signflip_max_copes(person_means, seed=91949, n_perm=1000):
    """Existing task's exact PCG64 whole-person max-|mean|/+1 convention."""
    import numpy as np
    x = np.asarray(person_means, dtype='float64')
    need(x.ndim == 3 and x.shape[0] == 19 and x.shape[2] == 8 and np.isfinite(x).all(),
         'Exactly nineteen complete participant maps')
    need(type(seed) is int and 0 <= seed < 2**64 and n_perm == 1000, 'Fixed sensitivity budget')
    mean = x.mean(axis=0)
    rng = np.random.Generator(np.random.PCG64(seed))
    counts = np.zeros(mean.shape, dtype='int64')
    for _ in range(n_perm):
        signs = rng.choice([-1., 1.], size=19)
        maximum = np.abs((x * signs[:, None, None]).mean(axis=0)).max()
        counts += maximum >= np.abs(mean)
    return {'mean': mean, 'p_fwer': (1 + counts) / (n_perm + 1),
            'unit': 'participant', 'permutations': n_perm, 'seed': seed,
            'native_equivalence_claimed': False}


def harmonized_age(records, values, endpoint):
    """Explicit prospective young-minus-old, complete65-person max-mean test.

    Preserves all full endpoint coordinates and group sizes. This independently
    named sensitivity uses 1000 label permutations and +1 probabilities; it does
    not claim to reproduce native glmtools statistics or historical RNGs.
    """
    import numpy as np
    need([r['person'] for r in records] == people('ctf_static'), 'All65 original age records')
    groups = np.array([age_group(r['age'], 'harmonized_young_le34') == 'young' for r in records])
    x = np.asarray(values, dtype='float64')
    need(x.ndim >= 2 and x.shape[0] == 65 and x.size > 0, 'Full person/endpoint axes')
    if not np.isfinite(x).all() or not groups.any() or groups.all():
        return {'available': False, 'reason': 'undefined_full_support_or_group'}
    def contrast(g):
        return x[g].mean(axis=0) - x[~g].mean(axis=0)
    effect = contrast(groups)
    need(np.isfinite(effect).all(), 'Representable complete contrast')
    seed = seed_for('harmonized_age_sensitivity', endpoint)
    rng = np.random.Generator(np.random.PCG64(seed))
    counts = np.zeros(effect.shape, dtype='int64')
    for _ in range(1000):
        maximum = np.abs(contrast(rng.permutation(groups))).max()
        need(np.isfinite(maximum), 'Representable complete permutation')
        counts += maximum >= np.abs(effect)
    return {'available': True, 'effect_young_minus_old': effect,
            'p_fwer': (1 + counts) / 1001, 'group_sizes': [int(groups.sum()), int((~groups).sum())],
            'policy': 'harmonized_young_le34', 'seed': seed, 'permutations': 1000,
            'native_equivalence_claimed': False}
