"""Fixed independent cross-montage spectral ridge source, not an original baseline.

Averages the five predefined log-band-power features over available qualified
channels, giving a fixed5-column input across montages. Train-only normalizer,
fixed penalty grid and validation-only selection are inherited unchanged. There
is no coordinate guessing, channelpadding or actual fit during construction.
"""
import numpy as np
from .reference_linear import features,fit,predict

def pooled_features(epochs,*,input_unit):
 if input_unit!='mV':raise ValueError('prospective spectral control requires physical millivolts; never substitute normalized model patches')
 a=np.asarray(epochs);x=features(a,200);return x.reshape(len(a),a.shape[1],5).mean(1)
