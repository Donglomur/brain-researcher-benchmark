"""Four-resource ordinary recovery. A renamed live ID is detected, not removed."""
import copy
import json
from pathlib import Path
import re
import uuid
from support import (HERE, SHARED, ROOT, ID, need, repo, read, save, api,
    runtime_manifest, admit_unit, worker_bindings, verify_grade_config)


def inventory(run):
    run=Path(run);found=[];names=set();errors=[]
    for folder,role in ((run/'unit','unit'),(run/'metadata/ordinary','grade')):
        try:
            need(all(not p.is_symlink()for p in(folder,*folder.parents)),'Unlinked recovery folder')
            path=folder/'resource_ownership.json'
            if not path.exists():
                evidence = ((folder/'resource_ownership.next').exists() or
                    any(folder.glob('create-result-*.json')) or any(folder.glob('inspect-*.json')) or
                    any(folder.glob('precreate-*.json')))
                need(not evidence, 'Missing ownership journal with attempted-resource evidence is unresolved')
                continue
            rows=read(path,65536)['owned'];need(type(rows)is list and len(rows)<=(3 if role=='unit'else 1),'Bounded journal')
            suffix=None
            for index,row in enumerate(rows):
                need(type(row)is dict and row.get('attempted_before_dispatch')is True and
                     type(row.get('name'))is str and type(row.get('canonical_create_argv'))is list,'Canonical owned request')
                kind,name=row['kind'],row['name'];need(name not in names,'Unique owned resource')
                if role=='unit':
                    prefix,wanted=(('volume','volume'),('holder','container'),('worker','container'))[index]
                    match=re.fullmatch('dmfc-prog-'+prefix+'-([a-f0-9]{32})',name)
                    need(kind==wanted and match is not None,'Ordered unit resource')
                    if suffix is None:suffix=match[1]
                    need(match[1]==suffix,'One unit suffix')
                else:need(kind=='container' and re.fullmatch('summary-score-[a-f0-9]{12}',name),'Exact grade resource')
                names.add(name);found.append((folder,row))
        except BaseException as error:errors.append({'folder':str(folder.relative_to(run)),'error':repr(error)[:1000]})
    need(len(found)<=4,'One producer/holder/volume and one grade')
    return list(reversed(found)),errors


def contract(run,folder,item):
    run,folder=Path(run),Path(folder);lib=api();kind,name=item['kind'],item['name'];identity=lib['identity']
    manifest=runtime_manifest(run)
    if folder==run/'metadata/ordinary':
        need(kind=='container' and re.fullmatch('summary-score-[a-f0-9]{12}',name),'Exact grade name')
        verify_grade_config(run);profile=lib['summary_profile'];mounts=worker_bindings(run)
        captured=identity.capture_request(lib['SummaryEngine'],'create_summary',(name,mounts))
        expected={'module':profile,'mounts':mounts}
    else:
        need(folder==run/'unit','Exact producer folder')
        unit=manifest['unit'];admit_unit(unit,manifest['program_sha256'],run)
        profile=lib['runtime'](unit);suffix=name.rsplit('-',1)[-1];need(re.fullmatch('[a-f0-9]{32}',suffix),'Unit suffix')
        volume='dmfc-prog-volume-'+suffix
        if kind=='volume':
            need(name==volume,'Exact tmpfs volume')
            captured=identity.capture_request(lib['ProfileEngine'],'volume',(name,),profile)
            expected={'module':lib['contract_profile']}
        else:
            need(kind=='container' and name in('dmfc-prog-holder-'+suffix,'dmfc-prog-worker-'+suffix),'Exact unit container')
            if name.startswith('dmfc-prog-holder-'):
                role='holder';mounts={'/trusted/holder.py':{'type':'bind','source':str(HERE/'holder_profile.py'),'rw':False},
                                     '/capture':{'type':'volume','source':volume,'rw':False}}
            else:
                role='candidate';mounts={'/program/program.py':{'type':'bind','source':str(run/'program.py'),'rw':False},
                                        '/output':{'type':'volume','source':volume,'rw':True}}
                mounts.update({a['mount_destination']:{'type':'bind','source':str(repo(a['path'])),'rw':False}for a in unit['public_inputs']})
            captured=identity.capture_request(lib['ProfileEngine'],'create',(name,role,mounts),profile)
            expected={'module':lib['contract_profile'],'role':role,'profile':profile,'mounts':mounts}
    need(captured[:2]==(kind,name),'Exact constructor identity')
    return {**expected,'kind':kind,'name':name,'argv':captured[2]}


def normalized_oom(info):
    need(type(info) is dict and type(info.get('HostConfig')) is dict and 'OomKillDisable' in info['HostConfig'], 'Explicit OOM field')
    need(info['HostConfig']['OomKillDisable'] is None or info['HostConfig']['OomKillDisable'] is False, 'Only strict null/false equivalence')
    result = copy.deepcopy(info); result['HostConfig']['OomKillDisable'] = False
    for parent,key in ((result['HostConfig'],'Mounts'),(result,'Mounts')):
        rows=parent.get(key,[]);dest='Target' if parent is result['HostConfig'] else 'Destination'
        need(type(rows) is list and all(type(x) is dict and type(x.get(dest)) is str for x in rows) and len({x[dest] for x in rows})==len(rows),'Unique complete mount records')
        parent[key]=sorted(rows,key=lambda x:x[dest])
    return result

