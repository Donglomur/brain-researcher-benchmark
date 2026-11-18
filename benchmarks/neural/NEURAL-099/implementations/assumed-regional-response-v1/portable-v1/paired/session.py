"""Trusted lazy current-trial broker; no provider execution or containment.

The two arms must both lock the current trial before any later history is read.
A failed submission terminates the study. There is no partial scoring, retries,
auto-imputation or resume. Candidate state isolation is an external obligation.
"""
import hashlib
import json
import secrets
from dependencies import load
from observations import ObservationAdapter
from transports import build_request
from access import profile, schedule

SCORER = load('scoring')
ARMS = ('direct-structured-zero-label-current-trial-v1',
        'frozen-programme-zero-label-current-trial-v1')
EDGES = [i / 1000 for i in range(101)]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def check_hash(value):
    if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('A lowercase SHA-256 procedure binding is required')
    return value


def validate_study_id(value):
    if type(value) is not str or not value or len(value) > 128 or not value.isascii() or any(ord(c) < 33 for c in value):
        raise ValueError('Invalid study ID')
    return value


class Study:
    """Trusted-only controller. Never give this object or its callback to agents.

    procedure_hashes bind separately frozen native instructions/configuration
    and programme source/initial parameters. Hashes do not verify their content,
    zero-label provenance, actual tool restrictions or fresh process/context.
    """
    def __init__(self, cases, history_projection, journal, *, study_id,
                 procedure_hashes, production=False):
        validate_study_id(study_id)
        if type(procedure_hashes) is not dict or set(procedure_hashes) != set(ARMS):
            raise ValueError('Both frozen procedures must be bound before release')
        self._procedures = {arm: check_hash(procedure_hashes[arm]) for arm in ARMS}
        self._schedule = schedule(cases, production=production)
        self._adapter = ObservationAdapter(cases, history_projection)
        self._journal = journal
        self._study_id = study_id
        self._attempt_nonce = secrets.token_hex(32)
        self._position = 0
        self._arm = 0
        self._observations = None
        self._request = None
        self._failed = False
        self._sealed = None
        self._locked_cases = {arm: 0 for arm in ARMS}
        self._case_count = len(cases)
        self._production = production
        self._roster_hash = digest(cases)
        # Durable start exists before any history can be requested.
        self._journal.start({
            'schema': 'neural099-paired-study-start/v1', 'study_id': study_id,
            'attempt_nonce': self._attempt_nonce,
            'production': production, 'case_metadata_sha256': self._roster_hash,
            'procedures': self._procedures, 'arms': list(ARMS),
            'profiles': [profile(arm) for arm in ARMS],
            'cases_per_arm': len(cases), 'trials_per_arm': len(self._schedule),
            'schedule_sha256': digest(self._schedule),
            'state': 'incomplete_no_score_or_label_release',
        })

    def _active(self):
        if self._failed:
            raise ValueError('Study is terminally incomplete after a failure')
        if self._sealed is not None:
            raise ValueError('Study is already sealed')

    def current(self):
        self._active()
        if self._position == len(self._schedule):
            raise ValueError('All predictions locked; call finish')
        if self._request is None:
            try:
                row = self._schedule[self._position]
                if self._observations is None:
                    self._observations = self._adapter.observations(
                        row['asset_id'], row['source_trial_row'], view='timing_history')
                token = digest({'study_id': self._study_id, 'attempt_nonce': self._attempt_nonce,
                                'procedures': self._procedures, 'ordinal': self._position,
                                'schedule_row': row})
                request = build_request(profile(ARMS[self._arm]), self._observations,
                                        self._study_id, token)
                # Fold number is grouping metadata, never a training permission.
                request['outer_fold'] = row['outer_fold']
                request['procedure_sha256'] = self._procedures[ARMS[self._arm]]
                self._request = request
            except Exception:
                self._failed = True
                raise
        return json.loads(canonical(self._request))

    def submit(self, submission):
        self._active()
        try:
            if self._request is None:
                raise ValueError('Request must be released before submission')
            if type(submission) is not dict or set(submission) != {'condition_id', 'trial_token', 'payload_sha256', 'predictions'}:
                raise ValueError('Exact submission envelope required')
            arm = ARMS[self._arm]
            for key in ('condition_id', 'trial_token', 'payload_sha256'):
                if type(submission[key]) is not str or submission[key] != self._request[key]:
                    raise ValueError('Stale, mismatched or altered submission')
            cases = [row['case'] for row in self._observations]
            admitted = SCORER.admit_predictions(cases, submission['predictions'], edges_seconds=EDGES)
            predictions = [{'case_id': case['case_id'], 'rates': admitted[case['case_id']]}
                           for case in cases]
            row = self._schedule[self._position]
            record = {
                'schema': 'neural099-locked-prediction/v1',
                'study_id': self._study_id, 'attempt_nonce': self._attempt_nonce,
                'trial_ordinal': self._position,
                'outer_fold': row['outer_fold'], 'condition_id': arm,
                'procedure_sha256': self._procedures[arm],
                'trial_token': self._request['trial_token'],
                'payload_sha256': self._request['payload_sha256'],
                'predictions_sha256': digest(predictions), 'predictions': predictions,
            }
            receipt = self._journal.commit(record)  # complete fsync before advance
            self._locked_cases[arm] += len(predictions)
            self._request = None
            self._arm += 1
            if self._arm == len(ARMS):
                self._arm = 0
                self._position += 1
                self._observations = None  # never forwarded into next context
            return {'state': 'locked', 'receipt': receipt}
        except Exception:
            self._failed = True
            raise

    def finish(self):
        self._active()
        if self._position != len(self._schedule) or self._arm or any(n != self._case_count for n in self._locked_cases.values()):
            raise ValueError('Incomplete pair: no score/label release is eligible')
        try:
            result = {
                'schema': 'neural099-paired-completion/v1',
                'study_id': self._study_id, 'attempt_nonce': self._attempt_nonce,
                'production': self._production,
                'state': 'all_configured_predictions_locked',
                'cases_per_arm': dict(self._locked_cases),
                'trials_per_arm': len(self._schedule), 'fold_groups': 5,
                'case_metadata_sha256': self._roster_hash,
                'procedures': self._procedures,
                'score_and_label_release': 'eligible_for_separate_evaluator_admission_only',
                'scores_computed': 0, 'target_values_released': 0,
            }
            receipt = self._journal.seal(result)
            self._sealed = {**result, 'journal_receipt': receipt}
            return json.loads(canonical(self._sealed))
        except Exception:
            self._failed = True
            raise
