#!/usr/bin/env python3
"""Generated-only orchestration controls; no native paths are opened as data.

Real pinned pure cores execute on an in-memory 171-member ZIP. The guard double
holds only generated scientific metadata and writes in-memory artifacts. The
ZIP guard's SIZE constant alone is rebound to the generated archive size.
"""
from collections import Counter
from contextlib import contextmanager, redirect_stdout
import copy
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import types
import unittest
import zipfile
import zlib

HERE=Path(__file__).resolve().parent
TASK=HERE.parents[1]
A=HERE/'archived-source'
MODULES={
 'numeric_policy':(TASK/'implementations/source-eeg-numeric-v1/numeric_policy.py','695022e90fb28deac0318b8c253bd66cc0b051155ac90746940951159b1997f5'),
 'numeric_stream':(TASK/'implementations/source-eeg-numeric-v1/numeric_stream.py','9d73432626c89843ae5c063a437876fe0dc064dc1962b96e5f3b8816999d31f7'),
 'annotation_adapter':(TASK/'implementations/source-annotation-events-v1/annotation_events.py','be81d3e1a9dda6161f90f8cd79b82212e3c64377c5b920c3529a03101753ac2d'),
 'zip_guard':(A/'inventory_original.py','9404129e5ba4e4ceab1afa744ff83cc800cac5b402d830b78eefae4cf1753cf9'),
}
FIELDS=('EVENT','MOAAS','SOC','Misc','Propofol','Midazolam','Endoscopy')
HEADER=('Time','Intellivue/EEG_1','Intellivue/EEG_2',*FIELDS)
OLD_PROTOCOL='e'*64

def digest(raw):return hashlib.sha256(raw).hexdigest()
def encode(value):return json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':')).encode()+b'\n'
def module_from(path,name,pin=None):
    raw=path.read_bytes()
    if pin is not None:assert digest(raw)==pin,(path,digest(raw))
    module=types.ModuleType(name);module.__file__=str(path);sys.modules[name]=module
    exec(compile(raw,str(path),'exec'),module.__dict__)
    return module

P=module_from(A/'eeg_producer.py','generated_eeg_producer',
              'b1badba3a1bd5701f53c710c12c6bb2c03e9466263ef73c32725f94587f650a2')
CODE={key:path.read_bytes() for key,(path,pin) in MODULES.items()}
for key,raw in CODE.items():assert digest(raw)==MODULES[key][1]

