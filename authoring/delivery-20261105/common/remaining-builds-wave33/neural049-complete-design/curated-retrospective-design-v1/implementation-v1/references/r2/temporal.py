"""Independent explicit patch-lowering graph and source-owned AdamW.

Torch supplies elementary tensor/autodiff operations only; no convolution,
optimizer, neural-network module, RNG or other implementation is called.
"""
import hashlib
import math
from .budget import require, encode
from .contracts import numpy, environment_check
from .features import standardized_waveform

VERSION = 'NEURAL049.curated-retrospective.v1.T'


def torch_library(environment):
    environment_check(environment, numerical=True, tensor=True)
    import torch
    torch.use_deterministic_algorithms(True)
    if hasattr(torch.backends, 'cuda'):
        torch.backends.cuda.matmul.allow_tf32 = False
    if hasattr(torch.backends, 'cudnn'):
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
    require(environment['device'] != 'cuda' or torch.cuda.is_available(), 'qualified device unavailable')
    return torch


def counter_bytes(scope, width, kind, suffix, budget):
    base = [VERSION, 'T', scope['endpoint'], scope['person'], scope['training_days'],
            scope['training_ids'], scope['base_generation'], width, kind]
    budget.ops(512+len(scope['training_ids'])*64, 'counter SHA source work bound')
    # json uses ordered arrays; no preliminary hash, implementation/view or targets.
    body = encode(base+list(suffix), budget, 'counter SHA tuple')
    return hashlib.sha256(body).digest()


def uniform(scope, width, kind, suffix, budget):
    return (int.from_bytes(counter_bytes(scope, width, kind, suffix, budget)[:8], 'big') >> 11)*2.**-53


def parameter_shapes(c, width):
    shapes = [('stem.weight', (width, 2*c, 25)), ('stem.bias', (width,))]
    for block in range(3):
        for conv in (1, 2):
            prefix = 'blocks.%d.conv%d' % (block, conv)
            shapes += [(prefix+'.weight', (width, width, 9)), (prefix+'.bias', (width,))]
    shapes += [('readout1.weight', (width, 20*width+6+48*c)), ('readout1.bias', (width,)),
               ('readout2.weight', (1, width)), ('readout2.bias', (1,))]
    return shapes


def initialize(scope, c, width, environment, budget):
    np, torch = numpy(), torch_library(environment)
    params = {}
    for name, shape in parameter_shapes(c, width):
        count = math.prod(shape)
        budget.arrays(count*12, 'parameter initialization buffers')
        if name.endswith('.bias'):
            a = np.zeros(shape, dtype=np.float32)
        else:
            kernel = shape[2] if len(shape) == 3 else 1
            bound = math.sqrt(6./((shape[0]+shape[1])*kernel))
            a = np.empty(shape, dtype=np.float32)
            flat = a.reshape(-1)
            for k in range(count):
                budget.tick('Xavier counter element')
                flat[k] = (2.*uniform(scope, width, 'weight', (name, k), budget)-1.)*bound
        params[name] = torch.tensor(a, dtype=torch.float32, device=environment['device'], requires_grad=True)
    return params


