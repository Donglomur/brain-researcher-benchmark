"""Task-local paired packet and completed-artifact bindings; no agent executor."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import types

TASK = 'PAPER-FIND-REP-013'
CONDITIONS = ('A', 'B')
CODE_NAMES = {'HumanvsMousePaperAnalysis.Rmd', 'source_semantics.json'}
PROGRAM_CAP = 131072
META_CAP = 65536
ARTIFACT_SOURCE = {'path':'components/purkinje-artifacts/artifact.py',
                   'bytes':13254,'sha256':'ebf846517265e562f6111c725d2a264c0e028a6084a2c76bfce7567f30a63201'}
PROFILE = 'benchmarks/neuroscience/paper-find-rep-013-purkinje-morphology/program-v1'


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def need(value, message):
    if not value:
        raise ValueError(message)


def exact_pin(value):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}, 'exact identity')
    need(type(value['bytes']) is int and value['bytes'] > 0 and type(value['sha256']) is str
         and len(value['sha256']) == 64 and all(c in '0123456789abcdef' for c in value['sha256']), 'strict identity fields')
    return value


def relative(name):
    p = Path(name)
    need(type(name) is str and str(p) == name and not p.is_absolute()
         and all(x not in ('', '.', '..') for x in p.parts), 'exact relative member')
    return p


def source_capture(path, expected):
    """Small task bootstrap; refuse aliases/nonordinary files before reading."""
    expected=exact_pin(expected);need(expected['bytes']<=META_CAP,'bounded task source')
    path=Path(path).absolute()
    need(not any(p.is_symlink() for p in (path,*path.parents)),'ordinary source path')
    before=path.lstat()
    stamp=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==expected['bytes'],'ordinary exact source extent')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        need(stamp(before)==stamp(os.fstat(fd)),'source changed before capture')
        with os.fdopen(fd,'rb',closefd=False) as stream:body=stream.read(expected['bytes']+1)
        need(stamp(before)==stamp(os.fstat(fd))==stamp(path.lstat()) and pin(body)==expected,'source capture identity')
        return body
    finally:os.close(fd)


class Paired:
    def __init__(self, repo, contract_path, expected, provider_root=None):
        """Authenticate operator source/metadata only; empirical/gold bodies stay closed."""
        self.repo = Path(repo).absolute()
        self.provider_root = Path(provider_root).absolute() if provider_root is not None else None
        self.contract_path = Path(contract_path).absolute()
        body = source_capture(self.contract_path, expected)
        self.contract_pin = pin(body)
        self.contract = json.loads(body)
        d = self.contract['artifact_source']
        need(encode(d)==encode(ARTIFACT_SOURCE),'fixed task artifact source before execution')
        source = self.repo / relative(d['path'])
        raw = source_capture(source, {k:d[k] for k in ('bytes','sha256')})
        self.a = types.ModuleType('purkinje_paired_artifact')
        self.a.__file__ = str(source)
        exec(compile(raw, str(source), 'exec'), self.a.__dict__)
        self.schema, self.scorer, self.references, _ = self.a.contracts(self.repo / PROFILE)
        self.common = self._manifest('COMMON.json')
        self.additions = {c: self._manifest(c + '.json') for c in CONDITIONS}
        self._validate_contract()

    def _manifest(self, name):
        expected = self.contract['manifests'][name]
        return self.a.decode(self.a.read(self.contract_path.parent / name, META_CAP, expected))

    def _validate_contract(self):
        c = self.contract
        need(c['schema']=='purkinje-paired-access-contract/v1' and c['task_id'] == TASK and c['source_only'] is True and c['scientific_qualified'] is False, 'source-only task contract')
        need(encode(c['scope'])==encode(dict(trees=10,components=13,branches=21116,author_sections=12603,empirical_files=12,table_numerical_fields=31,summary_errors=58)),'complete fixed scientific scope')
        expected_data = {'raw/' + n + '.swc' for n in self.schema.CELLS} | {'cells.json', 'author_sholl_totals.csv'}
        need(set(self.common['empirical_names']) == expected_data and len(self.common['empirical_names'])==len(expected_data)==12, 'full twelve empirical inputs')
        need(set(self.common['files']) == expected_data | {'paper.html', 'TASK.md', 'SCHEMA.json', 'ATTRIBUTION.md'}, 'exact shared packet')
        need(self.additions['A'] == {'condition': 'A', 'files': {}}, 'A has no code additions')
        need(self.additions['B']['condition'] == 'B' and set(self.additions['B']['files']) == CODE_NAMES, 'exact B-only additions')
        for name, row in {**self.common['files'], **self.additions['B']['files']}.items():
            namespace = 'component/' if name in ('TASK.md','SCHEMA.json','ATTRIBUTION.md') else 'provider/'
            need(row['source']==namespace+name, 'exact portable asset source')
            need(set(row) == {'source', 'bytes', 'sha256'}, 'exact asset descriptor')
            relative(row['source']); exact_pin({k: row[k] for k in ('bytes', 'sha256')})
        # Exact selected article extent; the legacy600000-byte non-SWC cap is not reused.
        need(self.common['files']['paper.html']['bytes'] == 622639, 'exact main-article extent')
        need(c['science']['scorer'] == dict(zip(('bytes', 'sha256'), self.a.PINS['numeric_score.py']))
             and c['science']['schema'] == dict(zip(('bytes', 'sha256'), self.a.PINS['schema.py'])), 'same corrected science')
        need(c['science']['output_schema'] == dict(zip(('bytes', 'sha256'), self.a.PINS['SCHEMA.json']))
             and c['science']['output_schema'] == {k:self.common['files']['SCHEMA.json'][k] for k in ('bytes','sha256')}, 'unchanged output schema')
        refs = {n: {k: r[k] for k in ('bytes', 'sha256')} for n, r in self.references['references'].items()}
        need(c['science']['references'] == pin(encode(refs)) and set(refs) == set(self.schema.REQUIRED), 'same complete reference descriptors')
        need(c['science']['specification'] == {k: self.common['files']['TASK.md'][k] for k in ('bytes', 'sha256')}, 'shared specification binding')

    def inventory(self, condition):
        need(condition in CONDITIONS, 'known condition')
        return {**self.common['files'], **self.additions[condition]['files']}

    def packet_identity(self, condition):
        files = {n: {k: r[k] for k in ('bytes', 'sha256')} for n, r in self.inventory(condition).items()}
        return dict(task_id=TASK, condition=condition, contract=self.contract_pin,
                    common=self.contract['manifests']['COMMON.json'], additions=self.contract['manifests'][condition + '.json'],
                    science=self.contract['science'], files=files, file_count=len(files), total_bytes=sum(r['bytes'] for r in files.values()))

    def source_path(self, row):
        name = relative(row['source']); namespace, *parts = name.parts
        need(bool(parts) and namespace in ('component','provider'), 'known asset namespace')
        if namespace == 'component':
            root = self.contract_path.parent
        else:
            need(self.provider_root is not None, 'explicit external provider root required')
            root = self.provider_root
        return self.a.path(root.joinpath(*parts))

    def materialize(self, condition, destination, receipt_path, selected=False):
        need(selected is True, 'separate packet materialization selection required')
        a = self.a; destination = a.path(destination); receipt_path = a.path(receipt_path)
        a.separate(destination, receipt_path)
        need(not destination.exists() and not receipt_path.exists() and destination.parent.is_dir() and receipt_path.parent.is_dir(), 'fresh packet and receipt outputs')
        identity = self.packet_identity(condition)
        # Resolve all declared roots and refuse input/output overlap before creation.
        sources = {n:self.source_path(r) for n,r in self.inventory(condition).items()}
        for source in sources.values():
            a.separate(destination, source); a.separate(receipt_path, source)
        destination.mkdir(mode=0o700)
        dirs = {destination}
        for name, row in sorted(self.inventory(condition).items()):
            target = destination / relative(name)
            if target.parent != destination:
                target.parent.mkdir(mode=0o700, exist_ok=True); dirs.add(target.parent)
            expected = {k: row[k] for k in ('bytes', 'sha256')}
            # One exact original-body capture feeds the copy. No generic larger cap.
            body = a.read(sources[name], row['bytes'], expected)
            a.write_new(target, body, 0o400)
        for d in sorted(dirs, key=lambda x: len(x.parts), reverse=True):
            d.chmod(0o500)
        value = dict(schema='purkinje-paired-packet/v1', packet=identity, packet_hash=pin(encode(identity)),
                     authoring_runtime_qualified=False, participant_executed=False)
        body = a.encoded(value, META_CAP); a.write_new(receipt_path, body, 0o400)
        return pin(body)

    def packet_receipt(self, path, expected, condition):
        value = self.a.decode(self.a.read(path, META_CAP, exact_pin(expected), 0o400))
        identity = self.packet_identity(condition)
        need(value == dict(schema='purkinje-paired-packet/v1', packet=identity, packet_hash=pin(encode(identity)),
                           authoring_runtime_qualified=False, participant_executed=False), 'exact condition packet receipt')
        return value

    def verify_packet(self, directory, condition):
        """Future pre-authoring byte/inventory check; does not observe effective mounts."""
        a = self.a; root = a.path(directory); expected = self.inventory(condition)
        need(root.is_dir() and stat.S_IMODE(root.stat().st_mode) == 0o500, 'sealed packet directory')
        found = set(); directories = {root: a.identity(root.lstat())}; stack = [root]
        allowed_dirs = {'raw'}
        while stack:
            d = stack.pop()
            with os.scandir(d) as entries:
                for entry in entries:
                    p = Path(entry.path); name = str(p.relative_to(root))
                    need(len(found) < len(expected) + len(allowed_dirs), 'bounded packet namespace')
                    if entry.is_dir(follow_symlinks=False):
                        need(name in allowed_dirs and stat.S_IMODE(p.lstat().st_mode) == 0o500, 'exact packet directories')
                        directories[p] = a.identity(p.lstat()); stack.append(p)
                    else:
                        need(name in expected and name not in found, 'exact packet file namespace')
                        found.add(name)
        need(found == set(expected), 'complete packet namespace')
        for name in sorted(expected):
            row = expected[name]
            a.read(root / name, row['bytes'], {k: row[k] for k in ('bytes', 'sha256')}, 0o400)
        need(all(a.identity(p.lstat()) == before for p, before in directories.items()), 'packet directory changed')
        return pin(encode(self.packet_identity(condition)))

    def validate_request(self, value, condition=None):
        fields = {'schema', 'task_id', 'pair_id', 'condition', 'context_id', 'execution_selected', 'packet', 'packet_receipt', 'program', 'resources', 'science', 'contract'}
        need(type(value) is dict and set(value) == fields, 'exact run-request fields')
        need(value['schema'] == 'purkinje-paired-run/v1' and value['task_id'] == TASK, 'paired task request')
        arm = value['condition']; need(arm in CONDITIONS and (condition is None or arm == condition), 'request condition')
        for key in ('pair_id', 'context_id'):
            need(type(value[key]) is str and len(value[key]) == 64 and all(c in '0123456789abcdef' for c in value[key]), 'opaque pair/context identity')
        need(value['execution_selected'] is True, 'future run selection required')
        exact_pin(value['contract']);exact_pin(value['packet']);exact_pin(value['packet_receipt'])
        need(type(value['science']) is dict and set(value['science'])==set(self.contract['science']), 'exact science descriptor set')
        for descriptor in value['science'].values():exact_pin(descriptor)
        need(value['contract'] == self.contract_pin and value['science'] == self.contract['science']
             and value['packet'] == pin(encode(self.packet_identity(arm))), 'exact packet/spec/scorer/reference/request bindings')
        exact_pin(value['program']); need(value['program']['bytes'] <= PROGRAM_CAP, 'bounded committed program')
        r = value['resources']
        need(type(r) is dict and set(r) == {'agent_model', 'harness_source', 'toolset_source', 'authoring_seconds', 'authoring_tokens', 'tool_calls', 'program_seconds', 'program_cpu_millicores', 'program_memory_bytes'}, 'exact common resource declaration')
        need(type(r['agent_model']) is str and bool(r['agent_model']), 'chosen agent identity required')
        exact_pin(r['harness_source']); exact_pin(r['toolset_source'])
        need(all(type(r[k]) is int and 0 < r[k] <= 10**12 for k in ('authoring_seconds','authoring_tokens','tool_calls','program_seconds','program_cpu_millicores','program_memory_bytes')), 'strict positive resource declarations')
        need((r['program_seconds'], r['program_cpu_millicores'], r['program_memory_bytes']) == (60,1750,3*1024**3), 'preserved prospective program limits')
        return value

    def freeze(self, request, request_pin, packet_receipt, packet_receipt_pin, program, submission, attempt, producer_stopped=False):
        a = self.a
        need(pin(encode(request)) == exact_pin(request_pin), 'exact canonical request bytes')
        r = self.validate_request(request)
        receipt = self.packet_receipt(packet_receipt, packet_receipt_pin, r['condition'])
        need(receipt['packet_hash'] == r['packet'] and packet_receipt_pin == r['packet_receipt'], 'request packet receipt')
        need(producer_stopped is True, 'stopped producer attestation')
        # Program commitment is authenticated before any output capture.
        program_body = a.read(program, PROGRAM_CAP, r['program']); program_body.decode('utf-8')
        attempt = a.path(attempt); need(not attempt.exists() and attempt.parent.is_dir(), 'fresh condition attempt')
        a.separate(attempt, a.path(submission)); a.separate(attempt, a.path(program))
        files = a.candidate(submission, self.schema, self.scorer)
        bound = dict(schema='purkinje-paired-submission/v1', task_id=TASK, condition=r['condition'], pair_id=r['pair_id'], context_id=r['context_id'],
                     request=request_pin, packet_receipt=packet_receipt_pin, packet=r['packet'], program=r['program'], science=r['science'],
                     producer_stopped_attested=True, files={n: pin(b) for n,b in files.items()}, total_bytes=sum(map(len,files.values())))
        body = a.encoded(bound, META_CAP)
        attempt.mkdir(mode=0o700)
        for n,b in files.items(): a.write_new(attempt/n,b,0o400)
        a.write_new(attempt/'PAIR_SUBMISSION.json',body,0o400); attempt.chmod(0o500)
        return pin(body)

    def admit_attempt(self, request, request_pin, attempt, expected):
        a = self.a; r = self.validate_request(request)
        need(pin(encode(request)) == exact_pin(request_pin), 'request identity')
        attempt = a.path(attempt)
        value = a.decode(a.read(attempt/'PAIR_SUBMISSION.json',META_CAP,exact_pin(expected),0o400))
        need(type(value) is dict and set(value) == {'schema','task_id','condition','pair_id','context_id','request','packet_receipt','packet','program','science','producer_stopped_attested','files','total_bytes'}, 'exact paired receipt')
        need(value['schema']=='purkinje-paired-submission/v1' and value['task_id']==TASK
             and all(encode(value[k])==encode(r[k]) for k in ('condition','pair_id','context_id','packet','packet_receipt','program','science'))
             and value['request']==request_pin and value['producer_stopped_attested'] is True, 'condition-bound stopped receipt')
        exact_pin(value['packet_receipt'])
        need(type(value['files']) is dict and set(self.schema.REQUIRED)<=set(value['files'])<=set(self.schema.CAPS), 'complete numerical products')
        need(type(value['total_bytes']) is int and 0<value['total_bytes']<=self.schema.TOTAL_CAP, 'submission extent')
        before=attempt.lstat();need(stat.S_IMODE(before.st_mode)==0o500, 'sealed attempt')
        need({p.name for p in attempt.iterdir()}==set(value['files'])|{'PAIR_SUBMISSION.json'}, 'exact attempt namespace')
        files={}
        for n,expected_file in value['files'].items():
            exact_pin(expected_file);need(expected_file['bytes']<=self.schema.CAPS[n], 'numerical product cap')
            files[n]=a.read(attempt/n,self.schema.CAPS[n],expected_file,0o400)
        need(sum(map(len,files.values()))==value['total_bytes'] and a.identity(before)==a.identity(attempt.lstat()), 'complete stable captured output')
        self.scorer.admit(files)
        return files

    def compare_closed_pair(self, requests, request_pins, attempts, receipt_pins, authority, authority_pin, reference_reader):
        """Trusted future integration seam, not an authoring-isolation implementation.

        reference_reader must be the existing fixed-pin private reader under the
        independently qualified owner. Tests supply invented references only.
        No CLI exposes this operation or launches a participant.
        """
        need(all(set(x)==set(CONDITIONS) for x in (requests,request_pins,attempts,receipt_pins)), 'complete A/B pair')
        for c in CONDITIONS:self.validate_request(requests[c],c)
        x,y=requests['A'],requests['B']
        need(x['pair_id']==y['pair_id'] and x['context_id']!=y['context_id'] and x['resources']==y['resources']
             and x['science']==y['science'] and x['contract']==y['contract'], 'matched pair contexts/resources/science')
        self.a.separate(self.a.path(attempts['A']),self.a.path(attempts['B']))
        required={'schema':'purkinje-paired-authoring-review/v1','approved':True,'pair_id':x['pair_id'],'requests':request_pins,
                  'receipts':receipt_pins,'resources':x['resources'],'harness_source':x['resources']['harness_source'],
                  'independent_fresh_contexts_observed':True,'exact_effective_mounts_observed':True,'network_and_parent_access_denied':True,
                  'equal_budget_enforced':True,'no_cross_arm_history':True,'no_target_feedback_before_both_closed':True,'both_producers_closed':True,
                  'revised_science_and_fixed_reference_qualified':True,'whole_owner_runtime_qualified':True}
        need(pin(encode(authority))==exact_pin(authority_pin) and encode(authority)==encode(required), 'independent paired authoring/runtime/closure authority required')
        # Admit both complete outputs before obtaining any private reference bytes.
        files={c:self.admit_attempt(requests[c],request_pins[c],attempts[c],receipt_pins[c]) for c in CONDITIONS}
        reference=reference_reader()
        need(type(reference) is dict and set(reference)==set(self.schema.REQUIRED), 'complete common private reference')
        for name,row in self.references['references'].items():
            need(pin(reference[name])=={k:row[k] for k in ('bytes','sha256')}, 'fixed common reference identity')
        grades={c:self.scorer.grade(files[c],lambda:reference) for c in CONDITIONS}
        return dict(task_id=TASK,pair_id=x['pair_id'],grades=grades,reference_bundle_reader_calls=1,
                    feedback_operator_private=True,authoring_isolation_implemented_here=False,
                    scientific_qualified=False,submission_ready=False,code_access_effect_established=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',required=True);p.add_argument('--contract',required=True)
    p.add_argument('--provider-root',required=True,help='Operator-provisioned original assets; no download')
    p.add_argument('--contract-bytes',type=int,required=True);p.add_argument('--contract-sha256',required=True)
    p.add_argument('--condition',choices=CONDITIONS,required=True)
    p.add_argument('--destination',required=True);p.add_argument('--receipt',required=True)
    p.add_argument('--materialization-selected',action='store_true')
    a=p.parse_args();paired=Paired(a.repo,a.contract,dict(bytes=a.contract_bytes,sha256=a.contract_sha256),a.provider_root)
    print(json.dumps(paired.materialize(a.condition,a.destination,a.receipt,a.materialization_selected)))


if __name__=='__main__':main()
