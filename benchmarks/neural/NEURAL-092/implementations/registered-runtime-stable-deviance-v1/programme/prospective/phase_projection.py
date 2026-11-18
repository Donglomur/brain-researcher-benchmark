"""Ordinary proposed prediction-index projection; not an isolation or issuer implementation.

No arrays, file paths, authentic cohort objects or scientific providers are read.
This is an inactive proposed component; the observed legacy entry is unchanged.
The caller must independently authenticate the complete index/cohort and enforce
actual mounts, prediction freeze, evaluator ownership and later observation.
"""
from copy import deepcopy
import re
EXPECTED_FIELDS={'schema','task_id','roster_sha256','sessions','limitations'}
SESSION_FIELDS={'session_id','mouse_id','metadata','counts'}
def descriptor(value,expected_path):
    if type(value)is not dict or set(value)!={'path','bytes','sha256'}:
        raise ValueError('closed original file descriptor')
    if value['path']!=expected_path or type(value['bytes'])is not int or not 0<=value['bytes']<=134217728:
        raise ValueError('exact original phase filename and bounded extent')
    if type(value['sha256'])is not str or not re.fullmatch('[0-9a-f]{64}',value['sha256']):
        raise ValueError('descriptor digest syntax, not authentication')
def project_prediction_index(index,expected_session_ids):
    if type(index)is not dict or set(index)!=EXPECTED_FIELDS:
        raise ValueError('closed original packet index')
    if index['schema']!='neuropixels_task_packet_v1' or index['task_id']!='NEURAL-092':
        raise ValueError('exact N092 original schema')
    if type(expected_session_ids)not in (tuple,list)or len(expected_session_ids)!=32:
        raise ValueError('full32 caller-selected session IDs, not a source-issued cohort')
    if any(type(x)is not str or not x for x in expected_session_ids)or len(set(expected_session_ids))!=32:
        raise ValueError('unique complete session IDs')
    if type(index['sessions'])is not list or len(index['sessions'])!=32:
        raise ValueError('complete original session list')
    sessions=[];seen=set()
    for row in index['sessions']:
        if type(row)is not dict or set(row)!=SESSION_FIELDS or type(row['session_id'])is not str:
            raise ValueError('closed original session descriptor')
        sid=row['session_id']
        if not re.fullmatch('[A-Za-z0-9_-]+',sid):raise ValueError('single original session component')
        if sid in seen or sid not in expected_session_ids:raise ValueError('duplicate/unselected session')
        seen.add(sid)
        if type(row['mouse_id'])is not str or not row['mouse_id']:
            raise ValueError('native mouse descriptor required')
        counts=row['counts']
        if type(counts)is not dict or set(counts)!={'FIT','VALIDATION','QUERY'}:
            raise ValueError('all original phase descriptors must be explicitly accounted')
        descriptor(row['metadata'],'public/'+sid+'.json')
        for phase in ('FIT','VALIDATION','QUERY'):
            descriptor(counts[phase],'public/'+sid+'-'+phase+'.npz')
        projected=deepcopy(row)
        projected['counts']={phase:deepcopy(counts[phase])for phase in ('FIT','VALIDATION')}
        sessions.append(projected)
    if seen!=set(expected_session_ids):raise ValueError('complete same-unit session panel')
    if len({row['mouse_id']for row in sessions})!=32:raise ValueError('selected32 distinct mouse descriptors')
    return {'schema':'neural092_prediction_view_proposal_v1','task_id':'NEURAL-092',
            'sessions':sessions,'roster_sha256':index['roster_sha256'],
            'limitations':deepcopy(index['limitations']),
            'status':'inactive_proposed_source_projection',
            'query_response_descriptors_included':False,
            'authentic_input_or_isolation_authority':False}

