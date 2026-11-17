"""Observed-data state contrast reconstruction; never a causal or model-gain estimator."""
from fractions import Fraction
from itertools import combinations
import math
import numpy as np
from state_core import AREAS,deterministic_pairs,unit_effects,area_effects,matched_area_units
PAIR_KEYS=tuple(a+'|'+b for a,b in combinations(AREAS,2))

def query_rows(meta):
 return [{'id':r['id'],'onset':r['onset'],'condition_key':(r['condition_key'],),'block':r['block'],'run_bin':r['run_bin'],'pupil_bin':r['pupil_bin']} for r in meta['rows'] if r['split']=='QUERY']

def reconstruct(meta,query_counts):
 rows=query_rows(meta);a=np.asarray(query_counts)
 if a.shape!=(len(rows),len(meta['unit_ids'])) or a.dtype.kind not in 'iu' or np.any(a<0):raise ValueError('complete observed query count matrix required')
 # Only arithmetic projection to rates; no model fit, state thresholds or selection use query counts.
 rates=a.astype(np.float64)/meta['exposure_seconds'];out={}
 ids={v:i for i,v in enumerate(meta['unit_ids'])}
 for mode in ('running','pupil'):
  pairs=deterministic_pairs(rows,mode);effects=unit_effects(rates,pairs,meta['baseline_rates']);areas=area_effects(effects,meta['areas']);matched={};support={}
  for aa,bb in combinations(AREAS,2):
   key=aa+'|'+bb;sel=matched_area_units(meta['unit_metadata'],(aa,bb));left=sel['selected_unit_ids'][aa];right=sel['selected_unit_ids'][bb]
   if not left or not pairs.low_indices:matched[key]=None
   else:matched[key]=sum((effects.values[ids[v]] for v in left),Fraction())/len(left)-sum((effects.values[ids[v]] for v in right),Fraction())/len(right)
   support[key]=sel
  out[mode]={'areas':areas,'matched':matched,'pairing':pairs,'matched_support':support}
 return out

def numeric_report(reconstruction):
 out={}
 for mode,v in reconstruction.items():
  out[mode]={'areas':{k:None if x is None else float(x) for k,x in v['areas'].values.items()},'matched':{k:None if x is None else float(x) for k,x in v['matched'].items()}}
  if any(x is not None and not math.isfinite(x) for d in out[mode].values() for x in d.values()):raise ValueError('effect beyond finite submission range; unavailable without clipping')
 return out
