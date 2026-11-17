"""Task-specific source assembly; never prepare data or invent runtime authority."""
import hashlib
import json
import os
from pathlib import Path
import stat

HERE = Path(__file__).absolute().parent
MANIFEST_SHA256 = '11531abb506bd4939cc3d8474b58f84e7fb40a83c91fcafeb09d56a4893b6a52'
ENTRY = 'authoring/rtt-neural-forecast-v1/causal-runtime-v1/run_program.py'
SOURCE_BYTE_CAP = 2 * 1024 * 1024


def need(value, message):
    if not value:
        raise ValueError(message)


def path(value):
    p = Path(value).absolute()
    need('..' not in p.parts and all(not q.is_symlink() for q in (p, *p.parents)),
         'Canonical unlinked operator path')
    return p


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def read(value, cap, expected=None):
    p = path(value)
    fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'Bounded ordinary source or operator metadata')
        body = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
    need(len(body) == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(p.lstat(), k)
                                           for k in fields), 'Unchanged complete file')
    need(expected is None or pin(body) == expected, 'Selected source bytes')
    return body


def decode(body):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, 'Duplicate metadata field')
            value[key] = item
        return value
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite metadata')))


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def manifest():
    body = read(HERE / 'SOURCE_MANIFEST.json', 65536)
    need(pin(body)['sha256'] == MANIFEST_SHA256, 'Exact reviewed recovery manifest')
    value = decode(body)
    need(value['schema'] == 'neural024_causal_source_recovery_v2', 'Task-specific recovery schema')
    return value, pin(body)


def verify_sources(root, selected):
    """Capture all selected bodies, reject import shadows and existing bytecode."""
    root = path(root)
    need(root.is_dir(), 'Materialized source directory')
    allowed_files = set(selected['files']) | set(selected['external_closure_files'])
    allowed_dirs = {str(p) for name in allowed_files for p in Path(name).parents if str(p) != '.'}
    # This bounded tree is source only; do not traverse artifacts-build (targets,
    # historical receipts or candidate outputs). External named files are not read.
    pending = [root / 'authoring']
    visited = 0
    while pending:
        directory = pending.pop()
        for entry in directory.iterdir():
            visited += 1
            need(visited <= 256 and not entry.is_symlink(), 'Bounded unlinked source inventory')
            name = str(entry.relative_to(root))
            if entry.is_dir():
                need(name in allowed_dirs, 'No extra import/cache directory')
                pending.append(entry)
            else:
                need(name in allowed_files and entry.is_file(), 'No unselected source/import artifact')
    captured = {name: read(root / name, SOURCE_BYTE_CAP, expected)
                for name, expected in selected['files'].items()}
    need(sum(map(len, captured.values())) <= SOURCE_BYTE_CAP, 'Complete source byte allowance')
    return captured


def write_new(target, body):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def materialize(destination):
    selected, identity = manifest()
    captured = verify_sources(HERE / 'source', selected)
    target = path(destination)
    need(not os.path.lexists(target) and target.parent.is_dir(), 'Fresh operator source root')
    need(all(not (p / '.git').exists() for p in (target, *target.parents)), 'Operator root outside Git')
    target.mkdir(mode=0o700)
    written = 0
    # Failure leaves a visible partial directory; never overwrite or auto-retry.
    for name, body in captured.items():
        write_new(target / name, body)
        written += len(body)
    result = {'schema': 'neural024_materialized_source_v2', 'source_manifest': identity,
              'runtime_freeze': selected['runtime_freeze'], 'source_files': len(captured),
              'source_bytes': written, 'external_closure_files': selected['external_closure_files'],
              'original_payloads': selected['original_payloads'],
              'payloads_read_or_copied': 0, 'execution_authority': False,
              'runtime_qualified': False, 'scientific_qualified': False, 'automatic_retry': False}
    body = encode(result)
    write_new(target / 'MATERIALIZED.json', body)
    return {'source_files': len(captured), 'written_bytes': written + len(body),
            'receipt': pin(body), 'execution_authority': False}


def operator_source(root):
    selected, identity = manifest()
    root = path(root)
    need(all(not (p / '.git').exists() for p in (root, *root.parents)), 'Operator root outside Git')
    marker = decode(read(root / 'MATERIALIZED.json', 32768))
    need(marker['schema'] == 'neural024_materialized_source_v2'
         and marker['source_manifest'] == identity and marker['runtime_freeze'] == selected['runtime_freeze']
         and marker['execution_authority'] is False, 'Exact source materialization, never execution authority')
    return selected, verify_sources(root, selected)


def dispatch(root, review_path, remaining):
    selected, captured = operator_source(root)
    root = path(root)
    review_path = path(review_path)
    need(review_path.is_relative_to(root), 'Review inside selected operator root')
    raw = read(review_path, 65536)
    review = decode(raw)
    need(review.get('execution_authority') is True
         and review.get('decision') == 'authorize_one_neural024_causal_program_attempt'
         and review.get('control') == 'ordinary'
         and review.get('freeze_sha256') == selected['runtime_freeze']['sha256'],
         'Fresh explicit grant for the portable freeze')
    endpoint = review.get('operator_docker_host')
    need(type(endpoint) is str and endpoint.startswith('unix:///') and len(endpoint) <= 4096
         and not any(ord(c) <= 32 for c in endpoint), 'Explicit local Unix socket endpoint')
    socket = endpoint[len('unix://'):]
    need(str(Path(socket)) == socket and '..' not in Path(socket).parts, 'Canonical selected socket path')
    need(type(review.get('prior_known_seconds')) in (int, float) and review['prior_known_seconds'] >= 2800,
         'Preserved historical cost floor; original receipt/allocation joins still required')
    # Only the original source_gate will hash external receipts/score records and
    # decide actual authority. This preflight does not manufacture those records.
    environment = dict(os.environ)
    for key in tuple(environment):
        if key.startswith('DOCKER_') or key.startswith('NEURAL024_') or key in ('PYTHONPATH', 'PYTHONHOME'):
            environment.pop(key)
    environment.update(NEURAL024_DOCKER_HOST=endpoint, NEURAL024_REVIEW_SHA256=pin(raw)['sha256'],
                       PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
    argv = [str(root / ENTRY), '--control', 'ordinary', '--review', str(review_path), *remaining]
    return captured[ENTRY], argv, environment
