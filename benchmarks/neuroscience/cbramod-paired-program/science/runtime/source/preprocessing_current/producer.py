"""Path-only compilation and real execution of pinned CBraMod raw producers.

Import/compile/staging is stdlib-only. dispatch is the separate native operator
preparation entry point; this source checkpoint does not invoke it or qualify
raw data, scientific parity, resource sufficiency or external execution rights.
"""
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

HERE = Path(__file__).absolute().parent
CATALOG_PIN = (23114, '254da40f7cd689129dcf08e7d5bf893bb4841903ecb105741cde00dc49d4852a')
SOURCE_LIMIT = 1048576


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def _pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def _read(path, expected):
    path = Path(path).absolute()
    for p in (path, *path.parents):
        if p.is_symlink():
            raise ValueError('symlink in source/staged owner')
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 <= before.st_size <= SOURCE_LIMIT:
        raise ValueError('not a bounded ordinary source file')
    with open(path, 'rb') as f:
        body = f.read(SOURCE_LIMIT + 1)
        observed = os.fstat(f.fileno())
    after = path.stat()
    key = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
    if key(before) != key(observed) or key(before) != key(after) or _pin(body) != expected:
        raise ValueError('source identity changed')
    body.decode('utf-8')
    if b'\0' in body:
        raise ValueError('non-text source')
    return body


def catalog():
    return json.loads(_read(HERE / 'PRODUCER_CATALOG.json', dict(zip(('bytes', 'sha256'), CATALOG_PIN))))


def dataset_spec(dataset_id):
    for row in catalog()['datasets']:
        if row['id'] == dataset_id:
            return row
    raise ValueError('unknown dataset')


def _binding_path(value):
    if not isinstance(value, str) or not value.startswith('/') or any(c in value for c in ('\0', '\n', '\r')):
        raise ValueError('bindings must be explicit absolute paths')
    if '..' in Path(value).parts or str(Path(value)) != value or value == '/':
        raise ValueError('bindings must be normalized non-root absolute paths')
    return value


def compile_producer(dataset_id, stage, bindings, official_root):
    """Return executable exact-source body with only declared path constants changed.

    Does not inspect raw directories/headers or import the native producer. TUAB
    retains its original private writable raw_workspace/process_refine layout.
    TUEV retains its official cp stage; filenames still require external safe
    staging, and no shell safety claim is inferred from path validation alone.
    """
    spec = dataset_spec(dataset_id)
    if stage not in spec['stages']:
        raise ValueError('unknown source stage')
    selected = spec['stages'][stage]
    required = {r['binding'] for r in selected['relocations']}
    if not isinstance(bindings, dict) or set(bindings) != required:
        raise ValueError('supply every exact stage binding, no extra roots')
    bindings = {k: _binding_path(v) for k, v in bindings.items()}
    if len(set(bindings.values())) != len(bindings):
        raise ValueError('distinct producer operands cannot share a path')
    if dataset_id == 'TUEV' and any(not re.fullmatch(r'/[A-Za-z0-9_./-]+', x) for x in bindings.values()):
        raise ValueError('official unquoted cp requires shell-safe workspace paths')
    original = selected['source']
    source = _read(Path(official_root) / original['path'], {k: original[k] for k in ('bytes', 'sha256')})
    tree = ast.parse(source)
    replacements = {r['original']: str(Path(bindings[r['binding']]) / r['suffix']) if r['suffix'] else bindings[r['binding']] for r in selected['relocations']}
    counts = {k: 0 for k in replacements}
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    edits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in replacements:
            counts[node.value] += 1
            value = replacements[node.value]
            edits.append((offsets[node.lineno-1] + node.col_offset, offsets[node.end_lineno-1] + node.end_col_offset, repr(value).encode()))
            node.value = value
    if counts != {r['original']: r['occurrences'] for r in selected['relocations']}:
        raise ValueError('official path occurrence count changed')
    compiled = source
    for start, end, body in sorted(edits, reverse=True):
        compiled = compiled[:start] + body + compiled[end:]
    if ast.dump(tree, include_attributes=False) != ast.dump(ast.parse(compiled), include_attributes=False):
        raise ValueError('relocation changed non-path source semantics')
    files = {'producer.py': compiled.decode('utf-8')}
    for auxiliary in selected['auxiliary']:
        files[auxiliary['output']] = _read(Path(official_root) / auxiliary['path'], {k: auxiliary[k] for k in ('bytes', 'sha256')}).decode('utf-8')
    metadata = {'schema': 'cbramod_compiled_producer_v1', 'dataset_id': dataset_id, 'stage': stage,
                'official_commit': catalog()['official_commit'], 'source': original,
                'bindings': bindings, 'relocations': selected['relocations'],
                'source_files': {name: _pin(body.encode()) for name, body in files.items()},
                'entrypoint': 'producer.py', 'paper_parity_holds': spec['paper_parity_holds'],
                'scientific_transformations_changed': False, 'source_parity_qualified': False}
    return {'metadata': metadata, 'identity': identity(metadata), 'files': files}


