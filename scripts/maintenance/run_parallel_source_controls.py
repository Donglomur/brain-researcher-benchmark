#!/usr/bin/env python3
"""Run reviewed generated controls separately, with exact counts and no skips.

This trusted CI launcher is not a sandbox for untrusted participant code.
Repository source ownership and workflow pins must pass the prerequisite gate.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_LOG_BYTES = 4 * 1024 * 1024
MAX_COMMANDS = 598
MAX_SECONDS = 180
ARTIFACT_TOKEN = '${ARTIFACT_DIR}'
THREAD_ENV = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
              'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS',
              'POLARS_MAX_THREADS', 'RAYON_NUM_THREADS')
PROTECTED_ENV = set(THREAD_ENV) | {'PYTHONPATH','PYTHONHOME','PYTEST_ADDOPTS','PYTEST_PLUGINS',
    'PYTHONNOUSERSITE','PYTHONDONTWRITEBYTECODE','PYTEST_DISABLE_PLUGIN_AUTOLOAD',
    'PYTHONSTARTUP','PYTHONINSPECT','PYTHONBREAKPOINT'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


class ControlFailure(ValueError):
    """A command failed admission after its owned process cleanup completed."""


def relative(value):
    need(type(value) is str and value and '\\' not in value, 'relative path required')
    p = PurePosixPath(value)
    need(not p.is_absolute() and '..' not in p.parts and str(p) == value,
         'normalized relative path required')
    return p


def local(root, value, directory=False):
    p = root / relative(value)
    for part in (p, *p.parents):
        if part == root.parent:
            break
        need(not part.is_symlink(), 'symlink in control path: ' + value)
    need(p.is_dir() if directory else p.is_file(), 'missing control path: ' + value)
    need(p.resolve().is_relative_to(root.resolve()), 'control path escapes checkout')
    return p


def fingerprint(info):
    return (info.st_dev,info.st_ino,info.st_mode,info.st_nlink,info.st_size,
            info.st_mtime_ns,info.st_ctime_ns)


def bounded_json(path, limit=MAX_MANIFEST_BYTES):
    before = path.stat()
    need(stat.S_ISREG(before.st_mode) and before.st_size <= limit, 'bounded JSON required')
    with path.open('rb') as stream:
        raw = stream.read(before.st_size + 1)
    need(len(raw) == before.st_size and fingerprint(path.stat()) == fingerprint(before), 'JSON changed during read')
    return json.loads(raw)


def pinned_read(path, pin):
    need(type(pin.get('bytes')) is int and 0 <= pin['bytes'] <= 8*1024*1024,
         'bounded source pin required')
    before = path.stat()
    need(stat.S_ISREG(before.st_mode) and before.st_size == pin['bytes'], 'source size mismatch')
    with path.open('rb') as stream:
        raw = stream.read(pin['bytes'] + 1)
    need(len(raw) == pin['bytes'] and fingerprint(path.stat()) == fingerprint(before)
         and hashlib.sha256(raw).hexdigest() == pin['sha256'], 'source pin mismatch')
    return raw


def result_summary(output, runner, expected, expected_output=None):
    """Use the final framework summary; earlier expected-mutant failures may appear."""
    need(type(expected) is int and 0 < expected <= 10000, 'positive exact test count required')
    if runner == 'unittest':
        reports = list(re.finditer(r'^Ran (\d+) tests? in [^\n]+\n', output, re.MULTILINE))
        need(bool(reports), 'unittest produced no completed test summary')
        report = reports[-1]
        count = int(report.group(1))
        following = output[report.end():]
        statuses = re.findall(r'^(OK(?:\s+\([^\n]*\))?|FAILED\s*\([^\n]*\))\s*$', following, re.MULTILINE)
        need(len(statuses) == 1, 'ambiguous or absent final unittest outcome')
        need(statuses[0] == 'OK', 'unittest failed or skipped controls: ' + statuses[0])
    elif runner == 'pytest':
        reports = re.findall(r'^(?:=+\s*)?((?:\d+ (?:passed|failed|skipped|errors?|xfailed|xpassed|deselected)|no tests ran)[^\n]*?)(?:\s*=+)?$', output, re.MULTILINE)
        need(bool(reports), 'pytest produced no completed summary')
        summary = reports[-1]
        need(bool(re.match(r'\d+ passed\b',summary)), 'pytest final outcome is not a passing suite: '+summary)
        need(not re.search(r'\b(skipped|failed|error|errors|xfailed|xpassed|deselected)\b', summary),
             'pytest did not execute every required control: ' + summary)
        count = int(re.match(r'\d+', summary).group())
    elif runner == 'json-controls':
        need(type(expected_output) is dict and type(expected_output.get('controls')) is list,
             'exact JSON control result required')
        actual = json.loads(output)
        need(json.dumps(actual, sort_keys=True, allow_nan=False) ==
             json.dumps(expected_output, sort_keys=True, allow_nan=False),
             'JSON software control result mismatch')
        count = len(actual['controls'])
    else:
        raise ValueError('unknown test runner')
    need(count == expected, 'test count mismatch: expected %d, observed %d' % (expected, count))
    return {'tests': count, 'skips': 0, 'runner': runner}


def stop_group(process):
    """Only signal the new process session owned by this invocation."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=3)


