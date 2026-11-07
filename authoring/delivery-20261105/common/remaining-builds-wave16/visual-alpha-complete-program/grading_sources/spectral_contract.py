"""Prospective fidelity metric for 36 released derived timecourses, not a fit.

The CLI owns strict UTF-8/duplicate-key JSON parsing and same-open <=16 MiB
capture. This module validates the entire decoded public submission before its
private-target callback. It never opens a path or fits a spectral/neural model.
MAE weighting is finite timepoints within electrode, equal native electrodes
within participant, equal nine participants within each of four separate units.
Missing support must match the fixed target's nonfinite mask exactly. An empty
electrode is unsupported, never silently excluded. This is a new benchmark
metric; the paper does not report these four MAEs.
"""
from fractions import Fraction
import math

import numpy as np

from interface import InvalidSubmission, InvalidRoster

MAX_BYTES=16*1024*1024
MAX_FINITE=float(np.finfo(np.float64).max)
PARTICIPANTS=('p01','p02','p05','p06','p07','p08','p09','p10','p11')
SIGNALS=('corrected_alpha','broadband','raw_alpha','low_broadband')


class InvalidTargets(ValueError):
    """Operator target/roster defect; never a candidate zero score."""


def _fields(value,keys,error):
    if type(value) is not dict or set(value)!=set(keys):raise error('Exact object fields required')


def _id(v):
    return type(v) is str and 0<len(v)<=512


def _sha(v):
    return type(v) is str and len(v)==64 and all(c in '0123456789abcdef' for c in v)


def validate_roster(roster):
    if type(roster) is not list or len(roster)!=36:raise InvalidRoster('Full nine-participant/four-signal roster required')
    ids=set();pairs=set();normalized=[]
    for r in roster:
        _fields(r,('case_id','participant','signal','electrode_ids'),InvalidRoster)
        if not _id(r['case_id']) or r['case_id'] in ids or r['participant'] not in PARTICIPANTS or r['signal'] not in SIGNALS:
            raise InvalidRoster('Roster identity')
        pair=(r['participant'],r['signal'])
        if pair in pairs:raise InvalidRoster('Duplicate participant/signal')
        e=r['electrode_ids']
        if type(e) is not list or not e or any(not _id(v) for v in e) or len(set(e))!=len(e):
            raise InvalidRoster('Explicit nonempty unique ordered native electrodes required')
        ids.add(r['case_id']);pairs.add(pair)
        normalized.append({**r,'electrode_ids':list(e)})
    if pairs!={(p,s) for p in PARTICIPANTS for s in SIGNALS}:raise InvalidRoster('Incomplete participant/signal product')
    return normalized


def validate_submission(value,roster,roster_sha256):
    rows=validate_roster(roster)
    if not _sha(roster_sha256):raise InvalidRoster('Authenticated roster SHA256 required')
    _fields(value,('schema','roster_sha256','cases'),InvalidSubmission)
    if value['schema']!='visual_alpha_timecourses_v1' or value['roster_sha256']!=roster_sha256:
        raise InvalidSubmission('Schema or roster identity mismatch')
    if type(value['cases']) is not list or len(value['cases'])!=36:raise InvalidSubmission('All36cases required')
    expected={r['case_id']:r for r in rows};by={}
    for case in value['cases']:
        _fields(case,('case_id','values'),InvalidSubmission)
        ident=case['case_id']
        if type(ident) is not str or ident not in expected or ident in by:raise InvalidSubmission('Case bijection required')
        vals=case['values'];count=len(expected[ident]['electrode_ids'])
        if type(vals) is not list or len(vals)!=count:raise InvalidSubmission('Exact native electrode row count required')
        copied=[]
        for row in vals:
            if type(row) is not list or len(row)!=75:raise InvalidSubmission('Each electrode requires all75timepoints')
            clean=[]
            for v in row:
                if v is not None:
                    if type(v) not in (int,float):raise InvalidSubmission('Finite JSON numbers ornull; booleans refused')
                    try:finite=math.isfinite(float(v))
                    except (OverflowError,ValueError):finite=False
                    if not finite or abs(v)>MAX_FINITE:
                        raise InvalidSubmission('Number outside finite float64 range')
                clean.append(v)
            copied.append(clean)
        by[ident]={'case_id':ident,'values':copied}
    return {'schema':'visual_alpha_timecourses_v1','roster_sha256':roster_sha256,
            'cases':[by[r['case_id']] for r in rows]}


