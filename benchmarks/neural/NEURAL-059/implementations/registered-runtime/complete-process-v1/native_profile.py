"""Selected N059 native capability checks; admission never means qualification.

The outer owner must bind the original Docker inspect to the container it created.
This module checks that captured object and current Linux worker facts. It cannot
independently attest an image digest from inside that image. No native package is
imported here; the inherited NativeRuntime.load authenticates complete package
manifests before importing the original numerical dependencies.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import sys


def need(ok, message):
    if not ok:
        raise ValueError(message)


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('utf-8')


def digest(value):
    """Inherited references._digest: compact JSON without a terminal newline."""
    return hashlib.sha256(compact(value)).hexdigest()


def pin(value):
    """Inherited contracts.pin: JSON has one terminal newline."""
    body = value if type(value) is bytes else compact(value) + b'\n'
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def _hex(value):
    return type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _identity(value):
    need(type(value) in (str, dict) and bool(value), 'nonempty selected source identity')
    compact(value)


def _absolute(value):
    need(type(value) is str and value.startswith('/') and '\x00' not in value,
         'absolute ordinary native path')
    p = PurePosixPath(value)
    need(str(p) == value and '..' not in p.parts, 'canonical native path')
    return Path(value)


def _ordinary_ancestry(path, *, directory):
    for part in reversed([path, *path.parents]):
        st = part.lstat()
        need(not stat.S_ISLNK(st.st_mode), 'native path has no symbolic ancestry')
        if part != path or directory:
            need(stat.S_ISDIR(st.st_mode), 'native directory ancestry')
        else:
            need(stat.S_ISREG(st.st_mode), 'ordinary native package file')


def _read_kernel(path, cap):
    """Bounded future kernel fact read; never invoked during source construction."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        body = os.read(fd, cap + 1)
        need(len(body) <= cap, 'kernel capability observation exceeds selected fixed cap')
        return body
    finally:
        os.close(fd)


def validate_profile(profile):
    need(type(profile) is dict and set(profile) == {
        'schema', 'image_id', 'python_version', 'packages', 'hgb_signature',
        'optimizer_signature', 'state_limit_bytes'}, 'exact prospective native profile schema')
    need(profile['schema'] == 'n059_native_profile_v1', 'selected native profile version')
    image = profile['image_id']
    need(type(image) is str and image.startswith('sha256:') and _hex(image[7:]),
         'explicit immutable native image ID')
    need(type(profile['python_version']) is str and
         re.fullmatch(r'\d+\.\d+\.\d+', profile['python_version']) is not None,
         'explicit complete Python version')
    need(all(type(profile[k]) is str and profile[k] for k in
             ('hgb_signature', 'optimizer_signature')), 'explicit original API signatures')
    need(type(profile['state_limit_bytes']) is int and profile['state_limit_bytes'] > 0,
         'explicit inherited native-state streaming byte ceiling')
    packages = profile['packages']
    need(type(packages) is dict and set(packages) == {'numpy', 'scipy', 'scikit-learn'},
         'complete inherited package profile')
    roots, total, count = [], 0, 0
    for name, package in packages.items():
        need(type(package) is dict and set(package) == {'version', 'root', 'files'},
             'exact package version/root/manifest')
        need(type(package['version']) is str and package['version'], 'explicit package version')
        root = _absolute(package['root']); roots.append(str(root))
        files = package['files']
        need(type(files) is dict and bool(files), 'nonempty complete package manifest')
        for relative, descriptor in files.items():
            need(type(relative) is str and relative and '\x00' not in relative,
                 'ordinary native manifest member')
            p = PurePosixPath(relative)
            need(not p.is_absolute() and str(p) == relative and '..' not in p.parts
                 and '__pycache__' not in p.parts and p.suffix != '.pyc',
                 'manifest member matches inherited non-bytecode census')
            need(type(descriptor) is dict and set(descriptor) == {'bytes', 'sha256'}
                 and type(descriptor['bytes']) is int and descriptor['bytes'] >= 0
                 and _hex(descriptor['sha256']), 'exact package body descriptor')
            total += descriptor['bytes']; count += 1
    need(len(set(roots)) == 3, 'distinct package roots')
    need(packages['numpy']['version'] == '2.2.6' and packages['scipy']['version'] == '1.15.3',
         'unchanged inherited NumPy/SciPy versions')
    return {'profile_sha256': digest(profile), 'package_file_count': count,
            'declared_package_bytes': total}


