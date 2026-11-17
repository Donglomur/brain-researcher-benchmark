"""Inert official-image runtime and independent comparator scalar checks only."""
import importlib.util
import json
from pathlib import Path
import platform
import sys

def load(name):
    p=Path('/task')/(name+'.py')
    spec=importlib.util.spec_from_file_location(name,p)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

assert sys.version_info[:3]==(3,12,16) and platform.system()=='Linux' and platform.machine()=='aarch64'
assert sys.flags.isolated==1 and sys.dont_write_bytecode
count=load('comparator_controls').check(load('comparator'))
print(json.dumps({'schema':'tms_official_stdlib_probe_v1','python':'3.12.16','platform':'linux/arm64',
    'stdlib_only':True,'inert_controls':count,'original_input_reads':0,'reference_reads':0,
    'authentic_candidate_runs':0,'scientific_result':False},sort_keys=True),flush=True)
