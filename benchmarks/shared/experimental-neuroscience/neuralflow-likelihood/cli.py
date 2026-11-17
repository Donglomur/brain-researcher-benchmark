"""Bounded local component CLI. Inputs and grading outputs are evaluator-only."""
import argparse
from decimal import Decimal
import json
import math
import os
import stat

from likelihood import (ContractError, build_lono_index, case_key, fields,
                        normalized_population_comparison, public_view, score_lono)

MAX_BYTES = 16 * 1024 * 1024


def pairs(items):
    result = {}
    for key,value in items:
        if key in result:
            raise ContractError("duplicate JSON field")
        result[key]=value
    return result


def read_json(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>MAX_BYTES:
            raise ContractError("ordinary bounded single-link input required")
        with os.fdopen(fd,'rb',closefd=False) as f:
            body=f.read(MAX_BYTES+1)
        after=os.fstat(fd)
        if (len(body)!=before.st_size or len(body)>MAX_BYTES or
                (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=
                (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)):
            raise ContractError("input changed during read")
        def invalid(value):
            raise ContractError("nonfinite JSON literal")
        def finite_float(token):
            value=float(token)
            if not math.isfinite(value) or (value==0 and Decimal(token)!=0):
                raise ContractError("nonfinite or underflowing JSON number")
            return value
        return json.loads(body.decode('utf-8'),object_pairs_hook=pairs,
                          parse_constant=invalid,parse_float=finite_float)
    finally:
        os.close(fd)


def dispatch(operation, payload):
    if operation=='normalize':
        fields(payload,('population','single_neurons','expected_units'),'normalization input')
        return {**normalized_population_comparison(**payload),
                'trusted_engine_outputs_required':True,'candidate_provenance_verified':False}
    if operation=='project-one':
        fields(payload,('projection','roster','case'),'projection input')
        fields(payload['case'],('population_id','subject_id','session_id','trial_id','unit_id'),'case')
        return public_view(build_lono_index(payload['projection'],payload['roster']),case_key(payload['case']))
    fields(payload,('projection','roster','predictions','numerics'),'grading input')
    binding={}
    for row in payload['numerics']:
        fields(row,('population_id','subject_id','session_id','trial_id','unit_id','knots_seconds','quadrature_seconds'),'numerics row')
        key=case_key(row)
        if key in binding:
            raise ContractError('duplicate evaluator numerical binding')
        binding[key]={k:row[k] for k in ('knots_seconds','quadrature_seconds')}
    return score_lono(build_lono_index(payload['projection'],payload['roster']),payload['predictions'],binding)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('project-one','score-lono','normalize'))
    parser.add_argument('--input',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    result=dispatch(args.operation,read_json(args.input))
    encoded=(json.dumps(result,sort_keys=True,allow_nan=False,separators=(',',':'))+'\n').encode()
    if len(encoded)>MAX_BYTES:
        raise ContractError('component output exceeds16MiB bound')
    # Exclusive creation: a failure cannot overwrite an earlier scientific result.
    fd=os.open(args.out,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:
        f.write(encoded);f.flush();os.fsync(f.fileno())


if __name__=='__main__':
    main()
