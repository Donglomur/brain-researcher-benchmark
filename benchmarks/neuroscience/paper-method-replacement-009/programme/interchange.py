"""Written-only numerical conversion. Imports are inside future scientific calls.

No authentic payload, header or numerical function is executed during construction.
This converter is the explicit prospective repair, not an assertion that released
normalization/masking reproduced the paper. Source objects must already be acquired
under an independently qualified input manifest; there is no ONE/network fallback.
"""
from dataclasses import dataclass
from hashlib import sha256
import io
import ast
import struct
from .domain import Refusal, Pin, closed, identity, unique, canonical
from . import schemas

WINDOWS = {'choice': ('stimOn_times', -.5, 1.5, .05, 40),
           'prior': ('stimOn_times', -.6, -.1, .05, 10),
           'wheel-speed': ('firstMovement_times', 0., 1., .02, 50),
           'whisker-motion-energy': ('firstMovement_times', 0., 1., .02, 50)}

@dataclass(frozen=True)
class NumericLeaf:
    pin: Pin
    dtype: str
    shape: tuple
    axis_ids: tuple
    def document(self):
        return {'pin': self.pin.document(), 'dtype': self.dtype, 'shape': list(self.shape),
                'axis_ids': list(self.axis_ids)}

def read_array(store, spec):
    import numpy as np
    schemas.numeric_leaf(spec)
    raw = store.read(Pin.parse(spec['pin']))
    validate_npy_envelope(raw,spec['dtype'],tuple(spec['shape']),store.budget.limits.memory_bytes)
    a = np.load(io.BytesIO(raw), allow_pickle=False)
    if not isinstance(a, np.ndarray) or a.dtype.hasobject or a.dtype.str != spec['dtype']:
        raise Refusal('array dtype')
    if tuple(a.shape) != tuple(spec['shape']) or not a.flags.c_contiguous:
        raise Refusal('array shape/order')
    if len(spec['axis_ids']) != a.ndim: raise Refusal('axis identity rank')
    return a

def validate_npy_envelope(raw,dtype,shape,memory_limit):
    """Bound complete claimed primitive extent before NumPy allocation; future payload path."""
    widths={'<f8':8,'<f4':4,'<i8':8,'<i4':4,'<u8':8,'<u4':4,'|u1':1,'|b1':1}
    if dtype not in widths or type(shape) is not tuple or any(type(x) is not int or x<0 for x in shape):
        raise Refusal('primitive finite array domain')
    extent=widths[dtype]
    for x in shape:
        extent*=x
        if extent>memory_limit:raise Refusal('declared array memory capacity')
    if len(raw)<10 or raw[:6]!=b'\x93NUMPY':raise Refusal('NPY magic')
    version=tuple(raw[6:8])
    if version==(1,0):off=10;length=struct.unpack('<H',raw[8:10])[0]
    elif version==(2,0) and len(raw)>=12:off=12;length=struct.unpack('<I',raw[8:12])[0]
    else:raise Refusal('fixed NPY version')
    if length>65536 or off+length>len(raw):raise Refusal('bounded NPY metadata')
    meta=ast.literal_eval(raw[off:off+length].decode('latin1'))
    closed(meta,('descr','fortran_order','shape'),'NPY metadata')
    if meta['descr']!=dtype or meta['shape']!=shape or meta['fortran_order'] is not False:
        raise Refusal('NPY descriptor inverse')
    if len(raw)!=off+length+extent:raise Refusal('complete primitive payload extent')
    return extent

def capture_array(store, path, a, axis_ids):
    import numpy as np
    if not isinstance(a, np.ndarray) or a.dtype.hasobject or not np.isfinite(a).all():
        raise Refusal('finite primitive output')
    buffer = io.BytesIO(); np.save(buffer, np.ascontiguousarray(a), allow_pickle=False)
    capture = store.put(path, buffer.getvalue())
    return capture, NumericLeaf(capture.pin, a.dtype.str, a.shape, tuple(axis_ids))

def validate_trial_support(v):
    return schemas.trial_support(v)


def prospective_split(session, typed_trial_ids):
    """Existing40RE split, explicitly not a historical433 split reconstruction."""
    pairs = [(identity(x), i) for i, x in enumerate(typed_trial_ids)]
    unique([x[0] for x in pairs], 'split trials')
    # Existing seed uses EID+NUL+original integer trial ID decimal spelling.
    if any(x[0][0] != 'integer' for x in pairs): raise Refusal('RE original integer trial IDs')
    order = sorted(pairs, key=lambda x: sha256((session+'\x00'+str(x[0][1])).encode()).digest())
    n = len(order); labels = [None]*n
    for rank, (_, i) in enumerate(order):
        labels[i] = 'train' if rank < int(.7*n) else 'validation' if rank < int(.8*n) else 'test'
    return labels

