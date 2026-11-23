"""Prospective native reference with an explicit local CPU operator profile.

No imports of tensor packages, data access, fitting or inference happen at import.
This is trusted operator source, never a common asset for the primary paper arm.
"""
from __future__ import annotations
from collections import OrderedDict
import hashlib
import importlib.metadata
from contextlib import nullcontext
import os
import sys
import time
import json
from pathlib import Path
import random
from types import ModuleType, SimpleNamespace

HERE = Path(__file__).resolve().parent
recipe = ModuleType('_reve_matched_recipe'); recipe.__file__ = str(HERE/'recipe.py')
exec(compile((HERE/'recipe.py').read_bytes(), recipe.__file__, 'exec'), recipe.__dict__)
AUTHOR_ADAPTER = HERE.parent/'original-physionet/author_adapter.py'
AUTHOR_ADAPTER_SHA = '0990eac5f5a478dfc6c00a0e8898d115e1ddc6049f58c8085ec69e2e7457aea1'
OPTIMIZER_SHA = '486342669b4d7d528d38d2aa4c84b312e14b9b60d73ea31dfc2439f0ce86035c'


def load_source(path, expected, name):
    raw = Path(path).read_bytes()
    recipe.need(hashlib.sha256(raw).hexdigest() == expected, 'pinned source changed: '+str(path))
    module = ModuleType(name); module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def file_pin(path, *, maximum_bytes=None):
    path = Path(path)
    recipe.need(path.is_file() and not path.is_symlink(), 'regular immutable file required')
    size = 0; sha = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            size += len(block)
            recipe.need(maximum_bytes is None or size <= maximum_bytes, 'file read extent exceeded')
            sha.update(block)
    return {'bytes': size, 'sha256': sha.hexdigest()}


# The CPU branch is a trusted local operator interface. It does not open the
# existing provider/installation gate or claim scientific qualification.
def prepare_environment(overlay):
    overlay = Path(overlay)
    recipe.need(overlay.is_dir() and not overlay.is_symlink(), "qualified isolated overlay directory required")
    installed = {dist.metadata["Name"].lower().replace("_", "-"): dist.version
                 for dist in importlib.metadata.distributions(path=[str(overlay)])}
    recipe.need(installed == recipe.CPU_OVERLAY_VERSIONS, "overlay must contain exactly the three selected distributions")
    sys.path.insert(0, str(overlay.resolve()))
    observed = {name: importlib.metadata.version(name) for name in recipe.CPU_RUNTIME_VERSIONS}
    recipe.need(observed == recipe.CPU_RUNTIME_VERSIONS, "selected local CPU distribution versions changed")
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                       "HF_HUB_DISABLE_TELEMETRY": "1", "TOKENIZERS_PARALLELISM": "false"})
    # A cooperative extra refusal, not an OS-level network/process sandbox.
    def no_external_calls(event, _args):
        if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system"}:
            raise RuntimeError("external calls are outside this CPU compatibility control")
    sys.addaudithook(no_external_calls)
    return observed



def install_math_attention(model, torch):
    from torch.nn.attention import SDPBackend, sdpa_kernel

    class MathAttention(torch.nn.Module):
        def forward(self, qkv):
            q, k, v = (value.reshape(value.shape[0], value.shape[1], 8, 64).transpose(1, 2)
                       for value in qkv.chunk(3, dim=-1))
            with sdpa_kernel(SDPBackend.MATH):
                result = torch.nn.functional.scaled_dot_product_attention(q, k, v)
            return result.transpose(1, 2).reshape(qkv.shape[0], qkv.shape[1], 512)

    for attention, _feedforward in model.encoder.transformer.layers:
        attention.attend = MathAttention()
        attention.use_flash = False



