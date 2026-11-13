"""Concrete external operator invocation; never generic run/score activation."""
import time
ORIGIN=time.monotonic()
CPU_ORIGIN=time.process_time()
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def main():
    if len(sys.argv)!=4:
        raise ValueError('usage: operator_entry.py SELECTION ABSOLUTE_SELECTION_SHA256 SOURCE_MANIFEST_SHA256')
    root=Path(__file__).absolute().parent
    manifest_path=root/'SOURCE_MANIFEST.json'
    if manifest_path.is_symlink() or manifest_path.stat().st_size>1048576:
        raise ValueError('bounded fixed source manifest')
    manifest=manifest_path.read_bytes()
    if hashlib.sha256(manifest).hexdigest()!=sys.argv[3]: raise ValueError('external manifest before loader execution')
    rows=[r for r in json.loads(manifest)['files'] if r['path']=='captured_loader.py']
    if len(rows)!=1: raise ValueError('one selected source loader')
    body=(root/'captured_loader.py').read_bytes()
    if len(body)!=rows[0]['bytes'] or hashlib.sha256(body).hexdigest()!=rows[0]['sha256']:
        raise ValueError('exact ordinary loader before execution')
    module=importlib.util.module_from_spec(importlib.util.spec_from_loader('_n059_operator_bootstrap',loader=None))
    exec(compile(body,str(root/'captured_loader.py'),'exec'),module.__dict__)
    selection_body=module.capture(Path(sys.argv[1]),1048576)
    if hashlib.sha256(selection_body).hexdigest()!=sys.argv[2]: raise ValueError('exact frozen operator selection')
    loader=module.install(root,sys.argv[3])
    entry_body=module.capture(Path(__file__).absolute(),1048576)
    if loader.bodies['operator_entry.py']!=entry_body:
        raise ValueError('launched operator joins captured capsule')
    from n059_owned.core import parse, need
    from n059_owned.operator import run
    selected=parse(selection_body)
    need(selected['source_sha256']==sys.argv[3] and selected['deployment']['code_root']==str(root),
         'same frozen whole source capsule')
    return run(selected,ORIGIN,CPU_ORIGIN,loader.bytes+len(selection_body)+len(body)+len(manifest)+len(entry_body))


if __name__=='__main__': raise SystemExit(main())
