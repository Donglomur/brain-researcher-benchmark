"""Finite dependency-image file audit; consumes a future owner export only."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile

DENIED = re.compile(r'^(studyInformation_publication\.xlsx|candidate_[AB]\.xlsx|variant_[123]\.xlsx|(?:ENGINEERING_)?REFERENCE_VALUES\.json|ISSUER_KEY\.bin|HANDOFF\.json|solution\.R|official_source\.R|article\.pdf|PRIVATE_SCORE\.json)$')


def need(ok,code):
    if not ok:raise ValueError(code)


def audit(path, image, setup_sha, build_plan_sha, forbidden_hashes, staged_names, expected_names):
    """No extraction or link resolution; bounded two-pass full regular-file scan."""
    p=Path(path)
    need(p.is_absolute() and not p.is_symlink() and p.stat().st_size<=2147483648,'export_extent')
    archive_hash=hashlib.sha256();last=b'';total=0
    with p.open('rb') as f:
        while True:
            chunk=f.read(1048576)
            if not chunk:break
            total+=len(chunk);archive_hash.update(chunk);last=(last+chunk)[-1024:]
    need(total>=1024 and total%512==0 and last==bytes(1024),'complete_export_tar_tail')
    paths=set();files=[];forbidden=[];badnames=[];regular_bytes=0
    with tarfile.open(p,'r|') as tar:
        for member in tar:
            name=member.name.removeprefix('./');parts=PurePosixPath(name).parts
            need(name and not name.startswith('/') and '..' not in parts and name not in paths,'export_member_name')
            paths.add(name)
            need(len(paths)<=250000,'export_member_count')
            if member.isfile():
                need(0<=member.size<=268435456 and regular_bytes+member.size<=2147483648,'export_file_extent')
                f=tar.extractfile(member);h=hashlib.sha256();seen=0
                while True:
                    chunk=f.read(1048576)
                    if not chunk:break
                    seen+=len(chunk);h.update(chunk)
                need(seen==member.size,'export_member_complete');regular_bytes+=seen
                sha=h.hexdigest();files.append({'path':name,'bytes':seen,'sha256':sha})
                if sha in forbidden_hashes:forbidden.append({'path':name,'sha256':sha})
                if DENIED.fullmatch(PurePosixPath(name).name):badnames.append(name)
            else:
                need(member.isdir() or member.issym() or member.islnk(),'export_supported_member_kind')
                # Links are inventoried but never followed; inode aliases cannot
                # hide a regular target because every tar member is scanned.
    canonical=json.dumps(files,sort_keys=True,separators=(',',':')).encode()
    return {'schema':'nider_dependency_image_content_audit_v1','image':image,'setup_lock_sha256':setup_sha,
            'build_plan_sha256':build_plan_sha,'export_archive':{'path':str(p),'bytes':total,'sha256':archive_hash.hexdigest()},
            'regular_file_count':len(files),'regular_file_bytes':regular_bytes,
            'filesystem_manifest_sha256':hashlib.sha256(canonical).hexdigest(),
            'forbidden_asset_digest_matches':forbidden,'forbidden_path_matches':badnames,
            'unexpected_build_inputs':sorted(set(staged_names) ^ set(expected_names)),'complete_export':True,
            'scope':'all_exported_regular_files_plus_build_input_closure_not_universal_backdoor_proof',
            'file_manifest':files,'managed_archive_reads_upper_bound':2*total}
