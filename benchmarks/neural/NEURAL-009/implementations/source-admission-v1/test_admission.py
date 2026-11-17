"""Generated source-admission controls; no original EEG is read or scored."""
from __future__ import annotations
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('neural009_new_admission',HERE/'admission.py')
a=importlib.util.module_from_spec(spec); spec.loader.exec_module(a)


def edf(labels=('FP1-F7','ECG'), sample_counts=(4,2), records=2, duration='1', reserved=''):
    n=len(labels)
    def field(value,size):
        value=str(value).encode('ascii')
        assert len(value)<=size
        return value.ljust(size,b' ')
    fixed=(b'0       '+field('synthetic',80)+field('synthetic',80)+field('01.01.01',8)
           +field('00.00.00',8)+field(256+256*n,8)+field(reserved,44)+field(records,8)
           +field(duration,8)+field(n,4))
    parts=[]
    for width,values in ((16,labels),(80,['']*n),(8,['uV']*n),(8,[-100]*n),(8,[100]*n),
                         (8,[-32768]*n),(8,[32767]*n),(80,['']*n),(8,sample_counts),(32,['']*n)):
        parts.extend(field(v,width) for v in values)
    return fixed+b''.join(parts)+b'\0'*(2*records*sum(sample_counts))


class SummaryTests(unittest.TestCase):
    def test_explicit_zero_and_multiple_events(self):
        body=b'File Name: chb01_01.edf\nNumber of Seizures in File: 0\n\nFile Name: chb01_02.edf\nNumber of Seizures in File: 2\nSeizure 1 Start Time: 1 seconds\nSeizure 1 End Time: 4 seconds\nSeizure 2 Start Time: 8 seconds\nSeizure 2 End Time: 10 seconds\n'
        self.assertEqual(a.parse_summary(body,'chb01'),{'chb01/chb01_01.edf':[], 'chb01/chb01_02.edf':[[10,40],[80,100]]})
    def test_repeated_unnumbered_annotations(self):
        body=b'File Name: chb24_01.edf\nNumber of Seizures in File: 2\nSeizure Start Time: 1 seconds\nSeizure End Time: 2 seconds\nSeizure Start Time: 4 seconds\nSeizure End Time: 6 seconds\n'
        self.assertEqual(a.parse_summary(body,'chb24')['chb24/chb24_01.edf'],[[10,20],[40,60]])
    def test_summary_refusals(self):
        valid='File Name: chb01_01.edf\nNumber of Seizures in File: 1\nSeizure Start Time: 1 seconds\nSeizure End Time: 2 seconds\n'
        failures=[valid.replace('File: 1','File: 0'),valid+valid,valid.replace('1 seconds','3 seconds'),valid.replace('End Time','Unknown Time'),valid.replace('Seizure End Time: 2 seconds\n',''),valid.replace('Number of Seizures in File: 1\n',''),valid.replace('chb01_01.edf','../secret.edf'),valid.replace('Start Time: 1','Start Time: 1.5')]
        for body in failures:
            with self.subTest(body=body),self.assertRaises(ValueError): a.parse_summary(body.encode(),'chb01')


