"""Label-free timing features from the already selected native phoneme starts."""
from bisect import bisect_right

GAP_EDGES_SAMPLES=(10,20,30,50,100,200,400)


def derive(starts,sample_count):
    if type(sample_count) is not int or not 125<=sample_count<=100000000 or not starts:
        raise ValueError('complete original250Hz run extent')
    if any(type(t) is not int or t<0 or t+125>sample_count for t in starts):
        raise ValueError('complete source event windows')
    previous=None;mapping={}
    for t in sorted(set(starts)):
        # Distinct predecessor avoids arbitrary event/label ordering at ties.
        gap=8 if previous is None else bisect_right(GAP_EDGES_SAMPLES,t-previous)
        mapping[t]=[(16*t)//sample_count,gap]
        previous=t
    return [mapping[t] for t in starts]