def run_command(argv, cwd, environment, log, seconds):
    need(type(seconds) is int and 1 <= seconds <= MAX_SECONDS, 'bounded timeout required')
    started = time.monotonic()
    process = None
    reason = None
    with log.open('xb') as stream:
        try:
            process = subprocess.Popen(argv, cwd=cwd, env=environment,
                                       stdout=stream, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            while process.poll() is None:
                if time.monotonic() - started >= seconds:
                    reason = 'wall timeout'
                    break
                if log.stat().st_size > MAX_LOG_BYTES:
                    reason = 'log byte limit'
                    break
                time.sleep(0.05)
            if reason:
                stop_group(process)
            code = process.wait()
        finally:
            if process is not None:
                stop_group(process)
    if log.stat().st_size > MAX_LOG_BYTES:
        raise ControlFailure('log byte limit')
    output = log.read_text(errors='replace')
    if reason is not None:
        raise ControlFailure(reason)
    if code != 0:
        raise ControlFailure('control process exit %d; see %s' % (code, log.name))
    return output, time.monotonic() - started


def validate_document(document, group):
    need(type(document) is dict and document.get('schema') == 'parallel-source-controls/v1',
         'unsupported control manifest')
    entries = document.get('commands')
    need(type(entries) is list and 0 < len(entries) <= MAX_COMMANDS, 'bounded command list required')
    ids = [row.get('id') for row in entries]
    need(all(type(x) is str and re.fullmatch(r'[A-Za-z0-9_.-]+', x) for x in ids)
         and len(set(ids)) == len(ids), 'unique command IDs required')
    groups = document.get('groups')
    need(type(groups) is dict and group in groups, 'unknown environment group')
    selected = [row for row in entries if row.get('group') == group]
    need(bool(selected), 'empty environment group')
    for row in selected:
        need(row.get('runner') in {'unittest', 'pytest', 'json-controls'}, 'unknown test runner')
        need(type(row.get('expected_tests')) is int and row['expected_tests'] > 0,
             'positive expected tests required')
        need(row.get('expected_skips') == 0, 'required suites may not skip')
        if row['runner'] == 'json-controls':
            need(type(row.get('expected_output')) is dict and
                 type(row['expected_output'].get('controls')) is list and
                 len(row['expected_output']['controls']) == row['expected_tests'],
                 'exact JSON control count required')
        need(type(row.get('argv')) is list and row['argv'] and row['argv'][0] == '${PYTHON}'
             and all(type(a) is str and '\x00' not in a for a in row['argv']), 'Python argv required')
        need(type(row.get('test_paths')) is list and bool(row['test_paths']), 'source test paths required')
        relative(row['cwd'])
        for path in row['test_paths']:
            relative(path)
        need(type(row.get('timeout_seconds')) is int and 1 <= row['timeout_seconds'] <= MAX_SECONDS,
             'bounded timeout required')
        overrides=row.get('environment',{})
        need(type(overrides) is dict and all(type(k) is str and type(v) is str for k,v in overrides.items()),
             'string environment overrides required')
        need(not (set(overrides) & PROTECTED_ENV),'control environment overrides enforced invariant')
    return groups[group], selected


def bind_fixtures(document, selected, fixtures):
    specs = document.get('fixtures', {})
    paths = {}
    required = {f for row in selected for f in row.get('fixtures', [])}
    for identifier in sorted(required):
        need(fixtures is not None and identifier in specs, 'required source fixture unavailable: ' + identifier)
        spec = specs[identifier]
        path = local(fixtures.resolve(), spec['filename'])
        pinned_read(path, spec)
        paths['${FIXTURE:' + identifier + '}'] = str(path)
    values = [v for row in selected for v in row['argv'] + list(row.get('environment', {}).values())]
    for token in sorted({v for v in values if v.startswith('${FIXTURE_DIR:')}):
        need(token.endswith('}'), 'invalid fixture directory placeholder')
        identifier = token[len('${FIXTURE_DIR:'):-1]
        spec = document.get('fixture_directories', {}).get(identifier)
        need(type(spec) is dict and type(spec.get('members')) is list and bool(spec['members']),
             'exact fixture directory membership required')
        members = set(spec['members'])
        need(len(members) == len(spec['members']) and members <= required, 'fixture directory members unavailable')
        directory = local(fixtures.resolve(), spec['path'], directory=True)
        expected = set()
        for member in members:
            member_path = local(fixtures.resolve(), specs[member]['filename'])
            need(member_path.is_relative_to(directory), 'fixture directory member outside directory')
            expected.add(member_path)
        actual = set()
        for number, path in enumerate(directory.iterdir(),1):
            need(number <= 64, 'bounded fixture directory required')
            need(path.is_file() and not path.is_symlink(), 'flat regular fixture directory required')
            actual.add(path)
        need(actual == expected, 'fixture directory membership mismatch')
        paths[token] = str(directory)
    return paths


def run(root, manifest, group, output, fixtures=None):
    root = root.resolve()
    document = bounded_json(manifest)
    profile, selected = validate_document(document, group)
    need(sys.version.split()[0] == profile['python'], 'exact CI interpreter mismatch')
    expected = profile.get('packages', {})
    actual = {name: importlib.metadata.version(name) for name in expected}
    need(actual == expected, 'exact CI dependency versions mismatch')
    need(not output.exists() and not output.is_symlink(), 'fresh output directory required')
    need(not output.resolve().is_relative_to(root), 'control outputs must be outside checkout')
    inventory = bounded_json(root/'benchmarks/integrity/source-ownership.json', 8*1024*1024)
    pins = {r['path']: r for r in inventory['files']}
    fixture_paths = bind_fixtures(document, selected, fixtures)
    working_directories = {}
    for row in selected:
        for name in row['test_paths']:
            need(name in pins, 'test lacks current source ownership: ' + name)
            pinned_read(local(root, name), pins[name])
        for value in row['argv'] + list(row.get('environment', {}).values()):
            need(not value.startswith('/Users/') and not value.startswith('/home/'), 'private path in manifest')
            need('${' not in value or value == '${PYTHON}' or value in fixture_paths or value == ARTIFACT_TOKEN,
                 'unresolved command placeholder: ' + value)
        working_directories[row['id']] = local(root,row['cwd'],directory=True)
    for parent in (output, *output.parents):
        need(not parent.is_symlink(), 'symlink in output path')
    output.mkdir(mode=0o700, parents=True)
    environment = dict(os.environ)
    for name in ('PYTHONPATH','PYTHONHOME','PYTEST_ADDOPTS','PYTEST_PLUGINS'):
        environment.pop(name,None)
    environment.update({name:'1' for name in THREAD_ENV})
    environment.update({'PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1',
                        'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'})
    results = []
    failures = []
    for row in selected:
        # -u also applies under -I, unlike PYTHONUNBUFFERED. Keep nested mutant
        # stdout in actual order relative to the outer framework's stderr.
        substitutions = dict(fixture_paths)
        substitutions['${PYTHON}'] = sys.executable
        artifact = None
        if ARTIFACT_TOKEN in row['argv'] + list(row.get('environment', {}).values()):
            artifact = output / (row['id'] + '.artifacts')
            need(not artifact.exists() and not artifact.is_symlink(), 'fresh control artifacts required')
            # The task adapter creates this exact directory exclusively.
            substitutions[ARTIFACT_TOKEN] = str(artifact.resolve())
        argv = [sys.executable, '-u'] + [substitutions.get(x, x) for x in row['argv'][1:]]
        child_env = dict(environment)
        child_env.update({k:substitutions.get(v, v) for k,v in row.get('environment', {}).items()})
        started = time.monotonic()
        problem = None
        try:
            text, elapsed = run_command(argv, working_directories[row['id']], child_env,
                                        output/(row['id']+'.log'), row['timeout_seconds'])
        except ControlFailure as error:
            problem = error
        else:
            try:
                result = result_summary(text, row['runner'], row['expected_tests'], row.get('expected_output'))
            except ValueError as error:
                problem = error
        if problem is None:
            record = {'id':row['id'],'task_id':row['task_id'],**result,'wall_seconds':elapsed}
            results.append(record)
        else:
            record = {'id':row['id'],'task_id':row['task_id'],'status':'failed',
                      'error':str(problem),'log':row['id']+'.log',
                      'wall_seconds':time.monotonic()-started}
            failures.append(record)
        if artifact is not None:
            record['artifact_directory'] = artifact.name
        attempted = len(results)+len(failures)
        status = 'failed' if failures else ('passed' if attempted == len(selected) else 'running')
        (output/'results.json').write_text(json.dumps({'scope':'generated_software_controls_only',
            'scientific_qualification':False,'group':group,'status':status,
            'attempted':attempted,'completed':results,'failed':failures},indent=2)+'\n')
        print(json.dumps(record),flush=True)
    need(not failures, '%d of %d authenticated commands failed; see results.json' % (len(failures),len(selected)))
    return results


FIXTURE_HOSTS = frozenset({'raw.githubusercontent.com', 'physionet.org'})
# PhysioNet's authenticated RECORDS redirect identifies this one public object.
# It is a direct address exception, never a general S3 host or redirect rule.
FIXTURE_EXACT_URLS = frozenset({
    'https://physionet-open.s3.amazonaws.com/chbmit/1.0.0/RECORDS',
})
MAX_FIXTURE_FILES = 64
MAX_FIXTURE_BYTES = 2 * 1024 * 1024
FIXTURE_SECONDS = 180
REQUEST_SECONDS = 20
MAX_REDIRECTS = 3


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _relative(value):
    _require(type(value) is str and value and '\\' not in value, 'relative fixture filename required')
    path = PurePosixPath(value)
    _require(bool(path.parts) and not path.is_absolute() and '..' not in path.parts and str(path) == value,
             'normalized fixture filename required')
    return path


def _url(value):
    _require(type(value) is str and value.isascii() and not any(c.isspace() for c in value),
             'public HTTPS fixture URL required')
    parsed = urllib.parse.urlsplit(value)
    _require(parsed.scheme == 'https' and
             ((parsed.netloc in FIXTURE_HOSTS and parsed.hostname in FIXTURE_HOSTS)
              or value in FIXTURE_EXACT_URLS) and not parsed.fragment
             and parsed.username is None and parsed.password is None,
             'fixture URL host or credentials refused')
    return parsed


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def _remaining_timeout(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('source fixture wall deadline')
    return min(REQUEST_SECONDS, remaining)


def _read_response(response, limit, record, deadline):
    """Count every response byte returned, including failed and redirect bodies."""
    chunks = []
    digest = hashlib.sha256()
    total = 0
    try:
        while total < limit:
            _remaining_timeout(deadline)
            chunk = response.read1(min(16384, limit - total))
            if not chunk:
                break
            _require(type(chunk) is bytes and len(chunk) <= min(16384, limit - total),
                     'response reader exceeded requested bound')
            chunks.append(chunk)
            total += len(chunk)
            record['bytes_read'] = total
            digest.update(chunk)
    finally:
        record['body_sha256'] = digest.hexdigest()
    return b''.join(chunks)


def prepare_fixtures(root, document, group, destination):
    """Fetch one reviewed group's exact fixtures into a fresh external directory.

    This runs in a dedicated Unix CI process. The overall alarm bounds blocking
    network operations; request timeouts provide a shorter individual bound.
    No requests occur during manifest/destination validation. Response accounting
    records bytes returned to this reader, including error and redirect bodies.
    """
    root = Path(root).resolve()
    destination = Path(destination).absolute()
    _require(root.is_dir(), 'checkout root required')
    _require(not destination.exists() and not destination.is_symlink(), 'fresh fixture directory required')
    for parent in destination.parents:
        _require(not parent.is_symlink(), 'symlink in fixture destination')
    _require(not destination.resolve().is_relative_to(root), 'fixtures must stay outside checkout')
    _require(destination.parent.is_dir(), 'fixture destination parent must exist')
    _require(type(document) is dict and type(document.get('fixtures', {})) is dict,
             'fixture definitions required')
    specs = document.get('fixtures', {})
    _require(len(specs) <= MAX_FIXTURE_FILES, 'fixture file limit')
    commands = document.get('commands')
    _require(type(commands) is list and len(commands) <= MAX_COMMANDS, 'bounded fixture commands required')
    selected = [row for row in commands if type(row) is dict and row.get('group') == group]
    _require(bool(selected), 'unknown fixture group')
    required = set()
    for row in selected:
        ids = row.get('fixtures', [])
        _require(type(ids) is list and all(type(x) is str for x in ids), 'fixture IDs required')
        required.update(ids)
    _require(required <= specs.keys(), 'missing fixture definition')
    names = set()
    expected_total = 0
    for identifier in sorted(required):
        _require(re.fullmatch(r'[A-Za-z0-9_.-]+', identifier), 'normalized fixture ID required')
        spec = specs[identifier]
        _require(type(spec) is dict, 'fixture pin required')
        path = _relative(spec.get('filename'))
        _require(path.parts[0] != 'acquisition-receipt.json' and str(path) not in names,
                 'duplicate or reserved fixture filename')
        names.add(str(path))
        _url(spec.get('url'))
        _require(type(spec.get('bytes')) is int and 0 < spec['bytes'] <= MAX_FIXTURE_BYTES,
                 'bounded positive fixture size required')
        _require(type(spec.get('sha256')) is str and re.fullmatch(r'[0-9a-f]{64}', spec['sha256']),
                 'exact fixture digest required')
        expected_total += spec['bytes']
    _require(expected_total < MAX_FIXTURE_BYTES, 'fixture byte limit including sentinel headroom')
    _require(not any(str(parent) in names for name in names for parent in PurePosixPath(name).parents),
             'fixture file/directory conflict')
    _require(hasattr(signal, 'setitimer') and signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0),
             'dedicated Unix fixture process required')

    destination.mkdir(mode=0o700)
    receipt = {'schema': 'source-fixture-acquisition/v1', 'group': group,
               'scope': 'public_source_for_generated_controls_only',
               'scientific_qualification': False, 'status': 'failed',
               'response_bytes_read': 0, 'responses': [], 'files': []}
    deadline = time.monotonic() + FIXTURE_SECONDS
    previous_handler = signal.getsignal(signal.SIGALRM)

    def wall_timeout(signum, frame):
        raise TimeoutError('source fixture wall deadline')

    try:
        signal.signal(signal.SIGALRM, wall_timeout)
        signal.setitimer(signal.ITIMER_REAL, FIXTURE_SECONDS)
        # Explicitly omit environment proxy settings and ambient credentials.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        for identifier in sorted(required):
            spec = specs[identifier]
            current = spec['url']
            original_host = _url(current).hostname
            for redirect_number in range(MAX_REDIRECTS + 1):
                request = urllib.request.Request(current, headers={'User-Agent': 'source-controls-fixtures/1',
                                                                  'Accept': 'application/octet-stream'})
                record = {'id': identifier, 'url': current, 'bytes_read': 0, 'status': None}
                receipt['responses'].append(record)
                response = None
                try:
                    try:
                        response = opener.open(request, timeout=_remaining_timeout(deadline))
                    except urllib.error.HTTPError as error:
                        response = error
                    record['status'] = response.code
                    record['fetched_url'] = response.geturl()
                    _require(record['fetched_url'] == current, 'implicit redirect refused')
                    remaining = MAX_FIXTURE_BYTES - receipt['response_bytes_read']
                    _require(remaining > 0, 'fixture acquisition byte limit')
                    # The one-byte sentinel remains inside the global acquisition cap.
                    limit = min(spec['bytes'] + 1, remaining)
                    body = _read_response(response, limit, record, deadline)
                except BaseException as error:
                    record['error'] = type(error).__name__ + ': ' + str(error)
                    raise
                finally:
                    receipt['response_bytes_read'] += record['bytes_read']
                    if response is not None:
                        response.close()
                if record['status'] in (301, 302, 303, 307, 308):
                    _require(redirect_number < MAX_REDIRECTS, 'fixture redirect limit')
                    _require(len(body) < limit, 'redirect body limit')
                    location = response.headers.get('Location')
                    _require(type(location) is str, 'redirect location required')
                    following = urllib.parse.urljoin(current, location)
                    _require(_url(following).hostname == original_host, 'cross-host fixture redirect refused')
                    current = following
                    continue
                _require(record['status'] == 200, 'fixture HTTP response failed')
                _require(len(body) == spec['bytes'] and hashlib.sha256(body).hexdigest() == spec['sha256'],
                         'fixture byte or digest mismatch')
                # A sentinel may be truncated by the global cap only when exactly
                # all remaining bytes form this expected file; require EOF then.
                _require(limit > spec['bytes'], 'fixture acquisition requires sentinel headroom')
                target = destination / spec['filename']
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(body)
                receipt['files'].append({'id': identifier, 'filename': spec['filename'],
                                         'bytes': len(body), 'sha256': spec['sha256'], 'fetched_url': current})
                break
        receipt['status'] = 'succeeded'
        return receipt
    except BaseException as error:
        receipt['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        with (destination / 'acquisition-receipt.json').open('x', encoding='utf-8') as stream:
            json.dump(receipt, stream, indent=2)
            stream.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--group',required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--fixtures',type=Path)
    parser.add_argument('--prepare-fixtures',action='store_true')
    args=parser.parse_args()
    try:
        if args.prepare_fixtures:
            need(args.fixtures is not None, 'fixture destination required')
            document = bounded_json(args.manifest)
            validate_document(document,args.group)
            prepare_fixtures(args.root,document,args.group,args.fixtures)
        else:
            need(args.output is not None, 'output destination required')
            run(args.root,args.manifest,args.group,args.output,args.fixtures)
    except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError) as error:
        print('parallel controls refused: '+str(error),file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
