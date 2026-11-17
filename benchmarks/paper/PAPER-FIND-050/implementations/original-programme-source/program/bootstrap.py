"""Neutral version gate before candidate or independently trusted producer entry."""
import importlib.metadata,json,os,platform,sys
from pathlib import Path
v=json.loads(Path('/input/CASE.json').read_text())['versions']
if v['python']!=platform.python_version():raise ValueError('exact immutableimage Python version')
for package,version in v.items():
    if package!='python' and importlib.metadata.version(package)!=version:raise ValueError('exact numerical dependency version: '+package)
os.execv(sys.executable,[sys.executable,'-I','-B','/program.py',*sys.argv[1:]])
