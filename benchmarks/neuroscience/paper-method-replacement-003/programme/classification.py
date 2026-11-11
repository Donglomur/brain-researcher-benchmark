"""Complete ten-repeat LOO and all-model transfer, using actual C4 methods.

GPL-3.0 derivative integration, modified 2026-11-11. No cached probabilities,
downloaded weights, archive extraction, truncated ensemble or classifier proxy.
"""
from c4_distribution.import_guard import require_bound_source as _c4_require_source
from c4_distribution.spawn_guard import source_worker_scope as _c4_source_worker_scope, worker_context as _c4_worker_context
from dataclasses import dataclass
from .cohort import CLASSES, Population, SupportError, leave_one_unit_out, validate_transfer_ensemble
from .profiles import MethodGap
from .preparation import source_training_matrix

@dataclass
class FittedFold:
    repeat: int
    held: object
    training: tuple
    model: object
    calibrated: object
    held_probability: object
    history: tuple
    oversample_rows: object
    rng_before: object
    rng_after: object

@dataclass
class Ensemble:
    folds: tuple
    fitted: tuple
    unit_order: tuple
    class_order: tuple
    profile: str

def _targets(keys, targets):
    if set(keys) != set(targets):raise SupportError('training label identity mismatch')
    if set(targets.values()) != set(CLASSES):raise SupportError('complete five-class target population required')
    return [CLASSES.index(targets[k]) for k in keys]

def fit_loo(cohort, prepared, targets, waveform_vae, acg_vae, *, profile,
            use_layer, augment_waveform, augment_spikes, freeze_heads,
            device, source_seed, dataloader_workers, population=Population.MOUSE_GROUND_TRUTH):
    """Full literal released classifier route; paper three-bit head stays gated."""
    with _c4_source_worker_scope():
        _c4_require_source()
        if profile.name != 'release_703a10f':
            raise MethodGap('three-bit paper head/unknown-layer convention needs explicit reconstruction selection')
        if type(source_seed) is not int or dataloader_workers != 4:
            raise MethodGap('explicit seed and released four-worker loader recipe required')
        folds = leave_one_unit_out(cohort,population=population)
        keys = tuple(m.key for m in cohort.eligible(population))
        if tuple(u.key for u in prepared) != keys:
            raise SupportError('training representation identity/order mismatch')
        pre_keys = tuple(m.key for m in cohort.eligible(Population.MOUSE_UNLABELLED_PRETRAIN))
        if waveform_vae.training_units != pre_keys or acg_vae.training_units != pre_keys:
            raise SupportError('pretrained models do not bind complete independent source units')
        if waveform_vae.modality != 'waveform' or acg_vae.modality != 'acg':
            raise SupportError('wrong pretrained modality')
        import copy
        import numpy as np
        import torch
        from torch.utils.data import DataLoader
        from imblearn.over_sampling import RandomOverSampler
        _c4_require_source()
        from npyx.ml import set_seed
        _c4_require_source()
        from npyx.c4.dl_utils import CNNCerebellum
        _c4_require_source()
        from npyx.c4.run_deep_classifier import CustomDataset, define_transformations, encode_layer_info, train, get_model_probabilities
        _c4_require_source()
        from npyx.c4.waveform_augmentations import SelectWave
        if augment_spikes and any(u.spikes_30khz is None for u in prepared):
            raise SupportError('training augmentation received non-30kHz source spikes')
        x, spikes, _ = source_training_matrix(prepared, waveform_augmentation=augment_waveform)
        y = np.asarray(_targets(keys, targets), dtype='int64')
        layers = encode_layer_info([u.layer for u in prepared]) if use_layer else None
        if use_layer and layers.shape != (len(keys), 4):raise SupportError('release four-layer representation mismatch')
        spike_transform, wave_transform = define_transformations(False, log_acg=True,
            transform_acg=augment_spikes, transform_wave=augment_waveform, multi_chan=False)
        set_seed(source_seed, seed_torch=True); fitted=[]; cross_seed=None
        for fold_index, fold in enumerate(folds):
            if fold_index % len(keys) == 0:
                cross_seed = source_seed + int(np.random.randint(0, 100))
            tr = np.asarray([keys.index(k) for k in fold.training]); val = np.asarray([keys.index(fold.held)])
            resampled, _ = RandomOverSampler(random_state=cross_seed).fit_resample(tr[:, None], y[tr])
            tr_resampled = resampled.ravel()
            train_set = CustomDataset(x[tr_resampled], y[tr_resampled],
                spikes_list=[spikes[i] for i in tr_resampled], spikes_transform=spike_transform,
                wave_transform=wave_transform, layer=layers[tr_resampled] if use_layer else None)
            test_set = CustomDataset(x[val], y[val], [spikes[i] for i in val],
                layer=layers[val] if use_layer else None,
                wave_transform=SelectWave(window=1) if augment_waveform else None)
            train_loader = DataLoader(train_set, batch_size=profile.classifier_batch, shuffle=True,
                                      num_workers=dataloader_workers, multiprocessing_context=_c4_worker_context())
            test_loader = DataLoader(test_set, batch_size=1)
            before={'numpy':np.random.get_state(), 'torch':torch.get_rng_state()}
            model=CNNCerebellum(copy.deepcopy(acg_vae.encoder), copy.deepcopy(waveform_vae.encoder),
                               5, freeze_vae_weights=freeze_heads, use_layer=use_layer).to(device)
            optimizer=torch.optim.AdamW(model.parameters(), lr=1e-3)
            scheduler=torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(optimizer, profile.classifier_epochs, 1)
            criterion=torch.nn.CrossEntropyLoss().to(device); history=[]
            for epoch in range(profile.classifier_epochs):
                loss,f1,accuracy=train(model,train_loader,optimizer,criterion,device)
                history.append({'epoch':epoch,'loss':float(loss),'f1':float(f1),'accuracy':float(accuracy),
                                'training_rows':len(tr_resampled),'batches':len(train_loader)})
                scheduler.step()
            _, probability, calibrated=get_model_probabilities(model,train_loader,test_loader,
                torch.device('cpu'),laplace=True,enforce_layer=False,labelling={n:i for i,n in enumerate(CLASSES)})
            fitted.append(FittedFold(fold.repeat,fold.held,fold.training,model.cpu().eval(),calibrated,
                probability.detach().cpu().numpy(),tuple(history),tr_resampled,
                before,{'numpy':np.random.get_state(),'torch':torch.get_rng_state()}))
        validate_transfer_ensemble(folds,fitted)
        return Ensemble(folds,tuple(fitted),keys,CLASSES,profile.name)

