"""Independent NEURAL-079 sample-space reference; source-only, no I/O or study driver.

Input arrays are caller-owned real binary64. Limits count conservative owned float
slots, not Python/BLAS memory. PreparedFeature is explicit state, never a cache.
"""
import hashlib
import json
import math
from collections.abc import Mapping
from types import MappingProxyType
import numpy as np

EPS = 2.0 ** -52
TINY = float(np.finfo(np.float64).tiny)
FRACTIONS = ('0.80', '0.95', '0.99', 'all')
LAMBDAS = tuple('1e' + str(k) for k in range(-6, 4))
TEMPLATES = ('all17', 'early7', 'late10', 'avgpool', 'classifier')
MEMBERS = {'all17': tuple(range(17)), 'early7': tuple(range(7)),
           'late10': tuple(range(7, 17)), 'avgpool': (15,), 'classifier': (16,)}
LIMIT_KEYS = ('max_rows', 'max_query_rows', 'max_columns',
              'max_matrix_elements', 'max_live_float_slots')


class NumericError(ValueError):
    """Typed refusal; code is stable, detail is diagnostic text."""
    def __init__(self, code, detail=''):
        self.code, self.detail = code, detail
        super().__init__(code + (': ' + detail if detail else ''))


def _fail(code, detail=''):
    raise NumericError(code, detail)


def _array(x, name, ndim=2):
    if not isinstance(x, np.ndarray) or x.dtype != np.dtype('float64'):
        _fail('dtype', name + ' must already be an ndarray of real binary64')
    if x.ndim != ndim or any(k < 1 for k in x.shape):
        _fail('shape', name)
    # Constant-space finite scan. No input-sized boolean mask is allocated
    # before the caller's selected extent check. The iterator needs at most
    # one scalar at a time, including for strided arrays.
    for scalar in x.flat:
        if not math.isfinite(float(scalar)):
            _fail('nonfinite', name)
    return x


def _bound(limits, *, n=0, m=0, d=0, matrices=(), live=0, optional=False):
    if limits is None:
        if optional:
            return {'owned_float_slots_upper': live, 'extent_assured': False}
        _fail('limits_required')
    if not isinstance(limits, Mapping) or set(limits) != set(LIMIT_KEYS):
        _fail('limits_schema')
    for k in LIMIT_KEYS:
        if isinstance(limits[k], bool) or not isinstance(limits[k], int) or limits[k] < 1:
            _fail('limits_schema', k)
    for actual, key in ((n, 'max_rows'), (m, 'max_query_rows'), (d, 'max_columns'),
                        (live, 'max_live_float_slots')):
        if actual > limits[key]:
            _fail('extent', key)
    if any(x > limits['max_matrix_elements'] for x in matrices):
        _fail('extent', 'max_matrix_elements')
    return {'owned_float_slots_upper': live, 'extent_assured': True}


def _finite(x, label):
    if not math.isfinite(float(x)):
        _fail('nonfinite_result', label)
    return float(x)


def _product(values, label, *, denominator=1.0):
    """Multiply without avoidable intermediate overflow; refuse lost positives."""
    if not math.isfinite(denominator) or denominator <= 0:
        _fail('denominator', label)
    if any(v == 0 for v in values):
        return 0.0
    mantissa, exponent = 1.0, 0
    for v in values:
        m, e = math.frexp(float(v))
        mantissa *= m
        a, b = math.frexp(mantissa)
        mantissa, exponent = a, exponent + e + b
    divisor_mantissa, divisor_exponent = math.frexp(float(denominator))
    mantissa /= divisor_mantissa
    exponent -= divisor_exponent
    try:
        value = math.ldexp(mantissa, exponent)
    except OverflowError:
        _fail('overflow', label)
    if value == 0:
        _fail('underflow', label)
    return _finite(value, label)


def _ratio(a, b, label, allow_zero=True):
    if b <= 0 or not math.isfinite(b):
        _fail('denominator', label)
    if a == 0:
        if allow_zero:
            return 0.0
        _fail('underflow', label)
    ma, ea = math.frexp(float(a))
    mb, eb = math.frexp(float(b))
    try:
        out = math.ldexp(ma / mb, ea - eb)
    except OverflowError:
        _fail('overflow', label)
    if out == 0:
        _fail('underflow', label)
    return _finite(out, label)


def _fsum(values, label):
    try:
        return _finite(math.fsum(values), label)
    except OverflowError:
        _fail('overflow', label)


def _norm(a):
    scale = max((abs(float(v)) for v in a.flat), default=0.0)
    if scale == 0:
        return 0.0
    return _product((scale, math.sqrt(_fsum(((float(v) / scale) ** 2 for v in a.flat), 'norm'))), 'norm')