def regional_spike_projection(regional):
    """Exact original-index to selected-column inverse; no scientific leaf."""
    from .support import RegionalSelection
    if type(regional) is not RegionalSelection: raise Refusal('original regional occurrence')
    regional.require_original()
    return {original:column for column,original in enumerate(regional.indices)}

def convert_ibl(raw, target, support, memory_limit, regional):
    """Exact selected-local-array→interchange producer, with retained original rows.

    raw fields are resolved by read_ibl_manifest, never arbitrary provider callbacks.
    No clock interpolation/extrapolation silently creates missing target support.
    """
    import numpy as np
    validate_trial_support(support)
    if target not in WINDOWS: raise Refusal('IBL target')
    align, left, right, dt, bins = WINDOWS[target]
    mapping=regional_spike_projection(regional)
    if support!=regional.owner.source_support(regional.case_id):raise Refusal('original regional support')
    n = len(support['trial_ids']); original_u = len(support['unit_ids']); u=len(mapping)
    trials = raw['trials']; times = raw['spike_times']; clusters = raw['spike_units']
    required = ('stimOn_times', 'firstMovement_times', 'feedback_times', 'choice',
                'probabilityLeft', 'feedbackType')
    if any(np.asarray(trials[k]).shape != (n,) for k in required): raise Refusal('trial columns')
    if times.ndim != 1 or clusters.shape != times.shape or np.any(np.diff(times) < 0):
        raise Refusal('spike clock/order')
    if not np.isfinite(times).all() or clusters.dtype.kind not in 'iu' or np.any(clusters < 0) or np.any(clusters >= original_u):
        raise Refusal('source unit index')
    rt = trials['firstMovement_times']-trials['stimOn_times']
    finite = np.logical_and.reduce([np.isfinite(trials[k]) for k in required])
    mask = finite & (rt >= .08) & (rt <= 2.) & (trials['choice'] != 0)
    # The input compiler's complete mask is additional, never replaced by the source's list-and bug.
    mask &= np.asarray(support['eligibility'], dtype=bool)
    out_bins = 1 if target in ('choice', 'prior') else bins
    if 8*n*(bins*u+out_bins)>memory_limit:raise Refusal('interchange allocation exceeds original memory bound')
    x = np.zeros((n, bins, u), dtype='<f8')
    y = np.full((n, out_bins), np.nan, dtype='<f8'); reasons = [[] for _ in range(n)]
    if target == 'prior' and support['prior_source'] is None:
        raise Refusal('fitted behavioral prior source is required; probabilityLeft is not prior')
    for k in range(n):
        if not mask[k]: reasons[k].append('original_trial_eligibility'); continue
        start = trials[align][k]+left; end = trials[align][k]+right
        edges = start + np.arange(bins+1)*dt
        if abs(edges[-1]-end) > 1e-9: raise Refusal('window arithmetic')
        lo, hi = np.searchsorted(times, (start, end), side='left')
        offsets = np.floor((times[lo:hi]-start)/dt).astype(np.int64)
        if np.any(offsets < 0) or np.any(offsets >= bins): raise Refusal('bin ownership')
        # Original spike indices stay original until this exact regional inverse.
        keep=np.asarray([int(index) in mapping for index in clusters[lo:hi]],dtype=bool)
        selected=np.asarray([mapping[int(index)] for index in clusters[lo:hi][keep]],dtype=np.int64)
        np.add.at(x[k], (offsets[keep], selected), 1)
        if target == 'choice':
            if trials['choice'][k] not in (-1, 1): raise Refusal('choice alphabet')
            y[k, 0] = int(trials['choice'][k] == 1)
        elif target == 'prior': y[k, 0] = raw['fitted_prior'][k]
        else:
            bt, bv = raw['behavior_times'], raw['behavior_values']
            # Original behavior helper excludes boundary samples, then interpolates at bin ends.
            a = np.searchsorted(bt, start, side='right'); b = np.searchsorted(bt, end, side='left')
            tt, vv = bt[a:b], bv[a:b]
            if len(tt) < 2 or not np.isfinite(vv).all() or tt[0]-start > dt or end-tt[-1] > dt:
                mask[k] = False; reasons[k].append('behavior_coverage'); continue
            if np.any(np.diff(tt) <= 0): raise Refusal('behavior clock')
            # Use released linear extrapolation at the final bin endpoint explicitly.
            from scipy.interpolate import interp1d
            y[k] = interp1d(tt, vv, kind='linear', fill_value='extrapolate')(edges[1:])
        if not np.isfinite(y[k]).all(): mask[k] = False; reasons[k].append('nonfinite_target')
    # No deletion of original IDs. Ineligible numerical slots are never made into zero labels.
    if mask.tolist()!=support['eligibility']:
        raise Refusal('observed target eligibility differs from earlier common-union support')
    return {'x': x, 'y': y, 'eligible': mask, 'reasons': reasons,
            'support':regional.owner.selected_support(regional),
            'unit_selection':regional.capture.pin.document(),'common_split':regional.owner.split.pin.document(),
            'window': {'align': align, 'left': left, 'right': right, 'binsize': dt, 'bins': bins},
            'method': 'prospective_intersection_train_only_v1'}

