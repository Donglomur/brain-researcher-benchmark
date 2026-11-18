"""New generated CSV/layout controls; the earlier subject-stage suite is not run."""
import copy
import csv
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('behavior_input', ROOT/'behavior_input.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
fixture_path = ROOT.parent/'source-subject-export-v1/tests/test_subject_export.py'
fixture_body = fixture_path.read_bytes()
if len(fixture_body)!=7637 or hashlib.sha256(fixture_body).hexdigest()!='76524bf938856a0b47bb9eb5a62d7e628d0354fde4e9cf91bda15a07f8d6c6b0':
    raise RuntimeError('exact accepted sibling fixture required')
fixture_spec=importlib.util.spec_from_file_location('original_subject_fixture',fixture_path)
fixture_module=importlib.util.module_from_spec(fixture_spec)
exec(compile(fixture_body,str(fixture_path),'exec'),fixture_module.__dict__)


def packet():
    return fixture_module.fixture()


def build(p=None,**overrides):
    args={'initial_cwd':'/selected workspace/ripple/R_scripts',
          'rscript_executable':'/configured/Rscript',
          'source_file':'/selected source/LearnR_predict_performance.R'}
    args.update(overrides)
    return m.build_input(packet() if p is None else p,**args)


def parse(body):
    return list(csv.DictReader(io.StringIO(body.decode('utf8'),newline='')))


class BehaviorInputControls(unittest.TestCase):
    def test_order_and_selected_native_group_count(self):
        body,manifest=build();rows=parse(body)
        self.assertEqual([r['subject'] for r in rows],['P2','P1'])
        self.assertEqual([r['GroupCount'] for r in rows],['1','2'])
        self.assertEqual([r['native_subject_row_id'] for r in manifest['subject_rows']],[3,2])
        self.assertEqual(manifest['upstream_support']['excluded_learned_subject_rows'],[1])

    def test_native_column_order_is_preserved_by_name(self):
        p=packet();p['native_tables']['joined']['columns'].reverse();p['native_tables']['joined']['classes'].reverse()
        body,manifest=build(p)
        header=next(csv.reader(io.StringIO(body.decode())))
        self.assertEqual(header,p['native_tables']['joined']['columns'])
        self.assertEqual(parse(body)[0]['subject'],'P2')
        self.assertEqual(manifest['csv']['columns'],header)

    def test_nan_and_both_infinities_are_transported_without_row_deletion(self):
        p=packet()
        for phase,state in zip(('stimulus','feedback','interval'),('nan','positive_infinity','negative_infinity')):
            value={'state':state};p['subjects'][2]['values'][phase]=value
            p['joined'][0]['values'][phase]=copy.deepcopy(value)
        p['performance'][0]['memory']={'state':'nan'};p['joined'][0]['memory']={'state':'nan'}
        body,manifest=build(p);rows=parse(body)
        self.assertEqual(len(rows),2)
        self.assertEqual([rows[0][p] for p in ('stimulus','feedback','interval')],['NaN','Inf','-Inf'])
        self.assertEqual(rows[0]['eleMemory_perf'],'NaN')
        self.assertEqual(manifest['csv']['native_R_read_table_parity'],'unqualified')

    def test_finite_value_precision_and_signed_zero(self):
        p=packet()
        for phase,value in [('stimulus',0.10000000000000002),('interval',-0.0)]:
            p['subjects'][2]['values'][phase]={'state':'finite','value':value}
            p['joined'][0]['values'][phase]={'state':'finite','value':value}
        rows=parse(build(p)[0])
        self.assertEqual(rows[0]['stimulus'],'0.10000000000000002')
        self.assertEqual(rows[0]['interval'],'-0.0')

    def test_identity_punctuation_is_quoted_as_a_complete_field(self):
        p=packet();new='P2#apostrophe\'double"comma,'
        for row in p['channels']:
            if row['channel']=='solo_P2':row['channel']='solo_'+new
        p['wide'][2]['channel']='solo_'+new;p['wide'][2]['subject']=new
        p['subjects'][2]['subject']=new;p['performance'][0]['subject']=new;p['joined'][0]['subject']=new
        p['native_tables']['subjects']['row_names'][2]=new
        p['native_tables']['joined']['row_names'][0]=new
        body,_=build(p)
        self.assertEqual(parse(body)[0]['subject'],new)
        self.assertTrue(all(line.startswith('"') and line.endswith('"') for line in body.decode().splitlines()))
        self.assertIn('"P2#apostrophe\'double""comma,"',body.decode())

    def test_behavior_assignments_are_not_swapped(self):
        rows=parse(build()[0]);self.assertEqual(rows[0]['eleMemory_perf'],'0.8')
        self.assertEqual(rows[0]['eleInfer_perf'],'0.7')

    def test_manifest_binds_csv_bytes_and_complete_row_counts(self):
        body,manifest=build()
        self.assertEqual(manifest['csv']['sha256'],hashlib.sha256(body).hexdigest())
        self.assertEqual(manifest['csv']['bytes'],len(body))
        self.assertEqual(manifest['csv']['rows'],len(parse(body)))
        self.assertFalse(manifest['reproduction_qualified'])
        self.assertFalse(manifest['same_task_improvement_qualified'])

    def test_exact_source_models_order_and_no_added_defaults(self):
        layout=build()[1]['layout']
        self.assertEqual([x['formula'] for x in layout['models_in_source_order']],
            ['eleMemory_perf~stimulus','eleInfer_perf~stimulus','eleMemory_perf~feedback',
             'eleInfer_perf~feedback','eleMemory_perf~interval','eleInfer_perf~interval'])
        self.assertTrue(all(x['setting']=='KS2014' for x in layout['models_in_source_order']))
        self.assertEqual(layout['source_default_overrides_added'],[])
        self.assertIn('cef[,4]<0.05',layout['source_postprocessing'][1])
        self.assertFalse(layout['original_helper_cwd_qualified'])

    def test_explicit_initial_cwd_drives_parent_results_without_shell(self):
        layout=build()[1]['layout']
        self.assertEqual(layout['input_csv'],'/selected workspace/ripple/Results/dt_sublevel_LearnR_behav.csv')
        self.assertEqual(layout['output_csv'],'/selected workspace/ripple/Results/LearnR_predict_infer/learnR_predict_feature_performance.csv')
        self.assertEqual(layout['argv'],['/configured/Rscript','/selected source/LearnR_predict_performance.R'])
        self.assertFalse(layout['source_file_check_performed'])
        changed=build(initial_cwd='/elsewhere/scriptdir')[1]['layout']
        self.assertEqual(changed['results_directory'],'/elsewhere/Results')

    def test_ambiguous_relative_or_non_posix_locations_are_refused(self):
        for path in ('relative/path','/x/../y','/x//y','/x/./y','C:\\scripts','/x\ny'):
            with self.assertRaises(m.BehaviorInputError):build(initial_cwd=path)

    def test_invalid_subject_packet_cannot_be_exported(self):
        p=packet();p['joined'][0]['subject_row_id']=1
        with self.assertRaises(m.BehaviorInputError):build(p)

    def test_incomplete_output_is_refused_without_returning_partial_csv(self):
        old=m.MAX_CSV_BYTES;m.MAX_CSV_BYTES=20
        try:
            with self.assertRaises(m.BehaviorInputError):build()
        finally:m.MAX_CSV_BYTES=old

    def test_source_identity_gate_refuses_wrong_or_oversized_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'generated.R'
            for body in (b'print(1)',b'x'*(m.SOURCE_BYTES+1)):
                p.write_bytes(body)
                with self.assertRaises(m.BehaviorInputError):m.check_source_file(p)


if __name__=='__main__':
    unittest.main()
