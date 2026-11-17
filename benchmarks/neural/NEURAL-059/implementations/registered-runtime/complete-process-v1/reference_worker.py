"""One selected session reference process, with original fit/validation numerics.

The enclosing server/owner owns transport, process limits, accounting and death
verification. This object never opens a socket and never sees held-out targets.
Closing its objects is not a claim that its process or native threads have exited.
"""
from copy import deepcopy
import resource
import time

from .native_profile import runtime_factory, pin, compact
from .scientific import campaign, native_references as reference, preparation
from .scientific.contracts import need, CONDITIONS, STATUS
from .scientific.io import OwnedDirectory, Journal


BOOT_KEYS = {'selection_identity', 'native_profile', 'native_authorization',
             'shape', 'session', 'conditions'}
SESSION_KEYS = {'session_id', 'source_identity', 'unit_ids', 'cases'}
CASE_KEYS = {'case_id', 'ordinal', 'split', 'S', 'B', 'H', 'N', 'y',
             'window_start', 'window_end', 'prior_case_id', 'history_available',
             'history_reason', 'unit_ids', 'count_row'}


def _clock():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {'wall': time.monotonic(), 'cpu': usage.ru_utime + usage.ru_stime,
            'maxrss_raw': usage.ru_maxrss, 'maxrss_units': 'KiB on selected Linux'}


def _elapsed(start):
    now = _clock()
    return {'wall_seconds': now['wall'] - start['wall'],
            'cpu_seconds': now['cpu'] - start['cpu'],
            'maxrss_raw': now['maxrss_raw'], 'maxrss_units': now['maxrss_units'],
            'scope': 'worker RUSAGE_SELF observation; outer owner accounts complete process tree'}


