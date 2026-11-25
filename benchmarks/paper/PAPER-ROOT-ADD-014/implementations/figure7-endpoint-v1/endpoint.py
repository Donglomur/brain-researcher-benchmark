"""Figure 7 source selection and prediction scoring; no data access on import.

This operator library does not establish the original 366/31 identities, source
permutation thresholds, training isolation, native optimizer parity or a win.
See SOURCE.md. Historical alpha-programme source is deliberately unchanged.
"""
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path


PARTICIPANTS = ('p01', 'p02', 'p05', 'p06', 'p07', 'p08', 'p09', 'p10', 'p11')
SIGNALS = ('corrected_alpha', 'raw_alpha', 'broadband')
ROW_FIELDS = {'participant', 'electrode_id', 'wangarea',
              'corrected_broadband_xval_percent', 'raw_broadband_xval_percent',
              'corrected_broadband_ecc_pixels', 'raw_broadband_ecc_pixels'}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def _key(row):
    return (row['participant'], row['electrode_id'])


@dataclass(frozen=True)
class Selection:
    """Operator-owned source selection; hashes bind values, not authenticity."""
    population_sha256: str
    selected: tuple
    selection_sha256: str


def compile_selection(rows, thresholds):
    """Compile the paper's 31-row V1–V3 panel from its 366-row population.

    rows must come from the original QC and wangprobchs/normalised-area pipeline,
    with the two broadband fits joined by participant AND electrode identity.
    thresholds are the two source round(prctile(cod_bb(:),95)) outputs, not
    invented constants or thresholds inferred from candidate performance.
    This pure function neither loads nor authenticates those source assets.

    Source expressions negate <= and >=. For finite inputs they are exactly
    xval > threshold and eccentricity < 50 pixels. Nonfinite inputs cause a
    refusal: silently copying MATLAB's NaN-passing comparison would select an
    unreconciled cohort. No alpha values or gain signs enter selection.
    """
    _need(type(rows) is list and len(rows) == 366, 'complete original 366-row population required')
    _need(type(thresholds) is dict and set(thresholds) == {'corrected', 'raw'},
          'both source broadband permutation thresholds required')
    _need(all(_finite(v) and v == round(v) for v in thresholds.values()),
          'finite source-rounded percent thresholds required')
    keys, selected = set(), []
    for row in rows:
        _need(type(row) is dict and set(row) == ROW_FIELDS, 'exact source selection row fields')
        _need(row['participant'] in PARTICIPANTS
              and type(row['electrode_id']) is str and bool(row['electrode_id'])
              and type(row['wangarea']) is str and bool(row['wangarea']),
              'native participant, electrode and source-normalised area required')
        key = _key(row)
        _need(key not in keys, 'duplicate participant/electrode source identity')
        keys.add(key)
        fields = ROW_FIELDS - {'participant', 'electrode_id', 'wangarea'}
        _need(all(_finite(row[f]) for f in fields),
              'nonfinite source selection operand requires native reconciliation')
        _need(row['corrected_broadband_ecc_pixels'] >= 0
              and row['raw_broadband_ecc_pixels'] >= 0, 'source eccentricity is nonnegative pixels')
        ok = (row['wangarea'] in ('V1', 'V2', 'V3')
              and row['corrected_broadband_xval_percent'] > thresholds['corrected']
              and row['raw_broadband_xval_percent'] > thresholds['raw']
              and row['corrected_broadband_ecc_pixels'] < 50
              and row['raw_broadband_ecc_pixels'] < 50)
        if ok:
            selected.append(key)
    _need({p for p, _ in keys} == set(PARTICIPANTS), 'all nine original participants required')
    _need(len(selected) == 31, 'original Figure 7 31-electrode panel not recovered')
    population_sha256 = _sha({'rows': rows, 'thresholds': thresholds})
    digest = _sha({'population_sha256': population_sha256, 'selected': selected})
    return Selection(population_sha256, tuple(selected), digest)