def inspections(folder, kind, name):
    paths = list(folder.glob('inspect-*-' + name + '.json'))
    need(len(paths) <= 8, 'Bounded saved inspections')
    captured = []; ids = set()
    for path in paths:
        reply = read(path, 200000)
        if reply['returncode'] != 0:
            continue
        values = json.loads(reply['stdout'])
        need(type(values) is list and len(values) == 1 and type(values[0]) is dict, 'One saved resource')
        value = values[0]
        need(value.get('Name') == (name if kind == 'volume' else '/' + name), 'Exact saved resource name')
        if kind == 'container':
            need(type(value.get('Id')) is str and re.fullmatch('[a-f0-9]{64}', value['Id']), 'Saved immutable container ID')
            ids.add(value['Id'])
        captured.append(value)
    need(len(ids) <= 1, 'No conflicting saved identities')
    return captured, (name, *sorted(ids))

def recover(run, folder, item, engine, budget):
    """Caller stops every owned group first, then continues best-effort per item."""
    run, folder = Path(run), Path(folder)
    lib = api(); expected = contract(run, folder, item); kind, name = item['kind'], item['name']
    need(item['attempted_before_dispatch'] is True and item['canonical_create_argv'] == expected['argv'],
         'Exact journal/constructor agreement before any removal')
    prior = read(folder / ('precreate-' + name + '.json'), 200000)
    absence = lib['absence']
    need(prior['kind'] == kind and prior['name'] == name and
         absence(prior['returncode'], prior['stdout'], prior['stderr'], kind, name), 'Durable exact precreate absence')
    captured, required = inspections(folder, kind, name)
    if kind == 'container':
        created = read(folder / ('create-result-' + name + '.json'), 16384)
        need(created.get('kind') == kind and created.get('name') == name and created.get('returncode') == 0
             and type(created.get('created_id')) is str and re.fullmatch('[a-f0-9]{64}', created['created_id'])
             and created.get('stdout','').strip() == created['created_id'], 'Durable successful create identity')
        need(all(x.get('Id') == created['created_id'] for x in captured), 'Create and saved inspect identities agree')
        required = (name, created['created_id'])
    nonce = uuid.uuid4().hex; files = []; calls = 0
    def call(argv):
        nonlocal calls
        calls += 1; need(calls <= 4, 'Bounded inspect/remove/dual-absence sequence')
        reply = engine.run(argv, timeout=3, cap=100000)
        record = {'argv': argv, 'returncode': reply.returncode, 'stdout': reply.stdout.decode(errors='replace'),
                  'stderr': reply.stderr.decode(errors='replace')}
        path = folder / ('ordinary-recovery-' + nonce + '-' + str(calls) + '.json')
        save(path, record, budget); files.append(str(path.relative_to(run)))
        return record
    def inspect(target):
        return ['volume', 'inspect', target] if kind == 'volume' else ['inspect', '--type', 'container', target]
    row = {'kind': kind, 'name': name, 'absence_verified': False, 'required_absence_targets': list(required), 'evidence': files}
    first = call(inspect(name))
    if absence(first['returncode'], first['stdout'], first['stderr'], kind, name):
        need(bool(captured), 'Attempted create requires durable successful saved identity before absence')
        if kind == 'volume':
            lib['identity'].verify_live(captured[0], expected, captured)
        observations = {name: True}
        for target in required[1:]:
            result = call(inspect(target)); observations[target] = absence(result['returncode'], result['stdout'], result['stderr'], kind, target)
        return {**row, 'already_absent_no_removal': True, 'absence_observations': observations, 'absence_verified': all(observations.values())}
    need(first['returncode'] == 0, 'Live inspection or exact recognized absence')
    values = json.loads(first['stdout']); need(type(values) is list and len(values) == 1 and type(values[0]) is dict, 'One current resource')
    if kind == 'container':
        need(values[0].get('Id') == created['created_id'], 'Create and live immutable IDs agree before removal')
        identity = lib['identity'].verify_live(normalized_oom(values[0]), expected, [normalized_oom(x) for x in captured])
    else:
        identity = lib['identity'].verify_live(values[0], expected, captured)
    call(['volume', 'rm', identity] if kind == 'volume' else ['rm', '--force', identity])
    observations = {}
    for target in dict.fromkeys((identity, name)):
        result = call(inspect(target)); observations[target] = absence(result['returncode'], result['stdout'], result['stderr'], kind, target)
    return {**row, 'required_absence_targets': list(observations), 'absence_observations': observations,
            'absence_verified': all(observations.values()), 'verified_identity': identity, 'configuration_verified_before_removal': True,
            'removed_by_immutable_container_id': kind == 'container',
            'volume_identity_limit': 'Exact name/tmpfs/CreatedAt/Mountpoint; no immutable Docker volume ID' if kind == 'volume' else None}
