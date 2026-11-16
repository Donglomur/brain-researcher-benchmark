"""Source-faithful native semantics. All numerical functions authored/static only.

Dependencies and MATLAB equivalence, RNG/quantile versions and authentic inputs
remain qualification gates. This module never silently corrects author behavior.
"""
def signed_native_permutation(a,b,random_uniform,draws=1000,optional_argument_present=True):
 import numpy as np
 a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
 if a.ndim!=1 or b.ndim!=1:raise ValueError('column-vector domain')
 observed=np.nanmean(a)-np.nanmean(b)
 if not optional_argument_present:observed=abs(observed)
 mixed=np.concatenate((a,b));null=[];indices=[]
 for _ in range(draws):
  u=np.asarray(random_uniform(len(a)),dtype=float)
  if u.shape!=(len(a),)or np.any((u<=0)|(u>=1)):raise ValueError('MATLAB RNG endpoint/version qualification required')
  selected=np.ceil(u*len(mixed)).astype(int)-1
  other=np.setdiff1d(np.arange(len(mixed)),selected)
  null.append(np.nanmean(mixed[selected])-np.nanmean(mixed[other]));indices.append({'first_with_replacement':selected.tolist(),'complement_unique':other.tolist()})
 null=np.asarray(null);p=float(np.sum(null>observed)/draws)
 return {'observed':float(observed),'null':null,'draw_indices':indices,'pvalue_native':p,'scientific_defined':bool(np.isfinite(observed)and np.all(np.isfinite(null))),'strict_upper_tail':True}

def physical_transition_role(prefvec):
 if prefvec==2:return {'a_nonpref':'high_to_mixed','b_pref':'low_to_mixed'}
 if prefvec==3:return {'a_nonpref':'low_to_mixed','b_pref':'high_to_mixed'}
 raise ValueError('native preference code')

def consecutive_native_mask(pvalues):
 import numpy as np
 p=np.asarray(pvalues,dtype=float);raw=p<.05;mask=np.zeros(raw.shape,dtype=bool);start=None
 for i,v in enumerate(np.r_[raw,False]):
  if v and start is None:start=i
  if not v and start is not None:
   if i-start>=3:mask[start:i]=True
   start=None
 return {'raw':raw,'consecutive':mask}

def native_event_block_tensor(event_matrices,block_trial_indices,window_indices):
 """One session/event. Preserve full-array zscore and whole block-slice guard."""
 import numpy as np
 z=[]
 for matrix in event_matrices:
  x=np.asarray(matrix,dtype=float);z.append((x-np.nanmean(x))/np.nanstd(x,ddof=1))
 a,b=window_indices;initial=np.zeros((len(z),b-a+1,3));history=[]
 if len(block_trial_indices)!=3:raise ValueError('low/mixed/high block axes')
 for block,indices in enumerate(block_trial_indices):
  avg=np.stack([np.nanmean(x[np.asarray(indices,dtype=int),a:b+1],axis=0)for x in z])
  nan=np.isnan(avg);assigned=bool(avg.size and np.all(~nan))
  if assigned:initial[:,:,block]=avg
  history.append({'block_axis':block,'preassignment':avg,'nan_mask':nan,'assigned':assigned,'default_zero_mask':np.full(avg.shape,not assigned,dtype=bool),'trial_indices':list(indices)})
 return initial,history

def native_acute_rows(rows):
 """Exact post-construction [distance,pre,post] filter/sort/mutation/bin path."""
 import numpy as np
 original=np.asarray(rows,dtype=float);keep=~(original[:,1]<.4);retained=original[keep];sort=np.argsort(retained[:,0],kind='stable');m=retained[sort].copy();before=m.copy()
 prezero=m[:,1]==0;m[prezero,0]=np.finfo(float).eps
 mid=m.copy();postzero=m[:,2]==0;m[postzero,0]=np.finfo(float).eps
 ratio=m[:,2]/m[:,1]
 if not len(m):raise ValueError('native empty retained rows; retain failure')
 # MATLAB positive-step colon is anchored to first/last mutated row, no resort.
 first,last=m[0,0],m[-1,0]
 if not np.isfinite(first+last):raise ValueError('native colon nonfinite endpoint')
 edges=np.arange(first,last+np.finfo(float).eps*max(abs(last),1),100.)if last>=first else np.array([])
 bins=[];membership=[]
 for lo,hi in zip(edges[:-1],edges[1:]):
  selected=(m[:,0]>=lo)&(m[:,0]<hi);values=ratio[selected];count=int(np.sum(~np.isnan(values)))
  bins.append({'lower':float(lo),'upper':float(hi),'mean':float(np.nanmean(values)),'sem':float(np.nanstd(values,ddof=1)/np.sqrt(count))if count else float('nan'),'count':count});membership.append(np.flatnonzero(selected).tolist())
 return {'original':original,'keep':keep,'sort':sort,'before':before,'after_pre_write':mid,'after':m,'pre_zero_mask':prezero,'post_zero_mask':postzero,'ratio':ratio,'edges':edges,'bins':bins,'membership':membership,'fit_bins':[i for i,b in enumerate(bins)if not np.isnan(b['mean'])],'native_semantics':'linear-index-distance-mutation-no-resort'}

def corrected_acute_rate_columns(rows,epsilon):
 """Distinct unselected sensitivity; NEVER substitute for native_acute_rows."""
 import numpy as np
 if epsilon<=0:raise ValueError('explicit positive epsilon policy')
 x=np.asarray(rows,dtype=float).copy();x[x[:,1]==0,1]=epsilon;x[x[:,2]==0,2]=epsilon
 return {'method':'corrected_rate_columns_separate_sensitivity','rows':x,'epsilon':epsilon}

def ati(u,v):
 import numpy as np
 u=np.asarray(u,dtype=float);v=np.asarray(v,dtype=float)
 if u.shape!=v.shape or not u.size or np.any(u<0)or np.any(v<0)or not np.all(np.isfinite(u))or not np.all(np.isfinite(v)):raise ValueError('ATI support/norm domain')
 # Keep ordinary finite-denominator arithmetic unchanged. Finite norms can
 # nevertheless overflow their sum; rescale only those pairs, not the support.
 with np.errstate(over='ignore'):
  denominator=u+v
 zero=denominator==0
 if np.any(zero):return {'value':None,'status':'scientifically_undefined','zero_count':int(np.sum(zero)),'full_count':int(u.size)}
 ratios=np.asarray(u/denominator)
 overflow=np.isinf(denominator)
 if np.any(overflow):
  large_u=u[overflow];large_v=v[overflow];scale=np.maximum(large_u,large_v)
  scaled_u=large_u/scale;scaled_v=large_v/scale
  ratios[overflow]=scaled_u/(scaled_u+scaled_v)
 return {'value':float(np.mean(ratios)),'status':'defined','zero_count':0,'full_count':int(u.size)}

def strict_native_tails(values,qualified_percentile):
 import numpy as np
 x=np.asarray(values,dtype=float)
 if not np.all(np.isfinite(x)):raise ValueError('undefined ATI cannot be a middle exclusion')
 lo=qualified_percentile(x,40);hi=qualified_percentile(x,60)
 return {'low':x<lo,'high':x>hi,'middle_or_tie':(x>=lo)&(x<=hi),'low_boundary':lo,'high_boundary':hi}