def read_ibl_manifest(store, manifest, target, regional):
    """Fixed local ALF projection. Acquisition/sorter/clock identity are earlier obligations."""
    regional_spike_projection(regional)
    if store is not regional.owner.input_store or manifest!=regional.owner.manifest(regional.case_id):
        raise Refusal('original regional input owner/manifest')
    if target!=regional.owner.case(regional.case_id).target:raise Refusal('regional target')
    closed(manifest, ('schema', 'session', 'sorter', 'atlas', 'source_capture',
                      'support', 'spike_times', 'spike_units', 'trials',
                      'fitted_prior', 'behavior_times', 'behavior_values'), 'IBL manifest')
    if manifest['schema'] != 'trial_session_local_ibl_v1': raise Refusal('local IBL schema')
    for k in ('sorter', 'atlas', 'source_capture'): Pin.parse(manifest[k])
    support = validate_trial_support(store.json(Pin.parse(manifest['support'])))
    if support['session'] != manifest['session']: raise Refusal('session identity')
    names = ('stimOn_times', 'firstMovement_times', 'feedback_times', 'choice', 'probabilityLeft', 'feedbackType')
    closed(manifest['trials'], names, 'fixed original trial columns')
    raw = {'trials': {k: read_array(store, manifest['trials'][k]) for k in names},
           'spike_times': read_array(store, manifest['spike_times']),
           'spike_units': read_array(store, manifest['spike_units'])}
    if target == 'prior': raw['fitted_prior'] = read_array(store, manifest['fitted_prior'])
    if target in ('wheel-speed', 'whisker-motion-energy'):
        for k in ('behavior_times', 'behavior_values'): raw[k] = read_array(store, manifest[k])
    return convert_ibl(raw, target, support,store.budget.limits.memory_bytes,regional)

def capture_interchange(store, case, converted):
    import numpy as np
    x, y, mask = converted['x'], converted['y'], converted['eligible']
    if len(mask) != len(converted['support']['trial_ids']): raise Refusal('full retained mask')
    # Capture only eligible numeric rows and an exact inverse to the full original support.
    rows = np.flatnonzero(mask)
    a, xleaf = capture_array(store, case+'/x.npy', x[rows], ('original_trial', 'time', 'unit'))
    b, yleaf = capture_array(store, case+'/y.private.npy', y[rows], ('original_trial', 'output'))
    doc = {'schema': 'trial_session_interchange_v1', 'case_id': case,
           'x': xleaf.document(), 'y': yleaf.document(), 'row_inverse': rows.tolist(),
           'full_support': converted['support'], 'exclusions': converted['reasons'],
           'window': converted['window'], 'method': converted['method'],
           'unit_selection':converted['unit_selection'],'common_split':converted['common_split']}
    return store.put_json(case+'/manifest.private.json', doc), (a, b)

def normalize_train_only(x, y, partitions, classification):
    import numpy as np
    if x.ndim != 3 or y.ndim != 2 or len(x) != len(y) or len(partitions) != len(x): raise Refusal('normalizer shape')
    train = np.asarray([p == 'train' for p in partitions])
    if not train.any() or not np.isfinite(x).all() or not np.isfinite(y).all(): raise Refusal('normalizer support')
    # Released intended per-time scalar over trial+neuron, fitted ONLY on training rows.
    mean = x[train].mean(axis=(0, 2), keepdims=True)
    sd = x[train].std(axis=(0, 2), keepdims=True); sd = np.where(sd == 0, 1, sd)
    z = (x-mean)/sd
    ym = np.zeros((1, y.shape[1])); ys = np.ones((1, y.shape[1]))
    if not classification:
        ym = y[train].mean(axis=0, keepdims=True); ys = y[train].std(axis=0, keepdims=True)
        ys = np.where(ys == 0, 1, ys)
    return z, (y-ym)/ys, {'x_mean': mean, 'x_sd': sd, 'y_mean': ym, 'y_sd': ys,
                        'fitted_rows': np.flatnonzero(train)}
