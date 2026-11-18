"""Generated companion controls: no R process, original workbook, fitting, or native RDS interpretation."""
import argparse
import base64
import copy
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[1]


def module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


replay = module_from_path('companion_replay_test', ROOT/'replay_companions.py')
contract = replay.contract
base = contract.load_predecessor()
public = base.public_contract()
prior_fixtures = module_from_path('frozen_generated_fixture',
    contract.PREDECESSOR/'tests/generated_controls.py')


def png_chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data) & 0xffffffff)


def generated_png(width=1, height=1):
    """A real tiny generated PNG container, not an original forest or an edited image."""
    header = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    pixels = b''.join(b'\x00'+b'\x07\x15\x29'*width for _ in range(height))
    return b'\x89PNG\r\n\x1a\n' + png_chunk(b'IHDR', header) + png_chunk(b'IDAT', zlib.compress(pixels)) + png_chunk(b'IEND', b'')


def generated_ledger(doc):
    names = {'quest_self':('meta_questSelf','dfQuestSelf','dfQuestSelf_conv'),
             'amy_quest':('meta_amyQuest','dfAmyQuest','dfAmyQuest_conv'),
             'amy_self':('meta_amySelf','dfAmySelf','dfAmySelf_conv')}
    return {'schema':'nider_primary_native_row_lineage_v1','task':doc['task'],
        'workbook_sha256':doc['workbook_sha256'],
        'contrasts':[{'contrast':row['contrast'],'native_model':names[row['contrast']][0],
            'native_subset':names[row['contrast']][1],
            'dl_n_column':'sample size rating' if row['contrast']=='amy_self' else 'sample size quest',
            'bayes_input_object':names[row['contrast']][2], 'bayes_n_column':'sample size quest',
            'bayes_n_choice_authority':'authenticated_original_escalc_expression_not_column_presence',
            'membership':copy.deepcopy(row['membership'])} for row in doc['contrasts']]}


def native_cell(value):
    return {'state':'finite','value':value}


def native_vector(values, names=None, storage='double'):
    return {'length':len(values),'storage_type':storage,'names':names,
            'values':[native_cell(value) for value in values]}


def generated_forest(row):
    extent=len(row['membership'])
    fields=('cor','n','TE','seTE','lower','upper','w.common','w.random')
    return {'schema':'nider_original_forest_native_vectors_v1','contrast':row['contrast'],
        'native_model':row['native_model'],
        'source_order':'unchanged_native_and_full120_membership_order',
        'membership':copy.deepcopy(row['membership']),
        'studlab':[unit['author_label'] for unit in row['membership']],
        'scales':{'cor':'native_input_Pearson_r','n':'source_sample_size','TE':'Fisher_z',
                  'seTE':'Fisher_z','lower':'Fisher_z','upper':'Fisher_z',
                  'w.common':'raw_native_weight_not_percent','w.random':'raw_native_weight_not_percent'},
        'vectors':{key:native_vector([i/100.0 for i in range(extent)]) for key in fields},
        'transformation_performed':False}


def generated_bayes(row):
    # Deliberately asymmetric sentinels preserve row/column identity; not fitted values.
    return {'schema':'nider_original_bma_native_values_v1','contrast':row['contrast'],
        'native_model':'B'+row['native_model'],
        'documented_positional_model_order':['fixed_H0','fixed_H1','random_H0','random_H1'],
        'inclusion_BF_role':'incl.BF_is_model_averaged_effect_inclusion_BF10_not_pairwise_BF',
        'inclusion':{'incl.BF':native_cell(2.25),'incl.prior':native_cell(.5),
                     'incl.posterior':native_cell(.75),'include':native_vector([2,4],storage='integer'),
                     'prior':native_vector([.25]*4),'posterior':native_vector([.1,.2,.3,.4])},
        'model_vectors':{'prior_models':native_vector([.25]*4),
                         'posterior_models':native_vector([.1,.2,.3,.4]),
                         'logml':native_vector([-5.0,-4.0,-3.0,-2.0])},
        'pairwise_BF':{'dimensions':[4,4],'storage_type':'double','dimension_axis_names':None,
                       'dimension_labels':[['a','b','c','d'],['a','b','c','d']],
                       'values_by_row':[[native_cell(i*4+j+.125) for j in range(4)] for i in range(4)]},
        'native_names_or_absence_preserved':True,'numerical_repair_performed':False}


