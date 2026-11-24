import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
W = HERE.parent
spec = importlib.util.spec_from_file_location('reference_rescore_generated_controls', HERE/'reference_rescore.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

def pin(path):
    body = path.read_bytes()
    return {'path': str(path), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

g = r.load_module('umbrae_generated_grounding', pin(W/'initial-evaluator-v1/grounding.py'))
a = r.load_module('umbrae_generated_alignment', pin(W/'endpoint-vector-v2/source_alignment.py'))

class CompleteReferenceRouteControls(unittest.TestCase):
    def test_pinned_input_mutation_and_duplicate_keys_refused(self):
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            p=Path(d)/'generated.json';p.write_text('{"x":1}')
            bound=pin(p);p.write_text('{"x":2}')
            with self.assertRaisesRegex(ValueError, 'pin mismatch'): r.pinned_json(bound)
            p.write_text('{"x":1,"x":2}')
            with self.assertRaisesRegex(ValueError, 'duplicate'): r.pinned_json(pin(p))

    def test_symlink_input_refused(self):
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            p=Path(d)/'generated.json';p.write_text('{}')
            link=Path(d)/'alias.json';link.symlink_to(p)
            bound=pin(p);bound['path']=str(link)
            with self.assertRaisesRegex(ValueError, 'resolved input path'):
                r.pinned_json(bound)

    def test_review_missing_answers_fixed_denominator_and_source_behavior(self):
        ann={'0':{'person':[[0.,0.,1.,1.]], 'car':[[0.,0.,.5,.5]]},
             '1':{'person':[[0.,0.,1.,1.]]}}
        # Missing a category is admitted without changing the target support.
        partial={'0':{'person':[[[0.,0.,1.,1.]]]},'1':{'person':[]}}
        r.validate_response_membership(partial,ann)
        targets,_=r.validate_annotation(ann,g,paper=False)
        rows=g.score_subject(targets,set(ann),partial)
        self.assertEqual(len(rows),3)
        self.assertEqual(sum(row['prediction_status']=='missing' for row in rows),1)
        self.assertEqual(g.summarize(rows)['All']['accuracy']['0.5'],1/3)
        pred,target=r.source_lists(ann,partial,['person','car'],a)
        self.assertEqual((len(pred),len(target)),(2,3))
        # Source's original zip truncation is preserved; neither list is padded.
        self.assertEqual(len(list(zip(pred,target))),2)
        no_image={'0':partial['0']}
        r.validate_response_membership(no_image,ann)
        self.assertEqual(len(g.score_subject(targets,set(ann),no_image)),3)
        with self.assertRaisesRegex(ValueError,'image-list length assertion'):
            r.source_lists(ann,no_image,['person','car'],a)
        with self.assertRaisesRegex(ValueError,'unknown response image'):
            r.validate_response_membership({'2':{}},ann)
        with self.assertRaisesRegex(ValueError,'unknown response category'):
            r.validate_response_membership({'0':{'dog':[]}},ann)

    def test_annotation_first_box_and_index_only_scope(self):
        ann={'0':{'person':[[0.,0.,1.,1.],[.2,.2,.4,.4]]}}
        targets, meta=r.validate_annotation(ann,g,paper=False)
        self.assertEqual(targets[('0','person')],(0.,0.,1.,1.))
        self.assertEqual(meta['boxes'],2)
        self.assertFalse(meta['NSD_COCO_stimulus_join_authenticated'])
        with self.assertRaisesRegex(ValueError, 'complete original'):
            r.validate_annotation(ann,g,paper=True)

    def test_original_source_order_diagnostic_not_repaired(self):
        ann={'0':{'person':[[0.,0.,1.,1.]]},'1':{'person':[[.1,.1,.2,.2]]}}
        response={'1':{'person':[[[.1,.1,.2,.2]]]},'0':{'person':[[[0.,0.,1.,1.]]]}}
        groups={name:list(g.GROUPS[local]) for name,local in a.GROUP_NAMES.items()}
        audit=a.audit_subject(ann,response,groups)
        self.assertEqual(audit['groups']['All']['wrong_image_pairs'],2)
        pred,target=r.source_lists(ann,response,groups['coco_cats'],a)
        self.assertEqual(pred[0],[.1,.1,.2,.2])
        self.assertEqual(target[0],[0.,0.,1.,1.])

    def test_source_empty_extraction_and_no_null_repair(self):
        ann={'0':{'person':[[0.,0.,1.,1.]]}}
        pred,target=r.source_lists(ann,{'0':{'person':[]}},['person'],a)
        self.assertEqual(pred,[None]);self.assertEqual(len(target),1)
        with self.assertRaises(TypeError):
            r.source_lists(ann,{'0':{'person':None}},['person'],a)

if __name__=='__main__': unittest.main()
