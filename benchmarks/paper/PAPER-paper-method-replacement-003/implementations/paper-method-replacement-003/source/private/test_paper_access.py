"""Invented files only; no scientific inputs, model or scorer execution."""
import hashlib, importlib.util, json, os, tempfile, unittest
from pathlib import Path

def digest(b): return hashlib.sha256(b).hexdigest()
class PaperAccessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.pkg=self.root/'pkg';self.pkg.mkdir()
        spec=importlib.util.spec_from_file_location('paper_access_under_test',Path(__file__).with_name('paper_access.py'))
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        def row(name,body,target):
            p=self.pkg/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body)
            return {'source':name,'target':target,'bytes':len(body),'sha256':digest(body)}
        self.paper=row('public/paper/article.xml',b'<article>invented fixture only</article>','paper/article.xml')
        self.material=row('public/PAPER_MATERIALS.json',b'{"invented":true}','PAPER_MATERIALS.json')
        self.code=row('private/author/example.py',b'# invented author source\n','author/example.py')
        self.secret=row('private/gold.json',b'{"secret":true}','private/gold.json')
        (self.pkg/'private').mkdir(exist_ok=True)
        self.p={'schema':'common_primary_paper_files_v1','files':[self.paper,self.material]}
        self.s={'schema':'paper_source_view_v1','task_id':'invented','common':[self.paper,self.material],'A_extra':[],'B_extra':[self.code]}
        self.bind()
    def bind(self):
        for name,value,attr in [('PAPER_COMMON.json',self.p,'PAPER_PLAN_SHA'),('SOURCE_VIEW.json',self.s,'SOURCE_PLAN_SHA')]:
            b=(json.dumps(value)+'\n').encode();(self.pkg/'private'/name).write_bytes(b);setattr(self.m,attr,digest(b))
    def tearDown(self):self.tmp.cleanup()
    def test_identical_paper_and_author_only_B(self):
        a=self.m.stage_source(self.pkg,self.root/'A','A');b=self.m.stage_source(self.pkg,self.root/'B','B')
        self.assertEqual(len(a['files']),2);self.assertEqual(len(b['files']),3)
        self.assertEqual((self.root/'A/paper/article.xml').read_bytes(),(self.root/'B/paper/article.xml').read_bytes())
        self.assertFalse((self.root/'A/author').exists());self.assertFalse((self.root/'B/private').exists())
        self.assertFalse(a['runtime_isolation_verified']);self.assertFalse(a['scientific_data_mounted'])
    def test_source_mutation_refused_before_output(self):
        (self.pkg/self.paper['source']).write_bytes(b'changed')
        with self.assertRaises(ValueError):self.m.stage_source(self.pkg,self.root/'view','A')
        self.assertFalse((self.root/'view').exists())
    def test_plan_mutation_refused(self):
        (self.pkg/'private/SOURCE_VIEW.json').write_text('{}')
        with self.assertRaises(ValueError):self.m.stage_source(self.pkg,self.root/'view','A')
    def test_complete_destination_admission_before_capture(self):
        self.s['common'][0]['source']='does-not-exist';self.s['common'].append(self.secret);self.bind()
        with self.assertRaisesRegex(ValueError,'candidate-only'):self.m.stage_source(self.pkg,self.root/'view','A')
        self.assertFalse((self.root/'view').exists())
    def test_reserved_receipt_and_duplicate_refused(self):
        for target in ('SOURCE_VIEW.json','paper/article.xml'):
            self.s['B_extra'][0]['target']=target;self.bind()
            with self.assertRaises(ValueError):self.m.stage_source(self.pkg,self.root/'view','B')
    def test_symlink_and_fifo_source_refused(self):
        p=self.pkg/self.paper['source'];p.unlink();p.symlink_to(self.pkg/self.material['source'])
        with self.assertRaises(ValueError):self.m.stage_source(self.pkg,self.root/'view','A')
        p.unlink();os.mkfifo(p)
        with self.assertRaises(ValueError):self.m.stage_source(self.pkg,self.root/'view','A')
    def test_fresh_output_and_arm(self):
        (self.root/'existing').mkdir()
        for out,arm in [(self.root/'existing','A'),(self.root/'new','C')]:
            with self.assertRaises(ValueError):self.m.stage_source(self.pkg,out,arm)
        (self.root/'dangling').symlink_to(self.root/'absent')
        with self.assertRaises(ValueError):self.m.stage_source(self.pkg,self.root/'dangling','A')
    def test_paper_required_in_each_arm(self):
        self.s['common']=[self.material];self.bind()
        with self.assertRaisesRegex(ValueError,'identical'):self.m.stage_source(self.pkg,self.root/'view','A')

if __name__=='__main__':unittest.main()
