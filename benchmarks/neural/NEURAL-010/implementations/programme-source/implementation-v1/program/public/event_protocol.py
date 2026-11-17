"""Fixed continuous-recording event semantics, following pinned timescoring defaults.

Half-open intervals,10Hz boundary quantization; merge gaps<90s then split>300s.
Reference tolerance30s before/60s after. Matching is event-overlap, not1:1.
"""
import math

RATE=10
MERGE_GAP=90
MAX_EVENT=300
TOLERANCE_START=30
TOLERANCE_END=60


def need(ok,message):
    if not ok:raise ValueError(message)


def canonical(events,duration):
    merged=[]
    for a,b in sorted(events):
        need(math.isfinite(a) and math.isfinite(b) and 0<=a<b<=duration,'finite in-record half-open event')
        a,b=round(a*RATE),round(b*RATE);need(a<b,'event survives10Hz boundary quantization')
        if merged and a-merged[-1][1]<MERGE_GAP*RATE:merged[-1][1]=max(merged[-1][1],b)
        else:merged.append([a,b])
    split=[]
    for a,b in merged:
        while b-a>MAX_EVENT*RATE:split.append([a,a+MAX_EVENT*RATE]);a+=MAX_EVENT*RATE
        split.append([a,b])
    return [[a/RATE,b/RATE] for a,b in split]


def from_scores(scores,duration):
    need(type(duration)is int and duration>0 and len(scores)==duration,'one score for every recorded second')
    raw=[];start=None
    for t,p in enumerate(scores):
        try:valid=type(p)in(int,float) and math.isfinite(p) and 0<=p<=1
        except OverflowError:valid=False
        need(valid,'finite probability in[0,1]; booleans invalid')
        if p>=.5 and start is None:start=t
        if p<.5 and start is not None:raw.append([start,t]);start=None
    if start is not None:raw.append([start,duration])
    return canonical(raw,duration)


def overlap(a,b):return max(0.,min(a[1],b[1])-max(a[0],b[0]))


def count_events(reference,hypothesis,duration):
    ref=canonical(reference,duration);hyp=canonical(hypothesis,duration)
    detected=[]
    for a,b in ref:
        window=[max(0.,a-TOLERANCE_START),min(float(duration),b+TOLERANCE_END)]
        occupied=math.fsum(overlap(window,h) for h in hyp)
        # Disjoint hyp events have no double-counted occupancy. This is the
        # source minOverlap=0 +1e-6 rule on the extended reference interval.
        if occupied/(window[1]-window[0])>1e-6:detected.append(window)
    fp=sum(not any(overlap(h,r)>0 for r in detected) for h in hyp)
    return {'reference_events':len(ref),'true_positive_events':len(detected),'false_alarm_events':fp,
            'false_negative_events':len(ref)-len(detected),'observed_seconds':duration,
            'annotated_ictal_seconds':math.fsum(b-a for a,b in reference)}


def summarize(counts):
    ref=sum(c['reference_events'] for c in counts);tp=sum(c['true_positive_events'] for c in counts)
    fp=sum(c['false_alarm_events'] for c in counts);seconds=sum(c['observed_seconds'] for c in counts)
    need(seconds>0,'positive observed duration')
    return {'event_f1':2*tp/(ref+tp+fp) if ref+tp+fp else None,
            'event_sensitivity':tp/ref if ref else None,'event_precision':tp/(tp+fp) if tp+fp else None,
            'false_alarms_per_24_observed_hours':fp*86400/seconds,
            'observed_seconds':seconds,'reference_events':ref,'true_positive_events':tp,
            'false_alarm_events':fp,'false_negative_events':ref-tp,
            'nonictal_seconds':seconds-sum(c['annotated_ictal_seconds'] for c in counts)}
