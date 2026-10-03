"""Disclosed reporting algebra, with no source I/O or endpoint constants."""
import math
import numpy as np


def need(ok,reason):
    if not ok: raise ValueError(reason)


def information(counts,occupancy):
    c=np.asarray(counts); o=np.asarray(occupancy,dtype=np.float64)
    need(c.ndim==o.ndim==1 and c.shape==o.shape and c.dtype.kind in 'iu','count_shape_type')
    need(np.all(c>=0) and np.isfinite(o).all() and np.all(o>=0),'count_occupancy_values')
    need(not np.any((o==0)&(c!=0)),'count_in_unoccupied_bin')
    n=sum(int(x) for x in c); t=math.fsum(float(x) for x in o)
    need(t>0,'zero_observed_duration')
    if n==0: return None
    return math.fsum((int(x)/n)*math.log2((int(x)/n)/(float(d)/t))
                     for x,d in zip(c,o) if x>0)


def replay(occupancy,raw_counts,shifted_counts,unit_ids,draws=300):
    raw=np.asarray(raw_counts); shifted=np.asarray(shifted_counts)
    need(raw.shape==(len(unit_ids),20) and shifted.shape==(len(unit_ids),draws,20),'evidence_shapes')
    need(raw.dtype.kind in 'iu' and shifted.dtype.kind in 'iu','integer_counts_required')
    duration=math.fsum(float(x) for x in occupancy); rows=[]
    for i,uid in enumerate(unit_ids):
        n=sum(int(x) for x in raw[i]); value=information(raw[i],occupancy)
        need(value is not None,'eligible_unit_without_spikes')
        null=[information(c,occupancy) for c in shifted[i]]
        defined=all(v is not None for v in null)
        mean=math.fsum(null)/draws if defined else None
        rows.append(dict(unit_id=str(uid),n_spikes=n,mean_rate_hz=n/duration,
            raw_bits_per_spike=value,null_mean_bits_per_spike=mean,
            shift_adjusted_bits_per_spike=value-mean if defined else None,
            p_upper=(1+sum(v>=value for v in null))/(draws+1) if defined else None,
            status='ok' if defined else 'undefined_null_draw'))
    return rows


def summarize(rows):
    n=len(rows); defined=sum(r['status']=='ok' for r in rows)
    def mean(key):
        if not n or any(r[key] is None for r in rows): return None
        return math.fsum(float(r[key]) for r in rows)/n
    return dict(schema_version='ratplace-output-v2',task_id='RATPLACE-001',
        status='complete' if n else 'no_eligible_units',n_units=n,n_null_defined_units=defined,
        mean_raw_bits_per_spike=mean('raw_bits_per_spike'),
        mean_null_bits_per_spike=mean('null_mean_bits_per_spike'),
        mean_shift_adjusted_bits_per_spike=mean('shift_adjusted_bits_per_spike'))
