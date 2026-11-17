"""Concrete prospective shared Conv+Transformer; imports only inside actions.

No training is performed by importing this module. Exact recovered package
implementations are called, not replaced by a callback or approximate network.
"""
import failures
import copy, hashlib, importlib.metadata, json, math, os, platform, random, sys
from pathlib import Path
from . import core, numeric

SOURCE_IO=None

def environment():
    core.need(sys.version_info >= (3, 12), 'held author distribution Python>=3.12; exact interpreter belongs to qualified image')
    core.need(SOURCE_IO is not None,'Source-owned reference I/O scope established before environment reads')
    lock=SOURCE_IO.source_lock
    for relative,expected in lock['implementation_files'].items():
        SOURCE_IO.source(Path(__file__).parent.parent/relative,expected)
    observed = {'python': platform.python_version()}
    for name, expected in lock['versions'].items():
        actual = importlib.metadata.version(name)
        observed[name] = actual
        core.need(actual == expected or (name == 'torch' and actual.split('+')[0] == expected), 'exact admitted reference distribution ' + name)
    checked = {}
    for row in [*lock['installed_source'], *lock['complete_record_members']]:
        key = (row['distribution'], row['member'])
        expected = (row['bytes'], row['sha256'])
        if key in checked:
            core.need(checked[key] == expected, 'noncontradictory complete dependency record')
            continue
        checked[key] = expected
        distribution = importlib.metadata.distribution(row['distribution'])
        path = Path(distribution.locate_file(row['member']))
        core.need(path.is_file() and (not path.is_symlink()), 'ordinary installed dependency source')
        core.need(path.stat().st_size == row['bytes'], 'exact installed source extent')
        raw=SOURCE_IO.source(path,{'bytes':row['bytes'],'sha256':row['sha256']})
        core.need(len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'], 'captured release source identity ' + row['member'])
    return (lock, observed)

def setup(device):
    import numpy as np
    import torch
    core.need(device == 'cpu', 'qualified literal device')
    core.need(os.environ.get('PYTHONHASHSEED') == '65', 'prospective Python hash seed fixed before launch')
    random.seed(65)
    np.random.seed(65)
    torch.manual_seed(65)
    if device.startswith('cuda'):
        core.need(torch.cuda.is_available() and os.environ.get('CUBLAS_WORKSPACE_CONFIG') in (':4096:8', ':16:8'), 'qualified deterministic CUDA configuration')
        torch.cuda.manual_seed_all(65)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision('highest')
    return {'seed': 65, 'device': device, 'deterministic_algorithms': True, 'mixed_precision': False, 'TF32': False, 'backend_nondeterminism': 'unsupported deterministic operations fail; source settings do not establish empirical cross-host byte parity'}

def geometry(doc, channels, modality):
    core.need(type(doc) is dict and set(doc) == {'schema', 'modality', 'channel_names', 'channel_types', 'positions', 'source_method', 'layout_kind'} and (doc['modality'] == modality) and (doc['schema'] == 'neural066_geometry_v1'), 'Exact actual native-projection geometry metadata')
    core.need(doc['source_method'] == 'MNE1.11.0 minimalInfo/find_layout per-axis minmax; fullcoverage' and type(doc['layout_kind']) is str and doc['layout_kind'], 'Source-owned layout provenance, never an invented spatial adapter')
    core.need(len(doc['channel_names']) == len(doc['channel_types']) == len(doc['positions']) == channels and len(set(doc['channel_names'])) == channels, 'complete exact ordered geometry')
    core.need(all((type(s) is str and s for s in doc['channel_names'] + doc['channel_types'])), 'named typed channels')
    core.need(all((type(x) is list and len(x) == 2 and all((core.finite(v) and 0 <= v <= 1 for v in x)) for x in doc['positions'])), 'finite full2D coordinates; no missing sentinel')
    return doc['positions']

def build(channels, lock):
    import torch
    from neuraltrain.models.simpleconv import SimpleConvTimeAgg
    from neuraltrain.models.transformer import TransformerEncoder
    cfg = copy.deepcopy(lock['held_config']['ENCODER'])
    cfg['subject_layers_config'] = None
    cfg['merger_config']['per_subject'] = False
    encoder = SimpleConvTimeAgg(**cfg).build(n_in_channels=channels, n_outputs=2048)
    transformer = TransformerEncoder(**lock['held_config']['TRANSFORMER']).build(dim=2048)
    core.need(encoder.subject_layers is None and encoder.merger is not None and (encoder.merger.per_subject is False) and (tuple(encoder.merger.heads.shape) == (270, 2048)), 'shared merger and no SubjectLayers')

    class SentenceModel(torch.nn.Module):

        def __init__(self):
            super().__init__()
            self.encoder = encoder
            self.transformer = transformer
            self.readout = torch.nn.Linear(2048, 29)

        def forward(self, x, positions):
            core.need(x.ndim == 3 and tuple(x.shape[1:]) == (channels, 25) and (len(x) > 0), 'complete sentence [keys,C,25]')
            pos = positions.unsqueeze(0).expand(len(x), -1, -1)
            embedded = self.encoder(x, subject_ids=None, channel_positions=pos)
            core.need(tuple(embedded.shape) == (len(x), 2048), 'source attention temporal aggregate')
            sequence = embedded.unsqueeze(0)
            mask = torch.ones((1, len(x)), dtype=torch.bool, device=x.device)
            logits = self.readout(self.transformer(sequence, mask=mask).squeeze(0))
            core.need(tuple(logits.shape) == (len(x), 29) and torch.isfinite(logits).all().item(), 'finite complete29 logits')
            return logits
    result = SentenceModel()
    with torch.no_grad():
        for module in result.modules():
            if type(module).__module__ == 'x_transformers.x_transformers' and type(module).__name__ == 'AlibiPositionalBias':
                module(256, 256)
    return result

def replace_unused(model):
    """Source forward never uses Ua when queries=None; explicit inert convention."""
    import torch
    unused = {'encoder.time_agg_out.Ua.weight', 'encoder.time_agg_out.Ua.bias'}
    for name, param in list(model.named_parameters()):
        if isinstance(param, torch.nn.UninitializedParameter):
            core.need(name in unused, 'unsupported uninitialized used parameter')
            parent, leaf = name.rsplit('.', 1)
            module = model.get_submodule(parent)
            module._parameters[leaf] = torch.nn.Parameter(torch.zeros(1, device=param.device, dtype=param.dtype))

def full_state(model):
    state = dict(model.state_dict())
    for name, tensor in model.named_buffers():
        if name not in state:
            state['@buffer/' + name] = tensor
    return state

def state_arrays(model):
    import numpy as np
    import torch
    result = {}
    for name, tensor in full_state(model).items():
        core.need(not isinstance(tensor, torch.nn.UninitializedParameter), 'materialized complete state')
        a = tensor.detach().cpu().contiguous().numpy().copy()
        core.need(a.dtype in (np.dtype('float32'), np.dtype('int64')) and np.isfinite(a).all(), 'finite explicit float32/int64 full model state')
        result[name] = a
    return result

def state_hash(model):
    import torch
    digest = hashlib.sha256()
    for name, tensor in full_state(model).items():
        core.need(not isinstance(tensor, torch.nn.UninitializedParameter) and torch.isfinite(tensor).all().item(), 'finite materialized parameters/buffers')
        value = tensor.detach().cpu().contiguous().numpy()
        digest.update(name.encode())
        digest.update(str((value.dtype.str, value.shape)).encode())
        digest.update(memoryview(value).cast('B'))
    return digest.hexdigest()

def predict(model, features, rows, ids, norm, positions, device):
    import numpy as np
    import torch
    selected = core.subset(rows, ids)
    before = state_hash(model)
    model.eval()
    core.need(all((not m.training for m in model.modules())), 'recursive immutable eval mode')
    outputs = []
    with torch.no_grad():
        for sentence in selected:
            start = sentence['begin']
            stop = start + sentence['n_keys']
            x = torch.from_numpy(numeric.transform(features[start:stop], norm)).to(device)
            probs = model(x, positions).softmax(dim=-1).to(dtype=torch.float64).cpu().numpy()
            core.probabilities(probs.tolist(), sentence['n_keys'])
            outputs.append(probs)
    core.need(state_hash(model) == before, 'inference preserves complete parameters and running buffers')
    return np.concatenate(outputs, axis=0)

class FitFailure(ValueError):
    def __init__(self,error,history,best_epoch):
        super().__init__('Reference fit failed; original retained')
        failures.cleanup(self,'original_fit_error',error)
        failures.remember(self,'fit_failure',{'history':history,'best_epoch':best_epoch,'underlying_error_type':failures.kind(error)})


def fit(features, labels, rows, fit_ids, validation_ids, positions, grid_index, device, final_epochs=None):
    """One actual complete inner fit or one fresh final fit; no supplied trainer."""
    import numpy as np
    import torch
    core.need(type(grid_index) is int and grid_index in (0, 1), 'fixed learning-rate grid')
    fitting = core.subset(rows, fit_ids)
    validation = core.subset(rows, validation_ids) if validation_ids is not None else None
    core.need((validation is not None) == (final_epochs is None), 'inner validation or fresh fixed-epoch final fit')
    if validation is not None:
        core.need(not {r['person'] for r in fitting} & {r['person'] for r in validation} and (not {r['template'] for r in fitting} & {r['template'] for r in validation}), 'neither validation people nor templates in fitting')
    epochs = 300 if validation is not None else final_epochs
    core.need(type(epochs) is int and 1 <= epochs <= 300, 'full declared epoch count')
    lock, versions = environment()
    rng = setup(device)
    channels = features.shape[1]
    norm = numeric.fit_normalization(features, rows, fit_ids)
    model = build(channels, lock).to(device=device, dtype=torch.float32)
    pos = torch.as_tensor(positions, dtype=torch.float32, device=device)
    first = fitting[0]
    model.eval()
    with torch.no_grad():
        model(torch.from_numpy(numeric.transform(features[first['begin']:first['begin'] + first['n_keys']], norm)).to(device), pos)
    replace_unused(model)
    state_hash(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=core.GRID[grid_index], weight_decay=0.0001)
    steps_per_epoch = math.ceil(len(fitting) / 64)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=core.GRID[grid_index], pct_start=0.1, total_steps=epochs * steps_per_epoch)
    w = core.weights(fitting)
    offset = 0
    by_weight = {}
    for r in fitting:
        by_weight[r['id']] = w[offset:offset + r['n_keys']]
        offset += r['n_keys']
    order_rng = random.Random(65)
    history = []
    best_score = None
    best_epoch = None
    best_state = None
    best_probs = None
    stale = 0
    try:
        for epoch in range(1, epochs + 1):
            order = list(fitting)
            order_rng.shuffle(order)
            model.train()
            epoch_terms = []
            for begin in range(0, len(order), 64):
                batch = order[begin:begin + 64]
                factor = len(fitting) / len(batch)
                optimizer.zero_grad(set_to_none=True)
                for sentence in batch:
                    start = sentence['begin']
                    stop = start + sentence['n_keys']
                    x = torch.from_numpy(numeric.transform(features[start:stop], norm)).to(device)
                    target = torch.as_tensor(labels[start:stop], dtype=torch.long, device=device)
                    logits = model(x, pos)
                    loss = torch.nn.functional.cross_entropy(logits, target, reduction='none')
                    weight = torch.as_tensor(by_weight[sentence['id']], dtype=torch.float32, device=device)
                    objective = (loss * weight).sum()
                    core.need(torch.isfinite(objective).item(), 'finite fit objective')
                    epoch_terms.append(float(objective.detach().double().cpu()))
                    (factor * objective).backward()
                core.need(all((p.grad is None or torch.isfinite(p.grad).all().item() for p in model.parameters())), 'finite full accumulated gradients')
                optimizer.step()
                scheduler.step()
                state_hash(model)
            record = {'epoch': epoch, 'training_weighted_CE': math.fsum(epoch_terms), 'optimizer_steps': epoch * steps_per_epoch}
            if validation is not None:
                prob = predict(model, features, rows, validation_ids, norm, pos, device)
                score = core.person_cer(validation, core.truth_by_sentence(validation, labels), core.split_predictions(validation, prob.tolist()))['mean_person_CER']
                record['validation_person_CER'] = score
                if best_score is None or score < best_score:
                    best_score = score
                    best_epoch = epoch
                    best_state = state_arrays(model)
                    best_probs = prob.copy()
                    stale = 0
                else:
                    stale += 1
            history.append(record)
            if validation is not None and stale == 30:
                break
        if validation is None:
            best_epoch = epochs
            best_state = state_arrays(model)
        core.need(best_state is not None, 'complete fitted state')
        config = {'kind': 'R2', 'channels': channels, 'grid_index': grid_index, 'max_lr': core.GRID[grid_index], 'epochs': best_epoch, 'seed_backend': rng, 'versions': versions, 'no_subject_layers': True, 'shared_merger': True, 'unused_state_convention': 'source-unused Ua lazy weight/bias replaced with finite zero length-one Parameters; prospective serialization only, no historical byte-parity claim', 'positional_buffer_convention': 'source ALiBi fixed256 domain precomputed before inputs; all nonpersistent buffers exported and checked immutable'}
        arrays = {**{'state/' + k: v for k, v in best_state.items()}, **{'normalization/' + k: v for k, v in norm.items()}}
        return (config, arrays, {'history': history, 'best_epoch': best_epoch, 'validation_probabilities': best_probs})
    except Exception as error:
        failures.hold(error, 'caught')
        failures.remember(error,'fit_failure',{'history':history,'best_epoch':best_epoch,'underlying_error_type':failures.kind(error)})
        raise

