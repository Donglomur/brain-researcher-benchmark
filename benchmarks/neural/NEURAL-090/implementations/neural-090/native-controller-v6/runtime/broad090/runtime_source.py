"""Verify a minimal exact reference code capsule, never the original data root."""
from pathlib import Path
import os,stat
from programme.contracts import need,Asset
from .custody import open_pinned,stable
from .catalogue import exact_json

def verify_runtime(root,manifest_asset,account,ledger):
    root=Path(root);need(type(manifest_asset) is Asset and manifest_asset.path=='RUNTIME_SOURCE.json','exact selected runtime source manifest')
    f=None
    try:
        f,before=open_pinned(root,manifest_asset,account,ledger);account.charge('read',manifest_asset.pin.bytes+1)
        raw=f.read(manifest_asset.pin.bytes+1);need(len(raw)==manifest_asset.pin.bytes and stable(before,os.fstat(f.fileno())),'stable runtime manifest')
        manifest=exact_json(raw)
    except BaseException as e:ledger.propagated('runtime-manifest-read',e)
    finally:
        if f is not None:ledger.attempt('runtime-manifest-close',f.close)
    ledger.raise_first();need(set(manifest)=={'schema','members'} and manifest['schema']=='n090-minimal-runtime-v1','exact minimal capsule schema')
    members=[Asset.parse(v) for v in manifest['members']];names={a.path for a in members}
    need(len(names)==len(members) and manifest_asset.path not in names,'unique executable-source members')
    need('broad090/worker.py' in names and 'broad090/models.py' in names,'actual original-reference worker')
    allowed=lambda n:n.startswith('broad090/') or n.startswith('vendor/experiments/') or n in ('programme/contracts.py','programme/n090_adapter.py','programme/n090_support.py','source/neural090/public/context.py')
    need(all(allowed(n) for n in names),'no original assets/intake/private result mounts in code capsule')
    actual=set()
    for base,dirs,files in os.walk(root,followlinks=False):
        for name in dirs:
            p=Path(base)/name;need(not p.is_symlink(),'no capsule symlink directories')
        for name in files:
            p=Path(base)/name;need(stat.S_ISREG(p.lstat().st_mode) and not p.is_symlink(),'ordinary capsule files only');actual.add(p.relative_to(root).as_posix())
    need(actual==names|{manifest_asset.path},'whole minimal code capsule tree, no hidden payloads')
    for asset in members:
        f=None
        try:f,_=open_pinned(root,asset,account,ledger)
        except BaseException as e:ledger.propagated('runtime-member-read',e)
        finally:
            if f is not None:ledger.attempt('runtime-member-close',f.close)
        ledger.raise_first()
    return manifest

def verify_loaded_modules(root,manifest):
    import sys
    root=Path(root).resolve()
    for row in manifest['members']:
        relative=row['path']
        if not relative.endswith('.py'):continue
        name=relative[:-3].replace('/','.')
        if relative.startswith('vendor/experiments/'):
            name=relative[len('vendor/experiments/'):-3].replace('/','.')
        if name.endswith('.__init__'):name=name[:-9]
        module=sys.modules.get(name)
        if module is not None:
            need(getattr(module,'__file__',None) is not None and Path(module.__file__).resolve()==root/relative,'actual loaded source module has the selected capsule origin')
    return True

def prepare_capsule(source_root,manifest_asset,destination,account,ledger):
    """Copy only exact selected ordinary code into a fresh evaluator-owned root.

    This does not install, publish, execute or qualify it. A failed partial root
    is retained as partial; no preexisting path is deleted/replaced or retried.
    The native owner must make completed roots read-only in actor namespaces.
    """
    from .custody import write_fresh
    destination=Path(destination);need(not destination.exists(),'fresh owned code capsule')
    need(type(manifest_asset) is Asset and manifest_asset.path=='RUNTIME_SOURCE.json','exact selected capsule-manifest path')
    bodies={};f=None
    try:
        f,before=open_pinned(source_root,manifest_asset,account,ledger);account.charge('read',manifest_asset.pin.bytes+1)
        body=f.read(manifest_asset.pin.bytes+1);need(len(body)==manifest_asset.pin.bytes and stable(before,os.fstat(f.fileno())),'whole exact source selection')
        manifest=exact_json(body)
    except BaseException as e:ledger.propagated('capsule-selection',e)
    finally:
        if f is not None:ledger.attempt('capsule-selection-close',f.close)
    ledger.raise_first();need(set(manifest)=={'schema','members'} and manifest['schema']=='n090-minimal-runtime-v1','declared exact source capsule')
    assets=[Asset.parse(v) for v in manifest['members']]
    names={a.path for a in assets}
    need(len(names)==len(assets) and manifest_asset.path not in names,'unique selected code members')
    allowed=lambda n:n.startswith('broad090/') or n.startswith('vendor/experiments/') or n in ('programme/contracts.py','programme/n090_adapter.py','programme/n090_support.py','source/neural090/public/context.py')
    need(all(allowed(n) for n in names) and {'broad090/worker.py','broad090/models.py'}<=names,'complete selected code only, before any copy effect')
    destination.mkdir(mode=0o700)
    for asset in assets:
        target=destination/asset.path;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True);f=None
        try:
            f,before=open_pinned(source_root,asset,account,ledger);account.charge('read',asset.pin.bytes+1)
            content=f.read(asset.pin.bytes+1);need(len(content)==asset.pin.bytes and stable(before,os.fstat(f.fileno())),'stable selected source copy')
        except BaseException as e:ledger.propagated('capsule-source-copy',e)
        finally:
            if f is not None:ledger.attempt('capsule-copy-source-close',f.close)
        ledger.raise_first();need(write_fresh(target,content,account,ledger)==asset.pin,'exact source copy identity')
    need(write_fresh(destination/manifest_asset.path,body,account,ledger)==manifest_asset.pin,'exact source selection copy')
    verify_runtime(destination,manifest_asset,account,ledger)
    return destination
