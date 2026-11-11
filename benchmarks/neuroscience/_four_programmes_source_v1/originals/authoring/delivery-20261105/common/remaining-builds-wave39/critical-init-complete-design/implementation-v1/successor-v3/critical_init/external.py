"""Independent numeric external-task projections after original identity/schema closure."""
from .custody import need
from .guard import integer,real
from .numerics import matrix,zscore

def task_psth(spikes,onsets,condition_ids,*,all_conditions,before_ms,after_ms,bin_ms,unit_rule):
    import numpy as np
    x=matrix(spikes);s=np.asarray(onsets);c=np.asarray(condition_ids)
    need(s.ndim==c.ndim==1 and len(s)==len(c)>0 and s.dtype.kind in 'iu','aligned complete native trial map')
    integer(before_ms);integer(after_ms,1);integer(bin_ms,1)
    need((before_ms+after_ms)%bin_ms==0,'complete full source windows')
    offsets=np.arange(-before_ms,after_ms);inds=s[:,None]+offsets
    need(inds.min()>=0 and inds.max()<x.shape[1],'source windows must not silently wrap or clip')
    a=x[:,inds].reshape(len(x),len(s),-1,bin_ms).mean(axis=-1)
    need(len(set(all_conditions))==len(all_conditions)and set(c)<=set(all_conditions),'complete condition census including empty conditions')
    groups=[]
    for label in all_conditions:
        mask=c==label;need(mask.any(),'empty original condition is unscorable; cannot silently drop')
        groups.append(a[:,mask].mean(axis=1))
    psth=np.stack(groups,axis=1);flat=psth.reshape(len(x),-1)
    need(unit_rule in ('all','sum_gt_1'),'declared original unit eligibility')
    keep=np.ones(len(x),dtype=bool)if unit_rule=='all'else flat.sum(axis=1)>1
    need(keep.any(),'nonempty original units')
    return {'psth':psth[keep],'zscored_flat':zscore(flat[keep]),'unit_indices':np.flatnonzero(keep),
            'conditions':all_conditions,'window_ms':[-before_ms,after_ms],'bin_ms':bin_ms}

def rtt_onsets(target_position,finger_velocity):
    import numpy as np
    target=matrix(target_position);velocity=matrix(finger_velocity)
    need(len(target)==len(velocity)and target.shape[1]==velocity.shape[1]==2,'aligned native target/velocity stream')
    speed=np.sqrt((velocity**2).sum(axis=1));cues=np.flatnonzero((np.diff(target,axis=0)!=0).sum(axis=1))+1
    cues=cues[:-1][np.diff(cues)>1];onsets=[];kept=[]
    for start,end in zip(cues,np.r_[cues[1:],len(target)]):
        hits=np.flatnonzero(speed[start:end]>20)
        if len(hits):onsets.append(int(start+hits[0]));kept.append(int(start))
    kept=np.asarray(kept,dtype='int64');need(len(kept),'original movements found')
    direction=target[kept]-target[kept-1];angle=np.arctan2(direction[:,1],direction[:,0])/np.pi*180
    angle[angle>=180]=180-1e-3;bins=np.floor((angle+180)/15).astype('int64')
    return {'onsets':np.asarray(onsets,dtype='int64'),'condition_ids':bins,'angles_degrees':angle,
            'all_conditions':list(range(int(bins.max())+1)),
            'bin_width_degrees':15,'not_fifteen_conditions':True}

def maze_onsets(cursor_position,trial_start,trial_end):
    import numpy as np
    x=matrix(cursor_position);start=np.asarray(trial_start);end=np.asarray(trial_end)
    need(start.shape==end.shape and start.ndim==1 and start.dtype.kind in 'iu'and end.dtype.kind in 'iu','native millisecond trial boundaries')
    onsets=[];kept=[];failed=[]
    for i,(a,b)in enumerate(zip(start[:-1],end[:-1])):
        need(0<=a<b<=len(x),'complete native trial bounds')
        moves=np.flatnonzero((np.diff(x[a:b],axis=0)**2).sum(axis=1)>.05)
        if len(moves):onsets.append(int(a+moves[0]));kept.append(i)
        else:failed.append(i)
    return {'onsets':np.asarray(onsets,dtype='int64'),'trial_indices':np.asarray(kept,dtype='int64'),
            'no_movement_trial_indices':failed,'original_excluded_final_trial':len(start)-1}

