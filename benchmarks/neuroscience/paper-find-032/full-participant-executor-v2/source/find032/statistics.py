"""Full subject-level inferential consumers. No computation at import time."""
from dataclasses import dataclass
import hashlib
from .core import Refusal
from .products import ProductKey, participant_products, validate_matrix
from .roster import PARTICIPANTS, CONDITIONS


@dataclass
class GroupResult:
    family: dict
    clusters: dict
    bayes: dict
    axes: tuple
    confusion: object
    policy: dict
    unavailable: dict
    structural: dict



class EndpointUnavailable(Refusal):
    """Only the defined Fisher-domain disposition; resource errors still fail."""
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason

def fisher_by_condition(values):
    """Pearson with ordinal predictability, then Fisher z, within each person.

    Undefined or infinite z is unavailable, never zero/imputed/capped. The
    historical qmd's NA->0 and +/-1->+/-.99 rule remains a separate exact route.
    """
    import numpy as np
    x = np.arange(values.shape[1], dtype=float)
    x -= x.mean()
    y = values - values.mean(axis=1, keepdims=True)
    denominator = np.sqrt((x*x).sum() * (y*y).sum(axis=1))
    if (denominator == 0).any():
        raise EndpointUnavailable('undefined within-person correlation; whole endpoint unavailable')
    r = (y*x[None, :, None, None]).sum(axis=1) / denominator
    if not np.isfinite(r).all() or (np.abs(r) >= 1).any():
        raise EndpointUnavailable('nonfinite Fisher coefficient; no historical clipping in corrected profile')
    return np.arctanh(r)


def comparison_family(products, theory_conditions):
    """All planned identities, with endpoint-local Fisher dependency failures.

    Only EndpointUnavailable is converted to a scientific disposition. No
    resource, library, operation, input or unexpected error is suppressed.
    """
    import numpy as np
    def stack(stim, pipeline, condition, score='accuracy'):
        return np.stack([products[ProductKey(s, stim, pipeline, condition, score)] for s in PARTICIPANTS])
    family, unavailable = {}, {}
    def absent(name, reason, dependencies=()):
        unavailable[name] = {'status': 'unavailable', 'reason': reason,
                             'dependencies': tuple(dependencies), 'subjects_required': 33}
    def fisher(name, values):
        try:
            family[name] = fisher_by_condition(values)
        except EndpointUnavailable as error:
            absent(name, error.reason)
    def difference(name, left, right):
        missing = tuple(key for key in (left, right) if key not in family)
        if missing:
            absent(name, 'required complete Fisher endpoint unavailable', missing)
        else:
            family[name] = family[left] - family[right]
    for stim in ('sound', 'omission'):
        conditions = CONDITIONS if stim == 'sound' else CONDITIONS[1:]
        for pipeline in ('replication', 'empirical_null'):
            for condition in CONDITIONS:
                family['accuracy/' + stim + '/' + pipeline + '/' + condition] = stack(stim, pipeline, condition) - .25
            fisher('fisher/' + stim + '/' + pipeline, np.stack([
                stack(stim, pipeline, c) for c in conditions], axis=1))
        for condition in CONDITIONS:
            family['accuracy_difference/' + stim + '/empirical/' + condition] = (
                stack(stim, 'replication', condition) - stack(stim, 'empirical_null', condition))
        difference('fisher_difference/' + stim + '/empirical',
                   'fisher/' + stim + '/replication', 'fisher/' + stim + '/empirical_null')
    for condition in CONDITIONS:
        names = ('accuracy/sound/theoretical_null/' + condition,
                 'accuracy_difference/sound/theoretical/' + condition)
        if condition not in theory_conditions:
            for name in names:
                absent(name, 'one or more complete subject theoretical endpoints unavailable',
                       ('theoretical_null/' + condition,))
        else:
            theoretical = stack('sound', 'theoretical_null', condition)
            family[names[0]] = theoretical - .25
            family[names[1]] = stack('sound', 'replication', condition) - theoretical
    if tuple(theory_conditions) == CONDITIONS:
        fisher('fisher/sound/theoretical_null', np.stack([
            stack('sound', 'theoretical_null', c) for c in CONDITIONS], axis=1))
    else:
        absent('fisher/sound/theoretical_null', 'complete four-condition theoretical support unavailable',
               tuple('theoretical_null/' + c for c in CONDITIONS if c not in theory_conditions))
    difference('fisher_difference/sound/theoretical',
               'fisher/sound/replication', 'fisher/sound/theoretical_null')
    for pipeline in ('replication', 'empirical_null'):
        for condition in CONDITIONS[1:]:
            family['accuracy/sound/' + pipeline + '/most_likely/' + condition] = stack('sound', pipeline, condition, 'most_likely') - .25
        fisher('fisher/sound/' + pipeline + '/most_likely', np.stack([
            stack('sound', pipeline, c, 'most_likely') for c in CONDITIONS[1:]], axis=1))
    for condition in CONDITIONS[1:]:
        family['accuracy_difference/sound/most_likely_empirical/' + condition] = (
            stack('sound', 'replication', condition, 'most_likely') -
            stack('sound', 'empirical_null', condition, 'most_likely'))
    difference('fisher_difference/sound/most_likely_empirical',
               'fisher/sound/replication/most_likely', 'fisher/sound/empirical_null/most_likely')
    return dict(sorted(family.items())), dict(sorted(unavailable.items()))


