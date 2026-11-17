"""Capture the same complete local paper for both arms; no network or PDF parser."""
import hashlib
from pathlib import Path
from io_contract import capture,decode,exact,require,sha256,TASK

def captured_paper(root):
    public=Path(root)/'public'
    require(not public.is_symlink(),'ordinary public asset directory')
    metadata=capture(public/'PAPER_ASSET.json',10000);p=decode(metadata)
    exact(p,('schema','task_id','path','bytes','sha256','official_url','use_scope'))
    require(p['schema']=='neuroformer_local_paper_v1' and p['task_id']==TASK,'local paper identity')
    require(p['path']=='paper.pdf' and type(p['bytes']) is int and 0<p['bytes']<=20_000_000,'bounded complete paper')
    sha256(p['sha256'])
    require(type(p['official_url']) is str and p['official_url'].startswith('https://proceedings.iclr.cc/'),'official paper provenance')
    require(type(p['use_scope']) is str and p['use_scope'],'explicit local-use scope')
    body=capture(public/'paper.pdf',p['bytes'])
    require(len(body)==p['bytes'] and hashlib.sha256(body).hexdigest()==p['sha256'],'complete pinned paper bytes')
    return {'paper.pdf':body,'PAPER_ASSET.json':metadata}
