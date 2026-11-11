"""NEURAL098 complete declared raw-event/retained-epoch binding bridge.

Primitive metadata only. No FIF opening, neural values, MNE, classifier, or
reference/scorer execution. Original asset custody remains an external input.
"""
from bisect import bisect_left
import hashlib
import json
import math
import time

PEOPLE = ('SA102','SA103','SA104','SA111','SA114','SA118','SA121','SA123','SA125','SA132','SA133',
 'SA134','SA136','SA138','SA139','SA140','SA144','SA145','SA146','SA147','SA148','SA150','SA151',
 'SA154','SA158','SA163','SA166','SA167','SA169','SA170','SA173','SA174','SA176')
LIMIT_KEYS={'max_input_bytes','max_events','max_retained','max_runs','max_output_bytes'}
MAXIMA={'max_input_bytes':128000000,'max_events':1000000,'max_retained':100000,
        'max_runs':2112,'max_output_bytes':128000000}
PROFILES=('strict_existing_v1','nullable_next_v2')
EXTRACTION={'stim_channel':'STI101','response_code':255,'response_consecutive':False,
 'other_consecutive':True,'other_min_duration':0.001001,'mask':65280,'mask_type':'not_and',
 'responses_merged_before_sample_sort':True}
META_KEYS={'Stim_trigger','Category','Orientation','Duration','Task_relevance','Response'}

class BindingRefusal(ValueError): pass
class BindingFailure(RuntimeError):
    def __init__(self,report,completed):
        super().__init__('complete binding export failed: '+report['phase'])
        self.report=report;self.completed_bindings=dict(completed)

def need(ok,why):
    if not ok:raise BindingRefusal(why)

def integer(v,low=0,high=10**12):
    need(type(v) is int and low<=v<=high,'bounded exact integer');return v

def clock(deadline):
    need(type(deadline) in (int,float),'original absolute bridge deadline')
    try:finite=math.isfinite(deadline)
    except OverflowError:finite=False
    need(finite and time.monotonic()<deadline,'original absolute bridge deadline')

def sha(v):
    need(type(v) is str and len(v)==64 and all(c in '0123456789abcdef' for c in v),'exact SHA256');return v

def pin(v):
    need(type(v) is dict and set(v)=={'bytes','sha256'},'exact descriptor');integer(v['bytes'],1);sha(v['sha256']);return v