def _validate_selection(selection, expected_selection_sha256):
    _need(type(selection) is Selection and type(selection.selected) is tuple
          and len(selection.selected) == 31, 'operator-owned 31-row selection required')
    _need(all(type(k) is tuple and len(k) == 2 and k[0] in PARTICIPANTS
              and type(k[1]) is str and bool(k[1]) for k in selection.selected),
          'valid selection identities')
    _need(len(set(selection.selected)) == 31, 'distinct source selection identities required')
    _need(type(selection.population_sha256) is str and len(selection.population_sha256) == 64
          and all(c in '0123456789abcdef' for c in selection.population_sha256),
          'source population binding required')
    digest = _sha({'population_sha256': selection.population_sha256, 'selected': selection.selected})
    _need(selection.selection_sha256 == digest == expected_selection_sha256,
          'operator-frozen selection binding mismatch')


def _series(value):
    _need(type(value) is list and len(value) == 75 and all(_finite(x) for x in value),
          'all 75 finite source-ordered samples required; no omissions or clipping')
    # The locked metric evaluates represented binary64 samples. Normalize here
    # so finite integer inputs cannot become an unsigned/object NumPy array only
    # after protected reference access. This preserves the metric conversion.
    return [float(x) for x in value]


def _median(values):
    ordered = sorted(Fraction(x) for x in values)
    n = len(ordered)
    return float(ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2)


def _delta(a, b):
    try:
        result = float(Fraction(a) - Fraction(b))
    except OverflowError as exc:
        raise ValueError('unrepresentable paired metric difference') from exc
    _need(math.isfinite(result), 'unrepresentable paired metric difference')
    return result


