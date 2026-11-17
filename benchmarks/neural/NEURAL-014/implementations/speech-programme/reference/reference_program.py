"""Frozen standalone NEURAL014 reference composition. Source-only, never trained here.

Original compact GRU/CTC baseline, not author weights or the paper's decoder.
Four independently supervised modes; scientific execution is not authorized by
source construction. Only stdlib/NumPy import eagerly; Torch loads lazily.
"""
import argparse
from collections import Counter
import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import stat
import sys
import zipfile
import numpy as np

SEED = 14014
MAX_TOKENS = 2048
MAX_CASES = 50000
MAX_STEPS = 100000
MAX_JSON = 64000000
MODEL_CAP = 64000000


# Exact helpers captured from protocol.py
def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()



# Exact helpers captured from tokens.py
SOURCE_CLASSES = ('BLANK', 'AA', 'AE', 'AH', 'AO', 'AW', 'AY', 'B', 'CH',
                  'D', 'DH', 'EH', 'ER', 'EY', 'F', 'G', 'HH', 'IH', 'IY',
                  'JH', 'K', 'L', 'M', 'N', 'NG', 'OW', 'OY', 'P', 'R',
                  'S', 'SH', 'T', 'TH', 'UH', 'UW', 'V', 'W', 'Y', 'Z',
                  'ZH', ' | ')

TOKENS = tuple(x.strip() for x in SOURCE_CLASSES[1:])

TOKEN_SET = frozenset(TOKENS)

class ContractError(ValueError):
    pass

def need(ok, why):
    if not ok:
        raise ContractError(why)

def normalize_tokens(value):
    """Formatting only: ASCII case and whitespace. No stress/CTC/LM repair."""
    if type(value) is str:
        need(len(value) <= MAX_TOKENS * 8 and value.isascii(), 'bounded ASCII token string')
        parts = value.split()
    else:
        need(type(value) is list and len(value) <= MAX_TOKENS, 'token list or whitespace string')
        parts = value
    need(len(parts) <= MAX_TOKENS, 'token count exceeds declared interface bound')
    result = []
    for token in parts:
        need(type(token) is str and len(token) <= 8 and token.isascii(), 'ASCII token required')
        token = token.strip().upper()
        need(token in TOKEN_SET, 'unknown token, stress suffix or CTC blank')
        result.append(token)
    return result

def edit_counts(reference, prediction):
    """Unit-cost Levenshtein; tie order diagonal, deletion, insertion.

    Only total distance is unique in general. I/D/S are a deterministic minimum
    alignment decomposition, not independently observed phonetic events.
    """
    previous = [(j, 0, 0, j) for j in range(len(prediction) + 1)]
    for i, ref in enumerate(reference, 1):
        current = [(i, 0, i, 0)]
        for j, pred in enumerate(prediction, 1):
            d, s, deletion, insertion = previous[j - 1]
            sub = int(ref != pred)
            diagonal = (d + sub, s + sub, deletion, insertion)
            d, s, deletion, insertion = previous[j]
            drop = (d + 1, s, deletion + 1, insertion)
            d, s, deletion, insertion = current[-1]
            add = (d + 1, s, deletion, insertion + 1)
            current.append(min((diagonal, drop, add), key=lambda x: x[0]))
        previous = current
    d, s, deletion, insertion = previous[-1]
    return {'distance': d, 'substitutions': s, 'deletions': deletion, 'insertions': insertion}



