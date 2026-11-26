"""Offline two-build ANTLR wheel construction; never import the ANTLR package."""
import argparse
import base64
import csv
import email
import hashlib
import io
import json
import os
import pathlib
import platform
import re
import runpy
import signal
import stat
import subprocess
import sys
import tarfile
import time
import zipfile
import zlib

SOURCE_SHA = 'f224469b4168294902bb1efa80a8bf7855f24c99aef99cbefc1bcd3cce77881b'
LOCK_SHA = 'ab0a8775f808dbafb9864e1a22238aec04500245c177a2e5a97aae05ceb538aa'
TOOLS = {'setuptools': '75.8.0', 'wheel': '0.45.1', 'packaging': '24.2'}
SOURCE_ROOT = 'antlr4-python3-runtime-4.9.3'
WHEEL_NAME = 'antlr4_python3_runtime-4.9.3-py3-none-any.whl'
EPOCH = 315532800
BOOTSTRAP = r'''
import importlib.metadata, json, os, pathlib, runpy, sys
assert sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode
assert sys.flags.hash_randomization == 1
tools, setup, output = map(pathlib.Path, sys.argv[1:])
sys.path.insert(0, str(tools))
import setuptools, wheel, packaging
selected = {'setuptools': ('75.8.0', setuptools), 'wheel': ('0.45.1', wheel), 'packaging': ('24.2', packaging)}
observed = {}
for name, (version, module) in selected.items():
    location = pathlib.Path(module.__file__).resolve()
    assert location.is_relative_to(tools.resolve()), (name, str(location))
    assert importlib.metadata.version(name) == version, name
    observed[name] = {'version': version, 'module': str(location.relative_to(tools))}
assert 'antlr4' not in sys.modules
print('BUILD_TOOL_MODULES=' + json.dumps(observed, sort_keys=True), flush=True)
print('HASH_SEED=uncontrolled_under_isolated_startup', flush=True)
os.chdir(setup.parent)
sys.argv = [str(setup), 'bdist_wheel', '--dist-dir', str(output)]
runpy.run_path(str(setup), run_name='__main__')
assert 'antlr4' not in sys.modules
'''


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bounded(path, limit):
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_size <= limit, 'bounded regular file required: ' + path.name)
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    need(len(raw) <= limit, 'read size changed')
    return raw


def safe_name(name):
    need(name and not name.startswith('/') and '\\' not in name
         and all(part not in ('', '.', '..') for part in name.rstrip('/').split('/')), 'unsafe archive name')
    return pathlib.PurePosixPath(name)


