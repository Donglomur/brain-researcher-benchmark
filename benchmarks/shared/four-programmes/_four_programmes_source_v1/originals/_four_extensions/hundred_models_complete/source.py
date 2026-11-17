"""Source custody after independent bootstrap checks; manifest is not a sandbox."""
from pathlib import Path
from .guard import capture,need
_FILES=None

def install_manifest(package,manifest):
    global _FILES
    need(_FILES is None,'source bindings installed once per owned process')
    need(manifest['schema']=='hundred_models_runtime_source_v1','complete runtime source manifest')
    rows=manifest['files'];need(len({r['path'] for r in rows})==len(rows),'unique source entries')
    _FILES=(Path(package).absolute(),{x['path']:x for x in rows})

def source_bytes(package,relative,budget):
    need(_FILES is not None and Path(package).absolute()==_FILES[0],'previous complete-source bootstrap admission')
    need(relative in _FILES[1],'operative source explicitly selected')
    return capture(package,_FILES[1][relative],budget)