def generated_bundle(root):
    """RDS bytes are opaque invented fixtures; tests make no native-serialization claim."""
    doc = prior_fixtures.generated_document()
    ledger = generated_ledger(doc)
    runtime = {'R_version':'4.3.2','evaluated_expression_count':57,
               'full120_frozen_before_Bayesian_mutations':True}
    for i, name in enumerate(contract.REQUIRED_ARTIFACTS):
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        if name == 'full120.json':
            raw = base.json_bytes(doc)
        elif name == 'row_lineage.json':
            raw = base.json_bytes(ledger)
        elif name == 'runtime.json':
            raw = base.json_bytes(runtime)
        elif name.endswith('.png'):
            raw = generated_png()
        elif name.endswith('.json'):
            # Generated mapped exports exercise the Python semantic boundary too.
            contrast=Path(name).stem
            row=next(row for row in ledger['contrasts'] if row['contrast']==contrast)
            export=generated_forest(row) if name.startswith('dl/') else generated_bayes(row)
            raw=base.json_bytes(export)
        else:
            raw = ('GENERATED ONLY '+name+'\n').encode()
        path.write_bytes(raw)
    return doc


def generated_manifest():
    return [{'phase':phase,'start':a,'end':b,'sha256':f'{a:064x}'}
            for phase,spans in contract.PHASES.items() for a,b in spans]