def construct_model(modules, torch, *, weights=None, complete_state=None, profile=recipe.CUDA_PROFILE):
    args = SimpleNamespace(embed_dim=512, depth=22, heads=8, head_dim=64,
                           mlp_dim_ratio=2.66, use_geglu=True)
    if complete_state is None:
        query = weights.pop("cls_query_token")
        encoder = modules["models.encoder"].REVE(args, 4, 200, 20, 0.0025)
        encoder.load_state_dict(weights, strict=True)
        model = modules["models.classifier"].ReveClassifier(
            encoder, n_classes=4, dropout=0.0, pooling="no", out_shape=recipe.FLAT)
        with torch.no_grad():
            model.cls_query_token.copy_(query)
    else:
        with torch.device("meta"):
            encoder = modules["models.encoder"].REVE(args, 4, 200, 20, 0.0025)
            model = modules["models.classifier"].ReveClassifier(
                encoder, n_classes=4, dropout=0.0, pooling="no", out_shape=recipe.FLAT)
        model.load_state_dict(complete_state, strict=True, assign=True)
    if profile == recipe.CPU_PROFILE:
        model.to(device="cpu", dtype=torch.float32)
        install_math_attention(model, torch)
    else:
        model.to("cuda")
    recipe.validate_shapes({key: list(value.shape) for key, value in model.state_dict().items()},
                           complete_classifier=True)
    recipe.need(sum(parameter.numel() for parameter in model.parameters()) == 69847556,
         "complete original classifier required")
    return model



def state_hashes(model):
    return {key: hashlib.sha256(value.detach().cpu().contiguous().numpy().tobytes()).hexdigest()
            for key, value in model.state_dict().items()}


def gradient_summary(model, torch):
    tensors = elements = nonzero = encoder_nonzero = 0
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            recipe.need(parameter.grad is None, "frozen parameter has a gradient: " + name)
            continue
        gradient = parameter.grad
        recipe.need(gradient is not None and bool(torch.isfinite(gradient).all()),
             "missing or nonfinite trainable gradient: " + name)
        nz = int(torch.count_nonzero(gradient))
        tensors += 1
        elements += gradient.numel()
        nonzero += nz
        if name.startswith("encoder."):
            encoder_nonzero += nz
    recipe.need(nonzero > 0, "all training gradients are zero")
    return {"tensor_count": tensors, "elements": elements, "nonzero_elements": nonzero,
            "encoder_nonzero_elements": encoder_nonzero}



def prepare_profile(profile, overlay):
    recipe.validate_profile(profile)
    if profile == recipe.CUDA_PROFILE:
        recipe.need(overlay is None, 'CUDA profile does not accept the CPU overlay')
        recipe.require_installation()
        return None
    recipe.need(overlay is not None, 'explicit CPU overlay binding required')
    return prepare_environment(overlay)


def verify_cpu_runtime(torch, np, safetensors, overlay):
    recipe.need(torch.get_default_dtype() == torch.float32, 'CPU constructor default must be float32')
    recipe.need({'torch':torch.__version__,'numpy':np.__version__,'safetensors':safetensors.__version__} ==
                {key:recipe.CPU_RUNTIME_VERSIONS[key] for key in ('torch','numpy','safetensors')},
                'imported CPU runtime version differs')
    overlay = Path(overlay).resolve()
    for name in recipe.CPU_RUNTIME_VERSIONS:
        module = importlib.import_module(name)
        origin = Path(module.__file__).resolve()
        recipe.need(origin.is_relative_to(overlay) == (name in recipe.CPU_OVERLAY_VERSIONS),
                    'module does not come from its selected overlay/shared location: '+name)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)


def model_logits(model, samples, positions, torch, profile, *, criterion=None, labels=None):
    device = 'cpu' if profile == recipe.CPU_PROFILE else 'cuda'
    context = nullcontext() if profile == recipe.CPU_PROFILE else torch.amp.autocast(device_type='cuda', dtype=torch.float16)
    # Native position jitter is in-place: CPU .to('cpu') would alias the caller.
    pos = positions.to(device)
    if profile == recipe.CPU_PROFILE: pos = pos.clone()
    with context:
        logits = model(samples.to(device), pos)
        if criterion is not None:
            return logits, criterion(logits, labels.to(device))
        return logits


