"""Actual selected FIT feature basis and dense design construction source."""
import json,math
from array import array
from .constants import AREAS,RUN,PUPIL,PHASES,BLOCKS,FIELDS,EXPOSURE,MODELS
from .authority import require_live

def inspect_metadata(meta):
    """Called only inside admitted programme; retains full rows and native axes."""
    if type(meta)is not dict or meta.get('schema')!='neuropixels_session_v1'or meta.get('task_id')!='NEURAL-092':raise ValueError('exact original N092 metadata')
    ids=meta['unit_ids'];areas=meta['areas'];rows=meta['rows'];um=meta['unit_metadata']
    if type(ids)is not list or not ids or any(type(x)is not str or not x for x in ids)or len(set(ids))!=len(ids):raise ValueError('complete unique native units')
    if len(areas)!=len(ids)or len(um)!=len(ids)or any(a not in AREAS for a in areas):raise ValueError('area axes')
    if meta['exposure_seconds']!=EXPOSURE or len(meta['baseline_rates'])!=len(ids):raise ValueError('original target exposure/baseline axes')
    for i,u in enumerate(um):
        if set(u)!={'unit_id','area','FITbaseline','presence_ratio','isi_violations','amplitude_cutoff'}or u['unit_id']!=ids[i]or u['area']!=areas[i]or u['FITbaseline']!=meta['baseline_rates'][i]:raise ValueError('native unit/QC/baseline join')
        if not math.isfinite(u['FITbaseline'])or u['FITbaseline']<=0:raise ValueError('positive FIT baseline')
        if not 0<=u['amplitude_cutoff']<=.1 or not .95<=u['presence_ratio']<=1 or not 0<=u['isi_violations']<=.5:raise ValueError('selected QC ranges')
    grouped={p:[]for p in PHASES};seen=set()
    for row in rows:
        if row['id']in seen or type(row['id'])is not str or row['family']!='drifting_gratings':raise ValueError('unique DG rows')
        seen.add(row['id']);phase=row['split']
        if phase not in PHASES or type(row['block'])is not int or row['block']!=BLOCKS[phase]:raise ValueError('fixed blocks')
        if row['run_bin']not in RUN or row['pupil_bin']not in PUPIL:raise ValueError('fixed state categories')
        if not math.isfinite(row['onset'])or not math.isfinite(row['stop'])or row['onset']<.5 or row['stop']<row['onset']+1.95 or row['window']!=[row['onset']+.05,row['onset']+1.95]:raise ValueError('original target window')
        encoded=json.dumps([row['family']]+[row['features'].get(k)for k in FIELDS],ensure_ascii=True,separators=(',',':'),allow_nan=False)
        if row['condition_key']!=encoded:raise ValueError('exact native condition serialization')
        grouped[phase].append(row)
    if any(not grouped[p]for p in PHASES):raise ValueError('complete three-block support')
    for p in PHASES:
        if grouped[p]!=sorted(grouped[p],key=lambda r:(r['onset'],r['id'])):raise ValueError('original within-block order')
    if any(max(r['stop']for r in grouped[a])>min(r['onset']for r in grouped[b])for a,b in zip(PHASES,PHASES[1:])):raise ValueError('chronological nonoverlap')
    vocab=tuple(sorted({r['condition_key']for r in grouped['FIT']},key=lambda x:x.encode('utf8')))
    return {'rows':grouped,'vocabulary':vocab,'unit_ids':tuple(ids),'areas':tuple(areas),
      'unknown_conditions':{p:tuple(r['id']for r in grouped[p]if r['condition_key']not in vocab)for p in PHASES},
      'pupil_supported':any(r['pupil_bin']!='MISSING'for r in grouped['QUERY'])}

def columns(model,k):
    if model not in MODELS:raise ValueError('fixed five models')
    return 1+(k if model!='state_only'else 0)+(16 if model in ('state_only','stimulus_plus_state')else 4 if model in ('stimulus_plus_running','stimulus_plus_pupil')else 0)

def design(meta_info,model,host,calls):
    require_live(host,'construct admitted full design')
    calls.enter('design');vocab=meta_info['vocabulary'];lookup={s:i for i,s in enumerate(vocab)}
    rows=[r for p in PHASES for r in meta_info['rows'][p]];p=columns(model,len(vocab))
    x=array('d',[0.0])*(len(rows)*p)
    if x.itemsize!=8:raise RuntimeError('float64 array storage required')
    for i,row in enumerate(rows):
        base=i*p;x[base]=1.;offset=1
        if model!='state_only':
            if row['condition_key']in lookup:x[base+1+lookup[row['condition_key']]]=1.
            offset+=len(vocab)
        if model in ('state_only','stimulus_plus_state'):x[base+offset+RUN.index(row['run_bin'])*4+PUPIL.index(row['pupil_bin'])]=1.
        elif model=='stimulus_plus_running':x[base+offset+RUN.index(row['run_bin'])]=1.
        elif model=='stimulus_plus_pupil':x[base+offset+PUPIL.index(row['pupil_bin'])]=1.
    return x,p

def validate_counts(values,nrows,units):
    if type(values)is not array or values.typecode!='q'or values.itemsize!=8 or len(values)!=nrows*units:raise ValueError('exact captured signed-int64 count plane')
    if any(x<0 for x in values):raise ValueError('nonnegative original counts; no clipping')

def verify_fit_offset(meta,fit_counts,nfit):
    units=len(meta['unit_ids']);validate_counts(fit_counts,nfit,units)
    for j,baseline in enumerate(meta['baseline_rates']):
        expected=(sum(fit_counts[i*units+j]for i in range(nfit))+.5)/(nfit*EXPOSURE)
        if expected!=baseline:raise ValueError('FIT offset must exactly match original count-derived baseline')
