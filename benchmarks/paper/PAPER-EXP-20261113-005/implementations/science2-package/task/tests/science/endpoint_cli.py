"""Finite local reference/participant/scorer path; no invocation at authoring.

The owner packet contains fixed learned categories, grouping and ROI inputs.
Participant access excludes protected reference cases and historical outputs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
from conditional_kernel import (case_keys, hierarchy_sensitivity, moment_errors,
                                need, reconstruct, validate_packet, validate_submission_case)

MAX_PACKET = 16*1024**2
MAX_SUBMISSION = 128*1024**2
MAX_CASE = 2*1024**2


def decode(raw):
    def pairs(items):
        result = {}
        for key,value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError('nonfinite JSON token: '+value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def read(path, maximum):
    path = Path(path)
    need(path.is_absolute() and not any(p.is_symlink() for p in (path,*path.parents)), 'ordinary absolute input')
    import stat
    before = path.stat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= maximum,
         'bounded single-link input')
    with path.open('rb') as stream:
        body = stream.read(before.st_size+1)
    after = path.stat()
    need(all(getattr(before,k) == getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),
         'stable input body')
    need(len(body) == before.st_size, 'complete input body')
    return body


def json_bytes(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def write(path, body, maximum):
    path = Path(path)
    need(len(body) <= maximum and path.is_absolute() and
         not any(p.is_symlink() for p in path.parents), 'bounded ordinary output')
    with path.open('xb') as stream:
        stream.write(body)


def packet(path):
    raw = read(path,MAX_PACKET); value = decode(raw)
    validate_packet(value, expected_units=19186, expected_recordings=99)
    return value, hashlib.sha256(raw).hexdigest()


def reference(packet_path, output_path, seconds=600):
    data, digest = packet(packet_path)
    end = time.monotonic()+seconds
    def tick(): need(time.monotonic()<end,'reference deadline')
    output = Path(output_path); need(not output.exists(),'new reference destination')
    total = 0
    with output.open('xb') as stream:
        header=json_bytes({'schema':'PFC_CONDITIONAL_CASES_V1','packet_sha256':digest,'cases':case_keys(data)})
        stream.write(header);total+=len(header)
        for animal in [None]+data['animals']:
            value = reconstruct(data,animal,tick); body=json_bytes(value)
            need(len(body)<=MAX_CASE and total+len(body)<=MAX_SUBMISSION,'reference retention bound')
            stream.write(body);total+=len(body)
    return {'cases':len(data['animals'])+1,'bytes':total,'scientific_claim':'fixed-map exact conditional moments'}


def candidate_cases(path, data, digest):
    # Complete validation barrier precedes the first target-dependent score.
    body = read(path,MAX_SUBMISSION)
    lines=body.splitlines();keys=case_keys(data)
    need(len(lines)==len(keys)+1 and all(0<len(line)<=MAX_CASE for line in lines),'all full/animal cases')
    header=decode(lines[0]);need(header=={'schema':'PFC_CONDITIONAL_CASES_V1','packet_sha256':digest,'cases':keys},
                                'immutable packet and full case roster')
    values=[decode(line) for line in lines[1:]]
    for value,key in zip(values,keys): validate_submission_case(value,data,key)
    return values,hashlib.sha256(body).hexdigest()


def score(packet_path, candidate_path, output_path, seconds=600):
    from continuous_analysis import analyse,compare
    data,digest=packet(packet_path)
    candidates,candidate_digest=candidate_cases(candidate_path,data,digest)
    end=time.monotonic()+seconds
    def tick(): need(time.monotonic()<end,'scoring deadline')
    records=[];reference_hierarchy=[];candidate_hierarchy=[]
    for animal,candidate in zip([None]+data['animals'],candidates):
        tick();truth=reconstruct(data,animal,tick)
        wanted=analyse(truth,data,tick);got=analyse(candidate,data,tick)
        reference_hierarchy.append(wanted['hierarchy']);candidate_hierarchy.append(got['hierarchy'])
        records.append({'case':candidate['case'],'moment_errors':moment_errors(candidate,truth),
                        'continuous_comparisons':compare(got,wanted),
                        'reference_hierarchy':wanted['hierarchy'],'candidate_hierarchy':got['hierarchy']})
    result={'schema':'PFC_FULL99_CONDITIONAL_SCORE_V1','packet_sha256':digest,
        'candidate_sha256':candidate_digest,'cases':records,
        'reference_animal_influence':hierarchy_sensitivity(reference_hierarchy[0],reference_hierarchy[1:],len(data['animals'])),
        'candidate_animal_influence':hierarchy_sensitivity(candidate_hierarchy[0],candidate_hierarchy[1:],len(data['animals'])),
        'roster':{'recordings':99,'units':19186,'animals':len(data['animals']),'families':12,'analytic_contexts':16,'gao_contexts':4},
        'claim':'descriptive fixed-map reconstruction and exhaustive grouped sensitivity; no population CI',
        'historical_diagnostics':data['historical_diagnostics'],
        'historical_equivalence':False,'biological_ground_truth':False,'readiness_count_delta':0}
    write(output_path,json_bytes(result),64*1024**2)
    return {'cases':len(records),'complete':True,'historical_equivalence':False,'readiness_count_delta':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['reference','score'])
    parser.add_argument('--packet',type=Path,required=True)
    parser.add_argument('--candidate',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.operation=='reference':
        need(args.candidate is None,'reference has no candidate input')
        result=reference(args.packet,args.output)
    else:
        need(args.candidate is not None,'score requires complete candidate')
        result=score(args.packet,args.candidate,args.output)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__': main()
