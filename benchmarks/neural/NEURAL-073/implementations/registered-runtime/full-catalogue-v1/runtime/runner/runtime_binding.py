"""Explicit metadata-only NumPy contract successor, never an unchecked backend.

Original frozen module bodies and original failed invocation remain unchanged.
Only the two named consumer globals are bound to this same concrete NumPy API
verifier, after exact old consumer and new contract authentication. No caller can
supply a learning implementation, callable or arbitrary import/module name.
"""
from pathlib import Path
from functools import lru_cache
import hashlib,importlib.metadata,json,sys
from ..core.custody import CustodyError,VerifiedAuthority,digest

_ROOT=Path(__file__).resolve().parent.parent
_ACTIVE=False
_ATTEMPTED=False
_ACTUAL_RECORD=None
# Pins are completed by the source-freeze builder, never derived from untrusted input.
CONTRACT_SHA256='4d299c47e4b4c71e25386466efecbacc6de2745ef021d3912ec5f8d0170a4b14'
CONSUMER_PINS={'transforms/numeric.py': '68deb2bc97e1644f4d8590ed2bd98daf155e8df228e54f289614db45430a19f2', 'transforms/public_tools_v1/projection.py': 'cd8e5e25ba6b5757a2d225e7f6773be86bcc85d84d48ab97ca4636b631684b72'}

@lru_cache(maxsize=1)
def numpy_api():
    global _ACTUAL_RECORD
    if not _ACTIVE:raise CustodyError('explicit metadata successor is not selected/activated')
    body=(_ROOT/'runtime-metadata-successor-v2/NUMPY_API_CONTRACT.json').read_bytes()
    if hashlib.sha256(body).hexdigest()!=CONTRACT_SHA256:raise CustodyError('metadata successor contract pin')
    c=json.loads(body)
    if tuple(sys.version_info[:2])!=tuple(c['python_major_minor']):raise CustodyError('numerical Python API version')
    dist=importlib.metadata.distribution(c['package'])
    if dist.version!=c['version']:raise CustodyError('numerical package version')
    root=Path(dist.locate_file('')).resolve()
    for p in c['source_pins']:
        path=root/p['relative_distribution_root_path']
        if path.resolve()!=path or not path.is_file() or path.stat().st_size!=p['bytes']:
            raise CustodyError('exact successor numerical source extent/path')
        h=hashlib.sha256()
        with path.open('rb') as f:
            for b in iter(lambda:f.read(65536),b''):h.update(b)
        if h.hexdigest()!=p['sha256']:raise CustodyError('exact successor numerical body hash')
    # The nine numerical/API/METADATA pins above remain single exact identities.
    # Only RECORD has two explicitly selected known packaging metadata bodies.
    path=root/c['record_path']
    if path.resolve()!=path or not path.is_file():raise CustodyError('exact RECORD metadata path')
    size=path.stat().st_size
    alternatives=[x for x in c['record_alternatives'] if x['bytes']==size]
    if not alternatives:raise CustodyError('unselected RECORD extent; no retry or fallback')
    h=hashlib.sha256();count=0
    with path.open('rb') as f:
        before=f.fileno()
        import os
        initial=os.fstat(before)
        for b in iter(lambda:f.read(65536),b''):
            count+=len(b)
            if count>size:raise CustodyError('RECORD changed during exact read')
            h.update(b)
        final=os.fstat(before)
    if (count!=size or (initial.st_dev,initial.st_ino,initial.st_size,initial.st_mtime_ns,initial.st_ctime_ns)!=(final.st_dev,final.st_ino,final.st_size,final.st_mtime_ns,final.st_ctime_ns)):
        raise CustodyError('RECORD changed during exact read')
    actual={'bytes':count,'sha256':h.hexdigest()}
    if actual not in c['record_alternatives']:raise CustodyError('unselected RECORD body; no retry or fallback')
    _ACTUAL_RECORD=actual
    import numpy as np
    if np.__version__!=c['version'] or Path(np.__file__).resolve()!=(root/'numpy/__init__.py').resolve():
        raise CustodyError('numerical imported identity')
    return np


def binding_digest():
    return digest({'contract_sha256':CONTRACT_SHA256,'consumer_pins':CONSUMER_PINS,
                   'algorithm_change':False,'metadata_delta':'two explicitly selected known NumPy RECORD bodies only'})


def activate(*,authority,domain):
    global _ACTIVE,_ATTEMPTED
    if _ACTIVE or _ATTEMPTED:raise CustodyError('numerical binding activation is single-use')
    if type(authority) is not VerifiedAuthority:raise CustodyError('verified exact runtime binding required')
    authority.require(role='admission',domain=domain,bindings={'runtime_binding_digest':binding_digest()})
    from ..transforms import numeric
    from ..transforms.public_tools_v1 import projection
    from ..transforms.dependency import numpy_api as original
    modules={'transforms/numeric.py':numeric,'transforms/public_tools_v1/projection.py':projection}
    if set(CONSUMER_PINS)!=set(modules):raise CustodyError('closed consumer source allowlist')
    for name,module in modules.items():
        b=(_ROOT/name).read_bytes()
        if hashlib.sha256(b).hexdigest()!=CONSUMER_PINS[name] or module.numpy_api is not original:
            raise CustodyError('consumer source/global changed before selected binding')
    _ATTEMPTED=True
    _ACTIVE=True
    try:np=numpy_api()
    except BaseException:
        _ACTIVE=False
        raise
    for module in modules.values():module.numpy_api=numpy_api
    return {'runtime_binding_digest':binding_digest(),'numpy_version':np.__version__,
            'preserved_original_body_files':tuple(modules),'source_verified':True,
            'actual_record_identity':dict(_ACTUAL_RECORD),'single_exact_numerical_source_pins':9,
            'native_full_environment_qualified':False}
