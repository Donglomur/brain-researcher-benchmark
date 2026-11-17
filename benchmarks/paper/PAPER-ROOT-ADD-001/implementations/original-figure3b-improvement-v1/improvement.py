"""Root-selected original Figure3b endpoint; no binary win or scope substitution."""
from __future__ import annotations

import hashlib
import json
import math

import numpy as np

SESSIONS = ('p1_1','p1_2','p2_1','p2_2','p3_1','p3_2','p4_1','p5_1','p5_2','p6_1','p7_1','p7_2','p8_1','p8_2')
PEOPLE = tuple(f'p{i}' for i in range(1,9))
ROOT_SELECTION_SHA256 = '4038501cc3050e8bbd7f1968c05768f9a0ed0322725f9e167466b694965cb762'
ORIGINAL_NOTEBOOK_SHA256 = '3cec508ef352d004525e377589d69dc05e6551f1356bcdb7a3b3ee2ca983239b'
PROVIDED_REFERENCE_SHA256 = 'd822f284c2d781f920841705a63fec38d3267ee5c62e5dd5635272cf087e49c9'
LAGS = (17,18,19)


def need(ok,message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def digest(value):
    need(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value),'Exact lowercase SHA256')
    return value


def contexts():
    """Exactly original order, fieldpopulation, layer5, source lagindices17–19."""
    return tuple({'session':s,'field':'population','family':'context','layer':5,
                  'lag_index':lag,'lag_bins':lag-20} for s in SESSIONS for lag in LAGS)


def coordinates():
    return tuple({'session_index':i,'field_index':0,'layer':5,'lag_index':lag,'lag_bins':lag-20}
                 for i in range(14) for lag in LAGS)


def selection():
    rows = contexts()
    return {'schema':'language-original-figure3b-selection/v1','scope':'original_figure3b_population_improvement',
            'root_selection_sha256':ROOT_SELECTION_SHA256,'original_notebook_sha256':ORIGINAL_NOTEBOOK_SHA256,
            'source_cell_zero_based':5,'contexts':list(rows),'ordered_context_sha256':hashlib.sha256(b''.join(encoded(x) for x in rows)).hexdigest(),
            'sessions':14,'participants':8,'jobs':42,'held_sentence_software_callbacks':5685,
            'callbacks_are_native_process_or_API_requirements':False,
            'aggregation':'mean of3 fixed lag Pearson values/session, then equal mean ofall14sessions',
            'author_preregistration_established':False,
            'full224_array_reproduction_unchanged':True,'scientific_qualification':False}


def is_selected(context):
    """Exact source coordinate filter; does not inspect target/prediction values."""
    need(type(context) is dict and set(context) == {'session','field','family','layer','lag_index','lag_bins'},
         'Exact bounded original source context')
    need(type(context['session']) is str and context['session'] in SESSIONS
         and type(context['field']) is str and type(context['family']) is str
         and all(type(context[k]) is int for k in ('layer','lag_index','lag_bins')),
         'Primitive source coordinate types')
    return (context['field'] == 'population' and context['family'] == 'context' and context['layer'] == 5
            and context['lag_index'] in LAGS and context['lag_bins'] == context['lag_index']-20)


def select_stream(jobs):
    """Filter source metadata only, then require all42 exact canonical selectedjobs.

    A private source reader should apply this predicate before array loading.
    The stream itself must be the separately authenticated original store.
    """
    need(hasattr(jobs,'__iter__'),'Original context stream')
    wanted = contexts(); index=0; consumed=0
    for row in jobs:
        consumed += 1
        need(consumed <= 58926 and type(row) is dict and 'context' in row,'Finite original job metadata')
        if is_selected(row['context']):
            need(index < len(wanted) and row['context'] == wanted[index],'Complete canonical fixed selection, no repeat/reordering')
            index += 1
            yield row
    need(index == 42,'All14sessions by3fixedlags required; no partial endpoint')


