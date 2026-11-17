"""Trusted generic-path candidate entry; dynamic Python remains in one capability.

This process never creates a native-success receipt. Host/daemon observations
alone establish closure. Candidate outputs and self-reported file hashes remain
untrusted until host admission after container closure. No call occurs on import.
"""
import ast
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys

CLASSES = [1, 2, 3, 4, 11, 12, 13, 14, 21, 22, 23, 24]
HANDLES = ["BP_LDA", "TM_LDA", "RBF_KRR", "HISTORICAL_BP_LDA"]
CHANNELS = ['Fp1','AF7','AF3','F1','F3','F5','F7','FT7','FC5','FC3','FC1','C1','C3','C5','T7','TP7','CP5','CP3','CP1','P1','P3','P5','P7','P9','PO7','PO3','O1','Iz','Oz','POz','Pz','CPz','Fpz','Fp2','AF8','AF4','AFz','Fz','F2','F4','F6','F8','FT8','FC6','FC4','FC2','FCz','Cz','C2','C4','C6','T8','TP8','CP6','CP4','CP2','P2','P4','P6','P8','P10','PO8','PO4','O2']


def need(condition, message):
    if not condition: raise ValueError(message)


def exact(value, keys):
    need(type(value) is dict and set(value) == set(keys), "exact runner schema")


def parse(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, "duplicate key"); result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: need(False, "finite JSON"))


def ordinary(path):
    need(type(path) is str and path.startswith('/') and not path.startswith('//') and '\\' not in path and
         all(p not in ('', '.', '..') for p in path.split('/')[1:]), "canonical generic path")
    value = Path(path)
    need(not any(p.is_symlink() for p in (value, *value.parents)), "no source aliases")
    return value


def _pin(desc, cap):
    exact(desc, ('path', 'bytes', 'sha256')); path = ordinary(desc['path'])
    need(type(desc['bytes']) is int and 0 <= desc['bytes'] <= cap and type(desc['sha256']) is str and
         len(desc['sha256']) == 64 and all(x in '0123456789abcdef' for x in desc['sha256']), "exact source/input descriptor")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd); need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == desc['bytes'], "complete ordinary mounted file")
        digest = hashlib.sha256(); total = 0
        while total <= desc['bytes']:
            block = os.read(fd, min(1048576, desc['bytes'] + 1 - total))
            if not block: break
            total += len(block); digest.update(block)
        after = os.fstat(fd); named = path.lstat()
        fields = ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink')
        need(total == desc['bytes'] and digest.hexdigest() == desc['sha256'] and
             all(getattr(before,k) == getattr(after,k) == getattr(named,k) for k in fields), "actual complete immutable mounted bytes")
    finally: os.close(fd)
    return path


def _source(desc):
    path = _pin(desc, 65536)
    raw = path.read_bytes(); need(len(raw) == desc['bytes'] and hashlib.sha256(raw).hexdigest() == desc['sha256'], "unchanged action source")
    text = raw.decode('utf-8', errors='strict'); ast.parse(text, filename=desc['path'])
    return text