class EDFTests(unittest.TestCase):
    def test_exact_geometry_and_duplicate_labels(self):
        body=edf(labels=('FP1-F7','FP1-F7'),sample_counts=(4,4),records=3,duration='.5')
        h=a.parse_edf_header(body[:768],len(body))
        self.assertEqual(h['observed_ticks'],15)
        self.assertEqual(h['record_duration'],Fraction(1,2))
        self.assertEqual(h['samples_per_record'],[4,4])
        self.assertEqual(h['labels'],['FP1-F7','FP1-F7'])
    def test_header_refusals(self):
        body=edf()
        fixtures=[(body[:256],len(body)),(body[:768],len(body)-1),(body[:768],len(body)+1),
                  (edf(reserved='EDF+D')[:768],len(body)),(edf(duration='0')[:768],len(body)),
                  (edf(duration='0.01')[:768],len(body))]
        for h,n in fixtures:
            with self.subTest(n=n,h=h[:8]),self.assertRaises(ValueError):a.parse_edf_header(h,n)
    def test_stream_hash_and_byte_cap(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp).resolve()/'x.edf'; body=edf();p.write_bytes(body)
            geometry,size,_=a.inspect_edf(p,a.digest(body),len(body))
            self.assertEqual((size,geometry['observed_ticks']),(len(body),20))
            for sha,cap in [('0'*64,len(body)),(a.digest(body),len(body)-1)]:
                with self.assertRaises(ValueError):a.inspect_edf(p,sha,cap)
    def test_symlink_hardlink_and_fifo_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();p=root/'x';body=edf();p.write_bytes(body)
            link=root/'link';link.symlink_to(p)
            with self.assertRaises(ValueError):a.inspect_edf(link,a.digest(body),len(body))
            link.unlink();os.link(p,link)
            with self.assertRaises(ValueError):a.inspect_edf(p,a.digest(body),len(body))
            link.unlink();fifo=root/'fifo';os.mkfifo(fifo)
            with self.assertRaises(ValueError):a.read_bytes(fifo,1024)
    def test_changed_file_snapshot_refused(self):
        class Info:
            st_dev=1;st_ino=2;st_size=3;st_mtime_ns=4;st_ctime_ns=5
        before=Info();after=Info();after.st_mtime_ns=6
        with self.assertRaises(ValueError):a.stable(before,after)
    def test_oversized_json_cap_does_not_overflow_read(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp).resolve()/'x';p.write_bytes(b'{}')
            self.assertEqual(a.read_bytes(p,2**53-1),b'{}')


class CompleteAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name).resolve()
        cls.core=a.load_core(); original,cls.people,_=cls.core.source_index()
        cls.body=edf();header_sha=a.digest(cls.body[:768]);body_sha=a.digest(cls.body)
        cls.index=copy.deepcopy(original)
        for row in cls.index.values(): row['publisher_sha256']=body_sha
        cls.index_sha=a.digest(a.canonical(cls.index))
        cls.core.source_index=lambda:(cls.index,cls.people,cls.index_sha)
        cls.review={'schema':'neural009_source_review_v1','source_index_sha256':cls.index_sha,
                    'normalization_recipe_sha256':'1'*64,'clock_review_sha256':'2'*64,'rights_review_sha256':'3'*64,
                    'accept_annotation_source_assumptions':True,'records':[]}
        sums={}
        for name in cls.index:
            p=cls.root/name;p.parent.mkdir(exist_ok=True);p.write_bytes(cls.body);sums[name]=body_sha
            cls.review['records'].append({'recording_id':name,'edf_header_sha256':header_sha,
                'channels':[{'label':'FP1-F7','role':'eeg'},{'label':'ECG','role':'other'}],'predictor_channels':[0]})
        for folder in sorted({r['case_folder'] for r in cls.index.values()}):
            lines=[]
            for name in cls.index:
                if not name.startswith(folder+'/') or name in a.MISSING_SUMMARIES:continue
                positive=name=='chb07/chb07_19.edf'
                lines.extend(['File Name: '+name.split('/')[1],'Number of Seizures in File: '+str(int(positive))])
                if positive:lines.extend(['Seizure Start Time: 0 seconds','Seizure End Time: 1 seconds'])
            body=('\n'.join(lines)+'\n').encode();name=folder+'/'+folder+'-summary.txt'
            (cls.root/name).write_bytes(body);sums[name]=a.digest(body)
        sums['chb07/chb07_19.edf.seizures']='4'*64
        records=('\n'.join(cls.index)+'\n').encode();(cls.root/'RECORDS').write_bytes(records)
        positive=b'chb07/chb07_18.edf\n\n';(cls.root/'RECORDS-WITH-SEIZURES').write_bytes(positive)
        checksum=('\n'.join(sha+' '+name for name,sha in sums.items())+'\n').encode()
        (cls.root/'SHA256SUMS.txt').write_bytes(checksum)
        cls.patchers=[mock.patch.object(a,'CHECKSUMS_SHA256',a.digest(checksum)),mock.patch.object(a,'RECORDS_SHA256',a.digest(records)),mock.patch.object(a,'POSITIVE_LIST_SHA256',a.digest(positive))]
        for patch in cls.patchers:patch.start()
        cls.limits={'max_record_ticks':20,'max_total_ticks':686*20,'max_prediction_segments':686}
    @classmethod
    def tearDownClass(cls):
        for patch in reversed(cls.patchers):patch.stop()
        cls.temp.cleanup()
    def build(self,review=None,**kwargs):
        return a.build(self.core,self.root,review or self.review,self.limits,max_edf_bytes=kwargs.get('per',len(self.body)),max_total_edf_bytes=kwargs.get('total',686*len(self.body)))
    def test_full_686_record_admission_and_private_projection(self):
        outputs=self.build();adm=outputs['admission.json'];support=outputs['public-support.json'];proof=outputs['private-source-evidence.json']
        self.assertEqual(len(adm['records']),686);self.assertEqual(len(adm['folds']),23)
        alias=next(r for r in adm['records'] if r['recording_id'].startswith('chb21/'))
        self.assertEqual(alias['biological_person'],'chb01')
        fold=next(f for f in adm['folds'] if f['id']=='chb01')
        self.assertNotIn('chb01',fold['train_people']);self.assertNotIn('chb21',fold['train_people'])
        self.assertEqual(proof['inferred_zero_recordings'],list(a.MISSING_SUMMARIES))
        self.assertEqual(proof['complete_edf_bytes_authenticated'],686*len(self.body))
        for row in support['records']:
            self.assertNotIn('reference_intervals',row);self.assertNotIn('annotation_sha256',row);self.assertNotIn('annotation_status',row)
        self.assertFalse(proof['normalization_executed']);self.assertFalse(proof['scientific_qualification'])
        self.assertEqual(proof['positive_list_only'],['chb07/chb07_18.edf'])
        self.assertEqual(proof['summary_sidecar_only'],['chb07/chb07_19.edf'])
    def test_exact_total_and_record_byte_limits(self):
        for kw in ({'per':len(self.body)-1},{'total':686*len(self.body)-1}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):self.build(**kw)
    def test_missing_or_duplicate_review_refused_before_edf(self):
        for mutate in (lambda x:x['records'].pop(),lambda x:x['records'].__setitem__(0,x['records'][1])):
            review=copy.deepcopy(self.review);mutate(review)
            with mock.patch.object(a,'inspect_edf',side_effect=AssertionError('EDF should not open')),self.assertRaises(ValueError):self.build(review)
    def test_unreviewed_negative_assumption_refused(self):
        review=copy.deepcopy(self.review);review['accept_annotation_source_assumptions']=False
        with self.assertRaises(ValueError):self.build(review)
    def test_invalid_scorer_limits_refused_before_source_read(self):
        for limits in ({},dict(self.limits,max_total_ticks=0),dict(self.limits,max_record_ticks=True)):
            with self.subTest(limits=limits),mock.patch.object(a,'metadata',side_effect=AssertionError('No source read')),self.assertRaises(ValueError):
                a.build(self.core,self.root,self.review,limits,max_edf_bytes=1,max_total_edf_bytes=1)
    def test_scorer_support_budget_stops_before_next_edf(self):
        limits=dict(self.limits,max_total_ticks=19)
        with mock.patch.object(a,'inspect_edf',wraps=a.inspect_edf) as reader,self.assertRaisesRegex(ValueError,'total scorer support'):
            a.build(self.core,self.root,self.review,limits,max_edf_bytes=len(self.body),max_total_edf_bytes=686*len(self.body))
        self.assertEqual(reader.call_count,1)
    def test_annotation_and_other_channels_cannot_be_predictors(self):
        for role in ('annotation','other'):
            review=copy.deepcopy(self.review);review['records'][0]['channels'][0]['role']=role
            with self.subTest(role=role),self.assertRaises(ValueError):self.build(review)
    def test_edf_annotations_cannot_be_relabelled_eeg(self):
        review=copy.deepcopy(self.review);review['records'][0]['channels'][0]['label']='EDF Annotations'
        with mock.patch.object(a,'inspect_edf',side_effect=AssertionError('EDF should not open')),self.assertRaisesRegex(ValueError,'non-EEG role'):
            self.build(review)
    def test_reviewed_header_and_channel_order_bound(self):
        for edit in ('header','channel'):
            review=copy.deepcopy(self.review)
            if edit=='header':review['records'][0]['edf_header_sha256']='0'*64
            else:review['records'][0]['channels'].reverse();review['records'][0]['predictor_channels']=[1]
            with self.subTest(edit=edit),self.assertRaises(ValueError):self.build(review)
    def test_incomplete_metadata_or_wrong_publisher_refused(self):
        path=self.root/'chb01/chb01-summary.txt';body=path.read_bytes()
        try:
            path.write_bytes(body+b' ')
            with mock.patch.object(a,'inspect_edf',side_effect=AssertionError('EDF should not open')),self.assertRaises(ValueError):self.build()
        finally:path.write_bytes(body)
    def test_unreviewed_missing_summary_set_refused(self):
        with mock.patch.object(a,'MISSING_SUMMARIES',a.MISSING_SUMMARIES[:-1]),self.assertRaises(ValueError):self.build()
    def test_sidecar_positive_set_must_match_summary(self):
        with mock.patch.object(a,'checksums',wraps=a.checksums) as original:
            actual=a.checksums((self.root/'SHA256SUMS.txt').read_bytes())
            actual['chb01/chb01_01.edf.seizures']='4'*64
            original.side_effect=lambda _:actual
            with self.assertRaisesRegex(ValueError,'sidecar inventory'):self.build()
    def test_all_686_source_files_required(self):
        name=next(reversed(self.index));path=self.root/name;body=path.read_bytes();path.unlink()
        try:
            with self.assertRaises(FileNotFoundError):self.build()
        finally:path.write_bytes(body)
    def test_full_outputs_owner_only_and_no_clobber(self):
        outputs=self.build();target=self.root/'output';pins=a.write_outputs(target,outputs,2**22)
        self.assertEqual(set(pins),{'admission.json','public-support.json','private-source-evidence.json'})
        self.assertEqual(target.stat().st_mode&0o777,0o700)
        for name in pins:self.assertEqual((target/name).stat().st_mode&0o777,0o600)
        with self.assertRaises(ValueError):a.write_outputs(target,outputs,2**22)
        refused=self.root/'too-small'
        with self.assertRaises(ValueError):a.write_outputs(refused,outputs,1)
        self.assertFalse(refused.exists())
    def test_candidate_labels_do_not_enter_public_support(self):
        outputs=self.build();adm=outputs['admission.json'];before=self.core.public_support(adm)
        altered=copy.deepcopy(adm)
        altered['records'][0]['reference_intervals']=[[0,10]]
        altered['records'][0]['annotation_status']='explicit_events'
        altered['records'][0]['annotation_sha256']='f'*64
        self.assertEqual(before,self.core.public_support(altered))


class CLITests(unittest.TestCase):
    def test_duplicate_json_keys_and_nan_refused(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}'):
            with self.assertRaises(ValueError):a.json_bytes(raw)
    def test_unsafe_members_refused(self):
        for name in ('../a','/a','a//b','a/./b','a/../b'):
            with self.assertRaises(ValueError):a.safe_member(HERE,name)
    def test_missing_build_inputs_refused_before_edf(self):
        with tempfile.TemporaryDirectory() as temp,mock.patch.object(a,'inspect_edf',side_effect=AssertionError('No EDF allowed')):
            code=a.main(['build','--source-root',temp,'--output',temp+'/out','--max-json-bytes','100','--max-output-bytes','100'])
            self.assertEqual(code,2);self.assertFalse((Path(temp)/'out').exists())


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() and result.testsRun==27 and not result.skipped and not result.expectedFailures else 1)