def _packet(packet,role):
    need(type(packet) is dict and set(packet) == {'schema','role','selection_sha256','source_support_sha256',
         'prediction_run_sha256','scores','execution_qualified'},'Exact bounded endpoint packet')
    need(packet['schema'] == 'language-original-figure3b-scores/v1' and packet['role'] == role
         and packet['selection_sha256'] == hashlib.sha256(encoded(selection())).hexdigest()
         and type(packet['execution_qualified']) is bool,'Exact endpoint role/selection')
    digest(packet['source_support_sha256']);digest(packet['prediction_run_sha256'])
    rows=packet['scores']
    need(type(rows) in (list,tuple) and len(rows)==42,'Exactly42 original score cells')
    values=[]
    for row,context in zip(rows,contexts()):
        need(type(row) is dict and set(row)=={'context','pearson_r'} and row['context']==context,
             'Canonical fixed source score coordinates')
        r=row['pearson_r']
        need(r is None or (type(r) in (float,int) and type(r) is not bool and math.isfinite(r) and -1 <= r <= 1),
             'Finite Pearson or explicit undefinednull; no nonfinite JSON')
        values.append(float(r) if r is not None else None)
    return values


def _mean(values):
    return float(np.asarray(values,dtype=np.float64).mean()) if all(v is not None for v in values) else None


def compare(candidate,reference):
    """Continuous paired effects only, with complete original session weighting.

    Hashes bind attributed upstream evidence, not independent execution proof.
    Missing structural cells fail; undefined correlations propagate withoutdrop.
    """
    c,r = _packet(candidate,'candidate'),_packet(reference,'provided_author_reference')
    need(candidate['source_support_sha256']==reference['source_support_sha256'],
         'Same original target/observations/support binding; no convenient alternativetask')
    sessions=[]
    for i,sid in enumerate(SESSIONS):
        cc,rr=c[3*i:3*i+3],r[3*i:3*i+3]
        cm,rm=_mean(cc),_mean(rr)
        delta=cm-rm if cm is not None and rm is not None else None
        sessions.append({'session':sid,'person':sid.split('_')[0], 'candidate_lag_correlations':cc,
                         'author_lag_correlations':rr,'candidate_mean':cm,'author_mean':rm,'paired_delta':delta})
    deltas=[row['paired_delta'] for row in sessions]
    participants=[]
    for person in PEOPLE:
        own=[row for row in sessions if row['person']==person]
        kept=[row['paired_delta'] for row in sessions if row['person']!=person]
        own_deltas=[row['paired_delta'] for row in own]
        participants.append({'person':person,'sessions':[row['session'] for row in own],
            'session_deltas':own_deltas,'contribution_to_equal_session_delta':float(np.asarray(own_deltas,dtype=np.float64).sum()/14) if all(v is not None for v in own_deltas) else None,
            'participant_mean_diagnostic':_mean(own_deltas),
            'leave_one_person_out_equal_remaining_session_delta':_mean(kept),
            'remaining_session_count':len(kept)})
    return {'schema':'language-original-figure3b-continuous-comparison/v1','selection':selection(),
            'candidate_packet_sha256':hashlib.sha256(encoded(candidate)).hexdigest(),
            'reference_packet_sha256':hashlib.sha256(encoded(reference)).hexdigest(),
            'source_support_sha256':candidate['source_support_sha256'],'sessions':sessions,'participants':participants,
            'candidate_equal_session_mean':_mean([row['candidate_mean'] for row in sessions]),
            'author_equal_session_mean':_mean([row['author_mean'] for row in sessions]),
            'equal_session_paired_mean_delta':_mean(deltas),'defined_session_pairs':sum(v is not None for v in deltas),
            'independent_participant_clusters':8,'source_lag_cells':42,
            'uncertainty_method':None,'meaningful_effect_criterion':None,'binary_win':None,
            'supplied_execution_qualification_claims':{'candidate':candidate['execution_qualified'],'reference':reference['execution_qualified']},
            'execution_qualification_independently_verified':False,'scientific_qualification':False,
            'claim_scope':'Original Figure 3b contextual population predictivity only; not all paper findings or current SOTA',
            'limits':['Full 224-array reproduction remains separate. No other main-result improvement follows from an anchor gain.',
                      'Equal-session estimand retained; participant means and leave-one-person-out values are diagnostics.',
                      'Eight people are clusters; 42 lag cells and 5,685 software callbacks are not independent people.',
                      'Original retrospective PCA, centered smoothing and public exposure remain; fresh state cannot repair them.',
                      'Provided author results are not authenticated baseline reexecution; 567-versus-579 representation identity remains.']}
