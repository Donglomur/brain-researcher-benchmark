"""Generated software controls, never empirical reconstruction evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import contract as c
import delivery as d


def rows():
    values = []
    for group in (0, 1):
        for index, time in enumerate((0.0, c.EDGES[1]*1000, 9000.0, 10000.0, None), 1):
            values.append(dict(mouse="control-animal", session="generated-session", trial_number=group*10+index,
                               success=1, optoProblem=0, wrongGrabFirst=0, optoTrial=group,
                               grabTimeC=time, liftTimeC=-1.0))
    return values


def independent(reference):
    keyed = c.index_trials(reference['trials'])
    return dict(schema='independent-opto-native-reference-v1', task_id=c.TASK, input_sha256=c.DATA_SHA,
                official_code_revision=c.REVISION, record_count=len(keyed), unique_keys=[list(k) for k in keyed],
                trial_outputs=copy.deepcopy(reference['trials']),
                selected_trial_keys={str(g): [list(k) for k,r in keyed.items() if r['selected'] and r['condition']==name]
                                     for g,name in ((0,'control'),(1,'opto'))},
                excluded_trial_keys=[list(k) for k,r in keyed.items() if not r['selected']],
                source_histogram_edges_seconds=c.EDGES, histograms=copy.deepcopy(reference['histograms']))


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.reference = c.reconstruct(rows())

    def test_native_values_edges_and_outside_denominator(self):
        h = self.reference['histograms']['control']
        self.assertEqual(h['selected_trials'], 4)
        self.assertEqual(h['counts'][0:2], [1,1])
        self.assertEqual(h['counts'][-1], 1)
        self.assertEqual(h['outside_display_window'], 1)
        self.assertAlmostEqual(sum(h['probability']), .75)
        self.assertEqual(self.reference['trials'][0]['contact_seconds'], 0)

    def test_all_exclusion_predicates_and_nan_bridge(self):
        values = rows()
        for i,field in enumerate(('success','optoProblem','wrongGrabFirst')):
            values[i][field] = 0 if field=='success' else 1
        values[3]['liftTimeC'] = values[3]['grabTimeC']
        values.extend([dict(values[5], trial_number=40, grabTimeC=4000)])
        # Keep one selected control observation so the report itself remains defined.
        values.append(dict(values[5], trial_number=41, optoTrial=0, grabTimeC=4000))
        result = c.reconstruct(values)
        self.assertEqual([r['selected'] for r in result['trials'][:5]], [False]*5)

    def test_exact_reconstruction_and_reordering(self):
        other = copy.deepcopy(self.reference)
        other['trials'].reverse()
        result = c.compare(self.reference, other)
        self.assertEqual(result['histogram_probability_rmse'], 0)
        self.assertEqual(result['contact_rmse_seconds'], 0)
        self.assertFalse(result['scientifically_qualified'])

    def test_missing_duplicate_extra_identity_rejected(self):
        for mutation in ('missing','duplicate','extra'):
            with self.subTest(mutation=mutation):
                other=copy.deepcopy(self.reference)
                if mutation=='missing': other['trials'].pop()
                elif mutation=='duplicate': other['trials'].append(other['trials'][0])
                else: other['trials'].append(dict(other['trials'][0], trial_number=999))
                with self.assertRaises(c.ContractError): c.compare(self.reference,other)

    def test_shifted_source_value_is_scored(self):
        other=copy.deepcopy(self.reference)
        for row in other['trials']:
            if row['selected']: row['contact_seconds'] += 1
        self.assertEqual(c.compare(self.reference,other)['contact_rmse_seconds'],1)

    def test_wrong_selection_and_condition_are_scored(self):
        other=copy.deepcopy(self.reference)
        # Swap group labels without changing complete populations or histogram arithmetic.
        for row in other['trials']: row['condition']='opto' if row['condition']=='control' else 'control'
        self.assertEqual(c.compare(self.reference,other)['condition_mismatches'],10)

    def test_inrange_renormalization_rejected(self):
        other=copy.deepcopy(self.reference)
        h=other['histograms']['control']; h['probability']=[x/3 for x in h['counts']]
        with self.assertRaises(c.ContractError): c.compare(self.reference,other)

    def test_source_edges_rejected(self):
        other=copy.deepcopy(self.reference);other['bin_edges_seconds'][-1]=10
        with self.assertRaises(c.ContractError): c.compare(self.reference,other)

    def test_boolean_count_and_nonfinite_rejected(self):
        for field,value in (('count',True),('contact',float('nan'))):
            other=copy.deepcopy(self.reference)
            if field=='count': other['histograms']['control']['counts'][0]=value
            else: other['trials'][0]['contact_seconds']=value
            with self.assertRaises(c.ContractError): c.compare(self.reference,other)

    def test_independent_check_covers_contact_and_excluded_condition(self):
        check=independent(self.reference); c.verify_independent(self.reference,check)
        check['trial_outputs'][0]['contact_seconds'] += 1
        with self.assertRaises(c.ContractError): c.verify_independent(self.reference,check)
        check=independent(self.reference);check['trial_outputs'][4]['condition']='opto'
        with self.assertRaises(c.ContractError): c.verify_independent(self.reference,check)

    def test_generated_reference_cannot_be_frozen_as_authentic(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);c.write_json(root/'draft.json',self.reference);c.write_json(root/'independent.json',independent(self.reference))
            with self.assertRaises(c.ContractError): d.freeze_reference(root/'draft.json',root/'independent.json',root/'freeze')
            self.assertFalse((root/'freeze').exists())

    def test_duplicate_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'test.json'
            for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
                path.write_text(raw)
                with self.assertRaises(c.ContractError): c.read_json(path)

    def test_self_authored_packet_and_code_contamination_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            packet=Path(temp);(packet/'optoData.mat').write_bytes(b'fake native data')
            manifest=dict(schema='opto-candidate-packet-v1',task_id=c.TASK,component=c.COMPONENT,
                          condition='paper_and_data',trials=3304,animals=2,sessions=8,
                          files={'optoData.mat':{'bytes':16,'sha256':c.digest(packet/'optoData.mat')}})
            c.write_json(packet/'packet.json',manifest)
            with self.assertRaises(c.ContractError): d.verify_packet(packet)
            manifest['files']['official-code/plotOptoHists.m']={'bytes':1,'sha256':'x'}
            c.write_json(packet/'packet.json',manifest)
            with self.assertRaises(c.ContractError): d.verify_packet(packet)

    def test_source_pin_rejects_changed_file_and_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'source';p.write_bytes(b'original')
            pin={'bytes':p.stat().st_size,'sha256':c.digest(p)}
            d.pin(p,pin);p.write_bytes(b'modified')
            with self.assertRaises(c.ContractError): d.pin(p,pin)
            link=Path(temp)/'link';link.symlink_to(p)
            with self.assertRaises(c.ContractError): d.pin(link,{'bytes':8,'sha256':c.digest(p)})

    def test_reference_tamper_rejected_before_scoring(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);c.write_json(root/'reference.json',self.reference)
            c.write_json(root/'freeze.json',{'schema':'opto-reference-freeze-v1','task_id':c.TASK,'reference_sha256':'0'*64})
            with self.assertRaisesRegex(c.ContractError,'reference tampering'): d.grade(root,root/'missing')


if __name__ == '__main__':
    unittest.main()