def validate_context(context):
    exact(context, ('schema','task_id','access_policy','mode','replication','view','context_alias','class_ids',
                    'representation','query','training','models','tools','remaining'))
    need(context['schema'] == 'neural081_candidate_context_v4' and context['task_id'] == 'NEURAL-081' and
         context['access_policy'] == 'single_query_transductive_v4' and context['mode'] in ('F','I') and
         context['replication'] in ('r0','r1','r2') and context['view'] in ('EEG','ZERO'), "selected public context")
    alias = context['context_alias']; need(type(alias) is str and len(alias) == 32 and all(v in '0123456789abcdef' for v in alias), "one opaque alias")
    need(context['class_ids'] == CLASSES and all(type(v) is int for v in context['class_ids']), "canonical class axis")
    need(context['representation'] == dict(dtype='float32',shape=[64,512],sample_rate_hz=128,units='V',channels=CHANNELS), "complete original representation")
    need(context['query'] == dict(path='/input/query.npy', row_alias=alias), "exactly one query")
    exact(context['training'], ('eeg_path','labels_path','rows_path','shape'))
    train = context['training']; need(train['eeg_path'] == '/input/train.npy' and train['labels_path'] == '/input/train_labels.npy' and train['rows_path'] == '/input/train_rows.json', "generic complete training paths")
    need(type(train['shape']) is list and len(train['shape']) == 3 and type(train['shape'][0]) is int and
         108 <= train['shape'][0] <= 90000 and train['shape'][1:] == [64,512], "complete nine-person training shape")
    need(type(context['models']) is list and len(context['models']) == 4, "four original models")
    for item, handle in zip(context['models'], HANDLES):
        exact(item, ('handle','path')); need(item == dict(handle=handle,path='/models/'+handle+'/model.json'), "generic sealed model handle")
    exact(context['tools'], ('api_version','module','source_path','source_sha256'))
    need(context['tools']['api_version'] == 'neural081_tools_v2' and context['tools']['module'] == 'reference_tools' and context['tools']['source_path'] == '/tools/reference_tools.py', "immutable generic tool API")
    need(type(context['tools']['source_sha256']) is str and len(context['tools']['source_sha256']) == 64, "tool source pin")
    exact(context['remaining'], ('native_seconds','native_actions','provider_requests','scratch_write_bytes','managed_read_bytes','source_bytes','normal_seconds_remaining'))
    for key, value in context['remaining'].items():
        if key == 'normal_seconds_remaining': need(type(value) in (int,float) and math.isfinite(value) and value >= 0, "relative finite time")
        else: need(type(value) is int and value >= 0, "exact relative remaining counter")
    return context


def probability_row(values):
    need(type(values) is list and len(values) == 12 and all(type(x) in (int,float) and math.isfinite(x) and 0 <= x <= 1 for x in values), "twelve finite nonboolean probabilities")
    row = [float(x) for x in values]
    need(abs(math.fsum(row)-1.) <= 1e-6, "canonical probability sum, no renormalization")
    return row


def _write(path, value):
    raw = (json.dumps(value, sort_keys=True, separators=(',',':'), ensure_ascii=True, allow_nan=False)+'\n').encode()
    temporary = path.with_name(path.name+'.new')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream: stream.write(raw); stream.flush(); os.fsync(fd)
    finally: os.close(fd)
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def _artifacts(root, max_bytes, max_entries):
    stack = [root]; rows = []; count = total = 0
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                count += 1; need(count <= max_entries, "complete candidate file entry bound")
                info = entry.stat(follow_symlinks=False); path = Path(entry.path)
                if stat.S_ISDIR(info.st_mode): stack.append(path); continue
                need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "ordinary created file")
                if path == root/'runtime-artifacts.json': continue
                total += info.st_size; need(total <= max_bytes, "complete candidate file byte bound")
                digest = hashlib.sha256(); size = 0
                with path.open('rb') as stream:
                    for block in iter(lambda: stream.read(1048576), b''): size += len(block); digest.update(block)
                need(size == info.st_size, "stable created file extent")
                rows.append(dict(relative_path=str(path.relative_to(root)), bytes=size, sha256=digest.hexdigest()))
    return sorted(rows, key=lambda value: value['relative_path'])