class GeneratedCompanionControls(unittest.TestCase):
    def check(self, root, limit=1_000_000):
        return contract.check_bundle(root, 'A', limit, base)

    def test_predecessor_pins_match_frozen_code(self):
        loaded = contract.load_predecessor()
        self.assertEqual(loaded.PINS['script'][0], 'caa4ac8a0ee84821c19df5fc26c4a7527ef164c6f48f19e2deed3d0a888cd334')
        self.assertEqual(contract.PREDECESSOR_COMMIT, '9701e99e181f1f8056a5c6f2849eb56977a37bcb')

    def test_predecessor_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            originals = {name:(contract.PREDECESSOR/name).read_bytes() for name in contract.PREDECESSOR_PINS}
            for bad in originals:
                with self.subTest(file=bad):
                    for name,raw in originals.items():
                        (root/name).write_bytes(raw + (b'\n' if name==bad else b''))
                    with patch.object(contract, 'PREDECESSOR', root):
                        with self.assertRaisesRegex(ValueError, 'predecessor_identity'):
                            contract.load_predecessor()

    def test_exact_source_phase_universe(self):
        self.assertEqual({key:len(value) for key,value in contract.PHASES.items()},
                         {'libraries':8,'core_DL':16,'table1':5,'forests':9,'Bayesian':19})
        spans = [span for group in contract.PHASES.values() for span in group]
        self.assertEqual(len(spans), 57)
        self.assertEqual(len(set(spans)), 57)
        for forbidden in (193,470,474,482,625):
            self.assertFalse(any(a<=forbidden<=b for a,b in spans))
        self.assertEqual(contract.PHASES['libraries'][-1], (23,23))
        self.assertEqual(contract.PHASES['table1'], [(31,67),(377,377),(379,379),(380,380),(381,381)])

    def test_source_manifest_is_bound_to_exact_bytes(self):
        raw = ''.join(f'# generated line {i}\n' for i in range(1,626)).encode()
        with patch.dict(base.PINS, {'script':(contract.digest(raw),len(raw))}):
            manifest = contract.source_manifest(raw,base)
            self.assertEqual(len(manifest),57)
            table = next(row for row in manifest if row['start']==31)
            self.assertEqual(table['sha256'],contract.digest(b''.join(raw.splitlines(keepends=True)[30:67])))
            with self.assertRaisesRegex(ValueError,'original_source_identity'):
                contract.source_manifest(raw+b' ',base)

    def test_complete_generated_artifact_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); generated_bundle(root)
            inventory,doc,runtime = self.check(root)
            self.assertEqual(len(inventory),26)
            self.assertEqual(set(inventory),set(contract.REQUIRED_ARTIFACTS))
            self.assertEqual(len(doc['contrasts']),3)
            self.assertEqual(runtime['evaluated_expression_count'],57)
            for name in contract.FIGURES.values():
                self.assertEqual(inventory[name]['png_dimensions'],[1,1])

    def test_each_artifact_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); generated_bundle(root)
            for name in contract.REQUIRED_ARTIFACTS:
                with self.subTest(artifact=name):
                    path = root/name; raw = path.read_bytes(); path.unlink()
                    with self.assertRaisesRegex(ValueError,'artifact_closure'):
                        self.check(root)
                    path.write_bytes(raw)

    def test_extra_empty_and_symlink_artifacts_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'bundle'; root.mkdir(); generated_bundle(root)
            extra = root/'extra'; extra.write_bytes(b'bad')
            with self.assertRaises(ValueError): self.check(root)
            extra.unlink()
            path = root/'dl/quest_self.rds'; raw=path.read_bytes();path.write_bytes(b'')
            with self.assertRaisesRegex(ValueError,'empty_native_artifact'): self.check(root)
            path.unlink(); target=Path(tmp)/'outside';target.write_bytes(raw);path.symlink_to(target)
            with self.assertRaisesRegex(ValueError,'regular_artifact_required'): self.check(root)

    def test_artifact_budget_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);generated_bundle(root)
            size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
            self.check(root,size)
            with self.assertRaisesRegex(ValueError,'artifact_byte_limit'):
                self.check(root,size-1)

    def test_png_requires_valid_chunks_and_compressed_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);generated_bundle(root);path=root/next(iter(contract.FIGURES.values()))
            valid=generated_png()
            variants=[b'not a PNG',valid[:-1],valid+b'trailing',generated_png(0,1)]
            corrupted=bytearray(valid);corrupted[29]^=1;variants.append(bytes(corrupted))
            bad_data=(b'\x89PNG\r\n\x1a\n'+png_chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))
                      +png_chunk(b'IDAT',b'not zlib')+png_chunk(b'IEND',b''))
            variants.append(bad_data)
            for i,raw in enumerate(variants):
                with self.subTest(case=i):
                    path.write_bytes(raw)
                    with self.assertRaises(Exception): self.check(root)

    def test_all_json_transport_is_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);generated_bundle(root)
            for name in contract.REQUIRED_ARTIFACTS:
                if not name.endswith('.json'): continue
                path=root/name;original=path.read_bytes()
                for raw in (b'{broken',b'{"x":1,"x":2}',b'{"x":NaN}'):
                    with self.subTest(artifact=name,raw=raw):
                        path.write_bytes(raw)
                        with self.assertRaises(Exception):self.check(root)
                path.write_bytes(original)

    def test_row_ledger_must_equal_validated_full120(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);doc=generated_bundle(root);path=root/'row_lineage.json'
            for kind in ('reorder','label','n_column','Bayesian_n','native_model','native_subset',
                         'Bayesian_input','contrast_missing'):
                ledger=generated_ledger(doc)
                if kind=='reorder':ledger['contrasts'][0]['membership'].reverse()
                if kind=='label':ledger['contrasts'][0]['membership'][0]['author_label']='wrong'
                if kind=='n_column':ledger['contrasts'][2]['dl_n_column']='sample size quest'
                if kind=='Bayesian_n':ledger['contrasts'][2]['bayes_n_column']='sample size rating'
                if kind=='native_model':ledger['contrasts'][0]['native_model']='meta_amySelf'
                if kind=='native_subset':ledger['contrasts'][0]['native_subset']='dfAmySelf'
                if kind=='Bayesian_input':ledger['contrasts'][0]['bayes_input_object']='dfAmySelf_conv'
                if kind=='contrast_missing':ledger['contrasts'].pop()
                path.write_bytes(base.json_bytes(ledger))
                with self.subTest(kind=kind),self.assertRaises(Exception):self.check(root)

    def test_runtime_phase_and_version_completion_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);generated_bundle(root);path=root/'runtime.json';original=json.loads(path.read_text())
            for key,value in [('R_version','4.4.0'),('evaluated_expression_count',56),
                              ('full120_frozen_before_Bayesian_mutations',False)]:
                record=original.copy();record[key]=value;path.write_bytes(base.json_bytes(record))
                with self.subTest(field=key),self.assertRaises(Exception):self.check(root)

    def test_native_export_identity_and_lineage_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);generated_bundle(root)
            for kind in ('dl','bayes'):
                path=root/kind/'quest_self.json';original=json.loads(path.read_text())
                mutations=[('contrast','amy_self'),('native_model','wrong')]
                if kind=='dl':
                    mutations.extend([('membership',list(reversed(original['membership']))),
                                      ('studlab',list(reversed(original['studlab'])))])
                for key,value in mutations:
                    changed=copy.deepcopy(original);changed[key]=value;path.write_bytes(base.json_bytes(changed))
                    with self.subTest(kind=kind,key=key),self.assertRaises(Exception):self.check(root)
                path.write_bytes(base.json_bytes(original))

    def test_missing_runtime_does_not_launch_or_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=self.arguments(Path(tmp)/'out');args.rscript='missing-generated-Rscript'
            with patch.object(contract,'load_predecessor',return_value=base), \
                 patch.object(base,'public_contract',return_value=public), \
                 patch.object(base,'read_pinned',return_value=b'GENERATED SOURCE'), \
                 patch.object(contract,'source_manifest',return_value=generated_manifest()), \
                 patch.object(replay.subprocess,'run') as launch:
                with self.assertRaisesRegex(ValueError,'Rscript_missing'):
                    replay.run(args)
                launch.assert_not_called()
                self.assertFalse(Path(args.output_directory).exists())

    def test_explicit_positive_bounds_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            for field in ('timeout_seconds','artifact_byte_limit'):
                for i,value in enumerate((0,True,1.5)):
                    args=self.arguments(Path(tmp)/f'{field}-{i}')
                    setattr(args,field,value)
                    with patch.object(contract,'load_predecessor',return_value=base), \
                         patch.object(base,'public_contract',return_value=public), \
                         patch.object(base,'read_pinned',return_value=b'GENERATED SOURCE'), \
                         patch.object(contract,'source_manifest',return_value=generated_manifest()), \
                         patch.object(replay.subprocess,'run') as launch:
                        with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,'positive_explicit'):
                            replay.run(args)
                        launch.assert_not_called()
                        self.assertFalse(Path(args.output_directory).exists())

    def arguments(self, output):
        return argparse.Namespace(original_workbook='generated',official_script='generated',renv_lock='generated',
            rscript=sys.executable,runtime_identity='GENERATED MOCK ONLY',arm='A',output_directory=str(output),
            timeout_seconds=1,artifact_byte_limit=1_000_000)

    def mock_pipeline(self, mode):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'out';args=self.arguments(output)
            expected_partial=b'GENERATED PARTIAL FOREST PNG'
            original_publish=base.publish_new
            def fake_launch(command,*,cwd,env,**kwargs):
                self.assertEqual(command[1],'--vanilla')
                self.assertEqual((cwd/'data/studyInformation/studyInformation_publication.xlsx').read_bytes(),b'GENERATED SOURCE')
                self.assertEqual(env['OMP_NUM_THREADS'],'1')
                self.assertEqual(len(json.loads((cwd/'job.json').read_text())['expressions']),57)
                if mode=='partial_png':
                    path=cwd/next(iter(contract.FIGURES.values()));path.write_bytes(expected_partial)
                    raise subprocess.TimeoutExpired(command,1,output=b'partial stdout',stderr=b'partial stderr')
                generated_bundle(cwd/'out')
                if mode=='timeout':raise subprocess.TimeoutExpired(command,1,output=b'partial stdout',stderr=b'partial stderr')
                if mode=='launch_error':raise OSError('generated launch failure')
                if mode=='invalid':(cwd/'out/full120.json').write_bytes(b'INVALID GENERATED JSON')
                if mode=='budget':args.artifact_byte_limit=137
                return subprocess.CompletedProcess(command,1 if mode=='nonzero' else 0,b'generated stdout',b'generated stderr')
            def publisher(path,raw):
                if mode=='publication' and Path(path).name=='MANIFEST.json':
                    raise OSError('generated manifest publication failure')
                return original_publish(path,raw)
            with patch.object(contract,'load_predecessor',return_value=base), \
                 patch.object(base,'public_contract',return_value=public), \
                 patch.object(base,'read_pinned',return_value=b'GENERATED SOURCE'), \
                 patch.object(contract,'source_manifest',return_value=generated_manifest()), \
                 patch.object(base,'publish_new',side_effect=publisher), \
                 patch.object(replay.subprocess,'run',side_effect=fake_launch) as launch:
                if mode=='success':
                    manifest=replay.run(args)
                    self.assertEqual(len(manifest['artifacts']),26)
                    self.assertFalse(manifest['complete_primary_success'])
                    self.assertFalse(manifest['companion_scientific_comparison_performed'])
                    provenance=(output/'PROVENANCE.json').read_bytes()
                    self.assertEqual(manifest['provenance']['sha256'],contract.digest(provenance))
                    self.assertEqual(json.loads((output/'MANIFEST.json').read_text()),manifest)
                    self.assertTrue(json.loads(provenance)['artifact_bundle_complete'])
                else:
                    with self.assertRaises(Exception):replay.run(args)
                    self.assertFalse((output/'MANIFEST.json').exists())
                    failure=output/'FAILURE.json'
                    if not failure.exists():failure=output/'PROVENANCE.json'
                    record=json.loads(failure.read_text())
                    self.assertFalse(record['artifact_bundle_complete'])
                    self.assertFalse(record['complete_primary_success'])
                    self.assertFalse(record['scientific_agreement_assessed'])
                    self.assertTrue(record['rejected_native_files'])
                    if mode=='partial_png':
                        name=next(iter(contract.FIGURES.values()))
                        self.assertEqual((output/'REJECTED_NATIVE'/name).read_bytes(),expected_partial)
                    if mode in ('timeout','partial_png'):
                        self.assertEqual(base64.b64decode(record['stdout']['base64']),b'partial stdout')
                    retained=sum(p.stat().st_size for p in output.rglob('*') if p.is_file()
                                 and p.name not in ('MANIFEST.json','PROVENANCE.json','FAILURE.json'))
                    self.assertLessEqual(retained,args.artifact_byte_limit)
                launch.assert_called_once()
                self.assertFalse(any(p.name.startswith('.private-stage-') for p in output.iterdir()))

    def test_mocked_pipeline_success(self):
        self.mock_pipeline('success')

    def test_mocked_pipeline_failure_evidence(self):
        for mode in ('timeout','launch_error','nonzero','invalid','publication','partial_png','budget'):
            with self.subTest(mode=mode):self.mock_pipeline(mode)

    def test_existing_output_directory_is_not_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'out';output.mkdir();(output/'sentinel').write_bytes(b'previous evidence')
            args=self.arguments(output)
            with patch.object(contract,'load_predecessor',return_value=base), \
                 patch.object(base,'public_contract',return_value=public), \
                 patch.object(base,'read_pinned',return_value=b'GENERATED SOURCE'), \
                 patch.object(contract,'source_manifest',return_value=generated_manifest()), \
                 patch.object(replay.subprocess,'run') as launch:
                with self.assertRaisesRegex(ValueError,'new_output_directory_required'):replay.run(args)
                launch.assert_not_called()
            self.assertEqual((output/'sentinel').read_bytes(),b'previous evidence')



