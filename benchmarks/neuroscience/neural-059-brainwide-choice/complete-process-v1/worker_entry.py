"""Standalone fixed worker entry. No candidate import precedes source capture."""
import time
ORIGIN=time.monotonic()
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def main():
    if len(sys.argv)!=3: raise ValueError('boot path and external complete body digest required')
    root=Path(__file__).absolute().parent
    boot_path=Path(sys.argv[1])
    if boot_path.is_symlink() or boot_path.stat().st_size>16777216: raise ValueError('bounded fixed boot')
    boot_body=boot_path.read_bytes()
    if hashlib.sha256(boot_body).hexdigest()!=sys.argv[2]: raise ValueError('exact original worker boot')
    boot=json.loads(boot_body)
    manifest=(root/'SOURCE_MANIFEST.json').read_bytes()
    if len(manifest)>1048576 or hashlib.sha256(manifest).hexdigest()!=boot['source_sha256']:
        raise ValueError('external whole source manifest before loader execution')
    loader_rows=[r for r in json.loads(manifest)['files'] if r['path']=='captured_loader.py']
    if len(loader_rows)!=1: raise ValueError('one frozen source loader')
    body=(root/'captured_loader.py').read_bytes(); expected=loader_rows[0]
    if len(body)!=expected['bytes'] or hashlib.sha256(body).hexdigest()!=expected['sha256']:
        raise ValueError('exact loader body before execution')
    module=importlib.util.module_from_spec(importlib.util.spec_from_loader('_n059_bootstrap',loader=None))
    exec(compile(body,str(root/'captured_loader.py'),'exec'),module.__dict__)
    if module.capture(boot_path,16777216)!=boot_body: raise ValueError('stable original boot')
    if not boot['origin']<=ORIGIN<boot['deadline']: raise ValueError('original startup lifetime')
    loader=module.install(root,boot['source_sha256'])
    if loader.bodies['worker_entry.py']!=module.capture(Path(__file__).absolute(),1048576):
        raise ValueError('launched worker source joins captured capsule')
    from n059_owned.worker import serve
    serve(boot)


if __name__=='__main__': main()
