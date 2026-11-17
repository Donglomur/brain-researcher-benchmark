"""Only layout/source coexistence controls; no Docker or Provider instance."""
from pathlib import Path
import hashlib, importlib.util, json, os, stat, sys, tempfile, time, unittest

ROOT=Path(__file__).resolve().parent
NEW=ROOT/'vendor_transport'
OLD=ROOT.parent/'program/vendor_transport'
NEW_MANIFEST='335f696f47529a115479f543c62cbcab12d12c02f8a62606b8dc133ae92333c4'
OLD_MANIFEST='93df92be5b388f4b2896805c8e02f0c41f301d1c86e6b06709444c1075ade0e4'

def authenticate(root,expected):
    raw=(root/'SOURCE_MANIFEST.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise AssertionError('manifest identity')
    files=json.loads(raw)['files']
    if {p.name for p in root.iterdir()}!=set(files)|{'SOURCE_MANIFEST.json'}:raise AssertionError('package membership')
    for name,pin in files.items():
        body=(root/name).read_bytes()
        if {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}!=pin:raise AssertionError(name)
    return files

def load(root,name):
    spec=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
    package=importlib.util.module_from_spec(spec);sys.modules[name]=package
    spec.loader.exec_module(package)
    return package,sys.modules[name+'.bounds']

class PackageBinding(unittest.TestCase):
    def test_exact_closure_and_explicit_package_import(self):
        files=authenticate(NEW,NEW_MANIFEST)
        self.assertEqual(len(files),7)
        package,bounds=load(NEW,'sleep_public_mode_v2_identity')
        self.assertEqual(Path(package.__file__).resolve(),NEW/'__init__.py')
        self.assertEqual(Path(bounds.__file__).resolve(),NEW/'bounds.py')
        self.assertEqual(package.Provider.__module__,'sleep_public_mode_v2_identity.provider')
    def test_predecessor_and_successor_coexist_without_rebinding(self):
        oldfiles=authenticate(OLD,OLD_MANIFEST);newfiles=authenticate(NEW,NEW_MANIFEST)
        self.assertEqual([n for n in oldfiles if oldfiles[n]!=newfiles[n]],['bounds.py'])
        old,oldbounds=load(OLD,'sleep_historical_public_mode')
        new,newbounds=load(NEW,'sleep_successor_public_mode')
        self.assertIsNot(old.Provider,new.Provider)
        self.assertEqual(Path(oldbounds.__file__).resolve(),OLD/'bounds.py')
        self.assertEqual(Path(newbounds.__file__).resolve(),NEW/'bounds.py')
        previous=os.umask(0o077)
        try:
            with tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary).resolve()
                for label,module,mode in [('old',oldbounds,0o400),('new',newbounds,0o444)]:
                    private=root/label;private.mkdir(mode=0o700)
                    meter=module.Meter(65536,65536,time.monotonic()+10)
                    public=private/'REQUEST.json';secret=private/'PRIVATE.json'
                    module.publish(public,b'fixed generated public bytes',meter,mode=0o444)
                    module.publish(secret,b'fixed generated private bytes',meter)
                    self.assertEqual(stat.S_IMODE(public.stat().st_mode),mode)
                    self.assertEqual(stat.S_IMODE(secret.stat().st_mode),0o600)
                    self.assertEqual(stat.S_IMODE(private.stat().st_mode),0o700)
                    self.assertEqual(public.read_bytes(),b'fixed generated public bytes')
        finally:os.umask(previous)

if __name__=='__main__':unittest.main(verbosity=2)
