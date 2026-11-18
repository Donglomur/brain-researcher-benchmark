"""Generated small-cohort checks only; no authentic source/packet access."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect import Journal
from dependencies import load
from observations import ObservationAdapter
from session import ARMS, Study, SCORER, EDGES


def cases():
    return [{'case_id':f'synthetic-{row}-{region}', 'animal_id':'synthetic-animal',
             'asset_id':'synthetic-asset', 'region':region,'source_trial_row':row,
             'source_trial_id':row+100,'source_cluster_count':2,
             'trial_start_seconds':10.0+row,'trial_stop_seconds':10.01+row}
            for row in range(2) for region in ('MGd','MGv')]


def projection(roster, calls):
    visible = {case['case_id']:{k:v for k,v in case.items() if k in SCORER.CASE_FIELDS}
               for case in roster}
    def history(key, *, released_case_id):
        if key != released_case_id:
            raise AssertionError('Wrong release identity')
        calls.append(key)
        return {'case':copy.deepcopy(visible[key]), 'history_rates':[500.0]*100}
    return history


class MemoryJournal:
    def __init__(self):
        self.records=[]
        self.started=None
        self.sealed=None
    def start(self,v): self.started=copy.deepcopy(v)
    def commit(self,v):
        self.records.append(copy.deepcopy(v))
        return {'record_sha256':'a'*64}
    def seal(self,v):
        self.sealed=copy.deepcopy(v)
        return {'record_sha256':'b'*64}


def submission(request, value=-2.5):
    return {k:request[k] for k in ('condition_id','trial_token','payload_sha256')} | {
        'predictions':[{'case_id':row['case']['case_id'],'rates':[value]*100}
                       for row in request['payload']]}


def study(journal=None):
    roster,calls=cases(),[]
    journal=journal or MemoryJournal()
    result=Study(roster,projection(roster,calls),journal,study_id='synthetic-study',
                 procedure_hashes={ARMS[0]:'1'*64,ARMS[1]:'2'*64})
    return result,calls,journal


class SessionTests(unittest.TestCase):
    def test_lazy_pair_match_and_full_completion(self):
        s,calls,j=study()
        self.assertEqual(calls,[])
        for row in range(2):
            first=s.current()
            self.assertEqual(len(calls),2*(row+1))
            self.assertEqual(s.current(),first)
            s.submit(submission(first))
            second=s.current()
            self.assertEqual(first['payload'],second['payload'])
            self.assertEqual(first['payload_sha256'],second['payload_sha256'])
            self.assertEqual(len(calls),2*(row+1))
            s.submit(submission(second,10**308+1))
        final=s.finish()
        self.assertEqual(final['cases_per_arm'],{arm:4 for arm in ARMS})
        self.assertEqual(final['scores_computed'],0)
        self.assertEqual(j.records[1]['predictions'][0]['rates'][0],10**308+1)
        self.assertIs(type(j.records[1]['predictions'][0]['rates'][0]),int)
        with self.assertRaises(ValueError): s.current()

    def test_frozen_chronological_transition_parity(self):
        s,_,_=study()
        adapter=ObservationAdapter(cases(),projection(cases(),[]))
        eager=[o for key in adapter.keys() for o in adapter.observations(*key,view='timing_history')]
        module=load('condition')
        with patch.dict(sys.modules,{'scoring':SCORER}):
            q=module.ChronologicalQuery(eager,view='timing_history',edges_seconds=EDGES)
            while q.current() is not None:
                r=s.current()
                self.assertEqual(r['payload'],q.current())
                preds=submission(r)['predictions']
                s.submit(submission(r))
                s.submit(submission(s.current()))
                q.commit(preds)
            self.assertEqual(len(q.locked_predictions()),4)
            self.assertEqual(s.finish()['cases_per_arm'][ARMS[0]],4)

    def test_incomplete_pair_never_eligible(self):
        s,_,j=study()
        s.submit(submission(s.current()))
        with self.assertRaises(ValueError): s.finish()
        self.assertIsNone(j.sealed)

    def test_request_and_submission_mutation_cannot_modify_locked_state(self):
        s,_,j=study()
        r=s.current()
        r['payload'][0]['history_rates'][0]=999
        self.assertEqual(s.current()['payload'][0]['history_rates'][0],500.0)
        p=submission(s.current())
        s.submit(p)
        p['predictions'][0]['rates'][0]=999
        self.assertEqual(j.records[0]['predictions'][0]['rates'][0],-2.5)

    def test_stale_or_partial_submission_terminates_without_future_history(self):
        for change in ('partial','token','extra','nonfinite'):
            s,calls,j=study()
            p=submission(s.current())
            if change=='partial': p['predictions'].pop()
            if change=='token': p['trial_token']='bad'
            if change=='extra': p['response_rates']=[1]
            if change=='nonfinite': p['predictions'][0]['rates'][0]=float('nan')
            with self.assertRaises(ValueError): s.submit(p)
            with self.assertRaises(ValueError): s.current()
            self.assertEqual(len(calls),2)
            self.assertEqual(j.records,[])

    def test_cross_attempt_replay_cannot_be_relabelled_under_new_procedure(self):
        old,_,_=study()
        prior=submission(old.current())
        roster,calls=cases(),[]
        journal=MemoryJournal()
        new=Study(roster,projection(roster,calls),journal,study_id='synthetic-study',
                  procedure_hashes={ARMS[0]:'3'*64,ARMS[1]:'2'*64})
        request=new.current()
        self.assertEqual(request['payload_sha256'],prior['payload_sha256'])
        self.assertNotEqual(request['trial_token'],prior['trial_token'])
        with self.assertRaises(ValueError): new.submit(prior)
        self.assertEqual(journal.records,[])

    def test_durable_failure_never_advances(self):
        class Failing(MemoryJournal):
            def commit(self,v): raise OSError('synthetic write failure')
        s,calls,_=study(Failing())
        with self.assertRaises(OSError): s.submit(submission(s.current()))
        with self.assertRaises(ValueError): s.current()
        self.assertEqual(len(calls),2)

    def test_real_generated_journal_seals_and_refuses_reuse(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path=Path(tmp)/'synthetic-journal'
            j=Journal(path,max_total_bytes=32768,max_record_bytes=8192)
            s,_,_=study(j)
            for _ in range(4): s.submit(submission(s.current()))
            s.finish()
            self.assertEqual(len(list(path.iterdir())),6)
            seal=json.loads((path/'COMPLETE.json').read_text())
            self.assertEqual(seal['locked_records'],4)
            self.assertEqual((path.stat().st_mode & 0o777),0o700)
            self.assertTrue(all((f.stat().st_mode & 0o777)==0o600 for f in path.iterdir()))
            with self.assertRaises(FileExistsError):
                Journal(path,max_total_bytes=32768,max_record_bytes=8192)

    def test_parent_directory_sync_failure_prevents_start(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            parent_inode=Path(tmp).stat().st_ino
            original=os.fsync
            def fail_parent(fd):
                if os.fstat(fd).st_ino==parent_inode:
                    raise OSError('synthetic parent persistence failure')
                return original(fd)
            path=Path(tmp)/'synthetic-unsynced'
            with patch('collect.os.fsync',side_effect=fail_parent):
                with self.assertRaises(OSError):
                    Journal(path,max_total_bytes=32768,max_record_bytes=8192)
            self.assertEqual(list(path.iterdir()),[])

    def test_late_seal_sync_failure_never_returns_completion_receipt(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path=Path(tmp)/'synthetic-late-sync'
            j=Journal(path,max_total_bytes=32768,max_record_bytes=8192)
            s,_,_=study(j)
            for _ in range(4): s.submit(submission(s.current()))
            original=os.fsync
            def fail_completion(fd):
                marker=path/'COMPLETE.json'
                if marker.exists() and os.fstat(fd).st_ino==marker.stat().st_ino:
                    raise OSError('synthetic completion persistence failure')
                return original(fd)
            with patch('collect.os.fsync',side_effect=fail_completion):
                with self.assertRaises(OSError): s.finish()
            # A retained marker alone must never be accepted as a successful run.
            candidate=json.loads((path/'COMPLETE.json').read_text())
            self.assertTrue(candidate['requires_successful_operator_finish_receipt'])
            with self.assertRaises(ValueError): s.finish()
            with self.assertRaises(ValueError): s.current()

    def test_byte_budget_failure_retains_incomplete_no_seal(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path=Path(tmp)/'synthetic-budget'
            j=Journal(path,max_total_bytes=2048,max_record_bytes=2048)
            j.start({'generated':True})
            with self.assertRaises(ValueError): j.commit({'rates':[10**308+1]*100})
            with self.assertRaises(ValueError): j.seal({'complete':True})
            self.assertFalse((path/'COMPLETE.json').exists())


if __name__=='__main__': unittest.main()
