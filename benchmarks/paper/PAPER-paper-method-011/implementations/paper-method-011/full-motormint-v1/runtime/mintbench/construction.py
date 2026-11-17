"""Source-defined library construction ingredients; no inferred historical recipe."""
import math
from .validation import need, matrix, finite, integer


def gaussian_filter(rows, sigma_samples, radius_samples):
    """Explicit finite support with edge renormalization: named prospective rule.

    Historical boundary/kernel truncation must match recovered native source;
    caller cannot infer this implementation equals the author gauss_filt.
    """
    matrix(rows); finite(sigma_samples); integer(radius_samples, 1, 10000)
    need(sigma_samples > 0, 'positive Gaussian width')
    weights = [math.exp(-0.5*(offset/sigma_samples)**2) for offset in range(-radius_samples, radius_samples+1)]
    out = []
    for index in range(len(rows)):
        offsets = [j for j in range(-radius_samples, radius_samples+1) if 0 <= index+j < len(rows)]
        total = sum(weights[j+radius_samples] for j in offsets)
        out.append([sum(weights[j+radius_samples]*rows[index+j][column] for j in offsets)/total for column in range(len(rows[0]))])
    return out


def type_i_average(trials):
    need(type(trials) is list and trials, 'nonempty original condition trials')
    first = matrix(trials[0])
    for trial in trials:
        matrix(trial, len(first), len(first[0]))
    return [[sum(trial[t][j] for trial in trials)/len(trials) for j in range(len(first[0]))] for t in range(len(first))]


def linear_resample(rows, coordinates):
    """Coordinates must come from an authenticated training warp/clock mapping."""
    matrix(rows)
    need(type(coordinates) is list and coordinates, 'explicit mapping coordinates')
    result = []
    previous = -1
    for coordinate in coordinates:
        finite(coordinate)
        need(0 <= coordinate <= len(rows)-1 and coordinate >= previous, 'bounded monotone source mapping')
        lo, hi = int(coordinate), min(int(coordinate)+1, len(rows)-1)
        weight = coordinate - lo
        result.append([(1-weight)*a + weight*b for a, b in zip(rows[lo], rows[hi])])
        previous = coordinate
    return result


def apply_neuron_loss(rows, retained_columns, regime, *, training):
    matrix(rows)
    need(regime in ('known', 'undetected'), 'source loss regimes')
    need(type(retained_columns) is list and retained_columns and
         len(set(retained_columns)) == len(retained_columns), 'source-bound retained neuron IDs')
    for column in retained_columns:
        integer(column, 0, len(rows[0])-1)
    if regime == 'known':
        return [[row[j] for j in retained_columns] for row in rows]
    if training:
        return [list(row) for row in rows]
    retained = set(retained_columns)
    return [[value if column in retained else 0 for column, value in enumerate(row)] for row in rows]


def pseudo_condition_average(training_trials, memberships, expected_trial_ids):
    """Executes supplied authenticated grouping; does not invent the missing rule."""
    need(type(training_trials) is dict and set(training_trials) == set(expected_trial_ids), 'complete original training trials')
    need(type(memberships) is dict and memberships, 'explicit original pseudo-condition groups')
    flattened = [trial for group in memberships.values() for trial in group]
    need(len(flattened) == len(set(flattened)) and set(flattened) == set(expected_trial_ids), 'training-only exhaustive non-overlapping groups')
    return {group: type_i_average([training_trials[trial] for trial in members]) for group, members in memberships.items()}
