"""Standalone controls using invented values and independent exact oracles."""
import copy
from fractions import Fraction
from itertools import permutations, product
from pathlib import Path
import sys
import unittest

# Support the isolated (-I) command while importing only the adjacent kernel.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from conditional_kernel import (CONTEXTS,FAMILIES,adjusted_rand,enrich,hierarchy_sensitivity,
    moment_errors,moments,pair,reconstruct,validate_packet,validate_submission_case)


def permutation_counts(N,a,b):
    left=set(permutations([1]*a+[0]*(N-a)))
    right=set(permutations([1]*b+[0]*(N-b)))
    return [sum(x*y for x,y in zip(u,v)) for u,v in product(left,right)]


def empirical(values):
    mean=Fraction(sum(values),len(values))
    return mean,sum(((Fraction(x)-mean)**2 for x in values),Fraction(0))/len(values)


def fixture():
    units=[]
    for i in range(9):
        animal='a' if i<2 else 'b' if i<5 else 'c';rec='r'+animal
        units.append({'id':str(i),'animal':animal,'recording':rec,'task':'one' if i%2 else 'two',
                      'category':i%2,'labels':[i%2]*12})
    # Task is a recording-level source attribute.
    for u in units: u['task']='one' if u['animal'] in ['a','b'] else 'two'
    contexts=[]
    for key in CONTEXTS:
        route,ref,subset=key.split('/')
        encoding={'deepRois':'laydepth','nolayRois':'nolays','layeredRois':'lays','deepSupRois':'laydepth'}[subset]
        contexts.append({'key':key,'family':FAMILIES.index('/'.join((route,ref,encoding))),
                         'indices':[0,1],'hierarchy':[1.,2.] if route=='gaoRois' and subset in ['deepRois','nolayRois'] else None})
    return {'schema':'PFC_FULL99_FIXED_MAP_PACKET_V1','units':units,'animals':['a','b','c'],
            'records':[{'id':'r'+a,'animal':a,'task':'one' if a in ['a','b'] else 'two'} for a in ['a','b','c','d']],
            'families':[{'key':key,'labels':['0','1']} for key in FAMILIES], 'contexts':contexts}


class ConditionalKernelControls(unittest.TestCase):
    def test_all_small_independent_permutations(self):
        for N in range(6):
            for a in range(N+1):
                for b in range(N+1):
                    self.assertEqual(moments(N,a,b),empirical(permutation_counts(N,a,b)))

    def test_independent_strata_sum(self):
        values=[a+b for a,b in product(permutation_counts(3,1,2),permutation_counts(2,1,1))]
        a,b=moments(3,1,2),moments(2,1,1)
        self.assertEqual(empirical(values),(a[0]+b[0],a[1]+b[1]))

    def test_same_permutation_mutant_breaks_null(self):
        pairs=set(permutations([1,1,0,0]));wrong=[sum(x*y for x,y in zip(v,v)) for v in pairs]
        self.assertEqual(empirical(wrong)[1],0)
        self.assertNotEqual(empirical(wrong),moments(4,2,2))

    def test_fixed_margin_cells_are_dependent(self):
        outcomes=permutation_counts(4,2,2);mean,var=empirical(outcomes)
        covariance=sum((Fraction(x)-mean)*(Fraction(2-x)-mean) for x in outcomes)/len(outcomes)
        self.assertEqual(covariance,-var)

    def test_finite_draw_population_variance_bias(self):
        averaged=sum(empirical(list(v))[1] for v in product([0,1],repeat=2))/4
        self.assertEqual(averaged,moments(2,1,1)[1]*Fraction(1,2))

    def test_zero_variance_is_undefined(self):
        family={'counts':[[0,1]],'mean':[[[0,1],[1,1]]],'variance':[[[0,1],[0,1]]]}
        self.assertEqual(enrich(family),[[None,None]])

    def test_all_recordings_and_fitting_animals_distinct(self):
        p=fixture();self.assertEqual(validate_packet(p,expected_units=9,expected_recordings=4),['a','b','c'])
        self.assertEqual(len(p['records']),4)  # zero-fit fourth recording remains accounted for

    def test_whole_animal_deleted_in_every_family(self):
        p=fixture();full=reconstruct(p);drop=reconstruct(p,'b')
        self.assertEqual(len(drop['families']),12)
        for a,b in zip(full['families'],drop['families']):
            self.assertEqual(sum(map(sum,a['counts'])),9)
            self.assertEqual(sum(map(sum,b['counts'])),6)
        self.assertNotEqual(full['families'][0]['mean'],drop['families'][0]['mean'])

    def test_singleton_and_empty_task_strata(self):
        self.assertEqual(moments(0,0,0),(Fraction(0),Fraction(0)))
        self.assertEqual(moments(1,1,1),(Fraction(1),Fraction(0)))
        with self.assertRaises(ValueError): moments(1,2,0)


    def test_no_tolerance_and_no_cell_omission(self):
        p=fixture();truth=reconstruct(p);candidate=copy.deepcopy(truth)
        candidate['families'][0]['mean'][0][0]=pair(Fraction(*candidate['families'][0]['mean'][0][0])+Fraction(1,10**30))
        validate_submission_case(candidate,p,'full')
        errors=moment_errors(candidate,truth)[0]['mean']
        self.assertEqual(errors['unequal_cells'],1)
        self.assertEqual(errors['max_absolute_error_exact'],[1,10**30])
        self.assertGreater(errors['mean_absolute_error_binary64'],0)
        candidate['families'][-1]['variance'].pop()
        with self.assertRaises(ValueError):validate_submission_case(candidate,p,'full')

    def test_partition_labels_are_not_numeric_truth(self):
        self.assertEqual(adjusted_rand([1,1,2,2],[7,7,8,8]),1)
        self.assertLess(adjusted_rand([1,1,2,2],[1,2,1,2]),1)

    def test_undefined_deletion_never_counts_as_sign_stability(self):
        full={'x':[.2,0,0,0,0,-.2,0,0]};deletions=[{'x':[None,0,0,0,0,-.1,0,0]}]
        out=hierarchy_sensitivity(full,deletions,1)['x']
        self.assertFalse(out[0]['complete_direction_stability']);self.assertTrue(out[5]['complete_direction_stability'])
        full['x'][5]=None;self.assertFalse(hierarchy_sensitivity(full,deletions,1)['x'][5]['complete_direction_stability'])




if __name__=='__main__':unittest.main()
