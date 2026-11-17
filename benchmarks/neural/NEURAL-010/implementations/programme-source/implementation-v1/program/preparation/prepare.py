"""Complete future NEURAL010 original preparation, never invoked by source review.

This trusted upstream operation legitimately reads original annotations and one
operator identity key. Its labels do NOT belong to the downstream controller's
assessment reader. Namespace/process qualification remains external.
"""
import argparse
import builtins
import hashlib
import hmac
import json
import os
from pathlib import Path
import stat
import sys
import time
import types
from storage import Budget, canonical, capture, descriptor, disjoint, encoded, hash_file, need, strict, valid_pin, write, mkdir_fresh, mkdirs_owned, sync_owned_file
from views import make_views, validate_rows

HERE=Path(__file__).resolve().parent

def bootstrap_capture(path,pin,cap):
    valid_pin(pin);need(pin['bytes']<=cap,'bootstrap metadata cap')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==pin['bytes'],'ordinary bounded bootstrap metadata')
        body=bytearray()
        while len(body)<=pin['bytes']:
            chunk=os.read(fd,min(65536,pin['bytes']+1-len(body)))
            if not chunk:break
            body.extend(chunk)
        z=os.fstat(fd);need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)==(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns),'bootstrap source immutable')
        body=bytes(body);need(descriptor(body)==pin,'bootstrap metadata identity');return body
    finally:os.close(fd)

LOCK={'bytes':270520,'sha256':'7485ba994f8d0a33f596e68d6f552d0849d911dd9c971bf9fbeee77dad1c4111'}

def _ordinary(path):
    s=path.lstat();need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'ordinary single-link input')
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)

def _secret(path,budget):
    # No hash, representation, copy into receipts or source-facing artifact.
    budget.reserve('read',33);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==32,'operator identity authority extent')
        key=os.read(fd,33);z=os.fstat(fd)
        need(len(key)==32 and (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)==(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns),'stable identity authority')
        budget.tick();return key
    finally:os.close(fd)

def load_vendor(budget, metadata_root, metadata_pins, annotation_reads, source_bodies):
    bindings=strict(source_bodies['VENDOR_BINDINGS.json']);bodies={}
    for r in bindings['files']:
        pin={'bytes':r['bytes'],'sha256':r['sha256']}
        bodies[r['name']]=source_bodies['vendor/'+r['name']]
        need(descriptor(bodies[r['name']])==pin,'exact original producer body')
    modules={};normal_import=builtins.__import__
    def importer(name,globals=None,locals=None,fromlist=(),level=0):
        if name in modules:return modules[name]
        return normal_import(name,globals,locals,fromlist,level)
    def build(name):
        mod=types.ModuleType('neural010_original_'+name)
        scope=dict(vars(builtins));scope['__import__']=importer
        mod.__dict__['__builtins__']=scope
        exec(compile(bodies[name+'.py'],str(HERE/'vendor'/(name+'.py')),'exec'),mod.__dict__)
        modules[name]=mod;return mod
    event=build('event_protocol');io=build('io_contract')
    def metadata_read(path,cap=1000000,pin=None):
        p=canonical(str(path));need(p.parent==metadata_root and p.name in metadata_pins,'selected original metadata source')
        admitted=metadata_pins[p.name]
        need(pin is None or pin==admitted['sha256'],'metadata caller pin agrees')
        body=capture(p,admitted,budget,cap)
        annotation_reads.append({'name':p.name,**admitted,'read_kind':'original_annotation_or_reconciliation_metadata'})
        return body
    io.read=metadata_read
    reconcile=build('reconcile_annotations');edf=build('edf_adapter')
    return reconcile,edf,descriptor(source_bodies['VENDOR_BINDINGS.json']),bodies

