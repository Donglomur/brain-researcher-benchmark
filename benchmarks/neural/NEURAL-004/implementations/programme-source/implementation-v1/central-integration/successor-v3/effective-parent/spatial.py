"""Complete descriptive spatial calculations, separate from prediction targets."""
import math
from .common import PEOPLE,CHANNELS,fields,need,finite,integer,pin

PAIRS=(('Fp1','Fp2'),('AF3','AF4'),('F7','F8'),('F3','F4'),('FC1','FC2'),('FC5','FC6'),('T7','T8'),('C3','C4'),('CP1','CP2'),('CP5','CP6'),('P7','P8'),('P3','P4'),('PO3','PO4'),('O1','O2'))
WINDOWS=(('stimulus',0,.1),('stimulus',.1,.2),('stimulus',.2,.4),('response',-.3,-.2),('response',-.2,-.1),('response',-.1,0))

def summary(rows,values):
    need(len(rows)==len(values),'whole descriptive support');out=[]
    for a,r in ((None,None),(0,'left'),(0,'right'),(1,'left'),(1,'right')):
        selected=[v for row,v in zip(rows,values) if v is not None and (a is None or (row['instruction']==a and row['response']==r))]
        out.append({'instruction':a,'response':r,'n':len(selected),'mean_left_minus_right_volts':None if not selected else math.fsum(selected)/len(selected),
            'undefined':'empty_support' if not selected else None})
    return out

def regression(rows,values):
    import numpy as np
    selected=[(r,v) for r,v in zip(rows,values) if v is not None]
    if not selected:return {'n':0,'rank':0,'coefficients':None,'reason':'empty_support'}
    x=np.asarray([[1,r['contrast'],r['instruction'],r['contrast']*r['instruction'],int(r['response']=='right')] for r,v in selected],float)
    y=np.asarray([v for r,v in selected],float);s=np.linalg.svd(x,compute_uv=False)
    rank=int(np.sum(s>s[0]*1e-10)) if len(s) else 0
    if rank<5:return {'n':len(selected),'rank':rank,'coefficients':None,'reason':'rank_deficient'}
    b=np.linalg.lstsq(x,y,rcond=1e-10)[0];need(np.all(np.isfinite(b)),'finite descriptive OLS coefficients')
    return {'n':len(selected),'rank':rank,'coefficients':b.tolist(),'reason':None}

def compute(private_rows,alias_audit,event_indices,ledger,limits):
    """Yields all1820 event records and2184 fixed-window records; no tests of signs."""
    need(len(private_rows)<=integer(limits['max_trials'],1),'full spatial trial extent')
    lookup={(r['person'],r['epoch']):r['alias_audit'] for r in alias_audit}
    need(len(lookup)==len(alias_audit)==len(private_rows),'complete private metadata join')
    rows={p:[] for p in PEOPLE}
    for r in private_rows:
        audit=lookup[(r['person'],r['epoch'])];need(audit['contrast']==r['contrast'] and audit['instruction']==r['instruction'],'same target/behavior for postseal descriptions')
        rows[r['person']].append({**r,'response':audit['response']})
    need(all(rows.values()),'all26 people in descriptions')
    for p in PEOPLE:
        ledger.tick();local=rows[p]
        need(p in event_indices,'complete event disposition per person')
        by_epoch={r['epoch']:r for r in event_indices[p]['rows']};need(set(by_epoch)=={r['epoch'] for r in local},'complete same-observation event support')
        for event in range(5):
            for left,right in PAIRS:
                values=[];support=[]
                for row in local:
                    item=by_epoch[row['epoch']]
                    if item['status']!='complete':values.append(None);support.append({'epoch':row['epoch'],'status':item['status'],'sample':None});continue
                    ix=item['indices'][event];need(type(ix) is int and 0<=ix<row['samples'],'exact marginal sample index')
                    values.append(finite(row['waveform'][CHANNELS.index(left)][ix]-row['waveform'][CHANNELS.index(right)][ix]))
                    support.append({'epoch':row['epoch'],'status':'complete','sample':ix})
                yield {'kind':'event_aligned','person':p,'event':event,'pair':[left,right],'summaries':summary(local,values),'trial_support':support,
                    'same_observation_selection':True,'state_pin':event_indices[p]['state_pin'],'evaluation_pin':event_indices[p]['evaluation_pin']}
        for wi,(alignment,start,end) in enumerate(WINDOWS):
            # Keep original native sample support, including undefined empty intersections.
            supports=[]
            for row in local:
                shift=0 if alignment=='stimulus' else row['rt']
                ix=[t for t in range(row['samples']) if start<=t/512-shift<end]
                supports.append(ix)
            for left,right in PAIRS:
                ledger.tick();ledger.reserve({'requests':1},'descriptive fixed-window OLS attempt')
                values=[]
                for row,ix in zip(local,supports):
                    values.append(None if not ix else math.fsum(row['waveform'][CHANNELS.index(left)][t]-row['waveform'][CHANNELS.index(right)][t] for t in ix)/len(ix))
                yield {'kind':'fixed_window','person':p,'window_index':wi,'alignment':alignment,'window_seconds':[start,end],'pair':[left,right],
                    'summaries':summary(local,values),'trial_support':[{'epoch':r['epoch'],'intersection_samples':ix,'n':len(ix),'undefined':not bool(ix)} for r,ix in zip(local,supports)],
                    'regression':regression(local,values),'sample_selection_depends_on_RT':True,'independent_biological_validation':False}
