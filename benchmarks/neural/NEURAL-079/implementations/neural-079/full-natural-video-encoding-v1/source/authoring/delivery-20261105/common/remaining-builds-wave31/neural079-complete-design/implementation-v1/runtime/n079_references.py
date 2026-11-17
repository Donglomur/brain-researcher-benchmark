"""One protected producer: all12 heads,5496 fits,36 spectra/546 factors.

Only trusted source-bound numeric modules are supplied by the fixed bootstrap.
They compute arrays; neither candidates nor metadata provide completed scores.
"""
import importlib
import math
from n079_common import require, fields, integer, identity, checked_pin, close_all
from n079_arrays import MatrixReader, MatrixWriter, preflight
from n079_plan import PERSONS, Q


class ReferenceProducer:
    def __init__(self, context, repository, primary, independent, output_fd, limits, coordinate_block):
        context.require_effect('reference_fit', 'reference/sub-01/measured')
        self.context, self.repository, self.primary, self.independent = context, repository, primary, independent
        self.output_fd, self.limits, self.width = output_fd, limits, integer(coordinate_block, 1)
        require(self.width <= Q, 'selected full-grid target block width')
        self.np = importlib.import_module('numpy')
        self.counts = {'spectra': 0, 'setting_factors': 0, 'completed_target_fits': 0, 'target_block_applications': 0}
        self.records, self.selections, self.final, self.baselines = [], {}, {}, {}
        self.shared_states = {}; self.mean_states = {}

    def _key(self, person, signal, family):
        return '%s/%s/%s' % (person, signal, family)

    def _load_grams(self, partition, selected):
        fields(selected, ('partition', 'train', 'cross', 'identity'))
        require(selected['partition'] == partition and len(selected['train']) == len(selected['cross']) == 17,
                'complete exact partition17 Gram pairs')
        ident = selected['identity']
        fields(ident, ('source_id', 'fit_id', 'query_id', 'columns_id'))
        require(ident['fit_id'] == identity(partition['train'], self.context.encoding_limits)['sha256'] and
                ident['query_id'] == identity(partition['other'], self.context.encoding_limits)['sha256'], 'same exact fitting/query rows')
        n, m = len(partition['train']), len(partition['other'])
        # Admit the full retained34 arrays plus one active reader copy before
        # the first numeric body is opened. Per-array checks alone are not an
        # aggregate live-memory bound. Solver workspaces are admitted later.
        retained = 17 * (n * n + m * n)
        preflight(self.limits, max(n, m), n, retained + 4 * max(n * n, m * n))
        train, cross = [], []
        for destination, descriptors in ((train, selected['train']), (cross, selected['cross'])):
            for item in descriptors:
                reader = MatrixReader(self.context, self.repository, item, self.limits, 'reference/sub-01/measured')
                error = None
                try:
                    destination.append(reader.block(list(range(reader.shape[0])), 0, reader.shape[1]))
                except BaseException as exc:
                    error = exc; raise
                finally:
                    reader.close(error)
        return train, cross, ident

    def _score_grid(self):
        for person in PERSONS:
            for signal in ('measured', 'mismatch'):
                choices = []
                for order, family in enumerate(('R1', 'R2', 'R3')):
                    key = self._key(person, signal, family)
                    rows = [{'setting_id': r['setting']['id'], 'fold': r['fold'], 'score': r['score']}
                            for r in self.records if r['key'] == key and r['fold'] is not None]
                    # Scores above originated in the independently authored
                    # scorer over actual full blocks, never candidate scalars.
                    selected = self.primary.select_setting(family, rows)
                    self.selections[key] = selected
                    choices.append((selected['score'], -order, family))
                self.selections['champion/' + person + '/' + signal] = max(choices)[2]
        self.context.journal.append('complete_inner_selection', self.selections)

    def _one_head(self, partition, person, signal, family, setting, prepared, ident, selected_targets):
        key = self._key(person, signal, family); work = 'reference/%s/%s' % (person, signal)
        fields(selected_targets, ('train', 'other', 'partition', 'person', 'signal', 'normalization_pin'))
        require(selected_targets['partition'] == partition['id'] and selected_targets['person'] == person and
                selected_targets['signal'] == signal, 'exact target fitting head/partition provenance')
        checked_pin(selected_targets['normalization_pin'])
        require((selected_targets['other'] is None) == (partition['id'] == 'final'),
                'outer query targets absent from reference producer material set')
        require(selected_targets['train']['rows_pin'] == identity(partition['train'], self.context.encoding_limits),
                'same target fitting identities')
        train = None
        evaluation = None; writer = None; error = None; scalar_parts = []; blocks = []
        name = '%s-%s-%s-%s-%d' % (person, signal, family, partition['id'], len(self.records))
        try:
            self.context.ledger.charge(work, {'fit_calls': 1}, 'one complete multioutput target-head fit')
            train = MatrixReader(self.context, self.repository, selected_targets['train'], self.limits, work)
            require(train.shape == (len(partition['train']), Q), 'all exact fitting rows/native coordinates')
            if partition['id'] != 'final':
                require(selected_targets['other']['rows_pin'] == identity(partition['other'], self.context.encoding_limits),
                        'exact inner validation rows')
                evaluation = MatrixReader(self.context, self.repository, selected_targets['other'], self.limits, work)
                require(evaluation.shape == (len(partition['other']), Q), 'all exact inner evaluation rows/native coordinates')
            rows = len(partition['other']) if evaluation is None else 1
            lineage = {'rows_pin': identity(partition['other'] if evaluation is None else ['independent-inner-Pearson'], self.context.encoding_limits),
                       'columns_pin': selected_targets['train']['columns_pin'],
                       'lineage_pin': identity({'targets': selected_targets, 'setting': setting, 'feature_identity': ident,
                                               'independent_scorer': self.context.numeric_source_pins['r2']}, self.context.encoding_limits)}
            writer = MatrixWriter(self.context, self.output_fd, name + '.f64', rows, Q, '<f8', self.limits, work, lineage)
            for start in range(0, Q, self.width):
                stop = min(Q, start + self.width); width = stop - start
                scratch_slots = 12 * (len(partition['train']) + len(partition['other'])) * width
                preflight(self.limits, len(partition['train']), width, prepared.owned_slots + self.loaded_gram_slots + scratch_slots)
                y = train.block(list(range(train.shape[0])), start, stop)
                self.context.ledger.charge(work, {'numeric_block_applications': 1}, 'actual complete-coordinate reference block')
                result = self.primary.predict_prepared(prepared, y, limits=self.limits, identity=ident)
                prediction = result['prediction']; self.counts['target_block_applications'] += 1
                require(prediction.shape == (len(partition['other']), width), 'full actual prediction block')
                block_lineage = {'key': key, 'setting': setting, 'partition_id': partition['id'],
                                 'partition_pin': identity(partition, self.context.encoding_limits), 'start': start, 'stop': stop,
                                 'normalization': selected_targets['normalization_pin'], 'feature_identity': ident,
                                 'numeric_source': self.context.numeric_source_pins['r1']}
                if evaluation is not None:
                    truth = evaluation.block(list(range(evaluation.shape[0])), start, stop)
                    metric = self.independent.pearson(prediction, truth, limits=self.limits)
                    values = metric['values']; require(values.shape == (width,), 'all-coordinate independent score')
                    scalar_parts.append(math.fsum(float(v) for v in values))
                    writer.append_columns(start, values.reshape(1, width))
                    # Immutable source/full inputs/settings and per-block
                    # numeric digests permit exact reviewed reconstruction.
                    # No authentic replay or free second solver is claimed.
                    blocks.append(self.context.record_numeric_digest(work, name + '-block%d' % start,
                        {'prediction': prediction, 'target': truth, 'coefficients': result['state']['coefficients']},
                        block_lineage))
                else:
                    writer.append_columns(start, prediction)
                    learned = {k: result['state'][k] for k in ('intercept', 'coefficients', 'coefficient_kind',
                               'feature_scale', 'selected_rank', 'target_digest')}
                    blocks.append(self.context.state_store.pack(work, name + '-state%d' % start, learned, block_lineage))
            artifact = writer.finish(); writer = None
            record = {'id': name, 'key': key, 'fold': partition['fold'], 'partition': partition,
                      'target_source': selected_targets, 'feature_identity': ident,
                      'shared_state_pin': identity({'prepared': self.shared_states[partition['id']]['prepared'],
                          'factor': self.shared_states[partition['id']]['factors'][family + '/' + setting['id']]}, self.context.encoding_limits),
                      'setting': setting, 'columns': Q,
                      'prediction_or_metric': artifact, 'blocks': blocks,
                      'score': None if evaluation is None else math.fsum(scalar_parts) / Q}
            if record['score'] is not None:
                require(math.isfinite(record['score']), 'finite complete inner score')
            self.records.append(record); self.counts['completed_target_fits'] += 1
            self.context.journal.append('reference_head_complete', record)
            if evaluation is None:
                self.final[key] = record
        except BaseException as exc:
            error = exc; exc.n079_prefix = {'counts': dict(self.counts), 'completed': list(self.records)}; raise
        finally:
            close_all(([('target training reader', lambda: train.close(error))] if train is not None else []) +
                      ([('inner evaluation reader', lambda: evaluation.close(error))] if evaluation is not None else []) +
                      ([('unfinished reference output', lambda: writer.close(error))] if writer is not None else []), error)

    def run(self, partitions, grams, targets):
        require([p['id'] for p in partitions] == ['inner-%d' % i for i in range(5)] + ['final'], 'complete fitting partition order')
        expected_heads = {(p, s) for p in PERSONS for s in ('measured', 'mismatch')}
        require(set(targets) == {p['id'] for p in partitions} and set(grams) == set(targets), 'all partition inputs')
        for partition in partitions:
            if partition['id'] == 'final':
                require(self.counts['completed_target_fits'] == 5460, 'all inner target fits before selection')
                self._score_grid()
            require(set(targets[partition['id']]) == expected_heads, 'all12 separate person/signal schedules')
            train, cross, ident = self._load_grams(partition, grams[partition['id']])
            self.loaded_gram_slots = sum(a.size for a in train + cross)
            preflight(self.limits, len(partition['train']), len(partition['train']), self.loaded_gram_slots * 16)
            prepared = self.primary.prepare_grams(train, cross, limits=self.limits, identity=ident)
            self.context.resident_numeric_slots = self.loaded_gram_slots + prepared.owned_slots
            self.counts['spectra'] += 6
            shared = self.context.state_store.pack('reference/sub-01/measured', partition['id'] + '-prepared',
                prepared, {'partition': partition, 'feature_identity': ident, 'source': self.context.numeric_source_pins['r1']})
            self.shared_states[partition['id']] = {'prepared': shared, 'factors': {}}
            for family in ('R1', 'R2', 'R3'):
                for setting in self.primary.settings(family):
                    factor = self.primary.prepare_setting(prepared, family, setting, limits=self.limits, identity=ident)
                    self.counts['setting_factors'] += 1
                    self.context.resident_numeric_slots = self.loaded_gram_slots + factor.owned_slots
                    factor_key = family + '/' + setting['id']
                    self.shared_states[partition['id']]['factors'][factor_key] = self.context.state_store.pack(
                        'reference/sub-01/measured', partition['id'] + '-factor%d' % self.counts['setting_factors'],
                        factor, {'partition': partition, 'setting': setting, 'feature_identity': ident})
                    # Every selected final state has an actual cached factor;
                    # unused final factors remain explicit work (546 total).
                    for person, signal in sorted(expected_heads):
                        if partition['id'] == 'final' and self.selections[self._key(person, signal, family)]['setting'] != setting:
                            continue
                        self._one_head(partition, person, signal, family, setting, factor, ident,
                                       targets[partition['id']][(person, signal)])
                    del factor
                    self.context.resident_numeric_slots = self.loaded_gram_slots + prepared.owned_slots
            del prepared, train, cross
            self.context.resident_numeric_slots = 0
            self.context.tick()
        require(self.counts['spectra'] == 36 and self.counts['setting_factors'] == 546 and
                self.counts['completed_target_fits'] == 5496 and len(self.final) == 36, 'complete original reference programme')
        self._baselines(targets['final'])
        return {'counts': self.counts, 'records': self.records, 'selections': self.selections, 'final': self.final,
                'baselines': self.baselines, 'mean_states': self.mean_states, 'shared_states': self.shared_states,
                'no_outer_targets_opened': True, 'qualification': 'requires independent execution/source/closure admission'}

    def _baselines(self, selected):
        for person in PERSONS:
            for signal in ('measured', 'mismatch'):
                work = 'reference/%s/%s' % (person, signal); descriptor = selected[(person, signal)]['train']
                reader = None
                lineage = {'rows_pin': identity(list(range(1001, 1103)), self.context.encoding_limits),
                           'columns_pin': descriptor['columns_pin'],
                           'lineage_pin': identity({'baseline': 'training_mean', 'source': descriptor}, self.context.encoding_limits)}
                writer = None; error = None; states = []
                try:
                    reader = MatrixReader(self.context, self.repository, descriptor, self.limits, work)
                    require(reader.shape == (1000, Q), 'all original baseline fitting video means')
                    writer = MatrixWriter(self.context, self.output_fd, '%s-%s-mean.f64' % (person, signal),
                                          102, Q, '<f8', self.limits, work, lineage)
                    self.context.ledger.charge(work, {'fit_calls': 1}, 'separate complete training-mean baseline state')
                    for start in range(0, Q, self.width):
                        stop = min(Q, start + self.width)
                        preflight(self.limits, 1000, stop - start, 6 * 1000 * (stop - start))
                        y = reader.block(list(range(1000)), start, stop)
                        moments = self.independent.moments(y, limits=self.limits)
                        mean = self.np.broadcast_to(moments['mean'], (102, stop - start)).copy()
                        writer.append_columns(start, mean)
                        states.append(self.context.state_store.pack(work, '%s-%s-mean-state%d' % (person, signal, start), moments,
                                                      {'fitting_target': descriptor, 'start': start, 'stop': stop}))
                    self.baselines[person + '/' + signal + '/mean'] = writer.finish(); writer = None
                    self.mean_states[person + '/' + signal] = {'fitting_target': descriptor, 'states': states}
                except BaseException as exc:
                    error = exc; raise
                finally:
                    close_all(([('mean fitting reader', lambda: reader.close(error))] if reader is not None else []) +
                        ([('mean output', lambda: writer.close(error))] if writer is not None else []), error)
        # One source-independent constant array can be safely shared across all
        # six people and signals; it carries no learned target information.
        work = 'reference/sub-01/measured'
        template = next(iter(self.baselines.values()))
        lineage = {k: template[k] for k in ('rows_pin', 'columns_pin')}
        lineage['lineage_pin'] = identity({'baseline': 'literal_zero', 'learned_state': None}, self.context.encoding_limits)
        writer = MatrixWriter(self.context, self.output_fd, 'zero-baseline.f64', 102, Q, '<f8', self.limits, work, lineage)
        error = None
        try:
            for start in range(0, Q, self.width):
                width = min(self.width, Q - start)
                preflight(self.limits, 102, width, 3 * 102 * width)
                writer.append_columns(start, self.np.zeros((102, width), dtype='float64'))
            self.baselines['zero'] = writer.finish()
        except BaseException as exc:
            error = exc; raise
        finally:
            writer.close(error)
        self.counts['mean_baseline_states'] = 12