def structural_identity_controls(participants, family):
    """Validate the two predeclared identity contrasts; emit no statistics.

    Source-produced provenance plus actual paired arrays/support are required.
    These rows describe internal scientific lineage, not trusted child receipts.
    A mismatch is an integrity failure, never an alternative null test.
    """
    import numpy as np
    controls = {}
    for stim in ('sound', 'omission'):
        name = 'accuracy_difference/' + stim + '/empirical/random'
        coverage = []
        for result in participants:
            row = result.support['structural_random/' + stim]
            if (row['kind'] != 'same_original_random_recording' or
                    row['support_checked'] != 'exact events/original-samples/labels/data/times' or
                    row['fit_route'] != 'paired_condition_random' or not row['event_indices']):
                raise Refusal('missing source-produced random identity provenance')
            if stim == 'sound':
                left = result.support['sound/folds/random/replication']
                right = result.support['sound/folds/random/empirical_null']
                if len(left) != 5 or left != right or any(
                        x['test']['replication'] != x['test']['empirical_null'] for x in left):
                    raise Refusal('random identity contrast did not share the exact five fit/test folds')
            else:
                left = result.support['omission/fit/random/replication']
                right = result.support['omission/fit/random/empirical_null']
                if left != right or left['test_count'] != len(row['event_indices']):
                    raise Refusal('random identity contrast did not share the exact omission fit/test support')
            a = result.products[ProductKey(result.participant, stim, 'replication', 'random', 'accuracy')]
            b = result.products[ProductKey(result.participant, stim, 'empirical_null', 'random', 'accuracy')]
            if not np.array_equal(a, b):
                raise Refusal('source identity control returned unequal actual products')
            coverage.append({'participant': result.participant, **row})
        if (tuple(x['participant'] for x in coverage) != PARTICIPANTS or
                not (family[name] == 0).all()):
            raise Refusal('complete structurally zero random contrast required')
        controls[name] = {'status': 'structural_identity_null',
            'reason': 'identical random recording, selected support, paired fits and actual products',
            'subjects': 33, 'coverage': tuple(coverage), 'inference': None,
            't': None, 'p': None, 'BF10': None,
            'interpretation': 'construction identity control, not evidence for a scientific null'}
    return controls


def cluster_inference(values, *, seed, operation, name):
    import numpy as np
    from scipy.stats import t
    from mne.stats import spatio_temporal_cluster_1samp_test
    if values.shape[0] != 33 or values.ndim != 3 or not np.isfinite(values).all():
        raise Refusal('all 33 finite subject matrices required')
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise Refusal('prospectively fixed seed input required')
    threshold = float(t.ppf(1 - .05 / 2, df=32))
    with operation('cluster-permutation', {'comparison': name, 'subjects': 33, 'permutations': 10000}):
        observed, clusters, probabilities, null = spatio_temporal_cluster_1samp_test(
            values, threshold=threshold, n_permutations=10000, tail=0,
            adjacency=None, n_jobs=1, seed=seed, out_type='mask', verbose=False)
    if not np.isfinite(observed).all() or not np.isfinite(probabilities).all() or not np.isfinite(null).all():
        raise Refusal('nonfinite cluster inference')
    return {'t': observed, 'clusters': tuple(clusters), 'p': probabilities, 'null_max': null,
            'seed': seed, 'permutations_requested': 10000, 'null_draws_observed': len(null),
            'threshold': threshold, 'alpha': .05, 'multiplicity': 'maximum cluster within each named map; not across maps'}


def bf10(values, *, operation, name):
    """Actual R BayesFactor call, matching the paper's named default prior.

    R/rpy2 installation, native-memory ownership and package qualification remain
    explicit deployment prerequisites; no caller dictionary can assert them.
    """
    import numpy as np
    from rpy2 import robjects
    from rpy2.robjects.packages import importr
    if values.shape[0] != 33 or not np.isfinite(values).all():
        raise Refusal('all subject Fisher differences required for BF10')
    with operation('bayes-factor-package', {'package': 'BayesFactor', 'version': '0.9.12-4.6'}):
        installed = str(robjects.r['as.character'](robjects.r['packageVersion']('BayesFactor'))[0])
        if installed.replace('-', '.') != '0.9.12.4.6':
            raise Refusal('unqualified BayesFactor version')
        package = importr('BayesFactor')
    result = np.empty(values.shape[1:], dtype=float)
    for i, j in np.ndindex(result.shape):
        with operation('bayes-factor-cell', {'comparison': name, 'train_index': i, 'test_index': j}):
            test = package.ttestBF(x=robjects.FloatVector(values[:, i, j]), rscale='medium')
            result[i, j] = float(package.extractBF(test, onlybf=True)[0])
    if not np.isfinite(result).all() or (result <= 0).any():
        raise Refusal('finite positive BF10 required')
    return result


