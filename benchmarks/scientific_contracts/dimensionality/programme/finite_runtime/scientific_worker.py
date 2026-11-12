"""Future isolated scientific process: typed array I/O, then genuine kernel dispatch.

Never imported or invoked by engineering controls. The controller supplies no
in-process scientific callback. The qualification monitor accounts all I/O and CPU.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from .common import require, decode, encode, relative_path
from .transport import resolve_parameter_tree

def run(request):
    require(request['scientific_execution_qualified'] is True,'SCIENTIFIC_GATE_CLOSED')
    require(request['issuer_namespace'] in {'independent_reference','trusted_preparation','trusted_collection','protected_grade'},
            'INVALID_SCIENTIFIC_ISSUER')
    def guard(effect):
        require(time.monotonic()<request['original_deadline'],'ORIGINAL_DEADLINE_EXPIRED',effect)
    guard('before_scientific_dependency_import')
    import numpy as np
    from finite_science.dispatch import execute
    def read_table(desc):
        guard('before_scientific_parameter_open')
        p=Path(desc['sandbox_path']);require(str(p).startswith('/tables/'),'TABLE_OUTSIDE_MOUNT')
        with p.open('rb') as stream:
            guard('before_scientific_parameter_read');body=stream.read(desc['bytes']+1)
        require(len(body)==desc['bytes'] and hashlib.sha256(body).hexdigest()==desc['sha256'],
                'PARAMETER_TABLE_IDENTITY_MISMATCH')
        guard('after_scientific_parameter_read');return body
    parameters=resolve_parameter_tree(request['parameters'],request['tables'],read_table,
        max_rows=request['max_parameter_rows'],guard=guard)
    arrays={}
    for name,desc in request['arrays'].items():
        relative_path(name)
        require(desc['format']=='npy_numeric_v1' and desc['readonly'],'UNQUALIFIED_ARRAY_FORMAT')
        p=Path(desc['sandbox_path'])
        require(str(p).startswith('/inputs/'),'ARRAY_OUTSIDE_QUALIFIED_MOUNT')
        guard('before_scientific_array_open')
        with p.open('rb') as stream:
            sha=hashlib.sha256();size=0
            while True:
                guard('before_scientific_array_hash_chunk')
                chunk=stream.read(65536)
                if not chunk:break
                sha.update(chunk);size+=len(chunk)
        require(size==desc['bytes'] and sha.hexdigest()==desc['sha256'],'SCIENTIFIC_INPUT_SUBSTITUTION')
        guard('before_scientific_array_decode')
        value=np.load(p,allow_pickle=False,mmap_mode='r')
        require(value.dtype.kind in 'biufc' and list(value.shape)==desc['shape']
                and str(value.dtype)==desc['dtype'],'SCIENTIFIC_ARRAY_SCHEMA_MISMATCH')
        arrays[name]=value
    guard('immediately_before_scientific_kernel')
    result=execute(request['operation'],{'arrays':arrays,'protocol':request['protocol'],
                   'request':parameters,'lineage':request['lineage']})
    guard('after_scientific_kernel_before_any_output_effect')
    artifacts=[]
    def transport(value,path):
        guard('next_scientific_output_node')
        if isinstance(value,np.ndarray):
            require(value.dtype.kind in 'biufc','EXECUTABLE_RESULT_ARRAY')
            name=relative_path(path+'.npy');p=Path('/outputs')/name
            p.parent.mkdir(parents=True,exist_ok=True)
            guard('before_scientific_array_output_create')
            with p.open('xb') as stream:np.save(stream,value,allow_pickle=False)
            guard('after_scientific_array_output_write')
            sha=hashlib.sha256();size=0
            with p.open('rb') as stream:
                while True:
                    guard('before_output_hash_chunk')
                    chunk=stream.read(65536)
                    if not chunk:break
                    sha.update(chunk);size+=len(chunk)
            d={'path':name,'bytes':size,'sha256':sha.hexdigest(),'shape':list(value.shape),
               'dtype':str(value.dtype),'format':'npy_numeric_v1','producer':request['request_id']}
            artifacts.append(d);return {'artifact':d}
        if isinstance(value,np.generic):return transport(value.item(),path)
        if isinstance(value,dict):return {k:transport(v,path+'/'+relative_path(k)) for k,v in value.items()}
        if isinstance(value,(list,tuple)):return [transport(v,path+f'/{i}') for i,v in enumerate(value)]
        # Nonfinite scalars are refused rather than silently made into positive estimates.
        return value
    result=transport(result,'result')
    guard('before_scientific_response_completion')
    return {'schema':'finite_scientific_result_v1','request_id':request['request_id'],
            'request_sha256':hashlib.sha256(encode(request)).hexdigest(),
            'source_manifest_sha256':request['source_manifest_sha256'],
            'lineage':request['lineage'],'result':result,'artifacts':artifacts}

def main():
    body=sys.stdin.buffer.read(1024*1024+1)
    req=decode(body)
    output=run(req)
    body=encode(output)
    require(time.monotonic()<req['original_deadline'],'ORIGINAL_DEADLINE_EXPIRED','before_final_scientific_stdout')
    sys.stdout.buffer.write(body);sys.stdout.buffer.flush()
    require(time.monotonic()<req['original_deadline'],'ORIGINAL_DEADLINE_EXPIRED','after_final_scientific_stdout')

if __name__=='__main__':main()
