"""Invented relocation-boundary controls. No authentic data, Docker or models.

The eight separately retained stream controls are not duplicated here.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).absolute().parent))
import deployment as d
from profile import (PROFILE, IMAGE, PACKET, SCIENCE, ASSISTANCE, OFFICIAL,
                     RUNTIME_FILES, BASELINE, NEGATIVE, EXECUTION_SCOPE)
from compatibility import inspect_score


def pin(path, identity=(1, 'a'*64)):
    return {'path':str(path), 'bytes':identity[0], 'sha256':identity[1]}


def fixture(root, compatibility=False):
    here = root/'package'
    r = {'schema':'PFC_PORTABLE_PARTICIPANT_REQUEST_V1', 'attempt':'invented-relocation',
         'policy':pin(root/'private'/'POLICY.json'), 'source_lock':pin(root/'LOCK.json'),
         'source_files':{name:pin(here/name) for name in RUNTIME_FILES},
         'programs':{arm:pin(root/('program-'+arm+'.py'), BASELINE) for arm in ('A','B')},
         'execution_scope':EXECUTION_SCOPE, 'compatibility':compatibility,
         'deployment':{'host_python':pin(root/'python'), 'docker_cli':pin(root/'docker'),
            'docker_host':'unix://'+str(root/'docker.sock'), 'daemon_id':'invented-daemon',
            'attempts_root':str(root/'attempts'), 'uid':1001, 'gid':1001}}
    p = {'schema':'PFC_PORTABLE_PARTICIPANT_POLICY_V1', 'profile':PROFILE, 'image':IMAGE,
         'packet':pin(root/'assets'/'packet.json', PACKET),
         'source_input_selection':pin(root/'private'/'input-selection.json'),
         'scorer_sources':{name:pin(here/'science'/name, value) for name,value in SCIENCE.items()},
         'common_assistance':{name:pin(root/'assets'/name, value) for name,value in ASSISTANCE.items()},
         'additional_B_assistance':{name:pin(root/'assets'/name, value) for name,value in OFFICIAL.items()},
         'inherited_owner':r['source_files']['lifecycle_owner.py'],
         'inherited_outer':r['source_files']['lifecycle_outer.py'],
         'negative_source':pin(here/'science'/'make_negative_submission.py',NEGATIVE),
         'assistance_interpretation':'invented metadata fixture', 'rights':'no authentic data'}
    return r,p,here


def invented_score(negative=False):
    # Structural score fixtures contain no genuine neural values or cases.
    cases=[];ordinal=0
    for case_index in range(69):
        families=[]
        for family in range(12):
            cells=640 if family<11 else 656
            row={'family':'invented-'+str(family),'cells':cells}
            for name in ('counts','mean','variance'):
                delta=int(negative and name=='counts')
                row[name]={'mean_absolute_error_binary64':delta,'max_absolute_error_exact':[delta,1],
                           'unequal_cells':cells if delta else 0}
            families.append(row)
        contexts={}
        for context in range(16):
            defined=ordinal>=46;ordinal+=1
            contexts['invented-'+str(context)]={
                'geometry_defined':{'candidate':defined,'reference':defined},
                'enrichment':{'coordinates':8,'undefined_coordinates':0,'undefined_state_mismatches':0,
                              'mean_absolute_error':0,'max_absolute_error':0},
                'partition_adjusted_rand':{'2':[1,1]} if defined else {}}
        hierarchy={'invented-'+str(i):[None]*8 for i in range(4)}
        errors={k:{'coordinates':8,'undefined_coordinates':8,'undefined_state_mismatches':0,
                   'mean_absolute_error':None,'max_absolute_error':None} for k in hierarchy}
        cases.append({'case':'full' if case_index==0 else 'without:invented-'+str(case_index),
            'moment_errors':families,'continuous_comparisons':{'contexts':contexts,'hierarchy_errors':errors},
            'reference_hierarchy':hierarchy,'candidate_hierarchy':hierarchy})
    influence={'invented-'+str(i):[{'predeclared_direction':sign,'category':category,'all_animals':68,
                'defined_deletions':65,'complete_direction_stability':False}
               for category,sign in [(1,1),(6,-1)]] for i in range(4)}
    return {'schema':'PFC_FULL99_CONDITIONAL_SCORE_V1','packet_sha256':PACKET[1],
            'candidate_sha256':'a'*64,'roster':{'recordings':99,'units':19186,'animals':68,
            'families':12,'analytic_contexts':16,'gao_contexts':4},'cases':cases,
            'candidate_animal_influence':influence}


class PortableControls(unittest.TestCase):
    def test_two_distinct_roots_keep_the_same_scientific_identities(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('host-one','different host two'):
                r,p,here=fixture(Path(tmp).resolve()/name)
                d.validate_request_metadata(r,p,here)
                self.assertEqual((p['packet']['bytes'],p['packet']['sha256']),PACKET)

    def test_wrong_packet_digest_and_extent_both_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            for field,value in [('sha256','0'*64),('bytes',PACKET[0]-1)]:
                r,p,here=fixture(Path(tmp).resolve());p['packet'][field]=value
                with self.assertRaises(ValueError):d.validate_request_metadata(r,p,here)

    def test_scientific_scorer_substitution_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            r,p,here=fixture(Path(tmp).resolve());p['scorer_sources']['conditional_kernel.py']['sha256']='0'*64
            with self.assertRaises(ValueError):d.validate_request_metadata(r,p,here)

    def test_relocated_runtime_rejects_remote_endpoint_and_root_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            for key,value in [('docker_host','tcp://example.invalid:2375'),('uid',0),('uid',True)]:
                r,p,here=fixture(Path(tmp).resolve());r['deployment'][key]=value
                with self.assertRaises(ValueError):d.validate_request_metadata(r,p,here)

    def test_mount_separator_and_output_input_overlap_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            r,p,here=fixture(Path(tmp).resolve());p['packet']['path']=str(Path(tmp).resolve()/'a,readonly=false')
            with self.assertRaises(ValueError):d.validate_request_metadata(r,p,here)
            r,p,here=fixture(Path(tmp).resolve());p['packet']['path']=str(Path(tmp).resolve()/'attempts'/'packet.json')
            with self.assertRaises(ValueError):d.validate_request_metadata(r,p,here)

    def test_symlink_and_hardlink_assets_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();original=root/'original';original.write_bytes(b'invented')
            identity=(8,hashlib.sha256(b'invented').hexdigest())
            alias=root/'alias';alias.symlink_to(original)
            with self.assertRaises(ValueError):d.read_pin(pin(alias,identity))
            linked=root/'linked';os.link(original,linked)
            with self.assertRaises(ValueError):d.read_pin(pin(linked,identity))

    def test_missing_owner_asset_has_explicit_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(FileNotFoundError,'Missing owner-provided asset'):
                d.read_pin(pin(Path(tmp).resolve()/'missing'))

    def test_duplicate_json_and_nonfinite_metadata_refuse(self):
        for raw in [b'{"x":1,"x":2}',b'{"x":NaN}']:
            with self.assertRaises(ValueError):d.decode(raw)

    def test_complete_source_lock_detects_body_tamper_and_duplicate_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();r,p,here=fixture(root);here.mkdir()
            files=[]
            for name in sorted(RUNTIME_FILES):
                body=('invented '+name).encode();(here/name).write_bytes(body)
                identity=(len(body),hashlib.sha256(body).hexdigest())
                r['source_files'][name]=pin(here/name,identity)
                files.append({'relative_path':'package/'+name,'bytes':identity[0],'sha256':identity[1]})
            def save(rows):
                body=json.dumps({'schema':'PFC_PORTABLE_SOURCE_LOCK_V1','files':rows}).encode()
                path=root/'LOCK.json';path.write_bytes(body)
                r['source_lock']=pin(path,(len(body),hashlib.sha256(body).hexdigest()))
            save(files);d.authenticate_source_graph(r,here)
            save(files+[files[0]])
            with self.assertRaises(ValueError):d.authenticate_source_graph(r,here)
            save(files);(here/files[0]['relative_path'].split('/')[-1]).write_bytes(b'changed')
            with self.assertRaises(ValueError):d.authenticate_source_graph(r,here)

    def test_compatibility_requires_the_independent_baseline_in_both_arms(self):
        with tempfile.TemporaryDirectory() as tmp:
            r,p,here=fixture(Path(tmp).resolve(),True);d.validate_request_metadata(r,p,here)
            r['programs']['B']['sha256']='0'*64
            with self.assertRaises(ValueError):d.validate_request_metadata(r,p,here)

    def test_runtime_cost_and_negative_stages_have_complete_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            r,p,here=fixture(Path(tmp).resolve(),True);selected=d.limits(r)
            self.assertEqual(len(selected['deadlines']),7)
            self.assertEqual(sum(selected['deadlines']),2460)
            self.assertLess(sum(selected['deadlines']),selected['owner_seconds'])
            self.assertLess(selected['owner_seconds'],selected['outer_seconds'])
            r['deployment']['docker_cli']['bytes']=64*1024**2
            r['deployment']['host_python']['bytes']=16*1024**2
            d.validate_request_metadata(r,p,here)
            self.assertLessEqual(d.preflight_reservation(r)+sum(selected['managed_stages'])*1024**2,selected['managed_cap'])

    def test_clean_client_environment_does_not_forward_credentials(self):
        with patch.dict(os.environ,{'SECRET_TOKEN':'invented','DOCKER_HOST':'tcp://elsewhere','HTTP_PROXY':'invented'}):
            env=d.safe_environment()
            self.assertNotIn('SECRET_TOKEN',env);self.assertNotIn('DOCKER_HOST',env);self.assertNotIn('HTTP_PROXY',env)

    def report(self, value, negative=False):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp).resolve()/'invented-score.json';path.write_text(json.dumps(value))
            return inspect_score(path,'a'*64,negative)

    def test_compatibility_report_keeps_all_69_cases_and_46_undefined_contexts(self):
        result=self.report(invented_score())
        self.assertEqual((result['cases'],result['exact_fields'],result['undefined_contexts']),(69,1593072,46))

    def test_late_case_error_and_missing_case_are_not_hidden_by_aggregate_match(self):
        value=invented_score();value['cases'][-1]['moment_errors'][-1]['variance']['unequal_cells']=1
        with self.assertRaises(ValueError):self.report(value)
        value=invented_score();value['cases'].pop()
        with self.assertRaises(ValueError):self.report(value)

    def test_incorrect_stability_or_filtered_undefined_state_refuses(self):
        value=invented_score();value['candidate_animal_influence']['invented-0'][0]['complete_direction_stability']=True
        with self.assertRaises(ValueError):self.report(value)
        value=invented_score();value['cases'][0]['continuous_comparisons']['contexts']['invented-0']['geometry_defined']={'candidate':True,'reference':True}
        with self.assertRaises(ValueError):self.report(value)

    def test_complete_count_plus_one_negative_preserves_moments(self):
        self.assertTrue(self.report(invented_score(True),True)['compatible'])
        value=invented_score(True);value['cases'][-1]['moment_errors'][-1]['mean']['mean_absolute_error_binary64']=1
        with self.assertRaises(ValueError):self.report(value,True)


if __name__ == '__main__':
    import signal
    # No subprocesses are launched by this suite. Bound the complete remaining
    # invocation, including temporary-file finalization; do not renew per case.
    signal.signal(signal.SIGALRM, lambda *_: os._exit(124))
    signal.setitimer(signal.ITIMER_REAL, 60)
    unittest.main(verbosity=2)
