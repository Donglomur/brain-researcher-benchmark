"""Bounded scalar producers for the declared hundred-model analysis.

These functions calculate numeric outputs; they do not read files, load models,
call a backend or attest native-library/historical arithmetic parity. Only plain
Python list/tuple/dict data is admitted. None is explicit undefined coverage,
never a license to remove an observation. The owner binds scientific identities.

Budget counts conservative logical scalar work and bounds each admitted compound
shape. It excludes import/native I/O and is NOT an allocator or physical RSS meter.
Deadline checks precede work and returning every public result. A surrounding
process controller is still required for a hard wall-clock/process-memory limit.
"""
import math
import time


class NumericalError(ValueError):
    pass


class BudgetError(NumericalError):
    pass


def _need(ok, why):
    if not ok:
        raise NumericalError(why)


class Budget:
    """One cumulative meter; callers retain it across an entire selected job."""
    def __init__(self, max_work, max_elements, deadline_ns):
        _need(type(max_work) is int and 0 < max_work <= 10**18, 'positive bounded max_work')
        _need(type(max_elements) is int and 0 < max_elements <= 10**9, 'positive bounded max_elements')
        _need(type(deadline_ns) is int and deadline_ns > 0, 'absolute monotonic deadline_ns')
        self.max_work = max_work
        self.max_elements = max_elements
        self.deadline_ns = deadline_ns
        self.used_work = 0
        self.maximum_elements_seen = 0
        self.requests = 0
        self.failed = False
        self.tick()

    def tick(self):
        if self.failed:
            raise BudgetError('meter is terminal after failure')
        if time.monotonic_ns() >= self.deadline_ns:
            self.failed = True
            raise BudgetError('numerical deadline expired')

    def charge(self, work, elements=0):
        self.tick()
        _need(type(work) is int and work >= 0 and type(elements) is int and elements >= 0,
              'nonnegative exact work and element extent')
        self.requests += 1
        self.maximum_elements_seen = max(self.maximum_elements_seen, elements)
        # Charge the attempted operation before refusal: no rollback of failed cost.
        self.used_work += work
        if self.used_work > self.max_work or elements > self.max_elements:
            self.failed = True
            raise BudgetError('logical work or compound element bound exceeded')

    def observation(self):
        return {'used_work': self.used_work, 'max_work': self.max_work,
                'maximum_elements_seen': self.maximum_elements_seen,
                'max_elements': self.max_elements, 'requests': self.requests,
                'terminal_failure': self.failed,
                'physical_RSS_and_native_IO_measured': False}


def _budget(budget):
    _need(type(budget) is Budget, 'exact cumulative Budget required')
    budget.tick()


def _sequence(value, why):
    _need(type(value) in (tuple, list), why)
    return len(value)


def _number(value, nullable=False):
    if nullable and value is None:
        return None
    _need(type(value) in (float, int), 'finite numeric scalar; bool/subclasses forbidden')
    if type(value) is int:
        _need(value.bit_length() <= 1024, 'bounded integer before float conversion')
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise NumericalError('finite representable scalar') from None
    _need(math.isfinite(result), 'finite numeric scalar')
    return result


def _vector(values, budget, *, nullable=False, minimum=1):
    n = _sequence(values, 'plain numeric vector')
    _need(n >= minimum, 'vector support is too short')
    budget.charge(n, 2*n)
    result = []
    for v in values:
        budget.tick()
        result.append(_number(v, nullable))
    return tuple(result)


def _condensed(values, budget):
    result = _vector(values, budget, nullable=True)
    k = len(result)
    root = math.isqrt(1+8*k)
    _need(root*root == 1+8*k and (1+root) % 2 == 0,
          'complete triangular condensed RDM support')
    _need(all(v is None or 0 <= v <= 2 for v in result),
          'correlation-distance RDM range [0,2] or explicit undefined')
    return result


def _matrix(values, budget, *, nullable=False, min_rows=1, min_cols=1):
    n = _sequence(values, 'plain row matrix')
    _need(n >= min_rows, 'matrix row support')
    k = _sequence(values[0], 'plain first matrix row')
    _need(k >= min_cols, 'matrix column support')
    budget.charge(n, n*k*2 + n)
    result = []
    for row in values:
        budget.tick()
        _need(_sequence(row, 'plain matrix row') == k, 'rectangular complete matrix')
        result.append(_vector(row, budget, nullable=nullable, minimum=min_cols))
    return tuple(result)