def moments(values, *, limits=None):
    x = _array(values, 'values')
    n, d = x.shape
    _bound(limits, n=n, d=d, matrices=(n*d,), live=4*d+3*n, optional=True)
    mean, variance, scale = (np.empty(d, dtype=np.float64) for _ in range(3))
    constant = np.empty(d, dtype=np.bool_)
    for j in range(d):
        col = x[:, j]
        lo, hi = float(np.min(col)), float(np.max(col))
        constant[j] = lo == hi
        if constant[j]:
            mean[j], variance[j], scale[j] = lo, 0.0, 0.0
            continue
        unit = max(abs(lo), abs(hi))
        mu = _fsum((float(v) / unit for v in col), 'mean') / n
        centered = [float(v) / unit - mu for v in col]
        c = max(map(abs, centered))
        if c == 0:
            _fail('underflow', 'nonconstant centered variance')
        ss = _fsum(((v/c)**2 for v in centered), 'variance') / n
        mean[j] = _product((unit, mu), 'mean') if mu else 0.0
        scale[j] = _product((unit, c, math.sqrt(ss)), 'standard deviation')
        variance[j] = _product((scale[j], scale[j]), 'variance')
    return {'mean': mean, 'variance': variance, 'scale': scale, 'constant': constant}


def _transform(x, stats):
    out = np.empty_like(x)
    for j in range(x.shape[1]):
        if stats['constant'][j]:
            out[:, j] = 0.0
            continue
        mu, sd = float(stats['mean'][j]), float(stats['scale'][j])
        for i in range(x.shape[0]):
            value = float(x[i, j])
            direct = value - mu
            if math.isfinite(direct):
                out[i, j] = _ratio(direct, sd, 'standardized value')
                continue
            unit = max(abs(value), abs(mu))
            delta = value/unit - mu/unit if unit else 0.0
            if not delta:
                out[i, j] = 0.0
            else:
                a, e = math.frexp(unit)
                b, f = math.frexp(sd)
                c, g = math.frexp(delta)
                try:
                    z = math.ldexp((a/b)*c, e-f+g)
                except OverflowError:
                    _fail('overflow', 'standardized value')
                if z == 0:
                    _fail('underflow', 'standardized value')
                out[i, j] = _finite(z, 'standardized value')
    return out


def standardize(train, other, *, limits=None):
    x, q = _array(train, 'train'), _array(other, 'other')
    n, d = x.shape
    if q.shape[1] != d:
        _fail('alignment', 'train/other columns')
    m = q.shape[0]
    ext = _bound(limits, n=n, m=m, d=d, matrices=(n*d, m*d),
                 live=(n+m)*d+4*d+3*n, optional=True)
    stats = moments(x, limits=limits)
    return {'train': _transform(x, stats), 'other': _transform(q, stats),
            'moments': stats, 'extents': ext}


def target_transform(train, other, *, limits=None):
    # Unlike feature constants, undefined target scale always refuses.
    x, q = _array(train, 'train'), _array(other, 'other')
    if x.shape[1] != q.shape[1]:
        _fail('alignment', 'target columns')
    n, d = x.shape
    ext = _bound(limits, n=n, m=q.shape[0], d=d, matrices=(n*d,q.size),
                 live=x.size+q.size+4*d+3*n, optional=True)
    stats = moments(x, limits=limits)
    if stats['constant'].any():
        _fail('zero_target_scale')
    return {'train': _transform(x, stats), 'other': _transform(q, stats),
            'moments': stats, 'extents': ext}


def aggregate_trials(normalized, video_ids, required_video_ids, *, limits=None):
    """Equal retained-trial weights (not equal session means), then one f32 cast."""
    x = _array(normalized, 'normalized')
    if len(video_ids) != x.shape[0] or not required_video_ids or len(set(required_video_ids)) != len(required_video_ids):
        _fail('trial_membership')
    wanted = tuple(required_video_ids)
    if any(v not in wanted for v in video_ids):
        _fail('trial_membership')
    _bound(limits, n=x.shape[0], m=len(wanted), d=x.shape[1], matrices=(len(wanted)*x.shape[1],),
           live=2*len(wanted)*x.shape[1], optional=True)
    out = np.empty((len(wanted), x.shape[1]), dtype=np.float64)
    for row, video in enumerate(wanted):
        selected = [i for i, v in enumerate(video_ids) if v == video]
        if not selected:
            _fail('missing_video')
        for j in range(x.shape[1]):
            unit = max(abs(float(x[i,j])) for i in selected)
            reduced = _fsum((float(x[i,j])/unit for i in selected), 'trial mean') / len(selected) if unit else 0.0
            out[row,j] = _product((unit,reduced),'trial mean') if reduced else 0.0
    return canonical_f32(out, limits=limits)


def _nearest_even_integer(numerator, denominator):
    whole, remainder = divmod(numerator, denominator)
    twice = 2 * remainder
    return whole + int(twice > denominator or (twice == denominator and whole % 2))


