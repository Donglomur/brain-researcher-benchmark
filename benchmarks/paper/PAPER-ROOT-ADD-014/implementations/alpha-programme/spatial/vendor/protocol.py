"""Frozen prospective full-panel condition contract; no data-dependent selection."""
PARTICIPANTS=('p01','p02','p05','p06','p07','p08','p09','p10','p11')
CONDITIONS=(
 ('corrected_alpha','GS',False),('broadband','GS',False),
 ('raw_alpha','GS',False),('low_broadband','GS',False),
 ('corrected_alpha','OG',False),('broadband','OG',False),
 ('corrected_alpha','GS',True),('raw_alpha','GS',True),
)
SIGNALS={'corrected_alpha':'FaCLb','broadband':'bbS','raw_alpha':'FaLb','low_broadband':'bbL'}
SCHEMA='visual_alpha_full_panel_v1'

def band(participant,signal):
 if participant not in PARTICIPANTS or signal not in SIGNALS:raise ValueError('frozen participant/signal')
 b=SIGNALS[signal]
 return b+'BW' if signal=='corrected_alpha' and participant in ('p10','p11') else b

def source_names(participant,signal,model,allow_negative_gain):
 if (signal,model,allow_negative_gain) not in CONDITIONS:raise ValueError('frozen condition')
 b=band(participant,signal)
 prefix='prfbidirgain' if allow_negative_gain else 'prf'
 return (f'{participant}_freq_spectra-timeseries_avg-runs_{b}-decimate3.mat',
         f'{participant}_{prefix}-linear-{model.lower()}_avg-runs_{b}-decimate3.mat')

def condition_key(signal,model,allow_negative_gain):
 if (signal,model,allow_negative_gain) not in CONDITIONS:raise ValueError('frozen condition')
 return signal+'__'+model+('__sign_free' if allow_negative_gain else '__positive_gain')

# CLOSED input-identity census829d66a…; full released rows, not paper366QC mask.
RELEASED_COUNTS=dict(zip(PARTICIPANTS,(11,25,35,38,31,10,19,136,128)))
