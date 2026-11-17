"""Full source-animal CV, refit and held-animal prediction, using real model code."""
from collections import defaultdict
from .contracts import need,ARMS,CLASSES,ScientificUnavailable
from .native_projection import reference_features
from .preparation import session_view
from . import models

def matrix(views,head,tick):
    import numpy as np
    eligible=[v for v in views if v['status']=='complete'];byanimal=defaultdict(list)
    for v in eligible:byanimal[v['animal']].append(v)
    if not byanimal:raise ScientificUnavailable('no_matching_source_animals',{'head':head})
    xx=[];yy=[];ww=[]
    for animal,sessions in sorted(byanimal.items()):
        for s in sorted(sessions,key=lambda v:v['ordinal']):
            windows=s['windows'];need(windows,'complete training windows')
            for w in windows:
                tick();x=reference_features(w,tuple(range(w['unit_count'])),head,tick);mask=w['mask']
                need(len(x)==len(w['values'])==len(mask) and mask.any(),'source common window mask')
                xx.append(x[mask]);yy.append(w['values'][mask]);ww.append(np.full(int(mask.sum()),1./(len(byanimal)*len(sessions)*len(windows)*int(mask.sum()))))
    result={'x':np.concatenate(xx),'y':np.concatenate(yy),'weights':np.concatenate(ww),'animals':tuple(sorted(byanimal))}
    if head in CLASSES and set(result['y'].tolist())!=set(range(CLASSES[head])):
        raise ScientificUnavailable('missing_source_class',{'head':head,'observed':sorted(set(result['y'].tolist()))})
    return result

def complete_reference(prepared,cell,owner):
    head=cell[0];source=[sid for sid,s in prepared['public'].items() if s['role']=='source'];evaluation=[sid for sid,s in prepared['public'].items() if s['role']=='evaluation']
    need(len(source)==423 and len(evaluation)==29,'complete original reference census')
    result={};states={};selection={}
    for arm in ARMS:
        views=[session_view(prepared,s,cell,arm,True) for s in source]
        folds=[]
        for fold in range(5):
            tr=[v for v in views if v['status']=='complete' and v['fold']!=fold]
            va=[v for v in views if v['status']=='complete' and v['fold']==fold]
            # Scientifically unavailable reference support is reported upstream as a whole
            # cell disposition, never silently selected on fewer folds.
            folds.append((matrix(tr,head,owner.tick),matrix(va,head,owner.tick)))
        config,cv=models.reference_select(folds,head,cell[3],owner.tick)
        allsource=matrix(views,head,owner.tick);state=models.fit(allsource['x'],allsource['y'],allsource['weights'],head,config,cell[3])
        states[arm]=state;selection[arm]={'selected':config,'all_five_folds':cv,'source_animals':allsource['animals']}
        for sid in evaluation:
            view=session_view(prepared,sid,cell,arm,False)
            if view['status']!='complete':result[sid,arm]=view;continue
            rows=[]
            for w in view['windows']:
                owner.tick();x=reference_features(w,tuple(range(w['unit_count'])),head,owner.tick)
                rows.append({'query':w['query'],'values':models.predict(state,x)})
            result[sid,arm]={'status':'complete','windows':tuple(rows)}
    return {'predictions':result,'states':states,'selection':selection,'source_only':True,'cost':owner.snapshot()}
