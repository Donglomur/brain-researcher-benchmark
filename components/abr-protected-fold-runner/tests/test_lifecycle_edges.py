"""Targeted independent invented checks. No full author-suite replay."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time
import unittest
from unittest.mock import patch

D=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('abr_author_fixture',D/'tests/test_runner.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
# The author fixture installs the strict no-process/no-network audit hook.
c=a.c;f=a.f;owner=a.owner

class Independent(unittest.TestCase):
    def setUp(self):
        self.x=a.Controls();self.x.setUp()
    def tearDown(self):self.x.tearDown()

    def test_durable_barrier_failure_never_scores(self):
        write=c.write
        def failing(path,raw,budget,**kw):
            if Path(path).name=='ALL_104_PAIRED_COMMITTED.private.json':
                raise OSError('invented barrier publication failure')
            return write(path,raw,budget,**kw)
        with patch.object(c,'write',side_effect=failing):
            with self.assertRaisesRegex(OSError,'barrier publication'):
                self.x.execute()
        self.assertEqual(len(self.x.calls),10)
        self.x.assert_no_score()

    def test_pinned_animal_mutation_refused_before_transport(self):
        first=sorted((self.x.packet/'animals').iterdir())[0]
        os.chmod(first,0o600);first.write_bytes(first.read_bytes()+b' ');os.chmod(first,0o400)
        with self.assertRaisesRegex(ValueError,'bounded complete input extent'):
            self.x.execute()
        self.assertEqual(self.x.calls,[]);self.x.assert_no_score()

    def test_completion_manifest_join_before_transport(self):
        cp=self.x.selection['completion']
        value=c.decode(Path(cp['path']).read_bytes())
        value['private_manifest_sha256']='0'*64
        raw=c.encode(value)
        path=Path(cp['path']);os.chmod(path,0o600);path.write_bytes(raw);os.chmod(path,0o400)
        self.x.selection['completion']={'path':str(path),**c.pin(raw)}
        with self.assertRaisesRegex(ValueError,'preparation exact opaque operands'):
            self.x.execute()
        self.assertEqual(self.x.calls,[]);self.x.assert_no_score()

    def test_closed_failed_episode_is_preserved_without_metric(self):
        life={'episode_closed':True,'candidate_closed':False,'remaining_owned_cid':None,
              'publication_errors':[],'journal':{'closed':True,'persistence_errors':[]},
              'submission':None,'failed_episode_reason':'candidate_timeout'}
        pin=c.write(self.x.root/'failed-life.json',c.encode(life),self.x.budget)
        ep=owner.ClosedFailure(pin,'candidate_timeout',owner._FAILED_TOKEN)
        with self.assertRaisesRegex(ValueError,'complete campaign has no score'):
            f.freeze_closed(ep,self.x.root,self.x.budget)
        out=c.decode((self.x.root/'CLOSED_CANDIDATE_FAILURE.private.json').read_bytes())
        self.assertIsNone(out['metric']);self.assertFalse(out['all104_predictions_available'])

    def corrupt_submission(self,replacement,error):
        write=c.write;changed=[]
        def corrupt(path,raw,budget,**kw):
            if Path(path).name=='SUBMISSION.private.json' and not changed:
                self.assertIn(b'"p_6n":0.5',raw)
                raw=raw.replace(b'"p_6n":0.5',replacement,1);changed.append(True)
            return write(path,raw,budget,**kw)
        with patch.object(c,'write',side_effect=corrupt):
            with self.assertRaisesRegex(ValueError,error):self.x.execute()
        self.assertEqual(changed,[True]);self.assertEqual(len(self.x.calls),1)
        self.x.assert_no_score()

    def test_duplicate_json_key_refused_after_closed_capture(self):
        self.corrupt_submission(b'"p_6n":0.5,"p_6n":0.25','duplicate_json_key')

    def test_overflow_number_refused_after_closed_capture(self):
        self.corrupt_submission(b'"p_6n":1e999','finite probability')

    def test_render_does_not_open_packet_or_program_operands(self):
        request=self.x.render_request()
        absent=self.x.root/'deliberately-absent-packet'
        operands=request['operands']
        operands['packet_root']=str(absent)
        operands['completion']=dict(operands['completion'],path=str(absent/'evaluator/PACKET_COMPLETION.json'))
        operands['manifest']=dict(operands['manifest'],path=str(absent/'evaluator/PRIVATE_MANIFEST.json'))
        operands['preparation']=dict(operands['preparation'],path=str(absent/'evaluator/PREPARATION_RECEIPT.json'))
        for route,pin in operands['programs'].items():
            pin['path']=str(self.x.root/('absent-program-'+route+'.py'))
        result=a.provision.render(request)
        self.assertFalse(result['dispatch_performed'])
        self.assertFalse(absent.exists())
        self.assertFalse(Path(result['required_selection_path']).exists())
        cfg=c.decode((Path(request['package_root'])/'CONFIG.json').read_bytes())
        self.assertEqual(cfg['operands'],operands)

    def test_postscore_actor_and_second_score_are_forbidden(self):
        camp=a.fold_context.Campaign(self.x.manifest,'a'*64,'b'*64)
        for route in a.fold_context.ROUTES:
            for fold in range(5):
                cid=hashlib.sha256((route+str(fold)).encode()).hexdigest()
                camp.start(route,fold,cid)
                rows=[{'animal_id':x,'outer_fold':fold,'p_6n':0.5}
                      for x in self.x.manifest['folds'][fold]['test_animal_ids']]
                camp.commit_stopped(cid,rows,'c'*64)
        result=camp.evaluate()
        self.assertEqual(result['score']['animal_count'],104)
        with self.assertRaisesRegex(ValueError,'post-score adaptation'):
            camp.start('candidate',0,'f'*64)
        with self.assertRaisesRegex(ValueError,'all10 stopped-context'):
            camp.evaluate()

if __name__=='__main__':unittest.main(verbosity=2)
