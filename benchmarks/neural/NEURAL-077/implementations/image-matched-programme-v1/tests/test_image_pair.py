"""Finite generated controls for image/programme matching, never study results.

The complete fake arm retains all400 production slots. Rendering, provider
execution, OS enforcement, public NPZ decoding and private scoring are explicitly
injected fixture authorities where documented; no protected source data is read.
Source authentication, new admission, matching and compare ordering remain real.
"""
from __future__ import annotations
import base64
import copy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest import mock
import zlib

HERE = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get('N077_IMPLEMENTATIONS_ROOT', str(HERE.parent))).absolute()
FIXTURE_LIMIT = 2 * 1024**2
WRITTEN = 0
VIRTUAL_BYTES = 0
VIRTUAL_FRAME_READS = 0
VIRTUAL_FRAME_MAX = 0
VIRTUAL_READ_CAP = 28 * 1024**2
OBSERVATIONS = []


def module(name, path):
    raw = path.read_bytes()
    value = types.ModuleType(name); value.__file__ = str(path); sys.modules[name] = value
    exec(compile(raw, str(path), 'exec', dont_inherit=True), value.__dict__)
    return value


pair = module('n077_image_pair_generated_controls', ROOT / 'image-matched-programme-v1/pair.py')


def put(path, body):
    global WRITTEN
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    if WRITTEN + len(body) > FIXTURE_LIMIT:
        raise ValueError('Generated fixture cumulative artifact allowance exceeded')
    path.write_bytes(body); WRITTEN += len(body)
    return pair.pin(body)


def png():
    def chunk(kind, body):
        return struct.pack('!I', len(body)) + kind + body + struct.pack('!I', zlib.crc32(kind + body) & 0xffffffff)
    scans = (b'\0' + bytes([0]) * (1400 * 3)) * 820
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 1400, 820, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(scans, 9)) + chunk(b'IEND', b''))


class ImageProgrammeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deps = pair.dependencies(ROOT)
        explicit = os.environ.get('ARTIFACT_DIR')
        cls.owner = None
        if explicit:
            cls.output = Path(explicit).absolute()
        else:
            cls.owner = tempfile.TemporaryDirectory(prefix='n077-image-pair-generated-')
            cls.output = Path(cls.owner.name).resolve()
        for path in (cls.output, *cls.output.parents):
            if path.is_symlink(): raise ValueError('Unlinked external artifacts required')
        for source in (HERE, ROOT):
            if cls.output.is_relative_to(source) or source.is_relative_to(cls.output):
                raise ValueError('Artifact/source trees must be disjoint')
        cls.output.mkdir(parents=True, exist_ok=True, mode=0o700)
        cls.pixels = png()
        cls.ids = [f'development-{1+i//200:03d}-{i:024x}' for i in range(400)]
        cls.arm_fixture = None

    @classmethod
    def tearDownClass(cls):
        put(cls.output / 'GENERATED_CONTROL_SCOPE.json', pair.encode({
            'generated_fixture_only': True, 'observations': OBSERVATIONS,
            'put_helper_cumulative_written_bytes_before_receipt': WRITTEN,
            'put_helper_write_cap_bytes': FIXTURE_LIMIT,
            'operator_write_bytes': 'pair.write result/failure/temp outputs are separately metered by campaign owner',
            'in_memory_serialized_read_bytes': VIRTUAL_BYTES,
            'in_memory_initial_frame_reads': VIRTUAL_FRAME_READS,
            'maximum_initial_frame_bytes': VIRTUAL_FRAME_MAX,
            'in_memory_read_cap_bytes': VIRTUAL_READ_CAP,
            'physical_source_fixture_reads': 'separately metered by campaign owner',
            'generated_scanline_construction_bytes': 3444820,
            'production_count_unchanged': pair.COUNT == 400,
            'provider_calls': 0, 'original_packet_reads': 0, 'private_labels_opened': 0,
            'os_enforcement_qualified': False, 'scientific_qualification': False,
            'injected_primitives': ['provider admission for explicitly generated arm',
                'renderer/process replay for generated complete programme fixture',
                'public NPZ decoder/validator for generated complete fixture',
                'private scoring callback; original metrics never run']}))
        if cls.owner is not None: cls.owner.cleanup()

    def location(self, name):
        path = self.output / name
        path.mkdir(mode=0o700)
        return path

    def contract(self, root):
        d = self.deps
        source = root / 'candidate'; source.mkdir()
        put(source / 'image_candidate.py', b'def main():\n    return 0\n')
        put(source / 'config.json', b'{"generated_fixture_only":true}\n')
        declaration = {'schema':'neural077_python_bundle_v1','entry_module':'image_candidate',
                       'modules':['image_candidate.py'],'config':'config.json'}
        frozen = d['bundle'].capture(source, declaration)
        limits = asdict(d['transport'].Limits(wall_seconds=30))
        protected = root / 'private'; protected.mkdir()
        packet_members = {'generated_packet':pair.pin(b'GENERATED_NO_ORIGINAL_PACKET')}
        c = {'schema':'neural077_image_programme_frozen_v1','condition':pair.CONDITION,
             'queries':400,'demonstrations':4,'source':d['identity'],
             'packet_path':str(protected / 'packet'), 'packet_members':packet_members,
             'bundle':frozen,
             'exposure':{'schema':'neural077_image_programme_exposure_v1',
                 'statement':'Generated source-control fixture; no EEG or provider output accessed.',
                 'held_query_access_declared':False,'provider_output_access_declared':False},
             'exposure_scope':'operator_declaration_not_hidden_pretraining_proof',
             'runtime':{'path':'/usr/bin/generated-fixture-runtime',**pair.pin(b'generated-runtime')},
             'sandbox_executable':{'path':'/usr/bin/sandbox-exec',**pair.pin(b'generated-sandbox')},
             'protected_roots':[str(protected)], 'limits':limits, 'campaign_seconds':1000,
             'max_artifact_bytes':1048576, 'frozen_monotonic':10.0,
             'clock_scope':'trusted_operator_same_host_monotonic',
             'permission_adapter':d['image_transport'].participant_permission_adapter,
             'compare_derivation':d['compare_derivation'], 'scientific_qualification':False}
        commitment = {k:v for k,v in c.items() if k != 'frozen_monotonic'}
        c['commitment'] = put(root / 'COMMITMENT.json', pair.encode(commitment))
        frozen_file = root / 'FROZEN.json'; frozen_pin = put(frozen_file, pair.encode(c))
        return c, frozen_file, frozen_pin, d['bundle'].verify(frozen)

    def information(self, c):
        packet = {k:v['sha256'] for k,v in c['packet_members'].items()}
        data = {'packet':packet,'rows':[{'trial_id':x} for x in self.ids]}
        a = {'packet':packet,'queries':400,'demonstrations':4,
             'limits':{'transport':c['limits']},'started_monotonic':20.0}
        b = {'packet':packet,'queries':400,'demonstrations':4,
             'limits':c['limits'],'started_monotonic':30.0}
        return data, a, b

    def frames(self, c, provider_root, programme_root, *, a_manifest=None, b_manifest=None, mutate=None):
        """Generated complete400 frame/receipt authority; no original source data."""
        t = self.deps['transport']; image = self.deps['image_transport']
        viewer = t.v; limits = t.Limits(**c['limits'])
        context = types.SimpleNamespace(query={'trial_id':self.ids[0]},
                    prompt=viewer.scientific_prompt(self.ids[0], 'four_demo'))
        initial = {'status':'rendered','display':viewer.display_metadata(viewer.initial_state(), {}),
                   'remaining_actions':limits.max_actions-1,
                   'image':{'mime_type':'image/png','bytes':len(self.pixels)}}
        native = t.ready_header(context, limits, '0'*32); native['initial']=initial
        programme = image.ready_header(context, limits, '1'*32); programme['initial']=copy.deepcopy(initial)
        if a_manifest is None or b_manifest is None:
            _,a_manifest,b_manifest=self.information(c)
        def frame(ordinal,is_b,apply_mutation=False):
            identifier=self.ids[ordinal]
            header=copy.deepcopy(programme if is_b else native)
            header['trial_id']=identifier
            prompt=viewer.scientific_prompt(identifier,'four_demo')
            header['prompt']=self.deps['adapter'].programme_prompt(prompt) if is_b else prompt
            header['episode_id']=f'{ordinal+(400 if is_b else 0):032x}'
            pixels=self.pixels
            if apply_mutation and mutate is not None:header,pixels=mutate(header,pixels,is_b,ordinal)
            body=t.wire(header,pixels)
            if len(body)>8192:raise ValueError('Generated frame exceeds selected8KiB read quote')
            return body
        a_manifest_body=pair.encode(a_manifest);b_manifest_body=pair.encode(b_manifest)
        client_ends=[pair.encode({'initial_frame':pair.pin(frame(i,False))}) for i in range(400)]
        initials=[pair.pin(frame(i,True)) for i in range(400)]
        a_arm=pair.encode({'manifest':pair.pin(a_manifest_body),
            'episodes':[{'client_end':pair.pin(body)} for body in client_ends]})
        b_arm=pair.encode({'manifest':pair.pin(b_manifest_body),'initial_frames':initials})
        seen=[]
        def read(path,cap=1048576,expected=None):
            global VIRTUAL_BYTES, VIRTUAL_FRAME_READS, VIRTUAL_FRAME_MAX
            path=Path(path);is_b=path.is_relative_to(programme_root)
            if not (path.is_relative_to(provider_root) or is_b):
                raise AssertionError('Unexpected read beyond generated frame custody')
            if path.name=='ARM.json':body=b_arm if is_b else a_arm
            elif path.name=='MANIFEST.json' and path.parent in (provider_root,programme_root):
                body=b_manifest_body if is_b else a_manifest_body
            elif path.name=='CLIENT_END.json' and not is_b:
                body=client_ends[int(path.parent.parent.name)]
            elif path.name=='0000-out.bin':
                ordinal=int(path.parent.parent.name);seen.append((is_b,ordinal))
                body=frame(ordinal,is_b,True)
            else:raise AssertionError('Unexpected read beyond initial-image/custody matching seam')
            if VIRTUAL_BYTES+len(body)>VIRTUAL_READ_CAP:raise ValueError('Cumulative generated serialized read cap')
            VIRTUAL_BYTES+=len(body)
            if path.name=='0000-out.bin':
                VIRTUAL_FRAME_READS+=1;VIRTUAL_FRAME_MAX=max(VIRTUAL_FRAME_MAX,len(body))
            if len(body)>cap:raise ValueError('Generated read bound')
            if expected is not None and pair.pin(body)!=expected:raise ValueError('Committed content changed')
            return body
        return read,seen,{'a_receipt':pair.pin(a_arm),'b_receipt':pair.pin(b_arm),
                         'a_arm':a_arm,'initial_frames':initials}

    def generated_arm(self):
        if self.__class__.arm_fixture is not None: return self.__class__.arm_fixture
        root=self.location('complete-generated400')
        c,frozen_file,frozen_pin,client=self.contract(root)
        provider=root/'provider';provider.mkdir()
        programme=root/'programme';programme.mkdir();(programme/'sessions').mkdir()
        data,am,bm=self.information(c)
        data.update(parser=self.deps['original']['parser'])
        validation=[]
        def validate(path, ids):
            self.assertEqual(sum(map(len,ids.values())),400)
            validation.append('generated-public-validation')
        data['validator']=types.SimpleNamespace(validate=validate)
        put(programme/'CLIENT.py',client)
        bm.update(schema='neural077_image_programme_campaign_v1',condition=pair.CONDITION,
                  contract=frozen_pin,source=self.deps['identity'],deadline=1030.0,
                  client=pair.pin(client),runtime=c['runtime'],sandbox_executable=c['sandbox_executable'],
                  sandbox='macos',retry_policy='none',private_target_reads=0,scoring_performed=False)
        manifest_pin=put(programme/'MANIFEST.json',pair.encode(bm))
        put(provider/'MANIFEST.json',pair.encode(am))
        initial_reader,_,authority=self.frames(c,provider,programme,a_manifest=am,b_manifest=bm)
        put(provider/'ARM.json',authority['a_arm'])
        ends=[]
        for i,identifier in enumerate(self.ids):
            session=programme/'sessions'/f'{i:03d}'
            ends.append(put(session/'transport/END.json',pair.encode({'generated_fixture_only':True,'ordinal':i})))
            put(session/'transport/MANIFEST.json',pair.encode({'episode_id':f'{i:032x}'}))
            put(session/'response.txt',pair.encode({'trial_id':identifier,'target_probability':0.5}))
        submission=put(programme/'collection/submission.npz',b'GENERATED_ARCHIVE_PLACEHOLDER')
        collection={'schema':'neural077_transport_collection_v1','status':'complete_unscored_transport_collection',
                    'queries':400,'condition':'four_demo','submission_sha256':submission['sha256'],'scoring_performed':False,
                    'configuration_sha256':pair.pin(pair.encode({}))['sha256'],
                    'performance_claim':'none','provider_qualification':'not_established'}
        cp=put(programme/'collection/TRANSPORT_COMPLETE.json',pair.encode(collection))
        arm={'schema':'neural077_image_programme_arm_v1','status':'closed_unscored_image_programme_arm',
             'condition':pair.CONDITION,'queries':400,'demonstrations':4,'sandbox':'macos',
             'private_target_reads':0,'scoring_performed':False,'os_enforcement_independently_qualified':False,
             'scientific_qualification':False,'contract':frozen_pin,'manifest':manifest_pin,'episodes':ends,
             'collection':cp,'submission':submission,'finished_monotonic':31.0,
             'initial_frames':authority['initial_frames']}
        receipt=put(programme/'ARM.json',pair.encode(arm))
        private=Path(c['protected_roots'][0])/'locations.json'
        put(private,pair.encode({'schema':'neural077_pair_private_locations_v1',
            'reference_grade':str(private.parent/'generated-reference-grade'),
            'reference_commit':str(private.parent/'generated-reference-commit'),
            'targets':{case:str(private.parent/(case+'.generated-labels')) for case in self.deps['original']['pair'].CASES}}))
        ids=self.ids
        class Array:
            def __init__(self,values):self.values=values
            def tolist(self):return self.values
        class Archive:
            files=['trial_ids','target_probability']
            def __enter__(self):return self
            def __exit__(self,*unused):return False
            def __getitem__(self,key):return Array(ids) if key=='trial_ids' else [0.5]*400
        numpy=types.SimpleNamespace(load=lambda *a,**k:Archive(),asarray=lambda values,**k:values,
                                   array_equal=lambda left,right:left==right,float64=float)
        value=types.SimpleNamespace(root=root,c=c,frozen=frozen_file,frozen_pin=frozen_pin,client=client,
            provider=provider,programme=programme,data=data,am=am,bm=bm,arm=arm,receipt=receipt,
            private=private,np=numpy,validation=validation,initial_reader=initial_reader,
            provider_receipt=authority['a_receipt'])
        self.__class__.arm_fixture=value
        return value

    def test_01_frozen_programme_and_dependency_drift_precede_packet_access(self):
        root=self.location('drift');c,frozen,expected,client=self.contract(root)
        original=frozen.read_bytes()
        put(root/'candidate/image_candidate.py',b'def main():\n    return 1\n')
        put(root/'candidate/config.json',b'{"generated_fixture_only":false}\n')
        changed=copy.deepcopy(c)
        changed['bundle']=self.deps['bundle'].capture(root/'candidate',c['bundle']['manifest'])
        self.assertNotEqual(changed['bundle']['bundle_identity'],c['bundle']['bundle_identity'])
        put(frozen,pair.encode(changed))
        with mock.patch.object(pair,'dependencies',return_value=self.deps),mock.patch.object(pair,'packet_data') as packet:
            with self.assertRaisesRegex(ValueError,'Committed content changed'):
                pair.run_programme(frozen,expected,root/'never-launched')
            packet.assert_not_called()
        put(frozen,original)
        drift=copy.deepcopy(self.deps['identity']);drift['own']['adapters.py']['sha256']='0'*64
        with mock.patch.object(pair,'dependencies',return_value=self.deps),\
             mock.patch.object(pair,'source_identity',return_value=(drift,{},{})),\
             mock.patch.object(pair,'packet_data') as packet:
            with self.assertRaisesRegex(ValueError,'Committed source changed'):
                pair.run_programme(frozen,expected,root/'never-launched')
            packet.assert_not_called()
        altered=self.deps['donor_transport_body']+b'\n'
        with self.assertRaisesRegex(ValueError,'Exact authenticated donor transport body'):
            self.deps['adapter'].make_transport(dict(self.deps,donor_transport_body=altered),
                                                self.deps['identity']['own']['adapters.py'])
        OBSERVATIONS.append({'control':'freeze_and_dependency_drift','packet_loads':0})

    def test_02_initial_images_permissions_and_donor_state_are_matched(self):
        d=self.deps;t=d['transport'];root=self.location('information');c,_,_,_=self.contract(root)
        data,am,bm=self.information(c);a=root/'provider';b=root/'programme'
        prompt=t.v.scientific_prompt(self.ids[0],'four_demo')
        donor_functions={name:getattr(t,name) for name in ('ready_header','run_episode','audit_transport','collect')}
        old_conditions=d['original']['pair'].CONDITIONS
        derived=d['adapter'].make_transport(d,d['identity']['own']['adapters.py'])
        replacement=d['adapter'].programme_prompt(prompt)
        self.assertEqual(replacement.replace(d['adapter'].PROGRAMME_PERMISSION,d['adapter'].NATIVE_PERMISSION),prompt)
        self.assertNotIn(d['adapter'].NATIVE_PERMISSION,replacement)
        self.assertEqual(t.v.scientific_prompt(self.ids[0],'four_demo'),prompt)
        self.assertTrue(all(getattr(t,name) is value for name,value in donor_functions.items()))
        self.assertEqual(d['original']['pair'].CONDITIONS,old_conditions)
        self.assertEqual(d['image_comparator'].CONDITIONS[pair.CONDITION],('frozen_program','visual_waveform',4))
        self.assertEqual(d['image_comparator'].CONDITIONS['matched_waveform_programme'],('frozen_program','numerical_waveform',4))
        read,seen,authority=self.frames(c,a,b)
        with mock.patch.object(pair,'read',side_effect=read):
            match=pair.match_arm_information(a,b,data,d,c,am,bm,authority['a_receipt'],authority['b_receipt'])
        self.assertEqual(len(seen),800);self.assertFalse(match['later_viewer_trajectories_identical_claimed'])
        self.assertTrue(match['same_initial_raster_bytes'])
        def changed(header,pixels,is_b,ordinal):
            return header,(pixels+b'changed' if is_b and ordinal==0 else pixels)
        read,_,authority=self.frames(c,a,b,mutate=changed)
        with mock.patch.object(pair,'read',side_effect=read),self.assertRaisesRegex(ValueError,'Committed content changed|Same initial raster/header'):
            pair.match_arm_information(a,b,data,d,c,am,bm,authority['a_receipt'],authority['b_receipt'])
        OBSERVATIONS.append({'control':'matching','first_frames_matched':800,'later_action_identity_required':False})

    def portable_profile(self,client):
        """Exact unchanged source with only platform/executable-existence fixture metadata.

        No sandbox or process is launched; this never qualifies OS enforcement.
        Private globals leave the real donor function/module unmodified.
        """
        function=self.deps['transport'].sandbox_profile
        class ExistingSandbox(type(Path())):
            def exists(self):
                return True if str(self)=='/usr/bin/sandbox-exec' else super().exists()
        namespace=dict(function.__globals__)
        namespace.update(sys=types.SimpleNamespace(platform='darwin'),Path=ExistingSandbox)
        clone=types.FunctionType(function.__code__,namespace,function.__name__,function.__defaults__,function.__closure__)
        return clone(client)

    def episode_fixture(self,name):
        root=self.location(name);c,_,_,client_body=self.contract(root)
        client=root/'CLIENT.py';put(client,client_body)
        episode=root/'episode';(episode/'transport').mkdir(parents=True)
        t=self.deps['image_transport'];profile=self.portable_profile(client)
        manifest=t.boundary_manifest(t.Limits(**c['limits']),'macos',client,'a'*32,profile)
        put(episode/'transport/sandbox.sb',profile.encode())
        put(episode/'transport/MANIFEST.json',pair.encode(manifest))
        return root,c,client,episode,profile,manifest

    def test_03_capability_routes_and_self_consistent_permissive_profile_refuse(self):
        d=self.deps;viewer=d['transport'].v
        for request in ({'action':'select','record':'demo5'},{'action':'raw_arrays'},
                        {'action':'inspect','path':'/private/labels'},{'action':'select','record':'../targets'}):
            with self.subTest(request=request),self.assertRaises(ValueError):
                viewer.transition(viewer.initial_state(),request,'four_demo')
        display=viewer.display_metadata(viewer.initial_state(),{})
        display['demonstration_target']=1
        leaked={'status':'rendered','display':display,'remaining_actions':127,
                'image':{'mime_type':'image/png','base64':base64.b64encode(self.pixels).decode()}}
        with self.assertRaisesRegex(ValueError,'Query label prohibited'):d['transport'].projection(leaked)
        for path in ('/usr/generated-private','/System/generated-private','/Library/Frameworks/generated-private','/'):
            with self.subTest(path=path),self.assertRaisesRegex(ValueError,'Protected input overlaps readable runtime root'):
                pair.protected_path(path)
        root,c,client,episode,profile,manifest=self.episode_fixture('policy')
        t=d['image_transport']
        with mock.patch.object(t,'sandbox_profile',side_effect=self.portable_profile),\
             mock.patch.object(t,'audit_transport',return_value={'generated_fixture_only':True}) as audit:
            pair.audit_programme_episode(episode,{},0,d,c,client);self.assertEqual(audit.call_count,1)
            put(episode/'transport/MANIFEST.json',pair.encode(dict(manifest,sandbox='protocol_only')))
            with self.assertRaisesRegex(ValueError,'requires macOS sandbox'):
                pair.audit_programme_episode(episode,{},0,d,c,client)
            permissive='(version 1) (allow default)'
            forged=t.boundary_manifest(t.Limits(**c['limits']),'macos',client,'a'*32,permissive)
            put(episode/'transport/sandbox.sb',permissive.encode())
            put(episode/'transport/MANIFEST.json',pair.encode(forged))
            with self.assertRaisesRegex(ValueError,'Exact frozen sandbox profile required'):
                pair.audit_programme_episode(episode,{},0,d,c,client)
            self.assertEqual(audit.call_count,1)
        OBSERVATIONS.append({'control':'capability_source_policy','os_enforcement_qualified':False})

    def test_04_complete_generated400_admission_and_pair_order(self):
        f=self.generated_arm();d=self.deps;trace=[]
        initial,seen,authority=self.frames(f.c,f.provider,f.programme,a_manifest=f.am,b_manifest=f.bm)
        real_read=pair.read
        def read(path,cap=1048576,expected=None):
            if Path(path).name=='0000-out.bin' or (Path(path).is_relative_to(f.provider) and Path(path).name in ('CLIENT_END.json','ARM.json','MANIFEST.json')):
                return initial(path,cap,expected)
            if Path(path)==f.private:
                self.assertEqual(len(seen),1200);self.assertIn('provider-admitted',trace)
                self.assertIn('generated-public-validations',trace)
                self.assertEqual(len(audited),400);trace.append('private-descriptor-after-arms')
            return real_read(path,cap,expected)
        def admit_provider(*args):
            trace.append('provider-admitted')
            return f.programme/'collection/submission.npz',f.arm['submission'],f.provider_receipt
        audited=[]
        def audit(*args):audited.append(args[2]);return {'generated_fixture_only':True}
        def score(*args):
            # Explicit fixture authority stands in for the unchanged two public
            # NPZ validations; then exercise the production lazy read facade.
            for submission,_,_ in args[3]:f.data['validator'].validate(submission,args[4])
            args[6]['both_public_validated_before_private']=True
            trace.append('generated-public-validations')
            args[0].read(args[5],65536)
            self.assertIn('private-descriptor-after-arms',trace);trace.append('generated-score-callback')
            return {'status':'generated_fixture_only_no_metrics'}
        with mock.patch.object(pair,'dependencies',return_value=d),\
             mock.patch.object(pair,'validate_frozen',return_value=(f.c,f.client)),\
             mock.patch.object(pair,'packet_data',return_value=f.data),\
             mock.patch.object(pair,'audit_programme_episode',side_effect=audit),\
             mock.patch.object(d['provider'],'admit_arm',side_effect=admit_provider),\
             mock.patch.object(d['image_protected'],'protected_compare',side_effect=score),\
             mock.patch.object(pair,'read',side_effect=read),mock.patch.dict(sys.modules,{'numpy':f.np}):
            result=pair.compare(f.provider,f.provider_receipt,f.programme,f.receipt,
                    f.frozen,f.frozen_pin,f.private,self.output/'complete-pair-result')
        self.assertEqual(audited,list(range(400)))
        self.assertEqual(result['status'],'generated_fixture_only_no_metrics')
        self.assertEqual(trace,['provider-admitted','generated-public-validations','private-descriptor-after-arms','generated-score-callback'])
        self.assertFalse(result['os_enforcement_independently_qualified'])
        OBSERVATIONS.append({'control':'complete_generated_pair','programme_queries':400,
                             'matched_initial_frames':800,'programme_admission_frames':400,'private_score_fixture_calls':1})

    def test_05_incomplete_misaligned_and_late_freeze_precede_private_access(self):
        f=self.generated_arm();d=self.deps;original=(f.programme/'ARM.json').read_bytes()
        with mock.patch.object(pair,'dependencies',return_value=d),\
             mock.patch.object(pair,'validate_frozen',return_value=(f.c,f.client)),\
             mock.patch.object(d['provider'],'admit_arm',side_effect=ValueError('Generated incomplete provider400')) ,\
             mock.patch.object(pair,'admit_programme') as programme,\
             mock.patch.object(d['image_protected'],'protected_compare') as private:
            with self.assertRaisesRegex(ValueError,'Generated incomplete provider400'):
                pair.compare(f.provider,{},f.programme,f.receipt,f.frozen,f.frozen_pin,f.private,self.output/'incomplete-provider')
            programme.assert_not_called();private.assert_not_called()
        cases=[('missing_query',dict(f.arm,episodes=f.arm['episodes'][:-1])),
               ('extra_demonstration',dict(f.arm,demonstrations=5))]
        for name,record in cases:
            badpin=put(f.programme/'ARM.json',pair.encode(record))
            with mock.patch.object(pair,'dependencies',return_value=d),\
                 mock.patch.object(pair,'validate_frozen',return_value=(f.c,f.client)),\
                 mock.patch.object(d['provider'],'admit_arm',return_value=('generated',{},{})),\
                 mock.patch.object(pair,'packet_data') as packet,\
                 mock.patch.object(d['image_protected'],'protected_compare') as private:
                try:
                    with self.assertRaises(ValueError):
                        pair.compare(f.provider,{},f.programme,badpin,f.frozen,f.frozen_pin,f.private,self.output/name)
                    packet.assert_not_called();private.assert_not_called()
                finally:put(f.programme/'ARM.json',original)
        for name,am,bm,c in (
            ('mismatched_packet',dict(f.am,packet={'changed':'0'*64}),f.bm,f.c),
            ('mismatched_viewer_limits',dict(f.am,limits={'transport':dict(f.c['limits'],max_images=31)}),f.bm,f.c),
            ('programme_frozen_after_A',f.am,f.bm,dict(f.c,frozen_monotonic=21.0))):
            private=mock.Mock(side_effect=AssertionError('Private access before matched arms'))
            with mock.patch.object(pair,'read',side_effect=AssertionError('Metadata refusal must precede image reads')):
                with self.assertRaises(ValueError):
                    pair._ordered_pair(lambda:('a',{},{}),lambda:('b',{},{}),
                        lambda:pair.match_arm_information(f.provider,f.programme,f.data,d,c,am,bm,f.provider_receipt,f.receipt),private)
            private.assert_not_called()
        OBSERVATIONS.append({'control':'pre_private_refusals','partial_or_extra_demo_arms':3,'matching_failures':3})

    def test_06_first_final_and_owned_closure_corruption_refuse(self):
        f=self.generated_arm();d=self.deps
        response=f.programme/'sessions/000/response.txt';original=response.read_bytes()
        put(response,pair.encode({'trial_id':self.ids[0],'target_probability':0.9}))
        real_read=pair.read
        def first_frames(path,cap=1048576,expected=None):
            return f.initial_reader(path,cap,expected) if Path(path).name=='0000-out.bin' else real_read(path,cap,expected)
        with mock.patch.object(pair,'packet_data',return_value=f.data),\
             mock.patch.object(pair,'audit_programme_episode',return_value={'generated_fixture_only':True}),\
             mock.patch.object(pair,'read',side_effect=first_frames),\
             mock.patch.dict(sys.modules,{'numpy':f.np}):
            try:
                with self.assertRaisesRegex(ValueError,'Submission equals every first response'):
                    pair.admit_programme(f.programme,f.receipt,f.c,d)
            finally:put(response,original)
        episode_manifest=f.programme/'sessions/000/transport/MANIFEST.json'
        original_manifest=episode_manifest.read_bytes()
        put(episode_manifest,pair.encode({'episode_id':f'{1:032x}'}))
        with mock.patch.object(pair,'packet_data',return_value=f.data),\
             mock.patch.object(pair,'audit_programme_episode',return_value={'generated_fixture_only':True}),\
             mock.patch.object(pair,'read',side_effect=first_frames):
            try:
                with self.assertRaisesRegex(ValueError,'Unique fresh programme episodes required'):
                    pair.admit_programme(f.programme,f.receipt,f.c,d)
            finally:put(episode_manifest,original_manifest)
        root,c,client,episode,profile,manifest=self.episode_fixture('unclosed')
        end={'status':'valid_unscored','reason':None,'client_exit_code':0,'client_forced_stop':False,
             'process_ownership':{'cleanup_complete':False,'leader_unreaped_before_signal':True,
                 'exit_observed_before_stop':True,'reaped':False,'returncode':0,'group_absence_observed':False}}
        put(episode/'transport/END.json',pair.encode(end))
        with mock.patch.object(d['image_transport'],'sandbox_profile',side_effect=self.portable_profile):
            with self.assertRaisesRegex(ValueError,'Owned cleanup receipt required'):
                pair.audit_programme_episode(episode,{},0,d,c,client)
        OBSERVATIONS.append({'control':'first_final_and_owned_closure','accepted_corruptions':0})


if __name__=='__main__':
    unittest.main()
