"""One production source-bound validation. Run with isolated Python (-I -B).

No environment, CLI path or pin overrides; no authoring/mutation tests. Import is
inert. Parent binds BOOTSTRAP_SHA after reviewing the final adjacent bootstrap.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types


BOOTSTRAP_SHA = 'aca6f8b5f2e53db071678b43a122dab97ea3fd03d996933955e111a972dc228e'
MAX_BOOTSTRAP_BYTES = 1024**2


def _load_bootstrap():
    if type(BOOTSTRAP_SHA) is not str or re.fullmatch('[0-9a-f]{64}', BOOTSTRAP_SHA) is None:
        raise ValueError('unfrozen_bootstrap_pin')
    path = Path(__file__).absolute().parent / 'grader_bootstrap.py'
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or (part != path and not stat.S_ISDIR(info.st_mode)):
            raise ValueError('bootstrap_path')
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_BOOTSTRAP_BYTES:
        raise ValueError('bootstrap_regular_size')
    def signature(info):
        return info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        if signature(os.fstat(stream.fileno())) != signature(before): raise ValueError('bootstrap_changed')
        raw = stream.read(MAX_BOOTSTRAP_BYTES + 1)
        if signature(os.fstat(stream.fileno())) != signature(before): raise ValueError('bootstrap_changed')
    if signature(path.lstat()) != signature(before): raise ValueError('bootstrap_changed')
    if len(raw) != before.st_size or hashlib.sha256(raw).hexdigest() != BOOTSTRAP_SHA:
        raise ValueError('bootstrap_sha256')
    module = types.ModuleType('_devconn_scoring_bootstrap')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def _score(boot):
    """Explicit test seam; production supplies only the SHA-bound adjacent code."""
    private_dir = Path(boot.__file__).absolute().parent
    output = boot.disjoint_output(boot.OUTPUT_DIR, boot.DATA_DIR, boot.PUBLIC_DOCUMENTS.values(), private_dir)
    context = boot.load_private()
    reference = context['modules']['source_reference'].reconstruct(
        data_dir=boot.DATA_DIR, **context['documents'], pilot=False)
    result = context['modules']['validator'].validate_output_directory(output, reference)
    boot.recheck_documents(context)
    if type(result) is not dict or result.get('status') != 'ok':
        raise ValueError('validation_not_complete')
    return {'status': 'pass', 'task_id': 'DEVCONN-001'}


def score():
    if not sys.flags.isolated:
        raise ValueError('isolated_python_required')
    return _score(_load_bootstrap())


def main(argv=None):
    # Reject even positional arguments; production paths and pins are not user inputs.
    args = sys.argv[1:] if argv is None else argv
    if args:
        print(json.dumps({'status': 'fail', 'error_type': 'UnexpectedArguments'}))
        return 1
    try:
        result = score()
    except Exception as exc:
        print(json.dumps({'status': 'fail', 'error_type': type(exc).__name__}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
