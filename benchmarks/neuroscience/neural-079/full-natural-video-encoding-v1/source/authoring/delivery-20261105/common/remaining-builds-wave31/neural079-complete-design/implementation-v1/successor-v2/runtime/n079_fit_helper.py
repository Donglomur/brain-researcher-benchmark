"""Packaged fit/transform/predict over the same permitted public information.

Invoked by the admitted worker or repeatedly by F/I code in its sandbox. It
has no protected label, reference-result, provider or host-controller interface.
"""
import hashlib
import importlib.util
import json
import math
import os
from n079_plan import DIMS, D, Q, TRAIN, PERSONS
from n079_common import require, fields, integer, pin
from n079_arrays import preflight


def load_numeric(path, expected, maximum):
    require(expected['bytes'] <= maximum, 'complete pinned helper arithmetic source capacity')
    with open(path, 'rb') as stream:
        raw = stream.read(maximum + 1)
    require(pin(raw) == expected, 'exact independent frozen arithmetic source')
    import types
    module = types.ModuleType('n079_private_fit_helper_numeric')
    import sys
    require(module.__name__ not in sys.modules, 'fresh helper numeric context')
    sys.modules[module.__name__] = module
    # Dataclass definition needs its own module registered during execution.
    # Remove only this temporary registration afterwards. Each call rereads,
    # verifies and executes the same source into a fresh namespace, so no
    # mutable learned/global state is silently reused between helper calls.
    # Returned functions/classes retain this namespace through normal Python
    # references; no numerical result is cached or supplied by the loader.
    primary = None
    try:
        exec(compile(raw, path, 'exec'), module.__dict__)
    except BaseException as error:
        primary = error; raise
    finally:
        try:
            require(sys.modules.get(module.__name__) is module, 'owned temporary helper module identity')
            del sys.modules[module.__name__]
        except BaseException as error:
            if primary is None:
                raise
            primary.add_note('Secondary helper module cleanup: ' + type(error).__name__)
    return module


class PublicMatrices:
    def __init__(self, np, mapping_limit):
        self.np = np; self.limit = integer(mapping_limit, 1); self.maps = []; self.total = 0

    def open(self, path, rows, columns):
        require(path.startswith(('/training/', '/query/')) and '..' not in path.split('/'), 'permitted fixed public roots')
        size = integer(rows, 1) * integer(columns, 1) * 4
        self.total += size; require(self.total <= self.limit, 'complete logical mapped-byte ceiling before mapping')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW); first = None
        try:
            import stat, mmap
            st = os.fstat(fd); require(stat.S_ISREG(st.st_mode) and st.st_size == size, 'actual complete fixed f32 public matrix')
            mapping = mmap.mmap(fd, size, access=mmap.ACCESS_READ); self.maps.append(mapping)
            return self.np.ndarray((rows, columns), dtype='<f4', buffer=mapping)
        except BaseException as error:
            first = error; raise
        finally:
            try:
                os.close(fd)
            except BaseException as error:
                if first is None:
                    raise
                first.add_note('Secondary public helper input close: ' + type(error).__name__)

    def close(self, primary=None):
        first = primary
        while self.maps:
            mapping = self.maps.pop()
            try:
                mapping.close()
            except BaseException as error:
                if first is None:
                    first = error
                else:
                    first.add_note('Secondary public helper mapping close: ' + type(error).__name__)
        if primary is None and first is not None:
            raise first