def _f32_expected_bits(value):
    """Exact finite binary64 to binary32 rounding using bounded-size integers."""
    sign = 0x80000000 if math.copysign(1.0, value) < 0 else 0
    absolute = abs(value)
    if absolute == 0:
        return sign
    numerator, denominator = absolute.as_integer_ratio()
    exponent = math.frexp(absolute)[1] - 1
    unit_exponent = max(exponent - 23, -149)
    if unit_exponent < 0:
        numerator <<= -unit_exponent
    else:
        denominator <<= unit_exponent
    significand = _nearest_even_integer(numerator, denominator)
    if exponent < -126:
        # A carry to 2**23 is the smallest normal; its bits are also 0x800000.
        return sign | significand
    if significand == (1 << 24):
        significand >>= 1
        exponent += 1
    if exponent > 127:
        return sign | 0x7f800000
    return sign | ((exponent + 127) << 23) | (significand - (1 << 23))


def canonical_f32(values, *, limits=None):
    """One nearest-even storage cast, signed-zero/subnormal diagnostics.

    Integer bit verification rejects a changed rounding/flush-to-zero runtime.
    It adds O(number of elements) scalar work, with bounded binary64-size
    integers, and no additional array-sized scratch or data acquisition.
    """
    x = _array(values, 'canonical source')
    n, q = x.shape
    _bound(limits, n=n, d=q, matrices=(n*q,), live=2*n*q+1, optional=True)
    with np.errstate(over='ignore', under='ignore', invalid='ignore'):
        canonical = x.astype('<f4')
    bit_view = canonical.view('<u4')
    nonzero_to_zero = subnormal = 0
    largest_zeroed = 0.0
    for original, converted, bits in zip(x.flat, canonical.flat, bit_view.flat):
        original, converted = float(original), float(converted)
        if not math.isfinite(converted):
            _fail('canonical_f32_range')
        if int(bits) != _f32_expected_bits(original):
            _fail('canonical_rounding_environment')
        if original != 0 and converted == 0:
            nonzero_to_zero += 1
            largest_zeroed = max(largest_zeroed, abs(original))
        if converted != 0 and abs(converted) < 2.0 ** -126:
            subnormal += 1
    return {'values': canonical,
            'quantization': {'nonzero_to_zero_count': nonzero_to_zero,
                             'subnormal_output_count': subnormal,
                             'largest_abs_binary64_rounded_to_zero': largest_zeroed,
                             'converted_elements': n*q,
                             'rounding': 'nearest_even',
                             'signed_zero_preserved': True}}


def gram_pair(train, other, *, limits):
    x, q = _array(train, 'train'), _array(other, 'other')
    n, d = x.shape
    if n < 2 or q.shape[1] != d:
        _fail('alignment', 'Gram dimensions')
    m = q.shape[0]
    ext = _bound(limits, n=n, m=m, d=d, matrices=(n*d,m*d,n*n,m*n),
                 live=6*(n*n+m*n))
    with np.errstate(all='ignore'):
        k, cross = x @ x.T, q @ x.T
    _array(k, 'Gram result'); _array(cross, 'cross Gram result')
    return {'train': k, 'cross': cross, 'extents': ext}


def _add_compensated(total, compensation, contribution):
    with np.errstate(all='ignore'):
        t = total + contribution
        correction = np.where(np.abs(total) >= np.abs(contribution),
                              (total-t)+contribution, (contribution-t)+total)
        compensation += correction
        total[:] = t
    if not np.isfinite(total).all() or not np.isfinite(compensation).all():
        _fail('nonfinite_result', 'compensated Gram accumulation')


