"""Frozen four-demo reference for the distinct adaptive-gain raster condition.

Intervals describe visible raster-column hulls, not recovered EEG samples.
No raw-array, query-label, tuning, random-seed or alternate-method interface.
"""
from __future__ import annotations
import copy
import math
import statistics

METHOD = 'erp-adaptive-image-interval-reference-v1'
LABELS = (0, 1, 0, 1)
GAINS = (20, 50, 100, 200, 500, 1000)
CONFIG = {
    'method': METHOD, 'observation_condition': 'erp-full32-first-unclipped-gain-observation-v1',
    'frame': 'selected_first_both_unclipped_else_cap; all_attempts_committed',
    'feature': 'exact_blue_column_hull_native_units_gain_over_30_plus_half_pixel',
    'support': 'intersection_of_all_four_demos_and_query_at_identical_columns',
    'baseline': 'common_pre_marker_columns_180_to_459',
    'bins': 'fifteen_56_column_post_marker_bins_per_channel_460_to_1299',
    'centroid': 'equal_two_demo_interval_endpoint_means_per_class',
    'scale': 'median_four_demo_visible_baseline_midpoint_RMS_floor_max_demo_gain_over_30',
    'distance': 'shared_coverage_weighted_mean_squared_interval_gap_over_demo_scale',
    'probability': 'sigmoid_half_distance_difference_clip60_shrink_by_shared_support',
    'no_support': 'one_half; retain_case', 'probability_calibration_established': False,
    'interval_is_raw_sample_confidence_bound': False,
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def extract(scanlines, gain):
    """Decode ONLY scanlines from the audited selected image.

    At x, native hull = [(middle-max_blue_y-.5)*g/30,
                        (middle-min_blue_y+.5)*g/30].
    White/missing columns stay None. Segment rasterization is not inverted.
    """
    need(type(gain) is int and gain in GAINS, 'Declared adaptive gain required')
    need(type(scanlines) is bytes and len(scanlines) == 820 * 4201 and
         all(scanlines[y * 4201] == 0 for y in range(820)), 'Fixed RGB scanlines required')
    columns = []
    for top in (205, 465):
        lows, highs = [181] * 1120, [-1] * 1120
        for y in range(181):
            row = scanlines[(top + y) * 4201 + 1 + 180 * 3:(top + y) * 4201 + 1 + 1300 * 3]
            at = row.find(b'\x14\x4b\xaa')
            while at >= 0:
                if at % 3 == 0:
                    x = at // 3
                    lows[x], highs[x] = min(lows[x], y), max(highs[x], y)
                at = row.find(b'\x14\x4b\xaa', at + 1)
        columns.append([[(90 - hi - .5) * gain / 30, (90 - lo + .5) * gain / 30]
                        if hi >= 0 else None for lo, hi in zip(lows, highs)])
    return {'gain': gain, 'columns': columns}


def validate_features(value):
    need(type(value) is dict and set(value) == {'gain', 'columns'} and
         type(value['gain']) is int and value['gain'] in GAINS, 'Exact raster feature fields')
    need(type(value['columns']) is list and len(value['columns']) == 2, 'Two channels')
    bound = 3 * value['gain'] + value['gain'] / 60
    for channel in value['columns']:
        need(type(channel) is list and len(channel) == 1120, 'All1120 raster columns')
        for interval in channel:
            need(interval is None or (type(interval) is list and len(interval) == 2 and
                 all(finite(v) for v in interval) and -bound <= interval[0] <= interval[1] <= bound),
                 'Finite ordered visible hull or explicit missing column')


def mean_interval(intervals):
    return [statistics.fmean(v[edge] for v in intervals) for edge in (0, 1)]


def subtract(a, b):
    return [a[0] - b[1], a[1] - b[0]]


def fit(demos, provenance):
    """Exactly four demos; labels are the protocol's ordered (0,1,0,1)."""
    need(type(demos) is list and len(demos) == 4 and type(provenance) is list and
         len(provenance) == 4, 'Exactly four ordered demonstration inputs')
    for demo in demos:
        validate_features(demo)
    scales = []
    for channel in range(2):
        rms = []
        for demo in demos:
            centers = [sum(v) / 2 for v in demo['columns'][channel][:280] if v is not None]
            if centers:
                center = statistics.fmean(centers)
                rms.append(math.sqrt(statistics.fmean((v - center) ** 2 for v in centers)))
        scales.append(max(max(d['gain'] for d in demos) / 30,
                          statistics.median(rms) if rms else 0))
    return {'config': copy.deepcopy(CONFIG), 'labels': list(LABELS),
            'demos': copy.deepcopy(demos), 'provenance': copy.deepcopy(provenance), 'scales': scales}


def validate_model(model):
    need(type(model) is dict and set(model) == {'config', 'labels', 'demos', 'provenance', 'scales'} and
         model['config'] == CONFIG and model['labels'] == list(LABELS) and
         all(type(v) is int for v in model['labels']), 'Frozen method and demo labels')
    rebuilt = fit(model['demos'], model['provenance'])
    need(model == rebuilt, 'Model must equal fixed four-demo construction')


def predict(query, model):
    """Fixed interval distances on equal support; no fitting or model mutation."""
    validate_features(query)
    # Model admission occurs once at the pinned MODEL.json boundary, not per query.
    weights, widths, distances = [], [], [0.0, 0.0]
    baseline_coverage = []
    records = model['demos'] + [query]
    for channel in range(2):
        traces = [r['columns'][channel] for r in records]
        shared = [all(t[x] is not None for t in traces) for x in range(1120)]
        pre = [x for x in range(280) if shared[x]]
        baseline_coverage.append(len(pre) / 280)
        baselines = [mean_interval([t[x] for x in pre]) for t in traces] if pre else None
        for start in range(280, 1120, 56):
            xs = [x for x in range(start, start + 56) if shared[x]]
            weight = len(xs) / 56 * len(pre) / 280 if pre else 0.0
            weights.append(weight)
            if not weight:
                widths.append(None)
                continue
            features = [subtract(mean_interval([t[x] for x in xs]), b)
                        for t, b in zip(traces, baselines)]
            q = features[-1]
            widths.append(q[1] - q[0])
            for label in (0, 1):
                centroid = mean_interval([features[i] for i in range(4) if LABELS[i] == label])
                gap = max(0.0, centroid[0] - q[1], q[0] - centroid[1])
                distances[label] += weight * (gap / model['scales'][channel]) ** 2
    total = sum(weights)
    fraction = total / 30
    distances = [d / total for d in distances] if total else [0.0, 0.0]
    margin = max(-60.0, min(60.0, .5 * (distances[0] - distances[1])))
    probability = .5 + fraction * (1 / (1 + math.exp(-margin)) - .5)
    need(finite(probability) and 0 <= probability <= 1, 'Finite probability required')
    return probability, {'shared_support_fraction': fraction, 'shared_weights': weights,
        'baseline_coverage': baseline_coverage, 'no_shared_support': total == 0,
        'interval_distances': distances, 'query_feature_widths_native': widths,
        'native_units_per_vertical_pixel': query['gain'] / 30,
        'in_range_sample_placement_rounding_bound_native': query['gain'] / 60,
        'raw_sample_recovery': False, 'calibrated_probability': False}
