"""Offline native reference implementation, dormant until GPU custody is qualified.

No imports of tensor packages, data access, fitting or inference happen at import.
This is trusted operator source, never a common asset for the primary paper arm.
"""
from __future__ import annotations
from collections import OrderedDict
import hashlib
import importlib.util
import json
from pathlib import Path
import random
from types import ModuleType, SimpleNamespace

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_reve_matched_recipe', HERE/'recipe.py')
recipe = importlib.util.module_from_spec(spec); spec.loader.exec_module(recipe)
AUTHOR_ADAPTER = HERE.parent/'original-physionet/author_adapter.py'
AUTHOR_ADAPTER_SHA = '0990eac5f5a478dfc6c00a0e8898d115e1ddc6049f58c8085ec69e2e7457aea1'
OPTIMIZER_SHA = '486342669b4d7d528d38d2aa4c84b312e14b9b60d73ea31dfc2439f0ce86035c'


def load_source(path, expected, name):
    raw = Path(path).read_bytes()
    recipe.need(hashlib.sha256(raw).hexdigest() == expected, 'pinned source changed: '+str(path))
    module = ModuleType(name); module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def file_pin(path):
    path = Path(path)
    recipe.need(path.is_file() and not path.is_symlink(), 'regular immutable file required')
    size = 0; sha = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): size += len(block); sha.update(block)
    return {'bytes': size, 'sha256': sha.hexdigest()}


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
    def __init__(self, *, source, encoder_path, packet_root, fit_rows, seed):
        recipe.require_installation()
        # After a future qualified installation binds this gate, these are the
        # concrete native operations. No download or remote-code loader is used.
        self.spec = recipe.reference_spec(seed)
        import numpy as np
        import torch
        import safetensors
        from safetensors.torch import load_file
        self.np = np; self.torch = torch
        recipe.need(torch.cuda.is_available() and torch.cuda.device_count() == 1, 'one explicitly owned CUDA device required')
        torch.cuda.set_device(0)
        random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
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
        query = weights.pop('cls_query_token')
        args = SimpleNamespace(embed_dim=512, depth=22, heads=8, head_dim=64, mlp_dim_ratio=2.66, use_geglu=True)
        encoder = native['models.encoder'].REVE(args, 4, 200, 20, 0.0025)
        encoder.load_state_dict(weights, strict=True)
        self.model = native['models.classifier'].ReveClassifier(encoder, n_classes=4, dropout=0.0, pooling='no', out_shape=recipe.FLAT)
        with torch.no_grad(): self.model.cls_query_token.copy_(query)
        recipe.validate_shapes({k:list(v.shape) for k,v in self.model.state_dict().items()}, complete_classifier=True)
        self.model.to('cuda'); del weights, query
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
        self.attention_profile = 'native_flash_attn' if native['models.backbone'].FLASH_AVAILABLE else 'native_sdpa_dispatch'
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
                                'cuda': [s.tolist() for s in torch.cuda.get_rng_state_all()],
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
        self.scaler = torch.amp.GradScaler(device='cuda', enabled=False)
        self.criterion = torch.nn.CrossEntropyLoss()

    def train_epoch(self, epoch):
        torch = self.torch; self.model.train(); self.train_data.access_order.clear()
        initial = self.rng_identity(); presentations = 0; attempts = 0
        for samples, labels, positions, _ids in self.train_loader:
            self.optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast(device_type='cuda', dtype=torch.float16):
                logits = self.model(samples.to('cuda'), positions.to('cuda'))
                loss = self.criterion(logits, labels.to('cuda'))
            recipe.need(bool(torch.isfinite(loss)), 'nonfinite training loss; fail instead of silently publishing a checkpoint')
            self.scaler.scale(loss).backward(); self.scaler.unscale_(self.optimizer)
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=2.0)
            self.scaler.step(self.optimizer); scale = self.scaler.get_scale(); self.scaler.update()
            if scale == self.scaler.get_scale() and epoch < self.stage['warmup_epochs']: self.warmup.step()
            presentations += len(labels); attempts += 1
        recipe.need(presentations == 6300 and attempts == 197, 'full training pass required')
        self.audit.append({'stage':self.stage['name'],'epoch':epoch,'presentations':presentations,'step_attempts':attempts,
                           'order_identity':recipe.identity(self.train_data.access_order),
                           'initial_rng':initial,'final_rng':self.rng_identity()})

    def _decisions(self, loader):
        torch = self.torch; self.model.eval()
        with torch.inference_mode():
            for samples, labels, positions, ids in loader:
                with torch.amp.autocast(device_type='cuda', dtype=torch.float16):
                    logits = self.model(samples.to('cuda'), positions.to('cuda'))
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
        with output.open('xb') as stream: self.torch.save(self.selected, stream)
        return file_pin(output)


