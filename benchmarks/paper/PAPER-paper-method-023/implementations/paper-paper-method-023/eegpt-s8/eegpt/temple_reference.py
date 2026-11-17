"""Nine concrete Temple comparators. Numerical operations are future workers only.

Exact upstream architectures live under reference-source/temple. Scientific
parity, native qualification and external artifacts are separate obligations.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import sys
from .protocol import HandleCustody,need, fields, digest, identity

KIND = 'temple_reference_v1'
MANIFEST_SHA256 = 'd588f41d855605f6a3221141718740bbaa0d96e79ee7fab9a64253a2eacc4cb6'
METHODS = ('BIOT', 'CNN-T', 'ContraWR', 'FFCL', 'LaBraM-Base', 'LaBraM-Large', 'LaBraM-Huge', 'SPaRCNet', 'ST-T')
REFERENTIAL = 'FP1 FP2 F3 F4 C3 C4 P3 P4 O1 O2 F7 F8 T3 T4 T5 T6 A1 A2 FZ CZ PZ T1 T2'.split()
BIPOLAR = 'FP1-F7 F7-T3 T3-T5 T5-O1 FP2-F8 F8-T4 T4-T6 T6-O2 FP1-F3 F3-C3 C3-P3 P3-O1 FP2-F4 F4-C4 C4-P4 P4-O2'.split()
BIOT_REFERENTIAL = list(dict.fromkeys(name for pair in BIPOLAR for name in pair.split('-')))
POSITION_CHANNELS = ['FP1', 'FPZ', 'FP2', 'AF9', 'AF7', 'AF5', 'AF3', 'AF1', 'AFZ', 'AF2', 'AF4', 'AF6', 'AF8', 'AF10', 'F9', 'F7', 'F5', 'F3', 'F1', 'FZ', 'F2', 'F4', 'F6', 'F8', 'F10', 'FT9', 'FT7', 'FC5', 'FC3', 'FC1', 'FCZ', 'FC2', 'FC4', 'FC6', 'FT8', 'FT10', 'T9', 'T7', 'C5', 'C3', 'C1', 'CZ', 'C2', 'C4', 'C6', 'T8', 'T10', 'TP9', 'TP7', 'CP5', 'CP3', 'CP1', 'CPZ', 'CP2', 'CP4', 'CP6', 'TP8', 'TP10', 'P9', 'P7', 'P5', 'P3', 'P1', 'PZ', 'P2', 'P4', 'P6', 'P8', 'P10', 'PO9', 'PO7', 'PO5', 'PO3', 'PO1', 'POZ', 'PO2', 'PO4', 'PO6', 'PO8', 'PO10', 'O1', 'OZ', 'O2', 'O9', 'CB1', 'CB2', 'IZ', 'O10', 'T3', 'T5', 'T4', 'T6', 'M1', 'M2', 'A1', 'A2', 'CFC1', 'CFC2', 'CFC3', 'CFC4', 'CFC5', 'CFC6', 'CFC7', 'CFC8', 'CCP1', 'CCP2', 'CCP3', 'CCP4', 'CCP5', 'CCP6', 'CCP7', 'CCP8', 'T1', 'T2', 'FTT9h', 'TTP7h', 'TPP9h', 'FTT10h', 'TPP8h', 'TPP10h', 'FP1-F7', 'F7-T7', 'T7-P7', 'P7-O1', 'FP2-F8', 'F8-T8', 'T8-P8', 'P8-O2', 'FP1-F3', 'F3-C3', 'C3-P3', 'P3-O1', 'FP2-F4', 'F4-C4', 'C4-P4', 'P4-O2']


def registry():
    """Closed metadata registry; no architecture import or allocation."""
    result = {}
    constructors = {'BIOT': 'BIOTClassifier', 'CNN-T': 'CNNTransformer', 'ContraWR': 'ContraWR', 'FFCL': 'FFCL', 'SPaRCNet': 'SPaRCNet', 'ST-T': 'STTransformer', 'LaBraM-Base': 'labram_base_patch200_200', 'LaBraM-Large': 'labram_large_patch200_200', 'LaBraM-Huge': 'labram_huge_patch200_200'}
    for dataset in ('TUAB', 'TUEV'):
        for method in METHODS:
            labram = method.startswith('LaBraM-')
            result[dataset + '/' + method] = {'dataset': dataset, 'method': method, 'constructor': constructors[method], 'classes': 2 if dataset == 'TUAB' else 6, 'logits': 1 if dataset == 'TUAB' else 6, 'sampling_hz': 200, 'samples': 2000 if dataset == 'TUAB' else 1000, 'channels': list(REFERENTIAL if labram else BIPOLAR), 'units': 'uV' if labram else 'V', 'preparation_policy': 'labram_continuous_23ch_v1' if labram else 'biot_continuous_16bipolar_v1', 'fixed_recipe_id': ('labram_readme_tuab_v1' if dataset == 'TUAB' else 'labram_cli_tuev_v1') if labram else 'biot_supervised_v1', 'source_project': 'LaBraM' if labram else 'BIOT'}
    return result


def fixed_fit(dataset, method):
    need(dataset in ('TUAB', 'TUEV') and method in METHODS, 'closed Temple dataset/method union')
    if method.startswith('LaBraM-'):
        return {'optimizer': 'AdamW', 'learning_rate': 0.0005, 'weight_decay': 0.05, 'batch_size': 64, 'epochs': 50 if dataset == 'TUAB' else 30, 'layer_decay': 0.65 if dataset == 'TUAB' else 0.9, 'warmup_epochs': 5, 'warmup_lr': 0.000001, 'min_lr': 0.000001, 'patience': None, 'precision': 'float32', 'drop_last': False, 'selection_tie': 'earliest', 'refit_policy': 'selected_epoch_no_refit'}
    return {'optimizer': 'Adam', 'learning_rate': 0.001, 'weight_decay': 0.00001, 'batch_size': 512, 'epochs': 100, 'patience': 5, 'precision': 'float32', 'drop_last': False, 'selection_tie': 'earliest', 'refit_policy': 'selected_epoch_no_refit'}


def preparation_contract(dataset, method):
    """Pure source-owned identity shared by raw preparer and private projection."""
    key = dataset + '/' + method
    need(key in registry(), 'closed Temple preparation domain')
    row = registry()[key]; labram = method.startswith('LaBraM-')
    return {'schema': 'eegpt_temple_preparation_v1', 'dataset': dataset, 'source_manifest': MANIFEST_SHA256, 'policy': row['preparation_policy'], 'input_kind': 'continuous_referential_recording', 'input_channel_selection': list(REFERENTIAL if labram else BIOT_REFERENTIAL), 'output_channels': row['channels'], 'sampling_hz': 200, 'units': row['units'], 'samples': row['samples'], 'bandpass_hz': [0.1, 75.0] if labram else None, 'notch_hz': 50.0 if labram else None, 'filter_scope': 'complete_continuous_recording_before_epoching', 'mne_filter': {'method': 'fir', 'phase': 'zero', 'fir_window': 'hamming', 'fir_design': 'firwin'}, 'resample': {'implementation': 'mne.Raw.resample', 'npad': 'auto', 'window': 'boxcar', 'pad': 'reflect_limited'}, 'event_rule': 'every_consecutive_full_ten_seconds' if dataset == 'TUAB' else 'first_sample_at_or_after_event_start_end_then_two_seconds_context_source_triple_recording_wrap', 'source_tuev_250_256_clock_discrepancy_resolved_prospectively': dataset == 'TUEV', 'query_labels_used': False}


def _channel_name(name):
    if name.startswith('EEG ') and name.endswith('-REF'): return name[4:-4]
    return name


def prepare_recording(signals, metadata, dataset, method):
    """Actual continuous source preparation; future authorized numerical worker only."""
    import numpy as np
    import mne
    contract = preparation_contract(dataset, method)
    fields(metadata, ('channels', 'sampling_hz', 'units'), 'continuous signal-only recording metadata')
    names = [_channel_name(name) for name in metadata['channels']]
    selected = contract['input_channel_selection']
    need(len(names) == len(set(names)) and all(name in names for name in selected), 'unique complete original referential channel selection')
    need(getattr(signals, 'ndim', None) == 2 and len(signals) == len(names) and signals.shape[1] > 0 and np.isfinite(signals).all(), 'complete finite continuous recording')
    scale = {'V': 1.0, 'mV': 0.001, 'uV': 0.000001}
    need(metadata['units'] in scale and type(metadata['sampling_hz']) in (int,float) and metadata['sampling_hz'] > 150, 'qualified volts/millivolts/microvolts and Nyquist support')
    ordered = np.asarray(signals[[names.index(name) for name in selected]], dtype=np.float64) * scale[metadata['units']]
    raw = mne.io.RawArray(ordered, mne.create_info(selected, metadata['sampling_hz'], ch_types='eeg'), verbose=False)
    if method.startswith('LaBraM-'):
        raw.filter(0.1, 75.0, method='fir', phase='zero', fir_window='hamming', fir_design='firwin', verbose=False)
        raw.notch_filter(50.0, method='fir', phase='zero', fir_window='hamming', fir_design='firwin', verbose=False)
    raw.resample(200, npad='auto', window='boxcar', pad='reflect_limited', n_jobs=1, verbose=False)
    result = raw.get_data(); raw.close()
    if method.startswith('LaBraM-'): result = result * 1e6
    else: result = np.stack([result[selected.index(pair.split('-')[0])] - result[selected.index(pair.split('-')[1])] for pair in BIPOLAR])
    return result, {'channels': contract['output_channels'], 'sampling_hz': 200, 'units': contract['units'], 'preparation_contract': contract, 'preparation_identity': identity(contract), 'source_sampling_hz': metadata['sampling_hz'], 'source_samples': signals.shape[1], 'source_channels': metadata['channels'], 'source_units': metadata['units']}


def extract_epochs(prepared_signals, prepared_metadata, dataset, method, events=None):
    """Yield every qualified event; never drop malformed events or invent labels."""
    import numpy as np
    contract = preparation_contract(dataset, method)
    need(prepared_metadata['preparation_contract'] == contract and prepared_metadata['preparation_identity'] == identity(contract), 'exact whole-recording source preparation')
    need(prepared_signals.ndim == 2 and len(prepared_signals) == len(contract['output_channels']), 'full prepared channel support')
    samples = prepared_signals.shape[1]; rate = 200
    if dataset == 'TUAB':
        need(events is None, 'TUAB source uses all full contiguous windows')
        for index in range(samples // 2000):
            start = index * 2000
            yield {'event_id': str(index), 'interval': [start/rate, (start+2000)/rate], 'signal': prepared_signals[:,start:start+2000], 'source_event': None}
    else:
        need(type(events) is list and events, 'all qualified original TUEV annotations in original order')
        need(len({e['id'] for e in events}) == len(events), 'unique original TUEV event identities')
        # This is the original three-recording wrap, not zero padding or a crop.
        wrapped = np.concatenate([prepared_signals, prepared_signals, prepared_signals], axis=1)
        for event in events:
            fields(event, ('id', 'start_seconds', 'end_seconds'), 'signal-only original TUEV event timing')
            start = math.ceil(event['start_seconds'] * rate); end = math.ceil(event['end_seconds'] * rate)
            need(0 <= start < end <= samples and end-start == 200, 'source one-second event with exact five-second context')
            left = samples+start-400; right = samples+end+400
            need(0 <= left < right <= 3*samples, 'original wrap context is available; no silent incomplete event')
            signal = wrapped[:,left:right]
            need(signal.shape[1] == 1000, 'complete five-second original TUEV event')
            yield {'event_id': event['id'], 'interval': [(start-400)/rate, (end+400)/rate], 'signal': signal, 'source_event': dict(event)}


def admit_recipe(recipe, dataset, method):
    """Validate fixed scientific metadata without touching signals or models."""
    fields(recipe, ('kind', 'dataset', 'method', 'fixed_recipe_id', 'fit', 'input', 'initialization', 'qualification'), 'complete closed Temple recipe')
    need(recipe['kind'] == KIND and recipe['dataset'] == dataset and recipe['method'] == method, 'exact Temple task recipe')
    key = dataset + '/' + method
    need(key in registry(), 'all and only eighteen Temple model/dataset combinations')
    row = registry()[key]
    need(recipe['fixed_recipe_id'] == row['fixed_recipe_id'], 'fixed source-owned Temple training recipe')
    digest(recipe['qualification'])
    fit = recipe['fit']; expected = fixed_fit(dataset, method)
    need(set(fit) == set(expected) | {'seed', 'device', 'qualification'}, 'closed fit keys prevent hidden algorithm overrides')
    need(all(type(fit[k]) is type(v) and fit[k] == v for k, v in expected.items()), 'exact typed prespecified source-derived fit constants')
    need(type(fit['seed']) is int and 0 <= fit['seed'] < 2**32, 'original FIT seed')
    need(fit['device'] == 'cpu', 'qualified CPU-only Linux worker; GPU budget is zero')
    digest(fit['qualification'])
    inp = recipe['input']
    need(set(inp) == {'preparation_policy', 'preparation_identity', 'channels', 'sampling_hz', 'units', 'samples'}, 'qualified full input recipe, no arbitrary transform callback')
    digest(inp['preparation_identity'])
    need(inp['preparation_identity'] == identity(preparation_contract(dataset, method)), 'source-owned preparation contract identity, not a free hash')
    need(all(inp[k] == row[k] for k in ('preparation_policy', 'channels', 'sampling_hz', 'units', 'samples')), 'exact source input units, order, clock and complete duration')
    init = recipe['initialization']
    if method.startswith('LaBraM-'):
        need(init.get('policy') == 'labram_pretrained_encoder', 'LaBraM requires actual pretrained encoder')
    elif method == 'BIOT':
        need(init.get('policy') in ('source_scratch', 'biot_pretrained_encoder'), 'BIOT explicit source scratch or pretrained encoder')
    else:
        need(init == {'policy': 'source_scratch'}, 'exact original scratch comparator initialization')
    if init['policy'] != 'source_scratch':
        need(set(init) == {'policy', 'member', 'variant', 'qualification', 'corpus_ancestry'}, 'complete authenticated pretrained state declaration')
        need(init['variant'] == method, 'exact selected pretrained architecture variant')
        fields(init['member'], ('path', 'bytes', 'sha256'), 'original checkpoint descriptor')
        rel = Path(init['member']['path'])
        need(not rel.is_absolute() and '..' not in rel.parts and rel.name == str(rel), 'fixed capability-root checkpoint basename')
        need(type(init['member']['bytes']) is int and init['member']['bytes'] > 0, 'positive actual checkpoint bytes')
        for value in (init['member']['sha256'], init['qualification'], init['corpus_ancestry']): digest(value)
    else:
        need(init == {'policy': 'source_scratch'}, 'closed scratch initialization')
    return row


def _source_root():
    root = Path(__file__).resolve().parent.parent / 'reference-source' / 'temple'
    raw = (root / 'MANIFEST.json').read_bytes()
    need(hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256, 'literal source-owned Temple manifest')
    manifest = json.loads(raw)
    for record in manifest['files']:
        path = root / record['path']; body = path.read_bytes()
        need(not path.is_symlink() and len(body) == record['bytes'] and hashlib.sha256(body).hexdigest() == record['sha256'], 'exact literal upstream Temple source and license')
    return root


def _author_module(project):
    root = _source_root(); name = '_eegpt_temple_' + project + '_' + MANIFEST_SHA256
    relative = 'BIOT/model/__init__.py' if project == 'BIOT' else 'LaBraM/modeling_finetune.py'
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=[str(path.parent)] if project == 'BIOT' else None)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def build_model(dataset, method):
    """Fixed source constructors; never a user-selected module or function."""
    row = registry()[dataset + '/' + method]; m = _author_module(row['source_project']); n = row['logits']; length = row['samples']
    if method == 'SPaRCNet':
        return m.SPaRCNet(in_channels=16, sample_length=length, n_classes=n, block_layers=4, growth_rate=16, bn_size=16, drop_rate=0.5, conv_bias=True, batch_norm=True)
    if method == 'ContraWR': return m.ContraWR(in_channels=16, n_classes=n, fft=200, steps=20)
    if method == 'CNN-T': return m.CNNTransformer(in_channels=16, n_classes=n, fft=200, steps=20, dropout=0.2, nhead=4, emb_size=256, n_segments=5)
    if method == 'FFCL': return m.FFCL(in_channels=16, n_classes=n, fft=200, steps=20, sample_length=length, shrink_steps=20)
    if method == 'ST-T': return m.STTransformer(emb_size=256, depth=4, n_classes=n, channel_legnth=length, n_channels=16)
    if method == 'BIOT': return m.BIOTClassifier(n_classes=n, n_channels=16, n_fft=200, hop_length=100)
    kwargs = {'EEG_size': length, 'num_classes': n, 'drop_rate': 0.0, 'attn_drop_rate': 0.0, 'drop_path_rate': 0.1, 'use_mean_pooling': True, 'init_scale': 0.001, 'use_rel_pos_bias': False, 'use_abs_pos_emb': True, 'init_values': 0.1, 'qkv_bias': False}
    if method == 'LaBraM-Base': return m.labram_base_patch200_200(**kwargs)
    if method == 'LaBraM-Large': return m.labram_large_patch200_200(**kwargs)
    if method == 'LaBraM-Huge': return m.labram_huge_patch200_200(**kwargs)
    need(False, 'closed actual Temple constructor')


def _pin(path):
    h = hashlib.sha256(); count = 0
    with Path(path).open('rb') as stream:
        for body in iter(lambda: stream.read(1024*1024), b''): h.update(body); count += len(body)
    return {'path': Path(path).name, 'bytes': count, 'sha256': h.hexdigest()}


def _initialize(worker, model, recipe):
    import torch
    init = recipe['initialization']
    if init['policy'] == 'source_scratch': return {'policy': 'source_scratch', 'seed': recipe['fit']['seed']}
    need('reference_parent' in worker.inputs, 'actual authenticated Temple parent capability')
    path = worker.inputs['reference_parent'] / init['member']['path']
    need(_pin(path) == init['member'], 'actual original parent checkpoint bytes and identity')
    state = torch.load(path, map_location='cpu', weights_only=True)
    if init['policy'] == 'biot_pretrained_encoder':
        model.biot.load_state_dict(state, strict=True)
    else:
        if 'model' in state: state = state['model']
        elif 'module' in state: state = state['module']
        need(type(state) is dict or hasattr(state, 'items'), 'actual state dictionary')
        state = {k[8:]: v for k, v in state.items() if k.startswith('student.') and 'relative_position_index' not in k}
        state = {k: v for k, v in state.items() if k not in ('head.weight', 'head.bias')}
        expected = set(model.state_dict()) - {'head.weight', 'head.bias'}
        need(set(state) == expected, 'complete matching LaBraM encoder: no silently absent learned source operations')
        result = model.load_state_dict(state, strict=False)
        need(set(result.missing_keys) == {'head.weight', 'head.bias'} and not result.unexpected_keys, 'only task-specific head is newly fitted')
    return init


def _seed(seed):
    import random
    import numpy as np
    import torch
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)


def validate_document(document, recipe):
    """Metadata-only exact full-epoch input admission."""
    inp = recipe['input']; expected_shape = [len(inp['channels']), inp['samples']]
    need(document.get('preparation_contract') == preparation_contract(recipe['dataset'], recipe['method']), 'host-bound exact raw-to-derived preparation contract')
    need(document['rows'] and document['whole_support_identity'] == identity([r['row_id'] for r in document['rows']]), 'all original ordered Temple rows')
    for row in document['rows']:
        need(row['channels'] == inp['channels'] and row['units'] == inp['units'] and row['sampling_hz'] == inp['sampling_hz'] and row['signal']['shape'] == expected_shape, 'full Temple channel/unit/clock/window contract')


def loader(worker, document, recipe, shuffle):
    import numpy as np
    import torch
    validate_document(document, recipe); labram = recipe['method'].startswith('LaBraM-')
    class Epochs(torch.utils.data.Dataset):
        def __len__(self): return len(document['rows'])
        def __getitem__(self, index):
            row = document['rows'][index]
            x, y, _, _ = next(worker.epochs({**document, 'rows': [row]}))
            if labram: x = (x / 100.0).reshape(23, -1, 200)
            else: x = x / (np.quantile(np.abs(x), 0.95, method='linear', axis=-1, keepdims=True) + 1e-8)
            need(np.isfinite(x).all(), 'finite actual source-normalized complete epoch')
            return torch.as_tensor(x, dtype=torch.float32), torch.as_tensor(-1 if y is None else y, dtype=torch.long)
    generator = torch.Generator(); generator.manual_seed(recipe['fit']['seed'])
    dataset = Epochs()
    # Source BatchNorm comparators cannot train a final singleton. Merge it into
    # the preceding batch without dropping or repeating any biological row.
    if shuffle and not labram:
        need(len(dataset) >= 2, 'BatchNorm training requires at least two independent original rows')
        class FullBatches(torch.utils.data.Sampler):
            def __iter__(self):
                ids = list(torch.utils.data.RandomSampler(dataset, generator=generator)); size = recipe['fit']['batch_size']
                batches = [ids[i:i+size] for i in range(0,len(ids),size)]
                if len(batches) > 1 and len(batches[-1]) == 1: batches[-2].extend(batches.pop())
                yield from batches
            def __len__(self):
                size = recipe['fit']['batch_size']; count = (len(dataset)+size-1)//size
                return count-1 if count > 1 and len(dataset)%size == 1 else count
        return torch.utils.data.DataLoader(dataset, batch_sampler=FullBatches(), num_workers=0, generator=generator)
    return torch.utils.data.DataLoader(dataset, batch_size=recipe['fit']['batch_size'], shuffle=shuffle, drop_last=False, num_workers=0, generator=generator)


def _forward(model, x, method):
    if method.startswith('LaBraM-'): return model(x, input_chans=[0] + [POSITION_CHANNELS.index(name)+1 for name in REFERENTIAL])
    return model(x)


def _optimizer(model, recipe):
    import torch
    fit = recipe['fit']
    if fit['optimizer'] == 'Adam': return torch.optim.Adam(model.parameters(), lr=fit['learning_rate'], weight_decay=fit['weight_decay'])
    groups = {}; depth = model.get_num_layers(); skip = model.no_weight_decay()
    for name, param in model.named_parameters():
        if not param.requires_grad: continue
        layer = 0 if name in ('cls_token', 'mask_token', 'pos_embed') or name.startswith('patch_embed') else int(name.split('.')[1])+1 if name.startswith('blocks.') else depth+1
        decay = 0.0 if param.ndim <= 1 or name.endswith('.bias') or name in skip else fit['weight_decay']
        key = (layer, decay)
        if key not in groups: groups[key] = {'params': [], 'weight_decay': decay, 'lr_scale': fit['layer_decay'] ** (depth+1-layer)}
        groups[key]['params'].append(param)
    return torch.optim.AdamW(list(groups.values()), lr=fit['learning_rate'], betas=(0.9, 0.999), eps=1e-8)


def _scheduled_lr(fit, step, steps_per_epoch):
    total = fit['epochs'] * steps_per_epoch; warmup = fit['warmup_epochs'] * steps_per_epoch
    if step < warmup: return fit['warmup_lr'] + (fit['learning_rate']-fit['warmup_lr']) * step / max(1, warmup-1)
    return fit['min_lr'] + 0.5 * (fit['learning_rate']-fit['min_lr']) * (1+math.cos(math.pi*(step-warmup)/(total-warmup)))



def architecture_metadata(model, recipe):
    """Count actual source feature body and task head, with no EEGPT name guess."""
    from .neural_kernel import architecture_census
    result=architecture_census(model,recipe=recipe);method=recipe['method']
    prefix='head.' if method.startswith('LaBraM-') else 'classification.' if method=='ST-T' else 'classifier.'
    head=sum(r['elements'] for r in result['parameters'] if r['name'].startswith(prefix))
    need(head>0,'actual original task head parameter membership')
    total=result['counts']['all_modules'];encoder=total-head
    result['counts'].update(encoder_only=encoder,ema_target_only=0,non_encoder_parameters=head,encoder_and_target_included=encoder)
    result['parameter_convention']={'encoder':'all source feature-body parameters excluding declared task head','head_prefix':prefix,'ema_target_present':False,'buffers_counted_as_parameters':False}
    return result


def fit(worker, recipe):
    spec = worker.request['scope']
    need(spec['mode'] == 'P', 'Temple fixed prospective recipes are P-only: H historical recipe unresolved; Temple methods are absent from the closed I control union')
    row = admit_recipe(recipe, spec['dataset'], spec['method'])
    need(recipe['fit']['seed'] == worker.request['seed'], 'original FIT declared stream')
    import torch
    from .metrics import classify, BinaryRankStore, MONITOR
    from .neural_kernel import semantic_probabilities, architecture_census
    from .family_products import training_products
    _seed(recipe['fit']['seed']); model = build_model(spec['dataset'], spec['method'])
    initialization = {'model_initialization': _initialize(worker, model, recipe), 'recipe_policy': 'prospective_source_derived_v1', 'fixed_recipe_id': recipe['fixed_recipe_id'], 'historical_parity': False, 'historical_recipe_specification': 'original H hyperparameters, seeds and native selection behavior unresolved; fixed prospective defaults do not supply them'}
    train = worker.rows('train'); validation = worker.rows('validation')
    need(train['labels_available'] is True and validation['labels_available'] is True, 'original same-episode training/validation labels')
    train_loader = loader(worker, train, recipe, True); val_loader = loader(worker, validation, recipe, False)
    device = recipe['fit']['device']; model.to(device); optimizer = _optimizer(model, recipe)
    records = []; best = None; stale = 0; step = 0; fit_config = recipe['fit']
    for epoch in range(fit_config['epochs']):
        model.train(); loss_sum = 0.0; count = 0
        for x, y in train_loader:
            if fit_config['optimizer'] == 'AdamW':
                rate = _scheduled_lr(fit_config, step, len(train_loader))
                for group in optimizer.param_groups: group['lr'] = rate * group['lr_scale']
            x = x.to(device); y = y.to(device); optimizer.zero_grad(set_to_none=True)
            logits = _forward(model, x, spec['method'])
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logits[:,0], y.float()) if row['logits'] == 1 else torch.nn.functional.cross_entropy(logits, y)
            need(bool(torch.isfinite(loss)), 'finite actual source Temple loss')
            loss.backward(); optimizer.step(); step += 1; loss_sum += float(loss.detach()) * len(y); count += len(y)
        need(count == len(train['rows']), 'all eligible complete training rows, including final batch')
        model.eval()
        def observations():
            with torch.no_grad():
                for x, y in val_loader:
                    p = semantic_probabilities(_forward(model, x.to(device), spec['method'])).double().cpu()
                    for label, probability in zip(y.tolist(), p.tolist()): yield label, probability, 1
        rank = BinaryRankStore(worker.output / ('temple-rank-%04d.sqlite' % epoch)) if row['classes'] == 2 else None
        with HandleCustody('original_validation_rank') as owned:
            if rank is not None:owned.own(rank,'rank_store')
            metrics = classify(observations(), row['classes'], rank_store=rank)
        need(metrics['rows'] == len(validation['rows']), 'all original validation rows reduced together')
        path = worker.output / ('temple-epoch-%04d.pt' % epoch)
        need(not path.exists(), 'new original complete epoch state')
        torch.save({'state_dict': model.state_dict(), 'optimizer': optimizer.state_dict(), 'epoch': epoch, 'step': step, 'fit_seed': fit_config['seed'], 'recipe_identity': identity(recipe)}, path)
        pin = _pin(path); worker.artifacts.append(pin)
        record = {'epoch': epoch, 'train_loss': loss_sum/count, 'training_rows': count, 'validation': metrics, 'state': pin, 'steps': step}
        records.append(record); value = metrics[MONITOR[spec['dataset']]]
        need(value is not None, 'undefined full-validation endpoint cannot silently select another support')
        if best is None or value > best['monitor']: best = {'epoch': epoch, 'monitor': value, 'state': pin}; stale = 0
        else: stale += 1
        if fit_config['patience'] is not None and stale >= fit_config['patience']: break
    need(best is not None, 'actual complete selected state exists')
    metadata = {'kind': KIND, 'dataset': spec['dataset'], 'method': spec['method'], 'actual_architecture': architecture_metadata(model, recipe), 'recipe': recipe, 'fit_seed': fit_config['seed'], 'source_manifest': MANIFEST_SHA256, 'adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'selected_state': best['state']['path'], 'selected_state_pin': best['state'], 'all_epoch_selection_records': records, 'actual_optimizer_membership': [n for n,p in model.named_parameters() if p.requires_grad], 'training_support': train['whole_support_identity'], 'validation_support': validation['whole_support_identity'], 'initialization': initialization, 'historical_parity': False, 'full_planned_epochs': fit_config['epochs'], 'actual_epochs': len(records), 'early_stopping': {'patience': fit_config['patience'], 'stale': stale, 'monitor': MONITOR[spec['dataset']], 'selected_epoch': best['epoch']}}
    metadata['recipe_policy'] = initialization['recipe_policy']
    metadata['historical_recipe_specification'] = initialization['historical_recipe_specification']
    meta = worker.json('STATE.json', metadata)
    worker.state_response([meta['path']] + [r['state']['path'] for r in records], train, recipe, initialization)
    worker.response['selected_state']['trainability'] = 'all actual source model parameters with requires_grad=True, including complete task head and encoder; nontrainable source channel-index state remains fixed'
    training_products(worker, worker.request['output_contract']['products'], metadata)


def reconstruct(worker, state_root, state):
    recipe = state['recipe']; spec = worker.request['scope']
    need(spec['mode'] == 'P', 'Temple prospective fitted states cannot serve H or out-of-scope I')
    admit_recipe(recipe, spec['dataset'], spec['method'])
    need(state['kind'] == KIND and state['dataset'] == spec['dataset'] and state['method'] == spec['method'], 'same fitted Temple scientific identity')
    need(state['source_manifest'] == MANIFEST_SHA256 and state['adapter_sha256'] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'same exact source-owned constructor and adapter')
    need(state['fit_seed'] == recipe['fit']['seed'], 'original fitted constructor stream; query stream never replaces FIT seed')
    need(state['selected_state'] == state['selected_state_pin']['path'] and Path(state['selected_state']).name == state['selected_state'], 'original selected state basename')
    path = Path(state_root) / state['selected_state']; need(_pin(path) == state['selected_state_pin'], 'actual selected fitted checkpoint bytes')
    import torch
    _seed(state['fit_seed']); model = build_model(state['dataset'], state['method'])
    saved = torch.load(path, map_location='cpu', weights_only=True)
    need(saved['fit_seed'] == state['fit_seed'] and saved['recipe_identity'] == identity(recipe), 'actual original fitted source recipe and seed')
    selected = [r for r in state['all_epoch_selection_records'] if r['state'] == state['selected_state_pin']]
    need(len(selected) == 1 and selected[0]['epoch'] == saved['epoch'], 'selected model has its original complete validation epoch record')
    model.load_state_dict(saved['state_dict'], strict=True); model.to(recipe['fit']['device']); model.eval(); return model


def predict(worker, state_root, state, document):
    need(worker.request['scope']['mode'] == 'P', 'only required prospective Temple scope may invoke numerical prediction')
    import torch
    from .neural_kernel import semantic_probabilities
    model = reconstruct(worker, state_root, state); recipe = state['recipe']; batches = []
    with torch.no_grad():
        for x, _ in loader(worker, document, recipe, False):
            batches.append(semantic_probabilities(_forward(model, x.to(recipe['fit']['device']), recipe['method'])).double().cpu())
    result = torch.cat(batches, dim=0).numpy()
    need(len(result) == len(document['rows']), 'all original ordered Temple probabilities')
    return result
