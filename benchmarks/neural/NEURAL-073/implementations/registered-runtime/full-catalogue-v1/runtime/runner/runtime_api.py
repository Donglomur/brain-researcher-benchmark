"""Exact future-host NumPy admission, separate from the Mac engineering binding.

No package installation, source discovery or arbitrary computation backend. A
future root-selected native contract supplies actual host extension/metadata pins;
all algorithm/API Python source pins remain the tested NumPy2.4.6 identities.
Nothing in this source claims those future host/native evidence bodies exist.
"""
from pathlib import Path
import hashlib,importlib,importlib.metadata,json,sys
from ..core.custody import CustodyError,VerifiedAuthority,canonical,digest,require_digest

_ACTIVE=None
_EXTENSION_IMPORTS={'multiarray_extension':'numpy._core._multiarray_umath',
                    'linalg_extension':'numpy.linalg._umath_linalg',
                    'lapack_extension':'numpy.linalg.lapack_lite'}
_API_SOURCE_PINS={'api_source_0': {'path': 'numpy/__init__.py', 'bytes': 26277, 'sha256': '92a46f791e453926d3292af2582b89995a289475f0eaaea71a949823200b838a'}, 'api_source_1': {'path': 'numpy/version.py', 'bytes': 293, 'sha256': '833eb1051581de6bf4d23cd6f090e0fa4cbab6c548463dc718b5be62920fa2d7'}, 'api_source_2': {'path': 'numpy/linalg/_linalg.py', 'bytes': 114861, 'sha256': 'e47d0e2aed21361291cd6651999a59e6479ba5866abb8eabb1dbea5b0d1618ac'}, 'api_source_3': {'path': 'numpy/_core/_methods.py', 'bytes': 9393, 'sha256': '724facf7e63c5b8fcc2fac14bf31a02cb048d9e28f516d86502ba5077a425476'}, 'api_source_4': {'path': 'numpy/lib/_function_base_impl.py', 'bytes': 193738, 'sha256': 'b2310fd26d09b566bc50c94be4d3032866503c16a75a5ff67ae994a4a7aea7c9'}}
_CONSUMERS={'transforms/numeric.py': '68deb2bc97e1644f4d8590ed2bd98daf155e8df228e54f289614db45430a19f2', 'transforms/public_tools_v1/projection.py': 'cd8e5e25ba6b5757a2d225e7f6773be86bcc85d84d48ab97ca4636b631684b72'}
_ROLE_PREFIX={'multiarray_extension':'numpy/_core/_multiarray_umath.',
              'linalg_extension':'numpy/linalg/_umath_linalg.',
              'lapack_extension':'numpy/linalg/lapack_lite.'}


def numpy_api():
    if _ACTIVE is None:raise CustodyError('future native numerical runtime is not admitted')
    return _ACTIVE['numpy']