class LimitedWriter:
    def __init__(self, stream):
        self.stream = stream
        self.requested_bytes = 0

    def write(self, data):
        self.requested_bytes += len(data)
        recipe.need(self.requested_bytes <= (320 * 1024 * 1024), "checkpoint cumulative write limit")
        return self.stream.write(data)

    def flush(self):
        self.stream.flush()



class PacketDataset:
    """Phase-local rows only; immutable mounts are authenticated by the qualified owner.

    At most eight NPY mappings are cached. No raw EDF, private mapping or target
    file is accepted. Training receives no test rows or filenames.
    """
    def __init__(self, root, rows, split, np):
        recipe.need(split in ('train','val','test'), 'known split')
        self.root = Path(root).resolve(); self.np = np; self.split = split
        self.rows = [r for r in rows if r['split'] == split]
        self.items = [(index, epoch) for index,r in enumerate(self.rows) for epoch in range(r['shape'][0])]
        recipe.need(len(self.items) == recipe.COUNTS[split], 'complete phase-local dataset required')
        if split == 'test':
            recipe.need(all(set(r) == {'split','shape','sha256','event_ids','signal'} for r in self.rows),
                        'opaque prediction rows only')
        self.cache = OrderedDict(); self.access_order = []

    def __len__(self): return len(self.items)

    def __getitem__(self, index):
        row_index, epoch = self.items[index]; row = self.rows[row_index]
        relative = Path(row['signal']); path = self.root/relative
        recipe.need(not relative.is_absolute() and '..' not in relative.parts and not path.is_symlink() and
                    path.resolve().is_relative_to(self.root), 'signal must stay in immutable packet')
        if row_index not in self.cache:
            value = self.np.load(path, mmap_mode='r', allow_pickle=False)
            recipe.need(list(value.shape) == row['shape'] and value.dtype == self.np.dtype('float64'), 'exact source NPY shape/dtype')
            self.cache[row_index] = value
            if len(self.cache) > 8: self.cache.popitem(last=False)
        self.cache.move_to_end(row_index)
        sample = self.cache[row_index][epoch]
        recipe.need(self.np.isfinite(sample).all(), 'nonfinite source signal')
        self.access_order.append(index)
        return sample/100.0, (None if self.split == 'test' else row['labels'][epoch]), row['event_ids'][epoch]


