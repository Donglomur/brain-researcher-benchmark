"""Trusted operator interface; describe is safe, serve needs separate admission.

Serve does not run models/programmes. It reads a private packet and receives
operator-forwarded predictions over JSONL. Never expose this process, its input
files, journal or complete stdout to a participant. Only forward the selected
request payload into a freshly isolated candidate context/process.

An execution manifest is an accident guard and exact scope record, not evidence
of root authorization or a resource supervisor. Actual execution is NOT admitted
by shipping this source. No resume/subset/testing flag exists on production serve.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

HERE = Path(__file__).resolve().parent
# Explicit trusted source import supports isolated (-I -S -B) invocation.
sys.path.insert(0, str(HERE))
from access import schedule
from collect import Journal
from dependencies import load
from session import ARMS, Study, check_hash, validate_study_id

CASE_FILE_SHA = '4cf619e8c06b012b299a45aaab1397c31ebe6cafee00db985077783f026e0582'
PACKET_SHA = 'f10a48794f2778b7f208b4323315e3ca034e58ee268e7653306e189f2c20e536'


def read_json(path, cap, expected_sha=None):
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > cap:
            raise ValueError('Input is not a bounded, single-link regular JSON file')
        data = bytearray()
        while len(data) <= cap:
            part = os.read(fd, min(65536, cap + 1 - len(data)))
            if not part:
                break
            data.extend(part)
        after = os.fstat(fd)
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        if len(data) > cap or len(data) != before.st_size or signature(before) != signature(after):
            raise ValueError('Input changed or exceeded its bound')
        if expected_sha is not None and hashlib.sha256(data).hexdigest() != expected_sha:
            raise ValueError('Input SHA-256 mismatch')
        return strict_json(data)
    finally:
        os.close(fd)


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError('Nonfinite JSON value')
    return json.loads(data, object_pairs_hook=pairs, parse_constant=nonfinite)


def manifest(value):
    fields = {'schema', 'phase', 'study_id', 'cases_path', 'packet_path',
              'packet_binding', 'output_path', 'procedure_hashes',
              'max_message_bytes', 'max_journal_bytes', 'max_record_bytes',
              'runtime_supervisor_and_isolation_admission_reference'}
    if type(value) is not dict or set(value) != fields:
        raise ValueError('Exact finite execution manifest required')
    if value['schema'] != 'neural099-paired-operator-manifest/v1' or value['phase'] != 'separately_admitted_authentic_observation_collection':
        raise ValueError('Manifest is not for the selected future phase')
    for field in ('max_message_bytes', 'max_journal_bytes', 'max_record_bytes'):
        if type(value[field]) is not int or value[field] <= 0:
            raise ValueError('Explicit finite storage/message limits required')
    if value['max_message_bytes'] > 262144 or value['max_record_bytes'] > 262144 or value['max_journal_bytes'] > 2 ** 32:
        raise ValueError('Operator limits exceed source interface ceiling')
    if value['max_record_bytes'] > value['max_journal_bytes']:
        raise ValueError('Invalid output cap')
    for field in ('cases_path', 'packet_path', 'output_path'):
        if type(value[field]) is not str or not Path(value[field]).is_absolute():
            raise ValueError('Explicit absolute private operator paths required')
    ref = value['runtime_supervisor_and_isolation_admission_reference']
    if type(ref) is not str or not ref or len(ref) > 256:
        raise ValueError('Later external runtime/containment admission reference required')
    if type(value['procedure_hashes']) is not dict or set(value['procedure_hashes']) != set(ARMS):
        raise ValueError('Both procedures must be frozen before authentic input access')
    validate_study_id(value['study_id'])
    for procedure in value['procedure_hashes'].values():
        check_hash(procedure)
    binding = value['packet_binding']
    if type(binding) is not dict or binding.get('sha256') != PACKET_SHA or binding.get('bytes') != 15787200 or binding.get('case_count') != 9867:
        raise ValueError('Selected complete authentic packet binding required')
    return value


def operator_loop(study, incoming, outgoing, *, max_message_bytes, max_commands):
    """Bounded generated-testable protocol. Malformed input terminates the loop."""
    def emit(value):
        body = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode() + b'\n'
        # Responses contain one trial or an aggregate receipt; no label outputs.
        if len(body) > max_message_bytes:
            raise ValueError('Response exceeds selected message budget')
        outgoing.write(body)
        outgoing.flush()
    emit({'operation': 'begin', 'state': 'incomplete', 'score_or_label_release': False})
    for _ in range(max_commands):
        body = incoming.readline(max_message_bytes + 1)
        if not body or len(body) > max_message_bytes or not body.endswith(b'\n'):
            raise ValueError('EOF, oversized or incomplete command; attempt incomplete')
        command = strict_json(body)
        if type(command) is not dict or type(command.get('operation')) is not str:
            raise ValueError('Exact operator command required')
        op = command['operation']
        if op == 'current' and set(command) == {'operation'}:
            emit({'operation': op, 'request': study.current()})
        elif op == 'submit' and set(command) == {'operation', 'submission'}:
            emit({'operation': op, 'receipt': study.submit(command['submission'])})
        elif op == 'finish' and set(command) == {'operation'}:
            emit({'operation': op, 'completion': study.finish()})
            return
        else:
            raise ValueError('Unknown operation or extra/private command fields')
    raise ValueError('Command budget exhausted; attempt incomplete')


def serve(path):
    # This function is not invoked in this source-construction phase.
    selected = manifest(read_json(path, 65536))
    cases = read_json(selected['cases_path'], 3 * 1024 ** 2, CASE_FILE_SHA)
    schedule(cases, production=True)  # no subset accepted before packet read
    codec = load('count_packet')
    with codec.verify_packet(selected['packet_path'], cases, selected['packet_binding'],
                             max_bytes=15787200) as packet:
        journal = Journal(selected['output_path'], max_total_bytes=selected['max_journal_bytes'],
                          max_record_bytes=selected['max_record_bytes'])
        study = Study(cases, packet.history_projection, journal, study_id=selected['study_id'],
                      procedure_hashes=selected['procedure_hashes'], production=True)
        operator_loop(study, sys.stdin.buffer, sys.stdout.buffer,
                      max_message_bytes=selected['max_message_bytes'], max_commands=5238 * 4 + 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('describe')
    selected = sub.add_parser('serve')
    selected.add_argument('--execution-manifest', required=True)
    args = parser.parse_args()
    if args.command == 'describe':
        print(json.dumps(read_json(HERE / 'CONTRACT.json', 65536), indent=2, sort_keys=True))
    else:
        serve(args.execution_manifest)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Detailed paths/data stay out of participant-forwarded diagnostics.
        print(json.dumps({'state': 'failed_or_incomplete', 'error_type': type(error).__name__,
                          'score_or_label_release': False}), file=sys.stderr)
        raise SystemExit(2)
