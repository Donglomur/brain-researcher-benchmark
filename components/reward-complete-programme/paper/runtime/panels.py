"""Full166-panel routing to scientific operators, with native obligations intact."""
import math
import statistics as st
from analysis import summary,compare,changepoint,regression,variance_test,welch_anova
from models import sigmoid_fit
from reward_common import need,object_sha256

# One entry per published letter; no selected Figure1 slice masquerades as full.
ROUTES={
 'F1':'S S S P B O O T B C Y',
 'F2':'S S E C Q L U A D',
 'F3':'S P O B O B X T',
 'F4':'S E C C O X B Q D Z',
 'F5':'S T M M M M M M M M M',
 'F6':'S B Y S B Y S B Y S B Y',
 'F7':'S C O B D C S E A Q',
 'F8':'S E E G N N',
 'ED1':'P Y W W',
 'ED2':'C C C O B W W O',
 'ED3':'H H H',
 'ED4':'E C A D D D R R',
 'ED5':'S F O T F F V H E Q U D',
 'ED6':'B Y C Y X C O Y X Q D D R D D R',
 'ED7':'M M M M M M M',
 'ED8':'D Z D D D K I I X X X',
 'ED9':'C O C B C X O K',
 'ED10':'X X Q O Q C C C E E O M'}
GROUPS={
 'F1':['60s','600s'],'F2':['60s','600s'],'F3':['30s','60s','300s','600s'],
 'F4':['30s','60s','300s','600s','3600s'],'F5':['30s','60s','300s','600s','3600s'],
 'F6':['60s','600s','60s-few','60s-few-ctxt','60s-CSminus','600s-bgdmilk'],
 'F7':['60s','600s','60s-50percent','60s-10percent'],'F8':['60s-50percent'],
 'ED1':['60s','600s'],'ED2':['60s','600s'],
 'ED3':['60s','600s','3600s','60s-few','60s-50percent','60s-10percent'],
 'ED4':['60s','600s'],'ED5':['FC-45s','FC-135s'],
 'ED6':['30s','300s','60s','600s','3600s'],'ED7':['30s','60s','300s','600s','3600s'],
 'ED8':['30s','60s','300s','600s','60s-few'],
 'ED9':['60s','600s','60s-CSminus','600s-bgdmilk'],
 'ED10':['60s','600s','60s-50percent','60s-10percent']}
RANGES={
 'F1k':{'60s':[301,400],'600s':[31,40]},'F4j':{'60s':[301,400],'600s':[31,40],'3600s':[15,16]},
 'ED1b':{'60s':[36,40],'600s':[36,40]},'ED1d':{'60s':[36,40],'600s':[36,40]},
 'ED2g':{'60s':[301,400],'600s':[31,40]},'ED6b':{'30s':[71,80],'300s':[71,80]},
 'ED6d':{'30s':[601,800],'300s':[61,80]},'ED6h':{'3600s':[14,16]}}
for letter,control in [('c','60s-few'),('f','60s-few-ctxt'),('i','60s-CSminus'),('l','600s-bgdmilk')]:
    RANGES['F6'+letter]={c:[36,40] for c in ('60s','600s',control)}


def registry(obligations):
    result=[]
    for figure in obligations['figures']:
        fid=figure['figure'];route=ROUTES[fid].split();byletter={x:p for p in figure['panels'] for x in p['letters']}
        need(len(route)==len(byletter),'Exact figure letter routing')
        for i,op in enumerate(route):
            letter=chr(97+i);need(letter in byletter,'Published panel letter')
            result.append({'panel_id':fid+letter,'figure':fid,'letter':letter,'operator':op,
                           'conditions':list(RANGES.get(fid+letter,GROUPS[fid])),
                           'range_by_condition':RANGES.get(fid+letter),
                           'obligation':byletter[letter]['obligation'],'native_driver':figure['native_driver_role']})
    need(len(result)==166,'Complete paper panel scope');return result