class NativeReference:
    def __init__(self, *, source, encoder_path, packet_root, fit_rows, seed,
                 profile=recipe.CUDA_PROFILE, overlay=None):
        prepare_profile(profile, overlay)
        self.profile = profile
        self.device = 'cpu' if profile == recipe.CPU_PROFILE else 'cuda'
        # After a future qualified installation binds this gate, these are the
        # concrete native operations. No download or remote-code loader is used.
        self.spec = recipe.reference_spec(seed, profile=profile)
        import numpy as np
        import torch
        import safetensors
        from safetensors.torch import load_file
        self.np = np; self.torch = torch
        if profile == recipe.CUDA_PROFILE:
            recipe.need(torch.cuda.is_available() and torch.cuda.device_count() == 1, 'one explicitly owned CUDA device required')
            torch.cuda.set_device(0)
        else:
            verify_cpu_runtime(torch, np, safetensors, overlay)
        random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
        if profile == recipe.CUDA_PROFILE: torch.cuda.manual_seed_all(seed)
        author = load_source(AUTHOR_ADAPTER, AUTHOR_ADAPTER_SHA, '_reve_matched_author')
        root, positions = author.verify_author_source(source)
        native = author._native_modules(root)
        self.optimizer_source = load_source(root/'src/utils/stable_adamw.py', OPTIMIZER_SHA, '_reve_matched_optimizer')
        expected = recipe.adapter().ENCODER
        recipe.need(file_pin(encoder_path) == expected, 'exact provisioned pretrained encoder required')
        weights = load_file(str(encoder_path), device='cpu')
        recipe.need(file_pin(encoder_path) == expected, 'encoder changed during loading')
        recipe.validate_shapes({k:list(v.shape) for k,v in weights.items()})
        recipe.need(all(v.dtype == torch.float32 and torch.isfinite(v).all() for v in weights.values()), 'finite float32 pretrained state')
        self.model = construct_model(native, torch, weights=weights, profile=profile)
        self.native_modules = native
        del weights
        self.runtime = {'torch':torch.__version__,'numpy':np.__version__,'safetensors':safetensors.__version__}
        head = hashlib.sha256()
        for key, value in sorted(self.model.state_dict().items()):
            if key == 'cls_query_token' or key.startswith('linear_head.'):
                head.update(key.encode()); head.update(value.detach().cpu().contiguous().numpy().tobytes())
        self.initial_head_identity = head.hexdigest()
        self.geometry = torch.tensor([positions[name] for name in author.ELECTRODES], dtype=torch.float32)
        # No padded samples, re-normalization, added dropout or encoder reinitialization.
        recipe.need({r['split'] for r in fit_rows} == {'train','val'}, 'fit cannot receive test rows')
        self.train_data = PacketDataset(packet_root, fit_rows, 'train', np)
        self.val_data = PacketDataset(packet_root, fit_rows, 'val', np)
        self.generator = torch.Generator().manual_seed(seed)
        self.train_loader = torch.utils.data.DataLoader(self.train_data, batch_size=32, shuffle=True,
            generator=self.generator, num_workers=0, drop_last=False, collate_fn=self.collate)
        self.val_loader = torch.utils.data.DataLoader(self.val_data, batch_size=32, shuffle=False,
            num_workers=0, drop_last=False, collate_fn=self.collate)
        recipe.need(len(self.train_loader) == 197 and len(self.val_loader) == 55, 'complete partial final batches required')
        self.selected = None; self.audit = []; self.frozen = False
        self.initial_rng = self.rng_identity()
        self.attention_profile = ('cpu_sdpa_math' if profile == recipe.CPU_PROFILE else
                                  ('native_flash_attn' if native['models.backbone'].FLASH_AVAILABLE else 'native_sdpa_dispatch'))
        # This observed backend must match the later frozen GPU image profile;
        # neither branch is currently deployment-qualified by this source.

    def collate(self, batch):
        torch = self.torch
        return (torch.from_numpy(self.np.array([item[0] for item in batch])).float(),
                None if batch[0][1] is None else torch.tensor([item[1] for item in batch], dtype=torch.long),
                self.geometry.unsqueeze(0).repeat(len(batch),1,1), [item[2] for item in batch])

    def rng_identity(self):
        torch = self.torch; np = self.np
        return recipe.identity({'python': repr(random.getstate()), 'numpy': repr(np.random.get_state()),
                                'torch': torch.get_rng_state().tolist(),
                                'cuda': ([s.tolist() for s in torch.cuda.get_rng_state_all()] if self.profile == recipe.CUDA_PROFILE else []),
                                'sampler': self.generator.get_state().tolist()})

    def begin_stage(self, stage):
        recipe.need(not self.frozen, 'fit already frozen')
        self.stage = stage; torch = self.torch
        for name, parameter in self.model.named_parameters():
            parameter.requires_grad = stage['name'] == 'ft' or name == 'cls_query_token' or name.startswith('linear_head.')
        self.optimizer = self.optimizer_source.StableAdamW(
            (p for p in self.model.parameters() if p.requires_grad), lr=1e-4, weight_decay=1e-2,
            betas=(0.92,0.999), eps=1e-9)
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(self.optimizer, mode='max', factor=0.5, patience=5)
        steps = len(self.train_loader)*stage['warmup_epochs']
        self.warmup = (torch.optim.lr_scheduler.LambdaLR(self.optimizer,
            lr_lambda=lambda step: (10**(step/steps)-1)/9 if step < steps else 1.0) if steps else None)
        self.scaler = torch.amp.GradScaler(device=self.device, enabled=False)
        self.criterion = torch.nn.CrossEntropyLoss()


    def train_batch(self, samples, labels, positions, *, epoch, verify=False):
        """Shared optimizer path; diagnostic mode never constitutes an epoch."""
        torch = self.torch; self.model.train()
        self.optimizer.zero_grad(set_to_none=True)
        before = state_hashes(self.model) if verify else None
        learning_rate = float(self.optimizer.param_groups[0]['lr'])
        logits, loss = model_logits(self.model, samples, positions, torch, self.profile,
                                    criterion=self.criterion, labels=labels)
        recipe.need(bool(torch.isfinite(loss)), 'nonfinite training loss; no checkpoint publication')
        self.scaler.scale(loss).backward(); self.scaler.unscale_(self.optimizer)
        gradients = gradient_summary(self.model, torch) if verify else None
        norm = torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=2.0)
        if verify or self.profile == recipe.CPU_PROFILE:
            recipe.need(bool(torch.isfinite(norm)), 'nonfinite clipped gradient norm')
        self.scaler.step(self.optimizer); scale = self.scaler.get_scale(); self.scaler.update()
        if scale == self.scaler.get_scale() and epoch < self.stage['warmup_epochs']: self.warmup.step()
        if not verify: return None
        recipe.need(tuple(logits.shape) == (len(labels),4) and bool(torch.isfinite(logits).all()),
                    'complete finite four-class training logits')
        recipe.need(all(bool(torch.isfinite(v).all()) for v in self.model.state_dict().values()),
                    'nonfinite post-step classifier')
        after = state_hashes(self.model)
        changed = [name for name in before if before[name] != after[name]]
        encoder_changed = [name for name in changed if name.startswith('encoder.')]
        if self.stage['name'] == 'lp':
            recipe.need(not encoder_changed and gradients['encoder_nonzero_elements'] == 0, 'LP encoder changed')
            recipe.need(not changed if learning_rate == 0 else bool(changed), 'LP update disagrees with learning rate')
        else:
            recipe.need(learning_rate > 0 and gradients['encoder_nonzero_elements'] > 0 and encoder_changed,
                        'FT requires a nonzero encoder gradient and update')
        return {'stage':self.stage['name'],'examples':len(labels),'learning_rate':learning_rate,
                'loss':float(loss.detach()),'gradient_norm_before_clip':float(norm),'gradients':gradients,
                'changed_tensor_count':len(changed),'changed_encoder_tensor_count':len(encoder_changed)}

    def train_epoch(self, epoch):
        torch = self.torch; self.model.train(); self.train_data.access_order.clear()
        initial = self.rng_identity(); presentations = 0; attempts = 0
        for samples, labels, positions, _ids in self.train_loader:
            self.train_batch(samples, labels, positions, epoch=epoch)
            presentations += len(labels); attempts += 1
        recipe.need(presentations == 6300 and attempts == 197, 'full training pass required')
        self.audit.append({'stage':self.stage['name'],'epoch':epoch,'presentations':presentations,'step_attempts':attempts,
                           'order_identity':recipe.identity(self.train_data.access_order),
                           'initial_rng':initial,'final_rng':self.rng_identity()})

    def _decisions(self, loader):
        torch = self.torch; self.model.eval()
        with torch.inference_mode():
            for samples, labels, positions, ids in loader:
                logits = model_logits(self.model, samples, positions, torch, self.profile)
                recipe.need(tuple(logits.shape) == (len(ids),4) and bool(torch.isfinite(logits).all()), 'finite complete four-class logits')
                yield ids, labels, logits.float().cpu()

    def validation_metrics(self):
        support = [0]*4; hits = [0]*4; total = 0
        for _ids, labels, logits in self._decisions(self.val_loader):
            for target, prediction in zip(labels.tolist(), logits.argmax(dim=1).tolist()):
                recipe.need(type(target) is int and 0 <= target < 4, 'four-class validation target')
                support[target] += 1; hits[target] += target == prediction; total += 1
        recipe.need(total == 1734 and all(support), 'complete all-class validation support required')
        return {'accuracy': sum(hits)/total, 'balanced_accuracy': sum(h/s for h,s in zip(hits,support))/4}

    def snapshot_selected(self):
        # Own detached tensors: state_dict() alone would alias later training.
        self.selected = {key: value.detach().cpu().clone() for key,value in self.model.state_dict().items()}

    def step_scheduler(self, accuracy): self.scheduler.step(accuracy)

    def restore_selected(self):
        recipe.need(self.selected is not None, 'selected complete state missing')
        self.model.load_state_dict(self.selected, strict=True); self.model.eval(); self.frozen = True

    def save_checkpoint(self, output):
        recipe.need(self.frozen, 'only frozen selected state may be serialized')
        output = Path(output)
        with output.open('xb') as stream:
            if self.profile == recipe.CPU_PROFILE:
                writer = LimitedWriter(stream); self.torch.save(self.selected, writer)
                self.checkpoint_requested_bytes = writer.requested_bytes
            else:
                self.torch.save(self.selected, stream)
        return file_pin(output)


