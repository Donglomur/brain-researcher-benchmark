"""Complete physical condition/query exports with no shared held-label backing."""
import importlib
from n079_common import require, integer, identity, close_all
from n079_arrays import MatrixReader, MatrixWriter, RecordingReader
from n079_preparation import public_trial_roster, opaque
from n079_plan import TRAIN, QUERY, PERSONS, Q, D


class ViewExporter:
    def __init__(self, context, repository, output_fd, limits, coordinate_block):
        context.require_effect('array_write', 'assembler')
        self.context, self.repository, self.output_fd, self.limits = context, repository, output_fd, limits
        self.width = integer(coordinate_block, 1)
        self.np = importlib.import_module('numpy')
        self.raw_training_cache = {}; self.mean_cache = {}

    def matrix_rows(self, source, row_indices, public_rows, name, work='assembler'):
        reader = None; writer = None; error = None
        try:
            reader = MatrixReader(self.context, self.repository, source, self.limits, work)
            require(len(row_indices) == len(public_rows), 'exact public/private row correspondence')
            lineage = {'rows_pin': identity(public_rows, self.context.encoding_limits),
                       'columns_pin': source['columns_pin'],
                       'lineage_pin': identity({'source': source, 'private_rows': row_indices,
                                               'public_rows': public_rows}, self.context.encoding_limits)}
            writer = MatrixWriter(self.context, self.output_fd, name + '.f32', len(row_indices), reader.shape[1],
                                  '<f4', self.limits, work, lineage)
            for start in range(0, reader.shape[1], self.width):
                stop = min(reader.shape[1], start + self.width)
                writer.append_columns(start, reader.block(row_indices, start, stop))
            return writer.finish()
        except BaseException as exc:
            error = exc; raise
        finally:
            close_all(([('public row reader', lambda: reader.close(error))] if reader is not None else []) +
                      ([('public row writer', lambda: writer.close(error))] if writer is not None else []), error)

    def training_bundle(self, seed, bundle_alias, signal, sessions, final_means, private_mapping):
        require(signal in ('measured', 'mismatch', 'absent'), 'private condition')
        require(len(sessions) == 48 and {(s['person'], s['session']) for s in sessions} ==
                {(p, s) for p in PERSONS for s in range(1, 9)}, 'full48-session export support')
        if signal == 'absent':
            result = {'schema': 'n079_public_training_v1', 'bundle_alias': bundle_alias,
                      'persons': list(PERSONS), 'trial_arrays': [], 'mean_arrays': [], 'trial_roster': None}
            self.context.journal.append('private_view_join', {'bundle_alias': bundle_alias, 'signal': signal,
                                                            'public': result, 'private_aliases': []})
            return result
        require(set(final_means) == set(PERSONS), 'all six people training means')
        public_roster, private = public_trial_roster(seed, bundle_alias, signal, sessions, private_mapping)
        # Keep the complete identity mapping protected before numeric staging;
        # public headers never receive these true rows, hashes or condition IDs.
        self.context.journal.append('private_alias_bijection', {'bundle_alias': bundle_alias,
            'signal': signal, 'private_aliases': private, 'public_roster': public_roster})
        trial_arrays = []; mean_arrays = []
        for session, public in zip(sessions, public_roster['sessions']):
            reader = None; writer = None; error = None
            try:
                cache_key = (session['person'], session['session'], session['array']['object']['sha256'])
                if cache_key in self.raw_training_cache:
                    cached = self.raw_training_cache[cache_key]
                    rebound = {**cached, 'rows_pin': identity(public['trials'], self.context.encoding_limits),
                               'lineage_pin': identity({'same_raw_backing': cached, 'new_public_aliases': public['trials']}, self.context.encoding_limits)}
                    trial_arrays.append({'person': session['person'], 'session': public['session'],
                                         'array': rebound})
                    continue
                reader = RecordingReader(self.context, self.repository, session['array'], self.limits, 'assembler')
                require(session['trial_video_ids'] == session['array']['trial_video_ids'], 'same actual complete trial identity vector')
                positions = [i for i, v in enumerate(session['trial_video_ids']) if v in TRAIN]
                require(len(positions) == len(public['trials']), 'full aliased retained-trial support')
                lineage = {'rows_pin': identity(public['trials'], self.context.encoding_limits),
                           'columns_pin': self.context.coordinate_pin,
                           'lineage_pin': identity({'source': session['array'], 'positions': positions,
                                                   'opaque_session': public['session']}, self.context.encoding_limits)}
                writer = MatrixWriter(self.context, self.output_fd, public['session'] + '.f32', len(positions), Q,
                                      '<f4', self.limits, 'assembler', lineage)
                for start in range(0, Q, self.width):
                    stop = min(Q, start + self.width)
                    raw = reader.block(start, stop); writer.append_columns(start, raw[positions])
                array = writer.finish(); self.repository.register(array['object'])
                self.raw_training_cache[cache_key] = array
                trial_arrays.append({'person': session['person'], 'session': public['session'], 'array': array})
            except BaseException as exc:
                error = exc; raise
            finally:
                close_all(([('training trial reader', lambda: reader.close(error))] if reader is not None else []) +
                          ([('training trial writer', lambda: writer.close(error))] if writer is not None else []), error)
        for person in PERSONS:
            source = final_means[person]
            require(source['shape'] == [1000, Q], 'separate physical fitting-mean backing only')
            rows = [private_mapping[v] - 1 if signal == 'mismatch' else v - 1 for v in TRAIN]
            name = opaque(seed, 'NEURAL-079/mean-alias/v1', [bundle_alias, person])
            key = (person, signal, source['object']['sha256'])
            if key not in self.mean_cache:
                self.mean_cache[key] = self.matrix_rows(source, rows, list(TRAIN), name)
                self.repository.register(self.mean_cache[key]['object'])
            mean_arrays.append({'person': person, 'array': self.mean_cache[key]})
        result = {'schema': 'n079_public_training_v1', 'bundle_alias': bundle_alias, 'persons': list(PERSONS),
                  'trial_arrays': trial_arrays, 'mean_arrays': mean_arrays, 'trial_roster': public_roster}
        self.context.journal.append('private_view_join', {'bundle_alias': bundle_alias, 'signal': signal, 'public': result})
        return result

    def features(self, source, seed):
        require(source['shape'] == [1102, D], 'all17/full1102 feature source')
        training = self.matrix_rows(source, [v - 1 for v in TRAIN], list(TRAIN),
                                    opaque(seed, 'NEURAL-079/stimulus-training/v1', ['full17']))
        queries = {}
        for video in QUERY:
            queries[video] = self.matrix_rows(source, [video - 1], [video],
                opaque(seed, 'NEURAL-079/current-query-feature/v1', [video]))
        require(len(queries) == 102, 'all102 individually backed current-query stimuli')
        return {'training': training, 'queries': queries}


def minimized_mounts(training, current_query, sealed, common, exposure_admission):
    """Exact generic backend view. Private descriptor paths stay operator-only."""
    from n079_common import checked_pin, descriptor
    checked_pin(exposure_admission)
    materials = {}
    for root, source in (('/training/', training), ('/query/', current_query), ('/sealed/', sealed), ('/common/', common)):
        require(type(source) is dict, 'explicit source-owned minimal view entries')
        for name, value in source.items():
            require(type(name) is str and '/' not in name and name not in ('', '.', '..'), 'fixed exposed leaf name')
            descriptor(value); materials[root + name] = value
    return {'schema': 'ach_minimized_process_view_v1', 'materials': materials,
            'exposure_admission': exposure_admission,
            'forbidden_feedback': ['native', 'reference_results', 'outer_labels', 'other_contexts']}
