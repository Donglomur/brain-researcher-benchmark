"""Invented fixtures check failure modes, not authentic scientific validity."""
import copy
import math
from pathlib import Path
import tempfile
import unittest

import score_lobes as s


def fixture():
    rows = []
    for species in s.SPECIES:
        for group in ('one', 'two', 'three'):
            for lobe in s.LOBES:
                for i in range(3 if group == 'one' else 1):
                    rows.append(dict(neuron_id=f'{species}-{group}-{lobe}-{i}', species=species,
                                     group_id=group, lobe=lobe, included=True))
    manifest = dict(schema='dendrite-lobe-protected-v1', source_revision='a0cc151a00384543a21c95c61479e65112ba6b5d',
                    group_map_sha256='a'*64, census=rows)
    predictions = [dict(neuron_id=r['neuron_id'], fold_id=s.fold_id(r['species'], r['group_id']),
                        p_PL=int(r['lobe']=='PL')) for r in rows]
    return manifest, dict(schema='dendrite-lobe-predictions-v1', predictions=predictions)


class ScoringControls(unittest.TestCase):
    def setUp(self):
        self.m, self.p = fixture()
        self.included, _, _ = s._validate_manifest(self.m, {'human':10, 'mouse':10})

    def test_perfect_and_wrong(self):
        self.assertEqual(s._evaluate(self.included,self.p)['primary'],1)
        for p in self.p['predictions']: p['p_PL'] = 1-p['p_PL']
        self.assertEqual(s._evaluate(self.included,self.p)['primary'],0)

    def test_neuron_replication_does_not_reweight_group(self):
        # Group one has three times as many neurons but equal primary weight.
        for p in self.p['predictions']:
            if '-one-' in p['neuron_id']:p['p_PL'] = 1-p['p_PL']
        self.assertAlmostEqual(s._evaluate(self.included,self.p)['primary'],2/3)

    def test_fixed_tie_and_probabilistic_metrics(self):
        for p in self.p['predictions']:p['p_PL']=0.5
        out=s._evaluate(self.included,self.p)
        self.assertEqual(out['primary'],0.5)
        for row in out['by_species'].values():
            self.assertEqual(row['group_class_brier'],0.25)
            self.assertAlmostEqual(row['group_class_log_loss'],math.log(2))

    def test_drop_case(self):
        self.p['predictions'].pop()
        with self.assertRaises(s.Invalid):s._evaluate(self.included,self.p)

    def test_duplicate_case_even_with_correct_length(self):
        self.p['predictions'][1]=copy.deepcopy(self.p['predictions'][0])
        with self.assertRaises(s.Invalid):s._evaluate(self.included,self.p)

    def test_foreign_fold(self):
        self.p['predictions'][0]['fold_id']=s.fold_id('human','two')
        with self.assertRaises(s.Invalid):s._evaluate(self.included,self.p)

    def test_bad_probabilities(self):
        for p in [True,float('nan'),float('inf'),-0.01,1.01,'0.5']:
            with self.subTest(p=p):
                self.p['predictions'][0]['p_PL']=p
                with self.assertRaises(s.Invalid):s._evaluate(self.included,self.p)

    def test_third_lobe_not_silently_pooled(self):
        self.m['census'][0]['lobe']='TL'
        with self.assertRaises(s.Invalid):s._validate_manifest(self.m,{'human':10,'mouse':10})

    def test_neuron_ids_not_biological_groups(self):
        for row in self.m['census']:row['group_id']='one'
        with self.assertRaises(s.Invalid):s._validate_manifest(self.m,{'human':10,'mouse':10})

    def test_absent_training_class(self):
        for row in self.m['census']:
            if row['group_id']=='two':row['lobe']='FL'
        with self.assertRaises(s.Invalid):s._validate_manifest(self.m,{'human':10,'mouse':10})

    def test_two_groups_cannot_support_nested_tuning(self):
        self.m['census']=[r for r in self.m['census'] if r['group_id']!='three']
        with self.assertRaises(s.Invalid):s._validate_manifest(self.m,{'human':8,'mouse':8})

    def test_inner_class_gap_with_valid_outer_training(self):
        for row in self.m['census']:
            if row['group_id']=='three':row['lobe']='FL'
        # Each outer complement still has both classes, but holding one and
        # two together in the nested split leaves FL only in training.
        with self.assertRaisesRegex(s.Invalid,'inner training'):
            s._validate_manifest(self.m,{'human':10,'mouse':10})

    def test_census_and_exclusions(self):
        row=self.m['census'][0];row.pop('group_id');row.pop('lobe');row['included']=False;row['exclusion']='missing_required_feature'
        included,_,_=s._validate_manifest(self.m,{'human':10,'mouse':10})
        self.assertEqual(len(included),19)
        row['exclusion']='poor_prediction'
        with self.assertRaises(s.Invalid):s._validate_manifest(self.m,{'human':10,'mouse':10})

    def test_real_entry_rejects_small_fixture(self):
        with self.assertRaises(s.Invalid):s.score(self.m,self.p)

    def test_complete_production_census_and_paired_baseline(self):
        # Entire production denominator, but explicitly invented records.
        for species,total in s.SOURCE_COUNTS.items():
            for i in range(total-10):
                self.m['census'].append(dict(neuron_id=f'excluded-{species}-{i}',species=species,
                                            included=False,exclusion='outside_FL_PL'))
        baseline=copy.deepcopy(self.p)
        for p in baseline['predictions']:p['p_PL']=0.5
        out=s.score(self.m,self.p,baseline)
        self.assertEqual(out['paired_primary_delta'],0.5)
        self.assertFalse(out['scientific_qualification'])

    def test_duplicate_and_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'x.json'
            for bad in ['{"a":1,"a":2}','{"a":NaN}']:
                f.write_text(bad)
                with self.assertRaises(s.Invalid):s.load_json(f)


if __name__=='__main__':unittest.main(verbosity=2)
