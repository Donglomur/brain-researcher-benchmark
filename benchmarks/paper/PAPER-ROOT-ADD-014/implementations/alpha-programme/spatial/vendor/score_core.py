"""Prospective finite-artifact evaluation; no fitting or file I/O.
Source-formula replay is distinct from MATLAB optimizer/bitwise reproduction.
"""
from fractions import Fraction
import math
import numpy as np
from forward import evaluate
from metrics import source_fold_projected_xval_percent,literal_paper_eq6_percent,FOLD_LABELS,aggregate_participants
from protocol import PARTICIPANTS,CONDITIONS,condition_key

def native_five(p,model,sign_free):
 a=np.asarray(p)
 if a.shape!=(7,)or a.dtype.kind!='f':raise ValueError('native seven-parameter source row')
 if not np.isfinite(a[[0,1,2,3,4,6]]).all():return None
 if a[4]!=1 or not (a[5]==np.inf or (a[6]==0 and a[5]>=1)):raise ValueError('published source is not frozen linear GS/OG')
 if model=='OG'and a[6]!=0:raise ValueError('published OG source ratio')
 return [float(a[0]),float(a[1]),abs(float(a[2])),float(a[3]) if sign_free else max(0.,float(a[3])),float(a[6])]

def score_case(y,stimulus,parameters,*,model,sign_free):
 y=np.asarray(y)
 if y.shape!=(75,)or y.dtype!=np.dtype('float64'):raise ValueError('source75float64 row')
 out={'status':'defined','source_cv':None,'literal_eq6':None,'full_geometry':None}
 results={k:evaluate(stimulus,parameters[k],model=model,allow_negative_gain=sign_free)for k in('full','train_first','train_second')}
 if any(x['status']!='defined'for x in results.values()):
  out.update(status='unsupported_forward',forward_dispositions={k:v['reason']for k,v in results.items()});return out
 # Training first38 predicts last37; training last37 predicts first38.
 pred=np.concatenate((results['train_second']['prediction'][:38],results['train_first']['prediction'][38:]))
 support=np.isfinite(y)
 out['source_cv']=source_fold_projected_xval_percent(y,pred,FOLD_LABELS,support_mask=support)
 out['literal_eq6']=literal_paper_eq6_percent(y,pred,support_mask=support)
 out['full_geometry']=results['full']['geometry']
 if out['source_cv']['status']!='defined':out['status']='undefined_source_cv'
 out['native_nan_parity_established']=bool(support.all())
 return out

def finite_mean(values):
 if not values or any(v is None or not math.isfinite(v)for v in values):return None
 return float(sum((Fraction.from_float(float(x))for x in values),Fraction())/len(values))
def difference(a,b):
 if a is None or b is None:return None
 try:v=float(Fraction.from_float(a)-Fraction.from_float(b))
 except OverflowError:return None
 return v if math.isfinite(v)else None

def aggregate(rows,case_reports,persons):
 """All eight frozen conditions and all nine native cohorts; undefined propagates."""
 expected={p['participant']:p['electrode_ids']for p in persons}
 if set(expected)!=set(PARTICIPANTS):raise ValueError('full participant cohort')
 outputs={}
 for signal,model,sign_free in CONDITIONS:
  key=condition_key(signal,model,sign_free);selected=[r for r in rows if (r['signal'],r['model'],r['allow_negative_gain'])==(signal,model,sign_free)]
  vals={p:{}for p in PARTICIPANTS};saved={p:{}for p in PARTICIPANTS};baseline={p:{}for p in PARTICIPANTS};err={p:{}for p in PARTICIPANTS}
  for row in selected:
   r=case_reports[row['case_id']];p=row['participant'];e=row['electrode_id'];c=r['candidate'].get('source_cv');b=r.get('baseline');bv=b.get('source_cv')if b else None
   v=c['value_percent']if c else None;u=bv['value_percent']if bv else None;a=r['published_xval_percent']
   vals[p][e]=v;baseline[p][e]=u;saved[p][e]=a;d=difference(v,a);err[p][e]=abs(d)if d is not None else None
  ca=aggregate_participants(vals,expected);ba=aggregate_participants(baseline,expected);au=aggregate_participants(saved,expected);er=aggregate_participants(err,expected)
  outputs[key]={'candidate':ca,'same_formula_author_parameters':ba,'published_author_xval':au,'absolute_error_to_published_xval':er,
    'prospective_equal_person_gain_pp':difference(ca['prospective_equal_person_mean_percent'],ba['prospective_equal_person_mean_percent'])}
 return {'conditions':outputs,'primary_reconstruction_metric':'corrected_alpha__GS__positive_gain absolute_error_to_published_xval prospective_equal_person_mean_percent;lowerbetter',
 'primary_model_comparison':'corrected_alpha__GS__positive_gain prospective_equal_person_gain_pp;higherbetter;requiresverifiedtrain-onlyexecutionforimprovementclaim',
 'original_source_cv_has_full_series_seed_initialization':True,'artifact_alone_proves_training_isolation':False,
 'full_paper_reproduction':False,'arbitrary_success_threshold':None}
