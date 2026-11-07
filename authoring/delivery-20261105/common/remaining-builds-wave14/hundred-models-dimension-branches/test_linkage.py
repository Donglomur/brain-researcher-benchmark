"""Small real compiler/linkage and catalog-geometry controls, invented only."""
from dataclasses import replace
import unittest

from hundred_models_dimensions import operations as o, linkage as link
from hundred_models_dimensions import program as p
import test_program as t

BUDGET=None  # The explicit runner binds one shared cumulative prospective cap.


class LinkageControls(unittest.TestCase):
    def test_model_and_brain_linkage_exact_axes_and_digest_conventions(self):
        budget=BUDGET
        ids=o.TEST_STIMULI
        stimuli=o.StimulusSupport(ids,o.canonical_digest(ids,budget),t.DUMMY['sha256'])
        shapes=(o.LayerShape('first',(200,)),o.LayerShape('last',(200,)))
        files=tuple(o.FeatureFile(identity+'.npz',identity,shapes) for identity in ids)
        support=o.FeatureSupport('AlexNet',stimuli,('first','last'),files,t.DUMMY['sha256'])
        contract=o.compile_model_contract(o.TEST_SPLIT,support,o.literal_script_pca(),budget=budget)
        record=link.model_condition_link(contract,'models_pca_rerun',('first','last'),t.DUMMY,t.DUMMY,budget=budget)
        self.assertEqual(record['producer_layer_order'],t.g.pin(t.g.encoded(('first','last'))))
        self.assertEqual(record['stimulus_order'],t.g.pin(t.g.encoded(ids)))
        self.assertEqual(record['operation_profile'],'literal_held_script_pca100_fit102')
        self.assertNotEqual(record['stimulus_order']['sha256'],stimuli.order_sha256) # newline is explicit
        with self.assertRaises(ValueError):link.model_condition_link(contract,'models',('first','last'),t.DUMMY,t.DUMMY,budget=budget)
        with self.assertRaises(ValueError):link.model_condition_link(contract,'models_pca_rerun',('absent',),t.DUMMY,t.DUMMY,budget=budget)
        records=tuple(o.BrainRecord(subject,roi,(102,10,2),stimuli.order_sha256,t.DUMMY['sha256'])
                      for subject in o.SUBJECTS for roi in o.ROIS)
        brain=o.compile_brain_contract(o.TEST_SPLIT,o.BrainSupport(stimuli,records,t.DUMMY['sha256']),budget=budget)
        shape={'bytes':1,'sha256':brain.input_metadata_sha256} # admitted invented declaration, no body proof
        output=link.brain_support_link(brain,shape,t.DUMMY,budget=budget)
        self.assertEqual((len(output['subjects']),len(output['rois'])),(10,17))
        self.assertFalse(output['average_external'])
        with self.assertRaises(ValueError):link.brain_support_link(brain,t.DUMMY,t.DUMMY,budget=budget)

    def test_catalog_known_modal_one_refuses_before_values(self):
        bound,_,_=t.binding('figure17')
        graph=t.g.strict(bound.graph_raw)
        for row in graph['models']:
            model=next(m for m in t.PROTOCOL['models'] if m['id']==row['model_id'])
            if not model['config'].get('layers'):
                row['named_modules']=['','first'];row['emitted_feature_keys']=['first']
        raw=t.g.encoded(graph)
        compiled=t.g.compile_catalog(t.P,t.I,raw,t.g.pin(raw),require_complete=False)
        run=t.g.strict(bound.run_raw)
        producer={row['model_id']:tuple(row['emitted_feature_keys']) for row in graph['models']}
        for row in run['conditions']:
            name=row['model'];row['layer_order']=t.g.pin(t.g.encoded(tuple(compiled['models'][name]['layers'])))
            row['producer_layer_order']=t.g.pin(t.g.encoded(producer[name]))
        run_raw=t.g.encoded(run)
        bad=replace(bound,graph_raw=raw,graph_pin=p._pin_tuple(t.g.pin(raw)),
                     run_raw=run_raw,run_pin=p._pin_tuple(t.g.pin(run_raw)))
        with self.assertRaisesRegex(ValueError,'modal depth one'):next(p.run_branch(bad,t.Never()))