def _admit(request,authority):
    need(type(authority)is dict and authority.get('schema')=='neural010-original-preparation-authority-v1','preparation authority schema')
    for k in ['qualified_original_preparation','qualified_source_closure','qualified_namespace','qualified_runtime_resources','operator_selected']:
        need(authority.get(k) is True,'missing independent '+k)
    need(authority.get('request')==descriptor(encoded(request)),'exact preparation request authority')
    required={'schema','task_id','lock','metadata_root','metadata_pins','staged_root','output_root','key_path','limits','original_origin'}
    need(type(request)is dict and set(request)==required and request['schema']=='neural010-original-preparation-request-v1' and request['task_id']=='NEURAL-010','complete typed request')
    need(authority.get('original_origin')==request['original_origin'] and type(request['original_origin'])in(int,float),'original clock binding')
    need(type(request['lock'])is dict and set(request['lock'])=={'path','bytes','sha256'} and {k:request['lock'][k] for k in ('bytes','sha256')}==LOCK,'exact selected original source roster')
    need(type(request['metadata_pins'])is dict and request['metadata_pins'],'complete original metadata authority')
    for n,pin in request['metadata_pins'].items():
        need(type(n)is str and n not in ('.','..') and '/' not in n,'metadata basename');valid_pin(pin)
    return Budget(request['limits'],request['original_origin'])