def accumulate_gram_pairs(blocks, *, total_columns, layer_boundaries, block_width, identity, limits):
    """Exact consecutive full blocks; each entry includes layer/start/end/identity/train/other.

    Inputs train/other are already fitting-standardized. One layer cannot be
    split across different source pins. Returns all 17 layer Grams in order.
    """
    _identity(identity)
    if not isinstance(total_columns,int) or total_columns<17 or not isinstance(block_width,int) or block_width<1:
        _fail('block_schema')
    if len(layer_boundaries)!=18 or layer_boundaries[0]!=0 or layer_boundaries[-1]!=total_columns or any(a>=b for a,b in zip(layer_boundaries,layer_boundaries[1:])):
        _fail('layer_partition')
    _bound(limits,d=total_columns)
    train_grams, cross_grams, pins = [], [], []
    cursor, layer, shape = 0, 0, None
    total = compensation = cross_total = cross_comp = None
    for block in blocks:
        if not isinstance(block,dict) or set(block)!={'layer','start','end','identity','source_pin','train','other'}:
            _fail('block_schema')
        if _identity(block['identity']) != _identity(identity):
            _fail('identity')
        start,end,ordinal=block['start'],block['end'],block['layer']
        if any(isinstance(v,bool) or not isinstance(v,int) for v in (start,end,ordinal)) or start!=cursor or ordinal!=layer or end<=start or end>layer_boundaries[layer+1] or end-start!=min(block_width,layer_boundaries[layer+1]-start):
            _fail('block_partition')
        if not isinstance(block['source_pin'],str) or not block['source_pin']:
            _fail('source_pin')
        x,q=_array(block['train'],'block train'),_array(block['other'],'block other')
        if x.shape[1]!=end-start or q.shape[1]!=end-start:
            _fail('block_shape')
        n,m=x.shape[0],q.shape[0]
        if shape is None:
            shape=(n,m)
        if shape!=(n,m):
            _fail('alignment','block rows')
        _bound(limits,n=n,m=m,d=total_columns,matrices=(n*n,m*n,x.size,q.size),live=48*(n*n+m*n))
        if start==layer_boundaries[layer]:
            pins.append(block['source_pin'])
            total=np.zeros((n,n)); compensation=np.zeros_like(total)
            cross_total=np.zeros((m,n)); cross_comp=np.zeros_like(cross_total)
        elif pins[-1]!=block['source_pin']:
            _fail('source_pin')
        pair=gram_pair(x,q,limits=limits)
        _add_compensated(total,compensation,pair['train'])
        _add_compensated(cross_total,cross_comp,pair['cross'])
        cursor=end
        if end==layer_boundaries[layer+1]:
            train_grams.append(total+compensation); cross_grams.append(cross_total+cross_comp)
            layer+=1
    if cursor!=total_columns or layer!=17:
        _fail('incomplete_blocks')
    return {'train_grams':train_grams,'cross_grams':cross_grams,'identity':json.loads(_identity(identity)),
            'source_pins':pins,'block_width':block_width,'total_columns':total_columns}


def _residual(a, b, c):
    with np.errstate(all='ignore'):
        residual = a @ b - c
    _array(residual, 'solve residual')
    rn, an, bn, cn = _norm(residual), _norm(a), _norm(b), _norm(c)
    # Normalize the denominator in exponent space: an*bn need not fit f64.
    if rn == 0:
        relative = 0.0
    else:
        terms = []
        for x,y in ((an,bn),(cn,1.0)):
            if x and y:
                mx,ex=math.frexp(x); my,ey=math.frexp(y)
                terms.append((mx*my,ex+ey))
        if not terms:
            _fail('denominator','solve residual')
        exponent=max(e for _,e in terms)
        den=_fsum((math.ldexp(m,e-exponent) for m,e in terms),'backward denominator')
        mr,er=math.frexp(rn)
        try:
            relative=math.ldexp(mr/den,er-exponent)
        except OverflowError:
            _fail('overflow','backward error')
        if relative==0:
            _fail('underflow','backward error')
        _finite(relative,'backward error')
    threshold=4096*EPS*max(a.shape[0],1)
    if relative>threshold:
        _fail('solve_residual',repr(relative))
    return {'backward_error':relative,'threshold':threshold,'residual_norm':rn,
            'a_norm':an,'b_norm':bn,'c_norm':cn}


def spectrum(gram, *, limits):
    raw=_array(gram,'gram')
    n=raw.shape[0]
    if raw.shape!=(n,n) or n<2:
        _fail('shape','square Gram with n>1 required')
    ext=_bound(limits,n=n,matrices=(n*n,),live=16*n*n+12*n)
    maxabs=float(np.max(np.abs(raw)))
    with np.errstate(all='ignore'):
        asym=float(np.max(np.abs(raw-raw.T)))
    tol=_product((4096*EPS,n,max(maxabs,1.0)),'symmetry tolerance')
    if not math.isfinite(asym) or asym>tol:
        _fail('asymmetry')
    symmetric=raw/2.0+raw.T/2.0
    g=symmetric/(n-1)
    if np.any((symmetric!=0)&(g==0)):
        _fail('underflow','Gram normalization')
    try:
        eigen,u=np.linalg.eigh(g)
    except np.linalg.LinAlgError as exc:
        _fail('eigensolver',str(exc))
    if not np.isfinite(eigen).all() or not np.isfinite(u).all():
        _fail('nonfinite_eigensystem')
    order=np.argsort(-eigen,kind='stable'); eigen=eigen[order]; u=u[:,order]
    for j in range(n):
        pivot=int(np.argmax(np.abs(u[:,j])))
        if u[pivot,j]<0:
            u[:,j]*=-1
    if eigen[0]<=0:
        _fail('zero_spectrum')
    tau=_product((64*EPS,n,max(float(eigen[0]),1.0)),'rank tolerance')
    if float(eigen[-1]) < -tau:
        _fail('negative_spectrum')
    positive=eigen>tau
    if not positive.any():
        _fail('zero_rank')
    retained=eigen[positive].copy()
    with np.errstate(all='ignore'):
        difference=g@u-u*eigen
        orth=u.T@u-np.eye(n)
    _array(difference,'eigen residual'); _array(orth,'orthogonality residual')
    eig_error=_ratio(_norm(difference),max(_norm(g),TINY),'eigen residual')
    orth_error=_ratio(_norm(orth),float(n),'orthogonality residual')
    threshold=4096*EPS*n
    if max(eig_error,orth_error)>threshold:
        _fail('eigensolver_residual')
    ranks={}; boundary={}
    mass=_fsum((float(v) for v in retained),'eigen mass')
    for fraction in FRACTIONS:
        rank=len(retained)
        if fraction!='all':
            cutoff=float(fraction)*mass
            for count in range(1,len(retained)+1):
                if _fsum((float(v) for v in retained[:count]),'prefix mass')>=cutoff:
                    rank=count; break
        ranks[fraction]=rank
        gap=float(eigen[rank-1]-eigen[rank]) if rank<n else None
        boundary[fraction]={'gap':gap,'near_tie':gap is not None and gap<=tau}
    discarded=eigen[~positive]
    diagnostics={'maximum_asymmetry':asym,'symmetry_threshold':tol,'tau':tau,
                 'rank':int(positive.sum()),'discarded_count':int((~positive).sum()),
                 'discarded_signed_mass':_fsum((float(v) for v in discarded),'discarded mass'),
                 'minimum_gap':min((float(a-b) for a,b in zip(eigen,eigen[1:])),default=None),
                 'eigen_residual':eig_error,'orthogonality_residual':orth_error,'threshold':threshold,
                 'condition_estimate':_ratio(float(retained[0]),float(retained[-1]),'spectral condition'),
                 'boundary':boundary}
    return {'gram':symmetric,'normalized_gram':g,'eigenvalues':eigen,'eigenvectors':u,
            'positive_eigenvalues':retained,'ranks':ranks,'diagnostics':diagnostics,'extents':ext}