def validate_capability(profile, authorization):
    declared = validate_profile(profile)
    need(type(authorization) is dict and set(authorization) == {
        'schema', 'profile_sha256', 'selection_identity', 'container_inspect',
        'container_inspect_pin', 'expected_cgroup', 'worker_io'},
        'exact owner native capability authorization')
    need(authorization['schema'] == 'n059_native_capability_v1', 'native capability version')
    need(authorization['profile_sha256'] == declared['profile_sha256'],
         'selected exact profile digest')
    _identity(authorization['selection_identity'])
    limits = authorization['worker_io']
    need(type(limits) is dict and set(limits) == {'journal_bytes', 'artifact_bytes'}
         and all(type(v) is int and v > 0 for v in limits.values())
         and limits['journal_bytes'] <= limits['artifact_bytes'],
         'explicit finite native worker journal/artifact allowances')
    inspected = authorization['container_inspect']
    need(type(inspected) is dict and authorization['container_inspect_pin'] == pin(inspected),
         'captured original inspect body identity')
    cid = inspected.get('Id')
    need(_hex(cid) and inspected.get('Image') == profile['image_id'],
         'owner-captured exact container and immutable image')
    config, host, state = (inspected.get(k) for k in ('Config', 'HostConfig', 'State'))
    need(all(type(x) is dict for x in (config, host, state)), 'complete captured Docker capabilities')
    need(config.get('User') == '65534:65534' and config.get('WorkingDir') == '/work',
         'fixed nonroot worker user and working directory')
    need(host.get('ReadonlyRootfs') is True and host.get('NetworkMode') == 'none'
         and host.get('Privileged') is False and host.get('PidMode') in ('', 'private')
         and host.get('CgroupnsMode') == 'host', 'captured root/network/PID/cgroup boundaries')
    need(host.get('CapAdd') in (None, []) and
         {str(x).lower() for x in host.get('CapDrop', [])} == {'all'}, 'captured zero added capabilities')
    security = host.get('SecurityOpt')
    need(type(security) is list and any(x in ('no-new-privileges', 'no-new-privileges=true')
         for x in security) and not any('unconfined' in str(x) for x in security),
         'captured no-new-privileges and active seccomp policy')
    need(state.get('Running') is True and state.get('Paused') is False
         and type(state.get('Pid')) is int and state['Pid'] > 0, 'owner observed live native process')
    need(platform.system() == 'Linux' and os.getuid() == os.geteuid() == 65534
         and os.getgid() == os.getegid() == 65534, 'actual Linux nonroot worker identity')
    need(Path.cwd() == Path('/work') and sys.dont_write_bytecode,
         'actual worker directory and disabled bytecode writes')
    need(os.uname().nodename == config.get('Hostname') == cid[:12],
         'actual default container hostname joins captured container')
    status_body = _read_kernel('/proc/self/status', 65536)
    status = {}
    for line in status_body.decode('ascii').splitlines():
        if ':' in line:
            key, value = line.split(':', 1); status[key] = value.strip()
    need(status.get('NoNewPrivs') == '1' and status.get('Seccomp') == '2',
         'actual no-new-privileges and seccomp filter')
    need(all(int(status.get(k, '-1'), 16) == 0 for k in
             ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb')), 'actual zero Linux capability sets')
    need(status.get('Uid', '').split() == ['65534'] * 4
         and status.get('Gid', '').split() == ['65534'] * 4, 'actual all real/effective/saved/filesystem IDs')
    cgroup_body = _read_kernel('/proc/self/cgroup', 65536)
    cgroup = cgroup_body.decode('ascii').strip()
    expected = authorization['expected_cgroup']
    need(type(expected) is str and expected.startswith('0::/') and '\n' not in expected
         and expected != '0::/' and '..' not in PurePosixPath(expected[3:]).parts
         and cgroup == expected, 'actual exact owner-observed unified cgroup membership')
    parent = host.get('CgroupParent')
    need(type(parent) is str and parent.startswith('/') and
         str(PurePosixPath(parent)) == parent and '..' not in PurePosixPath(parent).parts
         and expected[3:].startswith(parent.rstrip('/') + '/')
         and expected[3:].endswith('/' + cid),
         'captured cgroupfs parent/container ID joins actual worker membership')
    need(bool(os.statvfs('/').f_flag & os.ST_RDONLY), 'actual root filesystem read-only')
    need(bool(os.statvfs('/sys/fs/cgroup').f_flag & os.ST_RDONLY), 'actual cgroup filesystem read-only')
    network_body = _read_kernel('/proc/net/dev', 65536)
    interfaces = [line.split(':', 1)[0].strip() for line in network_body.decode('ascii').splitlines()[2:]
                  if ':' in line]
    need(set(interfaces) <= {'lo'}, 'actual network namespace has no external interface')
    for package in profile['packages'].values():
        root = Path(package['root']); _ordinary_ancestry(root, directory=True)
        need(bool(os.statvfs(root).f_flag & os.ST_RDONLY), 'actual native package filesystem read-only')
        for relative, descriptor in package['files'].items():
            path = root / relative; _ordinary_ancestry(path, directory=False)
            need(path.stat().st_size == descriptor['bytes'], 'actual selected package file extent')
    return {'schema': 'n059_observed_native_capability_v1', 'qualification': 'source_only_unqualified',
            'profile': declared, 'selection_identity': authorization['selection_identity'],
            'container_id': cid, 'image_id': profile['image_id'], 'cgroup': cgroup,
            'owner_inspect_pin': authorization['container_inspect_pin'],
            'kernel_observations': {'status': pin(status_body), 'cgroup': pin(cgroup_body),
                                    'network_interfaces': pin(network_body)},
            'image_provenance': 'outer-owner inspect binding; not independently attested inside image',
            'native_imports_performed': False}


def runtime_factory(shape, *, profile, authorization):
    """Concrete production constructor; caller can freeze profile/auth in a closure."""
    from .scientific import native_references
    return native_references.admit_runtime(profile, shape=shape, authorization=authorization)