def predict_transfer(ensemble, cohort, prepared, population, *, use_layer):
    """Every original LOO model, target-free external input, no fast subset."""
    _c4_require_source()
    if population not in (Population.MOUSE_EXPERT, Population.MONKEY_EXPERT,
                          Population.BEHAVIOUR_HULL, Population.BEHAVIOUR_MEDINA,
                          Population.BEHAVIOUR_HAUSSER, Population.BEHAVIOUR_LISBERGER):
        raise SupportError('not a transfer population')
    expected=tuple(m.key for m in cohort.eligible(population))
    if not expected or tuple(u.key for u in prepared)!=expected:
        raise SupportError('complete transfer input/order required')
    validate_transfer_ensemble(ensemble.folds,ensemble.fitted)
    import numpy as np
    import torch
    from torch.utils.data import DataLoader
    _c4_require_source()
    from npyx.c4.run_deep_classifier import CustomDataset, encode_layer_info, ensemble_predict
    matrix,_,_=source_training_matrix(prepared,waveform_augmentation=False)
    layer=encode_layer_info([u.layer for u in prepared]) if use_layer else None
    # The ignored tensor is only the author Dataset ABI placeholder. It is not
    # an expert label and never becomes a scoring target.
    loader=DataLoader(CustomDataset(matrix,np.zeros(len(expected),dtype='int64'),layer=layer),batch_size=len(expected))
    raw=ensemble_predict([m.calibrated for m in ensemble.fitted],loader,
        device=torch.device('cpu'),method='raw',enforce_layer=False,labelling=None)
    if raw.shape!=(len(expected),5,len(ensemble.fitted)):
        raise SupportError('full transfer probability tensor extent mismatch')
    return {'units':expected,'classes':CLASSES,'raw_probabilities':raw,
            'mean_probabilities':raw.mean(axis=2),'models':tuple((m.repeat,m.held) for m in ensemble.fitted)}