def prepare(request,authority,*,operator_origin,bootstrap_read_bytes=0):
    budget=_admit(request,authority)
    need(type(bootstrap_read_bytes)is int and bootstrap_read_bytes>=0,'bootstrap read debit')
    budget.reserve('read',bootstrap_read_bytes)
    manifest_pin=valid_pin(authority.get('source_manifest'))
    manifest_raw=capture(HERE/'SOURCE_MANIFEST.json',manifest_pin,budget,1000000)
    manifest=strict(manifest_raw);need(manifest.get('schema')=='neural010-preparation-runtime-sources-v1','source manifest schema')
    expected={'entry.py','prepare.py','storage.py','views.py','VENDOR_BINDINGS.json','vendor/edf_adapter.py','vendor/reconcile_annotations.py','vendor/io_contract.py','vendor/event_protocol.py','vendor/scorer.py'}
    need(type(manifest.get('files'))is list and {r['name'] for r in manifest['files']}==expected and len(manifest['files'])==len(expected),'complete exact preparation source closure')
    source_bodies={}
    for row in manifest['files']:
        source_bodies[row['name']]=capture(HERE/row['name'],{'bytes':row['bytes'],'sha256':row['sha256']},budget,1000000)
    # Parent must authenticate this producer before invocation; disk hashes alone cannot prove executing-code identity.
    budget.reserve('write',65536)
    need(type(operator_origin)in(int,float) and float(operator_origin)==budget.origin,'inherited preparer clock')
    staged=canonical(request['staged_root']);meta=canonical(request['metadata_root']);output=canonical(request['output_root'])
    key_path=canonical(request['key_path']);lock_path=canonical(request['lock']['path'])
    disjoint(staged,meta,output);need(not output.exists(),'fresh preparation output; no retry or overwrite')
    need(not key_path.is_relative_to(output) and not key_path.is_relative_to(staged) and not key_path.is_relative_to(meta),'private independent identity authority location')
    mkdir_fresh(output,budget);public=output/'public';private=output/'private';mkdir_fresh(public,budget);mkdir_fresh(private,budget);mkdir_fresh(public/'signals',budget)
    # External observer intent is still required: even this first record can fail.
    attempt={'schema':'neural010-preparation-attempt-v1','request':descriptor(encoded(request)),'original_origin':budget.origin,'status':'entered'}
    write(private/'ATTEMPT.json',encoded(attempt),budget)
    completed=[];annotation_reads=[]
    try:
        lock_raw=capture(lock_path,LOCK,budget,300000);lock=strict(lock_raw);rows=lock['records']
        need(lock['version']=='1.0.0' and len(rows)==686 and len({r['path'] for r in rows})==686 and len({r['patient'] for r in rows})==23 and len({r['case'] for r in rows})==24,'full686/24folder/23person original scope')
        expected_metadata={'RECORDS','RECORDS-WITH-SEIZURES','chb07_19.edf.seizures'}
        expected_metadata.update(r['path'].split('/')[0]+'-summary.txt' for r in lock['summaries'])
        expected_metadata.update(r['path'].split('/')[0]+'-index.html' for r in lock['summaries'])
        need(set(request['metadata_pins'])==expected_metadata,'exact complete reconciliation metadata namespace')
        need(request['metadata_pins']['RECORDS']['sha256']==lock['records_manifest_sha256'] and request['metadata_pins']['RECORDS-WITH-SEIZURES']['sha256']==lock['positive_manifest_sha256'],'original membership evidence')
        for row in lock['summaries']:
            name=row['path'].split('/')[0]+'-summary.txt';need(request['metadata_pins'][name]=={k:row[k] for k in ('bytes','sha256')},'exact original summary identity')
        rec,edf,vendor_pin,vendor_bodies=load_vendor(budget,meta,request['metadata_pins'],annotation_reads,source_bodies)
        source_annotations=rec.compile_annotations(lock,meta)['records']
        need(set(source_annotations)=={r['path'] for r in rows},'complete reconciled annotation support')
        key=_secret(key_path,budget)
        panels=[];targets=[];metadata=[];source_rows=[]
        for row in rows:
            budget.tick();need(type(row['bytes'])is int and row['bytes']>0,'original extent')
            src=canonical(str(staged/row['path']));need(src.is_relative_to(staged),'original source path confined')
            old=_ordinary(src);need(old[2]==row['bytes'],'source extent matches roster')
            rid=hmac.new(key,('record:'+row['path']).encode(),hashlib.sha256).hexdigest()[:24]
            pid=hmac.new(key,('patient:'+row['patient']).encode(),hashlib.sha256).hexdigest()[:24]
            dest=public/'signals'/(rid+'.h5')
            # Whole vendor invocation reservations; outer native observer enforces its actual resource limits.
            ceiling=2*row['bytes']+8*1048576
            need(16*row['bytes']+16*1048576<=budget.limits['project_peak_bytes'],'conservative per-record native allocation ceiling')
            budget.reserve('read',3*row['bytes']+1);budget.reserve('write',ceiling)
            header=edf.project(src,dest,row);budget.tick();need(_ordinary(src)==old,'original unchanged through conversion')
            sync_owned_file(dest,budget)
            projection=hash_file(dest,budget,ceiling);duration=header['duration_seconds']
            events=source_annotations[row['path']]['events'];last=-1
            for a,b in events:
                need(type(a)in(int,float) and type(b)in(int,float) and a==int(a) and b==int(b) and 0<=a<b<=duration and a>=last,'complete observed annotation alignment');last=b
            labels=[c['label'] for c in header['selected_channels']]
            montage=hashlib.sha256(encoded(sorted(labels),False)).hexdigest()
            panels.append({'recording_id':rid,'patient_id':pid,'duration_seconds':duration,'observed_intervals':[[0,duration]],'path':'signals/'+rid+'.h5',**projection})
            targets.append({'recording_id':rid,'events':events})
            metadata.append({'recording_id':rid,'patient_id':pid,'duration_seconds':duration,'montage_id':montage,'channel_count':len(labels),'channel_labels':labels,'source_edf':{k:row[k] for k in ('bytes','sha256')},'target_free_projection':projection})
            source_rows.append({'recording_id':rid,'source_path':row['path'],'source_edf':{k:row[k] for k in ('bytes','sha256')},'header':header,'annotation_evidence':source_annotations[row['path']]['evidence']})
            completed.append(rid)
        del key
        validate_rows(metadata)
        panel_body=encoded({'schema_version':1,'task_id':'NEURAL-009','records':sorted(panels,key=lambda r:r['recording_id'])})
        panel_pin=write(public/'panel.json',panel_body,budget)
        assessment=encoded({'schema_version':1,'task_id':'NEURAL-009','panel_sha256':panel_pin['sha256'],'records':sorted(targets,key=lambda r:r['recording_id'])})
        assessment_pin=write(private/'assessment.json',assessment,budget)
        metadata_pin=write(public/'metadata.json',encoded({'schema':'neural010-target-free-metadata-v1','records':sorted(metadata,key=lambda r:r['recording_id'])}),budget)
        annotations={r['recording_id']:r['events'] for r in targets};views=[]
        for view in make_views(metadata,annotations):
            directory=private/'views'/view['name'];mkdirs_owned(directory,private,budget)
            parts={}
            for name in ('TRAIN.json','QUERY.json','SUPPORT.json','VALIDATION.json'):
                if view[name] is not None:parts[name]=write(directory/name,view[name],budget)
            views.append({'name':view['name'],'artifacts':parts})
        need(len(views)==529,'all23 final and506 inner fold views')
        provenance_pin=write(private/'SOURCE_PROVENANCE.json',encoded({'records':source_rows}),budget)
        annotation_pin=write(private/'ANNOTATION_READS.json',encoded({'records':annotation_reads,'legitimate_upstream_label_reads':True,'downstream_assessment_operand_opened':False}),budget)
        receipt={'schema':'neural010-original-preparation-v1','status':'prepared_not_runtime_or_scientifically_qualified','records':686,'people':23,'source_folders':24,'source_roster':LOCK,'vendor_sources':vendor_pin,'source_manifest':manifest_pin,'panel':panel_pin,'assessment':assessment_pin,'metadata':metadata_pin,'source_provenance':provenance_pin,'annotation_reads':annotation_pin,'views':views,'cost_snapshot':budget.record(),'actual_models_or_scores':0,'global_assessment_release_authorized':False}
        n=0
        for _ in range(8):
            snapshot=budget.record();snapshot['logical_reserved_write_bytes']=budget.write_bytes+n
            receipt['cost_snapshot']=snapshot;body=encoded(receipt)
            if len(body)==n:break
            n=len(body)
        else:raise ValueError('receipt debit did not stabilize')
        write(private/'PREPARATION.json',body,budget);budget.tick()
        need(receipt['cost_snapshot']==budget.record(),'final receipt reservation matches actual logical ledger')
        return receipt
    except BaseException as error:
        # No repair, deletion, blind retry or fabricated success. Publication may itself fail.
        failure={'schema':'neural010-preparation-failure-v1','status':'failed_or_interrupted','completed_recording_ids':completed,'error_type':type(error).__name__,'cost_snapshot':budget.record(),'external_inspection_required':True}
        try:
            body=encoded(failure);need(len(body)<=65536,'reserved failure metadata bound');fd=os.open(private/'FAILURE.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
            try:
                remaining=memoryview(body)
                while remaining:
                    written=os.write(fd,remaining);need(written>0,'failure record write');remaining=remaining[written:]
                os.fsync(fd)
            finally:os.close(fd)
        except BaseException:pass
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('request','authority','authority-sha256'):p.add_argument('--'+n,required=True)
    p.add_argument('--authority-bytes',type=int,required=True);a=p.parse_args()
    # Bootstrap authority reads are metadata only and separately bounded. It cannot make itself trusted.
    auth_path=canonical(a.authority);need(0<a.authority_bytes<=1048576,'authority cap')
    b=bootstrap_capture(auth_path,{'bytes':a.authority_bytes,'sha256':a.authority_sha256},1048576)
    authority=strict(b);rpin=authority['request'];valid_pin(rpin);need(rpin['bytes']<=1048576,'request cap')
    rp=canonical(a.request);raw=bootstrap_capture(rp,rpin,1048576)
    request=strict(raw);result=prepare(request,authority,operator_origin=request['original_origin'],bootstrap_read_bytes=len(b)+len(raw)+2)
    print(json.dumps({'status':result['status'],'records':686,'people':23},sort_keys=True))

if __name__=='__main__':raise SystemExit('Use the authenticated isolated entry.py command; direct preparation-module execution is unsupported.')
