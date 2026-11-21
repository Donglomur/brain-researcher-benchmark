"""Future trusted-operator consumer for the additive full 6400 numerical packet.

This module does not enforce a participant sandbox or call any model. The caller
must authenticate this source and select an execution/resource envelope. Keep
PacketSession and its complete roster in the trusted operator; a participant
receives only context(). No original data or packet was read in preparation.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time

CONDITION_ID = 'erp-core-remaining-persons-released-marker-v1'
CONDITIONS = ('numeric_direct_four_demo', 'numeric_program_four_demo')
NO_TOOLS = 'Do not use tools, code execution, external retrieval, files, or memory from other query trials.'
PROGRAMME_TOOLS = ('Numerical tools and candidate code execution are allowed for this query. '
                   'Do not use external retrieval, other files, or memory from other query trials.')
LEGACY_PINS = {
    'demonstrations.json': {'bytes': 129921, 'sha256': '19e4018216376af334fd5ead21e2c33d5761d9d56ce5c76d3a89411483906ed2'},
    'prompt.txt': {'bytes': 1703, 'sha256': '2ecc6656d099083f2d87112147430aa1f780c714ce31579e025c69ac74ec77a0'},
    'response_schema.json': {'bytes': 480, 'sha256': 'bd0c92c7016a20b039fbb273aad8802be1da088b0f1fec3e15fac0a1070eed12'},
}
QUERY_COUNT = 6400
QUERY_LIMIT = 60000
SHARD_LIMIT = 200 * QUERY_LIMIT
ROSTER_LIMIT = 4 * 1024**2
MANIFEST_LIMIT = 1024**2
CONTEXT_LIMIT = 256 * 1024
RESPONSE_LIMIT = 4096
ENVELOPE_LIMIT = 16384
LEDGER_LIMIT = QUERY_COUNT * ENVELOPE_LIMIT
ID_RE = re.compile(r'q-[0-9a-f]{32}\Z')
SHARD_RE = re.compile(r'queries/p-[0-9a-f]{24}\.jsonl\Z')


class Refusal(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise Refusal(message)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode('utf-8')


def descriptor(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def decode(body):
    return json.loads(body.decode('utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(Refusal('Nonfinite JSON constant')))


def check_pin(pin, cap):
    need(type(pin) is dict and set(pin) == {'bytes', 'sha256'}, 'Exact byte/hash pin required')
    need(type(pin['bytes']) is int and 0 < pin['bytes'] <= cap, 'Pinned size outside bound')
    need(type(pin['sha256']) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256']), 'SHA256 required')


def identity(fd):
    s = os.fstat(fd)
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)


def ordinary(fd, size=None, cap=None):
    s = os.fstat(fd)
    need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'Ordinary single-link file required')
    if size is not None:
        need(s.st_size == size, 'Exact pinned file size required')
    if cap is not None:
        need(0 < s.st_size <= cap, 'File size outside bound')
    return identity(fd)


def compose_context(prompt, demos, query, condition):
    """Exact legacy split-before-insertion recipe; only permission text changes."""
    need(condition in CONDITIONS, 'Unknown numerical condition')
    need(prompt.count(NO_TOOLS) == 1, 'Exact original permission sentence required')
    if condition == 'numeric_program_four_demo':
        prompt = prompt.replace(NO_TOOLS, PROGRAMME_TOOLS)
    need(prompt.count('{{demonstrations_json}}') == prompt.count('{{query_json}}') == 1,
         'Exactly one original prompt slot of each kind required')
    before_demo, rest = prompt.split('{{demonstrations_json}}')
    need('{{query_json}}' not in before_demo, 'Original prompt slot order required')
    before_query, after_query = rest.split('{{query_json}}')
    context = before_demo + demos + before_query + query + after_query
    need(len(context.encode('utf-8')) <= CONTEXT_LIMIT, 'Complete context exceeds cap; never truncate')
    return context


class PacketSession:
    """Operator-side authenticated index. Never provide this object to a solver."""

    def __init__(self, public_root, manifest_pin, budget=None):
        check_pin(manifest_pin, MANIFEST_LIMIT)
        root = Path(public_root).absolute()
        need(root.resolve(strict=True) == root, 'Packet root must resolve directly')
        self._root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self._closed = False
        self.manifest_pin = dict(manifest_pin)
        self._budget = budget
        try:
            manifest = decode(self._read('PACKET.json', manifest_pin))
            need(type(manifest) is dict and manifest.get('schema') == 'erp-core-full32-public-packet-v1', 'Full32 packet schema')
            need(manifest.get('benchmark_id') == 'NEURAL-077' and manifest.get('condition_id') == CONDITION_ID, 'Condition identity')
            need(type(manifest.get('people')) is int and manifest['people'] == 32 and
                 type(manifest.get('query_count')) is int and manifest['query_count'] == QUERY_COUNT and
                 type(manifest.get('demonstration_count')) is int and manifest['demonstration_count'] == 4 and
                 manifest.get('natural_class_prior_supplied') is False, 'Complete 6400/four-demo condition required')
            files = manifest.get('files')
            need(type(files) is dict, 'Pinned member inventory required')
            fixed = set(LEGACY_PINS) | {'roster.json'}
            shard_names = set(files) - fixed
            need(fixed <= set(files) and len(shard_names) == 32 and all(SHARD_RE.fullmatch(x) for x in shard_names),
                 'Exactly 32 opaque query shards and four fixed members required')
            for name, pin in files.items():
                check_pin(pin, SHARD_LIMIT if name in shard_names else ROSTER_LIMIT)
            need(all(files[name] == pin for name, pin in LEGACY_PINS.items()), 'Unchanged four demonstrations and original prompt/schema required')
            self._files = files
            self._demos = self._read('demonstrations.json', files['demonstrations.json']).decode('utf-8')
            self._prompt = self._read('prompt.txt', files['prompt.txt']).decode('utf-8')
            self._read('response_schema.json', files['response_schema.json'])
            roster = decode(self._read('roster.json', files['roster.json']))
            need(type(roster) is list and len(roster) == QUERY_COUNT, 'All 6400 roster rows required')
            rows = {}
            previous = ''
            spans = {name: [] for name in shard_names}
            for row in roster:
                need(type(row) is dict and set(row) == {'trial_id', 'path', 'offset', 'bytes', 'sha256'}, 'Exact public roster fields')
                identifier = row['trial_id']
                need(type(identifier) is str and ID_RE.fullmatch(identifier) and identifier > previous, 'Sorted unique opaque query IDs required')
                previous = identifier
                need(type(row['path']) is str and row['path'] in shard_names, 'Roster references only selected query shards')
                need(type(row['offset']) is int and row['offset'] >= 0 and type(row['bytes']) is int and
                     0 < row['bytes'] <= QUERY_LIMIT, 'Bounded exact query span')
                need(type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']), 'Query SHA256 required')
                need(row['offset'] + row['bytes'] <= files[row['path']]['bytes'], 'Query span inside declared shard')
                rows[identifier] = dict(row)
                spans[row['path']].append((row['offset'], row['bytes']))
            for name, intervals in spans.items():
                need(len(intervals) == 200, 'Each accepted source-person shard has all 200 admitted queries')
                position = 0
                for offset, length in sorted(intervals):
                    need(offset == position, 'Query spans must partition each shard without overlap or gaps')
                    position += length
                need(position == files[name]['bytes'], 'Complete declared query shard coverage')
            self._rows = rows
            self.trial_ids = tuple(rows)  # Trusted operator-only roster, never in context().
            # Check template semantics without opening any query or normalizing waveform text.
            compose_context(self._prompt, '', '', CONDITIONS[0])
            compose_context(self._prompt, '', '', CONDITIONS[1])
        except BaseException:
            self.close()
            raise

    def _open(self, relative, size):
        need(not self._closed, 'Packet session closed')
        if '/' in relative:
            need(SHARD_RE.fullmatch(relative), 'Only declared query path shape')
            directory, leaf = relative.split('/')
            parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self._root_fd)
            try:
                fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            finally:
                os.close(parent)
        else:
            need(relative in {'PACKET.json', 'demonstrations.json', 'prompt.txt', 'response_schema.json', 'roster.json'}, 'Known packet member required')
            fd = os.open(relative, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self._root_fd)
        try:
            ordinary(fd, size=size)
        except BaseException:
            os.close(fd)
            raise
        return fd

    def _read(self, relative, pin):
        fd = self._open(relative, pin['bytes'])
        try:
            before = identity(fd)
            if self._budget is not None:
                self._budget.input(pin['bytes'] + 1)
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                body = stream.read(pin['bytes'] + 1)
            need(descriptor(body) == pin and identity(fd) == before, 'Authenticated member changed or hash mismatch')
            return body
        finally:
            os.close(fd)

    def _query(self, trial_id):
        """Read exactly one authenticated query span; trusted operator only."""
        need(type(trial_id) is str and trial_id in self._rows, 'Unknown query ID')
        row = self._rows[trial_id]
        fd = self._open(row['path'], self._files[row['path']]['bytes'])
        try:
            before = identity(fd)
            if self._budget is not None:
                self._budget.input(row['bytes'])  # Exact selected span, never a whole shard.
            os.lseek(fd, row['offset'], os.SEEK_SET)
            chunks = []
            remaining = row['bytes']
            while remaining:
                block = os.read(fd, remaining)
                need(block, 'Truncated complete query')
                chunks.append(block)
                remaining -= len(block)
            body = b''.join(chunks)
            need(identity(fd) == before and descriptor(body) == {'bytes': row['bytes'], 'sha256': row['sha256']},
                 'Request waveform span changed or hash mismatch')
        finally:
            os.close(fd)
        need(body.endswith(b'\n') and body.count(b'\n') == 1, 'One complete canonical query line required')
        query = decode(body)
        need(type(query) is dict and set(query) == {'trial_id', 'channels'} and query['trial_id'] == trial_id, 'Query identity/projection mismatch')
        channels = query['channels']
        need(type(channels) is list and len(channels) == 2 and all(type(c) is list and len(c) == 1024 for c in channels), 'Complete two-channel 1024-sample query required')
        need(all(type(v) in (int, float) and math.isfinite(v) for c in channels for v in c), 'Finite numeric waveform values required')
        return body, query

    def query_record(self, trial_id):
        """Operator-only structured record, never a participant-facing payload.

        The viewer renders this record through its existing image projection.
        This accessor neither parses a composed prompt nor exposes source joins.
        """
        return self._query(trial_id)[1]

    def demonstration_records(self):
        """Independent structured copies of the same four authenticated demos."""
        need(not self._closed, 'Packet session closed')
        demos = decode(self._demos.encode('utf-8'))
        need(type(demos) is list and len(demos) == 4, 'Exactly four demonstrations')
        for row in demos:
            need(type(row) is dict and set(row) == {'trial_id', 'channels', 'target'} and
                 type(row['trial_id']) is str and type(row['target']) is int and
                 row['target'] in (0, 1), 'Exact labelled demonstration record')
            channels = row['channels']
            need(type(channels) is list and len(channels) == 2 and
                 all(type(c) is list and len(c) == 1024 for c in channels) and
                 all(type(v) in (int, float) and math.isfinite(v) for c in channels for v in c),
                 'Complete finite two-channel demonstration')
        need(len({row['trial_id'] for row in demos}) == 4, 'Unique demonstration identities')
        return demos

    def context(self, trial_id, condition):
        need(type(trial_id) is str and trial_id in self._rows, 'Unknown query ID')
        need(condition in CONDITIONS, 'Unknown numerical condition')
        body, _ = self._query(trial_id)
        # Parsing above validates only; compose with unchanged authenticated text.
        prompt = compose_context(self._prompt, self._demos, body.decode('utf-8'), condition)
        return {'trial_id': trial_id, 'condition': condition, 'prompt': prompt,
                'context_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest()}

    def close(self):
        if not getattr(self, '_closed', True):
            self._closed = True
            os.close(self._root_fd)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def parse_response(text, trial_id):
    need(type(text) is str and 0 < len(text.encode('utf-8')) <= RESPONSE_LIMIT, 'Bounded original UTF-8 response string')
    value = decode(text.encode('utf-8'))
    need(type(value) is dict and set(value) == {'trial_id', 'target_probability'}, 'Exact response fields')
    need(value['trial_id'] == trial_id, 'Response identity differs from attempted query')
    probability = value['target_probability']
    need(type(probability) in (int, float) and math.isfinite(probability) and 0 <= probability <= 1, 'Finite scalar probability in [0,1]; booleans forbidden')
    return float(probability)


def deadline_check(deadline):
    need(type(deadline) in (int, float) and math.isfinite(deadline) and time.monotonic() < deadline, 'Collector deadline expired')


def write_new(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(body)
        while view:
            written = os.write(fd, view)
            need(written > 0, 'Output write progress')
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def collect(session, condition, responses_path, output, deadline):
    """Freeze/validate all 6400 first responses; no targets, metrics or model calls."""
    need(condition in CONDITIONS, 'Unknown numerical condition')
    identifiers = tuple(session.trial_ids)
    need(len(identifiers) == QUERY_COUNT and len(set(identifiers)) == QUERY_COUNT and
         identifiers == tuple(sorted(identifiers)) and all(ID_RE.fullmatch(x) for x in identifiers), 'Complete authenticated 6400 roster required')
    expected = set(identifiers)
    output = Path(output).absolute()
    need(output.parent.resolve(strict=True) == output.parent, 'Fresh output parent must resolve directly')
    output.mkdir(mode=0o700, exist_ok=False)
    copied = {'bytes': 0, 'sha256': None, 'complete': False}
    try:
        deadline_check(deadline)
        source_fd = os.open(responses_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = ordinary(source_fd, cap=LEDGER_LIMIT)
            output_fd = os.open(output / 'attempts.jsonl', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            digest = hashlib.sha256()
            try:
                while True:
                    deadline_check(deadline)
                    block = os.read(source_fd, min(65536, LEDGER_LIMIT - copied['bytes'] + 1))
                    if not block:
                        break
                    need(copied['bytes'] + len(block) <= LEDGER_LIMIT, 'Attempt ledger byte cap')
                    view = memoryview(block)
                    while view:
                        written = os.write(output_fd, view)
                        need(written > 0, 'Attempt preservation write progress')
                        view = view[written:]
                    copied['bytes'] += len(block)
                    digest.update(block)
                os.fsync(output_fd)
            finally:
                os.close(output_fd)
                copied['sha256'] = digest.hexdigest()
            need(identity(source_fd) == before and copied['bytes'] == before[2], 'Original response ledger changed while copied')
            copied['complete'] = True
        finally:
            os.close(source_fd)
        values = {}
        with (output / 'attempts.jsonl').open('rb') as stream:
            while True:
                deadline_check(deadline)
                line = stream.readline(ENVELOPE_LIMIT + 1)
                if not line:
                    break
                need(len(line) <= ENVELOPE_LIMIT and line.endswith(b'\n'), 'Complete bounded attempt envelope')
                need(len(values) < QUERY_COUNT, 'More than 6400 responses')
                envelope = decode(line)
                need(type(envelope) is dict and set(envelope) == {'trial_id', 'condition', 'context_sha256', 'status', 'response', 'error'}, 'Exact response envelope fields')
                identifier = envelope['trial_id']
                need(type(identifier) is str and identifier in expected and identifier not in values, 'Unknown or duplicate attempted query')
                need(envelope['condition'] == condition and envelope['status'] == 'ok' and envelope['error'] is None, 'Failed or mixed-condition attempt; no partial admission')
                context = session.context(identifier, condition)
                need(envelope['context_sha256'] == context['context_sha256'], 'Response not bound to authenticated complete context')
                values[identifier] = parse_response(envelope['response'], identifier)
        need(set(values) == expected, 'All 6400 attempted query responses required')
        deadline_check(deadline)
        predictions = b''.join(encoded({'trial_id': i, 'target_probability': values[i]}) for i in identifiers)
        need(len(predictions) <= 2 * 1024**2, 'Prediction output cap')
        write_new(output / 'predictions.jsonl', predictions)
        receipt = {'schema': 'erp-core-full6400-response-admission-v1', 'status': 'complete_unscored_submission',
                   'condition_id': CONDITION_ID, 'condition': condition, 'responses': QUERY_COUNT,
                   'manifest_pin': session.manifest_pin, 'attempts': copied, 'predictions': descriptor(predictions),
                   'first_response_only': True, 'private_target_reads': 0, 'scoring_performed': False,
                   'transport_isolation_qualified': False, 'model_calls': 0, 'new_benchmarks': 0}
        write_new(output / 'COMPLETE.json', encoded(receipt))
        return receipt
    except BaseException as error:
        failure = {'schema': 'erp-core-full6400-response-admission-v1', 'status': 'incomplete_response_admission',
                   'condition_id': CONDITION_ID, 'condition': condition, 'attempts': copied,
                   'error_type': type(error).__name__, 'message': str(error)[:512],
                   'private_target_reads': 0, 'scoring_performed': False, 'first_responses_preserved': copied['complete'],
                   'no_selective_omission_or_retry': True, 'new_benchmarks': 0}
        write_new(output / 'FAILED.json', encoded(failure))
        raise


def main(argv=None):
    """CLI for a separately selected trusted operator; no grants or models implied."""
    import argparse
    import signal
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('collect')
    command.add_argument('--public-root', type=Path, required=True)
    command.add_argument('--manifest-bytes', type=int, required=True)
    command.add_argument('--manifest-sha256', required=True)
    command.add_argument('--condition', choices=CONDITIONS, required=True)
    command.add_argument('--responses', type=Path, required=True)
    command.add_argument('--output', type=Path, required=True)
    command.add_argument('--work-seconds', type=float, required=True)
    command.add_argument('--whole-seconds', type=float, required=True)
    args = parser.parse_args(argv)
    started = time.monotonic()
    timer_installed = False
    old_handler = None
    try:
        need(math.isfinite(args.work_seconds) and math.isfinite(args.whole_seconds) and
             0 < args.work_seconds and args.work_seconds + 5 <= args.whole_seconds <= 86400,
             'Finite work/whole deadlines with at least 5s cleanup margin required')
        pin = {'bytes': args.manifest_bytes, 'sha256': args.manifest_sha256}
        check_pin(pin, MANIFEST_LIMIT)
        def alarm(_signum, _frame):
            raise TimeoutError('Inner collector whole-operation alarm')
        old_handler = signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, args.whole_seconds)
        timer_installed = True
        with PacketSession(args.public_root, pin) as session:
            result = collect(session, args.condition, args.responses, args.output, started + args.work_seconds)
        print(json.dumps({'status': result['status'], 'responses': result['responses'],
                          'condition': args.condition, 'output': str(args.output),
                          'outer_owned_process_closure_required': True,
                          'private_target_reads': 0, 'model_calls': 0}, allow_nan=False))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({'status': 'collector_refused_or_incomplete', 'error_type': type(error).__name__,
                          'message': str(error)[:512], 'outer_owned_process_closure_required': True}, allow_nan=False), file=sys.stderr)
        return 2
    finally:
        if timer_installed:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)


if __name__ == '__main__':
    raise SystemExit(main())
