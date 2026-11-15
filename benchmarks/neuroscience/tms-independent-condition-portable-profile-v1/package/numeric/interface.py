"""Controller-only grading of closed candidate artifacts.

Candidate code never runs in this process. The returned receipt describes only
ingestion; category agreement and every score remain with the private writer.
This boundary is not an arbitrary-code or timing/process-side-channel sandbox.
"""
import hashlib
import json
import os
import stat

from kernel import Refusal
from custody import require_operator_reference
from score_owned import score

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


class ControllerInterface:
    """Keep this object and writer wholly outside a candidate-controlled process."""
    __slots__ = ('__reference', '__writer', '__limit', '__calls')

    def __init__(self, *, operator_reference, private_writer, max_submissions):
        require_operator_reference(operator_reference)
        if not callable(private_writer) or type(max_submissions) is not int or max_submissions != 6:
            raise ValueError('fixed owner-only engineering interface configuration')
        self.__reference = operator_reference
        self.__writer = private_writer
        self.__limit = max_submissions
        self.__calls = 0

    def __claim_attempt(self):
        if self.__calls >= self.__limit:
            raise ValueError('finite closed-submission allowance exhausted')
        self.__calls += 1
        return self.__calls

    def submit_closed_file(self, path, /):
        # Charge the finite attempt BEFORE any file capture, including a failed
        # capture. Exhausted callers cannot issue more file reads.
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
            result = score(body, operator_reference=self.__reference)
        except Refusal as exc:
            # This private result must never become candidate-facing status.
            private = {'status': 'refused', 'reason': str(exc)}
        else:
            private = {'status': 'scored', 'score': result}
        self.__writer(prefix + '.outcome.private.json', encode(private))
        receipt = {'schema': 'tms_closed_submission_ingestion_v1',
                   'ordinal': ordinal, 'bytes': len(body),
                   'sha256': hashlib.sha256(body).hexdigest(), 'closed': True}
        self.__writer(prefix + '.receipt.private.json', encode(receipt))
        return receipt
