"""Replay complete NEURAL-021 visual receipts, then call the pinned current scorer.

This trusted-operator component establishes source-consistent observation/answer
lineage. It does not establish who produced answers, prohibit tools, isolate a
participant, or inherit the different frozen-program producer's qualification.
The CLI is an operator recipe, not authorization for authentic grading.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types

HERE = Path(__file__).resolve().parent
IMPLEMENTATIONS = HERE.parent
MAX_JSON = 4 * 1024**2
MAX_RESULT = 256 * 1024
MAX_EVENTS = 2048 + 92
SOURCES = {
    'delivery': {'path':'paired-count-delivery-v1/delivery.py','bytes':15991,
                 'sha256':'d900456bbe77c27d813a5d5d8dc8352e6c67071c83c15b9e33afe38076ce0da3'},
    'interface': {'path':'paired-count-delivery-v1/interface.py','bytes':3533,
                  'sha256':'c748bdb0386713d505e1d5d79bec51645263b859471011df81f205168a6e61e2'},
    'scorer': {'path':'neural021-deferred-grade/science/private/scorer.py','bytes':3567,
               'sha256':'320234c9e89a6c8c282d88e273a629d82217b35a8714244dee52097625e60f01'},
}
PUBLIC_PINS = {
    'cases.json': {'bytes':4075,'sha256':'f5fc38ca363db9367e259c466fc017af9e8e216726b302cc6f757857554c34c0'},
    'training.npz': {'bytes':497917,'sha256':'5fae3b5cf74edbf99d5d4c5a4fa80d8ee1f02c55f92aa91de58d60714fe4159b'},
    'queries.npz': {'bytes':127544,'sha256':'64d29c93749d7b66f22d7112e7fdbe3764ffecef4b1989464f2af89801090047'},
}
TARGET_PIN = {'bytes':120748,'sha256':'3250773fb399d2967224a268965f45fb82844684fc03cc3c049cb011e03da965'}
MODES = ('direct_observation','typed_viewer')


def need(value, message):
    if not value:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def pin(body):
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}


def ordinary_path(path):
    path = Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path,*path.parents)),
         'Ordinary unlinked operand path required')
    return path


def identity(info):
    return tuple(getattr(info,name) for name in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))


def capture(path, expected, cap):
    """Capture exact stable bytes; never follow links or unboundedly read growth."""
    need(type(expected) is dict and set(expected)=={'bytes','sha256'}
         and type(expected['bytes']) is int and 0 < expected['bytes'] <= cap
         and type(expected['sha256']) is str and re.fullmatch('[0-9a-f]{64}',expected['sha256']),
         'Bounded exact content pin required')
    path = ordinary_path(path)
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==expected['bytes'],
             'Exact single-link regular operand required')
        body = stream.read(expected['bytes']+1)
        need(identity(before)==identity(os.fstat(stream.fileno()))==identity(path.stat())
             and pin(body)==expected, 'Operand changed or content pin mismatch')
    return body


def load_sources():
    """Authenticate original source before import; no data or target access."""
    bodies = {key:capture(IMPLEMENTATIONS/entry['path'],
                         {k:entry[k] for k in ('bytes','sha256')},65536)
              for key,entry in SOURCES.items()}
    modules = {}
    for key in ('delivery','scorer'):
        name = 'neural021_observation_grade_'+key
        module = types.ModuleType(name)
        module.__file__ = str(IMPLEMENTATIONS/SOURCES[key]['path'])
        sys.modules[name] = module  # The unchanged delivery dataclass needs its module.
        exec(compile(bodies[key],module.__file__,'exec'),module.__dict__)
        modules[key] = module
    need(modules['delivery']._interface_raw==bodies['interface'], 'Original interface changed during source loading')
    need({name:{'bytes':row[0],'sha256':row[1]} for name,row in modules['delivery'].PINS.items()}==PUBLIC_PINS,
         'Original public packet identity changed')
    modules['interface'] = modules['delivery'].interface
    return modules


def replay(sources, packet, expected_mode, submission_bytes, receipt_bytes):
    """Pure trusted-packet API; production enters through authentic load_public.

    Packet.from_arrays is appropriate for generated controls, but is not proof
    of authentic input provenance. The host must keep this API and packet private.
    """
    delivery,interface = sources['delivery'],sources['interface']
    need(expected_mode in MODES, 'Explicit supported expected visual mode required')
    need(type(packet) is delivery.Packet and len(packet.training)==272 and len(packet.queries)==92,
         'Complete original 272-training/92-query Packet required')
    cases = interface.strict_json(packet.cases_bytes)
    roster = interface.validate_queries(cases)
    need(len(roster)==92 and sum(row['condition']=='active' for row in roster)==52
         and sum(row['condition']=='passive' for row in roster)==40
         and [row.trial_id for row in packet.queries]==[row['trial_id'] for row in roster],
         'Complete original query roster and order required')
    submission = interface.strict_json(submission_bytes)
    ordered = interface.validate_submission(submission,cases,packet.cases_sha256)
    by_id = dict(zip((row['trial_id'] for row in roster),ordered))
    receipt = interface.strict_json(receipt_bytes)
    expected_keys = {'schema','mode','cases_sha256','observation_sha256','submission_sha256',
                     'query_count','events','runtime_qualified','note'}
    need(type(receipt) is dict and set(receipt)==expected_keys
         and receipt['schema']=='neural021_visual_delivery_receipt_v1'
         and receipt['mode']==expected_mode and receipt['cases_sha256']==packet.cases_sha256
         and receipt['observation_sha256']==packet.observation_sha256
         and receipt['submission_sha256']==pin(submission_bytes)['sha256']
         and type(receipt['query_count']) is int and receipt['query_count']==92
         and receipt['runtime_qualified'] is False, 'Exact visual condition/input/submission receipt required')
    events = receipt['events']
    need(type(events) is list and 184 <= len(events) <= MAX_EVENTS, 'Complete bounded visual event history required')
    session = delivery.Session(packet,expected_mode)
    previous = '0'*64
    training_seen,query_seen = set(),set()
    for index,event in enumerate(events):
        need(type(event) is dict and type(event.get('sequence')) is int and event['sequence']==index
             and event.get('previous_sha256')==previous, 'Visual event order/hash chain mismatch')
        operation = event.get('operation')
        fields = {'training_view':{'training_index','svg_sha256'},
                  'query_view':{'trial_id','viewport','svg_sha256'},
                  'answer':{'trial_id','answer_sha256'}}
        need(operation in fields and set(event)=={'sequence','operation','previous_sha256','sha256'}|fields[operation],
             'Exact original visual event fields required')
        need(event['sha256']==pin(encode({k:v for k,v in event.items() if k!='sha256'}))['sha256'],
             'Visual event checksum mismatch')
        if operation=='training_view':
            rendered = session.calibration(event['training_index'])
            need(pin(rendered.encode())['sha256']==event['svg_sha256'], 'Training observation changed')
            training_seen.add(event['training_index'])
        elif operation=='query_view':
            need(type(event['viewport']) is dict, 'Typed original viewport required')
            rendered = session.view(event['trial_id'],**event['viewport'])
            need(pin(rendered.encode())['sha256']==event['svg_sha256'], 'Query observation changed')
            query_seen.add(event['trial_id'])
        else:
            need(type(event['trial_id']) is str and event['trial_id'] in by_id, 'Answer identity outside complete submission')
            values = by_id[event['trial_id']]
            need(pin(encode(values))['sha256']==event['answer_sha256'], 'Answer differs from committed submission')
            session.answer(event['trial_id'],values)
        previous = event['sha256']
    regenerated_submission,regenerated_receipt = session.finish()
    need(regenerated_submission==submission_bytes and regenerated_receipt==receipt_bytes,
         'Complete original Session output differs from captured visual artifacts')
    return {'schema':'neural021_visual_replay_v1','mode':expected_mode,'queries':92,
            'calibration_trials_available':272,'distinct_calibration_trials_viewed':len(training_seen),
            'distinct_queries_viewed':len(query_seen),'events':len(events),'last_event_sha256':previous,
            'observation_sha256':packet.observation_sha256,'cases_sha256':packet.cases_sha256,
            'submission':pin(submission_bytes),'receipt':pin(receipt_bytes)}


def evaluate(sources, packet, expected_mode, submission_bytes, receipt_bytes, load_private_targets):
    """Replay all observations/answers before the unchanged scorer's target call."""
    lineage = replay(sources,packet,expected_mode,submission_bytes,receipt_bytes)
    calls = 0
    def targets_once():
        nonlocal calls
        need(calls==0, 'Private target callback may run only once')
        calls += 1
        return load_private_targets()
    score = sources['scorer'].score(submission_bytes,packet.cases_bytes,targets_once,sources['interface'])
    need(calls==1, 'Original scorer must load one complete private target generation')
    return {'schema':'neural021_observation_grade_v1','task_id':'NEURAL-021','mode':expected_mode,
            'status':'complete_source_replay_and_numerical_grade','replay':lineage,'score':score,
            'source':SOURCES,'private_target_callbacks':calls,'runtime_qualified':False,
            'scientific_qualified':False,'submission_ready':False,
            'scope':'Original complete one-session retrospective endpoint; historically exposed labels. '
                    'Source replay does not identify the answer producer, demonstrate no-tools isolation, '
                    'or establish native understanding, generalization, neural advantage or SOTA.'}