def restore(config, arrays, device):
    import numpy as np
    import torch
    core.need(config['kind'] == 'R2' and config['no_subject_layers'] is True and (config['shared_merger'] is True), 'exact shared reference model')
    lock, versions = environment()
    core.need(config['versions'] == versions, 'same exact fitted reference environment')
    setup(device)
    model = build(config['channels'], lock).to(device=device, dtype=torch.float32)
    ua = model.encoder.time_agg_out.Ua
    ua.weight = torch.nn.Parameter(torch.zeros(1, device=device))
    ua.bias = torch.nn.Parameter(torch.zeros(1, device=device))
    persistent = set(model.state_dict())
    expected = set(full_state(model))
    provided = {k.removeprefix('state/') for k in arrays if k.startswith('state/')}
    core.need(expected == provided and set(arrays) == {'state/' + n for n in expected} | {'normalization/mean', 'normalization/scale', 'normalization/variance'}, 'complete exact model and normalization keys')
    state = {k: torch.from_numpy(np.asarray(arrays['state/' + k])).to(device) for k in persistent}
    model.load_state_dict(state, strict=True)
    core.need(all((not isinstance(p, torch.nn.UninitializedParameter) for p in model.parameters())), 'all used state restored')
    actual = state_arrays(model)
    for name, value in actual.items():
        core.need(value.dtype == arrays['state/' + name].dtype and np.array_equal(value, arrays['state/' + name]), 'exact dtype/value state restoration')
    for name in ('encoder.time_agg_out.Ua.weight', 'encoder.time_agg_out.Ua.bias'):
        core.need(actual[name].shape == (1,) and np.equal(actual[name], 0).all(), 'literal unused Ua zero state')
    model.eval()
    return (model, {k: arrays['normalization/' + k] for k in ('mean', 'scale', 'variance')})
