"""Hash-pin and import qualified095 transport helpers; no source mutation."""
from pathlib import Path
import hashlib,importlib,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PINS=json.loads((HERE/'QUALIFIED_IMPORTS.json').read_text())['files']
BASE=ROOT/'authoring/dmfc-timing/program-runner-v2'
for value in PINS.values():
    p=ROOT/value['path']
    if p.is_symlink()or p.stat().st_size!=value['bytes']or hashlib.sha256(p.read_bytes()).hexdigest()!=value['sha256']:raise ValueError('Qualified import source drift')
for name in ('absence','runtime_contract','host_budget','engine','recovery'):
    if name in sys.modules and Path(sys.modules[name].__file__).resolve()!=BASE/(name+'.py'):raise ValueError('Qualified module namespace collision')
sys.path.insert(0,str(BASE))
try:
    base=importlib.import_module('engine')
    recovery=importlib.import_module('recovery')
    HostBudget=importlib.import_module('host_budget').HostBudget
finally:sys.path.remove(str(BASE))
BaseEngine=base.Engine;regular=base.regular;snapshot=base.snapshot;digest=base.digest
recover_unit=recovery.recover;DOCKER=base.DOCKER;ENV=base.ENV