class NativeExportSemanticsControls(unittest.TestCase):
    def setUp(self):
        self.reference=prior_fixtures.generated_document()['contrasts'][0]
        self.row=generated_ledger({'task':'PAPER-EXP-20261113-003','workbook_sha256':'generated',
                                  'contrasts':[self.reference]})['contrasts'][0]
        self.decoder,_=base.load_validator(public)

    def decoded(self, value):
        return self.decoder.decode_numeric_json(base.json_bytes(value))

    def forest(self, value):
        contract.check_forest_export(self.decoded(value), self.decoded(self.reference), self.row['native_model'])

    def bayes(self, value):
        contract.check_bayes_export(self.decoded(value), self.row['contrast'], self.row['native_model'])

    def test_every_forest_vector_is_complete_and_source_scaled(self):
        initial=generated_forest(self.row);self.forest(initial)
        for key in ('cor','n','TE','seTE','lower','upper','w.common','w.random'):
            for mutation in ('missing','short','declared','wrong_scale','names'):
                value=copy.deepcopy(initial)
                if mutation=='missing':del value['vectors'][key]
                if mutation=='short':value['vectors'][key]['values'].pop()
                if mutation=='declared':value['vectors'][key]['length']-=1
                if mutation=='wrong_scale':value['scales'][key]='percent'
                if mutation=='names':value['vectors'][key]['names']=['incomplete']
                with self.subTest(key=key,mutation=mutation),self.assertRaises(ValueError):self.forest(value)
        for key,value in [('transformation_performed',True),('source_order','sorted_alphabetically')]:
            changed=copy.deepcopy(initial);changed[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.forest(changed)

    def test_explicit_native_states_preserved_without_repair(self):
        for state in ('NA','NaN','+Inf','-Inf'):
            value=generated_forest(self.row);value['vectors']['TE']['values'][0]={'state':state}
            before=copy.deepcopy(value);self.forest(value);self.assertEqual(value,before)
        invalid=[None,True,0.25,{'state':'finite','value':True},
                 {'state':'finite','value':'0.25'},{'state':'missing'},
                 {'state':'NA','value':0},{'state':'finite','value':0,'extra':1}]
        for cell in invalid:
            value=generated_forest(self.row);value['vectors']['TE']['values'][0]=cell
            with self.subTest(cell=cell),self.assertRaises(ValueError):self.forest(value)
        value=generated_forest(self.row);value['vectors']['TE']['storage_type']='integer'
        value['vectors']['TE']['values'][0]=native_cell(.5)
        with self.assertRaisesRegex(ValueError,'integer_storage'):self.forest(value)

    def test_integer_storage_matches_native_R_domain(self):
        for kind in ('forest', 'pairwise_BF'):
            def value_with(cell):
                if kind == 'forest':
                    value=generated_forest(self.row)
                    value['vectors']['TE']=native_vector([0]*len(self.row['membership']),storage='integer')
                    value['vectors']['TE']['values'][0]=cell
                    return value,self.forest
                value=generated_bayes(self.row)
                matrix=value['pairwise_BF'];matrix['storage_type']='integer'
                matrix['values_by_row']=[[native_cell(i*4+j) for j in range(4)] for i in range(4)]
                matrix['values_by_row'][0][0]=cell
                return value,self.bayes
            for cell in ({'state':'NA'},native_cell(-2147483647),native_cell(0),native_cell(2147483647)):
                value,check=value_with(cell)
                with self.subTest(kind=kind,valid=cell):check(value)
            invalid=[{'state':state} for state in ('NaN','+Inf','-Inf')]
            invalid.extend(native_cell(number) for number in (-2147483648,2147483648,.5))
            for cell in invalid:
                value,check=value_with(cell)
                with self.subTest(kind=kind,invalid=cell),self.assertRaises(ValueError):check(value)

    def test_native_names_and_missing_labels_remain_optional(self):
        value=generated_forest(self.row);n=len(self.row['membership'])
        value['vectors']['TE']['names']=[None]+['same']*(n-1)
        self.forest(value)
        value=generated_bayes(self.row);value['pairwise_BF']['dimension_labels']=[None,['same',None,'same','']]
        value['pairwise_BF']['dimension_axis_names']=['',None]
        before=copy.deepcopy(value);self.bayes(value);self.assertEqual(value,before)
        for bad in ([],['one'],[[1,2,3,4],None]):
            value=generated_bayes(self.row);value['pairwise_BF']['dimension_labels']=bad
            with self.subTest(labels=bad),self.assertRaises(ValueError):self.bayes(value)

    def test_inclusion_BF_cannot_be_replaced_by_pairwise_matrix(self):
        initial=generated_bayes(self.row);self.bayes(initial)
        for mutation in ('matrix_as_scalar','positions','role','order','repair','names_flag'):
            value=copy.deepcopy(initial)
            if mutation=='matrix_as_scalar':value['inclusion']['incl.BF']=value['pairwise_BF']
            if mutation=='positions':value['inclusion']['include']['values']=[native_cell(1),native_cell(3)]
            if mutation=='role':value['inclusion_BF_role']='pairwise_BF'
            if mutation=='order':value['documented_positional_model_order'].reverse()
            if mutation=='repair':value['numerical_repair_performed']=True
            if mutation=='names_flag':value['native_names_or_absence_preserved']=1
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.bayes(value)

    def test_bayesian_vector_and_matrix_extents_are_independently_checked(self):
        initial=generated_bayes(self.row)
        for key in ('prior_models','posterior_models','logml'):
            value=copy.deepcopy(initial);value['model_vectors'][key]['values'].pop()
            with self.subTest(vector=key),self.assertRaises(ValueError):self.bayes(value)
        for mutation in ('dimensions','rows','columns','axis_names','integer_cell','cell'):
            value=copy.deepcopy(initial);matrix=value['pairwise_BF']
            if mutation=='dimensions':matrix['dimensions']=[4,3]
            if mutation=='rows':matrix['values_by_row'].pop()
            if mutation=='columns':matrix['values_by_row'][0].pop()
            if mutation=='axis_names':matrix['dimension_axis_names']=['single']
            if mutation=='integer_cell':matrix['storage_type']='integer'
            if mutation=='cell':matrix['values_by_row'][0][1]={'state':'finite','value':False}
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.bayes(value)
        before=copy.deepcopy(initial);self.bayes(initial);self.assertEqual(before,initial)
        self.assertNotEqual(initial['pairwise_BF']['values_by_row'][0][1],initial['pairwise_BF']['values_by_row'][1][0])

    def test_bundle_rejects_previously_accepted_identity_only_stubs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);generated_bundle(root)
            for kind in ('dl','bayes'):
                path=root/kind/'quest_self.json';original=path.read_bytes();value=json.loads(original)
                keys={'schema','contrast','native_model','membership','studlab'}
                path.write_bytes(base.json_bytes({k:v for k,v in value.items() if k in keys}))
                with self.subTest(kind=kind),self.assertRaises(ValueError):
                    contract.check_bundle(root,'A',1_000_000,base)
                path.write_bytes(original)

if __name__=='__main__':
    unittest.main(verbosity=2)
