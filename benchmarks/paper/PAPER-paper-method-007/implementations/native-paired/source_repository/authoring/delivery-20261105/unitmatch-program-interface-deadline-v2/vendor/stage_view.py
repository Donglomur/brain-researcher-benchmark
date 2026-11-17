"""Copy only a frozen A/B and held-out-animal allowlist into a fresh directory.

This tool does not run candidate programs and does not enforce OS isolation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def selected(entries, view, held_out):
    if view not in ('A','B') or held_out not in [f'Mouse{i}' for i in range(1,6)]:
        raise ValueError('known view and held-out animal required')
    return [row for row in entries if row['arm'] in ('both',view)
        and row.get('validation_mouse')!=held_out]


def stage(root, output, view, held_out):
    root=Path(root).resolve();output=Path(output)
    if output.exists() or output.is_symlink():raise ValueError('fresh output required')
    if output.resolve().is_relative_to(root):raise ValueError('stage outside source package')
    entries=selected(json.loads((root/'private/PACKET_MAP.json').read_text())['files'],view,held_out)
    for row in entries:
        source=root/row['source'];target=Path(row['target'])
        if source.is_symlink() or not source.resolve().is_relative_to(root) or target.is_absolute() or '..' in target.parts:
            raise ValueError('unsafe packet path')
        if not source.is_file() or source.stat().st_size!=row['bytes']:
            raise ValueError('missing or changed packet input')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('packet pin mismatch')
    output.mkdir()
    for row in entries:
        target=output/row['target'];target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/row['source'],target)
        if target.stat().st_size!=row['bytes'] or hashlib.sha256(target.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('copied target pin mismatch; partial view must not be used')
    (output/'VIEW.json').write_text(json.dumps({'access_view':view,'held_out_mouse':held_out,
        'development_mice':[f'Mouse{i}' for i in range(1,6) if f'Mouse{i}'!=held_out],
        'access_attestation':False},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',type=Path,required=True);p.add_argument('--view',choices=['A','B'],required=True);p.add_argument('--held-out',required=True)
    a=p.parse_args();stage(a.root,a.output,a.view,a.held_out)