def _fraction(v):
    return Fraction(v) if type(v) is int else Fraction.from_float(float(v))


def _present(q):
    try:v=float(q)
    except OverflowError:return {'status':'unsupported_numeric_range','mae':None}
    if not math.isfinite(v) or (q!=0 and v==0):
        return {'status':'unsupported_numeric_range','mae':None}
    return {'status':'defined','mae':v}


def score_submission(value,roster,roster_sha256,load_targets):
    """Callback returns {case_id: primitivefloat64[ordered electrodes,75]}.

    All public cases are copied/validated BEFORE this callback. Malformed targets
    raise InvalidTargets; mask mismatches return invalid_comparison_support with
    ALL four primary values null. Exact Fraction errors prevent subtractive
    cancellation and intermediate overflow. Positive underflow is unsupported,
    not reported as zero. Integer JSON values are exact; floats use their exact
    represented binary value. No raw numeric targets are returned.
    """
    rows=validate_roster(roster)
    submission=validate_submission(value,rows,roster_sha256)
    targets=load_targets()
    expected={r['case_id'] for r in rows}
    if type(targets) is not dict or set(targets)!=expected:raise InvalidTargets('Exact target case support required')
    for r in rows:
        t=targets[r['case_id']]
        if type(t) is not np.ndarray or t.dtype.kind!='f' or t.dtype.itemsize!=8 or t.shape!=(len(r['electrode_ids']),75):
            raise InvalidTargets('Primitive float64 exact target geometry required')
    mismatches=[]
    for r,c in zip(rows,submission['cases']):
        t=targets[r['case_id']]
        for ei,(eid,v) in enumerate(zip(r['electrode_ids'],c['values'])):
            mismatch=sum((x is None)!= (not math.isfinite(float(y))) for x,y in zip(v,t[ei]))
            if mismatch:mismatches.append({'case_id':r['case_id'],'electrode_id':eid,'timepoints':mismatch})
    if mismatches:
        return {'schema':'visual_alpha_timecourse_score_v1','status':'invalid_comparison_support',
                'signals':{s:{'status':'invalid_comparison_support','mae':None} for s in SIGNALS},
                'support_mismatches':mismatches}
    cases={};exact={}
    for r,c in zip(rows,submission['cases']):
        electrodes=[];row_q=[]
        for ei,(eid,v) in enumerate(zip(r['electrode_ids'],c['values'])):
            pairs=[(x,float(y)) for x,y in zip(v,targets[r['case_id']][ei]) if x is not None]
            item={'electrode_id':eid,'finite_timepoints':len(pairs),'total_timepoints':75}
            if not pairs:
                item.update(status='unsupported_empty_electrode',mae=None);row_q.append(None)
            else:
                q=sum((abs(_fraction(x)-Fraction.from_float(y)) for x,y in pairs),Fraction(0))/len(pairs)
                item.update(_present(q));row_q.append(q if item['status']=='defined' else None)
            electrodes.append(item)
        key=(r['participant'],r['signal']);q=None
        if any(q0 is None for q0 in row_q):metric={'status':'unsupported_electrode','mae':None}
        else:q=sum(row_q,Fraction(0))/len(row_q);metric=_present(q)
        cases[key]={'participant':r['participant'],'case_id':r['case_id'],**metric,
                    'native_electrodes':len(electrodes),'electrodes':electrodes}
        exact[key]=q if metric['status']=='defined' else None
    signals={}
    for s in SIGNALS:
        q=[exact[p,s] for p in PARTICIPANTS]
        metric=({'status':'unsupported_participant','mae':None} if any(v is None for v in q)
                else _present(sum(q,Fraction(0))/len(q)))
        signals[s]={**metric,'metric':'equal_participant_equal_electrode_finite_time_mae',
                    'units':'released_'+s+'_timecourse_units','required_participants':9,
                    'participants':[cases[p,s] for p in PARTICIPANTS]}
    return {'schema':'visual_alpha_timecourse_score_v1',
            'status':'defined' if all(v['status']=='defined' for v in signals.values()) else 'unsupported',
            'signals':signals,'support_mismatches':[],
            'aggregation_across_signal_units':None,'paper_reported_mae':False}
