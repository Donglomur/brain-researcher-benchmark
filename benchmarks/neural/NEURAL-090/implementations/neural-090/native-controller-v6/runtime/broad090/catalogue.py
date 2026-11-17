"""Exact Broad cohort and original annotation/clock consumers.

No task metric, calibration count, estimator or new release is chosen here.
All source operands are private. The caller must possess authenticated original
assets and event-equivalence evidence; this module issues no authority.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib,json
from programme.contracts import Pin,Asset,need,fields,identity
from programme.n090_support import parse_run,complete_release
from programme.n090_adapter import parse_events

PEOPLE=tuple(str(x) for x in range(1,33))
KEYS=tuple((p,c,'Sherlock1','1') for p in PEOPLE for c in ('11','12'))

def complete_catalogue(document):
    fields(document,('schema','release','runs','person_subject_join','visit_interpretation'))
    need(document['schema']=='n090-broad-original-catalogue-v1','explicit catalogue version')
    release=Pin.parse(document['release'])
    need(document['visit_interpretation']=='two_chapter_blocks_one_visit','source session keys are not independent visits')
    join=document['person_subject_join'];need(type(join) is dict and set(join)==set(PEOPLE),'complete32 source-subject join')
    need(len(set(join.values()))==32,'one distinct biological person per source subject')
    for value in join.values():identity(value)
    runs=tuple(parse_run(row) for row in document['runs'])
    index=complete_release(runs,KEYS,tuple(join.values()))
    need(all(r.person==join[r.key[0]] and r.release==release for r in runs),'actual person/release join')
    need(all(r.key in KEYS for r in runs),'full original Broad64; no Deep or substituted run')
    need(len({r.annotations.path for r in runs})==64,'distinct original annotation aliases')
    need(len({r.channels for r in runs})==1,'common verified306-channel identity required')
    return index

def exact_json(body):
    def pairs(rows):
        out={}
        for k,v in rows:
            need(k not in out,'duplicate source metadata key');out[k]=v
        return out
    return json.loads(body,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite source metadata')))

def source_events(run,root,classes,equivalence_asset,read_limit,read_bytes):
    """Read exact original TSV and complete private canonical-event map.

    Equivalence is a separately authenticated source operand, not inferred from
    an equal local row number or a rounded MEG timestamp across participants.
    Full/reduced recording clocks are already explicit in the typed run.
    """
    need(type(equivalence_asset) is Asset,'exact private equivalence asset')
    required=2*(run.annotations.pin.bytes+equivalence_asset.pin.bytes)
    need(type(read_limit) is int and required<=read_limit,'whole annotation/equivalence reads before effects')
    events,disposition=parse_events(read_bytes(run.annotations),classes,run.clock)
    mapping=exact_json(read_bytes(equivalence_asset))
    fields(mapping,('schema','run_key','annotations','evidence','events'))
    need(mapping['schema']=='original-event-equivalence-v1' and tuple(mapping['run_key'])==run.key,'exact source-run correspondence')
    need(Pin.parse(mapping['annotations'])==run.annotations.pin,'equivalence bound to actual annotation bytes')
    evidence=Pin.parse(mapping['evidence'])
    entries=mapping['events'];need(type(entries) is list,'complete event list')
    mapped={}
    for row in entries:
        fields(row,('source_idx','source_row0','chapter','canonical_event','canonical_word','word_onset_seconds','word_end_seconds'))
        key=identity(row['source_idx']);need(key not in mapped,'unique original event row')
        need(type(row['source_row0']) is int and row['source_row0']>=0,'original row ordinal')
        need(row['chapter']==run.key[1],'original chapter equivalence')
        identity(row['canonical_event']);identity(row['canonical_word'])
        # Word times are exact source-clock strings, used later to mask target
        # words; they are never promoted to a public query timestamp.
        from programme.contracts import rational
        start,end=rational(row['word_onset_seconds']),rational(row['word_end_seconds'])
        need(start<end,'source word interval')
        mapped[key]=row
    need(set(mapped)=={e['source_idx'] for e in events},'every eligible event and no invented support')
    result=[]
    for e in events:
        r=mapped[e['source_idx']]
        need(r['source_row0']==e['source_row0'],'actual annotation row identity')
        from programme.contracts import rational
        onset=rational(e['annotation_seconds'])
        need(rational(r['word_onset_seconds'])<=onset<rational(r['word_end_seconds']),'phoneme lies in its original word')
        result.append({**e,**r,'run_key':run.key,'person':run.person,'recording':run.recording.pin.json(),
                       'annotations':run.annotations.pin.json(),'equivalence':equivalence_asset.pin.json(),
                       'equivalence_evidence':evidence.json(),'clock_evidence':run.clock.evidence.json()})
    return tuple(result),disposition

def whole_event_support(events_by_run,index):
    """Full64 join and global repeated-event audit, never a scoring reduction."""
    need(set(events_by_run)==set(index)==set(KEYS),'complete64 source-event producers')
    groups={};by_chapter={c:set() for c in ('11','12')};counts={}
    for key in KEYS:
        events=tuple(events_by_run[key]);need(events,'no missing or empty participant/chapter event source')
        ids=set()
        for e in events:
            need(tuple(e['run_key'])==key and e['person']==index[key].person,'event owner identity')
            identity(e['source_idx']);need(e['source_idx'] not in ids,'unique original event support');ids.add(e['source_idx'])
            event=e['canonical_event'];identity(event);need(e['chapter']==key[1],'chapter support')
            need(type(e['label']) is int and 0<=e['label']<39,'exact39-class source disposition')
            g=groups.setdefault(event,{'chapter':e['chapter'],'label':e['label'],'canonical_word':e['canonical_word'],'members':[]})
            need((g['chapter'],g['label'],g['canonical_word'])==(e['chapter'],e['label'],e['canonical_word']),
                 'same canonical event has coherent original chapter/label/word; no guessed equivalence')
            need(all(m['run_key']!=key for m in g['members']),'one canonical event occurrence per run')
            g['members'].append({'run_key':key,'source_idx':e['source_idx'],'source_row0':e['source_row0'],'person':e['person']})
            by_chapter[key[1]].add(event)
        counts['/'.join(key)]=len(events)
    need(not(by_chapter['11']&by_chapter['12']),'distinct chapters cannot share a canonical event token')
    return {'schema':'n090-global-original-support-v1','run_counts':counts,'canonical_event_groups':groups,
            'biological_people':32,'chapter_blocks':64,'independent_visits_claim':False,
            'availability':'source-derived only when all original operands supplied','qualification':False}
