"""Complete-roster invented adapter controls, never authentic neural observations."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("portable_cerebellar_grade", ROOT / "grade.py")
grade = importlib.util.module_from_spec(spec); spec.loader.exec_module(grade)
science, roster = grade.load_sources(ROOT)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()


def pin(body):
    return {"bytes":len(body), "sha256":hashlib.sha256(body).hexdigest()}


def invented(identity):
    n = identity['trials']
    target = {'identity':identity,'curve':{'starts_index1':[1],'FP':[0.],'TP':[0.]},
              'selected_index1':1,'selected_trial_counts':[[0,0,0,0] for _ in range(n)]}
    if identity['figure'] == 'F3':
        target['timing'] = {'mean_silencing':[0.]*350, 'mean_peak_index1':1,
            'trial_peak_indices1':[1]*n, 'trial_flat_selected_window':[True]*n}
    return target, {'target':target,'trial_count_steps':[[[1,0,0,0,0]] for _ in range(n)]}


class PortableControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.root = Path(cls.tmp.name).resolve()
        cls.candidate = cls.root/'candidate'; cls.reference = cls.root/'reference'
        cls.candidate.mkdir(); cls.reference.mkdir()
        inventories = {cls.candidate:{}, cls.reference:{}}
        for identity in roster:
            name = grade.filename(identity)
            for folder, value in zip((cls.candidate,cls.reference),invented(identity)):
                raw=encode(value);(folder/name).write_bytes(raw);(folder/name).chmod(0o444)
                inventories[folder][name]=pin(raw)
        for folder in (cls.candidate,cls.reference):
            value={'schema':grade.CANDIDATE_SCHEMA if folder==cls.candidate else grade.REFERENCE_SCHEMA,
                'candidate_id':grade.TASK,'files':inventories[folder],
                'total_bytes':sum(x['bytes']for x in inventories[folder].values())}
            (folder/'COMMIT.json').write_bytes(encode(value));(folder/'COMMIT.json').chmod(0o444);folder.chmod(0o555)

    @classmethod
    def tearDownClass(cls):
        for folder in (cls.candidate,cls.reference): folder.chmod(0o755)
        cls.tmp.cleanup()

    def setUp(self): self.changed = {}

    def tearDown(self):
        for p, raw in self.changed.items():
            p.chmod(0o644);p.write_bytes(raw);p.chmod(0o444)

    def replace(self, p, value):
        if p not in self.changed:self.changed[p]=p.read_bytes()
        raw=encode(value);p.chmod(0o644);p.write_bytes(raw);p.chmod(0o444)
        if p.name!='COMMIT.json':
            commit=p.parent/'COMMIT.json'; manifest=json.loads(commit.read_bytes())
            manifest['files'][p.name]=pin(raw)
            manifest['total_bytes']=sum(x['bytes']for x in manifest['files'].values())
            self.replace(commit,manifest)

    def evaluate(self, reference=None, reference_pin=None, tick=lambda:None):
        return grade.evaluate(science,roster,self.candidate,pin((self.candidate/'COMMIT.json').read_bytes()),
            reference or self.reference,reference_pin or pin((self.reference/'COMMIT.json').read_bytes()),tick)

    def test_complete_roster_and_both_figure_endpoints(self):
        out=self.evaluate()
        self.assertEqual((out['status'],out['records_scored'],out['private_reference_records_loaded']),('scored',1020,1020))
        self.assertEqual(len(out['diagnostics']['F2']['rows']),1006)
        self.assertEqual(len(out['diagnostics']['F3']['rows']),14)
        for figure in ('F2','F3'):
            self.assertTrue(all(v==0 for v in out['summary']['figures'][figure]['equal_mouse_mean'].values()))
        first=self.candidate/grade.filename(roster[0]);value=json.loads(first.read_bytes())
        value['curve']={'starts_index1':[1,150001],'FP':[0.,0.],'TP':[0.,.5]};self.replace(first,value)
        last=self.candidate/grade.filename(roster[-1]);value=json.loads(last.read_bytes())
        value['timing']['trial_peak_indices1'][0]=2;self.replace(last,value)
        changed=self.evaluate();self.assertEqual(changed['status'],'scored')
        f2=changed['summary']['figures']['F2'];f3=changed['summary']['figures']['F3']
        self.assertAlmostEqual(f2['equal_mouse_mean']['TP_MAE'],.5/150001/131/7,places=15)
        self.assertAlmostEqual(f3['equal_mouse_mean']['trial_timing_MAE_ms'],10/66/2/7,places=15)
        columns=changed['diagnostics']['F3']['columns']
        self.assertAlmostEqual(changed['diagnostics']['F3']['rows'][-1][columns.index('trial_timing_MAE_ms')],10/66)
        self.assertNotEqual(out['ordered_record_scores_sha256'],changed['ordered_record_scores_sha256'])

    def test_invalid_last_record_precedes_every_private_read(self):
        p=self.candidate/grade.filename(roster[-1]);value=json.loads(p.read_bytes())
        value['timing']['trial_peak_indices1'].pop();self.replace(p,value)
        out=self.evaluate(self.root/'reference-does-not-exist')
        self.assertEqual((out['status'],out['records_scored'],out['private_reference_records_loaded']),('invalid_submission',0,0))
        self.assertEqual(out['record'],p.name)

    def test_missing_inventory_record_precedes_private(self):
        p=self.candidate/'COMMIT.json';value=json.loads(p.read_bytes());value['files'].pop(grade.filename(roster[-1]));self.replace(p,value)
        out=self.evaluate(self.root/'absent')
        self.assertEqual((out['status'],out['private_reference_records_loaded']),('invalid_submission',0))

    def test_short_reference_series_is_operator_error(self):
        p=self.reference/grade.filename(roster[0]);value=json.loads(p.read_bytes());value['trial_count_steps'].pop();self.replace(p,value)
        out=self.evaluate()
        self.assertEqual((out['status'],out['records_scored'],out['private_reference_records_loaded']),('operator_error',0,1))
        self.assertIsNone(out['partial_score'])

    def test_all_private_step_invariants(self):
        identity=roster[0];_,reference=invented(identity)
        mutations=[lambda x:x['trial_count_steps'][0].__setitem__(0,[2,0,0,0,0]),
            lambda x:x['trial_count_steps'][0].append([1,0,0,0,0]),
            lambda x:x['trial_count_steps'][0].__setitem__(0,[True,0,0,0,0]),
            lambda x:x['trial_count_steps'][0].__setitem__(0,[1,1,0,1,1]),
            lambda x:x['trial_count_steps'][0].append([150002,0,0,0,0]),
            lambda x:x['trial_count_steps'][0].__setitem__(0,[1,1,1,0,0])]
        for mutate in mutations:
            value=copy.deepcopy(reference);mutate(value)
            with self.assertRaises(ValueError):grade.validate_reference(science,value,identity)

    def test_reference_commitment_pin_refusal(self):
        out=self.evaluate(reference_pin={'bytes':(self.reference/'COMMIT.json').stat().st_size,'sha256':'0'*64})
        self.assertEqual((out['status'],out['private_reference_records_loaded']),('operator_error',0))

    def test_candidate_snapshot_change_after_prevalidation(self):
        target=self.candidate/grade.filename(roster[0]);original=grade.read_file;count=0
        def changed(path,*args,**kwargs):
            nonlocal count
            if Path(path)==target:
                count+=1
                if count==2:
                    if target not in self.changed:self.changed[target]=target.read_bytes()
                    target.chmod(0o644);target.write_bytes(target.read_bytes()+b' ');target.chmod(0o444)
            return original(path,*args,**kwargs)
        with patch.object(grade,'read_file',side_effect=changed):out=self.evaluate()
        self.assertEqual((out['status'],out['records_scored'],out['private_reference_records_loaded']),('invalid_submission',0,0))

    def test_unrepresentable_loss_has_no_partial_score(self):
        identity=roster[1006];name=grade.filename(identity)
        c=json.loads((self.candidate/name).read_bytes());c['timing']['mean_silencing']=[-1e308]*350
        ref=json.loads((self.reference/name).read_bytes());ref['target']['timing']['mean_silencing']=[1e308]*350
        self.replace(self.candidate/name,c);self.replace(self.reference/name,ref)
        out=self.evaluate();self.assertEqual(out['status'],'invalid_submission')
        self.assertEqual(out['records_scored'],1006);self.assertIsNone(out['partial_score'])
        self.assertNotIn('summary',out)

    def test_special_files_and_exclusive_report(self):
        folder=self.root/'io';folder.mkdir()
        fifo=folder/'fifo';os.mkfifo(fifo)
        with patch.object(grade.os,'open',side_effect=AssertionError('FIFO must refuse before open')):
            with self.assertRaises(ValueError):grade.read_file(fifo,10)
        leaf=folder/'leaf';leaf.write_bytes(b'1');leaf.chmod(0o444)
        alias=folder/'alias';alias.symlink_to(leaf)
        with self.assertRaises(ValueError):grade.read_file(alias,10)
        link=folder/'hardlink';os.link(leaf,link)
        with self.assertRaises(ValueError):grade.read_file(leaf,10)
        output=folder/'score.json';grade.write_report(output,{'status':'invented'})
        raw=output.read_bytes()
        with self.assertRaises(FileExistsError):grade.write_report(output,{'status':'changed'})
        self.assertEqual(output.read_bytes(),raw)
        with self.assertRaises(ValueError):grade.write_report(folder/'oversize.json',{'x':'x'*1000000})
        self.assertFalse((folder/'oversize.json').exists())

    def test_relocated_real_cli_and_source_pin(self):
        folder=self.root/'portable';folder.mkdir()
        for name in ('science.py','ROSTER.json','grade.py'):shutil.copyfile(ROOT/name,folder/name)
        output=self.root/'real-cli.json';cp=pin((self.candidate/'COMMIT.json').read_bytes());rp=pin((self.reference/'COMMIT.json').read_bytes())
        command=[sys.executable,'-I','-S','-B',str(folder/'grade.py'),'--candidate-dir',str(self.candidate),
            '--candidate-bytes',str(cp['bytes']),'--candidate-sha256',cp['sha256'],'--reference-dir',str(self.reference),
            '--reference-bytes',str(rp['bytes']),'--reference-sha256',rp['sha256'],'--seconds','10','--output',str(output)]
        result=subprocess.run(command,cwd=self.root,capture_output=True,timeout=12)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(output.read_bytes())['records_scored'],1020)
        with (folder/'science.py').open('ab')as stream:stream.write(b'\n')
        with self.assertRaises(ValueError):grade.load_sources(folder)

    def test_deadline_is_not_candidate_failure(self):
        def expired():raise TimeoutError('invented clock cutoff')
        with self.assertRaises(TimeoutError):self.evaluate(tick=expired)


if __name__=='__main__':unittest.main(verbosity=2)