def _mean(values, budget):
    budget.charge(3*len(values), 2*len(values))
    if any(v is None for v in values):
        return None
    maximum = max(abs(v) for v in values)
    if maximum == 0:
        return 0.0
    # Scaling avoids overflow without changing which observations are included.
    value = math.fsum(v/maximum for v in values)/len(values)
    return min(1.0, max(-1.0, value))*maximum


def _units(values, budget):
    n = len(values)
    budget.charge(8*n, 4*n)
    if any(v is None for v in values):
        return None
    maximum = max(abs(v) for v in values)
    if maximum == 0:
        return None
    scaled = tuple(v/maximum for v in values)
    center = math.fsum(scaled)/n
    centered = tuple(v-center for v in scaled)
    norm = math.sqrt(math.fsum(v*v for v in centered))
    if norm == 0:
        return None
    result = tuple(v/norm for v in centered)
    budget.tick()
    return result


def _pearson(a, b, budget):
    ua, ub = _units(a, budget), _units(b, budget)
    if ua is None or ub is None:
        return None
    budget.charge(2*len(a), len(a))
    return max(-1.0, min(1.0, math.fsum(x*y for x, y in zip(ua, ub))))


def _ranks(values, budget):
    n = len(values)
    budget.charge(4*n*max(1, n.bit_length()) + 4*n, 5*n)
    if any(v is None for v in values):
        return None
    order = sorted(range(n), key=values.__getitem__)
    budget.tick()
    result = [0.0]*n
    start = 0
    while start < n:
        budget.tick()
        end = start+1
        while end < n and values[order[end]] == values[order[start]]:
            budget.tick()
            end += 1
        average = (start+1+end)/2.0
        for position in range(start, end):
            budget.tick()
            result[order[position]] = average
        start = end
    return tuple(result)


def _spearman(a, b, budget):
    ra, rb = _ranks(a, budget), _ranks(b, budget)
    if ra is None or rb is None:
        return None
    return _pearson(ra, rb, budget)


def spearman(a, b, *, budget):
    """Average-rank Spearman; constant/undefined support returns None."""
    _budget(budget)
    x = _vector(a, budget, nullable=True, minimum=2)
    y = _vector(b, budget, nullable=True, minimum=2)
    _need(len(x) == len(y), 'same complete rank support')
    out = _spearman(x, y, budget)
    budget.tick()
    return out


def repetition_mean(observations, *, budget):
    """Return stimulus x feature arithmetic means of stimulus x repeat x feature."""
    _budget(budget)
    n = _sequence(observations, 'plain stimulus/repetition/feature cube')
    _need(n >= 2, 'at least two stimuli')
    repeats = _sequence(observations[0], 'plain repetition block')
    _need(repeats >= 1, 'positive repetition support')
    width = _sequence(observations[0][0], 'plain response vector')
    _need(width >= 2, 'at least two features or voxels')
    budget.charge(n*repeats*width, n*repeats*width + 3*n*width + 2*repeats*width)
    result = []
    for block in observations:
        budget.tick()
        _need(_sequence(block, 'repetition block') == repeats, 'same complete repetitions')
        rows = _matrix(block, budget, min_cols=2)
        _need(len(rows[0]) == width, 'same complete voxel or feature support')
        result.append(tuple(_mean(tuple(row[j] for row in rows), budget) for j in range(width)))
    budget.tick()
    return tuple(result)


def correlation_rdm(observations, *, budget):
    """Condensed 1-Pearson across row features; constant rows retain None pairs."""
    _budget(budget)
    n = _sequence(observations, 'plain stimulus/feature matrix')
    _need(n >= 2, 'at least two stimuli')
    width = _sequence(observations[0], 'plain feature row')
    _need(width >= 2, 'at least two features')
    pairs = n*(n-1)//2
    budget.charge(n*width + pairs*width*2, 3*n*width + 2*pairs)
    rows = _matrix(observations, budget, min_rows=2, min_cols=2)
    units = tuple(_units(row, budget) for row in rows)
    output = []
    for i in range(n):
        budget.tick()
        for j in range(i+1, n):
            budget.tick()
            if units[i] is None or units[j] is None:
                output.append(None)
            else:
                rho = max(-1.0, min(1.0, math.fsum(x*y for x, y in zip(units[i], units[j]))))
                output.append(1.0-rho)
    budget.tick()
    return tuple(output)