def group(participants, *, fixed_seed, operation):
    import numpy as np
    if tuple(x.participant for x in participants) != PARTICIPANTS:
        raise Refusal('full source roster order required; no subset endpoint')
    axes = participants[0].axes
    products = {}
    for result in participants:
        if any(not np.array_equal(a, b) for a, b in zip(axes, result.axes)):
            raise Refusal('actual participant time axes differ')
        for key, array in result.products.items():
            validate_matrix(array, *axes, confusion=key.score == 'confusion')
            products[key] = array
    expected = {key for person in PARTICIPANTS for key in participant_products(person)}
    declared = set()
    for result in participants:
        for row in result.unavailable:
            prefix, condition = row['endpoint'].split('/')
            if prefix != 'theoretical_null' or condition not in CONDITIONS:
                raise Refusal('unknown scientific unavailability disposition')
            declared.add(ProductKey(result.participant, 'sound', prefix, condition, 'accuracy'))
    if set(products) != expected - declared:
        raise Refusal('missing/extra product outside exact declared theoretical endpoints')
    theory_conditions = tuple(c for c in CONDITIONS if all(
        ProductKey(p, 'sound', 'theoretical_null', c, 'accuracy') in products for p in PARTICIPANTS))
    family, unavailable = comparison_family(products, theory_conditions)
    structural = structural_identity_controls(participants, family)
    if (set(family) & set(unavailable) or
            set(family) | set(unavailable) != set(planned_family_names())):
        raise Refusal('complete planned comparison family disposition required')
    if type(fixed_seed) is not int or not 0 <= fixed_seed < 2**32:
        raise Refusal('fixed pre-data seed required')
    clusters = {}
    for name, values in family.items():
        if name in structural:
            continue
        seed = int.from_bytes(hashlib.sha256((str(fixed_seed) + ':' + name).encode()).digest()[:4], 'big')
        clusters[name] = cluster_inference(values, seed=seed, operation=operation, name=name)
    bayes_names = ('fisher_difference/sound/empirical', 'fisher_difference/sound/theoretical',
                   'fisher_difference/sound/most_likely_empirical')
    bayes = {name: bf10(family[name], operation=operation, name=name) for name in bayes_names if name in family}
    confusion = np.stack([products[ProductKey(s, 'sound', 'random_oof', 'random', 'confusion')]
                          for s in PARTICIPANTS]).mean(axis=(0, 1))
    return GroupResult(family, clusters, bayes, axes, confusion,
                       {'fixed_seed': fixed_seed, 'subjects': 33, 'correlation': 'Pearson ordinal predictability',
                        'contrast': 'paired difference of Fisher z; never correlation of accuracy difference',
                        'BF': 'BF10 Cauchy scale sqrt(2)/2', 'cluster_family': planned_family_names(), 'available_cluster_maps': tuple(clusters),
                        'structural_control_maps': tuple(structural),
                        'BF10_planned': bayes_names, 'BF10_available': tuple(bayes),
                        'BF10_unavailable': {name: unavailable[name] for name in bayes_names if name not in bayes},
                        'unavailable_cluster_maps': unavailable,
                        'cross_map_FWER': 'not claimed', 'historical_parity': False}, unavailable, structural)


def planned_family_names():
    names = []
    for stim in ('sound', 'omission'):
        for pipeline in ('replication', 'empirical_null'):
            names.extend('accuracy/'+stim+'/'+pipeline+'/'+c for c in CONDITIONS)
            names.append('fisher/'+stim+'/'+pipeline)
        names.extend('accuracy_difference/'+stim+'/empirical/'+c for c in CONDITIONS)
        names.append('fisher_difference/'+stim+'/empirical')
    names.extend('accuracy/sound/theoretical_null/'+c for c in CONDITIONS)
    names.extend('accuracy_difference/sound/theoretical/'+c for c in CONDITIONS)
    names.extend(('fisher/sound/theoretical_null','fisher_difference/sound/theoretical'))
    for pipeline in ('replication','empirical_null'):
        names.extend('accuracy/sound/'+pipeline+'/most_likely/'+c for c in CONDITIONS[1:])
        names.append('fisher/sound/'+pipeline+'/most_likely')
    names.extend('accuracy_difference/sound/most_likely_empirical/'+c for c in CONDITIONS[1:])
    names.append('fisher_difference/sound/most_likely_empirical')
    return tuple(sorted(names))