def fit_reference(*, info, packet_root, source, encoder_path, seed, checkpoint_output):
    recipe.require_installation()
    rows = recipe.phase_data(info, 'fit')
    backend = NativeReference(source=source, encoder_path=encoder_path, packet_root=packet_root, fit_rows=rows, seed=seed)
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


def predict_selected(*, info, packet_root, source, checkpoint_path, fit_receipt, expected_fit_identity):
    """Separate inference phase; no optimizer, adaptation, labels or target joins."""
    recipe.require_installation()
    recipe.validate_fit_receipt(fit_receipt, info, expected_fit_identity)
    recipe.need(file_pin(checkpoint_path) == fit_receipt['checkpoint'], 'selected checkpoint changed')
    import numpy as np
    import torch
    import safetensors
    recipe.need(torch.cuda.is_available() and torch.cuda.device_count() == 1, 'one explicitly owned CUDA device required')
    torch.cuda.set_device(0)
    recipe.need(fit_receipt['runtime'] == {'torch':torch.__version__,'numpy':np.__version__,'safetensors':safetensors.__version__}, 'selected fit runtime changed')
    author = load_source(AUTHOR_ADAPTER, AUTHOR_ADAPTER_SHA, '_reve_matched_prediction_author')
    root, positions = author.verify_author_source(source); native = author._native_modules(root)
    attention = 'native_flash_attn' if native['models.backbone'].FLASH_AVAILABLE else 'native_sdpa_dispatch'
    recipe.need(fit_receipt['attention_profile'] == attention, 'selected fit attention dispatch changed')
    state = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
    recipe.need(file_pin(checkpoint_path) == fit_receipt['checkpoint'], 'checkpoint changed during loading')
    recipe.validate_shapes({k:list(v.shape) for k,v in state.items()}, complete_classifier=True)
    recipe.need(all(v.dtype == torch.float32 and torch.isfinite(v).all() for v in state.values()), 'finite complete selected state')
    with torch.device('meta'):
        args = SimpleNamespace(embed_dim=512, depth=22, heads=8, head_dim=64, mlp_dim_ratio=2.66, use_geglu=True)
        encoder = native['models.encoder'].REVE(args,4,200,20,0.0025)
        model = native['models.classifier'].ReveClassifier(encoder,4,0.0,pooling='no',out_shape=recipe.FLAT)
    model.load_state_dict(state, strict=True, assign=True); model.to('cuda').eval()
    data = PacketDataset(packet_root, recipe.phase_data(info,'predict'), 'test', np)
    geometry = torch.tensor([positions[name] for name in author.ELECTRODES], dtype=torch.float32)
    predictions = []
    with torch.inference_mode():
        for start in range(0,len(data),32):
            items = [data[index] for index in range(start,min(start+32,len(data)))]
            samples = torch.from_numpy(np.array([item[0] for item in items])).float().to('cuda')
            pos = geometry.unsqueeze(0).repeat(len(items),1,1).to('cuda')
            with torch.amp.autocast(device_type='cuda', dtype=torch.float16): logits = model(samples,pos)
            recipe.need(tuple(logits.shape) == (len(items),4) and bool(torch.isfinite(logits).all()), 'finite four-class prediction')
            predictions.extend({'event_id': item[2], 'scores': score}
                               for item,score in zip(items,logits.float().cpu().tolist()))
    result = {'schema':'reve-candidate-predictions-v1','materials_identity':info['materials_identity'],'predictions':predictions}
    return recipe.adapter().admit_result(result,info)
