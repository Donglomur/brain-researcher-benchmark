"""Bind the existing fixed 44-asset declaration without reading any NWB.

Source subject/asset declarations are not authentic cohort ascertainment. The
actual preparation must independently match NWB subject/session identities.
Download URLs in the retained legacy declaration are not consumed or exposed.
"""
from core import need,pin,parse
LOCK={'bytes':16501,'sha256':'988b0b979d9d940963ee8c0223b2e0941ef8754279f59f60afb459da91dbe548'}

def declared(raw):
    need(pin(raw)==LOCK,'exact selected pre-existing source asset declaration')
    value=parse(raw)
    need(value['dandiset']=='000673' and value['version']=='0.240118.2135' and value['complete'] is True,'fixed archive declaration')
    rows=value['assets'];need(len(rows)==44 and len({r['asset_id'] for r in rows})==44,'complete distinct source asset slots')
    need(len({r['subject_id'] for r in rows})==36,'source-declared patient extent, not actual header evidence')
    return rows

def bind(raw,review):
    original=declared(raw);sessions={r['asset_id']:r for r in review['sessions']}
    need(len(sessions)==44 and set(sessions)=={r['asset_id'] for r in original},'complete independently reviewed sessions')
    return {'schema':'n041_roster_v1','dataset':'000673/0.240118.2135','provenance':{'declared_source_lock':LOCK,'actual_headers_verified':False},
        'assets':[{'asset_id':r['asset_id'],'patient_id':r['subject_id'],'session_id':sessions[r['asset_id']]['source_session_id'],
            'path':r['path'],'pin':{'bytes':r['bytes'],'sha256':r['sha256']}} for r in original]}
