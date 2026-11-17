"""Explicit full-output producer child ABI, separate from the legacy bridge.

Only a future qualified protected launcher may select this exact source and its
complete immutable program tree. Command-line extents carry no native authority.
"""
import hashlib,sys,types
from .native_bridge import read_at,parse

def main(invocation_path,output_path,invocation_bytes,driver_bytes):
    if invocation_path!='/inputs/invocation.json'or output_path!='/output':raise ValueError('fixed full-scientific mounts')
    if type(invocation_bytes)is not int or invocation_bytes<=0 or type(driver_bytes)is not int or driver_bytes<=0:raise ValueError('explicit admitted source extents')
    raw=read_at('/inputs','invocation.json',invocation_bytes);inv=parse(raw)
    if inv['schema']!='jaxley_full_scientific_invocation_v1'or inv['kind']!='native_reference':raise ValueError('separate trusted reference ABI')
    job=inv['scientific_job']
    if job['route']!='prospective_full_scientific_source_v1'or job['metadata_limits']['invocation_bytes']!=invocation_bytes:raise ValueError('original route/extent selection')
    pin=inv['source']
    if pin['path']!='scientific_driver.py'or pin['bytes']!=driver_bytes:raise ValueError('fixed full scientific driver')
    body=read_at('/program',pin['path'],driver_bytes)
    if len(body)!=driver_bytes or hashlib.sha256(body).hexdigest()!=pin['sha256']:raise ValueError('actual source bytes changed')
    # Parent verifies every module in the immutable source tree before birth.
    # This fixed module path does not make an arbitrary dictionary a source owner.
    if '/program'not in sys.path:sys.path.insert(0,'/program')
    module=types.ModuleType('fixed_full_scientific_driver');module.__file__='/program/scientific_driver.py'
    exec(compile(body,module.__file__,'exec'),module.__dict__)
    result=module.run_exact_job(job,'/inputs','/output')
    if result is not None:raise ValueError('producer result must be actual complete files')

if __name__=='__main__':
    if len(sys.argv)!=5:raise SystemExit('invocation, output, explicit invocation bytes, explicit driver bytes required')
    main(sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4]))
