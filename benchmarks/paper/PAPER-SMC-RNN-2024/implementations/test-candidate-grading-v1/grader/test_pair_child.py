"""One bounded child for both TEST reference/candidate scores; no inference owner."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import stat
import sys

HERE = Path(__file__).resolve().parent
CAP = 2 * 1024**2
THREAD_KEYS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS',
               'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS', 'OMP_THREAD_LIMIT')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(filename, expected=None):
    p = Path(filename)
    require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p, *p.parents)),
            'Exact unlinked source/metadata path required')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        a = os.fstat(f.fileno())
        require(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= CAP, 'Bounded source/metadata required')
        raw = f.read(CAP + 1); b, c = os.fstat(f.fileno()), p.lstat()
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
    require(len(raw) == a.st_size and all(getattr(a, k) == getattr(b, k) == getattr(c, k) for k in fields),
            'Stable complete source/metadata required')
    if expected is not None:
        require({'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                == {k: expected[k] for k in ('bytes', 'sha256')}, 'Exact selected source/metadata required')
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args(argv)
    # Set once for the WHOLE pair, before explicit site.main and numerical imports.
    # The retained -I -B host invocation also supplies Docker CPU/memory limits
    # from startup; this is not a claim of -S interpreter startup isolation.
    resource.setrlimit(resource.RLIMIT_CPU, (600, 605))
    require(resource.getrlimit(resource.RLIMIT_CPU) == (600, 605), 'Whole-child CPU limit installed')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    for key in THREAD_KEYS:
        os.environ[key] = '1'
    os.umask(0o022)
    sys.dont_write_bytecode = True
    raw = read(args.request)
    require(hashlib.sha256(raw).hexdigest() == args.sha256, 'Selected child request')
    request = json.loads(raw)
    selected = request['source']
    require(Path(selected['path']) == HERE / 'SOURCE.json', 'Exact adjacent adapter source')
    manifest = json.loads(read(selected['path'], selected))
    require(set(manifest) == {'schema', 'files', 'test_kernel'}
            and manifest['schema'] == 'smc_test_gain_grade_source_v1'
            and set(manifest['files']) == {'test_pair_child.py', 'test_pair_grade.py', 'scorer.py', 'reference_panel.json', 'gain_transform.py'},
            'Closed paired TEST source roster')
    read(HERE / 'test_pair_child.py', manifest['files']['test_pair_child.py'])
    adapter_raw = read(HERE / 'test_pair_grade.py', manifest['files']['test_pair_grade.py'])
    import site
    site.main()
    spec = importlib.util.spec_from_file_location('_smc_test_candidate_pair_score', HERE / 'test_pair_grade.py')
    adapter = importlib.util.module_from_spec(spec)
    exec(compile(adapter_raw, str(HERE / 'test_pair_grade.py'), 'exec'), adapter.__dict__)
    adapter.run(args.request, args.sha256)
    print(json.dumps({'schema': 'smc_test_gain_grade_child_completion_v1',
                      'report': str(Path(request['output_root']) / 'REPORT.json'),
                      'role': 'test_reference_candidate_gain_comparison', 'inference_executed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