def settings(family):
    if family=='R1':
        return [{'id':'R1/fraction=.95','family':'R1','fraction':'0.95','lambda':'0'}]
    if family=='R2':
        return [{'id':f'R2/fraction={f}/lambda={lam}','family':'R2','fraction':f,'lambda':lam}
                for f in FRACTIONS for lam in LAMBDAS]
    if family=='R3':
        return [{'id':f'R3/template={t}/lambda={lam}','family':'R3','template':t,'lambda':lam}
                for t in TEMPLATES for lam in LAMBDAS]
    _fail('family')


def _setting(family, setting):
    if not isinstance(setting,dict) or setting not in settings(family):
        _fail('setting')
    return dict(setting)


def _identity(identity):
    if not isinstance(identity,Mapping) or not identity or any(not isinstance(k,str) or not k or not isinstance(v,str) or not v for k,v in identity.items()):
        _fail('identity','nonempty mapping of string keys to nonempty string pins required')
    return json.dumps(dict(identity),sort_keys=True,separators=(',',':'),ensure_ascii=True)


def _freeze(value):
    """Copy numeric state into immutable bytes ownership, recursively."""
    if isinstance(value, np.ndarray):
        if value.dtype.hasobject:
            _fail('prepared_dtype')
        # ndarray.setflags(write=True) cannot unlock a view backed by bytes.
        return np.frombuffer(value.tobytes(order='C'), dtype=value.dtype).reshape(value.shape)
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    if type(value) not in (str, int, float, bool, type(None)):
        _fail('prepared_metadata')
    return value


