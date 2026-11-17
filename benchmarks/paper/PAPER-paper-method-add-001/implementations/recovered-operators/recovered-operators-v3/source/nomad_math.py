"""Recovered dPCA/PCR mathematics; no implicit original NoMAD profile.

No package is imported and no numerical operation occurs on module import.
Complete scientific profiles and exact support are explicit call inputs. Output
states are numerical artifacts, never claims about original-run provenance.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import math


class Refused(ValueError):
    pass


def need(value, reason):
    if not value:
        raise Refused(reason)


def closed(value, keys, reason):
    need(type(value) is dict and set(value) == set(keys), reason)


def integer(x, minimum=0):
    need(type(x) is int and x >= minimum, 'exact nonnegative extent')
    return x


def finite(x, minimum=None):
    need(type(x) in (int, float) and math.isfinite(x), 'finite scalar')
    need(minimum is None or x >= minimum, 'scalar lower bound')
    return float(x)


def identity(value):
    return sha256(json.dumps(value, allow_nan=False, sort_keys=True,
                             separators=(',', ':')).encode()).hexdigest()


@dataclass
class Budget:
    """Declared NumPy scalar/operation extents, not measured BLAS/RSS limits."""
    max_array_elements: int
    cumulative_elements: int
    cumulative_matmul_products: int

    def __post_init__(self):
        for x in (self.max_array_elements, self.cumulative_elements,
                  self.cumulative_matmul_products):
            integer(x, 1)
        self.used_elements = self.used_products = 0
        self.attempted_elements = self.attempted_products = 0
        self.plans = []

    def reserve(self, label, arrays, products=0):
        need(type(label) is str and label, 'named allocation')
        need(type(arrays) is dict and arrays, 'explicit allocation map')
        for n in arrays.values():integer(n)
        total=sum(arrays.values());integer(products)
        self.attempted_elements+=total;self.attempted_products+=products
        record={'label':label,'arrays':dict(arrays),'products':products,'status':'refused_before_allocation'}
        self.plans.append(record)
        need(all(n<=self.max_array_elements for n in arrays.values()), 'single internal array extent')
        need(self.used_elements+total<=self.cumulative_elements, 'cumulative internal arrays including every repeated temporary')
        need(self.used_products+products<=self.cumulative_matmul_products, 'full matrix product work')
        self.used_elements+=total;self.used_products+=products;record['status']='reserved'

    def report(self):
        return {'elements_reserved': self.used_elements,
                'elements_attempted':self.attempted_elements,'matmul_products_attempted':self.attempted_products,
                'matmul_products_reserved': self.used_products,
                'plans': list(self.plans),
                'backend_workspace_and_physical_RSS': 'not measured; deployment hold',
                'caller_owned_input_storage_excluded': True}


def numpy_for(profile):
    need(type(profile) is dict, 'explicit numerical profile')
    need(type(profile.get('numpy_version')) is str, 'selected NumPy version')
    import numpy as np
    need(np.__version__ == profile['numpy_version'], 'exact numerical runtime version')
    return np


def matrix(np, value, shape, budget, name):
    need(type(value) is np.ndarray and value.dtype == np.dtype('float64'),
         'caller array must be binary64 NumPy, no implicit coercion')
    need(value.shape == tuple(shape), 'complete exact array shape')
    need(value.flags.c_contiguous and value.dtype.str=='<f8',
         'canonical contiguous little-endian input; no hidden coercion/copy')
    budget.reserve(name + '.finite_mask', {'mask': value.size})
    need(bool(np.isfinite(value).all()), 'finite numerical source array')
    return value


def seal_array(np, array, budget, label):
    """Bytes-backed read-only state; ordinary returned aliases cannot mutate it."""
    budget.reserve(label + '.immutable_copy', {'bytes_as_float_slots': array.size})
    raw = array.astype('<f8', copy=False).tobytes(order='C')
    return np.frombuffer(raw, dtype='<f8').reshape(array.shape)


def array_identity(a):
    need(a.flags.c_contiguous and a.dtype.str=='<f8',
         'hash exact canonical array bytes without a whole-array copy')
    return {'shape': list(a.shape), 'dtype': '<f8',
            'sha256': sha256(memoryview(a).cast('B')).hexdigest()}


def profile_tolerances(profile):
    r = finite(profile['rank_relative_threshold'], 0)
    t = finite(profile['boundary_tie_relative_threshold'], 0)
    e = finite(profile['residual_relative_limit'], 0)
    need(r < 1 and t < 1 and e > 0, 'declared rank/tie/residual domain')
    return r, t, e


def condition_means(trials, support, profile, budget):
    """Derive complete condition/time means from every admitted trial tensor.

    support has exact ordered trial IDs, their conditions, all condition IDs,
    time coordinates and feature IDs. No implicit subset or padding is used.
    """
    closed(support, ['trial_ids', 'trial_conditions', 'condition_ids',
                     'time_coordinates', 'feature_ids'], 'closed trial support')
    np = numpy_for(profile)
    for key in ('trial_ids', 'condition_ids', 'feature_ids'):
        v = support[key]
        need(type(v) is list and v and all(type(x) is str and x for x in v)
             and len(set(v)) == len(v), 'complete unique support identifiers')
    conds = support['condition_ids']; tids = support['trial_ids']
    assignment = support['trial_conditions']; times = support['time_coordinates']
    need(type(assignment) is list and len(assignment) == len(tids)
         and set(assignment) == set(conds), 'every condition represented')
    need(type(times) is list and times and all(math.isfinite(finite(x)) for x in times)
         and all(a < b for a, b in zip(times, times[1:])), 'strict time grid')
    need(type(trials) is dict and set(trials) == set(tids), 'every trial and no extras')
    c, t, f = len(conds), len(times), len(support['feature_ids'])
    budget.reserve('condition_means', {'output': c*t*f, 'initial_accumulators':c*t*f,'repeated_online_mean_temporaries':3*len(tids)*t*f,
                                      'ordered_counts': c})
    means = np.empty((f, c, t), dtype=np.float64)
    counts = [];input_pins={}
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        for j, cond in enumerate(conds):
            members = [k for k, a in zip(tids, assignment) if a == cond]
            counts.append(len(members)); acc = np.zeros((t, f), dtype=np.float64)
            # Online mean avoids overflow from summing equal large finite values.
            for i, key in enumerate(members):
                a = matrix(np, trials[key], (t, f), budget, 'trial:' + key)
                input_pins[key]=array_identity(a)
                acc = acc * (i / (i + 1)) + a / (i + 1)
                need(array_identity(a)==input_pins[key],'unchanged consumed trial values')
            means[:, j, :] = acc.T
    need(bool(np.isfinite(means).all()), 'finite condition means')
    return {'means': seal_array(np, means, budget, 'condition_means'),
            'counts': tuple(counts), 'support': json.loads(json.dumps(support)),
            'support_pin': identity(support),'input_data_pins':input_pins}


def marginalize(prepared, profile, budget):
    """Weighted two-factor condition/time ANOVA; joins are explicit profile facts."""
    np = numpy_for(profile)
    m = prepared['means']; f, c, t = m.shape
    matrix(np, m, (f, c, t), budget, 'condition_means.input')
    mode = profile['condition_weighting']
    need(mode in ('equal_condition', 'trial_count'), 'explicit condition weighting')
    groups = profile['marginal_groups']
    need(type(groups) is dict and groups, 'explicit marginal grouping')
    all_terms = []
    for name, terms in groups.items():
        need(type(name) is str and name and type(terms) is list and terms,
             'named nonempty marginal')
        need(len(set(terms)) == len(terms), 'no duplicate marginal term')
        all_terms += terms
    need(set(all_terms) == {'condition', 'time', 'interaction'}
         and len(all_terms) == 3, 'complete nonoverlapping marginal partition')
    budget.reserve('marginalization', {'weights': c, 'grand': f,
        'raw_centered_and_components': 9*f*c*t,
        'weighted_design_and_group_outputs': (2 + len(groups))*f*c*t})
    w = np.ones(c, dtype=np.float64) if mode == 'equal_condition' else np.array(prepared['counts'], dtype=np.float64)
    w /= w.sum()
    grand = (m.mean(axis=2) * w[None, :]).sum(axis=1)
    centered = m - grand[:, None, None]
    condition = np.broadcast_to(centered.mean(axis=2)[:, :, None], m.shape).copy()
    time = np.broadcast_to((centered*w[None, :, None]).sum(axis=1)[:, None, :], m.shape).copy()
    interaction = centered - condition - time
    components = {'condition': condition, 'time': time, 'interaction': interaction}
    # Columns weighted so XX.T realizes the selected condition measure.
    scale = np.sqrt(c*w)[None, :, None]
    X = (centered * scale).reshape(f, c*t)
    out = {}
    for name, terms in groups.items():
        a = np.zeros_like(centered)
        for term in terms:
            a += components[term]
        out[name] = seal_array(np, (a*scale).reshape(f, c*t), budget, name)
    return {'X': seal_array(np, X, budget, 'design'),
            'marginals': out, 'mean': seal_array(np, grand, budget, 'grand'),
            'condition_weights': seal_array(np, w, budget, 'weights'),
            'support': prepared['support'], 'support_pin': prepared['support_pin']}


def canonical_columns(np, u):
    for j in range(u.shape[1]):
        k = int(np.argmax(np.abs(u[:, j])))
        if u[k, j] < 0:
            u[:, j] *= -1
    return u


def fit_dpca(prepared, profile, budget):
    required = {'numpy_version', 'condition_weighting', 'marginal_groups', 'lambda',
                'components', 'rank_relative_threshold', 'boundary_tie_relative_threshold',
                'residual_relative_limit', 'profile_id', 'source_profile_pin'}
    closed(profile, required, 'complete explicit dPCA numerical profile')
    np = numpy_for(profile); rcond, tie, tol = profile_tolerances(profile)
    need(type(profile['components']) is dict and
         set(profile['components']) == set(profile['marginal_groups']), 'all marginal component counts')
    lam = finite(profile['lambda'], 0)
    v = marginalize(prepared, profile, budget); X = v['X']; f, p = X.shape
    budget.reserve('dpca.covariance', {'gram_identity_scaled_and_regularized': 4*f*f,
                                     'norm_temporaries': 2*f*p}, f*f*p)
    norm = float(np.linalg.norm(X)); mu = (lam * norm)**2
    need(math.isfinite(mu), 'finite ridge magnitude')
    gram = X @ X.T; regularized = gram + mu*np.eye(f)
    encoders, decoders, operators, spectra, diagnostics = {}, {}, {}, {}, {}
    for name, Y in v['marginals'].items():
        q = integer(profile['components'][name], 1)
        need(q <= min(f, p), 'full selected component count')
        k = min(f, p)
        budget.reserve('dpca:' + name, {'cross_solve': 5*f*f,
            'projected_and_residuals': 7*f*p, 'svd_U': f*k, 'svd_s': k,
            'svd_Vh': k*p, 'encoder_decoder': 2*f*q},
            3*f*f*p + 2*f*f*f + 2*f*f*q)
        cross = Y @ X.T
        # Zero regularization does not silently authorize a pseudoinverse.
        evals = np.linalg.eigvalsh(regularized)
        need(evals[-1] > 0 and evals[0] > rcond*evals[-1],
             'regularized system must have admitted positive rank')
        A = np.linalg.solve(regularized, cross.T).T
        denom = max(float(np.linalg.norm(cross)), float(np.linalg.norm(regularized))*float(np.linalg.norm(A)))
        residual = float(np.linalg.norm(A @ regularized-cross))
        need(denom > 0 and residual/denom <= tol, 'ridge solve residual')
        u, singular, _ = np.linalg.svd(A @ X, full_matrices=False)
        need(len(singular) >= q and singular[0] > 0 and singular[q-1] > rcond*singular[0],
             'requested components must have positive admitted rank')
        if q < len(singular):
            need(abs(singular[q-1]-singular[q]) > tie*singular[0],
                 'unresolved selected singular-subspace boundary')
        F = canonical_columns(np, u[:, :q].copy()); D = F.T @ A
        for collection, a in [(encoders,F),(decoders,D),(operators,A),(spectra,singular)]:
            collection[name] = seal_array(np, a, budget, 'dpca.state.' + name)
        diagnostics[name] = {'mu':mu, 'solve_relative_residual':residual/denom,
            'regularized_rank':f,'retained_components':q,
            'reconstruction_squared_error':float(np.linalg.norm(Y-F@(D@X))**2)}
    arrays = {'mean': v['mean'],'design':v['X'],'condition_weights':v['condition_weights'],
              **{'marginal/'+n:a for n,a in v['marginals'].items()},
              **{'encoder/'+n:a for n,a in encoders.items()},
              **{'decoder/'+n:a for n,a in decoders.items()},
              **{'operator/'+n:a for n,a in operators.items()},
              **{'spectrum/'+n:a for n,a in spectra.items()}}
    state = {'kind':'regularized_dpca_v1', 'profile':json.loads(json.dumps(profile)),
             'support':v['support'], 'support_pin':v['support_pin'],
             'input_data_pins':prepared['input_data_pins'],'arrays':arrays, 'diagnostics':diagnostics}
    state['identity'] = state_identity(state)
    return state


def state_identity(state):
    need(identity(state['support'])==state['support_pin'],'support body matches immutable state support pin')
    return identity({'kind':state['kind'], 'profile':state['profile'],
                     'support_pin':state['support_pin'],
                     'input_data_pins':state['input_data_pins'],
                     'arrays':{n:array_identity(a) for n,a in sorted(state['arrays'].items())},
                     'diagnostics':state['diagnostics']})


def transfer_dpca(state, expected_state_identity, trials, support, budget):
    need(state['identity'] == expected_state_identity == state_identity(state),
         'immutable fitted state identity')
    np = numpy_for(state['profile'])
    need(support['condition_ids'] == state['support']['condition_ids']
         and support['time_coordinates'] == state['support']['time_coordinates']
         and support['feature_ids'] == state['support']['feature_ids'],
         'same condition/time/feature coordinates; trial IDs may differ')
    prepared = condition_means(trials, support, state['profile'], budget)
    mean = state['arrays']['mean']; t = len(support['time_coordinates']); f = len(mean)
    projected = {}
    for name in state['profile']['components']:
        D = state['arrays']['decoder/'+name]; q = D.shape[0]
        budget.reserve('dpca.transfer.'+name, {'full_trial_outputs':len(trials)*t*q,
                                             'repeated_centered_trials':len(trials)*t*f}, len(trials)*t*f*q)
        projected[name] = {}
        for key in support['trial_ids']:
            projected[name][key] = seal_array(np, (trials[key]-mean) @ D.T,
                                               budget, 'transferred.'+key)
    return {'state_identity':expected_state_identity,'support':prepared['support'],
            'support_pin':prepared['support_pin'],'input_data_pins':prepared['input_data_pins'],
            'projected_trials':projected}


def generic_three_coordinate_distance_grid(reference, query, components, budget):
    need(reference['state_identity'] == query['state_identity'], 'one fixed Day0 projection')
    rs, qs = reference['support'], query['support']
    for key in ('condition_ids','time_coordinates','feature_ids'):
        need(rs[key] == qs[key], 'matched full condition/time coordinates')
    need(type(components) is list and len(components) == 3
         and len({tuple(x) for x in components}) == 3, 'explicit three dPC coordinates')
    import numpy as np
    c,t = len(rs['condition_ids']),len(rs['time_coordinates'])
    budget.reserve('distance_grid', {'result_matrices':6*c*t,'initial_accumulators':6*c*t,
        'repeated_online_mean_temporaries':9*(len(rs['trial_ids'])+len(qs['trial_ids']))*t,
        'delta_and_square':6*c*t,'reduction_and_root':2*c*t})
    means=[]
    for product in (reference,query):
        s=product['support']; result=np.empty((c,t,3),dtype=np.float64)
        for ci,cond in enumerate(s['condition_ids']):
            keys=[key for key,a in zip(s['trial_ids'],s['trial_conditions']) if a==cond]
            need(keys, 'complete condition coverage')
            for di,(name,index) in enumerate(components):
                integer(index)
                need(name in product['projected_trials'], 'selected named marginal')
                value=np.zeros(t,dtype=np.float64)
                for j,key in enumerate(keys):
                    a=product['projected_trials'][name][key]
                    need(a.shape[0]==t and index<a.shape[1], 'component support')
                    value=value*(j/(j+1))+a[:,index]/(j+1)
                result[ci,:,di]=value
        means.append(result)
    delta=means[1]-means[0]
    distances=np.sqrt(np.sum(delta*delta,axis=2))
    need(bool(np.isfinite(distances).all()), 'finite full distance grid')
    return {'reference_means':seal_array(np,means[0],budget,'reference.means'),
            'query_means':seal_array(np,means[1],budget,'query.means'),
            'distances':seal_array(np,distances,budget,'distances'),
            'components':components,'scalar_aggregation':'not selected'}


def nomad_distance_grid(reference,query,state,selection,budget):
    closed(selection,['schema','source_profile_pin','fitted_state_identity','marginal_roles','coordinates'],
           'immutable scientific NoMAD distance selection')
    need(selection['schema']=='nomad_one_ci_two_cd_selection_v2'
         and selection['source_profile_pin']==state['profile']['source_profile_pin']
         and selection['fitted_state_identity']==state['identity']==state_identity(state),
         'selected scientific recipe and actual fitted state')
    groups=state['profile']['marginal_groups'];roles=selection['marginal_roles']
    need(type(roles) is dict and set(roles)==set(groups), 'complete source-selected marginal roles')
    for name,role in roles.items():
        terms=set(groups[name])
        need(role in ('CI','CD') and (terms=={'time'} if role=='CI' else bool(terms) and terms<={'condition','interaction'}),
             'marginal algebra agrees with declared independent/dependent role')
    coordinates=selection['coordinates'];need(type(coordinates) is list and len(coordinates)==3,'full declared component coordinates')
    selected=[];kinds=[]
    for row in coordinates:
        closed(row,['marginal','index','role'],'exact scientific component identity')
        need(row['marginal'] in roles and row['role']==roles[row['marginal']], 'component role joins fitted marginal')
        selected.append([row['marginal'],row['index']]);kinds.append(row['role'])
    need(kinds.count('CI')==1 and kinds.count('CD')==2, 'NoMAD endpoint requires exactly one CI and two CD coordinates')
    value=generic_three_coordinate_distance_grid(reference,query,selected,budget)
    value['scientific_selection_pin']=identity(selection);value['scientific_roles']=kinds
    value['original_recipe_independently_qualified']=False
    return value


def fit_pcr(sessions, profile, budget):
    closed(profile, ['numpy_version','profile_id','source_profile_pin','shared_dimension',
        'centering','rank_relative_threshold','boundary_tie_relative_threshold',
        'residual_relative_limit'], 'complete explicit PCR profile')
    np=numpy_for(profile);rcond,tie,tol=profile_tolerances(profile)
    need(type(sessions) is dict and len(sessions)>=2, 'complete joint session roster')
    need(profile['centering'] in ('per_unit','none'), 'explicit original centering selection')
    ordered=sorted(sessions);supports=[sessions[s]['support'] for s in ordered]
    for s in supports[1:]:
        need(s['condition_ids']==supports[0]['condition_ids'] and
             s['time_coordinates']==supports[0]['time_coordinates'], 'shared condition/time grid')
    cols=len(supports[0]['condition_ids'])*len(supports[0]['time_coordinates'])
    rows=sum(sessions[s]['means'].shape[0] for s in ordered);q=integer(profile['shared_dimension'],1)
    need(q<=min(rows,cols), 'complete selected shared dimension')
    budget.reserve('pcr.shared_svd', {'stack_and_centered':3*rows*cols,
        'U':rows*min(rows,cols),'Vh':min(rows,cols)*cols,'singular':min(rows,cols),
        'scores':q*cols,'session_means':rows}, rows*cols*min(rows,cols))
    matrices={};offsets={}
    for key in ordered:
        a=sessions[key]['means'];f=a.shape[0]
        matrix(np,a,(f,len(supports[0]['condition_ids']),len(supports[0]['time_coordinates'])),budget,'pcr.source.'+key)
        a=a.reshape(f,cols);offset=a.mean(axis=1) if profile['centering']=='per_unit' else np.zeros(f)
        matrices[key]=a-offset[:,None];offsets[key]=offset
    C=np.concatenate([matrices[k] for k in ordered],axis=0)
    U,S,Vh=np.linalg.svd(C,full_matrices=False)
    need(S[0]>0 and S[q-1]>rcond*S[0], 'positive shared PCA rank')
    if q<len(S):need(abs(S[q-1]-S[q])>tie*S[0], 'unresolved shared-PCA boundary')
    Uq=canonical_columns(np,U[:,:q].copy());Z=Uq.T@C
    readins={};readouts={};diagnostics={}
    for key,Cs in matrices.items():
        f=Cs.shape[0];k=min(Cs.shape)
        budget.reserve('pcr.session.'+key,{'svd_and_inverse':5*f*cols+2*k*k,
            'readin_readout':4*f*q,'residuals':4*q*cols}, 4*q*f*cols+4*f*q*min(f,q))
        ui,si,vi=np.linalg.svd(Cs,full_matrices=False)
        keep=si>rcond*si[0] if len(si) and si[0]>0 else np.zeros(len(si),dtype=bool)
        need(bool(keep.any()), 'nonzero session rank')
        inverse=(vi[keep].T/si[keep])@ui[:,keep].T
        A=Z@inverse
        ua,sa,va=np.linalg.svd(A,full_matrices=False)
        ka=sa>rcond*sa[0] if len(sa) and sa[0]>0 else np.zeros(len(sa),dtype=bool)
        need(bool(ka.any()), 'nonzero PCR map rank')
        B=(va[ka].T/sa[ka])@ua[:,ka].T
        denom=float(np.linalg.norm(A))
        resid=float(np.linalg.norm(A@B@A-A))/denom
        need(math.isfinite(resid) and resid<=tol, 'pseudoinverse consistency')
        readins[key]=seal_array(np,A,budget,'readin.'+key)
        readouts[key]=seal_array(np,B,budget,'readout.'+key)
        diagnostics[key]={'session_rank':int(keep.sum()),'map_rank':int(ka.sum()),
            'pseudoinverse_relative_residual':resid,'prediction_squared_error':float(np.linalg.norm(Z-A@Cs)**2)}
    arrays={'shared_scores':seal_array(np,Z,budget,'shared_scores'),
        'shared_spectrum':seal_array(np,S,budget,'shared_spectrum')}
    for key in ordered:
        arrays['readin/'+key]=readins[key];arrays['readout/'+key]=readouts[key]
        arrays['mean/'+key]=seal_array(np,offsets[key],budget,'mean.'+key)
        arrays['session_matrix/'+key]=seal_array(np,matrices[key],budget,'session_matrix.'+key)
    support={'sessions':{k:sessions[k]['support'] for k in ordered}}
    state={'kind':'pcr_stitch_initialization_v1','profile':json.loads(json.dumps(profile)),
        'support':support,'support_pin':identity(support),
        'input_data_pins':{k:sessions[k]['input_data_pins'] for k in ordered},
        'arrays':arrays,'diagnostics':diagnostics}
    state['identity']=state_identity(state)
    return state