# Exact helpers captured from io_contract.py
def ordinary(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Linked path refused")
    return path

def fresh(path):
    path = ordinary(path)
    if path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise ValueError("Fresh output with existing ordinary parent required")
    return path

def capture(path, cap=64_000_000):
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_nlink != 1 or not 0 < a.st_size <= cap:
            raise ValueError("Bounded ordinary single-link file required")
        with os.fdopen(fd, "rb", closefd=False) as f:
            body = f.read(cap + 1)
        b, c = os.fstat(fd), os.lstat(path)
        fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if len(body) != a.st_size or fields(a) != fields(b) or fields(a) != fields(c):
            raise ValueError("Input identity changed during capture")
        return body
    finally:
        os.close(fd)

def parse(body):
    text = body.decode("utf-8")
    depth, quoted, escape = 0, False, False
    for c in text:
        if quoted:
            if escape: escape = False
            elif c == "\\": escape = True
            elif c == '"': quoted = False
        elif c == '"': quoted = True
        elif c in "[{":
            depth += 1
            if depth > 48: raise ValueError("JSON nesting bound")
        elif c in "]}": depth -= 1
    def pairs(rows):
        out = {}
        for k, v in rows:
            if k in out: raise ValueError("Duplicate JSON field")
            out[k] = v
        return out
    def integer(s):
        if len(s) > 18: raise ValueError("JSON integer bound")
        return int(s)
    def number(s):
        x = float(s)
        if not math.isfinite(x): raise ValueError("Nonfinite JSON number")
        return x
    def reject(s): raise ValueError("Nonfinite JSON constant")
    return json.loads(text, object_pairs_hook=pairs, parse_int=integer, parse_float=number, parse_constant=reject)

def load(path, cap=64_000_000):
    return parse(capture(path, cap))

def put(path, value):
    path = fresh(path)
    body = canonical(value) + b"\n"
    if len(body) > 64_000_000: raise ValueError("JSON output cap")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(body); f.flush(); os.fsync(f.fileno())



# Exact helpers captured from reference.py
def feature(view_root, row):
    pin = row["features"]
    require(pin["path"] == "arrays/" + row["id"] + ".npy", "Exact candidate feature path")
    b = capture(view_root / pin["path"], 409_601_024)
    require(len(b) == pin["bytes"] and hashlib.sha256(b).hexdigest() == pin["sha256"], "Feature identity")
    f = io.BytesIO(b); version = np.lib.format.read_magic(f)
    require(version in ((1, 0), (2, 0)), "Primitive NPY version")
    reader = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
    shape, order, dtype = reader(f)
    require(shape == (row["steps"], 512) and 0 < row["steps"] <= 100000 and not order and
            not dtype.hasobject and dtype.kind == "f" and dtype.itemsize in (4, 8) and
            len(b) - f.tell() == row["steps"] * 512 * dtype.itemsize, "Complete floating feature geometry")
    x = np.frombuffer(b, dtype=dtype, offset=f.tell()).reshape(shape)
    require(np.isfinite(x).all(), "Finite feature values")
    return x

def moments(matrices):
    """Training-only anchored Welford merge; exact constant columns use scale1."""
    n = 0; mean = np.zeros(512); m2 = np.zeros(512)
    lo = np.full(512, np.inf); hi = np.full(512, -np.inf)
    for x in matrices:
        x = np.asarray(x, dtype=np.float64)
        require(x.ndim == 2 and x.shape[1] == 512 and len(x) and np.isfinite(x).all(), "Finite training geometry")
        lo = np.minimum(lo, x.min(axis=0)); hi = np.maximum(hi, x.max(axis=0))
        mu = x[0] + np.mean(x - x[0], axis=0)
        local = np.sum(np.square(x - mu), axis=0)
        delta = mu - mean; total = n + len(x)
        m2 += local + np.square(delta) * (n * len(x) / total)
        mean += delta * (len(x) / total); n = total
        require(np.isfinite(mean).all() and np.isfinite(m2).all(), "Unrepresentable normalization; no imputation")
    require(n > 0, "Training support required")
    mean[lo == hi] = lo[lo == hi]
    scale = np.sqrt(m2 / n); scale[lo == hi] = 1
    require(np.isfinite(scale).all() and np.all(scale > 0), "Positive training scales")
    return mean, scale

def ctc_greedy(ids):
    out = []; previous = None
    for i in ids:
        i = int(i); require(0 <= i <= 40, "CTC class range")
        if i != previous and i != 0: out.append(TOKENS[i - 1])
        previous = i
    return normalize_tokens(out)

def language_prior(rows):
    counts = Counter(tuple(normalize_tokens(r["tokens"])) for r in rows if r["role"] in ("train", "calibration"))
    require(bool(counts), "Training/calibration tokens required")
    # Unconditioned empirical sentence-mode prior, lexical tie by token tuple.
    return list(min(counts, key=lambda s: (-counts[s], s)))

def libraries():
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    import torch
    require(torch.__version__.split("+")[0] == "2.6.0" and np.__version__ == "2.2.6", "Frozen reference dependencies")
    random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
    torch.set_num_threads(1); torch.use_deterministic_algorithms(True)
    return torch

def network(torch):
    class Net(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.input = torch.nn.Linear(512, 128)
            self.gru = torch.nn.GRU(128, 128, num_layers=2, batch_first=True, dropout=0)
            self.output = torch.nn.Linear(128, 41)
        def forward(self, x):
            h, _ = self.gru(torch.tanh(self.input(x)))
            return self.output(h)
    return Net()

def input_tensor(torch, root, row, center, scale, device):
    x = (feature(root, row).astype(np.float64) - center) / scale
    require(np.isfinite(x).all(), "Finite normalized values")
    # Explicit baseline-only clipping, not a source data transformation.
    return torch.from_numpy(np.clip(x, -10, 10).astype(np.float32)).to(device)[None]

def update(torch, model, opt, root, row, center, scale, device):
    classes = [TOKENS.index(t) + 1 for t in normalize_tokens(row["tokens"])]
    require(row["steps"] >= len(classes) + sum(a == b for a, b in zip(classes, classes[1:])), "CTC alignment infeasible; refuse baseline trial")
    x = input_tensor(torch, root, row, center, scale, device)
    logp = model(x).log_softmax(-1).transpose(0, 1)
    loss = torch.nn.functional.ctc_loss(logp, torch.tensor(classes, dtype=torch.long, device=device),
        torch.tensor([row["steps"]], dtype=torch.long), torch.tensor([len(classes)], dtype=torch.long),
        blank=0, reduction="mean", zero_infinity=False)
    require(bool(torch.isfinite(loss)), "Finite CTC loss required")
    opt.zero_grad(); loss.backward()
    torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1, error_if_nonfinite=True)
    opt.step()

def predict(torch, model, root, rows, center, scale, device):
    model.eval(); result = {}
    with torch.no_grad():
        for row in sorted(rows, key=lambda r: r["id"]):
            ids = model(input_tensor(torch, root, row, center, scale, device)).argmax(-1)[0].cpu().tolist()
            result[row["id"]] = ctc_greedy(ids)
    return result


# New transport/admission composition; mathematical helpers above are unchanged.
STATE_SHAPES = {
    'input.weight': (128,512), 'input.bias': (128,),
    'gru.weight_ih_l0': (384,128), 'gru.weight_hh_l0': (384,128),
    'gru.bias_ih_l0': (384,), 'gru.bias_hh_l0': (384,),
    'gru.weight_ih_l1': (384,128), 'gru.weight_hh_l1': (384,128),
    'gru.bias_ih_l1': (384,), 'gru.bias_hh_l1': (384,),
    'output.weight': (41,128), 'output.bias': (41,),
}
MODEL_SPEC = {k:(shape, np.dtype('<f4')) for k,shape in STATE_SHAPES.items()}
MODEL_SPEC.update({'normalization_center':((512,),np.dtype('<f8')),
                   'normalization_scale':((512,),np.dtype('<f8')),
                   'metadata_generation':((64,),np.dtype('uint8')),
                   'metadata_selected_epoch':((1,),np.dtype('<i8')),
                   'metadata_artifact_kind':((1,),np.dtype('uint8'))})


def sha256_string(value):
    return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value)