def operator_grade(public_root, expected_mode, submission_path, submission_pin,
                   receipt_path, receipt_pin, target_path, output_path):
    """Original fixed public/target generations only; no alternative-data override."""
    public_root = ordinary_path(public_root)
    target_path = ordinary_path(target_path)
    output_path = ordinary_path(output_path)
    submission_path,receipt_path = ordinary_path(submission_path),ordinary_path(receipt_path)
    need(public_root.is_dir() and output_path.parent.is_dir() and not os.path.lexists(output_path),
         'Existing public directory and fresh operator output required')
    paths = [submission_path,receipt_path,target_path,output_path]
    need(len(set(paths))==4 and all(not path.is_relative_to(public_root) for path in paths)
         and all(not path.is_relative_to(IMPLEMENTATIONS) for path in paths),
         'Separate operator artifacts, protected target and source/public trees required')
    sources = load_sources()
    need(expected_mode in MODES, 'Explicit supported expected visual mode required')
    submission = capture(submission_path,submission_pin,MAX_JSON)
    receipt = capture(receipt_path,receipt_pin,MAX_JSON)
    import numpy as np  # Existing operator dependency; this component installs nothing.
    packet = sources['delivery'].load_public(public_root,np)
    def targets():
        return sources['interface'].strict_json(capture(target_path,TARGET_PIN,1024**2))
    result = evaluate(sources,packet,expected_mode,submission,receipt,targets)
    result['authenticated_input_generation'] = {'public':PUBLIC_PINS,'private_targets':TARGET_PIN}
    body = encode(result)
    need(len(body)<=MAX_RESULT, 'Bounded complete result required')
    with output_path.open('xb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-root',required=True)
    parser.add_argument('--mode',choices=MODES,required=True)
    for name in ('submission','receipt'):
        parser.add_argument('--'+name,required=True)
        parser.add_argument('--'+name+'-bytes',required=True,type=int)
        parser.add_argument('--'+name+'-sha256',required=True)
    parser.add_argument('--private-targets',required=True)
    parser.add_argument('--output',required=True)
    args = parser.parse_args(argv)
    try:
        result = operator_grade(args.public_root,args.mode,args.submission,
            {'bytes':args.submission_bytes,'sha256':args.submission_sha256},args.receipt,
            {'bytes':args.receipt_bytes,'sha256':args.receipt_sha256},args.private_targets,args.output)
    except (ValueError,OSError,KeyError,TypeError) as error:
        # Avoid echoing private operands or values supplied by a failed target loader.
        print(json.dumps({'schema':'neural021_observation_grade_failure_v1','error_type':type(error).__name__,
                          'complete_grade':False,'automatic_retry':False}),file=sys.stderr)
        return 2
    print(json.dumps({'status':result['status'],'mode':result['mode'],'queries':92}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