def zip_inventory(raw, expected_root, extract_to=None, output_wheel=False):
    """Validate the outer wheel RECORD; nested vendored metadata remains ordinary data."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        need(len(members) <= 4096 and sum(x.file_size for x in members) <= 16777216, 'wheel expansion bounds')
        names = [x.filename for x in members]
        need(len(names) == len(set(names)), 'duplicate wheel member')
        need([n for n in names if n.count('/') == 1 and n.endswith('.dist-info/METADATA')] == [expected_root + '/METADATA'], 'exact top-level metadata')
        need([n for n in names if n.count('/') == 1 and n.endswith('.dist-info/WHEEL')] == [expected_root + '/WHEEL'], 'exact top-level wheel descriptor')
        record_name = expected_root + '/RECORD'
        need(record_name in names and archive.getinfo(record_name).file_size <= 1048576, 'bounded RECORD required')
        record_raw = archive.read(record_name)
        rows = list(csv.reader(io.StringIO(record_raw.decode('utf-8'))))
        need(all(len(row) == 3 for row in rows), 'RECORD row shape')
        records = {row[0]: row[1:] for row in rows}
        need(len(records) == len(rows), 'duplicate RECORD row')
        files = {member.filename for member in members if not member.is_dir()}
        need(set(records) == files, 'RECORD must cover exactly wheel files')
        metadata_raw = descriptor_raw = None
        native_magic = (b'\x7fELF', b'MZ', b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe')
        for member in members:
            safe_name(member.filename)
            need(not member.flag_bits & 1 and member.compress_type in (0, 8), 'unsupported zip encoding')
            filetype = (member.external_attr >> 16) & 0o170000
            need(filetype in (0, stat.S_IFREG, stat.S_IFDIR), 'zip link/device forbidden')
            need(member.file_size <= 4194304, 'individual zip member bound')
            if member.is_dir():
                continue
            body = archive.read(member)
            digest, size = records[member.filename]
            if member.filename == record_name:
                need(digest == size == '', 'RECORD self row must omit hash/size')
            else:
                expected = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip('=')
                need(digest == expected and size == str(len(body)), 'wheel RECORD hash/size mismatch')
            if output_wheel:
                need(not member.filename.lower().endswith(('.so', '.pyd', '.dll', '.dylib', '.o', '.a'))
                     and not body.startswith(native_magic), 'native output forbidden')
            if member.filename == expected_root + '/METADATA':
                metadata_raw = body
            if member.filename == expected_root + '/WHEEL':
                descriptor_raw = body
            if extract_to is not None:
                need('.data/' not in member.filename, 'tool relocation layout not selected')
                destination = extract_to.joinpath(*safe_name(member.filename).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                need(not destination.exists(), 'tool file overlap')
                with destination.open('xb') as stream:
                    stream.write(body)
                destination.chmod(0o644)
                os.utime(destination, (EPOCH, EPOCH))
        need(metadata_raw is not None and descriptor_raw is not None, 'wheel descriptors absent')
        metadata = email.message_from_bytes(metadata_raw)
        descriptor = email.message_from_bytes(descriptor_raw)
        need(descriptor.get('Root-Is-Purelib', '').lower() == 'true'
             and descriptor.get_all('Tag') == ['py3-none-any'], 'pure py3-none-any wheel required')
        return {'members': len(members), 'file_count': len(files),
                'uncompressed_bytes': sum(x.file_size for x in members),
                'metadata_sha256': sha(metadata_raw), 'wheel_descriptor_sha256': sha(descriptor_raw),
                'record_sha256': sha(record_raw), 'name': metadata.get('Name'),
                'version': metadata.get('Version'), 'requires_dist': metadata.get_all('Requires-Dist', []),
                'tags': descriptor.get_all('Tag'), 'root_is_purelib': True,
                'all_record_hashes_verified': True, 'native_output_checked': output_wheel}


def unpack_source(raw, destination):
    need(len(raw) == 117034 and sha(raw) == SOURCE_SHA, 'exact reviewed source archive required')
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    decoded = decoder.decompress(raw, 8388608)
    need(decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data
         and len(decoded) == 624640, 'exact reviewed decoded source')
    names, regular_bytes, regular_count = set(), 0, 0
    with tarfile.open(fileobj=io.BytesIO(decoded), mode='r:') as archive:
        members = archive.getmembers()
        need(len(members) == 78, 'exact reviewed real-member count')
        for member in members:
            safe_name(member.name)
            name = pathlib.PurePosixPath(member.name)
            need(name.parts[0] == SOURCE_ROOT and str(name) not in names, 'source root/duplicate path')
            names.add(str(name))
            need(member.isdir() or member.isfile(), 'source links/devices forbidden')
            need(member.size <= 262144, 'source member size ceiling')
            target = destination.joinpath(*name.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                regular_count += 1
                regular_bytes += member.size
                need(regular_bytes <= 477312, 'reviewed source size ceiling')
                target.parent.mkdir(parents=True, exist_ok=True)
                body = archive.extractfile(member).read(262145)
                need(len(body) == member.size, 'source member length')
                with target.open('xb') as stream:
                    stream.write(body)
                target.chmod(member.mode & 0o777)
                os.utime(target, (EPOCH, EPOCH))
    need(regular_count == 68 and regular_bytes == 477312, 'reviewed source inventory mismatch')
    setup = destination / SOURCE_ROOT / 'setup.py'
    need(sha(bounded(setup, 527)) == '00ce3bb1670e8e4961d9ef2414dfa6ac467b52465382841b432578f91733ec67', 'reviewed setup.py only')
    return setup


def build_once(label, source, tools_dir, output, work):
    source_dir = work / label
    source_dir.mkdir()
    setup = unpack_source(source, source_dir)
    dist = output / label
    dist.mkdir()
    log = dist / 'build.log'
    command = [sys.executable, '-I', '-S', '-B', '-c', BOOTSTRAP, str(tools_dir), str(setup), str(dist)]
    with log.open('xb') as stream:
        child = subprocess.Popen(command, cwd=setup.parent, stdout=stream, stderr=subprocess.STDOUT,
                                 env={'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(work),
                                      'SOURCE_DATE_EPOCH': str(EPOCH),
                                      'PYTHONDONTWRITEBYTECODE': '1', 'TZ': 'UTC',
                                      'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}, start_new_session=True)
        started = time.monotonic()
        try:
            while child.poll() is None:
                need(time.monotonic() - started < 45 and log.stat().st_size <= 65536, 'build time/log ceiling')
                time.sleep(0.02)
        except BaseException:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
            raise
    need(child.returncode == 0 and log.stat().st_size <= 65536, 'build failed or log exceeded ceiling')
    wheels = sorted(dist.glob('*.whl'))
    need(len(wheels) == 1 and wheels[0].name == WHEEL_NAME, 'exact output wheel identity')
    need({x.name for x in dist.iterdir()} == {WHEEL_NAME, 'build.log'}, 'unexpected output files')
    raw = bounded(wheels[0], 1048576)
    inspection = zip_inventory(raw, 'antlr4_python3_runtime-4.9.3.dist-info', output_wheel=True)
    need(inspection['name'] == 'antlr4-python3-runtime' and inspection['version'] == '4.9.3', 'output name/version')
    requirements = [re.sub(r'\s+', '', x).replace('"', "'") for x in inspection['requires_dist']]
    need(requirements == ["typing;python_version<'3.5'"], 'output runtime dependency must remain source-defined')
    return {'label': label, 'wheel': label + '/' + WHEEL_NAME, 'bytes': len(raw), 'sha256': sha(raw),
            'log': label + '/build.log', 'log_bytes': log.stat().st_size,
            'native_exit': child.returncode, 'inspection': inspection}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=pathlib.Path, required=True)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    need(output.is_dir() and not any(output.iterdir()), 'fresh output directory required')
    result = {'schema': 'standalone_antlr_two_build_v1', 'status': 'FAIL', 'builds': [], 'errors': [],
              'source_sha256': SOURCE_SHA, 'tool_lock_sha256': LOCK_SHA, 'scientific_runtime_qualified': False}
    start = time.monotonic()
    try:
        need(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode, 'isolated no-site startup')
        need(platform.python_version() == '3.11.18' and sys.platform == 'linux'
             and platform.machine() in ('aarch64', 'arm64'), 'selected ARM Python builder only')
        os.umask(0o022)
        work = pathlib.Path('/work')
        need(work.is_dir() and not any(work.iterdir()), 'fresh bounded tmpfs required')
        tools_dir = work / 'tools'
        tools_dir.mkdir()
        lock_raw = bounded(args.inputs / 'TOOL_LOCK.json', 65536)
        need(sha(lock_raw) == LOCK_SHA, 'frozen tool lock')
        lock = json.loads(lock_raw)
        need(lock['status'] == 'ACQUIRED_TOOL_CLOSURE' and lock['extras'] == []
             and {x['name']: x['version'] for x in lock['tools']} == TOOLS, 'selected complete build tooling only')
        tool_checks = []
        for item in lock['tools']:
            need(pathlib.PurePosixPath(item['filename']).name == item['filename'], 'tool filename')
            raw = bounded(args.inputs / item['filename'], 3145728)
            need(len(raw) == item['bytes'] and sha(raw) == item['sha256'], 'actual locked tool wheel')
            root = item['name'].replace('-', '_') + '-' + item['version'] + '.dist-info'
            observed = zip_inventory(raw, root, extract_to=tools_dir)
            need(observed['metadata_sha256'] == item['metadata_sha256'], 'admitted tool metadata')
            tool_checks.append({'name': item['name'], 'version': item['version'], 'sha256': sha(raw), 'inspection': observed})
        source = bounded(args.inputs / 'source.tar.gz', 117034)
        for label in ('first', 'second'):
            result['builds'].append(build_once(label, source, tools_dir, output, work))
        need(result['builds'][0]['sha256'] == result['builds'][1]['sha256'], 'independent wheel bytes differ')
        result.update({'status': 'PASS', 'reproducible_bytes': True,
                       'wheel_sha256': result['builds'][0]['sha256'], 'tool_checks': tool_checks,
                       'environment': {'python': platform.python_version(), 'sys_platform': sys.platform,
                                       'machine': platform.machine(), 'source_date_epoch': EPOCH,
                                       'python_hash_seed': 'uncontrolled_under_isolated_startup',
                                       'hash_randomization_enabled': True},
                       'qualification': 'Only two source-wheel builds in this pinned software environment; no ANTLR import, scientific runtime, model or data qualification.'})
    except BaseException as error:
        result['errors'].append({'type': type(error).__name__, 'message': str(error)[:1024]})
    result['wall_seconds'] = time.monotonic() - start
    body = (json.dumps(result, indent=2) + '\n').encode()
    need(len(body) <= 65536, 'result ceiling')
    with (output / 'RESULT.json').open('xb') as stream:
        stream.write(body)
    print(json.dumps({'status': result['status'], 'result_bytes': len(body), 'result_sha256': sha(body),
                      'wheel_sha256': result.get('wheel_sha256')}))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
