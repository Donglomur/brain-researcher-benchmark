"""Invented paper bytes and arrays only; original PDF is never copied by tests."""
import sys,unittest,tempfile,hashlib,json
from pathlib import Path
from unittest.mock import patch
PACKAGE=Path(__file__).resolve().parents[1]
BASE=PACKAGE if (PACKAGE/'public/contract.py').is_file() else PACKAGE.parent
sys.path[:0]=[str(PACKAGE/'operator'),str(BASE/'public'),str(BASE/'operator'),str(BASE/'tests')]
from io_contract import TASK,encode
from stage import stage
from fixtures import make
from prepare import publish
from paper_asset import captured_paper

class Paper(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.assets=self.root/'package';public=self.assets/'public';public.mkdir(parents=True)
        self.body=b'%PDF-1.4\nInvented complete paper fixture, not a scientific source.\n%%EOF\n'
        self.meta={'schema':'neuroformer_local_paper_v1','task_id':TASK,'path':'paper.pdf','bytes':len(self.body),
          'sha256':hashlib.sha256(self.body).hexdigest(),'official_url':'https://proceedings.iclr.cc/invented-test-only','use_scope':'invented test'}
        (public/'paper.pdf').write_bytes(self.body);(public/'PAPER_ASSET.json').write_bytes(encode(self.meta))
        for name in ('TASK.md','PROTOCOL.json','PANEL.json','submission.schema.json','reference_linear.py','io_contract.py','DEPENDENCIES.md','requirements.txt'):
            chosen=PACKAGE/'public'/name
            if not chosen.exists():chosen=BASE/'public'/name
            (public/name).write_bytes(chosen.read_bytes())
        self.obs=self.root/'obs';self.obs.mkdir();self.q,self.bridge=make(self.obs)
        self.target=publish(self.q,self.bridge,self.obs,self.root/'packet',1_000_000,False)
        self.cid='medial--speed_regression--neuroformer--100'
    def tearDown(self):self.tmp.cleanup()
    def run_view(self,arm,path,cap=2_000_000):
        with patch('stage.ROOT',self.assets):return stage(self.q,self.target,self.obs,self.cid,arm,path,cap,False)
    def test_complete_paper_identical_in_both_views(self):
        a=self.run_view('paper_and_data',self.root/'a');b=self.run_view('paper_data_official_code',self.root/'b')
        for root in ('a','b'):
            self.assertEqual((self.root/root/'paper.pdf').read_bytes(),self.body)
            self.assertEqual((self.root/root/'PAPER_ASSET.json').read_bytes(),encode(self.meta))
        ap={r['path']:(r['bytes'],r['sha256']) for r in a['files']};bp={r['path']:(r['bytes'],r['sha256']) for r in b['files']}
        self.assertEqual(ap,{k:v for k,v in bp.items() if not k.startswith('official_code/')})
        self.assertEqual(ap['paper.pdf'],(len(self.body),self.meta['sha256']))
        self.assertFalse((self.root/'a/official_code').exists());self.assertEqual(len(bp)-len(ap),26)
    def test_bad_pin_precedes_array_access_or_publication(self):
        (self.assets/'public/paper.pdf').write_bytes(b'changed')
        with patch('stage.windows',side_effect=AssertionError('must not read observations')):
            with self.assertRaises(ValueError):self.run_view('paper_and_data',self.root/'bad')
        self.assertFalse((self.root/'bad').exists())
    def test_missing_paper_precedes_array_access(self):
        (self.assets/'public/paper.pdf').unlink()
        with patch('stage.windows',side_effect=AssertionError('must not read observations')):
            with self.assertRaises(OSError):self.run_view('paper_data_official_code',self.root/'missing')
        self.assertFalse((self.root/'missing').exists())
    def test_paper_included_in_exact_prepublication_cap(self):
        self.run_view('paper_and_data',self.root/'good')
        size=sum(p.stat().st_size for p in (self.root/'good').rglob('*') if p.is_file())
        with patch('stage.windows',side_effect=AssertionError('must not read observations')):
            with self.assertRaises(ValueError):self.run_view('paper_and_data',self.root/'small',size-1)
        self.assertFalse((self.root/'small').exists())
    def test_symlink_paper_refused(self):
        p=self.assets/'public/paper.pdf';p.unlink();other=self.root/'other';other.write_bytes(self.body);p.symlink_to(other)
        with self.assertRaises(OSError):captured_paper(self.assets)
    def test_static_views_have_exact_unique_runtime_common_members(self):
        v=json.loads((PACKAGE/'operator/ACCESS_VIEWS.json').read_bytes())
        a=[r['target'] for r in v['paper_and_data']];b=[r['target'] for r in v['paper_data_official_code']]
        expected={'public/'+n for n in ('TASK.md','PROTOCOL.json','PANEL.json','submission.schema.json','reference_linear.py','io_contract.py','DEPENDENCIES.md','requirements.txt','PAPER_ASSET.json','paper.pdf')}
        self.assertEqual(set(a),expected);self.assertEqual(len(a),10)
        self.assertEqual(len(b),len(set(b)));self.assertEqual(len(b),36)
        self.assertNotIn('public/official_code/requirements.txt',a)
        self.assertEqual(b.count('public/official_code/requirements.txt'),1)
        self.assertEqual({p for p in b if not p.startswith('public/official_code/')},expected)

if __name__=='__main__':unittest.main()