def compute(request, numeric, limits, *, column_block, mapping_limit):
    """One explicitly declared person/target-block fit, not a study score."""
    import numpy as np
    fields(request, ('schema', 'phase', 'bundle_alias', 'query_video_id', 'persons', 'shape', 'public_metadata', 'helper', 'report_evidence_path', 'helper_configuration'))
    require(request['report_evidence_path'] in (None, '/report/evidence.json'), 'fixed report metadata path, never protected feedback')
    selected = request['helper']
    fields(selected, ('person', 'fit_video_ids', 'predict_video_ids', 'coordinate_start', 'coordinate_stop', 'family', 'setting_id'))
    require(selected['person'] in PERSONS and request['persons'] == list(PERSONS), 'same full permitted population with explicit target person')
    metadata = request['public_metadata']; training = metadata['training']
    require(training['trial_roster'] is not None and training['trial_roster']['neural_support'] == 'present',
            'absent condition cannot invoke a neural-label fit')
    fit = selected['fit_video_ids']; other = selected['predict_video_ids']
    require(type(fit) is list and len(fit) >= 2 and fit == sorted(set(fit)) and set(fit) <= set(TRAIN), 'explicit unique fitting training videos')
    allowed = set(TRAIN) | ({request['query_video_id']} if request['query_video_id'] is not None else set())
    require(type(other) is list and other and len(set(other)) == len(other) and set(other) <= allowed, 'current authorized prediction identities only')
    start = integer(selected['coordinate_start']); stop = integer(selected['coordinate_stop'], 1)
    require(start < stop <= Q, 'explicit complete requested target-coordinate block')
    family = selected['family']; settings = [s for s in numeric.settings(family) if s['id'] == selected['setting_id']]
    require(len(settings) == 1, 'one exact declared helper method setting')
    width = integer(column_block, 1); target_width = stop - start
    n, m = len(fit), len(other); cells = n * n + m * n
    require(23 * cells + 3 * D + 6 * (n + m) * width + 8 * (n + m) * target_width <= limits['max_live_float_slots'],
            'full17 cached Grams and active feature/target blocks before allocation')
    matrices = PublicMatrices(np, mapping_limit); error = None; row_maps = {}; opened = []
    try:
        raw_train = matrices.open('/training/features.f32', 1000, D)
        current = None if request['query_video_id'] is None else matrices.open('/query/features.f32', 1, D)
        grams = []; cross = []; feature_states = []; offset = 0
        for layer, dimension in enumerate(DIMS):
            total = np.zeros((n, n), dtype='float64'); compensation = np.zeros_like(total)
            query = np.zeros((m, n), dtype='float64'); qcomp = np.zeros_like(query)
            for col in range(offset, offset + dimension, width):
                end = min(offset + dimension, col + width); b = end - col
                preflight(limits, max(n, m), b, 6 * (n + m) * b + 4 * cells)
                values = raw_train[[v - 1 for v in fit], col:end].astype('float64')
                prediction_rows = np.empty((m, b), dtype='float64')
                for i, video in enumerate(other):
                    prediction_rows[i] = raw_train[video - 1, col:end] if video in TRAIN else current[0, col:end]
                transformed = numeric.standardize(values, prediction_rows, limits=limits)
                pair = numeric.gram_pair(transformed['train'], transformed['other'], limits=limits)
                from n079_preparation import compensated_add
                compensated_add(total, compensation, pair['train'], np)
                compensated_add(query, qcomp, pair['cross'], np)
                feature_states.append({'layer': layer, 'start': col, 'stop': end, 'moments': transformed['moments']})
            grams.append(total + compensation); cross.append(query + qcomp); offset += dimension
        require(offset == D and len(grams) == 17, 'all original feature columns in packaged helper')
        # Fit-only session transforms over the supplied raw training trials;
        # precomputed final1000 means cannot substitute for an inner transform.
        rows = [r for r in training['trial_arrays'] if r['person'] == selected['person']]
        roster = {r['session']: r for r in training['trial_roster']['sessions'] if r['person'] == selected['person']}
        require(len(rows) == len(roster) == 8, 'all eight authorized sessions for selected person')
        sums = np.zeros((n, target_width), dtype='float64'); correction = np.zeros_like(sums); counts = [0] * n
        positions = {v: i for i, v in enumerate(fit)}; target_states = []
        for row in rows:
            trials = roster[row['session']]['trials']; count = len(trials)
            require(row['array']['shape'] == [count, Q], 'public raw trial/axis alignment')
            preflight(limits, count, target_width, 8 * count * target_width + 4 * n * target_width)
            raw = matrices.open('/training/trial-' + row['session'] + '.f32', count, Q)
            block = raw[:, start:stop].astype('float64')
            take = [i for i, trial in enumerate(trials) if trial['video'] in positions]
            require(take, 'fitting support in every original session')
            moments = numeric.moments(block[take], limits=limits)
            require(np.all(moments['scale'] > 0), 'positive fitting session target SD')
            normalized = (block - moments['mean']) / moments['scale']
            require(np.isfinite(normalized).all(), 'finite exact helper target transform')
            for i in take:
                j = positions[trials[i]['video']]
                compensated_add(sums[j:j + 1], correction[j:j + 1], normalized[i:i + 1], np); counts[j] += 1
            target_states.append({'session': row['session'], 'fit_trial_indices': take, 'moments': moments})
        require(all(counts), 'every requested fitting video has full retained-trial support')
        target = (sums + correction) / np.array(counts)[:, None]
        canonical_values = target.astype('float32')
        require(np.isfinite(canonical_values).all(), 'finite once-rounded helper target')
        zeroed = (target != 0) & (canonical_values == 0)
        quantization = {'nonzero_to_zero': int(np.count_nonzero(zeroed)),
            'subnormal_output': int(np.count_nonzero((canonical_values != 0) & (np.abs(canonical_values) < np.finfo('float32').tiny))),
            'maximum_abs_value_rounded_to_zero': float(np.max(np.abs(target[zeroed]))) if np.any(zeroed) else 0.0}
        values = canonical_values.astype('float64')
        result = numeric.reference_predict(family, grams, cross, values, settings[0], limits=limits)
        return {'prediction': result['prediction'], 'learned': result['state'], 'diagnostics': result['diagnostics'],
                'feature_states': feature_states, 'target_states': target_states, 'quantization': quantization,
                'fit_video_ids': fit, 'predict_video_ids': other, 'person': selected['person'], 'coordinate_start': start,
                'coordinate_stop': stop, 'feature_columns': D, 'no_protected_metric': True,
                'logical_mapping_bytes': matrices.total}
    except BaseException as exc:
        error = exc; raise
    finally:
        # Arrays returned above are computed owned arrays, not views into the
        # public mappings. Input-only mappings close before publication.
        raw_train = current = raw = None
        matrices.close(error)
