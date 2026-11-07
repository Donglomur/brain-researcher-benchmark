"""Fixed operator only: all five PUBLIC blocks; no private labels or scoring."""
import argparse,math,sys
from pathlib import Path
def need(ok, why):
    if not ok:
        raise ValueError(why)


def ranks(values):
    """Average zero-based ranks, normalized by n-1; one/all-tied value is0.5."""
    n = len(values)
    need(n >= 1 and all(type(x) in (int, float) and math.isfinite(x) for x in values),
         'finite scalar rank vector')
    if n == 1:
        return [0.5]
    ordered = sorted(range(n), key=lambda i: values[i])
    result = [0.0] * n
    start = 0
    while start < n:
        stop = start + 1
        while stop < n and values[ordered[stop]] == values[ordered[start]]:
            stop += 1
        mid = (start + stop - 1) / (2.0 * (n - 1))
        for i in ordered[start:stop]:
            result[i] = mid
        start = stop
    return result


def baseline(calibration_peaks, calibration_active):
    need(len(calibration_peaks) == len(calibration_active) == 5, 'all5public blocks')
    n = len(calibration_peaks[0]); total = [0.0] * n
    for values, active in zip(calibration_peaks, calibration_active):
        need(len(values) == len(active) == n, 'same calibration cell inventory')
        chosen = [i for i, yes in enumerate(active) if yes]
        block = [0.5] * n
        if len(chosen) >= 2:
            for i, value in zip(chosen, ranks([values[i] for i in chosen])):
                block[i] = value
        for i, value in enumerate(block):
            total[i] += value / 5.0
    return total


def predict(sessions,np):
    out=[]
    for session in sessions:
        blocks=np.concatenate((session['calibration'],session['validation']),axis=0)
        peaks=np.argmax(blocks,axis=1).tolist()
        active=(np.max(blocks,axis=1)!=np.min(blocks,axis=1)).tolist()
        fixed=baseline(peaks,active)
        for query in session['metadata']['queries']:
            out.append({'query_id':query['query_id'],'ordering_scores':list(fixed)})
    return {'schema':'neural035-order-predictions-v1','predictions':out}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    import numpy as np
    if np.__version__!='2.2.6':raise ValueError('original public-loader numerical version')
    sys.path.insert(0,str(Path(a.input)))
    import load_public,io_utils
    sessions=load_public.load(a.input,np)
    if sum(len(s['metadata']['cell_ids']) for s in sessions)!=1012:raise ValueError('all1012 session-local cells')
    io_utils.write_new(a.output,predict(sessions,np),2000000)
if __name__=='__main__':main()