def execute(request):
    exact(request, ('schema','operation','context','input_manifest','action_source','programme','workspace_cap_bytes','workspace_entry_cap'))
    need(request['schema'] == 'neural081_candidate_runner_v1' and request['operation'] in ('python','fixed','author_python'), "selected runner operation")
    operation = request['operation']; context = request['context']
    if operation == 'author_python':
        exact(context, ('schema','replication','public_protocol')); need(context['schema'] == 'neural081_author_context_v1' and context['replication'] in ('r0','r1','r2'), "data-free author context")
    else: validate_context(context)
    need(type(request['input_manifest']) is list and request['input_manifest'], "exact mounted input/source manifest")
    seen = {}; logical_bytes = 0
    for desc in request['input_manifest']:
        exact(desc, ('path','bytes','sha256')); path = desc['path']; ordinary(path)
        need(path not in seen and path.startswith(('/input/','/models/','/tools/','/programme/','/action/')), "unique generic admitted input")
        if operation == 'author_python': need(not path.startswith(('/input/','/models/')), "author has no authentic inputs/models")
        _pin(desc, 2**63-1); seen[path] = desc; logical_bytes += desc['bytes']
    if operation != 'author_python':
        need({'/input/query.npy','/input/train.npy','/input/train_labels.npy','/input/train_rows.json'} | {'/models/'+handle+'/model.json' for handle in HANDLES} <= set(seen), "full training/current query and models present")
        need(logical_bytes <= context['remaining']['managed_read_bytes'], "trusted authentication read reservation")
        tool = seen.get('/tools/reference_tools.py'); need(tool and tool['sha256'] == context['tools']['source_sha256'], "same frozen inference source")
    for key in ('workspace_cap_bytes','workspace_entry_cap'): need(type(request[key]) is int and request[key] > 0, "positive native output bounds")
    need(os.getcwd() == '/workspace', "only private generic cwd")
    sys.path[:0] = ['/tools','/programme']
    result = {'schema':'neural081_candidate_operation_result_v1','operation':operation,'status':'completed','error_category':None,'probabilities':None}
    try:
        if operation == 'fixed':
            need(request['action_source'] is None, "fixed route has no external query action")
            programme = request['programme']; exact(programme, ('entrypoint','files'))
            need(programme['entrypoint'] == '/programme/program.py' and type(programme['files']) is list and 1 <= len(programme['files']) <= 16, "sealed fixed entry and helper closure")
            need(sum(desc['bytes'] for desc in programme['files']) <= 524288, "sealed source byte cap")
            for desc in programme['files']:
                need(desc['path'].startswith('/programme/') and desc['path'].endswith('.py') and seen.get(desc['path']) == desc, "same sealed program source")
            spec = importlib.util.spec_from_file_location('sealed_candidate_program', programme['entrypoint'])
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            need(callable(getattr(module,'predict',None)), "one fixed predict(context) entry")
            result['probabilities'] = probability_row(module.predict(context))
        else:
            need(request['programme'] is None and type(request['action_source']) is dict and
                 seen.get(request['action_source']['path']) == request['action_source'], "exact submitted action source")
            text = _source(request['action_source'])
            namespace = {'__name__':'__candidate_action__','__file__':request['action_source']['path'],'context':context}
            exec(compile(text, request['action_source']['path'], 'exec'), namespace, namespace)
    except UnicodeError:
        result.update(status='closed_encoding_error', error_category='encoding_error', probabilities=None)
    except (Exception, SystemExit):
        result.update(status='closed_analytical_error', error_category='analytical_error', probabilities=None)
    _write(Path('/workspace/RESULT.json'), result)
    artifacts = _artifacts(Path('/workspace'), request['workspace_cap_bytes'], request['workspace_entry_cap'])
    _write(Path('/workspace/runtime-artifacts.json'), {'schema':'neural081_runtime_artifacts_v1','artifacts':artifacts,'operation_result':'RESULT.json'})
    return result


def main():
    need(len(sys.argv) == 2 and sys.argv[1] == '/action/request.json', "generic source-owned request argument")
    path = ordinary(sys.argv[1]); info = path.lstat(); need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= 2097152, "bounded exact request")
    with path.open('rb') as stream: raw = stream.read(2097153)
    need(len(raw) == info.st_size, "complete request")
    execute(parse(raw))


if __name__ == '__main__':
    try: main()
    except BaseException:
        # Custody/protocol failures are fatal; ordinary analytical exceptions were
        # handled inside execute. No traceback/private diagnostic is emitted.
        sys.stderr.write('candidate_protocol_failure\n'); sys.exit(2)