def fit_reference(*, info, packet_root, source, encoder_path, seed, checkpoint_output,
                  profile=recipe.CUDA_PROFILE, overlay=None):
    recipe.validate_profile(profile)
    if profile == recipe.CUDA_PROFILE: recipe.require_installation()
    rows = recipe.phase_data(info, 'fit')
    backend = NativeReference(source=source, encoder_path=encoder_path, packet_root=packet_root,
                              fit_rows=rows, seed=seed, profile=profile, overlay=overlay)
    result = recipe.drive_fit(backend)
    checkpoint = backend.save_checkpoint(checkpoint_output)
    receipt = {**result, 'schema':'reve-matched-fit-receipt-v1','recipe':backend.spec,
               'materials_identity':info['materials_identity'],'data_identity':info['data_identity'],
               'checkpoint':checkpoint,'audit':backend.audit,'initial_rng':backend.initial_rng,
               'final_rng':backend.rng_identity(),'attention_profile':backend.attention_profile,
               'runtime':backend.runtime,'initial_head_identity':backend.initial_head_identity,
               'reuse_policy':'operator_reference_only_same_data_identity_across_both_primary_conditions',
               'historical_classifier_authenticated':False,'scientific_qualification':False}
    receipt['identity'] = recipe.identity(receipt)
    return receipt


