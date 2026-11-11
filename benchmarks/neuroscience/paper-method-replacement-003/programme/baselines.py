"""Full-feature author baseline callers, not a substitute for the deep model.

GPL-3.0 integration of NeuroPyxels 703a10f, modified 2026-11-11. No fitted model
or feature data is imported or created during source construction.
"""
from c4_distribution.import_guard import require_bound_source as _c4_require_source
from .cohort import CLASSES,SupportError,Population
from .classification import _targets

def reconstructed_label_conditioned_features(raw_units,protected_labels):
    """Label-conditioned reconstruction, not original waveform-crop parity.

    This producer must never be exposed as target-blind query preprocessing.
    The 10 ms complex-spike filtering branch is retained visibly, not corrected
    or silently applied to every class as a new method.
    """
    _c4_require_source()
    import numpy as np
    _c4_require_source()
    from npyx import feat,datasets,spk_t
    names=tuple(x for x in feat.FEATURES if x not in
                ('label','dataset','unit','relevant_channel','any_somatic','max_peaks'))
    keys=tuple(u.key for u in raw_units)
    if set(keys)!=set(protected_labels):raise SupportError('literal feature target identity mismatch')
    rows=[]
    for unit in raw_units:
        spikes=unit.spike_indices[unit.sane_mask & unit.quality_mask]
        label=protected_labels[unit.key]
        if label=='PkC_cs':spikes=spk_t.enforce_rp(spikes,enforced_rp=10,fs=unit.sampling_rate)
        waveform=np.asarray(unit.multichannel_template)
        if waveform.ndim!=2:raise SupportError('original spatial baseline requires aligned multi-channel template')
        if waveform.shape[0]>waveform.shape[1]:waveform=waveform.T
        peak=int(np.argmax(np.ptp(waveform,axis=1)))
        channels=np.asarray(unit.channel_map)
        if channels.shape[0]!=waveform.shape[0]:raise SupportError('template/channel support alignment unresolved')
        temporal=feat.temporal_features(spikes,unit.sampling_rate)
        shape=feat.waveform_features(waveform,peak,channels,waveform_type='flipped',fs=unit.sampling_rate)
        all_values=dict(zip(feat.FEATURES[3:],[*temporal,*shape],strict=True))
        rows.append([all_values[k] for k in names])
    matrix=np.asarray(rows)
    if matrix.shape!=(len(keys),37) or not np.isfinite(matrix).all():
        raise SupportError('undefined baseline features; retain unit disposition rather than zero-fill')
    return {'units':keys,'names':names,'matrix':matrix,
            'scope':'label_conditioned_literal_reproduction_only','held_label_used_for_refractory_filter':True}

def literal_features(source_path,members,*,source_group_dispositions,dataset_arguments,feature_arguments,csv_path):
    """Call the actual original dataset and feature producer, including its leak.

    Complete explicit source arguments are required. Dataset construction may
    inspect labels and discard records; exact eligible HDF5 identities must
    still match the independently retained census, or this call refuses. No
    result here is a target-blind prediction input or a protected benchmark.
    The original monkey MLI_B exclusion/resampling and numerical undefined
    feature support must be reconciled before claiming historical parity.
    """
    _c4_require_source()
    import numpy as np
    _c4_require_source()
    from npyx import datasets,feat
    if not dataset_arguments or not feature_arguments:
        raise SupportError('literal source preprocessing recipe is unresolved')
    if dataset_arguments.get('_label') not in ('optotagged_label','expert_label'):
        raise SupportError('explicit original label source required for reproduction')
    if feature_arguments.get('_wvf_type')!='flipped' or feature_arguments.get('ignore_exceptions',False):
        raise SupportError('flipped waveform and explicit failures required; no silent zero-filled features')
    source=datasets.NeuronsDataset(source_path,**dataset_arguments)
    expected=tuple(m.h5_group for m in members)
    if len(set(source.h5_ids))!=len(source.h5_ids) or not set(source.h5_ids)<=set(source_group_dispositions):
        raise SupportError('literal constructor identities missing from complete source census')
    if not set(expected)<=set(source.h5_ids):
        raise SupportError('literal constructor dropped eligible units; retain dispositions')
    if any(source_group_dispositions[k]!='excluded' for k in set(source.h5_ids)-set(expected)):
        raise SupportError('extra constructor units need explicit excluded dispositions')
    source._apply_mask(np.asarray([k in expected for k in source.h5_ids]))
    if tuple(source.h5_ids)!=expected:
        raise SupportError('literal selected source order differs from complete census')
    for m,info in zip(members,source.info):
        if info!=m.key.recording+'/'+m.key.unit:
            raise SupportError('literal source biological identity mismatch')
    frame=feat.h5_feature_extraction(source,save_path=csv_path,**feature_arguments)
    if len(frame)!=len(expected):raise SupportError('original feature producer changed complete support')
    names=tuple(x for x in feat.FEATURES if x not in
                ('label','dataset','unit','relevant_channel','any_somatic','max_peaks'))
    matrix=frame.loc[:,list(names)].to_numpy()
    if matrix.shape!=(len(expected),37) or not np.isfinite(matrix).all():
        raise SupportError('undefined literal features; complete census dispositions required')
    return {'units':tuple(m.key for m in members),'names':names,'matrix':matrix,
            'labels':dict(zip((m.key for m in members),frame['label'],strict=True)),
            'scope':'original_h5_feature_extraction_label_conditioned_reproduction_only',
            'held_label_used_for_refractory_filter':True}

