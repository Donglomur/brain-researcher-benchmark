"""Pure array/JSON seams for arbitrary matched programs; no empirical readers."""
import math
from io031 import need

VIEWS = ('baseline', 'neural')
KEYS = ('train_x', 'train_y', 'train_mouse', 'train_rowid', 'query_x', 'query_rowid')
COMMON_FEATURES = ('baseline_volume', 'basal_indicator', 'local_missing', 'coincident_missing')
NEURAL_FEATURES = COMMON_FEATURES + ('local_coactivity_norm', 'dendrite_coincident_norm')


def original_packet(np, packet, manifest, fold, mice):
    need(set(packet) == set(KEYS) and type(fold) is int and 0 <= fold < 20,
         'Exact original outer-fold arrays and index')
    need(manifest['schema'] == 'neural031_outer_public_v1'
         and manifest['candidate_id'] == 'NEURAL-031' and manifest['fold'] == fold
         and manifest['held_mouse'] == mice[fold]
         and manifest['training_mouse_indices'] == [i for i in range(20) if i != fold]
         and manifest['features'] == ['baseline_volume', 'basal_indicator', 'local_coactivity_norm', 'dendrite_coincident_norm']
         and manifest['training_target'] == 'next_day_ratio_with_NaN_unavailable'
         and manifest['query_target_or_followup_metadata'] is False, 'Exact previously frozen public semantics')
    for split in ('train', 'query'):
        x, row = packet[split + '_x'], packet[split + '_rowid']
        need(x.dtype == np.dtype('float64') and x.ndim == 2 and x.shape[1] == 4
             and row.dtype == np.dtype('int64') and row.shape == (len(x),)
             and 0 < len(x) <= 1143 and len(np.unique(row)) == len(row)
             and bool(np.all((row >= 0) & (row < 1143))) and bool(np.all(np.diff(row) > 0))
             and bool(np.all(np.isfinite(x[:, :2]))) and bool(np.all(x[:, 0] > 0))
             and bool(np.all((x[:, 1] == 0) | (x[:, 1] == 1))), 'All original baseline requests retained')
        need(manifest[split + '_rows'] == len(x), 'Public row count exact')
    y, group = packet['train_y'], packet['train_mouse']
    need(y.dtype == np.dtype('float64') and y.shape == group.shape == (len(packet['train_x']),)
         and group.dtype == np.dtype('int64') and set(group.tolist()) == set(range(20)) - {fold}
         and not set(packet['train_rowid'].tolist()) & set(packet['query_rowid'].tolist())
         and bool(np.all(np.isnan(y) | (np.isfinite(y) & (y >= 0))))
         and all(bool(np.any((group == i) & np.isfinite(y))) for i in range(20) if i != fold),
         'Nineteen whole training mice, explicit unavailable labels, no query labels')


def physical_view(np, packet, view):
    need(view in VIEWS, 'Declared information view')
    result = {key: value.copy() for key, value in packet.items() if key not in ('train_x', 'query_x')}
    for split in ('train', 'query'):
        x = packet[split + '_x']
        present = np.isfinite(x[:, 2:])
        common = np.column_stack((x[:, :2], (~present).astype(np.float64)))
        # Missingness alone is shared context. Nonfinite activity values become
        # NaN only in the neural archive; no activity-valued buffer enters baseline.
        result[split + '_x'] = common if view == 'baseline' else np.column_stack(
            (common, np.where(present, x[:, 2:], np.nan)))
    return result


def validate_views(np, original, baseline, neural):
    need(set(baseline) == set(neural) == set(KEYS), 'No extra archive arrays')
    for key in KEYS:
        if key.endswith('_x'):
            need(baseline[key].shape == (len(original[key]), 4)
                 and neural[key].shape == (len(original[key]), 6)
                 and np.array_equal(baseline[key], neural[key][:, :4]), 'Identical physical common context')
            activity = neural[key][:, 4:]
            need(np.array_equal(np.isfinite(activity), np.isfinite(original[key][:, 2:]))
                 and np.array_equal(activity[np.isfinite(activity)], original[key][:, 2:][np.isfinite(activity)])
                 and np.array_equal(baseline[key][:, 2:], (~np.isfinite(activity)).astype(np.float64)),
                 'Complete original neural values and common availability only')
        else:
            need(np.array_equal(baseline[key], original[key], equal_nan=True)
                 and np.array_equal(neural[key], original[key], equal_nan=True), 'Identical labels/groups/support')


def check_all_folds(np, packets):
    """Trusted projector only: all-fold consistency never enters a candidate."""
    need(len(packets) == 20, 'All twenty original outer folds')
    rows = [p['query_rowid'].tolist() for p in packets]
    union = [row for values in rows for row in values]
    need(len(union) == len(set(union)) <= 1143, 'Disjoint complete held-mouse requests')
    by_row = {row: (fold, j) for fold, values in enumerate(rows) for j, row in enumerate(values)}
    labels = {}
    for fold, packet in enumerate(packets):
        expected = sorted(set(union) - set(rows[fold]))
        need(packet['train_rowid'].tolist() == expected, 'Every other mouse request, no truncated support')
        for j, row in enumerate(expected):
            owner, index = by_row[row]
            need(packet['train_mouse'][j] == owner
                 and np.array_equal(packet['train_x'][j], packets[owner]['query_x'][index], equal_nan=True),
                 'Whole-mouse identity and original predictor agreement across folds')
            value = float(packet['train_y'][j])
            if row in labels:
                need(value == labels[row] or (math.isnan(value) and math.isnan(labels[row])),
                     'Same original training label wherever legally available')
            else:
                labels[row] = value
    return rows