def _load_metrics():
    # Reuse the reviewed metric and verify its existing vendor lock. No new
    # formula, alternative normalisation or native numerical parity is implied.
    path = Path(__file__).resolve().parents[1] / 'alpha-programme/spatial/sources.py'
    spec = importlib.util.spec_from_file_location('_figure7_spatial_sources', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load().metrics


def evaluate_predictions(selection, candidate, *, expected_selection_sha256, load_reference):
    """Score complete out-of-fold predictions after admitting all candidate rows.

    candidate: list of {participant, electrode_id, predictions}; predictions
    maps all three SIGNALS to 75 finite samples. Each prediction is already
    cross-fitted: indices 0..37 were predicted from the last37 training samples,
    and 38..74 from the first38. A producer-isolation protocol must prove this.

    load_reference(participant, electrode_id) is operator-only and returns
    {observations, author_predictions}, each mapping SIGNALS to 75 samples.
    Its corrected and raw alpha predictions must be the Figure7 signed-gain GS
    source branches; broadband is the original positive-gain GS companion.
    Caller custody must bind the author replay and fixed observations before
    candidate exposure. The candidate cannot submit scores or reference rows.

    All31 rows and all3 signals must produce defined source metrics. Nonfinite
    observations or zero centered energy refuse the complete result rather
    than changing the original selected cohort. No pass threshold or confidence
    interval is inferred from the published rounded43/10 percent anchors.
    """
    _validate_selection(selection, expected_selection_sha256)
    _need(type(candidate) is list and len(candidate) == 31, 'all31 candidate electrode rows required')
    expected, admitted = set(selection.selected), {}
    for row in candidate:
        _need(type(row) is dict and set(row) == {'participant', 'electrode_id', 'predictions'},
              'exact prediction row fields; candidate scores are forbidden')
        _need(type(row['participant']) is str and type(row['electrode_id']) is str,
              'string candidate identity required')
        key = _key(row)
        _need(key in expected and key not in admitted, 'complete candidate identity bijection required')
        pred = row['predictions']
        _need(type(pred) is dict and set(pred) == set(SIGNALS), 'all alpha and broadband controls required')
        admitted[key] = {s: list(_series(pred[s])) for s in SIGNALS}
    _need(set(admitted) == expected, 'complete candidate identity bijection required')
    metrics = _load_metrics()
    values = {metric: {s: {'candidate': [], 'author': []} for s in SIGNALS}
              for metric in ('source_cv', 'literal_eq6')}
    for key in selection.selected:
        reference = load_reference(*key)
        _need(type(reference) is dict and set(reference) == {'observations', 'author_predictions'},
              'exact operator reference fields')
        for kind in ('observations', 'author_predictions'):
            _need(type(reference[kind]) is dict and set(reference[kind]) == set(SIGNALS),
                  'complete operator signal panel')
        reference = {kind: {signal: _series(reference[kind][signal]) for signal in SIGNALS}
                     for kind in ('observations', 'author_predictions')}
        for signal in SIGNALS:
            y = reference['observations'][signal]
            for method, prediction in (('candidate', admitted[key][signal]),
                                       ('author', reference['author_predictions'][signal])):
                results = {
                    'source_cv': metrics.source_fold_projected_xval_percent(y, prediction, metrics.FOLD_LABELS),
                    'literal_eq6': metrics.literal_paper_eq6_percent(y, prediction),
                }
                for metric, result in results.items():
                    _need(result['status'] == 'defined' and _finite(result['value_percent']),
                          'undefined metric on fixed cohort; complete result unavailable')
                    values[metric][signal][method].append(result['value_percent'])
    summaries = {}
    for metric, signals in values.items():
        summaries[metric] = {}
        for signal, paired in signals.items():
            c, a = paired['candidate'], paired['author']
            cm, am = _median(c), _median(a)
            summaries[metric][signal] = {
                'candidate_median_percent': cm, 'author_median_percent': am,
                'difference_of_medians_pp': _delta(cm, am),
                'median_paired_difference_pp': _median([_delta(x, y) for x, y in zip(c, a)]),
                'per_participant': {
                    p: {'electrodes': len(indices),
                        'candidate_median_percent': _median([c[i] for i in indices]),
                        'author_median_percent': _median([a[i] for i in indices])}
                    for p in PARTICIPANTS
                    if (indices := [i for i, key in enumerate(selection.selected) if key[0] == p])
                },
            }
    contrasts = {
        metric: {method + '_corrected_minus_raw_medians_pp': _delta(
            summaries[metric]['corrected_alpha'][method + '_median_percent'],
            summaries[metric]['raw_alpha'][method + '_median_percent'])
            for method in ('candidate', 'author')}
        for metric in summaries
    }
    # Preserve the complete source-ordered distribution for operator audit and
    # figure reconstruction. Summary medians cannot recover these paired values.
    per_electrode = []
    for i, (participant, electrode_id) in enumerate(selection.selected):
        per_electrode.append({
            'participant': participant, 'electrode_id': electrode_id,
            'metrics': {
                metric: {
                    signal: {
                        'candidate_percent': paired['candidate'][i],
                        'author_percent': paired['author'][i],
                        'paired_difference_pp': _delta(paired['candidate'][i], paired['author'][i]),
                    }
                    for signal, paired in signals.items()
                }
                for metric, signals in values.items()
            },
            'baseline_correction_contrasts': {
                metric: {
                    method + '_corrected_minus_raw_pp': _delta(
                        signals['corrected_alpha'][method][i], signals['raw_alpha'][method][i])
                    for method in ('candidate', 'author')
                }
                for metric, signals in values.items()
            },
        })
    return {'schema': 'visual_alpha_figure7_prediction_report_v1',
            'selection_sha256': selection.selection_sha256,
            'electrodes': 31, 'selected_participants': len({p for p, _ in selection.selected}),
            'primary': 'source_cv.corrected_alpha.difference_of_medians_pp',
            'metrics': summaries, 'baseline_correction_contrasts': contrasts,
            'per_electrode': per_electrode,
            'uncertainty': 'not_estimated; electrodes remain nested within participants',
            'qualification': 'software endpoint component; source identities and native replay require independent qualification'}