class ReferenceWorker:
    def __init__(self, bootstrap):
        self.origin = _clock()
        self.directory = self.journal = self.runtime = None
        self.state = 'initializing'
        self.failure_records, self.operation_records, self.fit_records = [], [], []
        self.models, self.fitted = {}, None
        self.prior_record = None
        self.infer_attempts = 0
        self.query_position, self.query_seen = 0, set()
        self.selection_identity = None
        try:
            need(type(bootstrap) is dict and set(bootstrap) == BOOT_KEYS, 'exact reference bootstrap')
            authorization = bootstrap['native_authorization']
            need(type(authorization) is dict and authorization.get('selection_identity') ==
                 bootstrap['selection_identity'], 'reference bootstrap joins owner source selection')
            self.selection_identity = deepcopy(bootstrap['selection_identity'])
            shape = reference._shape(bootstrap['shape'])
            self.shape = shape
            conditions = tuple(bootstrap['conditions'])
            need(type(bootstrap['conditions']) is list and conditions in (CONDITIONS, ('SHN', 'SBHN')),
                 'original full primary or neural-diagnostic condition scope')
            self.conditions = conditions
            session = bootstrap['session']
            need(type(session) is dict and set(session) == SESSION_KEYS,
                 'target-free reference session has no slots/raw/diagnostic donor metadata')
            need(session['session_id'] == shape['session_id'] and session['unit_ids'] == shape['unit_ids'],
                 'reference session binds complete original unit axis')
            need(type(session['source_identity']) in (str, dict) and session['source_identity'],
                 'original source identity retained')
            need(type(session['cases']) is list, 'training and validation case list')
            for case in session['cases']:
                need(type(case) is dict and set(case) == CASE_KEYS,
                     'exact original prepared calibration case schema')
                need(case['split'] in ('train', 'val') and case['case_id'] in
                     shape['case_ids'][case['split']], 'held case never enters reference fit process')
                need(type(case['y']) is int and case['y'] in (0, 1), 'original binary calibration target')
                need(case['unit_ids'] == shape['unit_ids'], 'calibration keeps complete ordered unit census')
                need(type(case['ordinal']) is int and case['ordinal'] >= 0, 'original case ordinal')
            need([c['case_id'] for c in session['cases']] ==
                 shape['case_ids']['train'] + shape['case_ids']['val'],
                 'all original ordered train/validation cases exactly once')
            need([c['ordinal'] for c in session['cases']] ==
                 sorted({c['ordinal'] for c in session['cases']}), 'original unique calibration chronology')
            self.session = deepcopy(session)
            self.bootstrap_identity = pin(bootstrap)
            self.runtime = runtime_factory(shape, profile=bootstrap['native_profile'],
                                           authorization=authorization)
            limits = authorization['worker_io']
            # /work is an owner-created private writable mount. /work/ref must not exist.
            self.directory = OwnedDirectory('/work/ref', limits['artifact_bytes'])
            self.journal = Journal(self.directory, 'validation.jsonl', limits['journal_bytes'])
            self.state = 'ready'
        except BaseException as error:
            self.state = 'failed'
            self.failure_records.append({'phase': 'initialize', 'type': type(error).__name__,
                                         'message': str(error)})
            for name, owned in (('journal', self.journal), ('directory', self.directory)):
                if owned is not None:
                    try:
                        owned.close()
                    except BaseException as secondary:
                        self.failure_records.append({'phase': 'initialize_' + name + '_close',
                            'type': type(secondary).__name__, 'message': str(secondary)})
                        error.add_note('Initialization closure also refused: ' + repr(secondary))
            raise

    def _prior(self, labels):
        # Same available/empty disposition as campaign.fit_references, lines171–173.
        return {**reference.prior(labels), 'status': 'available'} if labels else {
            'status': 'unavailable', 'error': 'empty fitting support',
            'qualification': STATUS, 'fit_attempted': False}

    def _write(self, name, value):
        return self.directory.write(name, compact(value) + b'\n')

    def _failure(self, phase, error, start):
        row = {'phase': phase, 'type': type(error).__name__, 'message': str(error),
               'own_process_work': _elapsed(start), 'original_failure': True}
        self.failure_records.append(row)
        self.state = 'failed'
        try:
            row['retained'] = self._write('failure-%06d.json' % len(self.failure_records), {
                'failure': row, 'fit_records': self.fit_records,
                'prior_record': self.prior_record,
                'inference_records': [] if self.runtime is None else self.runtime.inference_records})
        except BaseException as secondary:
            row['publication_failure'] = {'type': type(secondary).__name__, 'message': str(secondary)}
            error.add_note('Reference worker failure publication also refused: ' + repr(secondary))

    def fit(self):
        need(self.state == 'ready', 'one selected reference fit; no retry after failure')
        self.state = 'fitting'; start = _clock()
        try:
            train = [c['y'] for c in self.session['cases'] if c['split'] == 'train']
            self.prior_record = {'session_id': self.session['session_id'], 'family': 'prior',
                                 'train': self._prior(train), 'refit': None}
            fitted = campaign.fit_validation_panel(
                self.session, self.conditions, self.runtime, reference,
                preparation.project_case, self.journal, records=self.fit_records)
            # ValidationPanel sealed the entire selected L/H grid before this label use.
            val = [c['y'] for c in self.session['cases'] if c['split'] == 'val']
            self.prior_record['refit'] = self._prior(train + val)
            self.models = fitted
            rows = [{'condition': condition, 'family': family,
                     'model': deepcopy(fitted[(condition, family)])}
                    for condition in self.conditions for family in ('L', 'H')]
            complete = all(row['model'].get('status') == 'available' for row in rows)
            complete = complete and self.prior_record['refit'].get('status') == 'available'
            self.state = 'fitted' if complete else 'unavailable'
            original_records = [deepcopy(self.prior_record), {
                'session_id': self.session['session_id'],
                'complete_panel_records': deepcopy(self.fit_records),
                'runtime_inference_records': deepcopy(self.runtime.inference_records)}]
            result = {'models': rows, 'prior': deepcopy(self.prior_record['refit']),
                      'records': original_records, 'runtime_identity': deepcopy(self.runtime.identity),
                      'inference_records': deepcopy(self.runtime.inference_records),
                      'status': self.state, 'qualification': STATUS}
            self.operation_records.append({'phase': 'fit', 'own_process_work': _elapsed(start),
                                           'result_identity': pin(result)})
            self.fit_result_identity = self._write('fit.json', result)
            self.fitted = result
            return deepcopy(result)
        except BaseException as error:
            self._failure('fit', error, start)
            raise

    def infer(self, request):
        need(self.state == 'fitted', 'complete available frozen reference panel before held inference')
        self.infer_attempts += 1
        start, begin = _clock(), len(self.runtime.inference_records)
        try:
            need(type(request) is dict and set(request) == {'family', 'condition', 'view'},
                 'exact one-view reference inference request')
            family, condition, view = request['family'], request['condition'], request['view']
            need(family in ('L', 'H') and condition in self.conditions, 'selected frozen reference cell')
            need(type(view) is dict and set(view) == {'case_id', 'condition', 'feature_names', 'features'}
                 and view['condition'] == condition, 'current y-free held projection only')
            cases = self.shape['case_ids']['test']
            need(self.query_position < len(cases) and view['case_id'] == cases[self.query_position],
                 'original held chronology; no future/previous case revisit')
            key = (family, condition)
            need(key not in self.query_seen, 'one original reference response per current panel cell')
            model = self.models[(condition, family)]
            probabilities = reference.predict(model, [deepcopy(view)], self.runtime)
            need(type(probabilities) is list and len(probabilities) == 1, 'one current-case probability')
            result = {'p': probabilities[0],
                      'inference_records': deepcopy(self.runtime.inference_records[begin:]),
                      'qualification': STATUS}
            self.operation_records.append({'phase': 'infer', 'request_identity': pin(request),
                                           'result_identity': pin(result), 'own_process_work': _elapsed(start)})
            self._write('infer-%09d.json' % self.infer_attempts, result)
            self.query_seen.add(key)
            if self.query_seen == {(f, c) for f in ('L', 'H') for c in self.conditions}:
                self.query_position += 1; self.query_seen.clear()
            return result
        except BaseException as error:
            self._failure('infer', error, start)
            raise

    def close(self):
        need(self.state != 'closed', 'one reference object closure')
        previous = self.state
        self.state = 'closing'
        result = {'status': STATUS, 'previous_state': previous,
                  'selection_identity': deepcopy(self.selection_identity),
                  'bootstrap_identity': getattr(self, 'bootstrap_identity', None),
                  'runtime_identity': None if self.runtime is None else deepcopy(self.runtime.identity),
                  'fit_result_identity': getattr(self, 'fit_result_identity', None),
                  'fit_records': deepcopy(self.fit_records), 'prior_record': deepcopy(self.prior_record),
                  'operation_records': deepcopy(self.operation_records),
                  'failure_records': deepcopy(self.failure_records),
                  'inference_attempts': self.infer_attempts,
                  'complete_held_cases': self.query_position,
                  'pending_held_cells': [list(x) for x in sorted(self.query_seen)],
                  'required_held_cases': len(self.shape['case_ids']['test']),
                  'own_process_work': _elapsed(self.origin),
                  'process_exit_verified': False,
                  'closure_scope': 'owned Python handles; outer owner must verify actual process/tree exit'}
        if self.runtime is not None:
            result['inference_records'] = deepcopy(self.runtime.inference_records)
            result['runtime_calls'] = deepcopy(self.runtime.calls)
            result['native_state_keys_before_release'] = sorted(self.runtime.models)
            # Keys bind original recorded states; this does not claim a fresh native-state audit.
            self.runtime.models.clear()
        errors = []
        try:
            if self.journal is not None:
                result['validation_journal'] = {
                    'attempted_bytes': self.journal.total, 'poisoned': self.journal.poisoned}
                self.journal.close()
        except BaseException as error:
            errors.append({'phase': 'journal_close', 'type': type(error).__name__, 'message': str(error)})
        try:
            if self.directory is not None:
                result['owned_io_before_close_record'] = {
                    'attempted_write_bytes': self.directory.written,
                    'readback_bytes': self.directory.readback_bytes,
                    'max_bytes': self.directory.max_bytes}
                self._write('close.json', result)
        except BaseException as error:
            errors.append({'phase': 'close_record', 'type': type(error).__name__, 'message': str(error)})
        finally:
            try:
                if self.directory is not None:
                    self.directory.close()
            except BaseException as error:
                errors.append({'phase': 'directory_close', 'type': type(error).__name__, 'message': str(error)})
        self.state = 'closed'
        result['object_handles_closed'] = not errors
        result['closure_errors'] = errors
        result['owned_io_after_close_record'] = None if self.directory is None else {
            'attempted_write_bytes': self.directory.written, 'readback_bytes': self.directory.readback_bytes}
        return result
