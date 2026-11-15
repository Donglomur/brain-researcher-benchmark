"""Source and invented-wrapper controls; never read authentic scientific files.
The positive fixture replaces ONLY the two release-identity literals inside the
embedded accepted algorithm. The selected production program stays unchanged.
Path.read_bytes is intercepted; the only permitted request is the input CSV.
"""
import ast,contextlib,copy,csv,hashlib,io,json,runpy,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
PROFILE=ROOT.parent
SOURCE=PROFILE/'reference'
PROGRAM=(SOURCE/'construction_program.py').read_text()
REFERENCE=(SOURCE/'behavior_reference.py').read_text()
REUSE=runpy.run_path(str(ROOT/'test_behavior_boundary.py'),run_name='_reuse_independent_fixture')
scorer=REUSE['scorer'];owner=REUSE['docker_owner']
import route_config

def invented_csv(omit=None,bad=False):
    stream=io.StringIO(newline='');writer=csv.writer(stream,lineterminator='\n')
    writer.writerow(['subjID','day','TMS_condition','ierr','isacc_rt','isacc_peakvel'])
    groups=[(1,'No TMS'),(1,'TMS intoVF'),(1,'TMS outVF'),(4,'TMS intoVF'),(4,'TMS outVF'),(5,'TMS intoVF'),(5,'TMS outVF')]
    for person in scorer.ROSTER:
        if person==omit:continue
        for day,label in groups:
            for k in range(2):writer.writerow([person,day,label,'Infinity' if bad and person==1 and k==0 else '1.0','1.0','1.0'])
    return stream.getvalue().encode()

def fixture_program(data):
    # Identity substitution is explicit and limited to literals, not parser/math.
    tree=ast.parse(PROGRAM);found=0
    for node in tree.body:
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='SOURCE':
            assert node.value.value==REFERENCE
            identity_source=REFERENCE.replace('RELEASE_BYTES = 4926544','RELEASE_BYTES = '+str(len(data))).replace('RELEASE_SHA256 = "b677bede5c7c8c2806e2796ed58c783b07d2a73687d662b97ceb078916ade80a"','RELEASE_SHA256 = "'+hashlib.sha256(data).hexdigest()+'"')
            assert identity_source!=REFERENCE;node.value=ast.Constant(identity_source);found+=1
    assert found==1
    return compile(ast.fix_missing_locations(tree),'<invented-identity-production-wrapper>','exec')

def execute(code,data):
    reads=[];stream=io.StringIO()
    def only_csv(path):
        if str(path)!='/input/behavioralData_allsubs.csv':raise AssertionError('unapproved file read '+str(path))
        reads.append(str(path));return data
    with patch.object(Path,'read_bytes',only_csv),contextlib.redirect_stdout(stream):
        exec(code,{'__name__':'_wrapper_source_control'})
    return stream.getvalue().encode(),reads

class FixedProgram(unittest.TestCase):
    def test_complete_program_identity_and_embedded_source(self):
        self.assertEqual(hashlib.sha256(PROGRAM.encode()).hexdigest(),'c8fec1a48547b5658f90bc9e38843a301d4c51747d5a39c8e589e3ddc0afa3db')
        literal=next(n.value.value for n in ast.parse(PROGRAM).body if isinstance(n,ast.Assign)and isinstance(n.targets[0],ast.Name)and n.targets[0].id=='SOURCE')
        self.assertEqual(literal,REFERENCE)
        self.assertNotIn('behavior_reference.private.json',PROGRAM)
        self.assertNotIn('benchmark-engineering-evidence',PROGRAM)

    def test_unmodified_production_program_rejects_invented_input(self):
        with self.assertRaisesRegex(ValueError,'wrong released behavioral CSV identity'):
            execute(compile(PROGRAM,'<selected-program>','exec'),invented_csv())

    def test_complete_csv_wrapper_matches_independent_all_one_arithmetic(self):
        data=invented_csv();raw,reads=execute(fixture_program(data),data)
        actual=scorer.validate(scorer.decode(raw));expected=REUSE['independent_fixture']()
        self.assertEqual(actual,expected)
        self.assertEqual(reads,['/input/behavioralData_allsubs.csv'])
        self.assertLess(len(raw),2*1024*1024)
        self.assertEqual(set(actual),{'schema','roster','metrics'})
        self.assertEqual(sum(len(v['participant_cells'])for v in actual['metrics'].values()),315)
        self.assertEqual(sum(len(v['contrasts'])for v in actual['metrics'].values()),18)
        self.assertEqual(sum(len(c['leave_one_person_out'])for v in actual['metrics'].values()for c in v['contrasts'].values()),270)

    def test_changed_csv_body_is_rejected_before_calculation(self):
        data=invented_csv();changed=data.replace(b',1.0,',b',2.0,',1)
        with self.assertRaisesRegex(ValueError,'wrong released behavioral CSV identity'):execute(fixture_program(data),changed)

    def test_complete_cohort_required_after_identity_admission(self):
        data=invented_csv(omit=27)
        with self.assertRaisesRegex(ValueError,'complete fifteen-person release'):execute(fixture_program(data),data)

    def test_nonfinite_metric_rejected_after_identity_admission(self):
        data=invented_csv(bad=True)
        with self.assertRaisesRegex(ValueError,'contains infinity'):execute(fixture_program(data),data)

    def test_public_template_is_unselected_and_two_programs_require_pins(self):
        request=json.loads((ROOT/'REQUEST.template.json').read_bytes())
        self.assertFalse(request['owner_use']['authorized_local_use'])
        self.assertEqual(set(request['programs']),{'A','B'})
        self.assertEqual({v['sha256'] for v in request['programs'].values()},{'0'*64})
        config=json.loads((ROOT/'owner-template/CONFIG.json').read_bytes())
        self.assertFalse(config['root_execution_selected'])
        self.assertEqual(config['study_budget']['model_calls'],0)

    def test_exact_existing_container_command_matches_corrected_proposal(self):
        # Build argv only; no command, service query, container or candidate runs.
        argv=owner.create_argv('invented-command-control',ROOT,ROOT,SOURCE/'construction_program.py')
        self.assertIn('--pull=never',argv);self.assertIn('--network=none',argv)
        self.assertEqual(argv[-5:],['--entrypoint=python3',owner.IMAGE,'-I','-B','/candidate/solution.py'])
        self.assertEqual(sum(x=='--mount' for x in argv),3)
        self.assertTrue(any('dst=/candidate/solution.py,readonly' in x for x in argv))
        self.assertNotIn('-S',argv)

if __name__=='__main__':unittest.main(verbosity=2)