def _values(animal,metric):
    rows=[t for t in animal['trials'] if t['kind'] in ('CS_plus','shock')]
    values=[]
    for i,r in enumerate(rows,1):
        if metric=='behavior':v=r.get('delta_hz',r.get('behavior',{}).get('freezing_change'))
        elif metric=='cue':v=r.get('cue_da',{}).get('auc')
        elif metric=='reward':v=r.get('reward_da',{}).get('auc')
        elif metric=='omission':v=r.get('omission_da',{}).get('auc')
        elif metric=='freezing':v=r.get('behavior',{}).get('freezing_change')
        elif metric=='motion':v=r.get('behavior',{}).get('motion_change')
        elif metric=='probability':v=None if r.get('D') is None else int(r['D']>1)
        elif metric=='iti':v=r.get('preceding_ITI_lick_rate')
        elif metric=='bout':v=r.get('consumption_bout_seconds')
        else:raise ValueError('Metric')
        values.append({'trial_id':r['trial_id'],'trial':i,'session':r['session_number'],
                       'value':v,'conditioning_seconds':r['elapsed_conditioning_cue'],
                       'delivered':r['delivered']})
    return values


def _psth(animal):
    bins=[-2.5+i*.1 for i in range(101)];counts=[0]*100;n=0
    for row in animal['trials']:
        if row['kind'] not in ('CS_plus','shock'):continue
        if not row.get('lick_epoch_complete'):continue
        n+=1
        for t in row['lick_times_relative']:
            i=int(math.floor((t+2.5)/.1))
            if 0<=i<100:counts[i]+=1
    raw=[x/(n*.1) for x in counts] if n else []
    # Figure smoothing is display only; raw100ms rates remain output.
    kernel=[math.exp(-.5*(i/.75)**2) for i in range(-3,4)];scale=sum(kernel);kernel=[x/scale for x in kernel]
    smooth=[sum(kernel[j+3]*raw[min(max(i+j,0),99)] for j in range(-3,4)) for i in range(100)] if n else []
    return {'animal_id':animal['animal_id'],'condition':animal['condition'],'n_trials':n,
            'bins_left':bins[:-1],'raw_hz':raw,'display_smoothed_hz':smooth}


def _series(animals,metric,ranges=None,cumulative=False):
    result=[]
    for a in animals:
        rows=_values(a,metric)
        if ranges:
            left,right=ranges[a['condition']];rows=[r for r in rows if left<=r['trial']<=right]
        if cumulative:
            total=0;known=True
            for row in rows:
                if row['value'] is None:known=False
                if known:total+=row['value'];row['cumulative']=total
                else:row['cumulative']=None
        vals=[r['value'] for r in rows if r['value'] is not None]
        result.append({'animal_id':a['animal_id'],'condition':a['condition'],'rows':rows,
                       'summary':summary(vals),'expected_rows':len(rows),'observed_rows':len(vals)})
    return result


def _onsets(animals,metric,time=False):
    result=[]
    for a in animals:
        series=_values(a,metric);values=[r['value'] for r in series]
        direction='decrease' if a['condition'].startswith('FC-') and metric=='cue' else 'increase'
        cp=changepoint(values,direction=direction) if len(values)>=3 and all(x is not None for x in values) else {'status':'unscorable','trial':None}
        trial=cp['trial'];elapsed=None;reward_count=None
        if trial is not None:
            reward_count=sum(r['delivered'] for r in series[:trial])
            if trial<len(series):elapsed=series[trial]['conditioning_seconds']
        result.append({'animal_id':a['animal_id'],'condition':a['condition'],'onset':cp,
                       'rewards_before_onset':reward_count,'conditioning_seconds':elapsed,
                       'metric':metric,'time_requested':time})
    return result


