"""Generated transport/support controls; no MATLAB or scientific data execution."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('subject_export', HERE / 'validate_export.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def finite(x):
    return {'state': 'finite', 'value': x}


def fixture():
    phases = ('stimulus', 'feedback', 'interval')
    channels = []
    wide = []
    for name in ('deep_contact_P1', 'other_P1', 'solo_P2', 'extra_P3'):
        vv = {}
        for p in phases:
            if name == 'other_P1' and p == 'feedback':
                vv[p] = {'state': 'nan'}
                continue
            before = finite(0.25)
            flag = name == 'deep_contact_P1' and p == 'stimulus'
            if name == 'other_P1' and p == 'stimulus':
                before = {'state': 'nan'}
            if name == 'extra_P3' and p == 'interval':
                before = {'state': 'positive_infinity'}
            after = {'state': 'nan'} if flag else copy.deepcopy(before)
            channels.append({'row_id': len(channels)+1, 'channel': name, 'phase': p,
                'group_count': 12, 'before': before, 'after': after, 'outlier': flag})
            vv[p] = copy.deepcopy(after)
        wide.append({'row_id': len(wide)+1, 'channel': name,
                     'subject': name.rsplit('_', 1)[-1], 'values': vv})
    subjects = [{'row_id': i, 'subject': s, 'group_count': 2 if s=='P1' else 1,
                 'values': {p: finite(0.5) for p in phases}}
                for i, s in enumerate(('P3', 'P1', 'P2'), 1)]
    performance = [{'row_id': i, 'subject': s, 'inference': finite(0.7), 'memory': finite(0.8)}
                   for i, s in enumerate(('P2', 'P1'), 1)]
    joined = [{'row_id': i, 'subject_row_id': ib, 'subject': performance[i-1]['subject'],
               'values': copy.deepcopy(subjects[ib-1]['values']),
               'inference': copy.deepcopy(performance[i-1]['inference']),
               'memory': copy.deepcopy(performance[i-1]['memory'])}
              for i, ib in enumerate((3, 2), 1)]
    def meta(cols, height, names=None):
        return {'columns': cols, 'classes': ['cell' if c in ('channel','subject','phase') else 'double'
                                           for c in cols],
                'row_names': names or [], 'height': height}
    native = {'before': meta(['channel','phase','GroupCount','fun1_trial_ripple'], len(channels)),
              'after': meta(['channel','phase','GroupCount','fun1_trial_ripple'], len(channels)),
              'wide': meta(['channel','feedback','interval','stimulus'],4),
              'subjects': meta(['subject','GroupCount','feedback','interval','stimulus'],3,['P3','P1','P2']),
              'performance': meta(['subject','testBeforeInfer','testBeforeMemory'],2),
              'joined': meta(['subject','GroupCount','feedback','interval','stimulus','eleInfer_perf','eleMemory_perf'],2,['P2','P1'])}
    return {'schema':'ripple-subject-native-export/v1','source':dict(m.SOURCE),
            'input_identity':{'learnr_input_sha256':'a'*64,'performance_input_sha256':'b'*64},
            'runtime':{'matlab_version':'generated, not a real runtime',
                       'rmoutliers_which':'generated','grpstats_which':'generated','nanmean_which':'generated'},
            'channels':channels,'wide':wide,'subjects':subjects,'performance':performance,
            'join':{'ia':[1,2],'ib':[3,2],'excluded_subject_row_ids':[1]},
            'joined':joined,'native_tables':native}


class SubjectExportControls(unittest.TestCase):
    def reject(self, packet):
        with self.assertRaises(m.ExportError):
            m.validate_packet(packet)

    def test_complete_ordered_join_permits_extra_learned_subject(self):
        result=m.validate_packet(fixture())
        self.assertEqual(result['excluded_learned_subject_rows'],[1])
        self.assertEqual(result['performance_subjects'],2)
        self.assertEqual(result['native_numeric_correctness'],'not_evaluated')
        self.assertFalse(result['reproduction_qualified'])

    def test_correct_stored_subject_cannot_replace_source_suffix(self):
        p=fixture();p['wide'][0]['subject']='contact_P1';self.reject(p)

    def test_mask_requires_nan_instead_of_deleting_or_zeroing(self):
        p=fixture();p['channels'][0]['after']=finite(0);self.reject(p)
        p=fixture();p['channels'].pop(0);self.reject(p)

    def test_unflagged_values_must_remain_identical(self):
        p=fixture();p['channels'][1]['after']=finite(123);self.reject(p)

    def test_no_duplicate_channel_phase_groups(self):
        p=fixture();p['channels'][1]['phase']='stimulus';self.reject(p)

    def test_missing_individual_phase_is_nan_not_zero(self):
        m.validate_packet(fixture())
        p=fixture();p['wide'][1]['values']['feedback']=finite(0);self.reject(p)

    def test_wide_row_and_subject_support_cannot_be_dropped(self):
        p=fixture();p['wide'].pop();self.reject(p)
        p=fixture();p['subjects'].pop();self.reject(p)

    def test_performance_coverage_is_full_and_ordered(self):
        p=fixture();p['join']['ia']=[2,1];self.reject(p)
        p=fixture();p['join']['ib']=[2,3];self.reject(p)
        p=fixture();p['performance'][1]['subject']='P2';self.reject(p)

    def test_joined_behavior_and_source_row_are_exact(self):
        p=fixture();p['joined'][0]['inference']=finite(0.9);self.reject(p)
        p=fixture();p['joined'][0]['subject_row_id']=1;self.reject(p)

    def test_excluded_subject_roster_is_not_silent(self):
        p=fixture();p['join']['excluded_subject_row_ids']=[];self.reject(p)

    def test_infinities_and_nan_are_distinct_states(self):
        self.assertNotEqual(m.scalar({'state':'nan'}),m.scalar({'state':'positive_infinity'}))
        self.assertNotEqual(m.scalar({'state':'negative_infinity'}),m.scalar({'state':'positive_infinity'}))
        p=fixture();p['wide'][-1]['values']['interval']={'state':'negative_infinity'};self.reject(p)

    def test_native_means_are_retained_not_recomputed_or_scored(self):
        p=fixture();p['subjects'][2]['values']['interval']={'state':'negative_infinity'}
        p['joined'][0]['values']['interval']={'state':'negative_infinity'}
        self.assertFalse(m.validate_packet(p)['same_task_improvement_qualified'])
        p['joined'][0]['values']['interval']=finite(-1);self.reject(p)

    def test_bool_and_lossy_large_integer_numeric_states_refused(self):
        for v in (True, float('inf'), float('nan'), 2**53+1):
            with self.assertRaises(m.ExportError):m.scalar(finite(v))
        p=fixture();p['join']['ib'][0]=True;self.reject(p)

    def test_native_metadata_support_and_original_source_pin(self):
        p=fixture();p['native_tables']['joined']['height']=1;self.reject(p)
        p=fixture();p['native_tables']['wide']['columns'].pop();self.reject(p)
        p=fixture();p['source']['caller_sha256']='c'*64;self.reject(p)

    def test_json_roundtrip_preserves_full_packet_and_refuses_bad_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'generated.json'
            target.write_text(json.dumps(fixture()))
            self.assertEqual(m.validate_packet(m.load_packet(target))['channels'],4)
            for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":1e9999}', '{"x":1e-9999}'):
                target.write_text(raw)
                with self.assertRaises(m.ExportError):m.load_packet(target)


if __name__=='__main__':
    unittest.main()
