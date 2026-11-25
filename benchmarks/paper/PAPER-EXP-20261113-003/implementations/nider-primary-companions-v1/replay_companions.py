"""Future owner-only original companion production; requires separately authorized runtime execution."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_loader('_companion_contract', loader=None)
contract = importlib.util.module_from_spec(spec)
contract.__file__ = str(HERE/'companion_contract.py')
exec(compile((HERE/'companion_contract.py').read_bytes(),contract.__file__,'exec'),contract.__dict__)


def copy_artifacts(source, destination, inventory):
    # Publish only the authenticated closure and bind the bytes actually copied.
    for name, expected in inventory.items():
        path = source/name
        contract.need(path.is_file() and not path.is_symlink(), 'symlink_artifact_forbidden')
        target = destination/name
        target.parent.mkdir(parents=True,exist_ok=True)
        digest = contract.hashlib.sha256()
        size = 0
        with path.open('rb') as src, target.open('xb') as dst:
            while block := src.read(min(1024*1024, expected['bytes'] - size + 1)):
                contract.need(size + len(block) <= expected['bytes'], 'artifact_changed_during_copy:' + name)
                dst.write(block)
                digest.update(block)
                size += len(block)
        contract.need(size == expected['bytes'] and digest.hexdigest() == expected['sha256'],
                      'artifact_changed_during_copy:' + name)


def run(args):
    base = contract.load_predecessor()
    public = base.public_contract()
    sources = {key:base.read_pinned(path,key) for key,path in {
        'workbook':args.original_workbook,'script':args.official_script,'lock':args.renv_lock}.items()}
    expressions = contract.source_manifest(sources['script'],base)
    executable = shutil.which(args.rscript)
    contract.need(executable is not None,'Rscript_missing_no_install_attempted')
    executable = str(Path(executable).resolve())
    contract.need(args.runtime_identity.strip(),'owner_runtime_identity_required')
    contract.need(type(args.timeout_seconds) is int and args.timeout_seconds > 0,'positive_explicit_deadline')
    contract.need(type(args.artifact_byte_limit) is int and args.artifact_byte_limit > 0,'positive_explicit_artifact_limit')
    output = Path(args.output_directory).resolve()
    contract.need(output.parent.is_dir() and not output.exists(),'new_output_directory_required')
    # A unique owner directory retains partial evidence; MANIFEST.json is written only on success.
    output.mkdir()
    started = time.time()
    record = {'schema':'nider_original_companions_provenance_v1',
        'predecessor_commit':contract.PREDECESSOR_COMMIT,
        'owner_runtime_identity':args.runtime_identity,'owner_runtime_identity_is_external_admission':True,
        'Rscript':{'path':executable,'sha256':contract.digest(Path(executable).read_bytes())},
        'sources':{key:{'sha256':contract.digest(raw),'bytes':len(raw)} for key,raw in (sources|public).items()},
        'expressions':expressions,'arm':args.arm,
        'bounds':{'timeout_seconds':args.timeout_seconds,'artifact_byte_limit':args.artifact_byte_limit,
                  'bounds_are_not_native_execution_authorization':True},
        'artifact_bundle_complete':False,'scientific_agreement_assessed':False,
        'complete_primary_success':False}
    with tempfile.TemporaryDirectory(prefix='.private-stage-',dir=output) as temporary:
        root = Path(temporary)
        (root/'data/studyInformation').mkdir(parents=True)
        (root/'results/figures').mkdir(parents=True)
        (root/'out/results/figures').mkdir(parents=True)
        (root/'.here').write_bytes(b'')
        staged = {'workbook':'data/studyInformation/studyInformation_publication.xlsx',
                  'script':'official.R','lock':'original-renv.lock','schema':'FIELD_SCHEMA.json'}
        for key,name in staged.items():
            (root/name).write_bytes((sources|public)[key])
        implementation = {'frozen_collector.R':contract.PREDECESSOR/'collector.R',
                          'native_artifacts.R':HERE/'native_artifacts.R',
                          'replay_companions.R':HERE/'replay_companions.R'}
        for name,path in implementation.items():
            (root/name).write_bytes(path.read_bytes())
        hashes = {name:contract.digest((root/name).read_bytes()) for name in implementation}
        job = {'arm':args.arm,'pins':{key:base.PINS[key][0] for key in staged},
               'implementation_hashes':hashes,'expressions':expressions}
        (root/'job.json').write_bytes(base.json_bytes(job))
        record['implementation'] = hashes | {name:contract.digest((HERE/name).read_bytes()) for name in
                                             ('replay_companions.py','companion_contract.py')}
        command = [executable,'--vanilla',str(root/'replay_companions.R')]
        record['command'] = command
        try:
            completed = subprocess.run(command,cwd=root,env=base.clean_environment(),
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=args.timeout_seconds)
            record.update(returncode=completed.returncode,stdout=base.retained_bytes(completed.stdout),
                          stderr=base.retained_bytes(completed.stderr))
            if completed.returncode:
                record['status'] = 'native_process_failed'
                raise RuntimeError('native process failed')
            inventory,full120,runtime = contract.check_bundle(root/'out',args.arm,args.artifact_byte_limit,base)
            record.update(status='original_companion_artifacts_produced',runtime=runtime)
            manifest = {'schema':'nider_selected_original_companion_bundle_v1',
                'task':'PAPER-EXP-20261113-003','arm':args.arm,'workbook_sha256':base.PINS['workbook'][0],
                'selected_result':'three habitual-reappraisal/rating/amygdala associations; Table1 and ED1-3',
                'artifacts':inventory,'artifact_bytes':sum(x['bytes'] for x in inventory.values()),
                'full120_unchanged_interface_validated':True,
                'companion_scientific_comparison_performed':False,
                'canonical_admission_changed':False,'complete_primary_success':False,
                'native_objects_are_owner_only':True,
                'excludes':['ability-questionnaire participant CSV branches','ED4 whole-brain jackknife',
                            'optional benchmark-added leave-study/cohort robustness'],
                'source_expression_count':57}
            copy_artifacts(root/'out',output,inventory)
            record['artifact_bundle_complete'] = True
            record['elapsed_wall_seconds'] = time.time()-started
            provenance = base.json_bytes(record)
            base.publish_new(output/'PROVENANCE.json',provenance)
            manifest['provenance'] = {'path':'PROVENANCE.json','sha256':contract.digest(provenance),'bytes':len(provenance)}
            base.publish_new(output/'MANIFEST.json',base.json_bytes(manifest))
            return manifest
        except Exception as error:
            if isinstance(error,subprocess.TimeoutExpired):
                status = 'native_process_timeout'
            elif isinstance(error,OSError):
                status = 'launch_or_artifact_IO_failed'
            else:
                status = record.get('status','artifact_validation_failed')
            if status == 'original_companion_artifacts_produced':
                status = 'artifact_publication_failed'
            record.update(status=status,error=str(error),artifact_bundle_complete=False,
                          elapsed_wall_seconds=time.time()-started)
            if isinstance(error,subprocess.TimeoutExpired):
                record.update(stdout=base.retained_bytes(error.stdout),stderr=base.retained_bytes(error.stderr))
            # Retain partial source-produced outputs privately, up to the declared artifact budget.
            # Complete lengths/hashes remain recorded when a large file's retained prefix is bounded.
            retained = {}
            already_copied = {name:output/name for name in contract.REQUIRED_ARTIFACTS
                              if (output/name).is_file() and not (output/name).is_symlink()}
            copied_bytes = sum(path.stat().st_size for path in already_copied.values())
            remaining = max(0,args.artifact_byte_limit-copied_bytes)
            failure_root = output/'REJECTED_NATIVE'
            candidates = {str(p.relative_to(root/'out')):p for p in (root/'out').rglob('*')
                          if p.is_file() or p.is_symlink()}
            # A failed original forest call can leave a partial PNG before the phase copy.
            for name in contract.FIGURES.values():
                if name not in candidates and (root/name).is_file():
                    candidates[name] = root/name
            for name,path in sorted(candidates.items()):
                if path.is_file() and not path.is_symlink():
                    info = contract.artifact_identity(path)
                    if name in already_copied:
                        copied_info = contract.artifact_identity(already_copied[name])
                        retained[name] = info | {'retained_path':name,'retained_bytes':copied_info['bytes'],
                            'retained_sha256':copied_info['sha256'],
                            'truncated':copied_info['bytes'] < info['bytes'],
                            'already_published_before_failure':True}
                        continue
                    keep = min(info['bytes'],remaining)
                    if keep:
                        target = failure_root/name
                        target.parent.mkdir(parents=True,exist_ok=True)
                        with path.open('rb') as src, target.open('xb') as dst:
                            left = keep
                            while left:
                                block = src.read(min(left,1024*1024))
                                dst.write(block);left -= len(block)
                    retained[name] = info | {'retained_path':'REJECTED_NATIVE/'+name if keep else None,
                        'retained_bytes':keep,'truncated':keep < info['bytes']}
                    remaining -= keep
            record['rejected_native_files'] = retained
            record['retained_native_payload_bytes'] = copied_bytes + sum(
                item['retained_bytes'] for item in retained.values() if not item.get('already_published_before_failure'))
            # Never overwrite an earlier successful-looking provenance on a publication failure.
            failure_name = 'FAILURE.json' if (output/'PROVENANCE.json').exists() else 'PROVENANCE.json'
            base.publish_new(output/failure_name,base.json_bytes(record))
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-workbook',required=True)
    parser.add_argument('--official-script',required=True)
    parser.add_argument('--renv-lock',required=True)
    parser.add_argument('--rscript',default='Rscript')
    parser.add_argument('--runtime-identity',required=True)
    parser.add_argument('--arm',choices=('A','B'),required=True)
    parser.add_argument('--output-directory',required=True)
    parser.add_argument('--timeout-seconds',type=int,required=True)
    parser.add_argument('--artifact-byte-limit',type=int,required=True)
    run(parser.parse_args())


if __name__=='__main__':
    main()