def brain_rdm(observations, *, budget):
    """Actual repeated-response mean followed by the actual RDM producer."""
    _budget(budget)
    means = repetition_mean(observations, budget=budget)
    out = correlation_rdm(means, budget=budget)
    budget.tick()
    return out


def observed_rsa(model_condensed, subject_condensed_rows, *, budget):
    _budget(budget)
    model = _condensed(model_condensed, budget)
    subjects = _matrix(subject_condensed_rows, budget, nullable=True)
    for row in subjects:
        _condensed(row, budget)
    _need(len(subjects[0]) == len(model), 'all subjects share complete model pair support')
    budget.charge(len(subjects)*len(model), (len(subjects)+5)*len(model))
    scores = []
    for row in subjects:
        budget.tick()
        scores.append(_spearman(model, row, budget))
    out = {'subject_rho': tuple(scores), 'mean': _mean(scores, budget),
           'coverage': {'defined': sum(v is not None for v in scores), 'required': len(scores)}}
    budget.tick()
    return out


def noise_ceilings(subject_condensed_rows, *, budget):
    """Unsquared rank-based upper/lower ceilings, retaining every subject."""
    _budget(budget)
    subjects = _matrix(subject_condensed_rows, budget, nullable=True, min_rows=2)
    for row in subjects:
        _condensed(row, budget)
    n, k = len(subjects), len(subjects[0])
    budget.charge(n*n*k, (n+7)*k + 4*n)
    grand = tuple(_mean(tuple(row[j] for row in subjects), budget) for j in range(k))
    upper, lower = [], []
    for holdout, row in enumerate(subjects):
        budget.tick()
        other = tuple(_mean(tuple(subjects[s][j] for s in range(n) if s != holdout), budget) for j in range(k))
        upper.append(_spearman(row, grand, budget))
        lower.append(_spearman(row, other, budget))
    out = {'upper_subjects': tuple(upper), 'lower_subjects': tuple(lower),
           'upper': _mean(upper, budget), 'lower': _mean(lower, budget),
           'coverage': {'upper_defined': sum(v is not None for v in upper),
                        'lower_defined': sum(v is not None for v in lower), 'required_subjects': n},
           'interpretation': 'unsquared Spearman reference, not explained variance'}
    budget.tick()
    return out


def permute_rdm(condensed, permutation, *, mode, budget):
    """Source row-only upper triangle or explicitly separate congruent relabeling.

    Row-only selection can reach the zero diagonal. It is intentionally not a
    symmetric relabeling and does not get silently repaired into one.
    """
    _budget(budget)
    n = _sequence(permutation, 'plain stimulus permutation')
    _need(n >= 2, 'nontrivial stimulus support')
    k = n*(n-1)//2
    budget.charge(4*k + n*max(1, n.bit_length()), 3*k + 3*n)
    _need(all(type(p) is int for p in permutation), 'exact integer permutation, no bool')
    _need(sorted(permutation) == list(range(n)), 'complete unique permutation')
    _need(mode in ('source_rows_only', 'congruent_stimulus_labels'), 'explicit permutation convention')
    vector = _condensed(condensed, budget)
    _need(len(vector) == k, 'complete condensed stimulus pair support')
    result = []
    for i in range(n):
        budget.tick()
        for j in range(i+1, n):
            budget.tick()
            a, b = permutation[i], j if mode == 'source_rows_only' else permutation[j]
            if a == b:
                result.append(0.0)
            else:
                lo, hi = min(a, b), max(a, b)
                index = n*lo - lo*(lo+1)//2 + hi-lo-1
                result.append(vector[index])
    budget.tick()
    return tuple(result)


