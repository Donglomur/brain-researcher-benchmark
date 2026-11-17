"""Generated campaign metadata only; no real WORK, roster, audit, task payload or execution.

The small pinned DECLARATIONS file is the sole authentic task metadata input.
All graph identities outside its named pairs, requests and loader trees are
invented. Tests call assess/load_bound directly; no CLI, candidate or grader runs.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import validate as v
DECLARATIONS=v.parse((HERE/'DECLARATIONS.json').read_bytes())
IDS=[f'NEURAL-{i:03}' for i in range(1,101)]+[f'PAPER-GENERATED-{i:03}' for i in range(1,101)]
WROTE=0
READ_CHARGE=0
WRITE_CAP=75000  # Leaves at least25KB for authored source under100KB total.
GENERATED_READ_CAP=45000


def encoded(value):return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def put(path,value):
    global WROTE
    raw=value if type(value)is bytes else encoded(value)
    if WROTE+len(raw)>WRITE_CAP:raise AssertionError('generated write cap')
    WROTE+=len(raw);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    return {'path':path.name,**v.pin(raw)}


class CountedReader(v.Reader):
    def __init__(self,limit=1500000):super().__init__(limit);self.paths=[]
    def read(self,path,cap,expected=None):
        global READ_CHARGE
        size=Path(path).lstat().st_size+1
        if READ_CHARGE+size>GENERATED_READ_CAP:raise AssertionError('generated read cap')
        READ_CHARGE+=size;self.paths.append(Path(path))
        return super().read(path,cap,expected)


def graph():
    edges=[]
    def edge(a,b,relation):edges.append({'tasks':sorted([a,b]),'relation':relation})
    for a,b in [('NEURAL-023','NEURAL-024'),('NEURAL-095','NEURAL-096')]:
        edge(a,b,'shared_declared_neural_source');edge(a,b,'shared_exact_paper_locator')
    edge('NEURAL-001','NEURAL-002','shared_research_source_family')
    edge('NEURAL-002','NEURAL-003','shared_stimulus_family')
    edge('NEURAL-004','NEURAL-005','shared_exact_paper_locator')
    edge('NEURAL-007','NEURAL-008','shared_exact_data_locator')
    linked={x for row in edges for x in row['tasks']}
    return {'status':'declared_metadata_links_only','candidate_tasks':200,'edges':edges,
            'papers_without_detected_cross_suite_edge':[x for x in IDS if x.startswith('PAPER-') and x not in linked],
            'neural_tasks_without_detected_cross_suite_edge':[x for x in IDS if x.startswith('NEURAL-') and x not in linked]}


def evaluation(task,kind='development_only',*,prior=(),concurrent=(),against=()):
    return {'task_id':task,'prior_access':list(prior),'concurrent_inputs':list(concurrent),
            'claims':[{'kind':kind,'against':list(against)}]}


def request(*items):return {'schema':'campaign_exposure_request_v1','evaluations':list(items)}


def decision(item,audit=None,declarations=None):
    return v.assess(request(item),graph() if audit is None else audit,
                    DECLARATIONS if declarations is None else declarations)['decisions'][0]


def reason_codes(row):return {r['code'] for c in row['claims'] for r in c['reasons']}


class ClaimControls(unittest.TestCase):
    def test_directional_actual_target_exposure_and_forbidden_joint_development(self):
        row=decision(evaluation('NEURAL-024',prior=['NEURAL-023']))
        self.assertTrue(row['accepted']);self.assertEqual(len(row['known_actual_target_exposure']),1)
        self.assertEqual(row['known_actual_target_exposure'][0]['access'],['prior'])
        self.assertFalse(decision(evaluation('NEURAL-023',prior=['NEURAL-024']))['known_actual_target_exposure'])
        row=decision(evaluation('NEURAL-024',concurrent=['NEURAL-023']))
        self.assertFalse(row['accepted'])
        self.assertEqual(row['operational_conflicts'],[{'code':'forbidden_joint_inputs','access_task':'NEURAL-023'}])
        row=decision(evaluation('NEURAL-023',concurrent=['NEURAL-024']))
        self.assertTrue(row['accepted']);self.assertFalse(row['known_actual_target_exposure'])

    def test_prior023_blocks_fresh024_and_exposed095096_are_not_fresh(self):
        row=decision(evaluation('NEURAL-024','fresh_targets',prior=['NEURAL-023']))
        self.assertEqual(row['claims'][0]['status'],'contradicted')
        self.assertIn('known_actual_target_exposure',reason_codes(row))
        for task in ['NEURAL-095','NEURAL-096']:
            row=decision(evaluation(task,'fresh_targets'))
            self.assertFalse(row['accepted']);self.assertIn('declared_exposed_development_scope',reason_codes(row))
        row=decision(evaluation('NEURAL-010','fresh_targets',prior=['NEURAL-010']))
        self.assertEqual(row['claims'][0]['status'],'unresolved')
        self.assertFalse(row['known_actual_target_exposure'])

    def test_same_haydn_biology_without_invented_target_leak(self):
        for task,other in [('NEURAL-095','NEURAL-096'),('NEURAL-096','NEURAL-095')]:
            for kind,code in [('new_animal','declared_same_animal'),('new_session','declared_shared_session'),
                              ('independent_acquisition','declared_shared_session')]:
                row=decision(evaluation(task,kind,prior=[other],against=[other]))
                self.assertEqual(row['claims'][0]['status'],'contradicted');self.assertIn(code,reason_codes(row))
                self.assertFalse(row['known_actual_target_exposure']);self.assertFalse(row['operational_conflicts'])

    def test_development_preserves_distinct_ids_and_never_authorizes_execution(self):
        result=v.assess(request(evaluation('NEURAL-095',concurrent=['NEURAL-096']),
                                evaluation('NEURAL-096',prior=['NEURAL-095'])),graph(),DECLARATIONS)
        self.assertTrue(result['accepted']);self.assertEqual(result['distinct_requested_tasks'],2)
        self.assertEqual([r['task_id'] for r in result['decisions']],['NEURAL-095','NEURAL-096'])
        for key in ['task_ids_merged','graph_components_or_RL_split_computed',
                    'readiness_or_execution_authorized','history_independently_verified']:
            self.assertFalse(result[key])

    def test_weak_links_and_absence_never_establish_new_biology(self):
        pairs=[('NEURAL-001','NEURAL-002'),('NEURAL-002','NEURAL-003'),
               ('NEURAL-004','NEURAL-005'),('NEURAL-007','NEURAL-008'),('NEURAL-009','NEURAL-010')]
        for task,other in pairs:
            for kind in ['new_animal','new_session','new_stimuli','independent_acquisition']:
                row=decision(evaluation(task,kind,against=[other]))
                self.assertEqual(row['claims'][0]['status'],'unresolved');self.assertFalse(row['accepted'])
                self.assertFalse(row['typed_direct_links'][0]['absence_means_independent'])
        self.assertEqual(decision(evaluation('NEURAL-004','new_paper',against=['NEURAL-005']))['claims'][0]['status'],'contradicted')
        self.assertEqual(decision(evaluation('NEURAL-009','new_paper',against=['NEURAL-010']))['claims'][0]['status'],'unresolved')
        self.assertEqual(decision(evaluation('NEURAL-010','fresh_targets'))['claims'][0]['status'],'unresolved')

    def test_no_transitive_family_union(self):
        row=decision(evaluation('NEURAL-001','new_session',against=['NEURAL-003']))
        self.assertEqual(row['typed_direct_links'],[{'other':'NEURAL-003','relations':[],
                                                    'absence_means_independent':False}])
        self.assertEqual(row['claims'][0]['status'],'unresolved')

    def test_malformed_unknown_and_duplicate_requests_fail_closed(self):
        good=evaluation('NEURAL-023')
        invalid=[{},request(),request(good,copy.deepcopy(good)),request(evaluation('MISSING')),
                 request(evaluation('NEURAL-023','unknown')),
                 request(evaluation('NEURAL-023',prior=['MISSING'])),
                 request(evaluation('NEURAL-023',prior=['NEURAL-024','NEURAL-024'])),
                 request(evaluation('NEURAL-023',concurrent=['NEURAL-023'])),
                 request(evaluation('NEURAL-023','fresh_targets',against=['NEURAL-024'])),
                 request(evaluation('NEURAL-023','new_animal')),
                 request(evaluation('NEURAL-023','new_animal',against=['NEURAL-023'])),
                 request(evaluation('NEURAL-023',against=['NEURAL-024']))]
        for claims in [[{'kind':'fresh_targets','against':[]}]*2,
                       [{'kind':'development_only','against':[]},{'kind':'fresh_targets','against':[]}]]:
            row=copy.deepcopy(good);row['claims']=claims;invalid.append(request(row))
        extra=copy.deepcopy(good);extra['unexpected']=1;invalid.append(request(extra))
        for item in invalid:
            with self.subTest(request=item):
                with self.assertRaises((ValueError,KeyError,TypeError)):v.assess(item,graph(),DECLARATIONS)
        bad=graph();bad['edges'][0]['relation']='invented_unknown'
        with self.assertRaises(ValueError):v.assess(request(good),bad,DECLARATIONS)
        for raw in [b'{"a":1,"a":2}',b'{"x":NaN}',b'{"x":Infinity}']:
            with self.assertRaises(ValueError):v.parse(raw)


class LoaderControls(unittest.TestCase):
    def test_references_include_evaluation_prior_concurrent_and_against(self):
        value=request(evaluation('NEURAL-024','new_animal',against=['NEURAL-096'],
                                 prior=['NEURAL-023'],concurrent=['NEURAL-095']),
                      evaluation('NEURAL-010'))
        self.assertEqual(v.references(value),{'NEURAL-024','NEURAL-023','NEURAL-095',
                                               'NEURAL-096','NEURAL-010'})
        value['evaluations'][0]['prior_access']=[None]
        with self.assertRaises(ValueError):v.references(value)

    def test_bounded_reader_pin_special_file_and_budget_refusals(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();p=root/'metadata';put(p,b'{}')
            reader=CountedReader();self.assertEqual(reader.read(p,2,v.pin(b'{}')),b'{}')
            self.assertEqual(reader.used,3)
            with self.assertRaises(ValueError):CountedReader(limit=2).read(p,2)
            with self.assertRaises(ValueError):CountedReader().read(p,1)
            with self.assertRaises(ValueError):CountedReader().read(p,2,v.pin(b'xx'))
            link=root/'link';link.symlink_to(p)
            with self.assertRaises(ValueError):CountedReader().read(link,10)
            fifo=root/'fifo';os.mkfifo(fifo)
            with self.assertRaises(ValueError):CountedReader().read(fifo,10)

    def test_pinned_loader_never_opens_payload_and_rejects_stale_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo=Path(temporary).resolve();here=repo/'source';here.mkdir()
            ids=['NEURAL-023','NEURAL-024','NEURAL-095']+[f'X{i:03}' for i in range(197)]
            audit={'status':'declared_metadata_links_only','candidate_tasks':200,'edges':[],
                   'neural_tasks_without_detected_cross_suite_edge':ids,
                   'papers_without_detected_cross_suite_edge':[]}
            audit_pin=put(repo/'audit.json',audit)
            builder_pin=put(repo/'builder.py',b'# invented builder; not executed\n')
            decl={'schema':'campaign_exposure_declarations_v1','tasks':{}}
            work={'preferred_sources':dict.fromkeys(ids,'')}
            for task in ids[:3]:
                declared=put(repo/(task+'.md'),b'Invented selected task declaration.\n')
                descriptor={'task_ids':[task],'files':[
                    {'source':declared['path'],**{k:declared[k] for k in ('bytes','sha256')}},
                    {'source':'DO_NOT_OPEN_PAYLOAD.npz','bytes':9,'sha256':'0'*64}]}
                selected=put(repo/(task+'.json'),descriptor)
                decl['tasks'][task]={'selected_source':selected,'declaration':declared}
                work['preferred_sources'][task]=selected['path']
            # A fresh WORK pin may contain an unrelated changed selected source.
            # Only evaluated024 and its explicitly prior-access023 must still bind.
            work['preferred_sources']['NEURAL-095']='changed-unrelated.json'
            work_pin=put(repo/'work.json',work)
            lock={'audit':audit_pin,'builder':builder_pin,'work_path':'work.json'}
            bodies={'validate.py':b'# invented pinned source; loader never executes it\n',
                    'LOCK.json':encoded(lock),'DECLARATIONS.json':encoded(decl)}
            rows=[]
            for name,body in bodies.items():rows.append(put(here/name,body))
            source=put(here/'SOURCE_MANIFEST.json',{'files':rows})
            relevant=v.references(request(evaluation('NEURAL-024',prior=['NEURAL-023'])))
            reader=CountedReader()
            result=v.load_bound(repo,here,source['sha256'],work_pin['sha256'],reader,relevant)
            self.assertEqual(result[0],audit);self.assertEqual(result[1],decl)
            self.assertEqual(result[2]['verified_declaration_tasks'],['NEURAL-023','NEURAL-024'])
            self.assertNotIn(repo/'DO_NOT_OPEN_PAYLOAD.npz',reader.paths)
            for name in ['NEURAL-095.json','NEURAL-095.md','changed-unrelated.json']:
                self.assertNotIn(repo/name,reader.paths)
            with self.assertRaisesRegex(ValueError,'source manifest SHA256'):
                v.load_bound(repo,here,'0'*64,work_pin['sha256'],CountedReader(),relevant)
            for task in ['NEURAL-024','NEURAL-023']:
                work['preferred_sources'][task]='wrong-selected.json'
                changed=put(repo/'work.json',work)
                with self.subTest(relevant_changed_task=task):
                    with self.assertRaisesRegex(ValueError,'selected task declaration path changed'):
                        v.load_bound(repo,here,source['sha256'],changed['sha256'],CountedReader(),relevant)
                work['preferred_sources'][task]=task+'.json'
            restored=put(repo/'work.json',work)
            put(repo/'NEURAL-024.json',b'{"task_ids":["MISSING"],"files":[]}')
            with self.assertRaisesRegex(ValueError,'metadata pin'):
                v.load_bound(repo,here,source['sha256'],restored['sha256'],CountedReader(),relevant)


if __name__=='__main__':
    result=unittest.main(exit=False,verbosity=2).result
    print(json.dumps({'generated_fixture_body_write_bytes':WROTE,
                      'generated_metadata_read_charge_bytes':READ_CHARGE,
                      'temporary_trees_retired':True,'actual_payload_reads':0,
                      'native_candidate_or_scoring_calls':0}))
    raise SystemExit(not result.wasSuccessful())