class Fixture:
    def __init__(self):
        self.ids=['83','84','209']+[str(i) for i in range(1,171) if i not in (83,84)]
        assert len(self.ids)==171
        self.objects={};self.files={};self.ledgers={};self.reports={};self.receipts={};self.summaries={}
        self.source={};self.annotations={};self.protocol={'full_scope_recordings':171,'total_source_rows':513,
            'archive_path':'/generated/data.zip','native_run_id':'generated-eeg-only',
            'producer_path':'/generated/eeg_producer.py','producer_sha256':'a'*64,
            'guards_path':'/generated/eeg_guards.py','guards_sha256':'b'*64,
            'source_release':'generated-test-not-native'}
        for key,(path,pin) in MODULES.items():self.protocol[key+'_path']=str(path);self.protocol[key+'_sha256']=pin
        base=dt.datetime(2024,1,2,3,4,5)
        for rid in self.ids:
            times=[base,base+dt.timedelta(milliseconds=4),base+dt.timedelta(milliseconds=4 if rid=='83' else 8)]
            annotations=[];buf=io.StringIO(newline='');writer=csv.writer(buf,lineterminator='\n');writer.writerow(HEADER)
            for index,timestamp in enumerate(times):
                raw={key:'' for key in FIELDS}
                if index==0:raw.update(EVENT='MOAAS3',MOAAS='3.0')
                if index==2:
                    if rid=='84':raw.update(EVENT='PROP',Propofol='10.0')
                    else:raw.update(EVENT='LOC',SOC='0.0')
                raw_time=timestamp.isoformat(sep=' ',timespec='milliseconds')
                numeric=[('-0',''),('bad','187.5'),('1e-9999','188')][index]
                writer.writerow([raw_time,*numeric,*(raw[key] for key in FIELDS)])
                if index!=1:
                    annotations.append({'source_row':index,'source_physical_line_end':index+2,'raw_time':raw_time,
                      'recognized_time_ms':timestamp.toordinal()*86400000+((3*60+4)*60+5)*1000+(timestamp.microsecond//1000),
                      'timestamp_issues':['duplicate_timestamp'] if rid=='83' and index==2 else [],'original_fields':raw})
            self.source[rid]=buf.getvalue().encode();self.annotations[rid]=annotations
            self.ledgers[rid]=b''.join(encode(row) for row in annotations)
        raw_zip=io.BytesIO()
        with zipfile.ZipFile(raw_zip,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('data/',b'')
            for rid in self.ids:archive.writestr('data/generated-'+rid+'.csv',self.source[rid])
        self.archive=raw_zip.getvalue();self.protocol['archive_sha256']=digest(self.archive)
        inv_members=[];header_members=[];manifest_members=[]
        with zipfile.ZipFile(io.BytesIO(self.archive)) as archive:
            for info in archive.infolist():
                rid=None if info.is_dir() else info.filename.split('-')[-1].split('.')[0]
                inv_members.append({'path':info.filename,'study_id':rid,'directory':info.is_dir(),'expanded_bytes':info.file_size,
                    'compressed_bytes':info.compress_size,'crc32_from_directory_only':f'{info.CRC:08x}',
                    'header_offset':info.header_offset,'compression_method':info.compress_type,'flag_bits':info.flag_bits})
            for index,rid in enumerate(self.ids):
                info=archive.getinfo('data/generated-'+rid+'.csv');source=self.source[rid]
                header_sha=digest(source.splitlines(keepends=True)[0]);clock={'duplicate_timestamp':1} if rid=='83' else {}
                common={'recording_id':rid,'protocol_sha256':OLD_PROTOCOL,'archive_sha256':self.protocol['archive_sha256'],
                    'archive_path':self.protocol['archive_path'],'member_path':info.filename,'source_data_rows':3}
                report={**common,'schema':'dosei_private_annotation_member_census_v1','status':'succeeded',
                    'expanded_bytes_read':len(source),'member_sha256':digest(source),'member_crc32':f'{info.CRC:08x}',
                    'header_sha256':header_sha,'protected_annotation_rows':2,'complete_member_EOF':True,
                    'complete_member_CRC_verified':True,'source_member_release_authenticated':True,
                    'timestamp_audit':{'issue_counts':clock}}
                self.reports[rid]=report
                self.receipts[rid]={**common,'schema':'dosei_annotation_census_member_receipt_v1','status':'succeeded','error':None}
                self.summaries[rid]={key:report[key] for key in ('recording_id','member_path','source_data_rows','expanded_bytes_read',
                    'member_sha256','member_crc32','header_sha256','protected_annotation_rows')}
                header_members.append({'recording_id':rid,'path':info.filename,'header_sha256':header_sha})
                manifest_members.append({'index':index,'recording_id':rid,'member_path':info.filename,
                    'expanded_bytes':info.file_size,'compressed_bytes':info.compress_size,'member_crc32':f'{info.CRC:08x}',
                    'header_sha256':header_sha})
        self.objects['inventory']={'schema':'dosei_range_directory_inventory_v1','status':'succeeded','csv_count':171,
            'archive_path':self.protocol['archive_path'],'archive_sha256_verified_during_acquisition':self.protocol['archive_sha256'],'members':inv_members}
        self.objects['headers']={'schema':'dosei_native_header_inventory_v1','status':'succeeded','csv_header_lines_read':171,
            'archive_sha256':self.protocol['archive_sha256'],'header_recordings':header_members}
        self.objects['manifest']={'schema':'dosei_annotation_census_manifest_v1','full_scope_recordings':171,
            'total_expanded_bytes':sum(map(len,self.source.values())),'members':manifest_members}
        self.objects['cohort']={'schema':'dosei_complete_private_annotation_row_census_v1','status':'succeeded',
            'archive_sha256':self.protocol['archive_sha256'],'protocol_sha256':OLD_PROTOCOL,'complete_source_recordings':171,
            'totals':{'source_data_rows':513,'expanded_bytes_read':sum(map(len,self.source.values())),'protected_annotation_rows':342},
            'timestamp_issue_counts':{'duplicate_timestamp':1},'recordings':[self.summaries[rid] for rid in self.ids]}
        self.objects['census_supervisor']={'schema':'dosei_annotation_census_supervisor_receipt_v1','status':'succeeded',
            'complete_member_recordings':171,'protocol_sha256':OLD_PROTOCOL}
        self.refresh()

    def put(self,path,value):
        raw=value if isinstance(value,bytes) else encode(value);self.files[path]=raw
        return {'path':path,'bytes':len(raw),'sha256':digest(raw)}

    def refresh(self):
        for rid in self.ids:
            stem='/generated/census/recording-'+rid
            raw=self.ledgers[rid];self.files[stem+'.annotations.provisional.jsonl']=raw
            ledger={'path':stem+'.annotations.provisional.jsonl','bytes_successfully_written':len(raw),
                    'sha256_of_actual_retained_bytes':digest(raw),'complete_and_bound_to_member_census':True}
            report=self.put(stem+'.census.json',self.reports[rid]);receipt=self.receipts[rid]
            receipt['member_census_report']=report;receipt['annotation_ledger']=ledger
            self.summaries[rid].update(final_member_receipt=self.put(stem+'.receipt.json',receipt),
                member_census_report=report,annotation_ledger=ledger)
        for key in ('inventory','headers','manifest','cohort','census_supervisor'):
            obj=self.objects[key]
            if key=='headers':obj['source_inventory_sha256']=self.protocol['inventory_sha256']
            if key=='manifest':obj.update(source_inventory_sha256=self.protocol['inventory_sha256'],source_headers_sha256=self.protocol['headers_sha256'])
            if key=='cohort':obj['manifest_sha256']=self.protocol['manifest_sha256']
            if key=='census_supervisor':obj['cohort_report']={'path':self.protocol['cohort_path'],'sha256':self.protocol['cohort_sha256']}
            path='/generated/census/COHORT_ANNOTATION_CENSUS.json' if key=='cohort' else '/generated/'+key+'.json'
            binding=self.put(path,obj);self.protocol[key+'_path']=path;self.protocol[key+'_sha256']=binding['sha256']

class Writer:
    def __init__(self,ctx,name,cap,binary):self.ctx=ctx;self.name=name;self.cap=cap;self.binary=binary;self.raw=bytearray();self.closed=False
    def write(self,raw):
        assert not self.closed
        view=memoryview(raw).cast('B');assert len(self.raw)+len(view)<=self.cap
        if self.name==self.ctx.short_write:
            kept=max(0,len(view)-1);self.raw.extend(view[:kept]);return kept
        self.raw.extend(view);return len(view)
    def close(self):
        self.closed=True
        if self.name==self.ctx.close_failure:raise OSError('generated close failure')
    def binding(self):
        assert self.closed
        sha=digest(self.raw)
        if self.name==self.ctx.bad_binding:sha='0'*64
        return {'path':'/generated/output/'+self.name,'bytes':len(self.raw),'sha256':sha,'hash_scope':'generated memory only',
                'closed_file_signature':{'st_dev':1,'st_ino':1,'st_size':len(self.raw),'st_mtime_ns':1,'st_ctime_ns':1}}

class Context:
    def __init__(self,fixture):
        self.args=types.SimpleNamespace(protocol=Path('/generated/PROTOCOL.json'),protocol_sha256='c'*64)
        self.fixture=fixture;self.protocol=copy.deepcopy(fixture.protocol);self.reads=Counter();self.outputs={};self.json_values={}
        self.operations=[];self.archive_opens=0;self.member_entries=0;self.archive_exits=0
        self.short_write=self.close_failure=self.bad_binding=self.fail_json=None
        self.source_exit_failure=False;self.throw_boundary=None;self.boundary_calls=0
        self.modules={}
    def load_bytes(self,path,pin,cap,scientific=True):
        path=str(path);self.reads[path]+=1;raw=self.fixture.files[path]
        if len(raw)>cap or digest(raw)!=pin:raise ValueError('generated saved input pin/cap mismatch')
        return raw
    def load_json(self,path,pin,cap,scientific=True):return P.unique_json(self.load_bytes(path,pin,cap,scientific))
    def load_module(self,path,pin,name):
        assert name in ('numeric_policy','numeric_stream','annotation_events','inventory_guard')
        key=next(key for key,(expected,_) in MODULES.items() if expected==path)
        raw=CODE[key];assert digest(raw)==pin
        module=types.ModuleType(name);module.__file__=str(path);sys.modules[name]=module
        exec(compile(raw,str(path),'exec'),module.__dict__)
        if key=='zip_guard':module.SIZE=len(self.fixture.archive)
        self.modules[key]=module;return module
    @contextmanager
    def open_archive(self):
        self.archive_opens+=1;assert self.archive_opens==1
        source=io.BytesIO(self.fixture.archive)
        try:yield source
        finally:
            source.close();self.archive_exits+=1
            if self.source_exit_failure:raise ValueError('generated source descriptor changed on close')
    def writer(self,name,cap,binary=False):
        assert name not in self.outputs
        writer=Writer(self,name,cap,binary);self.outputs[name]=writer;self.operations.append(('writer',name));return writer
    def json(self,name,obj,cap,critical=False):
        raw=P.bounded_json(obj,cap)
        writer=self.writer(name,cap,False)
        if name==self.fail_json:
            writer.write(raw[:17]);writer.close();raise OSError('generated receipt write failure')
        writer.write(raw);writer.close();self.json_values[name]=copy.deepcopy(obj)
        self.operations.append(('json_complete',name));return writer.binding()
    @contextmanager
    def member_deadline(self):self.member_entries+=1;yield
    def check_boundary(self):
        self.boundary_calls+=1
        if self.boundary_calls==self.throw_boundary:raise TimeoutError('generated finite boundary')
    def resources(self):return {'generated_only':True,'known_written_output_bytes':sum(len(w.raw) for w in self.outputs.values())}

class ProducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.base=Fixture()
    def setUp(self):self.f=copy.deepcopy(self.base);self.ctx=Context(self.f)
    def run_success(self):
        with redirect_stdout(io.StringIO()):return P.produce(self.ctx)
    def run_failure(self):
        with redirect_stdout(io.StringIO()),self.assertRaises((ValueError,OSError,AssertionError,TimeoutError,zipfile.BadZipFile)):
            P.produce(self.ctx)
        self.assertNotIn('COHORT_SUCCESS.json',self.ctx.json_values)
        self.assertIn('COHORT_FAILURE.json',self.ctx.json_values)
    def test_complete171_single_source_pass_once_saved_reads_and_outputs(self):
        self.run_success();ctx=self.ctx;result=ctx.json_values['COHORT_SUCCESS.json']
        self.assertEqual((ctx.archive_opens,ctx.archive_exits,ctx.member_entries),(1,1,171))
        self.assertEqual(len(ctx.reads),5+171*3);self.assertEqual(set(ctx.reads.values()),{1})
        self.assertEqual(result['totals']['binary_bytes'],513*26)
        self.assertEqual(result['totals']['annotation_rows'],342)
        self.assertEqual(result['clock_issue_counts'],{'duplicate_timestamp':1})
        self.assertEqual(result['event_projection_counts']['source_supported_moaas_targets'],171)
        self.assertEqual(result['event_projection_counts']['source_supported_soc_transition_targets'],170)
        self.assertEqual(result['event_projection_counts']['retained_ungraded_source_marker'],1)
        self.assertEqual(ctx.operations[-1],('json_complete','COHORT_SUCCESS.json'))
        self.assertEqual(result['execution_binding']['protocol'],{'path':'/generated/PROTOCOL.json','sha256':'c'*64})
        self.assertEqual(set(result['saved_scientific_inputs']),{'cohort','census_supervisor','inventory','headers','manifest'})
        for rid in self.f.ids:
            receipt=ctx.json_values['recording-'+rid+'.success.json']
            self.assertEqual(receipt['execution_binding'],result['execution_binding'])
            self.assertEqual(receipt['saved_final_member_receipt'],self.f.summaries[rid]['final_member_receipt'])
            for name,binding in receipt['outputs'].items():
                out=ctx.outputs['recording-'+rid+'.'+P.STREAM_SUFFIXES[name]]
                self.assertTrue(out.closed);self.assertEqual(binding['sha256'],digest(out.raw))
            self.assertFalse(receipt['canonical_scoring_admitted'])
        clock=struct.unpack('<3q',ctx.outputs['recording-83.time.i64le.provisional'].raw)
        self.assertEqual(clock[1],clock[2]);self.assertEqual(clock[1]-clock[0],4)
        quality=bytes(ctx.outputs['recording-83.quality.u8.provisional'].raw)
        self.assertEqual(quality,bytes((0,1,2,16,32,8)))
        first=struct.unpack('<Q',ctx.outputs['recording-83.eeg.f64le.provisional'].raw[:8])[0]
        self.assertEqual(first,0x8000000000000000)
        events=[json.loads(line) for line in ctx.outputs['recording-84.annotation-events.jsonl.provisional'].raw.splitlines()]
        self.assertEqual(events[1]['original_fields']['Propofol'],'10.0');self.assertIsNone(events[1]['moaas_grouped_ordinal'])
    def test_saved_final_receipt_required_and_stops_before_later_member(self):
        self.f.receipts['84']['status']='incomplete';self.f.refresh();self.ctx=Context(self.f);self.run_failure()
        self.assertIn('recording-83.success.json',self.ctx.json_values)
        self.assertNotIn('recording-84.success.json',self.ctx.json_values)
        self.assertNotIn('recording-209.start.json',self.ctx.outputs)
        self.assertEqual(self.ctx.member_entries,2)
    def test_saved_ledger_hash_and_semantic_join_are_distinct_gates(self):
        rawpath='/generated/census/recording-83.annotations.provisional.jsonl'
        self.f.files[rawpath]+=b' ';self.run_failure();self.assertNotIn('recording-83.start.json',self.ctx.outputs)
        self.setUp();rows=copy.deepcopy(self.f.annotations['83']);rows[0]['original_fields']['MOAAS']='4.0'
        self.f.ledgers['83']=b''.join(encode(row) for row in rows);self.f.refresh();self.ctx=Context(self.f);self.run_failure()
        self.assertIn('recording-83.annotation-events.jsonl.provisional',self.ctx.outputs)
        self.assertNotIn('recording-83.success.json',self.ctx.json_values)
        projected=json.loads(self.ctx.outputs['recording-83.annotation-events.jsonl.provisional'].raw.splitlines()[0])
        self.assertIsNone(projected['moaas_grouped_ordinal'])
    def test_directory_complete_population_and_metadata_cannot_be_rebound(self):
        for mutate in ('missing','compressed','duplicate'):
            with self.subTest(mutate=mutate):
                self.setUp();members=self.f.objects['inventory']['members']
                if mutate=='missing':members.pop()
                elif mutate=='duplicate':members[-1]=copy.deepcopy(members[-2])
                else:members[1]['header_offset']+=1
                self.f.refresh();self.ctx=Context(self.f);self.run_failure();self.assertEqual(self.ctx.member_entries,0)
    def test_projection_short_write_close_and_binding_failure_preserve_partials(self):
        name='recording-83.eeg.f64le.provisional'
        for attribute in ('short_write','close_failure','bad_binding'):
            with self.subTest(attribute=attribute):
                self.setUp();setattr(self.ctx,attribute,name);self.run_failure()
                self.assertIn(name,self.ctx.outputs);self.assertGreater(len(self.ctx.outputs[name].raw),0)
                self.assertNotIn('recording-83.success.json',self.ctx.json_values)
                self.assertEqual(self.ctx.member_entries,1)
    def test_success_marker_write_failure_never_propagates_member_success(self):
        self.ctx.fail_json='recording-84.success.json';self.run_failure()
        self.assertIn('recording-84.success.json',self.ctx.outputs) # partial preserved, not a committed receipt
        self.assertNotIn('recording-84.success.json',self.ctx.json_values)
        self.assertEqual(len(self.ctx.json_values['COHORT_FAILURE.json']['completed_member_receipts']),1)
        self.assertNotIn('recording-209.start.json',self.ctx.outputs)
    def test_source_identity_finalization_and_cohort_receipt_write_failure(self):
        self.ctx.source_exit_failure=True;self.run_failure()
        self.assertEqual(len(self.ctx.json_values['COHORT_FAILURE.json']['completed_member_receipts']),171)
        self.setUp();self.ctx.fail_json='COHORT_SUCCESS.json';self.run_failure()
        self.assertEqual(len(self.ctx.json_values['COHORT_FAILURE.json']['completed_member_receipts']),171)
        self.assertIn('COHORT_SUCCESS.json',self.ctx.outputs) # partial cannot be treated as successful parsed JSON
    def test_complete_ledger_shape_types_and_no_unknown_numeric_json(self):
        for change in ('extra','null','booltime','countbool'):
            with self.subTest(change=change):
                self.setUp();rows=copy.deepcopy(self.f.annotations['83'])
                if change=='extra':rows.append(rows[-1])
                if change=='null':rows[-1]=None
                if change=='booltime':rows[0]['recognized_time_ms']=True
                if change=='countbool':self.f.reports['83']['timestamp_audit']['issue_counts']={'duplicate_timestamp':True}
                self.f.ledgers['83']=b''.join(encode(row) for row in rows);self.f.refresh();self.ctx=Context(self.f);self.run_failure()
                self.assertNotIn('recording-83.success.json',self.ctx.json_values)
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):P.unique_json(raw)
    def test_boundary_failure_has_no_retry_and_bootstrap_unfrozen_fails_before_read(self):
        self.ctx.throw_boundary=4;self.run_failure();self.assertEqual(self.ctx.member_entries,1)
        self.assertNotIn('recording-84.start.json',self.ctx.outputs)
        if P.GUARDS_SHA256=='UNFROZEN_GUARD_REQUIRES_LEAD_PIN':
            args=types.SimpleNamespace()
            with self.assertRaises(ValueError):P.bootstrap_guards(args)
            self.assertFalse(hasattr(args,'bootstrap_operational_read_bytes'))

    def test_closed_output_stat_is_mandatory_and_exact(self):
        base={'path':'/generated/file','bytes':4,'sha256':digest(b'abcd'),
              'closed_file_signature':{'st_dev':1,'st_ino':2,'st_size':4,'st_mtime_ns':3,'st_ctime_ns':4}}
        self.assertEqual(P.checked_binding(types.SimpleNamespace(binding=lambda:base),None),base)
        for mutation in ('absent','size','bool','extra'):
            with self.subTest(mutation=mutation):
                bad=copy.deepcopy(base)
                if mutation=='absent':del bad['closed_file_signature']
                elif mutation=='size':bad['closed_file_signature']['st_size']=3
                elif mutation=='bool':bad['closed_file_signature']['st_dev']=True
                else:bad['closed_file_signature']['extra']=0
                with self.assertRaises(ValueError):P.checked_binding(types.SimpleNamespace(binding=lambda:bad),None)

    def test_reviewed_guard_bootstrap_only_and_wrong_hash_rejection(self):
        # Import only. GuardContext construction and native authority/source IO
        # are deliberately never invoked by this generated control.
        args=types.SimpleNamespace()
        module=P.bootstrap_guards(args)
        self.assertEqual(args.bootstrap_operational_read_bytes,(A/'eeg_guards.py').stat().st_size)
        self.assertEqual(module.__name__,'dosei_eeg_guards')
        self.assertTrue(callable(module.GuardContext))
        original=P.GUARDS_SHA256
        try:
            P.GUARDS_SHA256='0'*64
            with self.assertRaises(ValueError):P.bootstrap_guards(types.SimpleNamespace())
        finally:P.GUARDS_SHA256=original

if __name__=='__main__':unittest.main(verbosity=2)
