"""Operator-side ingestion for explicitly invented TMS fixture references.

This arithmetic adapter does not run a candidate or prove process isolation.
"Closed" means the operator supplies a complete packet after its own candidate
execution has ended. The caller receives ingestion-only receipts; the trusted
private_writer receives requests, scores/refusals, and rounding diagnostics.
Production reference admission remains closed in certificate.py.
"""
import hashlib
import json
import os
import stat

from kernel import Refusal
from certificate import FixtureContext, admit_fixture_reference
from scorer import score_fixture
from rounding import from_score

MAX_SUBMISSION_BYTES = 2232

def capture_closed_file(path):
    """Path selected by the trusted controller after candidate closure."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 <= before.st_size <= MAX_SUBMISSION_BYTES:
            raise ValueError('bounded ordinary closed submission required')
        chunks = []
        left = before.st_size
        while left:
            block = os.read(fd, left)
            if not block:
                raise ValueError('incomplete closed submission')
            chunks.append(block)
            left -= len(block)
        after = os.fstat(fd)
        signature = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if signature(before) != signature(after):
            raise ValueError('closed submission changed')
        body = b''.join(chunks)
    finally:
        os.close(fd)
    return body

def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()

class FixtureControllerInterface:
    """Keep this object and writer outside any candidate-controlled process."""
    __slots__ = ('__body', '__pin', '__context', '__writer', '__limit', '__calls')

    def __init__(self, *, reference_body, reference_pin, context,
                 private_writer, max_submissions=6):
        if not callable(private_writer) or type(max_submissions) is not int or max_submissions != 6:
            raise ValueError('fixed owner-only engineering interface configuration')
        if type(context) is not FixtureContext:
            raise ValueError('explicit invented fixture context required')
        # Snapshot the caller's mutable pin/context containers before admission.
        # This is an ordinary trusted-operator API, not adversarial memory isolation.
        snapshot = FixtureContext(context.fixture_sha256, context.source_lock_sha256,
                                  context.runtime_sha256, context.attempt)
        admit_fixture_reference(reference_body, reference_pin, snapshot)
        self.__body = reference_body
        self.__pin = dict(reference_pin)
        self.__context = snapshot
        self.__writer = private_writer
        self.__limit = max_submissions
        self.__calls = 0

    def __claim_attempt(self):
        if self.__calls >= self.__limit:
            raise ValueError('finite closed-submission allowance exhausted')
        self.__calls += 1
        return self.__calls

    def submit_closed_file(self, path, /):
        ordinal = self.__claim_attempt()
        return self.__process_body(capture_closed_file(path), ordinal)

    def submit_closed_bytes(self, body, /):
        return self.__process_body(body, self.__claim_attempt())

    def __process_body(self, body, ordinal):
        if type(body) is not bytes or len(body) > MAX_SUBMISSION_BYTES:
            raise ValueError('bounded candidate bytes before hashing')
        prefix = f'submission-{ordinal:02d}'
        self.__writer(prefix + '.request.private.bin', body)
        try:
            result = score_fixture(candidate_body=body, reference_body=self.__body,
                                   reference_pin=self.__pin, context=self.__context)
        except Refusal as exc:
            # No target-derived refusal is returned to the submission caller.
            outcome = {'status': 'refused', 'reason': str(exc)}
        else:
            outcome = {'status': 'scored', 'score': result}
            self.__writer(prefix + '.rounding.private.json', encode(from_score(body, result)))
        self.__writer(prefix + '.outcome.private.json', encode(outcome))
        receipt = {'schema': 'tms_closed_submission_ingestion_v1',
                   'ordinal': ordinal, 'bytes': len(body),
                   'sha256': hashlib.sha256(body).hexdigest(), 'closed': True}
        self.__writer(prefix + '.receipt.private.json', encode(receipt))
        return receipt
