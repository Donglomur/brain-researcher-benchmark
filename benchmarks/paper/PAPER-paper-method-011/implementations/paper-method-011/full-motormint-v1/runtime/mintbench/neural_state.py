"""Concrete operator-side NLB transformations; historical evaluator still gated."""
import math
from .validation import need, matrix, vector, integer, finite


def condition_average(rate_rows, condition_ids, time_ids, expected_keys):
    """Average only operator-authenticated condition/time joins, no test fit."""
    matrix(rate_rows)
    need(len(condition_ids) == len(rate_rows) == len(time_ids), 'all rate rows have condition/time identity')
    expected = [tuple(key) for key in expected_keys]
    need(len(set(expected)) == len(expected), 'unique expected PSTH support')
    sums, counts = {}, {}
    for rates, condition, tick in zip(rate_rows, condition_ids, time_ids):
        key = (condition, tick)
        need(key in expected, 'no undocumented PSTH support')
        if key not in sums:
            sums[key], counts[key] = [0.0] * len(rates), 0
        for j, value in enumerate(rates):
            sums[key][j] += value
        counts[key] += 1
    need(set(sums) == set(expected), 'no missing condition/time PSTH rows')
    return [[value / counts[key] for value in sums[key]] for key in expected]


def _solve_spd(a, b):
    """Cholesky with explicit failure; no singular inverse or silent ridge change."""
    n = len(a)
    l = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            value = a[i][j] - sum(l[i][k] * l[j][k] for k in range(j))
            if i == j:
                need(value > 0 and math.isfinite(value), 'positive-definite original ridge system')
                l[i][j] = math.sqrt(value)
            else:
                l[i][j] = value / l[j][j]
    y = []
    for i in range(n):
        y.append((b[i] - sum(l[i][k] * y[k] for k in range(i))) / l[i][i])
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (y[i] - sum(l[k][i] * x[k] for k in range(i + 1, n))) / l[i][i]
    return x


def ridge_readout(training_rates, training_behavior, query_rates, *, ridge, train_pairs):
    """Explicit source-clock rate/lagged-behavior index pairs; never test tuning.

    Centered unpenalized-intercept ridge is a named engineering implementation.
    The original NLB evaluator's grid/folds/lag/normalization must be bound before
    it can be claimed historically equivalent.
    """
    matrix(training_rates); matrix(training_behavior); matrix(query_rates, columns=len(training_rates[0]))
    finite(ridge, nonnegative=True)
    need(type(train_pairs) is list and len(train_pairs) >= 2 and len({tuple(p) for p in train_pairs}) == len(train_pairs), 'unique original training lag pairs')
    xs, ys = [], []
    for pair in train_pairs:
        need(type(pair) is list and len(pair) == 2, 'rate/behavior pair')
        a = integer(pair[0], 0, len(training_rates)-1)
        b = integer(pair[1], 0, len(training_behavior)-1)
        xs.append(training_rates[a]); ys.append(training_behavior[b])
    n, d, m = len(xs), len(xs[0]), len(ys[0])
    mx = [sum(row[j] for row in xs)/n for j in range(d)]
    my = [sum(row[j] for row in ys)/n for j in range(m)]
    gram = [[sum((row[i]-mx[i])*(row[j]-mx[j]) for row in xs) + (ridge if i == j else 0) for j in range(d)] for i in range(d)]
    weights = []
    for out in range(m):
        rhs = [sum((x[i]-mx[i])*(y[out]-my[out]) for x, y in zip(xs, ys)) for i in range(d)]
        weights.append(_solve_spd(gram, rhs))
    return [[my[out] + sum((x[i]-mx[i])*weights[out][i] for i in range(d)) for out in range(m)] for x in query_rates]


def rate_metric_payload(packet, predicted, kind, bound_payload, parameters):
    """Join complete rate artifacts to source-frozen PSTH or velocity recipes.

    All conditions, lags, labels and column identities are protected operator
    inputs. No candidate-supplied score, grouping, subset or ridge is accepted.
    This realizes the recipe; it does not certify historical NLB equivalence.
    """
    from .validation import exact, digest
    exact(bound_payload, ('field', 'payload', 'sha256'), 'protected NLB readout binding')
    data = bound_payload['payload']
    need(digest(data) == bound_payload['sha256'], 'precommitted NLB readout data')
    query = [row for stream in packet.streams('query') for row in predicted[stream['id']]]
    train = [row for stream in packet.streams('train') for row in predicted['training:'+stream['id']]]
    need(data['query_sample_ids'] == [row['sample_id'] for row in query], 'exact complete query-rate identity')
    columns = data['rate_columns']
    need(type(columns) is list and columns and len(set(columns)) == len(columns), 'explicit unique rate columns')
    for column in columns:
        integer(column, 0, packet.index['output_schema']['width']-1)
    query_rates = [[max(.1,row['value'][c]) for c in columns] for row in query]
    if kind == 'psth':
        need(bound_payload['field'] == 'nlb_psth', 'PSTH-specific operator recipe')
        exact(data, ('query_sample_ids', 'rate_columns', 'condition_ids', 'time_ids', 'expected_keys', 'truth'), 'PSTH readout')
        exact(parameters, (), 'PSTH has no candidate-selectable parameter')
        average = condition_average(query_rates, data['condition_ids'], data['time_ids'], data['expected_keys'])
        matrix(data['truth'], rows=len(average), columns=len(columns))
        return {'truth': data['truth'], 'prediction': average}
    need(kind == 'behavior' and bound_payload['field'] == 'nlb_velocity', 'velocity-specific operator recipe')
    exact(data, ('query_sample_ids', 'training_sample_ids', 'rate_columns', 'training_behavior',
                 'train_pairs', 'query_rows', 'truth'), 'rate-to-velocity readout')
    exact(parameters, ('ridge', 'metric'), 'preselected readout and behavior statistic')
    need(data['training_sample_ids'] == [row['sample_id'] for row in train], 'exact complete training-rate identity')
    training_rates = [[max(.1,row['value'][c]) for c in columns] for row in train]
    readout = ridge_readout(training_rates, data['training_behavior'], query_rates,
                           ridge=parameters['ridge'], train_pairs=data['train_pairs'])
    rows = data['query_rows']
    need(type(rows) is list and rows and len(set(rows)) == len(rows), 'unique original lagged velocity support')
    for row in rows:
        integer(row, 0, len(readout)-1)
    prediction = [readout[i] for i in rows]
    matrix(data['truth'], rows=len(prediction), columns=len(prediction[0]))
    exact(parameters['metric'], ('groups', 'circular_columns', 'phase_period'), 'frozen velocity metric')
    return dict(parameters['metric'], truth=data['truth'], prediction=prediction)
