import copy
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluator as e


def fixture():
    """Generated controls; no empirical rows, neural recordings or source results."""
    sessions = []
    for s in range(2):
        trials = []
        for i in range(32):
            left = i % 2 == 0
            choice = 1 if (i // 2) % 2 == 0 else -1
            reward = 1 if (i // 4) % 2 == 0 else 0
            t = float(3 * i + 2)
            trials.append(dict(trial_id=i, source_mask=True, choice=choice,
                               probabilityLeft=.8 if i < 16 else .2, feedbackType=1 if reward else -1,
                               feedback_times=t+1, stimOn_times=t, firstMovement_times=t+.5,
                               contrastLeft=.5 if left else None, contrastRight=None if left else .5,
                               rewardVolume=reward))
        units = []
        for u in range(5):
            spikes = sorted([t['stimOn_times']+.025 for t in trials if t['contrastLeft'] is not None]
                            + [t['firstMovement_times']-.025 for t in trials if t['choice'] == 1]
                            + [t['feedback_times']+.025 for t in trials if t['rewardVolume'] > 0])
            units.append(dict(uuid=f'generated-unit-{s}-{u}', pid=f'generated-pid-{s}', region='VISp',
                              quality_label=1, gray_matter=True, spike_times=spikes))
        sessions.append(dict(eid=f'generated-eid-{s}', mouse_id=f'generated-mouse-{s}',
                             pids=[f'generated-pid-{s}'], trials=trials, expected_trial_count=len(trials),
                             units=units, expected_unit_uuids=[u['uuid'] for u in units]))
    return dict(schema_version=1, freeze=e.FREEZE, source_revision=e.SOURCE_REVISION,
                evidence_kind='generated_engineering', spike_sorting_revision='2024-05-06',
                trials_modified_before='2024-07-10', unit_version_evidence='generated; not source UUID-qualified',
                mask_provenance='generated all-true source mask', regions=['VISp'],
                roster=[dict(eid=s['eid'], mouse_id=s['mouse_id'], pids=s['pids']) for s in sessions], sessions=sessions)


class StatisticalControls(unittest.TestCase):
    def test_window_boundaries_and_zero_spikes(self):
        self.assertEqual(e.window_counts([0., .099, .1, 1., 1.099, 1.1], [0.,1.], 0., .1).tolist(), [2,2])
        self.assertEqual(e.window_counts([], [0.,1.], 0., .1).tolist(), [0,0])
        with self.assertRaises(ValueError): e.window_counts([1,0], [0], 0,1)

    def test_source_independent_directional_null_distribution(self):
        # Independently enumerate all six rank-subsets per direction: values are
        # U=0 (1/6), U=2 (4/6), U=4 (1/6). Min of independent draws has 11/36,24/36,1/36.
        ranks = [1.5,1.5,3.5,3.5]
        u = [sum(ranks[i] for i in pair)-3 for pair in itertools.combinations(range(4),2)]
        minima = [min(a,b) for a in u for b in u]
        self.assertEqual([minima.count(v) for v in [0,2,4]], [11,24,1])
        rng = np.random.RandomState(4)
        forward=e.directional_u(np.array([0,0]),np.array([1,1]),np.array([0,0]),np.array([0,0]),12000,rng)
        reverse=e.directional_u(np.array([1,1]),np.array([0,0]),np.array([0,0]),np.array([0,0]),12000,rng)
        draws=np.minimum(forward[1:],reverse[1:])
        self.assertAlmostEqual(np.mean(draws==0),11/36,delta=.015)
        self.assertAlmostEqual(np.mean(draws==4),1/36,delta=.008)

    def test_constant_ties_retain_source_average_rank(self):
        r=e.conditional_test([1]*6,[1,1,1,-1,-1,-1],[0]*6,[0]*6,3000,np.random.RandomState(2))
        self.assertEqual(r['statistic'],.5)
        self.assertEqual(r['p'],1501/3001)
        self.assertEqual(e.simple_test(np.array([1]*6),np.array([1,1,1,-1,-1,-1])),1.)

    def test_no_comparable_strata_is_explicit(self):
        r=e.conditional_test([0,1],[1,-1],[0,1],[0,0],9,np.random.RandomState(0))
        self.assertIsNone(r['p'])
        self.assertEqual(r['status'],'not_estimable')

    def test_block_isolation_prevents_exchange(self):
        r=e.conditional_test([0,0,10,10],[1,1,-1,-1],[0]*4,[0,0,1,1],9,np.random.RandomState(0))
        self.assertEqual(r['exchangeable_blocks'],0)
        self.assertEqual(r['p'],.55)

    def test_simpson_confound_removed(self):
        # Stratum 0 has mostly A and low counts, stratum 1 mostly B and high counts.
        counts=[0]*20+[10]*20
        labels=[1]*18+[-1]*2+[1]*2+[-1]*18
        r=e.conditional_test(counts,labels,[0]*20+[1]*20,[0]*40,99,np.random.RandomState(7))
        self.assertEqual(r['statistic'],.5)
        self.assertEqual(r['p'],.505)
        self.assertLess(e.simple_test(np.array(counts),np.array(labels)),.001)

    def test_bh_known_family(self):
        np.testing.assert_allclose(e.bh_adjust([.01,.04,.03]),[.03,.04,.04])


class PipelineControls(unittest.TestCase):
    def test_mask_and_profiles(self):
        packet=fixture(); trials=packet['sessions'][0]['trials']
        trials[0]['source_mask']=False
        trials[1]['firstMovement_times']=trials[1]['stimOn_times']+3
        trials[2]['feedback_times']=None
        self.assertEqual(e.trial_mask(trials)[:4].tolist(),[False,False,False,True])
        source=e.endpoint_design(trials[3:],'choice','pinned-examples')
        paper=e.endpoint_design(trials[3:],'choice','paper-choice-window-proposal')
        np.testing.assert_allclose(paper[0]-source[0],.5)

    def test_complete_pipeline_and_order_invariance(self):
        packet=fixture()
        result=e.evaluate(packet,profile='paper-choice-window-proposal',n_shuffles=199,n_bootstrap=99,seed=17)
        self.assertEqual(len(result['units']),30)
        self.assertTrue(all(row['sensitive'] for row in result['units']))
        source=e.evaluate(packet,profile='pinned-examples',n_shuffles=199,n_bootstrap=19,seed=17)
        self.assertTrue(all(not row['sensitive'] for row in source['units'] if row['endpoint']=='choice'))
        self.assertEqual(len(result['regions']),3)
        self.assertEqual(result['scientific_qualification'],'unknown')
        self.assertFalse(result['full_contract_complete'])
        self.assertEqual(result['regions'][0]['eligible_sessions'],2)
        packet['sessions'].reverse()
        for s in packet['sessions']:s['units'].reverse()
        changed=e.evaluate(packet,profile='paper-choice-window-proposal',n_shuffles=199,n_bootstrap=99,seed=17)
        self.assertEqual(result['units'],changed['units'])
        self.assertEqual(result['regions'],changed['regions'])
        json.dumps(result,allow_nan=False)

    def test_missing_population_and_wrong_pins_rejected(self):
        for mutation in ('session','unit','trial','revision','probe','uuid','contrast'):
            packet=fixture()
            if mutation=='contrast':del packet['sessions'][0]['trials'][0]['contrastLeft']
            if mutation=='session':packet['sessions'].pop()
            if mutation=='unit':packet['sessions'][0]['units'].pop()
            if mutation=='trial':packet['sessions'][0]['trials'].pop()
            if mutation=='revision':packet['spike_sorting_revision']='unknown'
            if mutation=='probe':packet['sessions'][0]['units'][0]['pid']='absent'
            if mutation=='uuid':packet['sessions'][1]['units'][0]['uuid']=packet['sessions'][0]['units'][0]['uuid']
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):e.validate_packet(packet)

    def test_minimum_three_error_trials_after_common_mask(self):
        packet=fixture()
        trials=packet['sessions'][0]['trials']
        errors=[i for i,t in enumerate(trials) if t['feedbackType']==-1]
        for i in errors[2:]:trials[i]['source_mask']=False
        result=e.evaluate(packet,profile='pinned-examples',n_shuffles=9,n_bootstrap=19)
        self.assertFalse(result['coverage'][0]['analysis_included'])
        self.assertEqual(result['coverage'][0]['error_trials_after_mask'],2)
        self.assertTrue(all(row['eid']!='generated-eid-0' for row in result['units']))
        self.assertTrue(all(row['status']=='insufficient_sessions' for row in result['regions']))

    def test_source_export_cannot_lower_shuffle_budget(self):
        packet=fixture();packet['evidence_kind']='unverified_local_export'
        with self.assertRaises(ValueError):e.evaluate(packet,profile='pinned-examples',n_shuffles=10)

    def test_probes_grouped_by_session_and_mouse_weighted(self):
        rows=[]
        # One mouse contributes two all-sensitive sessions, another contributes one zero session.
        for endpoint in e.ENDPOINTS:
            for s,k in [('a',5),('b',5),('c',0)]:
                for u in range(5):
                    rows.append(dict(region='VISp',endpoint=endpoint,eid=s,mouse_id='M1' if s!='c' else 'M2',sensitive=u<k))
        result=e.summarize(rows,['VISp'],99,2)
        self.assertAlmostEqual(result[0]['mean_session_fraction'],2/3)
        self.assertEqual(result[0]['prospective_mouse_summary']['mean'],.5)
        self.assertEqual(result[0]['prospective_mouse_summary']['n_mice'],2)
        self.assertEqual(len(result[0]['sessions']),3)
        self.assertLess(result[0]['source_session_fisher_p'],1e-30)

    def test_incomplete_region_family_withholds_bh(self):
        rows=[dict(region='A',endpoint=ep,eid=str(s),mouse_id=str(s),sensitive=False)
              for ep in e.ENDPOINTS for s in range(2) for _ in range(5)]
        result=e.summarize(rows,['A','B'],10,0)
        self.assertTrue(all(row['source_family_bh_q'] is None for row in result))

    def test_cli_generated_control(self):
        with tempfile.TemporaryDirectory() as tmp:
            inp,out=Path(tmp)/'in.json',Path(tmp)/'out.json'
            inp.write_text(json.dumps(fixture()))
            subprocess.run([sys.executable,str(Path(e.__file__)),'--input',str(inp),'--output',str(out),
                            '--profile','pinned-examples','--shuffles','9','--bootstrap','19'],check=True)
            result=json.loads(out.read_text())
            self.assertEqual(result['profile'],'pinned-examples')
            self.assertEqual(len(result['coverage']),2)


if __name__=='__main__':
    unittest.main()