def lowered_conv(x, weight, bias, dilation, budget):
    import torch
    b, channels, length = x.shape
    outputs, inputs, kernel = weight.shape
    require(inputs == channels and kernel % 2 == 1 and dilation > 0, 'convolution axes')
    pad = (kernel//2)*dilation
    elements = b*channels*(length+2*pad) + 3*b*length*channels*kernel + 3*b*outputs*length
    budget.arrays(elements*4, 'explicit convolution patch/transpose/matmul buffers')
    budget.ops(2*b*length*outputs*channels*kernel, 'full explicit convolution matmul')
    zeros = torch.zeros((b, channels, pad), dtype=x.dtype, device=x.device)
    padded = torch.cat((zeros, x, zeros), dim=2)
    # Patch axis order is event,time,input-channel,kernel; weights out,input,kernel.
    patch = torch.stack([padded[:, :, k*dilation:k*dilation+length] for k in range(kernel)], dim=3)
    matrix = patch.permute(0, 2, 1, 3).contiguous().reshape(b*length, channels*kernel)
    y = matrix @ weight.reshape(outputs, channels*kernel).T + bias
    return y.reshape(b, length, outputs).permute(0, 2, 1).contiguous()


def gelu(x, budget):
    import torch
    budget.arrays(x.numel()*24, 'exact GELU intermediates')
    budget.ops(x.numel()*16, 'exact erf GELU')
    return .5*x*(1.+torch.erf(x/math.sqrt(2.)))


def dropout(x, scope, width, epoch, ids, layer, budget):
    np = numpy()
    import torch
    require(x.ndim in (2, 3) and x.shape[0] == len(ids), 'dropout axes')
    budget.arrays(x.numel()*12, 'counter dropout mask/copy/product')
    mask = np.empty(tuple(x.shape), dtype=np.float32)
    for b, event in enumerate(ids):
        for f in range(x.shape[1]):
            for time in range(x.shape[2] if x.ndim == 3 else 1):
                t = time if x.ndim == 3 else -1
                keep = uniform(scope, width, 'dropout', (epoch, event, layer, f, t), budget) >= .1
                if x.ndim == 3:
                    mask[b, f, time] = 1./.9 if keep else 0.
                else:
                    mask[b, f] = 1./.9 if keep else 0.
    return x * torch.tensor(mask, dtype=torch.float32, device=x.device)


def graph(params, x, scalar, scope, width, budget, *, epoch=None, ids=None):
    import torch
    require(x.shape[2] == 5000, 'full temporal support')
    h = gelu(lowered_conv(x, params['stem.weight'], params['stem.bias'], 1, budget), budget)
    budget.arrays(h.numel()*4, 'five-position average pooling')
    h = h.reshape(h.shape[0], width, 1000, 5).mean(dim=3)
    for block, dilation in enumerate((1, 4, 16)):
        prefix = 'blocks.%d.' % block
        branch = gelu(lowered_conv(h, params[prefix+'conv1.weight'], params[prefix+'conv1.bias'], dilation, budget), budget)
        if epoch is not None:
            branch = dropout(branch, scope, width, epoch, ids, prefix+'dropout', budget)
        branch = lowered_conv(branch, params[prefix+'conv2.weight'], params[prefix+'conv2.bias'], dilation, budget)
        budget.arrays(h.numel()*8, 'residual sum/scaling')
        h = gelu((h+branch)/math.sqrt(2.), budget)
    budget.arrays(h.numel()*8 + h.shape[0]*(40*width+scalar.shape[1])*4, 'ordered ten-bin mean/max pooling')
    parts = []
    for timebin in range(10):
        piece = h[:, :, 100*timebin:100*(timebin+1)]
        # torch.max(dim) routes tied gradients to the first index, unlike amax.
        parts.extend((piece.mean(dim=2), piece.max(dim=2).values))
    joined = torch.cat(parts+[scalar], dim=1)
    budget.arrays(joined.shape[0]*width*12, 'readout layers')
    budget.ops(joined.numel()*width*2, 'complete dense readout')
    h = gelu(joined @ params['readout1.weight'].T + params['readout1.bias'], budget)
    if epoch is not None:
        h = dropout(h, scope, width, epoch, ids, 'readout.dropout', budget)
    return (h @ params['readout2.weight'].T + params['readout2.bias']).reshape(-1)


def learning_rate(step, total):
    return .001 if total == 1 else 1e-5+(.001-1e-5)*(1.+math.cos(math.pi*(step-1)/(total-1)))/2.


def adamw_step(params, moments, step, total, decay, budget):
    import torch
    count = sum(p.numel() for p in params.values())
    budget.arrays(count*72, 'full gradient norm/AdamW intermediates')
    budget.ops(count*80, 'global norm and manual AdamW')
    norm2 = math.fsum(float((p.grad.to(torch.float64)**2).sum(dtype=torch.float64).item())
                      for p in params.values())
    require(math.isfinite(norm2) and norm2 >= 0, 'finite gradient norm')
    factor = min(1., 1./math.sqrt(norm2)) if norm2 else 1.
    rate = learning_rate(step, total)
    with torch.no_grad():
        for name, p in params.items():
            require(p.grad is not None and bool(torch.isfinite(p.grad).all()), 'complete finite gradients')
            g = (p.grad*factor).to(torch.float32)
            m, v = moments[name]
            m.mul_(.9).add_(g, alpha=.1)
            v.mul_(.999).add_(g*g, alpha=.001)
            mh, vh = m/(1.-.9**step), v/(1.-.999**step)
            wd = 0. if name.endswith('.bias') else decay
            p.copy_(p*(1.-rate*wd)-rate*mh/(torch.sqrt(vh)+1e-8))
            require(bool(torch.isfinite(p).all()), 'finite optimizer state')
            p.grad = None
    budget.tick('AdamW step completed')
    return norm2, rate


def tensor_bound(n, c, width, native_workspace):
    b = min(32, max(1, n))
    parameters = sum(math.prod(s) for _, s in parameter_shapes(c, width))
    patches = b*(2*c*25*5000 + 6*width*9*1000)
    activations = b*(2*c*5000 + width*5000 + 24*width*1000 + 20*width+6+48*c)
    # Retained graph, backward gradients, parameter/moment/update copies, host input.
    return 4*(16*patches+24*activations+32*parameters)+n*c*5000*32+native_workspace


def parameter_digest(params, budget):
    digest = hashlib.sha256()
    for name, value in params.items():
        budget.arrays(value.numel()*8, 'parameter commitment host-copy reservation')
        a = value.detach().cpu().numpy().copy()
        digest.update(encode([name, list(a.shape), 'float32'], budget, 'parameter commitment schema'))
        digest.update(memoryview(a).cast('B'))
    return digest.hexdigest()


def input_tensors(batch, rows, channels, view, scalar, environment, budget):
    np = numpy()
    import torch
    c = len(batch['axis'])
    budget.arrays(len(rows)*2*c*5000*16+len(rows)*scalar.shape[1]*12, 'complete minibatch host/device materialization')
    a = np.empty((len(rows), 2*c, 5000), dtype=np.float32)
    for k, row in enumerate(rows):
        a[k, :c] = standardized_waveform(batch, row, channels, view, budget)
        a[k, c:] = batch['mask'][row]
    return (torch.tensor(a, dtype=torch.float32, device=environment['device']),
            torch.tensor(scalar[rows], dtype=torch.float32, device=environment['device']))


def train(scope, batch, channel_state, scalar, y, config, budget):
    np = numpy()
    env, width = scope['environment'], config['width']
    torch = torch_library(env)
    n, c = len(batch['ids']), len(batch['axis'])
    bound = tensor_bound(n, c, width, env['native_workspace_bytes'])
    budget.workspace(bound, 'entire temporal training simultaneous bound')
    params = initialize(scope, c, width, env, budget)
    initial_pin = parameter_digest(params, budget)
    parameters = sum(p.numel() for p in params.values())
    budget.arrays(parameters*8, 'zero Adam first/second moments', live=bound)
    moments = {name: (torch.zeros_like(p), torch.zeros_like(p)) for name, p in params.items()}
    b = min(32, n)
    total = config['epochs']*((n+b-1)//b)
    step, roster_digest = 0, hashlib.sha256()
    for epoch in range(config['epochs']):
        budget.tick('full temporal epoch')
        budget.charge('allocation_bytes', n*256, 'shuffle key/row metadata')
        keyed = [(counter_bytes(scope, width, 'shuffle', (epoch, event), budget), event, r)
                 for r, event in enumerate(batch['ids'])]
        ordered = [r for _, _, r in sorted(keyed)]
        for start in range(0, n, b):
            rows = ordered[start:start+b]
            ids = [batch['ids'][r] for r in rows]
            step += 1
            roster_digest.update(encode([epoch, step, ids], budget, 'actual batch roster'))
            x, q = input_tensors(batch, rows, channel_state, scope['view'], scalar, env, budget)
            prediction = graph(params, x, q, scope, width, budget, epoch=epoch, ids=ids)
            budget.arrays(len(rows)*32+bound, 'backward graph and float64 loss reservation', live=bound)
            target = torch.tensor(y[rows], dtype=torch.float64, device=env['device'])
            # Common written precision ABI: preserve float64 standardized targets.
            difference = prediction.to(torch.float64)-target
            loss = (difference**2).sum(dtype=torch.float64)/len(rows)
            require(bool(torch.isfinite(loss)), 'finite training loss')
            loss.backward()
            adamw_step(params, moments, step, total, config['decay'], budget)
    require(step == total, 'full optimizer schedule')
    final_pin = parameter_digest(params, budget)
    arrays = {}
    for name, p in params.items():
        budget.arrays(p.numel()*12, 'final parameter and optimizer primitive export', live=bound)
        arrays['parameter/'+name] = p.detach().cpu().numpy().copy()
        arrays['adam_m/'+name] = moments[name][0].detach().cpu().numpy().copy()
        arrays['adam_v/'+name] = moments[name][1].detach().cpu().numpy().copy()
    budget.tick('full temporal fit completed')
    return arrays, {'steps': step, 'epochs': config['epochs'], 'batch_size': b,
                    'batch_roster_sha256': roster_digest.hexdigest(),
                    'initial_parameter_sha256': initial_pin, 'final_parameter_sha256': final_pin,
                    'parameter_order': [name for name, _ in parameter_shapes(c, width)]}


def infer(scope, batch, channel_state, scalar, config, arrays, budget):
    np = numpy()
    env, width = scope['environment'], config['width']
    torch = torch_library(env)
    n, c = len(batch['ids']), len(batch['axis'])
    bound = tensor_bound(n, c, width, env['native_workspace_bytes'])
    budget.workspace(bound, 'complete temporal inference bound')
    params = {}
    for name, shape in parameter_shapes(c, width):
        a = arrays['parameter/'+name]
        require(a.dtype == np.float32 and a.shape == shape and bool(np.isfinite(a).all()), 'parameter shape/value')
        budget.arrays(a.nbytes*2, 'sealed parameter tensor copy', live=bound)
        params[name] = torch.tensor(a, dtype=torch.float32, device=env['device'])
    budget.arrays(n*8, 'full temporal prediction', live=bound)
    out = np.empty(n, dtype=np.float64)
    with torch.no_grad():
        for start in range(0, n, 32):
            rows = list(range(start, min(n, start+32)))
            x, q = input_tensors(batch, rows, channel_state, scope['view'], scalar, env, budget)
            result = graph(params, x, q, scope, width, budget)
            out[rows] = result.cpu().numpy()
    return out
