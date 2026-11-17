"""Protected complete target preparation and opaque correspondence views."""
import hashlib
import hmac
import importlib
import math
from n079_common import require, integer, checked_pin, identity
from n079_arrays import MatrixWriter, RecordingReader, preflight
from n079_plan import TRAIN, QUERY, PERSONS, Q


def private_derangement(seed, quartiles):
    require(type(seed) is bytes and len(seed) == 32, 'independently admitted private256-bit campaign seed')
    require(len(quartiles) == 4 and sorted(v for q in quartiles for v in q) == list(TRAIN), 'complete acquisition quartiles')
    out = {}
    for quartile in quartiles:
        require(len(quartile) == 250 and quartile == sorted(quartile), 'ordered full quartile')
        for fold in range(5):
            values = [v for i, v in enumerate(quartile) if i % 5 == fold]
            require(len(values) == 50, 'full within-fold stratum')
            ordered = sorted(values, key=lambda v: (hmac.new(seed, ('NEURAL-079/mismatch-v2/' + str(v)).encode(),
                                                            hashlib.sha256).digest(), v))
            out.update({v: ordered[(i + 1) % 50] for i, v in enumerate(ordered)})
    require(sorted(out) == list(TRAIN) and sorted(out.values()) == list(TRAIN) and
            all(k != v for k, v in out.items()), 'complete fixed-point-free correspondence map')
    return out


def opaque(seed, domain, parts):
    require(type(seed) is bytes and len(seed) == 32 and type(domain) is str, 'private alias source')
    require(all(type(p) in (str, int) for p in parts), 'typed alias components')
    raw = domain.encode() + b'\0' + b'\0'.join(str(p).encode() for p in parts)
    return hmac.new(seed, raw, hashlib.sha256).hexdigest()


def public_trial_roster(seed, bundle_alias, signal, sessions, mapping):
    require(signal in ('measured', 'mismatch', 'absent'), 'private condition')
    if signal == 'absent':
        return {'schema': 'n079_training_trial_view_v1', 'sessions': [], 'neural_support': 'absent'}, []
    require(sorted(mapping) == list(TRAIN) and sorted(mapping.values()) == list(TRAIN), 'complete admitted mapping')
    inverse = {v: k for k, v in mapping.items()} if signal == 'mismatch' else {v: v for v in TRAIN}
    public, private = [], []
    for session in sessions:
        sid = opaque(seed, 'NEURAL-079/session-alias/v1', [bundle_alias, session['person'], session['session']])
        trials = []
        for index, video in enumerate(session['trial_video_ids']):
            if video not in inverse:
                continue
            tid = opaque(seed, 'NEURAL-079/trial-alias/v1', [bundle_alias, session['person'], session['session'], index])
            trials.append({'trial': tid, 'video': inverse[video]})
            private.append({'alias': tid, 'session_alias': sid, 'person': session['person'],
                            'session': session['session'], 'row': index, 'true_video': video})
        public.append({'person': session['person'], 'session': sid, 'trials': trials})
    require(len({r['alias'] for r in private}) == len(private), 'bijective trial aliases')
    require(len({r['session'] for r in public}) == len(public), 'bijective session aliases')
    return {'schema': 'n079_training_trial_view_v1', 'sessions': public, 'neural_support': 'present'}, private


def compensated_add(total, correction, value, np):
    current = total + value
    correction += np.where(np.abs(total) >= np.abs(value), (total - current) + value, (value - current) + total)
    total[:] = current


