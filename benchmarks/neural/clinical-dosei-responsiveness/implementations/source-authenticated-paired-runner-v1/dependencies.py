"""Authenticate existing source roles before compilation; no data/runtime calls."""
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import types

SOURCES = {
    'host': ('source-paired-delivery-v1/host_projection.py', '35d71ffef64415fc89f7828a4377ef6516eccb0fd32e8fcad1b929f494891dd2'),
    'indexed': ('source-paired-packets-v1/indexed_windows.py', 'dcb95c883a84f9601964899471d1e446e2dfa5d9e8c0efce1c90082cfb3a9741'),
    'core': ('source-paired-packets-v1/paired_windows.py', '00b4358cbd834f6d9a443c5c553920561301c4bfe2910075743ff92556a878be'),
    'numeric_policy': ('source-eeg-numeric-v1/numeric_policy.py', '695022e90fb28deac0318b8c253bd66cc0b051155ac90746940951159b1997f5'),
    'viewer': ('source-signal-viewer-v1/trace_viewer.py', 'c65b111c76fea971963dab4ecab0850171fb10802ba1e9dc45f7b91bd1d9db79'),
    'controller': ('source-paired-controller-v1/controller.py', 'b33987ba18de4e9f5f092191abf81ed35b0816a3d2dd96449cc351d62c7d45d1'),
    'interface': ('source-paired-controller-v1/participant_interface.py', 'dd36989bf6e9f613e03f08944010a68f4d80db90d34b89f9ac60c76d9d7f0d7b'),
    'sealer': ('source-paired-controller-v1/sealed_predictions.py', '75c7584a7953278304275179308903f4f5831d4e333d897f84d77935486189ee'),
    'transport': ('source-paired-packets-v1/prediction_contract.py', '69fd0c85374240bba63fc212304b4af9882c8afee0ff8b7d0fbeea3e5b6ef048'),
    'terminal': ('source-terminal-mapping-v1/terminal_mapping.py', 'c3b6933d70d3ef377c7c160ffec65363ef29af78016b2125296c9a268ac5e179'),
    'target': ('source-zero-shot-scoring-v1/target_projection.py', '8cfb4f7af2792b8b688336e1d9146c8c2197fc83848d24c86ef6683276b51333'),
    'scorer': ('source-zero-shot-scoring-v1/scorer.py', 'e0c4be9ebbc10a88d9f49c0839a4a6b6c6471227d2a40fb31311948e22dbfada'),
    'code_backend': ('source-runtime-adapters-v1/docker_code_backend.py', '1a8d96d57e325db0aacd31f2abf8b92ba20de8821bf065aee6b6ef8a9ba3bd9a'),
    'code_policy': ('source-runtime-adapters-v1/docker_code_policy.py', '6d4d8e952042d6b7a9557ba8c035da80b557b1778ec9b551f55d6b45bbdd6412'),
    'command': ('source-runtime-adapters-v1/raw_command.py', '9c2285abdbca85075bf885a2cf40721d9be1ea843671e69ebf05ddc3a46a87a0'),
    'owned_process_v2': ('source-runtime-adapters-v1/owned_process_v2.py', 'afae111f8dec293391bbf077cd0d700e8061328d5541f5d116ade63c1cf7d219'),
}
DATA = {
    'terminal_policy': ('source-terminal-mapping-v1/policy.json', '82674ea847a74e7f4e3229f14cb7beac75a35d033d03451031c05a0695a4e4c3'),
    'scoring_policy': ('source-zero-shot-scoring-v1/policy.json', 'f3d8bc83cfd233fca3882b39a633354837216311a466a2b711056838ad170952'),
    'runtime_profile': ('source-runtime-adapters-v1/runtime_profile.json', 'c1830439a06254a982279604d645de5969c3444260e74262f7ad0efc7bc3129b'),
}


def _signature(value):
    return tuple(getattr(value, x) for x in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def source_bytes(path, pin):
    if not re.fullmatch('[0-9a-f]{64}', pin):
        raise ValueError('fixed role pin is malformed')
    if not path.is_absolute() or path.parent.resolve() != path.parent:
        raise ValueError('real absolute source directory required')
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= 65536:
            raise ValueError('bounded regular source required')
        raw = os.read(fd, 65537)
        if len(raw) != before.st_size or _signature(before) != _signature(os.fstat(fd)) or \
                _signature(before) != _signature(path.lstat()) or hashlib.sha256(raw).hexdigest() != pin:
            raise ValueError('role source identity differs')
        return raw
    finally:
        os.close(fd)


def load_dependencies(implementations_root, *, prefix):
    """At most nineteen small named source reads; no recursive discovery.

    This loader and new connector modules themselves require an authenticated
    caller bootstrap/source manifest. Authenticated modules remain trusted host
    objects, not a security boundary against host-side monkeypatching.
    """
    root = Path(implementations_root)
    if type(prefix) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,63}', prefix):
        raise ValueError('exact private module prefix required')
    modules, data, bindings = {}, {}, {}
    for role, (relative, pin) in {**SOURCES, **DATA}.items():
        path = root / relative
        raw = source_bytes(path, pin)
        bindings[role] = {'bytes': len(raw), 'sha256': pin, 'source': relative}
        if role in DATA:
            data[role] = raw
            continue
        name = prefix+'_'+role
        if name in sys.modules:
            raise ValueError('fresh source module namespace required')
        module = types.ModuleType(name)
        module.__file__ = str(path)
        sys.modules[name] = module
        exec(compile(raw, str(path), 'exec'), module.__dict__)
        modules[role] = module
    return modules, data, bindings
