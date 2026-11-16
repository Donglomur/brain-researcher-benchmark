"""Scientific calculations selected from original figure consumers, never run here.

Original plotting sources stay unchanged. Undefined/nonfinite source summaries
fail explicitly; no epsilon, nearest neighbour, row dropping or clipping repair.
"""
from .core import need
def symmetric_theory(e):
 import numpy as np
 a=np.asarray(e);need(a.shape==(10000,) and np.all(a.imag==0),'complete symmetric connectivity eigenbasis')
 a=a.real;need(np.all(a<1),'stable complete source spectrum')
 variance=1/(2*(1-a));timescale_seconds=.020/(1-a)
 return {'eigenvalues':a,'normalized_noise_covariance_variance':variance,'timescale_seconds':timescale_seconds,
  'variance_per_second':variance/timescale_seconds}
def rotations(e,threshold=.25):
 import numpy as np
 e=np.asarray(e);keep=(np.abs(e)>threshold)&(e.imag>=0)
 selected=e[keep];need(len(selected)>0,'source rotation support is nonempty')
 rotation=(np.angle(selected)/(2*np.pi))/(-np.log10(np.abs(selected)))
 need(np.isfinite(rotation).all(),'source rotation summary defined; no silent clipping')
 return {'stats':np.r_[rotation.mean(),rotation.std(),np.percentile(rotation,[5,25,50,75,95])],
  'selected_count':np.asarray([len(selected)]),'selected_indices':np.flatnonzero(keep),'values':rotation}
def empirical_pc(rows):
 import numpy as np
 need(len(rows)==29,'all empirical Fig3 sessions')
 groups=(list(range(18)),list(range(26,29)),list(range(18,26)));nmax=(400,100,100);out=[]
 for indices,n in zip(groups,nmax):
  # Exact avg_acg: average the unnormalized source ACGs first, then divide
  # the pooled curve by pooled zero-lag. Never average normalized sessions.
  pooled=np.zeros((400,100))
  for i in indices:
   a=np.asarray(rows[i]['acg']);need(a.ndim==2 and a.shape[0]>=400 and a.shape[1]>=100,'full avg_acg source support')
   pooled+=a[:400,:100]
  pooled/=len(indices);need(np.all(pooled[:,:1]!=0),'source zero-lag normalization is defined');pooled/=pooled[:,:1]
  lag=pooled[:n,4:7].mean(-1);need(np.all(lag>0),'source logarithmic lag-index statistic is defined')
  corr=np.asarray([np.corrcoef(np.log(lag),np.log(1+np.arange(n)))[0,1]])
  ranks=np.round(np.exp(np.linspace(np.log(.5),np.log(n-1),50))).astype('int32')
  out.append({'pooled_zero_lag_normalized':pooled,'lag4_6_index':lag,'logrank_correlation':corr,'display_rank_indices_with_duplicates':ranks})
 return out
def distance_odds(strong,other,pstrong):
 import numpy as np
 s=np.asarray(strong);o=np.asarray(other);need(s.shape==o.shape and s.ndim>=2 and s.shape[-1]>=5,'complete source distance support')
 nn=s.shape[-2];nstrong=int(np.round(pstrong*nn));nother=nn-nstrong
 need(0<nstrong<nn,'source nonempty strong/other populations')
 sm=s.mean(axis=-2);om=o.mean(axis=-2);need(np.all(om!=0),'source odds denominator defined')
 odds=sm/nstrong/(om/nother);far=odds[...,-4:].mean(-1);need(np.all(far!=0),'source far-bin denominator defined')
 return {'odds':odds,'near_far_ratio':odds[...,:1].mean(-1)/far,'strong_neurons':np.asarray([nstrong]),'other_neurons':np.asarray([nother])}
def augment(operation,result):
 derived={}
 if operation=='dense_covariance':
  need(len(result)==40,'all dense networks before derivation')
  for i,r in enumerate(result):need(r['network']==i%10 and r['symmetry']==(0,1/3,2/3,1)[i//10],'source dense replicate axis')
  derived['symmetric_theory']=[symmetric_theory(r['connectivity_eigenvalues']) for r in result[:10]]
 if operation in ('empirical_dynamics','simulated_dynamics'):
  need(len(result)==(29 if operation=='empirical_dynamics' else 8),'complete Fig3 operation denominator')
  derived['rotations']=[rotations(r['e']) for r in result]
  if operation=='empirical_dynamics':derived['pc_groups']=empirical_pc(result)
 if operation=='local_connectivity':
  need(len(result)==21 and result[18]==200 and result[19]==.01 and result[20]==20,'exact literal local tuple/strong-pair definitions')
  derived['distance']=distance_odds(result[12],result[13],result[19])
 if operation=='neural_strong_pairs':
  need(len(result)==12 and result[9]==200 and result[10]==.01 and result[11]==20,'exact literal neural strong-pair definitions')
  need(len(result[4])==len(result[5]),'complete aligned neural source cohort')
  derived['distance']=[distance_odds(s,o,result[10]) for s,o in zip(result[4],result[5])]
 return {'raw':result,'derived':derived}
def part(selector,shape):return {'selector':selector,'shape':shape,'kind':'real'}
def fixed_bindings(operation):
 """Concrete source-defined derived joins; unknown native input geometry is not fabricated."""
 out={}
 if operation=='dense_covariance':
  out['variance_timescale_relation']=[part(['derived','symmetric_theory',i,k],[10000]) for i in range(10) for k in ('eigenvalues','normalized_noise_covariance_variance','timescale_seconds','variance_per_second')]
 if operation in ('empirical_dynamics','simulated_dynamics'):
  out['rotation_distributions']=[part(['derived','rotations',i,k],[7] if k=='stats' else [1]) for i in range(29 if operation=='empirical_dynamics' else 8) for k in ('stats','selected_count')]
 if operation=='empirical_dynamics':
  out['pooled_normalized_curves']=[part(['derived','pc_groups',i,k],shape) for i,n in enumerate((400,100,100)) for k,shape in (('pooled_zero_lag_normalized',[400,100]),('lag4_6_index',[n]),('logrank_correlation',[1]),('display_rank_indices_with_duplicates',[50]))]
 if operation=='local_connectivity':
  out['distance_odds']=[part(['derived','distance','odds'],[10,12,15]),part(['derived','distance','near_far_ratio'],[10,12])]
 # Neural cohort count/identity and the remaining shape bindings remain
 # unissued; the exact source-derived values exist but are not declared ready.
 return out