class TargetAssembler:
    def __init__(self, context, repository, numerical, output_fd, limits, block_columns, encoding_limits):
        context.require_effect('prepare_targets', 'assembler')
        self.context, self.repository, self.numeric = context, repository, numerical
        self.output_fd, self.limits = output_fd, limits
        self.width = integer(block_columns, 1); self.encoding_limits = encoding_limits
        require(self.width <= Q, 'selected full-grid coordinate block width')
        self.np = importlib.import_module('numpy')

    def person_partition(self, person, selected_sessions, partition, source_pin):
        require(person in PERSONS and len(selected_sessions) == 8, 'all8 sessions for one admitted person')
        checked_pin(source_pin)
        require([r['session'] for r in selected_sessions] == list(range(1, 9)), 'ordered complete sessions')
        train = partition['train']; rows = sorted(train + partition['other'])
        require(len(set(rows)) == len(rows), 'disjoint complete fit/evaluation identities')
        index = {v: i for i, v in enumerate(rows)}; readers = []; writers = {}; error = None
        moments_manifest = []
        try:
            for session in selected_sessions:
                readers.append(RecordingReader(self.context, self.repository, session['array'], self.limits, 'assembler'))
            lineage = {'rows_pin': identity(rows, self.encoding_limits),
                       'columns_pin': self.context.coordinate_pin,
                       'lineage_pin': identity({'source': source_pin, 'person': person, 'partition': partition,
                                               'normalization': 'fit-only-session-trial-population-v1'}, self.encoding_limits)}
            # Separate backing objects enforce target custody. In particular,
            # final1000 fitting labels never share a file/FD with102 held labels.
            for scope, videos in (('train', train), ('other', partition['other'])):
                scoped_lineage = {**lineage, 'rows_pin': identity(videos, self.encoding_limits)}
                writers[scope] = MatrixWriter(self.context, self.output_fd,
                    '%s-%s-%s-target.f32' % (person, partition['id'], scope),
                    len(videos), Q, '<f4', self.limits, 'assembler', scoped_lineage)
            for start in range(0, Q, self.width):
                stop = min(Q, start + self.width); width = stop - start
                preflight(self.limits, len(rows), width, 4 * len(rows) * width)
                sums = self.np.zeros((len(rows), width), dtype='float64'); compensation = self.np.zeros_like(sums)
                counts = self.np.zeros(len(rows), dtype='int64')
                for session, reader in zip(selected_sessions, readers):
                    raw = reader.block(start, stop)
                    ids = reader.selected['trial_video_ids']; fit = [i for i, video in enumerate(ids) if video in train]
                    require(fit, 'nonempty fitting trials in each original session')
                    preflight(self.limits, len(ids), width, 4 * len(ids) * width)
                    state = self.numeric.moments(raw[fit], limits=self.limits)
                    require(self.np.isfinite(state['scale']).all() and (state['scale'] > 0).all(), 'positive fitting session SD')
                    normalized = (raw - state['mean']) / state['scale']
                    require(self.np.isfinite(normalized).all(), 'finite fit-only transformed trials')
                    # Actual moments are retained as protected binary artifacts,
                    # not exported to absent or private-correspondence views.
                    stats = self.np.stack((state['mean'], state['variance'], state['scale']))
                    state_artifact = self.context.write_numeric_state('assembler', '%s-%s-session%d-col%d' %
                        (person, partition['id'], session['session'], start), stats,
                        {'fit_rows': fit, 'source': source_pin, 'start': start, 'stop': stop})
                    moments_manifest.append({'session': session['session'], 'start': start, 'stop': stop,
                                             'fit_rows': fit, 'source': source_pin, 'state_artifact': state_artifact})
                    for i, video in enumerate(ids):
                        if video in index:
                            j = index[video]
                            compensated_add(sums[j:j + 1], compensation[j:j + 1], normalized[i:i + 1], self.np)
                            counts[j] += 1
                require((counts > 0).all(), 'every required person/video has retained support')
                means = (sums + compensation) / counts[:, None]
                writers['train'].append_columns(start, means[[index[v] for v in train]])
                writers['other'].append_columns(start, means[[index[v] for v in partition['other']]])
            result = {scope: writer.finish() for scope, writer in writers.items()}; writers = {}
            return {'person': person, 'partition': partition['id'], 'targets': result,
                    'moment_blocks': moments_manifest, 'full_rows': rows, 'coordinate_count': Q}
        except BaseException as exc:
            error = exc; raise
        finally:
            operations = [('session reader', lambda reader=reader: reader.close(error)) for reader in readers]
            operations += [('unfinished target writer', lambda writer=writer: writer.close(error)) for writer in writers.values()]
            from n079_common import close_all
            close_all(operations, error)


