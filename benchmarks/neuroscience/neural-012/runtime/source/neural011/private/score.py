"""Target-private full-panel continuous seizure event scorer; stdlib only."""
import argparse
import hashlib
import math
from pathlib import Path
import io_contract as io
import event_protocol as event


def intervals(value,duration):
    io.need(type(value)is list and len(value)<=duration,'bounded event array')
    last=0
    for pair in value:
        io.need(type(pair)is list and len(pair)==2,'onset/offset pair')
        a,b=pair
        io.need(all(type(x)in(int,float) and math.isfinite(x) for x in pair)
                and 0<=a<b<=duration and a>=last,'sorted disjoint finite in-file intervals')
        last=b
    return value


def panel(value):
    io.header(value,'records');rows=value['records']
    io.need(type(rows)is list and len(rows)==41,'all41 source recordings required')
    result={}
    for r in rows:
        io.fields(r,['recording_id','patient_id','duration_seconds','observed_intervals','path','bytes','sha256'])
        rid=r['recording_id'];pid=r['patient_id'];d=r['duration_seconds']
        io.need(type(rid)is str and io.ID.fullmatch(rid) and rid not in result
                and type(pid)is str and io.ID.fullmatch(pid),'unique opaque record and patient IDs')
        io.need(type(d)is int and 0<d<=86400 and r['observed_intervals']==[[0,d]],'entire observed continuous file')
        io.need(r['path']=='signals/'+rid+'.h5' and type(r['bytes'])is int and 0<r['bytes']<10000000000
                and type(r['sha256'])is str and len(r['sha256'])==64 and all(c in '0123456789abcdef' for c in r['sha256']),'exact input binding')
        result[rid]=r
    io.need(len({r['patient_id'] for r in rows})==14 and sum(r['duration_seconds'] for r in rows)<=10000000,'all14 patients/bounded full observed panel')
    return result


def predictions(value,records):
    io.header(value,'records');rows=value['records'];result={}
    io.need(type(rows)is list and len(rows)==len(records),'complete prediction support')
    for r in rows:
        io.fields(r,['recording_id','scores','events']);rid=r['recording_id']
        io.need(type(rid)is str and rid in records and rid not in result,'unique known prediction ID')
        d=records[rid]['duration_seconds'];io.need(type(r['scores'])is list,'score list')
        derived=event.from_scores(r['scores'],d);intervals(r['events'],d)
        io.need(r['events']==derived,'events must equal fixed score threshold/merge/split transform')
        result[rid]=derived
    io.need(set(result)==set(records),'every full recording predicted')
    return result


def targets(value,records,panel_sha):
    io.fields(value,['schema_version','task_id','panel_sha256','records'])
    io.need(type(value['schema_version'])is int and value['schema_version']==1 and value['task_id']==io.TASK
            and value['panel_sha256']==panel_sha,'exact private target/panel binding')
    rows=value['records'];io.need(type(rows)is list and len(rows)==len(records),'complete targets');result={}
    for r in rows:
        io.fields(r,['recording_id','events']);rid=r['recording_id']
        io.need(type(rid)is str and rid in records and rid not in result,'one exact target per record')
        events=intervals(r['events'],records[rid]['duration_seconds'])
        io.need(all(x==int(x) for pair in events for x in pair),'pinned Siena annotations have integral-second endpoints')
        result[rid]=events
    return result


def grade(panel_raw,prediction_raw,target_provider):
    records=panel(io.strict(panel_raw));hyp=predictions(io.strict(prediction_raw),records)
    # Candidate admission is complete before any private provider is invoked.
    gold=targets(io.strict(target_provider()),records,hashlib.sha256(panel_raw).hexdigest())
    groups={}
    for rid,r in records.items():
        groups.setdefault(r['patient_id'],[]).append(event.count_events(gold[rid],hyp[rid],r['duration_seconds']))
    patient={pid:event.summarize(counts) for pid,counts in sorted(groups.items())}
    io.need(all(p['reference_events']>0 for p in patient.values()),'full source every patient must have a reference seizure')
    macro=lambda field:math.fsum(p[field] for p in patient.values())/14
    return {'schema_version':1,'task_id':io.TASK,'primary_metric':'patient_macro_event_f1',
            'patient_macro_event_f1':macro('event_f1'),'patient_macro_event_sensitivity':macro('event_sensitivity'),
            'patient_macro_false_alarms_per_24_observed_hours':macro('false_alarms_per_24_observed_hours'),
            'pooled':event.summarize([c for rows in groups.values() for c in rows]),'patients':patient,
            'recordings':41,'biological_patients':14,'interfile_gaps_counted':False}


def run(panel_path,prediction_path,target_path,output_path,targets_sha256):
    io.need(not output_path.exists() and not output_path.is_symlink(),'fresh output before grading/private access')
    return io.write(output_path,grade(io.read(panel_path,1000000),io.read(prediction_path),
                                     lambda:io.read(target_path,1000000,pin=targets_sha256)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('panel','prediction','targets','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--targets-sha256',required=True)
    a=p.parse_args();run(a.panel,a.prediction,a.targets,a.output,a.targets_sha256)