def source_layer_summary(layer_subject_rho, *, budget):
    """First largest signed subject mean; any undefined eligible mean stays open."""
    _budget(budget)
    rows = _matrix(layer_subject_rho, budget, nullable=True)
    _need(all(v is None or -1 <= v <= 1 for row in rows for v in row), 'signed correlation range')
    means = tuple(_mean(row, budget) for row in rows)
    complete = all(v is not None for v in means)
    chosen = max(range(len(means)), key=means.__getitem__) if complete else None
    out = {'layer_subject_rho': rows, 'layer_subject_mean': means,
           'selected_layer_index': chosen,
           'observed_max_mean': means[chosen] if chosen is not None else None,
           'selected_subject_values': rows[chosen] if chosen is not None else None,
           'coverage': {'defined_values': sum(v is not None for row in rows for v in row),
                        'required_values': len(rows)*len(rows[0]), 'all_eligible_layers_defined': complete},
           'selection': 'descriptive same-cohort first maximum; not a held-out estimate'}
    budget.tick()
    return out


def _median(values, budget):
    budget.charge(4*len(values)*max(1, len(values).bit_length()), 3*len(values))
    if any(v is None for v in values):
        return None
    ordered = sorted(values)
    budget.tick()
    n = len(ordered)
    return ordered[n//2] if n % 2 else ordered[n//2-1]/2 + ordered[n//2]/2


def _tail(null, observed, budget):
    budget.charge(3*len(null), len(null))
    defined = observed is not None and all(v is not None for v in null)
    count = sum(abs(v) >= abs(observed) for v in null) if defined else None
    return {'tail_count': count, 'permutations': len(null),
            'p': count/len(null) if defined else None,
            'defined_null': sum(v is not None for v in null), 'observed_defined': observed is not None}


def source_group_inference(groups, selected_model_observed, selected_model_null_rows, *, budget):
    """Actual signed medians and source conditional-null group comparisons.

    groups: ((label, (model_id, ...)), ...). The two dictionaries must have exactly
    the union of these disjoint memberships. Null rows have identical, positive
    lengths and the caller binds their joint schedule. Ordered pair corrections
    are deliberately not capped at one, following the retained source.
    """
    _budget(budget)
    _need(type(selected_model_observed) is dict and type(selected_model_null_rows) is dict,
          'plain observed/null dictionaries')
    ng = _sequence(groups, 'plain ordered group specification')
    _need(ng >= 1, 'nonempty groups')
    budget.charge(ng, 4*ng)
    labels, members, seen = [], [], set()
    for group in groups:
        budget.tick()
        _need(_sequence(group, 'label/member pair') == 2, 'two-field group')
        label, names = group
        _need(type(label) is str and 0 < len(label) <= 256 and label not in labels, 'unique bounded group label')
        count = _sequence(names, 'plain group member list')
        _need(count > 0, 'nonempty scientific group')
        budget.charge(count, len(seen)+count+ng)
        for name in names:
            budget.tick()
            _need(type(name) is str and 0 < len(name) <= 256 and name not in seen,
                  'unique bounded model membership across groups')
            seen.add(name)
        labels.append(label)
        members.append(tuple(names))
    _need(len(selected_model_observed) == len(seen) and len(selected_model_null_rows) == len(seen),
          'exact group dictionary cardinality before key allocation')
    _need(all(type(k) is str and 0 < len(k) <= 256 for k in selected_model_observed) and
          all(type(k) is str and 0 < len(k) <= 256 for k in selected_model_null_rows),
          'bounded plain dictionary keys before set construction')
    _need(set(selected_model_observed) == seen and set(selected_model_null_rows) == seen,
          'exact group model support, no missing or unused values')
    nmodels = len(seen)
    first = members[0][0]
    nperm = _sequence(selected_model_null_rows[first], 'plain first null row')
    _need(nperm > 0, 'positive complete permutation support')
    budget.charge(nmodels*nperm + ng*ng*nperm, 2*nmodels*nperm + 3*ng*nperm + 2*ng*(ng-1)*nperm + 8*ng*ng)
    observed, nulls = {}, {}
    for name in (name for group in members for name in group):
        budget.tick()
        value = _number(selected_model_observed[name], True)
        _need(value is None or -1 <= value <= 1, 'observed signed correlation range')
        null = _vector(selected_model_null_rows[name], budget, nullable=True)
        _need(len(null) == nperm and all(v is None or -1 <= v <= 1 for v in null),
              'same null length and signed correlation range')
        observed[name], nulls[name] = value, null
    output_groups = []
    for label, names in zip(labels, members):
        budget.tick()
        value = _median(tuple(observed[name] for name in names), budget)
        null = tuple(_median(tuple(nulls[name][p] for name in names), budget) for p in range(nperm))
        output_groups.append({'label': label, 'models': names, 'observed_median': value,
                              'median_null': null, 'against_zero': _tail(null, value, budget)})
    factor = 1 if 'Kinetics-710' in labels else ng*(ng-1)//2
    pairs = []
    for i, left in enumerate(output_groups):
        budget.tick()
        for j, right in enumerate(output_groups):
            budget.tick()
            if i == j:
                continue
            observed_difference = (left['observed_median']-right['observed_median']
                                   if left['observed_median'] is not None and right['observed_median'] is not None else None)
            differences = tuple(a-b if a is not None and b is not None else None
                                for a, b in zip(left['median_null'], right['median_null']))
            tail = _tail(differences, observed_difference, budget)
            pairs.append({'left': left['label'], 'right': right['label'],
                          'observed_difference': observed_difference, 'null_difference': differences,
                          'tail': tail, 'source_pair_factor': factor,
                          'source_adjusted_p': tail['p']*factor if tail['p'] is not None else None})
    out = {'groups': tuple(output_groups), 'ordered_pairs': tuple(pairs),
           'source_pair_factor': factor, 'permutations': nperm,
           'null_convention': 'caller-bound schedule; observed-selected-layer conditional null',
           'undefined_policy': 'propagate full support; never omit a member or permutation',
           'interpretation': 'source convention only; not calibrated confirmatory inference'}
    budget.tick()
    return out


def iterative_source_clip_mean(clips, *, budget):
    _budget(budget)
    rows = _matrix(clips, budget)
    budget.charge(3*len(rows)*len(rows[0]), (len(rows)+3)*len(rows[0]))
    result = rows[0]
    for row in rows[1:]:
        budget.tick()
        # Half first avoids overflowing the source's literal (a+b)/2 operation.
        result = tuple(a/2+b/2 for a, b in zip(result, row))
    budget.tick()
    return result


def uniform_clip_mean(clips, *, budget):
    """Prospective separate convention; never labeled exact legacy aggregation."""
    _budget(budget)
    rows = _matrix(clips, budget)
    budget.charge(len(rows)*len(rows[0]), (len(rows)+3)*len(rows[0]))
    result = tuple(_mean(tuple(row[j] for row in rows), budget) for j in range(len(rows[0])))
    budget.tick()
    return result


def null_distribution(model_condensed, subject_condensed_rows, permutations, *, mode, budget):
    """Compose actual permutation and subject-RSA production for the full schedule.

    Identity, historical schedule provenance and sharing across models/layers are
    admitted by the owner. All supplied permutations are processed in their given
    order; none is omitted after undefined output. No generator/backend callback.
    """
    _budget(budget)
    model = _condensed(model_condensed, budget)
    subjects = _matrix(subject_condensed_rows, budget, nullable=True)
    _need(len(subjects[0]) == len(model), 'same complete subject/model pair support')
    for row in subjects:
        _condensed(row, budget)
    count = _sequence(permutations, 'plain complete permutation schedule')
    _need(count > 0, 'positive permutation schedule')
    n = (1 + math.isqrt(1+8*len(model)))//2
    budget.charge(count*n + count*len(subjects)*len(model),
                  count*n + 3*count*len(subjects) + (len(subjects)+6)*len(model))
    subject_rows, means = [], []
    for permutation in permutations:
        budget.tick()
        _need(_sequence(permutation, 'plain permutation row') == n,
              'all permutations have the same complete stimulus domain')
        permuted = permute_rdm(model, permutation, mode=mode, budget=budget)
        observation = observed_rsa(permuted, subjects, budget=budget)
        subject_rows.append(observation['subject_rho'])
        means.append(observation['mean'])
    out = {'subject_null_rows': tuple(subject_rows), 'mean_null': tuple(means),
           'permutations': count, 'subjects': len(subjects), 'mode': mode,
           'coverage': {'defined_subject_values': sum(v is not None for row in subject_rows for v in row),
                        'required_subject_values': count*len(subjects),
                        'defined_permutation_means': sum(v is not None for v in means),
                        'required_permutation_means': count}}
    budget.tick()
    return out