class PreparationProducer:
    """All48 sessions/all fitting partitions plus physically separated views."""
    def __init__(self, context, repository, numerical, output_fd, limits, coordinate_block):
        from n079_products import ProducedRepository
        self.context, self.output_fd, self.limits = context, output_fd, limits
        self.repository = ProducedRepository(context, repository, output_fd, 'assembler')
        self.assembler = TargetAssembler(context, self.repository, numerical, output_fd, limits, coordinate_block, context.encoding_limits)
        from n079_views import ViewExporter
        self.exporter = ViewExporter(context, self.repository, output_fd, limits, coordinate_block)

    def run(self, selected):
        from n079_common import fields, close_all
        from n079_plan import compile_study, bundles
        from n079_products import write_index
        import os
        fields(selected, ('study', 'sessions', 'seed_object', 'raw_features', 'policy_source_pins'))
        compiled = compile_study(selected['study'])
        self.context.coordinate_pin = identity({'channels': selected['study']['channels'], 'times': selected['study']['times'],
                                                'order': 'channel-time'}, self.context.encoding_limits)
        require(identity(selected['study'], self.context.encoding_limits) == self.context.effect_admission['study_pin'],
                'actual preparation study matches independent source admission')
        require(len(selected['sessions']) == 48 and sorted((s['person'], s['session']) for s in selected['sessions']) ==
                sorted((p, s) for p in PERSONS for s in range(1, 9)), 'all authentic session schema declarations')
        original_recordings = {r['id']: r for r in selected['study']['recordings']}
        for session in selected['sessions']:
            original = original_recordings['%s/session-%02d' % (session['person'], session['session'])]
            require(session['array']['object'] == original['object'] and
                    session['array']['schema_admission'] == original['schema_pin'] and
                    session['array']['trial_roster_pin'] == original['trial_roster_pin'],
                    'each actual complete recording/schema/trial roster is the admitted full-study source')
            require(session['trial_video_ids'] == session['array']['trial_video_ids'], 'exact recording trial vector join')
            require(session['array']['channel_pin'] == identity(selected['study']['channels'], self.context.encoding_limits) and
                    session['array']['time_pin'] == identity(selected['study']['times'], self.context.encoding_limits),
                    'every actual session has the same authenticated complete named coordinate axes')
        require(selected['seed_object']['bytes'] == 32, 'actual private seed exact extent')
        fd = self.repository.open(selected['seed_object']); error = None
        try:
            self.context.ledger.charge('assembler', {'data_read_bytes': 33}, 'actual private seed read, contents never logged')
            seed = os.read(fd, 33); require(len(seed) == 32, 'complete actual private seed')
        except BaseException as exc:
            error = exc; raise
        finally:
            close_all([('private seed descriptor', lambda: os.close(fd))], error)
        mapping = private_derangement(seed, selected['study']['quartiles'])
        # Protected mapping is required for audit; public objects contain no
        # seed, map/inverse, original event IDs or reconstructible condition.
        self.context.journal.append('private_correspondence', {'seed_object': selected['seed_object'], 'mapping': mapping})
        targets = {}; query_targets = {}; final_means = {}; moments = []
        for partition in compiled['partitions']:
            heads = []
            for person in PERSONS:
                sessions = sorted((s for s in selected['sessions'] if s['person'] == person), key=lambda s: s['session'])
                result = self.assembler.person_partition(person, sessions, partition, self.context.source_pin)
                moments.append(result)
                for array in result['targets'].values():
                    self.repository.register(array['object'])
                normalized_pin = identity(result, self.context.encoding_limits)
                for signal in ('measured', 'mismatch'):
                    arrays = {}
                    for scope in ('train', 'other'):
                        if scope == 'other' and partition['id'] == 'final':
                            arrays[scope] = None; continue
                        source = result['targets'][scope]; ids = partition[scope]
                        if signal == 'mismatch':
                            positions = {v: i for i, v in enumerate(ids)}
                            require(all(mapping[v] in positions for v in ids), 'private map preserves whole fit/validation stratum')
                            rows = [positions[mapping[v]] for v in ids]
                            array = self.exporter.matrix_rows(source, rows, ids,
                                '%s-%s-%s-%s-reference' % (person, partition['id'], signal, scope))
                            self.repository.register(array['object']); arrays[scope] = array
                        else:
                            arrays[scope] = source
                    heads.append({'person': person, 'signal': signal, 'partition': partition['id'],
                                  **arrays, 'normalization_pin': normalized_pin})
                if partition['id'] == 'final':
                    final_means[person] = result['targets']['train']; query_targets[person] = result['targets']['other']
            targets[partition['id']] = heads
        public_features = self.exporter.features(selected['raw_features'], seed)
        public_bundles = {}; public_exports = {}
        for bundle in bundles():
            alias = opaque(seed, 'NEURAL-079/bundle-alias/v1', [bundle['id']])
            training = self.exporter.training_bundle(seed, alias, bundle['signal'], selected['sessions'], final_means, mapping)
            files = {'features.f32': public_features['training']['object']}
            for row in training['trial_arrays']:
                files['trial-' + row['session'] + '.f32'] = row['array']['object']
            for row in training['mean_arrays']:
                files['mean-' + row['person'] + '.f32'] = row['array']['object']
            metadata = {'training': training, 'feature_outputs': selected['study']['feature_outputs'],
                        'train_video_ids': list(TRAIN), 'persons': list(PERSONS), 'shape': [127, 1800],
                        'channels': selected['study']['channels'], 'times': selected['study']['times']}
            # Public numeric descriptors are input metadata, not outcome
            # claims. Relative host object names are not mounted paths.
            public_bundles[bundle['id']] = {'alias': alias, 'training': files,
                'queries': {str(v): {'features.f32': public_features['queries'][v]['object']} for v in QUERY},
                'public_metadata': metadata, 'policy_source_pin': selected['policy_source_pins'][bundle['policy_id']]}
            public_exports[bundle['id']] = {'alias': alias, 'training': files,
                'queries': public_bundles[bundle['id']]['queries'], 'metadata_pin': identity(metadata, self.context.encoding_limits)}
        result = {'schema': 'n079_preparation_index_v1', 'study_pin': self.context.effect_admission['study_pin'],
                  'source_pin': self.context.source_pin, 'compiled': compiled, 'reference_targets': targets,
                  'query_targets': query_targets, 'fit_targets': final_means, 'moment_evidence': moments,
                  'public_bundles': public_bundles, 'public_exports': public_exports,
                  'private_mapping_evidence': identity({'mapping': mapping, 'seed_object': selected['seed_object']}, self.context.encoding_limits),
                  'normalization': 'fit-only population moments/equal retained trials/canonical f32'}
        result['index'] = write_index(self.context, self.output_fd, result, 'assembler')
        seed = None
        return result

    def close(self, primary=None):
        self.repository.close(primary)
