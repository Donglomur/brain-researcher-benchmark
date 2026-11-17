"""R1 public schemas and complete fixed configuration enumeration."""
import hashlib
import json
import math

TASK = 'NEURAL-049'
VIEWS = ('C', 'N', 'NC', 'NC_D')
ENDPOINTS = ('angle', 'magnitude', 'speed')
WINDOWS = tuple((float(k), float(k+1)) for k in range(-5, 5)) + ((-1.5,-1.0),(0.0,0.5))
BANDS = ((1,4),(4,8),(8,32),(32,55),(65,76),(76,100),(100,115),(125,175),(185,200))
SEED_VERSION = 'NEURAL049.curated-retrospective.v1.T'

def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def candidate_specs():
    out=[]
    for exponent in range(-6,3):
        out.append({'family':'R','lambda':10.0**exponent,'id':'R-'+str(exponent)})
    for leaves in (4,16):
        for l2 in (1,10):
            for trees in (100,300):
                out.append({'family':'B','leaves':leaves,'leaf_l2':l2,'trees':trees,
                            'id':f'B-{leaves}-{l2}-{trees}'})
    for width in (16,32):
        for decay in (0.001,0.1):
            for epochs in (80,240):
                out.append({'family':'T','width':width,'decay':decay,'epochs':epochs,
                            'id':f'T-{width}-{decay}-{epochs}'})
    # Fresh primitive copies: callers cannot mutate the source enumeration.
    return tuple(out)

def config_admit(config):
    if type(config) is not dict or not any(canonical(config)==canonical(x) for x in candidate_specs()):
        raise ValueError('not one of the complete 25 configurations')
    return dict(config)

def scope_admit(scope, batch, config):
    required={'task','implementation','person','view','endpoint','training_days','training_ids',
              'base_generation','input_identity','source_identity','environment','axis'}
    if type(scope) is not dict or set(scope)!=required:
        raise ValueError('exact fit scope keys required')
    if scope['task']!=TASK or scope['implementation']!='R1' or scope['view'] not in VIEWS or scope['endpoint'] not in ENDPOINTS:
        raise ValueError('wrong scientific scope')
    if scope['person'] not in tuple(f'{i:02d}' for i in range(1,13)):
        raise ValueError('unknown person')
    days=scope['training_days']; ids=scope['training_ids']
    if type(days) is not list or not days or any(type(x) is not int or x<=0 for x in days) or days!=sorted(set(days)):
        raise ValueError('training day identities')
    if type(ids) is not list or ids!=batch['ids'] or len(ids)!=len(set(ids)) or any(type(x) is not str or not x for x in ids):
        raise ValueError('training event identities')
    if scope['axis']!=batch['axis'] or type(scope['base_generation']) is not str or not scope['base_generation']:
        raise ValueError('axis/generation identity')
    for key in ('input_identity','source_identity'):
        if type(scope[key]) is not dict or not scope[key]: raise ValueError('missing input/source commitments')
    environment(scope['environment'])
    canonical(scope)

def environment(e):
    required={'qualified','receipt','numpy_version','torch_version','device','shared_monotonic_domain',
              'deterministic_algorithms','native_workspace_bytes'}
    if type(e) is not dict or set(e)!=required or e['qualified'] is not True:
        raise ValueError('independent numerical qualification absent')
    if type(e['receipt']) is not str or len(e['receipt'])!=64 or any(x not in '0123456789abcdef' for x in e['receipt']):
        raise ValueError('qualification receipt identity')
    if e['shared_monotonic_domain'] is not True or e['deterministic_algorithms'] is not True:
        raise ValueError('clock/deterministic qualification absent')
    if e['device'] not in ('cpu','cuda') or type(e['native_workspace_bytes']) is not int or e['native_workspace_bytes']<0:
        raise ValueError('device/workspace contract')
    if not all(type(e[k]) is str and e[k] for k in ('numpy_version','torch_version')):
        raise ValueError('exact numerical versions required')
    return e

def numpy_checked(e):
    environment(e)
    import numpy as np
    if np.__version__!=e['numpy_version']: raise ValueError('numpy environment differs')
    return np

def seed_base(scope, width, stream):
    return [SEED_VERSION,'T',scope['endpoint'],scope['person'],scope['training_days'],
            scope['training_ids'],scope['base_generation'],width,stream]

def counter(base, *tail):
    # No floating values or dicts in a random tuple; architecture/config identity
    # excludes view, implementation, decay, epoch budget and held outcomes.
    def valid(x):
        return type(x) in (str,int) or (type(x) is list and all(valid(v) for v in x))
    obj=base+list(tail)
    if not valid(obj): raise ValueError('invalid counter tuple')
    return int.from_bytes(hashlib.sha256(canonical(obj)).digest()[:8], 'big')

def uniform(base, *tail):
    return (counter(base,*tail)>>11)*2.0**-53

def projection(np, raw, endpoint):
    if not np.isfinite(raw).all(): raise ValueError('nonfinite raw prediction')
    if endpoint=='angle': return np.clip(raw,-90.0,90.0)
    if endpoint in ('magnitude','speed'): return np.maximum(raw,0.0)
    raise ValueError('unknown endpoint')


class CounterStream:
    """Exact incremental SHA of complete base+suffix JSON, never hash-of-hash.

    Cache SHA internal prefix state, not an encoded digest. copy/update produces
    exactly hashlib.sha256(canonical(base+suffix)); no change to random contract.
    """
    def __init__(self,base):
        # Validate base using the same closed set as the scalar reference helper.
        counter(base)
        self.prefix=hashlib.sha256(canonical(base)[:-1]+b',')
    def digest(self,*tail):
        if not tail: raise ValueError('counter suffix required')
        def valid(v): return type(v) in (str,int) or (type(v) is list and all(valid(x) for x in v))
        if not all(valid(v) for v in tail): raise ValueError('counter suffix type')
        h=self.prefix.copy();h.update(canonical(list(tail))[1:]);return h.digest()
    def uniform(self,*tail):
        return (int.from_bytes(self.digest(*tail)[:8],'big')>>11)*2**-53
