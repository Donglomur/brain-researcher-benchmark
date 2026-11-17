"""Root-selected target-blind37-feature alternative; no target argument exists.

Derivative of pinned GPL3 NeuroPyxels feature definitions, modified2026-11-11.
This is a prospective recipe, not historical baseline equivalence. Actual QC
producer independence and source clock/channel support remain qualification
requirements. No class-dependent or universal extra refractory edit is made.
"""
from c4_distribution.import_guard import require_bound_source as _c4_require_source
from dataclasses import dataclass
from .cohort import SupportError

OMIT=('label','dataset','unit','relevant_channel','any_somatic','max_peaks')

@dataclass(frozen=True)
class QcSourceBinding:
    unit: object
    source_identity: str
    mask_producer_identity: str
    independence_review_identity: str
    disposition: str

    def validate(self,key):
        if self.unit!=key:raise SupportError('QC source/unit identity mismatch')
        if self.disposition!='independently_eligible' or not all((self.source_identity,
                self.mask_producer_identity,self.independence_review_identity)):
            raise SupportError('independently eligible target-blind QC provenance unresolved')

@dataclass(frozen=True)
class FeatureRecipe:
    source_revision: str
    channel_count: int
    source_window_seconds: float
    waveform_type: str
    clip_seconds: tuple
    support_provenance: str

    def validate(self):
        if self.source_revision!='703a10fb43fc7fe0076c9c331e6b52d3195b5e60':raise SupportError('wrong feature definition revision')
        # Source dataset_init fixes10 channels and120 samples at30kHz. These
        # specify waveform support, not a refractory constant or new neuron rule.
        if self.channel_count!=10 or self.source_window_seconds!=120/30000:
            raise SupportError('complete original waveform-window extent required')
        if self.waveform_type!='flipped' or self.clip_seconds!=(.001,.002) or not self.support_provenance:
            raise SupportError('explicit original feature waveform recipe required')

@dataclass(frozen=True)
class FeatureRow:
    unit: object
    disposition: str
    values: object
    reason: str
    qc_binding: QcSourceBinding

@dataclass(frozen=True)
class FeatureTable:
    names: tuple
    rows: tuple
    recipe: FeatureRecipe

    def require_complete(self,units):
        if tuple(r.unit for r in self.rows)!=tuple(units) or len(set(units))!=len(units):
            raise SupportError('feature table changed full ordered support')
        if len(self.names)!=37 or len(set(self.names))!=37:raise SupportError('complete37 feature schema required')
        if any(r.disposition!='valid' for r in self.rows):
            raise SupportError('invalid feature dispositions retained; whole estimator unavailable, no available-case fit')
        return self

def admit_feature_bindings(keys,qc_bindings,recipe):
    recipe.validate();keys=tuple(keys)
    if len(set(keys))!=len(keys) or set(qc_bindings)!=set(keys):
        raise SupportError('complete raw/QC biological identity join required')
    for key in keys:qc_bindings[key].validate(key)
    return keys

def admit_feature_inputs(raw_units,qc_bindings,recipe):
    return admit_feature_bindings(tuple(u.key for u in raw_units),qc_bindings,recipe)

def extract_target_blind(raw_units,qc_bindings,recipe):
    """Every row remains present; only actual finite37-feature rows are valid.

    The source clock is retained. Original waveform_features internally
    conforms its peak waveform; non30kHz input requires a separately resolved
    waveform/spike feature-clock contract and is marked invalid, not silently
    corrected. All V1 external deep transfer routes remain independent.
    """
    _c4_require_source()
    keys=admit_feature_inputs(raw_units,qc_bindings,recipe)
    import numpy as np
    _c4_require_source()
    from npyx import datasets,feat
    names=tuple(k for k in feat.FEATURES if k not in OMIT);rows=[];failures=[]
    for raw,key in zip(raw_units,keys):
        binding=qc_bindings[key]
        try:
            spikes=np.asarray(raw.spike_indices);sane=np.asarray(raw.sane_mask);qc=np.asarray(raw.quality_mask)
            if sane.dtype.kind!='b' or qc.dtype.kind!='b' or sane.shape!=spikes.shape or qc.shape!=spikes.shape:
                raise SupportError('unaligned genuine QC masks')
            selected=spikes[sane & qc]  # no enforce_rp; no target-conditioned path
            if len(selected)<2:raise SupportError('insufficient independently eligible source spikes')
            if raw.sampling_rate!=30000:
                raise SupportError('non30kHz feature-clock qualification unresolved; row retained')
            waveform=np.asarray(raw.multichannel_template);channels=np.asarray(raw.channel_map)
            if waveform.ndim!=2:raise SupportError('missing actual multichannel waveform; no tiling invented for spatial features')
            if waveform.shape[0]>waveform.shape[1]:waveform=waveform.T
            if channels.ndim!=2 or channels.shape[0]!=waveform.shape[0] or waveform.shape[0]<recipe.channel_count:
                raise SupportError('waveform/channel-map support cannot supply all spatial features')
            if not np.isfinite(waveform).all() or not np.isfinite(channels).all():raise SupportError('nonfinite source waveform/channel support')
            samples=int(recipe.source_window_seconds*raw.sampling_rate)
            cropped,peak=datasets.crop_original_wave(waveform,samples,recipe.channel_count)
            chanmap=datasets.crop_chanmap(channels,peak,recipe.channel_count)
            if cropped.shape!=(recipe.channel_count,samples) or chanmap.shape[0]!=recipe.channel_count:
                raise SupportError('original crop/channel identity extent unresolved; no fabricated coordinates')
            temporal=feat.temporal_features(selected,raw.sampling_rate)
            shape=feat.waveform_features(cropped,recipe.channel_count//2,chanmap,
                waveform_type=recipe.waveform_type,_clip_size=recipe.clip_seconds,fs=raw.sampling_rate)
            combined=dict(zip(feat.FEATURES[3:],[*temporal,*shape],strict=True))
            values=np.asarray([combined[k] for k in names],dtype=float)
            if values.shape!=(37,) or not np.isfinite(values).all():raise SupportError('undefined original feature value')
            rows.append(FeatureRow(key,'valid',values,'complete target-blind37-feature producer returned',binding))
        except (ValueError,ArithmeticError,IndexError,KeyError) as error:
            failures.append((key,error))
            rows.append(FeatureRow(key,'invalid',None,type(error).__name__,binding))
    return FeatureTable(names,tuple(rows),recipe),tuple(failures)