def validate_input(value, mode):
    require(type(value) is dict and set(value)=={'schema','mode','generation','rows'}, 'Exact program input fields')
    require(value['schema']=='neural014-program-input-v1' and value['mode']==mode
            and mode in ('fit','adapt','infer','prior') and sha256_string(value['generation']), 'Program schema/mode/generation')
    rows=value['rows']
    require(type(rows) is list and 0<len(rows)<=MAX_CASES, 'Complete bounded nonempty rows')
    ids=set(); roles=set(); sessions={}; clean=[]
    for row in rows:
        require(type(row) is dict, 'Object row')
        if mode=='prior':
            require(set(row)=={'role','tokens'} and row['role'] in ('train','calibration'),
                    'Prior receives only training/calibration token sequences, no identifiers or timing')
            tokens=normalize_tokens(row['tokens']); require(bool(tokens),'Nonempty source target')
            clean.append({'role':row['role'],'tokens':tokens}); roles.add(row['role']); continue
        labeled = mode in ('fit','adapt')
        fields={'id','session','role','steps','features'} | ({'tokens'} if labeled else set())
        require(set(row)==fields, 'Exact role row; no held labels or side information')
        ident=row['id']; session=row['session']; role=row['role']; steps=row['steps']; pin=row['features']
        require(sha256_string(ident) and ident not in ids,'Unique opaque trial ID')
        require(type(session) is str and 0<len(session)<=128 and session.isascii()
                and '\x00' not in session,'Bounded operator session alias')
        allowed={'fit':('train','development'),'adapt':('calibration',),'infer':('query',)}[mode]
        require(role in allowed,'Only mode-permitted rows')
        require(type(steps) is int and 0<steps<=MAX_STEPS,'Full bounded trial steps')
        require(type(pin) is dict and set(pin)=={'path','bytes','sha256'}
                and pin['path']=='arrays/'+ident+'.npy' and type(pin['bytes']) is int
                and 0<pin['bytes']<=409601024 and sha256_string(pin['sha256']), 'Exact feature pin')
        item=dict(row)
        if labeled:
            item['tokens']=normalize_tokens(row['tokens']); require(bool(item['tokens']),'Nonempty source target')
            if role in ('train','calibration'):
                labels=item['tokens']
                require(steps>=len(labels)+sum(a==b for a,b in zip(labels,labels[1:])),
                        'CTC alignment infeasible; refuse complete reference before fitting')
        ids.add(ident); roles.add(role); sessions.setdefault(role,set()).add(session); clean.append(item)
    if mode=='fit':
        require(roles=={'train','development'} and len(sessions['train'])==27
                and len(sessions['development'])==9 and not sessions['train']&sessions['development'],
                'All27 training and9 development sessions, with nonempty disjoint support')
    elif mode=='adapt':
        require(len(rows)<=20 and len(sessions['calibration'])==1,'Complete nonempty one-session calibration prefix1..20')
    elif mode=='infer':
        require(len(rows)==1,'Exactly one complete query, no cross-query state')
    else:
        require(roles=={'train','calibration'},'Prior requires complete training and same-session calibration tokens')
    return {**value,'rows':clean}