def fit_baselines(cohort,feature_matrix,feature_names,keys,targets,external,*,model_names,source_seed):
    """Each selected published baseline, full ten-repeat LOO and both transfers."""
    _c4_require_source()
    expected=tuple(m.key for m in cohort.eligible(Population.MOUSE_GROUND_TRUTH))
    if tuple(keys)!=expected or len(feature_names)!=37 or len(set(feature_names))!=37:
        raise SupportError('complete named 37-feature/unit population required')
    if set(model_names)!={'logistic_regression','random_forest','gaussian_process'}:
        raise SupportError('all three author baseline model families required')
    if set(external)!={Population.MOUSE_EXPERT,Population.MONKEY_EXPERT}:
        raise SupportError('both full external cohorts required')
    import numpy as np
    import pandas as pd
    _c4_require_source()
    from npyx.feat import FEATURES
    from sklearn.model_selection import LeaveOneOut
    from sklearn.preprocessing import StandardScaler
    _c4_require_source()
    from npyx.ml import set_seed,run_cross_validation
    _c4_require_source()
    from npyx.c4.dataset_init import ArgsNamespace
    _c4_require_source()
    from npyx.c4.run_baseline_classifier import get_model_class,train_predict_test
    x=np.asarray(feature_matrix)
    expected_names=tuple(k for k in FEATURES if k not in ('label','dataset','unit','relevant_channel','any_somatic','max_peaks'))
    if tuple(feature_names)!=expected_names:raise SupportError('feature names/order do not match original producer')
    if x.shape!=(len(keys),37) or not np.isfinite(x).all():raise SupportError('undefined/missing baseline feature support')
    y=np.asarray(_targets(keys,targets));set_seed(source_seed)
    results={}
    for name in model_names:
        cls,params=get_model_class(ArgsNamespace(model=name,kernel='rbf'))
        cv=run_cross_validation(pd.DataFrame(x,columns=feature_names),pd.Series(y),10,params,oversampler=None,kfold=LeaveOneOut(),
                               model_class=cls,get_importance=name=='random_forest',scaler=StandardScaler())
        transfer={}
        for population,(other_keys,other_x,protected_y) in external.items():
            wanted=tuple(m.key for m in cohort.eligible(population))
            if tuple(other_keys)!=wanted or np.asarray(other_x).shape!=(len(wanted),37):
                raise SupportError('baseline external population/feature join mismatch')
            labels=np.asarray([CLASSES.index(protected_y[k]) for k in wanted])
            transfer[population.value]=train_predict_test(x,y,other_x,labels,params,
                oversampler=None,model_class=cls,scaler=StandardScaler(),n_runs=10)
        results[name]={'unit_order':expected,'feature_names':tuple(feature_names),
                       'loo':cv,'transfers':transfer,'profile':'released_baseline_source',
                       'scope':'label_conditioned_literal_reproduction_only; not target-blind predictive reference'}
    return results