def predict_selected(*, info, packet_root, source, checkpoint_path, fit_receipt, expected_fit_identity,
                     profile=recipe.CUDA_PROFILE, overlay=None):
    """Separate inference phase; no optimizer, adaptation, labels or target joins."""
    prepare_profile(profile, overlay)
    recipe.validate_fit_receipt(fit_receipt, info, expected_fit_identity, profile=profile)
    recipe.need(file_pin(checkpoint_path) == fit_receipt['checkpoint'], 'selected checkpoint changed')
    import numpy as np
    import torch
    import safetensors
    if profile == recipe.CUDA_PROFILE:
        recipe.need(torch.cuda.is_available() and torch.cuda.device_count() == 1, 'one explicitly owned CUDA device required')
        torch.cuda.set_device(0)
    else:
        verify_cpu_runtime(torch, np, safetensors, overlay)
    recipe.need(fit_receipt['runtime'] == {'torch':torch.__version__,'numpy':np.__version__,'safetensors':safetensors.__version__}, 'selected fit runtime changed')
    author = load_source(AUTHOR_ADAPTER, AUTHOR_ADAPTER_SHA, '_reve_matched_prediction_author')
    root, positions = author.verify_author_source(source); native = author._native_modules(root)
    attention = ('cpu_sdpa_math' if profile == recipe.CPU_PROFILE else
                 ('native_flash_attn' if native['models.backbone'].FLASH_AVAILABLE else 'native_sdpa_dispatch'))
    recipe.need(fit_receipt['attention_profile'] == attention, 'selected fit attention dispatch changed')
    state = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
    recipe.need(file_pin(checkpoint_path) == fit_receipt['checkpoint'], 'checkpoint changed during loading')
    recipe.validate_shapes({k:list(v.shape) for k,v in state.items()}, complete_classifier=True)
    recipe.need(all(v.dtype == torch.float32 and torch.isfinite(v).all() for v in state.values()), 'finite complete selected state')
    model = construct_model(native, torch, complete_state=state, profile=profile).eval()
    data = PacketDataset(packet_root, recipe.phase_data(info,'predict'), 'test', np)
    geometry = torch.tensor([positions[name] for name in author.ELECTRODES], dtype=torch.float32)
    predictions = []
    with torch.inference_mode():
        for start in range(0,len(data),32):
            items = [data[index] for index in range(start,min(start+32,len(data)))]
            samples = torch.from_numpy(np.array([item[0] for item in items])).float()
            pos = geometry.unsqueeze(0).repeat(len(items),1,1)
            logits = model_logits(model, samples, pos, torch, profile)
            recipe.need(tuple(logits.shape) == (len(items),4) and bool(torch.isfinite(logits).all()), 'finite four-class prediction')
            predictions.extend({'event_id': item[2], 'scores': score}
                               for item,score in zip(items,logits.float().cpu().tolist()))
    result = {'schema':'reve-candidate-predictions-v1','materials_identity':info['materials_identity'],'predictions':predictions}
    return recipe.adapter().admit_result(result,info)