def activate(contract,*,authority,native_qualification_digest):
    global _ACTIVE
    if _ACTIVE is not None:raise CustodyError('native numerical runtime binding is single-use')
    if type(authority) is not VerifiedAuthority:raise CustodyError('verified authentic runtime admission required')
    require_digest(native_qualification_digest)
    required={'schema','package','version','python_major_minor','distribution_root','source_read_cap','pins'}
    if type(contract) is not dict or set(contract)!=required or contract['schema']!='n073_native_numpy_runtime_v1':
        raise CustodyError('closed explicit native numerical contract')
    if contract['package']!='numpy' or contract['version']!='2.4.6' or contract['python_major_minor']!=[3,11]:
        raise CustodyError('tested numerical API version must be preserved')
    if type(contract['source_read_cap']) is not int or contract['source_read_cap']<=0:
        raise CustodyError('explicit full native source read budget')
    root=Path(contract['distribution_root'])
    if not root.is_absolute() or '..' in root.parts:raise CustodyError('explicit canonical distribution root')
    pins=contract['pins']
    roles=set(_API_SOURCE_PINS)|set(_ROLE_PREFIX)|{'metadata','record'}
    if type(pins) is not dict or set(pins)!=roles:raise CustodyError('exact complete native API/source role set')
    total=0;paths=[]
    for role,pin in pins.items():
        if type(pin) is not dict or set(pin)!={'path','bytes','sha256'}:raise CustodyError('closed source pin')
        rel=Path(pin['path']);require_digest(pin['sha256'])
        if rel.is_absolute() or '..' in rel.parts or str(rel)!=pin['path'] or type(pin['bytes']) is not int or pin['bytes']<=0:
            raise CustodyError('exact relative regular source extent required')
        if role in _API_SOURCE_PINS and pin!=_API_SOURCE_PINS[role]:raise CustodyError('numerical algorithm/API source changed')
        if role in _ROLE_PREFIX and (not pin['path'].startswith(_ROLE_PREFIX[role]) or not pin['path'].endswith('.so')):
            raise CustodyError('wrong explicit native extension role')
        if role in ('metadata','record') and pin['path']!='numpy-2.4.6.dist-info/'+{'metadata':'METADATA','record':'RECORD'}[role]:
            raise CustodyError('wrong package metadata role')
        total+=pin['bytes'];paths.append(pin['path'])
    if len(paths)!=len(set(paths)) or total>contract['source_read_cap']:raise CustodyError('duplicate/overbudget runtime sources')
    bindings={'numerical_runtime_contract_digest':digest(contract),'native_qualification_digest':native_qualification_digest,
              'numerical_consumer_sources_digest':digest(_CONSUMERS)}
    authority.require(role='admission',domain='authentic',bindings=bindings)
    # Only now inspect the exact selected package/source paths. No authentic
    # neural headers, arrays, fitted states, credentials or results are opened.
    if tuple(sys.version_info[:2])!=(3,11) or root.resolve()!=root:raise CustodyError('host Python/path binding')
    dist=importlib.metadata.distribution('numpy')
    if dist.version!='2.4.6' or Path(dist.locate_file('')).resolve()!=root:raise CustodyError('host distribution identity')
    for pin in pins.values():
        p=root/pin['path']
        if p.resolve()!=p or not p.is_file() or p.stat().st_size!=pin['bytes']:raise CustodyError('native source path/extent')
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(65536),b''):h.update(b)
        if h.hexdigest()!=pin['sha256']:raise CustodyError('native source exact body hash')
    from ..transforms import numeric
    from ..transforms.public_tools_v1 import projection
    from ..transforms.dependency import numpy_api as original
    modules={'transforms/numeric.py':numeric,'transforms/public_tools_v1/projection.py':projection}
    base=Path(__file__).resolve().parent.parent
    for name,module in modules.items():
        if module.numpy_api is not original or hashlib.sha256((base/name).read_bytes()).hexdigest()!=_CONSUMERS[name]:
            raise CustodyError('frozen consumer changed or prior engineering runtime active')
    import numpy as np
    if np.__version__!='2.4.6' or Path(np.__file__).resolve()!=(root/'numpy/__init__.py').resolve():
        raise CustodyError('loaded numerical package differs from selected host')
    loaded_roles={}
    for role,name in _EXTENSION_IMPORTS.items():
        module=importlib.import_module(name)
        actual=Path(module.__file__).resolve()
        if actual!=(root/pins[role]['path']).resolve():
            raise CustodyError('loaded native extension differs from its exact authenticated role: '+role)
        loaded_roles[role]={'import_name':name,'path':str(actual),'sha256':pins[role]['sha256']}
    receipt={'loaded_extension_roles':loaded_roles,'contract_digest':digest(contract),'native_qualification_digest':native_qualification_digest,
             'actual_source_bytes_hashed':total,'authentic_admission_digest':authority.authority_digest,
             'algorithm_sources_preserved':True,'full_environment_evidence':'separate root-selected evidence, not inferred from hashing'}
    _ACTIVE={'numpy':np,'receipt':receipt,'domain':'authentic'}
    for module in modules.values():module.numpy_api=numpy_api
    return dict(receipt)


def require_domain(domain):
    if _ACTIVE is None or _ACTIVE['domain']!=domain:
        raise CustodyError('numerical runtime domain mismatch or unadmitted runtime')
    return dict(_ACTIVE['receipt'])


def activate_engineering(*,authority):
    """Only the exact selected real NumPy metadata successor, never a mock API.

    Invented capability cannot issue authentic reference execution. The separate
    authentic activation refuses any process already bound for engineering.
    """
    global _ACTIVE
    if _ACTIVE is not None:raise CustodyError('numerical runtime already activated')
    from . import runtime_binding
    receipt=runtime_binding.activate(authority=authority,domain='invented')
    _ACTIVE={'numpy':runtime_binding.numpy_api(),'domain':'invented',
             'receipt':{'contract_digest':receipt['runtime_binding_digest'],
                        'engineering_receipt':receipt,'authentic_qualification':False}}
    return dict(_ACTIVE['receipt'])