def _detached_metadata(value):
    if isinstance(value, Mapping):
        return {key: _detached_metadata(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_detached_metadata(item) for item in value]
    return value


def _prepared_digest(fields):
    """Verify immutable ownership and hash all feature contents without copying arrays.

    This full-state read is additional per-prediction work, not free cache reuse.
    The returned byte count includes numeric payload and canonical metadata.
    """
    digest = hashlib.sha256()
    visited = 0

    def feed(payload):
        nonlocal visited
        digest.update(payload)
        visited += len(payload)

    def visit(value):
        if type(value) is np.ndarray:
            owner = value
            while isinstance(owner, np.ndarray) and owner.base is not None:
                owner = owner.base
            if value.flags.writeable or not value.flags.c_contiguous or not isinstance(owner, bytes) or value.dtype.hasobject:
                _fail('prepared_custody', 'array must retain immutable bytes ownership')
            header = json.dumps({'dtype':value.dtype.str,'shape':value.shape},separators=(',',':')).encode()
            feed(b'A'+len(header).to_bytes(8,'little')+header)
            payload = memoryview(value).cast('B')
            feed(len(payload).to_bytes(8,'little'))
            feed(payload)
        elif isinstance(value, MappingProxyType):
            if any(type(key) is not str for key in value):
                _fail('prepared_custody', 'metadata keys')
            feed(b'M'+len(value).to_bytes(8,'little'))
            for key in sorted(value):
                visit(key); visit(value[key])
        elif type(value) is tuple:
            feed(b'T'+len(value).to_bytes(8,'little'))
            for item in value:
                visit(item)
        elif type(value) in (str,int,float,bool,type(None)):
            try:
                data=json.dumps(value,allow_nan=False,separators=(',',':')).encode()
            except (TypeError,ValueError):
                _fail('prepared_custody', 'nonfinite metadata')
            feed(b'S'+len(data).to_bytes(8,'little')+data)
        else:
            _fail('prepared_custody', 'mutable or unsupported state')

    visit(fields)
    return digest.hexdigest(), visited


class PreparedFeature(tuple):
    """Immutable feature state; constructed only by prepare_reference.

    This is an in-process API boundary, not a Python-code sandbox: the owner
    must not expose module internals or execute untrusted code in its process.
    No registry, hidden cache, target state or mutable identity is retained.
    """
    __slots__ = ()
    _fields = ('family', 'template', 'identity_json', 'identity_sha256',
               'train_gram', 'cross_gram', 'spectral', 'layer_scales', 'extents')

    def __new__(cls, *args, **kwargs):
        _fail('prepared_constructor', 'use prepare_reference')

    def __getattr__(self, name):
        if name == 'content_sha256':
            return self[9]
        if name in self._fields:
            return self[self._fields.index(name)]
        raise AttributeError(name)


def _make_prepared(**fields):
    if set(fields) != set(PreparedFeature._fields):
        _fail('prepared_constructor')
    frozen = tuple(_freeze(fields[name]) for name in PreparedFeature._fields)
    content_hash, _ = _prepared_digest(frozen)
    return tuple.__new__(PreparedFeature, frozen + (content_hash,))


def prepare_reference(family, train_grams, cross_grams, setting, *, limits, identity):
    chosen=_setting(family,setting); identity_json=_identity(identity)
    if not isinstance(train_grams,(list,tuple)) or not isinstance(cross_grams,(list,tuple)) or len(train_grams)!=17 or len(cross_grams)!=17:
        _fail('layer_support','exactly all17 aligned train and cross Grams required')
    n=_array(train_grams[0],'layer Gram').shape[0]
    m=_array(cross_grams[0],'layer cross Gram').shape[0]
    for k,c in zip(train_grams,cross_grams):
        _array(k,'layer Gram'); _array(c,'layer cross Gram')
        if k.shape!=(n,n) or c.shape!=(m,n):
            _fail('alignment','all17 Gram shape')
    # Includes immutable byte copies while the mutable constructor arrays live.
    ext=_bound(limits,n=n,m=m,matrices=(n*n,m*n),live=64*n*n+24*m*n+64*n)
    total=np.zeros((n,n)); compensation=np.zeros_like(total)
    cross=np.zeros((m,n)); cross_comp=np.zeros_like(cross)
    selected=MEMBERS[chosen['template']] if family=='R3' else tuple(range(17))
    layer_scales=[]
    # Validate symmetry of every required input, including non-selected layers.
    for ordinal,(k,c) in enumerate(zip(train_grams,cross_grams)):
        asym=float(np.max(np.abs(k-k.T)))
        allowed=4096*EPS*n*max(float(np.max(np.abs(k))),1.0)
        if not math.isfinite(asym) or not math.isfinite(allowed) or asym>allowed:
            _fail('asymmetry',f'layer {ordinal+1}')
        if family=='R3':
            scale=_fsum((float(k[i,i])/n for i in range(n)),'layer scale')
            if scale<=0:
                _fail('zero_layer_scale',str(ordinal+1))
            layer_scales.append(scale)
        else:
            scale=1.0
        if ordinal in selected:
            with np.errstate(all='ignore'):
                contribution=k/scale/len(selected) if family=='R3' else k
                cross_contribution=c/scale/len(selected) if family=='R3' else c
            if not np.isfinite(contribution).all() or not np.isfinite(cross_contribution).all():
                _fail('nonfinite_result','template scaling')
            if (np.any((k!=0)&(contribution==0)) or np.any((c!=0)&(cross_contribution==0))):
                _fail('underflow','template scaling')
            _add_compensated(total,compensation,contribution)
            _add_compensated(cross,cross_comp,cross_contribution)
    total=total+compensation; cross=cross+cross_comp
    sp=spectrum(total,limits=limits)
    return _make_prepared(family='PCA' if family in ('R1','R2') else family,
                           template=chosen.get('template'), identity_json=identity_json,
                           identity_sha256=hashlib.sha256(identity_json.encode()).hexdigest(),
                           train_gram=total, cross_gram=cross, spectral=sp,
                           layer_scales=tuple(layer_scales), extents=ext)


def _target_center(targets):
    n,q=targets.shape
    mean=np.empty(q); centered=np.empty_like(targets)
    for j in range(q):
        unit=max(abs(float(v)) for v in targets[:,j])
        mu=_fsum((float(v)/unit for v in targets[:,j]),'target mean')/n if unit else 0.0
        mean[j]=_product((unit,mu),'target mean') if mu else 0.0
        for i in range(n):
            centered[i,j]=_finite(float(targets[i,j])-float(mean[j]),'centered target')
    return mean,centered


def predict_prepared(prepared, targets, setting, *, limits, identity):
    if type(prepared) is not PreparedFeature or len(prepared)!=10 or type(prepared[9]) is not str:
        _fail('prepared_constructor', 'only trusted preparation state is accepted')
    if _identity(identity)!=prepared.identity_json:
        _fail('identity','prepared source/fit/query identity changed')
    if not isinstance(setting,dict):
        _fail('setting')
    family=setting.get('family')
    if (prepared.family=='PCA' and family not in ('R1','R2')) or (prepared.family=='R3' and family!='R3'):
        _fail('prepared_family')
    chosen=_setting(family,setting)
    if prepared.family=='R3' and chosen['template']!=prepared.template:
        _fail('prepared_template')
    y=_array(targets,'targets'); n,q=y.shape; m=prepared.cross_gram.shape[0]
    if n!=prepared.train_gram.shape[0]:
        _fail('alignment','target fitting rows')
    # Include retained PreparedFeature arrays and conservative temporaries.
    ext=_bound(limits,n=n,m=m,d=q,matrices=(n*n,m*n,n*q,m*q),
               live=48*n*n+20*m*n+20*n*q+8*m*q+32*n+8*q)
    content_hash, verified_bytes = _prepared_digest(tuple(prepared[:9]))
    if content_hash != prepared.content_sha256:
        _fail('prepared_content', 'prepared numeric or metadata contents changed')
    mean,yc=_target_center(y)
    sp=prepared.spectral; u=sp['eigenvectors']; eigen=sp['eigenvalues']
    lam=float(chosen['lambda']); scale=1.0
    if family in ('R1','R2'):
        rank=sp['ranks'][chosen['fraction']]; basis=u[:,:rank]
        k=(n-1)*eigen[:rank]
        if family=='R2':
            scale=_fsum((float(prepared.train_gram[i,i])/n for i in range(n)),'R2 scale squared')
            if scale<=0:
                _fail('zero_scale')
        with np.errstate(all='ignore'):
            denominators=k/scale+n*lam
            projected=basis.T@yc
            spectral_dual=projected/denominators[:,None]
            alpha=basis@spectral_dual
            prediction=(prepared.cross_gram@alpha)/scale+mean
            # Exact declared retained-PC normal equation in sample space.
            a=(basis*(k/scale))@basis.T+n*lam*np.eye(n)
            c=basis@projected
        penalty_scale=math.sqrt(scale)
    else:
        rank=sp['diagnostics']['rank']; basis=u
        with np.errstate(all='ignore'):
            denominators=(n-1)*eigen+n*lam
            projected=u.T@yc
            spectral_dual=projected/denominators[:,None]
            alpha=u@spectral_dual
            prediction=prepared.cross_gram@alpha+mean
            a=prepared.train_gram+n*lam*np.eye(n)
            c=yc
        penalty_scale=1.0
    if not np.isfinite(denominators).all() or np.any(denominators<=0):
        _fail('denominator','dual eigenvalues')
    for name,value in (('projection',projected),('spectral dual',spectral_dual),('dual coefficients',alpha),
                       ('prediction',prediction),('normal operator',a),('normal rhs',c)):
        _array(value,name)
    solve=_residual(a,alpha,c)
    condition=_ratio(float(np.max(denominators)),float(np.min(denominators)),'solve condition')
    state={'family':family,'setting':chosen,'identity':json.loads(prepared.identity_json),
           'identity_sha256':prepared.identity_sha256,'target_mean':mean,'centered_targets':yc,
           'prepared_content_sha256':prepared.content_sha256,
           'rank':rank,'feature_scale':penalty_scale,'layer_scales':prepared.layer_scales,
           'eigenvalues':eigen,'eigenvectors':u,'selected_basis':basis,'dual_denominators':denominators,
           'projected_targets':projected,'spectral_dual':spectral_dual,'dual_coefficients':alpha,
           'solve_a':a,'solve_b':alpha,'solve_c':c,'train_gram':prepared.train_gram,
           'cross_gram':prepared.cross_gram,'normalized_gram':sp['normalized_gram']}
    return {'prediction':prediction,'state':state,
            'diagnostics':{'spectrum':_detached_metadata(sp['diagnostics']),'solve':solve,'condition_estimate':condition,
                           'extent':ext,'feature_decomposition_reused':True,
                           'prepared_verified_payload_bytes':verified_bytes}}


def reference_predict(family, train_grams, cross_grams, targets, setting, *, limits, identity):
    prepared=prepare_reference(family,train_grams,cross_grams,setting,limits=limits,identity=identity)
    return predict_prepared(prepared,targets,setting,limits=limits,identity=identity)


def pearson(prediction, target, *, limits=None):
    p,t=_array(prediction,'prediction'),_array(target,'target')
    if p.shape!=t.shape or p.shape[0]<2:
        _fail('undefined_metric','Pearson support/alignment')
    n,q=p.shape
    _bound(limits,n=n,d=q,matrices=(n*q,),live=6*n+3*q,optional=True)
    result=np.empty(q); constant=np.zeros(q,dtype=np.bool_); excess=np.zeros(q)
    for j in range(q):
        tv,pv=t[:,j],p[:,j]
        if float(np.min(tv))==float(np.max(tv)):
            _fail('undefined_target','constant Pearson target')
        if float(np.min(pv))==float(np.max(pv)):
            constant[j]=True; result[j]=0.0; continue
        centered=[]
        for v in (pv,tv):
            unit=max(abs(float(x)) for x in v)
            mu=_fsum((float(x)/unit for x in v),'Pearson center')/n
            c=[float(x)/unit-mu for x in v]
            amplitude=max(map(abs,c))
            if amplitude==0:
                _fail('underflow','Pearson denominator')
            centered.append([x/amplitude for x in c])
        x,y=centered
        xx=_fsum((v*v for v in x),'Pearson x norm'); yy=_fsum((v*v for v in y),'Pearson y norm')
        denominator=math.sqrt(xx)*math.sqrt(yy)
        value=_ratio(_fsum((a*b for a,b in zip(x,y)),'Pearson dot'),denominator,'Pearson')
        if abs(value)>1:
            if abs(value)>1+64*EPS*n:
                _fail('correlation_range')
            excess[j]=value-math.copysign(1.0,value)
            value=math.copysign(1.0,value)
        result[j]=value
    return {'values':result,'constant_prediction':constant,'rounding_excess':excess,
            'rounding_excess_count':int(np.count_nonzero(excess))}


def mse(prediction, target, fit_variance=None, *, limits=None):
    p,t=_array(prediction,'prediction'),_array(target,'target')
    if p.shape!=t.shape:
        _fail('alignment','MSE')
    n,q=p.shape
    _bound(limits,n=n,d=q,matrices=(n*q,),live=3*n+q,optional=True)
    if fit_variance is not None:
        _array(fit_variance,'fit_variance',ndim=1)
        if fit_variance.shape!=(q,) or np.any(fit_variance<=0):
            _fail('undefined_variance')
    out=np.empty(q)
    for j in range(q):
        direct=[float(a)-float(b) for a,b in zip(p[:,j],t[:,j])]
        if all(math.isfinite(v) for v in direct):
            unit=max(map(abs,direct))
            differences=[v/unit for v in direct] if unit else direct
        else:
            unit=max(float(np.max(np.abs(p[:,j]))),float(np.max(np.abs(t[:,j]))))
            differences=[float(a)/unit-float(b)/unit for a,b in zip(p[:,j],t[:,j])]
        if not unit:
            out[j]=0.0; continue
        amplitude=max(map(abs,differences))
        if amplitude==0:
            if np.any(p[:,j]!=t[:,j]):
                _fail('underflow','nonzero MSE difference')
            out[j]=0.0; continue
        reduced=_fsum(((v/amplitude)**2 for v in differences),'MSE square')/n
        # Normalize in exponent space before materializing the requested value.
        # A raw square may be outside f64 while its requested ratio is finite.
        denominator = float(fit_variance[j]) if fit_variance is not None else 1.0
        out[j]=_product((unit,unit,amplitude,amplitude,reduced),
                        'normalized MSE' if fit_variance is not None else 'MSE',
                        denominator=denominator)
    return out


def select_setting(family, records):
    choices=settings(family); lookup={s['id']:s for s in choices}
    if not isinstance(records,(list,tuple)) or len(records)!=5*len(choices):
        _fail('incomplete_grid')
    observed={}
    for record in records:
        if not isinstance(record,dict) or set(record)!={'setting_id','fold','score'}:
            _fail('record_schema')
        sid,fold,score=record['setting_id'],record['fold'],record['score']
        if sid not in lookup or isinstance(fold,bool) or not isinstance(fold,int) or fold not in range(5):
            _fail('record_schema')
        if isinstance(score,bool) or not isinstance(score,(int,float)) or not math.isfinite(score):
            _fail('nonfinite_score')
        if (sid,fold) in observed:
            _fail('duplicate_grid')
        observed[sid,fold]=float(score)
    means={sid:_fsum((observed[sid,f] for f in range(5)),'fold mean')/5 for sid in lookup}
    def key(s):
        secondary=0 if family=='R1' else (FRACTIONS.index(s['fraction']) if family=='R2' else TEMPLATES.index(s['template']))
        return (-means[s['id']],-float(s['lambda']),secondary,s['id'])
    best=min(choices,key=key)
    return {'setting':best,'mean_score':means[best['id']],
            'fold_scores':[observed[best['id'],i] for i in range(5)],'all_mean_scores':means,
            'scalar_provenance_authenticated':False}