def training_compatibility(*, info, packet_root, source, encoder_path, seed, checkpoint_output,
                           profile=recipe.CPU_PROFILE, overlay=None):
    """Bounded integration control through the real trainer, never a fit receipt.

    One full batch32 and the original final partial batch28 are selected by a
    diagnostic draw of the existing batch sampler. Intervening arrays are never
    opened. This draw is not claimed to reproduce a full epoch's loader order.
    """
    recipe.need(profile == recipe.CPU_PROFILE, 'explicit CPU training control only')
    started = time.monotonic()
    rows = recipe.phase_data(info, 'fit')
    backend = NativeReference(source=source, encoder_path=encoder_path, packet_root=packet_root,
                              fit_rows=rows, seed=seed, profile=profile, overlay=overlay)
    torch = backend.torch
    roster = list(backend.train_loader.batch_sampler)
    recipe.need(len(roster) == 197 and [len(roster[0]),len(roster[-1])] == [32,28],
                'original full and partial batch geometry required')
    chosen = [roster[0],roster[-1]]
    recipe.need(len(set(chosen[0]+chosen[1])) == 60, 'sixty distinct training examples required')
    selected_rows = {backend.train_data.items[i][0] for batch in chosen for i in batch}
    selected_pins = []; total_shard_bytes = 0
    for index in sorted(selected_rows):
        row = backend.train_data.rows[index]
        path = Path(packet_root)/row['signal']
        recipe.need(path.is_file() and not path.is_symlink() and
                    path.resolve().is_relative_to(Path(packet_root).resolve()), 'selected training shard remains in packet')
        size = path.stat().st_size
        recipe.need(0 < size <= 16*1024*1024, 'bounded selected training shard')
        total_shard_bytes += size
        recipe.need(total_shard_bytes <= 512*1024*1024, 'bounded selected shard inventory')
        pin = file_pin(path, maximum_bytes=size)
        recipe.need(pin == {'bytes':size,'sha256':row['sha256']}, 'selected training signal changed')
        selected_pins.append({'path':str(path),'pin':pin})
    diagnostic_loader = torch.utils.data.DataLoader(
        backend.train_data, batch_sampler=chosen, generator=backend.generator,
        num_workers=0, collate_fn=backend.collate)
    batches = list(diagnostic_loader)
    recipe.need([len(batch[1]) for batch in batches] == [32,28], 'bounded DataLoader batch shapes')
    recipe.need(not backend.val_data.access_order, 'validation arrays must remain unopened')
    steps = []
    backend.begin_stage(dict(recipe.STAGES[0]))
    for index,batch in enumerate(batches):
        samples,labels,positions,_ids = batch
        row = backend.train_batch(samples, labels, positions, epoch=0, verify=True)
        row['step'] = index; steps.append(row)
    recipe.need(steps[0]['learning_rate'] == 0 and steps[1]['learning_rate'] > 0,
                'zero then positive LP warmup learning rates required')
    backend.begin_stage(dict(recipe.STAGES[1]))
    samples,labels,positions,_ids = batches[0]
    row = backend.train_batch(samples, labels, positions, epoch=0, verify=True)
    row['step'] = 0; steps.append(row)
    # A diagnostic snapshot exercises the same serialization path but has no
    # validation selection history and cannot satisfy validate_fit_receipt().
    backend.snapshot_selected(); backend.restore_selected()
    checkpoint = backend.save_checkpoint(checkpoint_output)
    recipe.need(checkpoint['bytes'] <= 320*1024*1024, 'bounded complete checkpoint')
    state = torch.load(checkpoint_output, map_location='cpu', weights_only=True)
    recipe.need(file_pin(checkpoint_output, maximum_bytes=320*1024*1024) == checkpoint,
                'checkpoint changed during safe reload')
    recipe.validate_shapes({key:list(value.shape) for key,value in state.items()}, complete_classifier=True)
    recipe.need(all(value.dtype == torch.float32 and bool(torch.isfinite(value).all()) for value in state.values()),
                'complete finite float32 checkpoint required')
    restored = construct_model(backend.native_modules, torch, complete_state=state, profile=profile).eval()
    same_tensors = state_hashes(restored) == state_hashes(backend.model)
    recipe.need(same_tensors, 'complete checkpoint tensor byte equality required')
    with torch.inference_mode():
        reference_logits = model_logits(backend.model, samples, positions, torch, profile)
        restored_logits = model_logits(restored, samples, positions, torch, profile)
    recipe.need(bool(torch.isfinite(reference_logits).all()) and bool(torch.isfinite(restored_logits).all()),
                'finite roundtrip logits required')
    same_logits = torch.equal(reference_logits.contiguous().view(torch.uint8),
                              restored_logits.contiguous().view(torch.uint8))
    recipe.need(same_logits, 'bitwise logits with fresh geometry required')
    recipe.need(not backend.val_data.access_order and not backend.audit,
                'control must not claim validation access or completed training epochs')
    for selected in selected_pins:
        recipe.need(file_pin(selected['path'], maximum_bytes=selected['pin']['bytes']) == selected['pin'],
                    'selected training shard changed during control')
    recipe.need(file_pin(encoder_path, maximum_bytes=recipe.adapter().ENCODER['bytes']) == recipe.adapter().ENCODER,
                'pretrained encoder changed during control')
    return {'schema':'reve-trainer-cpu-batch-compatibility-v1','status':'PASS',
            'profile':profile,'recipe':backend.spec,'seed':seed,'elapsed_seconds':time.monotonic()-started,
            'batch_sizes':[32,28],'distinct_training_examples_loaded':60,'training_presentations':92,
            'sampler_draw':'bounded_diagnostic_not_full_epoch_order',
            'selected_index_identity':recipe.identity(chosen),'selected_signal_bytes':total_shard_bytes,
            'selected_signal_pins':selected_pins,'steps':steps,'checkpoint':checkpoint,
            'checkpoint_requested_bytes':backend.checkpoint_requested_bytes,
            'checkpoint_role':'compatibility_only_without_validation_selection',
            'checkpoint_tensor_byte_equality':same_tensors,'eval_logit_bitwise_equality':same_logits,
            'runtime':backend.runtime,'attention_profile':backend.attention_profile,
            'full_training_run':False,'completed_training_epochs':0,'validation_predictions':0,
            'test_predictions':0,'scored_metrics':0,'held_examples_read':0,
            'scientific_qualification':False,'historical_paper_equivalence':False,
            'original_CUDA_installation_gate_unchanged':True}