def primitive_npz_bytes(values):
    """Deterministic primitive ZIP_STORED NPZ; no pickle/metadata timestamps."""
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED,allowZip64=False) as z:
        for key in sorted(values):
            array=np.asarray(values[key])
            require(type(key) is str and key and '/' not in key and '\\' not in key
                    and not array.dtype.hasobject and array.dtype.kind in 'fiu', 'Primitive fixed model members')
            f=io.BytesIO(); np.lib.format.write_array(f,np.ascontiguousarray(array),version=(1,0),allow_pickle=False)
            info=zipfile.ZipInfo(key+'.npy',date_time=(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_STORED; info.create_system=3
            info.external_attr=0o600<<16; info.flag_bits=0
            z.writestr(info,f.getvalue())
    body=out.getvalue(); require(0<len(body)<=MODEL_CAP,'Complete bounded model artifact')
    return body


def primitive_npz_arrays(body, spec):
    """Read each exact-sized primitive member once; reject object/shape tricks."""
    require(type(body) is bytes and 0<len(body)<=MODEL_CAP,'Bounded opaque model bytes')
    values={}
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        infos=z.infolist(); expected=[k+'.npy' for k in sorted(spec)]
        require([i.filename for i in infos]==expected and len(set(expected))==len(expected)
                and all(i.compress_type==zipfile.ZIP_STORED and not i.flag_bits&1 for i in infos)
                and sum(i.file_size for i in infos)<=MODEL_CAP,'Exact bounded primitive model roster')
        for info in infos:
            key=info.filename[:-4]; shape,dtype=spec[key]; dtype=np.dtype(dtype)
            expected_bytes=math.prod(shape)*dtype.itemsize
            require(expected_bytes<info.file_size<=expected_bytes+1024,'Bounded exact model member allocation')
            raw=z.read(info); f=io.BytesIO(raw); version=np.lib.format.read_magic(f)
            require(version in ((1,0),(2,0)),'Primitive model NPY version')
            reader=np.lib.format.read_array_header_1_0 if version==(1,0) else np.lib.format.read_array_header_2_0
            actual_shape,order,actual_dtype=reader(f)
            require(actual_shape==shape and not order and actual_dtype==dtype and not actual_dtype.hasobject
                    and len(raw)-f.tell()==expected_bytes,'Exact model array shape/dtype/payload')
            values[key]=np.frombuffer(raw,dtype=dtype,offset=f.tell()).reshape(shape)
    return values


def validate_model_values(values,generation,expected_kind=None):
    require(set(values)==set(MODEL_SPEC),'Exact mathematical state plus fixed metadata')
    for key,(shape,dtype) in MODEL_SPEC.items():
        value=values[key]
        require(type(value) is np.ndarray and value.shape==shape and value.dtype==dtype
                and np.isfinite(value).all(),'Finite exact model array schema')
    require(bytes(values['metadata_generation'])==generation.encode('ascii'),'Frozen model generation')
    epoch=int(values['metadata_selected_epoch'][0]); kind=int(values['metadata_artifact_kind'][0])
    require(1<=epoch<=10 and kind in (0,1) and (expected_kind is None or kind==expected_kind),
            'Selected epoch and required base/adapted model lineage')
    require(np.all(values['normalization_scale']>0),'Positive frozen train-only scales')
    return epoch,kind


def model_values(model,center,scale,generation,epoch,kind):
    values={k:v.detach().cpu().numpy() for k,v in model.state_dict().items()}
    values.update({'normalization_center':center,'normalization_scale':scale,
        'metadata_generation':np.frombuffer(generation.encode('ascii'),dtype=np.uint8).copy(),
        'metadata_selected_epoch':np.array([epoch],dtype='<i8'),
        'metadata_artifact_kind':np.array([kind],dtype=np.uint8)})
    validate_model_values(values,generation,kind)
    return values


def save_model(path,model,center,scale,generation,epoch,kind):
    path=fresh(path); body=primitive_npz_bytes(model_values(model,center,scale,generation,epoch,kind))
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:
        f.write(body); f.flush(); os.fsync(f.fileno())


def load_model(torch,path,model,generation,expected_kind=None):
    values=primitive_npz_arrays(capture(path,MODEL_CAP),MODEL_SPEC)
    epoch,kind=validate_model_values(values,generation,expected_kind)
    require({k:tuple(v.shape) for k,v in model.state_dict().items()}==STATE_SHAPES,'Exact original network parameter layout')
    model.load_state_dict({k:torch.from_numpy(values[k].copy()) for k in STATE_SHAPES})
    return values['normalization_center'],values['normalization_scale'],epoch,kind


def fit(view,root,out,device):
    torch=libraries(); model=network(torch).to(device)
    fit_rows=sorted([r for r in view['rows'] if r['role']=='train'],key=lambda r:r['id'])
    dev=[r for r in view['rows'] if r['role']=='development']
    center,scale=moments(feature(root,r) for r in fit_rows)
    opt=torch.optim.Adam(model.parameters(),lr=0.001)
    best,state,epoch_best=None,None,None
    for epoch in range(1,11):
        model.train()
        order=np.random.default_rng(SEED+epoch).permutation(len(fit_rows))
        for j in order: update(torch,model,opt,root,fit_rows[int(j)],center,scale,device)
        predictions=predict(torch,model,root,dev,center,scale,device)
        sums={}
        for row in dev:
            totals=sums.setdefault(row['session'],[0,0])
            totals[0]+=edit_counts(row['tokens'],predictions[row['id']])['distance']
            totals[1]+=len(row['tokens'])
        metric=sum(a/b for a,b in sums.values())/len(sums)
        if best is None or metric<best:
            best,epoch_best=metric,epoch
            state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
    model.load_state_dict(state)
    save_model(out,model,center,scale,view['generation'],epoch_best,0)


def adapt(view,root,base,out,device):
    torch=libraries(); model=network(torch).to(device)
    center,scale,epoch,_=load_model(torch,base,model,view['generation'],expected_kind=0)
    calibration=sorted(view['rows'],key=lambda r:r['id'])
    for parameter in model.parameters(): parameter.requires_grad_(False)
    for parameter in model.input.parameters(): parameter.requires_grad_(True)
    opt=torch.optim.Adam(model.input.parameters(),lr=0.001)
    model.train()
    for step in range(100):
        update(torch,model,opt,root,calibration[step%len(calibration)],center,scale,device)
    save_model(out,model,center,scale,view['generation'],epoch,1)


def infer(view,root,base,out,device):
    torch=libraries(); model=network(torch).to(device)
    center,scale,_,_=load_model(torch,base,model,view['generation'])
    predictions=predict(torch,model,root,view['rows'],center,scale,device)
    ident=view['rows'][0]['id']; put(out,{'id':ident,'tokens':predictions[ident]})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('fit','adapt','infer','prior'))
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--model',type=Path)
    parser.add_argument('--model-output',type=Path)
    parser.add_argument('--output',type=Path)
    # Only the CPU condition is selected in this source transport. A different
    # device is a separate prospective runtime condition, not an implicit default.
    parser.add_argument('--device',choices=('cpu',),default='cpu')
    args=parser.parse_args()
    require(args.input==Path('/input/INPUT.json'),'Fixed input mount')
    expected_model=args.mode in ('adapt','infer')
    expected_model_output=args.mode in ('fit','adapt')
    expected_prediction=args.mode in ('infer','prior')
    require((args.model is not None)==expected_model and (args.model_output is not None)==expected_model_output
            and (args.output is not None)==expected_prediction,'Only mode-permitted CLI artifacts')
    if expected_model: require(args.model==Path('/model/model.bin'),'Fixed sealed model mount')
    if expected_model_output: require(args.model_output==Path('/output/model.bin'),'Fixed fresh model output')
    if expected_prediction: require(args.output==Path('/output/prediction.json'),'Fixed fresh prediction output')
    output=args.model_output if expected_model_output else args.output
    fresh(output)
    view=validate_input(load(args.input,MAX_JSON),args.mode)
    if args.mode=='prior':
        put(output,{'tokens':language_prior(view['rows'])})
    else:
        require(sys.version_info[:2]==(3,12),'Frozen Python3.12 reference runtime')
        if args.mode=='fit':fit(view,args.input.parent,output,args.device)
        elif args.mode=='adapt':adapt(view,args.input.parent,args.model,output,args.device)
        else:infer(view,args.input.parent,args.model,output,args.device)


if __name__=='__main__': main()