def _validate_plan(plan):
    if not isinstance(plan, dict) or set(plan) != {'metadata', 'identity', 'files'}:
        raise ValueError('compiled producer schema')
    if identity(plan['metadata']) != plan['identity']:
        raise ValueError('compiled producer identity mismatch')
    if {n: _pin(b.encode()) for n, b in plan['files'].items()} != plan['metadata']['source_files']:
        raise ValueError('compiled producer file mismatch')
    if plan['metadata']['entrypoint'] != 'producer.py' or 'producer.py' not in plan['files']:
        raise ValueError('compiled producer entrypoint')
    for name, body in plan['files'].items():
        if name not in ('producer.py', 'edf_.py') or not isinstance(body, str) or len(body.encode()) > SOURCE_LIMIT:
            raise ValueError('unexpected or oversized compiled source')
    # Rebuild from the selected, byte-pinned official tree. Self-consistent
    # caller hashes alone cannot establish that this is the selected producer.
    metadata = plan['metadata']
    authoritative = compile_producer(metadata['dataset_id'], metadata['stage'],
                                     metadata['bindings'], HERE.parent / 'official')
    if plan != authoritative:
        raise ValueError('compiled producer differs from authoritative official compilation')


def stage_producer(plan, work_dir):
    """Create a private executable text bundle; never run its native imports."""
    _validate_plan(plan)
    root = Path(_binding_path(str(work_dir)))
    for parent in root.parents:
        if parent.is_symlink():
            raise ValueError('symlink in stage owner')
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, body in plan['files'].items():
        with open(root / name, 'xb') as f:
            f.write(body.encode())
    metadata = dict(plan['metadata'])
    metadata['identity'] = plan['identity']
    encoded = json.dumps(metadata, sort_keys=True, indent=2).encode() + b'\n'
    with open(root / 'STAGED_PRODUCER.json', 'xb') as f:
        f.write(encoded)
    return {'work_dir': str(root), 'metadata_pin': _pin(encoded), 'identity': plan['identity']}


def dispatch(staged, python_executable, timeout_seconds, maximum_log_bytes, execution):
    """Real future native dispatcher with a single deadline and bounded log.

    `execution` selects native operator preparation, not a permission protocol.
    Resource ownership/cgroup/dataset-size admission belongs to the caller; this
    subprocess helper does not claim a scientific-data or sandbox qualification.
    """
    if execution != 'native_operator_preparation':
        raise ValueError('dispatch is native operator preparation only')
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError('explicit positive finite time allocation required')
    if type(maximum_log_bytes) is not int or not 1 <= maximum_log_bytes <= SOURCE_LIMIT:
        raise ValueError('explicit positive bounded log allocation required')
    executable = _binding_path(python_executable)
    root = Path(_binding_path(staged['work_dir']))
    metadata = json.loads(_read(root / 'STAGED_PRODUCER.json', staged['metadata_pin']))
    identifier = metadata.pop('identity')
    if identifier != staged['identity'] or identity(metadata) != identifier:
        raise ValueError('staged producer metadata mismatch')
    if set(p.name for p in root.iterdir()) != set(metadata['source_files']) | {'STAGED_PRODUCER.json'}:
        raise ValueError('stage owner contains undeclared members')
    captured_files = {}
    for name, expected in metadata['source_files'].items():
        if name not in ('producer.py', 'edf_.py'):
            raise ValueError('unexpected stage member')
        captured_files[name] = _read(root / name, expected).decode('utf-8')
    _validate_plan({'metadata': metadata, 'identity': identifier, 'files': captured_files})
    from benchmark.native.process import run_process
    result = run_process([executable, '-B', str(root / 'producer.py')],
                         cwd=root, timeout_seconds=timeout_seconds,
                         maximum_log_bytes=maximum_log_bytes)
    return {'schema': 'cbramod_producer_execution_v1', 'producer_identity': identifier,
            'returncode': result['returncode'], 'log': result['log'],
            'log_bytes': result['log_bytes'], 'elapsed_seconds': result['elapsed_seconds'],
            'cleanup': result['cleanup'],
            'source_parity_qualified': False,
            'output_qualification': 'requires complete authentic inventory and row lineage; execution exit is not qualification'}