def encode(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')
def digest(raw):return hashlib.sha256(raw).hexdigest()

def decode(raw,expected,cap):
    pin(expected);integer(cap,1,128000000)
    need(type(raw) is bytes and 0<len(raw)<=cap and len(raw)==expected['bytes'] and digest(raw)==expected['sha256'],'exact bounded selected observation bytes')
    def pairs(items):
        d={}
        for k,v in items:
            need(k not in d,'duplicate JSON key');d[k]=v
        return d
    def int_token(s):
        need(len(s)<=14,'bounded JSON integer token');return int(s)
    def float_token(s):
        need(len(s)<=32,'bounded JSON real token');v=float(s);need(math.isfinite(v),'finite JSON real');return v
    def bad(s):raise BindingRefusal('nonfinite JSON token')
    try:return json.loads(raw,object_pairs_hook=pairs,parse_int=int_token,parse_float=float_token,parse_constant=bad)
    except (UnicodeError,ValueError,RecursionError) as exc:raise BindingRefusal('bounded observation JSON') from exc

def triples(rows,*,cap,deadline):
    need(type(rows) is list and 0<len(rows)<=cap,'complete bounded event table')
    out=[]
    for i,row in enumerate(rows):
        if i%256==0:clock(deadline)
        need(type(row) is list and len(row)==3,'three event columns')
        out.append(tuple(integer(v) for v in row))
    return out

def bool_response(v):
    if type(v) is bool:return v
    if type(v) is str and v in ('True','False'):return v=='True'
    raise BindingRefusal('exact metadata Response boolean')

def _trial(run_events,index):
    """P04 V1 field semantics, plus separately documented physical96 offset."""
    sample,_,trigger=run_events[index]
    need(1<=trigger<=80,'complete V1 stimulus vocabulary')
    near=run_events[index:index+9]
    ends=[j for j,row in enumerate(near) if row[2]==97]
    need(ends and ends[0]>0,'source first97 in nine-event metadata horizon')
    body=near[:ends[0]];blank=near[ends[0]][0]
    need(not any(1<=v[2]<=80 for v in body[1:]),'overlapping stimulus before blank end')
    def one(codes):
        found=[r for r in body if r[2] in codes]
        need(len(found)==1,'unique complete trial condition marker');return found[0][2]
    orientation=one((101,102,103));duration=one((151,152,153));relevance=one((201,202,203))
    offsets=[r[0] for r in body if r[2]==96]
    need(len(offsets)==1 and sample<offsets[0]<blank,'one observed physical96 offset, distinct from97')
    return {'Stim_trigger':trigger,'Category':('face','object','letter','false')[(trigger-1)//20],
      'Orientation':('Center','Left','Right')[orientation-101],
      'Duration':('500ms','1000ms','1500ms')[duration-151],
      'Task_relevance':('Relevant target','Relevant non-target','Irrelevant')[relevance-201],
      'Response':any(r[2]==255 for r in body)},offsets[0]

def export_person(observation,expected,*,profile,limits,deadline):
    """All observed retained rows preserved; eligibility is downstream work."""
    clock(deadline)
    need(profile in PROFILES,'explicit binding ABI profile')
    fields={'schema','participant','source_roster','extraction_profile','runs','concatenated_events','epochs','preprocessing_provenance'}
    need(type(observation) is dict and set(observation)==fields,'exact person observation schema')
    need(observation['schema']=='neural098-event-observation-v1' and observation['participant']==expected['participant'],'selected person observation')
    need(encode(observation['source_roster'])==encode(expected['source_roster']),'complete declared raw source roster pin')
    need(encode(observation['extraction_profile'])==encode(EXTRACTION),'full P04 event extraction declaration')
    provenance=observation['preprocessing_provenance']
    need(type(provenance) is dict and set(provenance)=={'history_sha256','epoch_event_coordinates'}
         and provenance['epoch_event_coordinates'] in ('observed_retained_unscaled','observed_retained_transformed'),'explicit observed preprocessing history/epoch coordinate policy')
    sha(provenance['history_sha256'])
    runs=observation['runs'];ids=expected['run_ids']
    need(type(runs) is list and len(runs)==len(ids) and 0<len(runs)<=limits['max_runs'],'complete declared run sequence')
    need([r.get('run') for r in runs if type(r) is dict]==ids,'all declared runs in source concatenation order')
    projected=[];origin_rows=[];trial_lookup={};button_lists={};bounds={};source_rows=[]
    cumulative=0;first_origin=None;raw_sfreq=None
    for run in runs:
        clock(deadline)
        need(type(run) is dict and set(run)=={'run','first_sample','last_sample','sfreq','raw_source','event_source','events'},'exact raw run fields')
        rid=integer(run['run'],1);first=integer(run['first_sample']);last=integer(run['last_sample'])
        need(last>=first,'ordered original raw sample domain');pin(run['raw_source']);pin(run['event_source'])
        sf=run['sfreq'];need(type(sf) in (int,float) and math.isfinite(sf) and 1<=sf<=10000,'actual raw sampling frequency')
        if first_origin is None:first_origin=first;raw_sfreq=sf
        need(sf==raw_sfreq,'one actual raw clock per person; no rate conversion inferred')
        events=triples(run['events'],cap=limits['max_events'],deadline=deadline)
        need(len(projected)+len(events)<=limits['max_events'],'whole-person event cap')
        need(all(first<=v[0]<=last for v in events) and all(a[0]<=b[0] for a,b in zip(events,events[1:])),'complete ordered events within raw bounds')
        need(len(set(events))==len(events) and all(v[2]>0 for v in events),'distinct positive source event records')
        onsets=[i for i,r in enumerate(events) if 1<=r[2]<=80]
        need(onsets and len({events[i][0] for i in onsets})==len(onsets),'distinct observed stimulus onsets')
        buttons=[r[0] for r in events if r[2]==255]
        need(buttons==sorted(set(buttons)),'complete distinct ordered response samples')
        button_lists[rid]=buttons;bounds[rid]=(first,last)
        for oi,index in enumerate(onsets):
            meta,offset=_trial(events,index)
            next_sample=events[onsets[oi+1]][0] if oi+1<len(onsets) else None
            if next_sample is not None:need(next_sample>offset,'next stimulus follows physical offset')
            trial_lookup[(rid,index)]=(meta,offset,next_sample)
        for j,row in enumerate(events):
            sample=row[0]-first+cumulative+first_origin
            integer(sample);projected.append((sample,row[1],row[2]));origin_rows.append((rid,j,row[0]))
        cumulative+=last-first+1;integer(cumulative)
        source_rows.append({'run':rid,'raw_source':dict(run['raw_source']),'event_source':dict(run['event_source']),
                            'first_sample':first,'last_sample':last,'event_rows':len(events),'stimulus_rows':len(onsets)})
    observed=triples(observation['concatenated_events'],cap=limits['max_events'],deadline=deadline)
    need(observed==projected,'whole observed raw-concatenation event bijection')
    epochs=observation['epochs']
    need(type(epochs) is dict and set(epochs)=={'source','sfreq','selection','events','metadata','drop_log'},'exact retained-epoch observations')
    pin(epochs['source']);esf=epochs['sfreq'];need(type(esf) in (int,float) and math.isfinite(esf) and 1<=esf<=10000,'observed epoch sampling frequency')
    selection=epochs['selection'];metadata=epochs['metadata'];drop=epochs['drop_log']
    need(type(selection) is list and 0<len(selection)<=limits['max_retained'] and len(set(selection))==len(selection),'complete distinct retained selection')
    for i in selection:integer(i,0,len(projected)-1)
    need(type(metadata) is list and len(metadata)==len(selection),'all retained metadata rows')
    kept=triples(epochs['events'],cap=limits['max_retained'],deadline=deadline)
    need(len(kept)==len(selection) and type(drop) is list and len(drop)==len(projected),'full original drop/selection domain')
    selected=set(selection)
    for i,reasons in enumerate(drop):
        need(type(reasons) is list and len(reasons)<=512 and all(type(v) is str and 0<len(v)<=128 and v.isascii() for v in reasons),'bounded observed drop reasons')
        need((len(reasons)==0)==(i in selected),'all and only retained indices have empty drop log')
        if not 1<=projected[i][2]<=80:need('IGNORED' in reasons and i not in selected,'nonstimulus events explicitly ignored')
        elif i not in selected:need('IGNORED' not in reasons,'stimulus missing through untracked event filtering')
    rows=[];unknown=[]
    for position,index in enumerate(selection):
        if position%256==0:clock(deadline)
        rid,local,onset=origin_rows[index]
        need((rid,local) in trial_lookup,'retained event must be an original stimulus')
        meta,offset,next_sample=trial_lookup[(rid,local)]
        supplied=metadata[position]
        need(type(supplied) is dict and set(supplied)==META_KEYS,'exact projected retained metadata')
        supplied=dict(supplied,Response=bool_response(supplied['Response']))
        need(encode(supplied)==encode(meta),'source trigger/condition/response versus retained metadata join')
        epoch_sample,previous,trigger=kept[position]
        need((previous,trigger)==projected[index][1:],'retained event code/previous-state join')
        if provenance['epoch_event_coordinates']=='observed_retained_unscaled':
            need(epoch_sample==projected[index][0],'unscaled observed epoch sample join')
        # Transformed coordinates are OBSERVED, never rate-ratio rounded. The
        # selected preprocessing history is an external authenticity prerequisite.
        duration=int(meta['Duration'][:-2]);first,last=bounds[rid]
        need((onset-first)/raw_sfreq>=.5 and (last+1-onset)/raw_sfreq>=duration/1000+.3,
             'complete within-run raw button horizon; no cross-run continuity assumed')
        need(abs((offset-onset)/raw_sfreq-duration/1000)<=1.01/raw_sfreq,'actual96 offset versus declared duration')
        buttons=button_lists[rid]
        begin=bisect_left(buttons,math.floor(onset-.5*raw_sfreq)-1)
        stop=bisect_left(buttons,math.ceil(onset+(duration/1000+.3)*raw_sfreq)+1)
        relevant=[v for v in buttons[begin:stop] if -.5<=(v-onset)/raw_sfreq<duration/1000+.3]
        need(len(relevant)<=100,'existing per-binding button extent')
        if next_sample is None:
            need(profile=='nullable_next_v2','terminal retained stimulus has no observed successor; strict v1 cannot represent it')
            unknown.append(index)
        rows.append({'selection_index':index,'run':rid,'event_sample':onset,'epoch_event_sample':epoch_sample,
                     'offset_sample':offset,'next_onset_sample':next_sample,'stim_trigger':trigger,'button_samples':relevant})
    result={'schema':'neural098-event-bindings-v1' if profile=='strict_existing_v1' else 'neural098-event-bindings-v2',
            'participant':observation['participant'],'sfreq':raw_sfreq,'rows':rows}
    receipt={'participant':observation['participant'],'declared_run_ids':ids,'raw_event_rows':len(projected),
      'retained_rows':len(rows),'retained_selection_sha256':digest(encode(selection)),
      'unknown_next_onset_selection_indices':unknown,'epochs_source':epochs['source'],
      'raw_sfreq':raw_sfreq,'saved_epoch_sfreq':esf,'preprocessing_provenance':provenance,
      'sources':source_rows,'all_retained_bindings_preserved':True,'original_asset_custody_authenticated':False,
      'scientific_cell_support_verified':False,'native_or_historical_parity':False}
    clock(deadline);return result,receipt

def export_panel(*, manifest_raw,expected_manifest_sha256,person_raw,profile,limits,deadline_monotonic):
    """Return all33 binding byte bundles or fail with retained partial evidence."""
    clock(deadline_monotonic);sha(expected_manifest_sha256)
    need(deadline_monotonic-time.monotonic()<=600,'at most600 seconds remaining on original caller clock')
    need(type(limits) is dict and set(limits)==LIMIT_KEYS,'exact whole-panel resource caps')
    for key,value in limits.items():integer(value,1,MAXIMA[key])
    need(type(profile) is str and profile in PROFILES,'explicit separate ABI profile')
    need(type(manifest_raw) is bytes and 0<len(manifest_raw)<=1048576 and digest(manifest_raw)==expected_manifest_sha256,'externally selected full manifest')
    manifest=decode(manifest_raw,{'bytes':len(manifest_raw),'sha256':expected_manifest_sha256},1048576)
    need(type(manifest) is dict and set(manifest)=={'schema','participants'} and manifest['schema']=='neural098-binding-observation-manifest-v1','manifest schema')
    declared=manifest['participants']
    need(type(declared) is dict and set(declared)==set(PEOPLE) and type(person_raw) is dict and set(person_raw)==set(PEOPLE),'all33 fixed people before parsing observations')
    input_bytes=len(manifest_raw);run_count=0
    for person in PEOPLE:
        row=declared[person]
        need(type(row) is dict and set(row)=={'observation','source_roster','run_ids'},'exact selected observation operands')
        pin(row['observation']);pin(row['source_roster'])
        ids=row['run_ids'];need(type(ids) is list and 0<len(ids)<=64,'complete explicitly ordered raw run roster')
        for i in ids:integer(i,1)
        need(len(set(ids))==len(ids),'distinct explicitly ordered raw run roster')
        need(type(person_raw[person]) is bytes,'immutable person observations')
        input_bytes+=len(person_raw[person]);run_count+=len(ids)
    need(input_bytes<=limits['max_input_bytes'] and run_count<=limits['max_runs'],'whole-panel input/run reservation')
    completed={};receipts=[];events=retained=written=0;phase='preflight';person=None
    try:
        for person in PEOPLE:
            phase='export:'+person;clock(deadline_monotonic)
            row=declared[person];observation=decode(person_raw[person],row['observation'],min(128000000,limits['max_input_bytes']))
            expected=dict(row,participant=person)
            remaining=dict(limits,max_events=limits['max_events']-events,max_retained=limits['max_retained']-retained)
            result,receipt=export_person(observation,expected,profile=profile,limits=remaining,deadline=deadline_monotonic)
            events+=receipt['raw_event_rows'];retained+=receipt['retained_rows']
            need(events<=limits['max_events'] and retained<=limits['max_retained'],'cumulative all-person event/retained caps')
            body=encode(result);need(len(body)<=32000000,'existing JSON reader domain')
            written+=len(body);need(written<=limits['max_output_bytes'],'whole-panel binding output cap')
            clock(deadline_monotonic);completed[person]=body;receipts.append(receipt)
        phase='completion';receipt={'schema':'neural098-full33-binding-export-v1','complete_binding_export':True,
          'profile':profile,'manifest_sha256':expected_manifest_sha256,'participants':receipts,
          'input_bytes':input_bytes,'output_binding_bytes':written,'raw_event_rows':events,'retained_rows':retained,
          'all33_people_preserved':True,'scientific_packet_ready':False,'original_sources_authenticated_by_bridge':False,
          'runtime_qualified':False,'scientific_qualified':False,'candidate_or_reference_executed':False}
        receipt_raw=encode(receipt);need(written+len(receipt_raw)<=limits['max_output_bytes'],'receipt included in whole output cap')
        result={'bindings':completed,'receipt':receipt_raw,'pins':{p:{'bytes':len(b),'sha256':digest(b)} for p,b in completed.items()}}
        clock(deadline_monotonic)
        return result
    except BaseException as exc:
        report={'complete_binding_export':False,'phase':phase,'participant':person,'error_type':type(exc).__name__,
                'completed_people':list(completed),'output_binding_bytes':written,'raw_event_rows':events,'retained_rows':retained}
        if not isinstance(exc,Exception):raise
        raise BindingFailure(report,completed) from exc
