"""Attempt lifetime admission, monotonic enforcement and terminal failure custody.

The complete allocation is never silently reduced to fit a nearly expired
attempt. The extra 30 seconds is a finalization reserve, not scientific time.
An expired attempt can issue only an archival terminal_failure envelope; that
kind can never satisfy a DONE predecessor or authorize another operation.
"""
from __future__ import annotations
import time
from .io import ContractError
FINALIZATION_SECONDS = 30
FAILURE_RECORD_VALIDITY_SECONDS = 86400


def admit(expiry, wall_seconds, *, wall=None, mono=None):
    wall = time.time() if wall is None else wall
    mono = time.monotonic() if mono is None else mono
    if type(expiry) is not int or type(wall_seconds) is not int or wall_seconds <= 0:
        raise ContractError('finite exact attempt expiry and full stage wall allocation required')
    if expiry - wall < wall_seconds + FINALIZATION_SECONDS:
        raise ContractError('attempt lifetime cannot contain full stage and finalization reserve')
    return {'attempt_expires_at': expiry, 'admitted_wall': wall, 'admitted_monotonic': mono,
            'stage_deadline': mono + wall_seconds,
            'terminal_deadline': mono + wall_seconds + FINALIZATION_SECONDS,
            'expiry_monotonic': mono + expiry - wall,
            'finalization_reserve_seconds': FINALIZATION_SECONDS}


def check(plan, *, phase='stage', wall=None, mono=None):
    wall = time.time() if wall is None else wall
    mono = time.monotonic() if mono is None else mono
    bound = plan['stage_deadline' if phase == 'stage' else 'terminal_deadline']
    if wall >= plan['attempt_expires_at'] or mono >= min(bound, plan['expiry_monotonic']):
        raise ContractError('attempt execution/finalization deadline exhausted: ' + phase)


def finalize(payload, plan, *, wall=None, mono=None):
    """Pure final signing policy. A late result is retained only as a failure."""
    wall = time.time() if wall is None else wall
    mono = time.monotonic() if mono is None else mono
    result = dict(payload); body = dict(result['content'])
    try:
        check(plan, phase='terminal', wall=wall, mono=mono)
    except ContractError as exc:
        body['outcome'] = 'failed'
        body['failure'] = {'class': 'AttemptDeadlineFailure', 'message': str(exc),
                           'prior_failure': body.get('failure')}
        body['deadline_disposition'] = 'archival_only_no_predecessor_authority'
        body['original_attempt_expires_at'] = plan['attempt_expires_at']
        result['kind'] = 'terminal_failure'
        result['evidence_id'] = 'FAILED_' + result['stage']
        result['expires_at'] = int(wall) + FAILURE_RECORD_VALIDITY_SECONDS
    else:
        result['expires_at'] = plan['attempt_expires_at']
    result['issued_at'] = int(wall)
    result['content'] = body
    return result