def compute_panel(spec,prepared,analysis,native_exports=()):
    pid=spec['panel_id'];op=spec['operator']
    duplicates=[r for e in native_exports for r in e['panels'] if r['panel_id']==pid]
    need(len({object_sha256(r) for r in duplicates})<=1,'Conflicting duplicate native panel exports')
    for export in native_exports:
        need(export.get('verified_native_collection') is True,'Only trusted collector exports')
        for row in export['panels']:
            if row['panel_id']==pid:
                if export.get('collection_tier')=='engineering_mock':
                    return {'panel_id':pid,'status':'required-unscorable','component_status':'engineering_mock_collected',
                            'reason':'Invented export cannot satisfy original scientific panel obligation'}
                if row['status']=='required-unscorable':
                    return {'panel_id':pid,'status':'required-unscorable','reason':row['reason'],
                            'branch':'native_collected_missing','native_receipt':export['receipt_sha256']}
                return {'panel_id':pid,'status':'computed','value':row['value'],
                        'branch':'native_collected','native_receipt':export['receipt_sha256'],
                        'cohort_manifest':row['cohort_manifest'],'statistical_recipe':row['statistical_recipe'],
                        'artifact_pins':row['artifact_pins'],'artifact_contract':row['artifact_contract']}
    animals=[a for a in prepared['animals'] if a['condition'] in spec['conditions']]
    missing=sorted(set(spec['conditions'])-{a['condition'] for a in animals})
    if missing:return {'panel_id':pid,'status':'required-unscorable','reason':'missing_conditions','missing':missing}
    if op in ('S','M','H'):
        # S requires scientific interpretation review; M/H need original bodies/images.
        return {'panel_id':pid,'status':'required-unscorable','reason':{'S':'expert_schematic_reference',
                'M':'original_full_model_export','H':'original_histology_image_and_placement_reference'}[op],
                'source_obligation':spec['obligation']}
    if op=='P':value=[_psth(a) for a in animals]
    elif op=='E':value=[{'animal_id':a['animal_id'],'condition':a['condition'],
                        'lick':_psth(a),'neural_epochs':[{'trial_id':t['trial_id'],'epoch':t.get('da_epoch')}
                        for t in a['trials']]} for a in animals]
    elif op in ('B','C','D','R','F','V','W','I','K','Y','Z'):
        metric={'B':'behavior','C':'behavior','D':'cue','R':'reward','F':'freezing','V':'motion',
                'W':'probability','I':'iti','K':'bout','Y':'behavior','Z':'cue'}[op]
        value=_series(animals,metric,spec['range_by_condition'],op=='C')
        if not any(r['observed_rows'] for r in value):
            return {'panel_id':pid,'status':'required-unscorable','reason':'required_metric_not_available','diagnostics':value}
    elif op in ('O','Q','T','U'):
        value=_onsets(animals,'cue' if op in ('Q','U') else 'behavior',op in ('T','U'))
    elif op=='L':
        behavior=_onsets(animals,'behavior');da=_onsets(animals,'cue');value=[]
        for b,d in zip(behavior,da):
            bt,dt=b['onset']['trial'],d['onset']['trial']
            value.append({'animal_id':b['animal_id'],'condition':b['condition'],'behavior':bt,'DA':dt,
                          'lag':None if bt is None or dt is None else bt-dt,'horizon':'independent_fixed'})
    elif op=='A':
        value=[]
        for a,entry in zip(animals,_onsets(animals,'behavior')):
            onset=entry['onset']['trial'];series=_values(a,'cue')
            value.append({'animal_id':a['animal_id'],'condition':a['condition'],'onset':onset,
                          'relative_trials':[dict(r,relative_trial=None if onset is None else r['trial']-onset) for r in series]})
    elif op=='X':value={'behavior_scaling':analysis['scaling'],'animal_onsets':_onsets(animals,'behavior'),
                        'note':'Four-group mean line only; extrapolation/control hypotheses require their exact source recipes'}
    elif op in ('N','G'):
        value=[]
        for a in animals:
            rows=[t for t in a['trials'] if t['kind']=='CS_plus' and not t['delivered']]
            cue=[t.get('cue_da',{}).get('auc') for t in rows];om=[t.get('omission_da',{}).get('auc') for t in rows]
            result={'animal_id':a['animal_id'],'condition':a['condition'],'omission_trial_ids':[t['trial_id'] for t in rows],
                    'cue':cue,'omission':om,'native_behavior_learner_exclusion_applied':False}
            if len(cue)>=6 and all(x is not None for x in cue+om):
                result['cue_fit']=sigmoid_fit(list(range(1,len(cue)+1)),cue)
                result['omission_fit']=sigmoid_fit(list(range(1,len(om)+1)),om)
            else:result['fit_status']='required-unscorable: insufficient complete omission observations'
            value.append(result)
    else:raise ValueError('Unimplemented panel operator '+op)
    return {'panel_id':pid,'status':'required-unscorable','component_status':'computed','component_value':value,
            'reason':'independent component is not a complete qualified panel; native masks, denominators, statistics and artifacts remain',
            'branch':'independent_scientific_operator',
            'native_status':'required-unscorable','native_reason':'original driver/export and numerical parity gates remain',
            'scientific_qualification':False}


def complete_panels(obligations,prepared,analysis,native_exports=()):
    specs=registry(obligations)
    result=[compute_panel(s,prepared,analysis,native_exports) for s in specs]
    return {'schema':'reward_complete_panels_v1','panels':result,'expected_panels':166,
            'native_complete':all(r.get('branch')=='native_collected' for r in result),
            'scientific_qualification':False}
