"""Generated full-cohort controls. No authentic recordings, network, or model runs.

Only the tests patch private source identity constants for synthetic OIDs. The
production API/CLI exposes no source trust override. A bounded log sink avoids
large failure dumps; the shared two-slot pool owns execution.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import signal
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('neural002_source_pin_compiler_controls', HERE/'source_pin_compiler.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)


def framed(body):
    return hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()


def pointer(size, digest, extension):
    key = f'SHA256E-s{size}--{digest}.{extension}'
    return f'../../.git/annex/objects/0G/gM/{key}/{key}'.encode()


def fixture():
    rows, supplied, expected = [], [], []
    for p in c.PEOPLE:
        for task in c.TASKS:
            row = {'subject': p, 'task': task}
            output = {'source_commit': c.SOURCE_COMMIT, 'participant': p, 'task': task, 'files': {}}
            for role in c.ROLES:
                path = f'{p}/eeg/{p}_task-{task}'+c.EXTENSIONS[role]
                if role == 'events':
                    body = b'opaque-generated-event-body\x00\xff'+path.encode()
                    size, digest = len(body), hashlib.sha256(body).hexdigest()
                else:
                    size = 1535 if role == 'header' else 5643 if role == 'markers' else 201207360
                    digest = hashlib.sha256(('synthetic expected payload '+path).encode()).hexdigest()
                    body = pointer(size, digest, c._POINTER_EXT[role].decode())
                oid = framed(body); mode = '100644' if role == 'events' else '120000'
                row[c.SOURCE_ROLES[role]] = {'path': path, 'git_mode': mode, 'git_object': oid, 'bytes': len(body)}
                supplied.append({'path': path, 'git_mode': mode, 'git_object': oid, 'body': body})
                output['files'][role] = {'path': path, 'bytes': size, 'sha256': digest}
            rows.append(row); expected.append(output)
    source = {'source_commit': c.SOURCE_COMMIT,
              'cohort_metadata': {'commit': c.SOURCE_COMMIT, 'participants': 32, 'recordings': 64, 'files': rows}}
    return source, supplied, expected


def encoded(source):
    return (json.dumps(source,sort_keys=True,separators=(',',':'))+'\n').encode()


@contextlib.contextmanager
def generated_trust(source):
    body = encoded(source)
    with mock.patch.object(c, '_SOURCE_BYTES', len(body)), mock.patch.object(c, '_SOURCE_SHA256', hashlib.sha256(body).hexdigest()):
        yield body


class CompilerControls(unittest.TestCase):
    def test_full64_recordings_all256_pins_and_separate_provenance(self):
        source, supplied, expected = fixture()
        with generated_trust(source) as body:
            manifest, receipt = c.compile_pins(body, list(reversed(supplied)))
        self.assertEqual(manifest, {'schema':'morse-pinned-cohort-v1','source_commit':c.SOURCE_COMMIT,'recordings':expected})
        self.assertEqual(receipt['source_objects_authenticated'],256)
        self.assertEqual(receipt['recordings'],64)
        self.assertEqual(len(receipt['source_evidence']),256)
        self.assertEqual(receipt['manifest_sha256'],hashlib.sha256(c._encoded(manifest)).hexdigest())
        self.assertFalse(receipt['raw_payload_custody_verified'])
        self.assertFalse(receipt['scientific_certificate_issued'])
        self.assertFalse(receipt['provider_or_runtime_admission'])
        self.assertFalse(receipt['dataset_tag_commit_equivalence_verified'])
        for row, original in zip(receipt['source_evidence'], supplied):
            self.assertEqual(row['source_git_blob_sha1'],original['git_object'])
            self.assertEqual(row['source_blob_bytes'],len(original['body']))
            self.assertEqual(row['source_blob_sha256'],hashlib.sha256(original['body']).hexdigest())
        self.assertEqual(sum(r['derivation']=='opaque_regular_git_blob_bytes' for r in receipt['source_evidence']),64)
        self.assertEqual(sum(r['derivation']=='authenticated_source_pointer_content_key' for r in receipt['source_evidence']),192)

    def test_public_anchor_rejects_caller_selected_source(self):
        source, supplied, _ = fixture()
        with self.assertRaisesRegex(c.PinError,'selected SOURCES identity'):
            c.compile_pins(encoded(source),supplied)
        with generated_trust(source) as body:
            with self.assertRaisesRegex(c.PinError,'selected SOURCES identity'):
                c.compile_pins(body+b' ',supplied)
            altered=body.replace(b'sub-01',b'sub-99',1)
            with self.assertRaisesRegex(c.PinError,'selected SOURCES identity'):
                c.compile_pins(altered,supplied)

    def test_missing_extra_duplicate_and_unknown_supplied_support(self):
        source, original, _ = fixture()
        cases=[original[:-1],original+[original[0]],original[:-1]+[original[0]]]
        cases.append([{**original[0],'path':'../../unexpected'},*original[1:]])
        with generated_trust(source) as body:
            for supplied in cases:
                with self.subTest(case=len(supplied)),self.assertRaises(c.PinError):c.compile_pins(body,supplied)

    def test_supplied_mode_oid_body_type_and_extent_mismatch(self):
        source, original, _ = fixture()
        changes=[{'git_mode':'100644'},{'git_object':'0'*40},{'body':bytearray(original[0]['body'])},
                 {'body':original[0]['body']+b'\n'},{'extra':'not allowed'},{'path':[]}]
        with generated_trust(source) as body:
            for change in changes:
                supplied=[{**original[0],**change},*original[1:]]
                with self.subTest(keys=list(change)),self.assertRaises(c.PinError):c.compile_pins(body,supplied)

    def test_every_object_authenticates_before_first_pointer_interpretation(self):
        source, original, _ = fixture()
        tampered=original[-1]['body'][:-1]+bytes([original[-1]['body'][-1]^1])
        supplied=original[:-1]+[{**original[-1],'body':tampered}]
        with generated_trust(source) as body,mock.patch.object(c,'_pointer_pin',side_effect=AssertionError('projection too early')) as parser:
            with self.assertRaisesRegex(c.PinError,'Git blob authentication'):c.compile_pins(body,supplied)
            parser.assert_not_called()

    def test_generated_selected_roster_identity_path_mode_and_extent_controls(self):
        source, supplied, _ = fixture()
        def case(change):
            changed=json.loads(json.dumps(source));change(changed)
            with generated_trust(changed) as body,self.assertRaises(c.PinError):c.compile_pins(body,supplied)
        changes=[lambda s:s['cohort_metadata'].__setitem__('participants',True),
                 lambda s:s['cohort_metadata'].__setitem__('recordings',63),
                 lambda s:s['cohort_metadata']['files'].reverse(),
                 lambda s:s['cohort_metadata']['files'][0].__setitem__('subject','sub-99'),
                 lambda s:s['cohort_metadata']['files'][0]['header'].__setitem__('path','/tmp/wrong.vhdr'),
                 lambda s:s['cohort_metadata']['files'][0]['header'].__setitem__('git_mode','100644'),
                 lambda s:s['cohort_metadata']['files'][0]['header'].__setitem__('bytes',True),
                 lambda s:s['cohort_metadata']['files'][0]['header'].__setitem__('bytes',1025),
                 lambda s:s['cohort_metadata']['files'][0]['header'].__setitem__('git_object',s['cohort_metadata']['files'][0]['markers']['git_object'])]
        for n,change in enumerate(changes):
            with self.subTest(case=n):case(change)

    def test_three_observed_authenticated_pointer_examples(self):
        examples=[('header',1535,'51a5bcf0154d48c0041b06cf061c773235c9424cc05a6b2871718b6ff71094ce','0G/07','40efd15a68b95a5b9909c4c8ea033f2035203f4b'),
                  ('markers',5643,'0d92531d5d0f40e05f1b115a34b3fedd67dd20bfa1fb6ccce95558c318c38bfe','74/gM','5a00688eb235bb04c3e1e7d7527898f3b225fa32'),
                  ('signal',201207360,'24b3e9d46d64ee25cdfa86932b4e91450eaffdaa25f8acf0a9d860804a65f87c','Mf/kP','5fa087cdc1bd05b31399747c3613228c1b7759aa')]
        for role,size,digest,shards,oid in examples:
            body=pointer(size,digest,c._POINTER_EXT[role].decode()).replace(b'0G/gM',shards.encode())
            self.assertEqual(framed(body),oid)
            self.assertEqual(c._pointer_pin(body,role),(size,digest))

    def test_parser_rejects_unobserved_grammar_mismatch_and_extent(self):
        digest='a'*64; good=pointer(1535,digest,'vhdr')
        bad=[good+b'\n',good.replace(b'../../',b'../../../',1),good.replace(b'0G/gM',b'0G/../gM'),
             good.replace(b'SHA256E',b'SHA1E'),good.replace(b's1535',b's01535'),good.replace(b'a'*64,b'A'*64),
             good[:-1]+b'x',pointer(0,digest,'vhdr'),pointer(2**20+1,digest,'vhdr'),
             pointer(10**20,digest,'vhdr'),pointer(1535,digest,'vmrk')]
        for n,body in enumerate(bad):
            with self.subTest(case=n),self.assertRaises(c.PinError):c._pointer_pin(body,'header')
        with self.assertRaises(c.PinError):c._pointer_pin(pointer(8*2**30+1,digest,'eeg'),'signal')
        self.assertEqual(c._pointer_pin(pointer(8*2**30,digest,'eeg'),'signal')[0],8*2**30)

    def test_authenticated_but_unsupported_pointer_fails_whole_projection(self):
        source,supplied,_=fixture();old=supplied[0];bad=old['body'].replace(b'SHA256E',b'SHA1EXX')
        newoid=framed(bad);supplied[0]={**old,'body':bad,'git_object':newoid}
        source['cohort_metadata']['files'][0]['header'].update(git_object=newoid,bytes=len(bad))
        with generated_trust(source) as body,self.assertRaisesRegex(c.PinError,'unsupported or malformed'):
            c.compile_pins(body,supplied)

    def test_opaque_event_bytes_are_not_rewritten_or_semantically_approved(self):
        source,supplied,_=fixture()
        with generated_trust(source) as body:manifest,receipt=c.compile_pins(body,supplied)
        event=supplied[2]['body'];self.assertIn(b'\xff',event)
        self.assertEqual(manifest['recordings'][0]['files']['events']['sha256'],hashlib.sha256(event).hexdigest())
        self.assertEqual(manifest['recordings'][0]['files']['events']['bytes'],len(event))
        self.assertFalse(receipt['scientific_certificate_issued'])

    def test_fifo_refused_before_blocking_open(self):
        temp_root=HERE.parent/'generated';temp_root.mkdir(exist_ok=True)
        def expired(*unused):raise TimeoutError('FIFO refusal exceeded2 seconds')
        with tempfile.TemporaryDirectory(prefix='fifo-',dir=temp_root) as name:
            fifo=Path(name)/'required.blob';os.mkfifo(fifo)
            prior=signal.signal(signal.SIGALRM,expired);signal.alarm(2)
            try:
                with self.assertRaisesRegex(c.PinError,'ordinary bounded single-link input'):
                    c._read_regular(fifo,208,208)
            finally:
                signal.alarm(0);signal.signal(signal.SIGALRM,prior)

    def test_full_directory_cli_and_no_overwrite_missing_extra_symlink_hardlink(self):
        source,supplied,expected=fixture()
        # One complete on-disk generated cohort only; everything else in memory.
        temp_root=HERE.parent/'generated';temp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='pins-',dir=temp_root) as name,generated_trust(source) as body:
            root=Path(name); sources=root/'SOURCES.json';sources.write_bytes(body)
            blobs=root/'blobs';blobs.mkdir()
            for row in supplied:(blobs/(row['git_object']+'.blob')).write_bytes(row['body'])
            out,proof=root/'pins.json',root/'proof.json'
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(c.main(['--sources',str(sources),'--blobs',str(blobs),'--manifest-output',str(out),'--receipt-output',str(proof)]),0)
            self.assertEqual(json.loads(out.read_bytes())['recordings'],expected)
            self.assertEqual(json.loads(proof.read_bytes())['manifest_sha256'],hashlib.sha256(out.read_bytes()).hexdigest())
            self.assertFalse(json.loads(stdout.getvalue())['actual_raw_payload_custody'])
            before=out.read_bytes()
            with self.assertRaises(c.PinError):c.write_outputs({}, {}, out,root/'new.json')
            self.assertEqual(out.read_bytes(),before);self.assertFalse((root/'new.json').exists())
            p=blobs/(supplied[0]['git_object']+'.blob');held=root/'held';p.rename(held)
            with self.assertRaises(c.PinError):c.compile_directory(sources,blobs)
            p.symlink_to(held)
            with self.assertRaises(c.PinError):c.compile_directory(sources,blobs)
            p.unlink();p.hardlink_to(held)
            with self.assertRaises(c.PinError):c.compile_directory(sources,blobs)
            p.unlink();held.rename(p)
            extra=blobs/'extra';extra.write_bytes(b'x')
            with self.assertRaises(c.PinError):c.compile_directory(sources,blobs)
            extra.unlink()
            p.write_bytes(supplied[0]['body']+b'x')
            with self.assertRaises(c.PinError):c.compile_directory(sources,blobs)
            # Durable-byte cost is conservatively charged below despite cleanup.
            print(json.dumps({'generated_written_upper_bound_bytes':393216,'full_recordings':64,'files':256}))


class BoundedLog:
    def __init__(self):self.parts=[];self.bytes=0;self.overflow=False
    def write(self,text):
        raw=text.encode('utf-8');remaining=14000-self.bytes
        if len(raw)>remaining:self.overflow=True
        keep=raw[:max(0,remaining)].decode('utf-8',errors='ignore');self.parts.append(keep);self.bytes+=len(keep.encode())
    def flush(self):pass


if __name__=='__main__':
    sink=BoundedLog()
    suite=(unittest.TestSuite(CompilerControls(name) for name in sys.argv[1:]) if sys.argv[1:]
           else unittest.defaultTestLoader.loadTestsFromTestCase(CompilerControls))
    result=unittest.TextTestRunner(stream=sink,verbosity=2).run(suite)
    sys.stdout.write(''.join(sink.parts))
    if sink.overflow:sys.stdout.write('\nBounded test log exceeded; control run fails.\n')
    raise SystemExit(0 if result.wasSuccessful() and not sink.overflow else 1)
