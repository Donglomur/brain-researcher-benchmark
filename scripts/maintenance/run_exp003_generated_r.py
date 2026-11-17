#!/usr/bin/env python3
"""One fixed EXP003 generated-control job; no scientific author execution."""
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request

MAX_LOG = 128 * 1024
THREADS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS')


class JobCancelled(RuntimeError):
    """Do not use InterruptedError: selectors intentionally catches that type."""


def need(ok, message):
    if not ok:
        raise ValueError(message)


def fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def secure_parent(path):
    path = Path(path).absolute()
    need('..' not in path.parts, 'normalized absolute path required')
    descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            following = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = following
        return descriptor, path.name
    except BaseException:
        os.close(descriptor)
        raise


def pinned(path, size, digest):
    need(type(size) is int and 0 < size <= 65536, 'source extent refused')
    parent, name = secure_parent(path)
    descriptor = None
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        before = os.fstat(descriptor)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == size, 'ordinary single-link source of exact size required')
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            body = stream.read(size + 1)
        after = os.fstat(descriptor)
        current = os.stat(name, dir_fd=parent, follow_symlinks=False)
        need(fingerprint(before) == fingerprint(after) == fingerprint(current)
             and len(body) == size and hashlib.sha256(body).hexdigest() == digest, 'source pin mismatch')
        return body
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)


def exact_namespace(namespace, expected):
    parent, name = secure_parent(namespace)
    descriptor = None
    found = set()
    allowed_dirs = {str(parent) for name in expected for parent in Path(name).parents if str(parent) != '.'}
    def walk(directory, prefix=''):
        before = os.fstat(directory)
        names = os.listdir(directory)
        need(len(names) <= 32, 'source namespace entry limit')
        for name in names:
            relative = prefix + name
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                need(relative in allowed_dirs, 'unexpected source directory')
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                try:
                    walk(child, relative + '/')
                finally:
                    os.close(child)
            else:
                need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and relative in expected, 'unexpected or linked source file')
                found.add(relative)
        need(fingerprint(before) == fingerprint(os.fstat(directory)), 'source namespace changed during inspection')
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        walk(descriptor)
        need(found == set(expected), 'source namespace membership mismatch')
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)


def local(root, name):
    path = Path(name)
    need(not path.is_absolute() and '..' not in path.parts and str(path) == name, 'normalized source path required')
    target = root / path
    for part in (target, *target.parents):
        if part == root.parent:
            break
        need(not part.is_symlink(), 'source symlink refused')
    return target


def cleanup_group(process, output_eof):
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
    try:
        if process is not None:
            # The session remains owned after leader exit while descendants may
            # retain stdout. Always TERM/KILL that group, then reap and close.
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
            if not output_eof:
                time.sleep(0.1)
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=3)
    finally:
        if process is not None and process.stdout is not None:
            process.stdout.close()
        # Pending cancellation is delivered only after group escalation, reap
        # and pipe closure, including pull/inspect without a named container.
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def command(argv, log, seconds=180, allowed_exit=(0,)):
    process = None
    started = time.monotonic()
    retained = 0
    output_eof = False
    with log.open('xb') as stream:
        try:
            process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    remaining = seconds - (time.monotonic() - started)
                    need(remaining > 0, 'command deadline: ' + log.name)
                    for key, _ in selector.select(min(0.1, remaining)):
                        chunk = os.read(key.fd, min(16384, MAX_LOG - retained + 1))
                        if not chunk:
                            output_eof = True
                            selector.unregister(key.fileobj)
                            continue
                        admitted = chunk[:MAX_LOG - retained]
                        stream.write(admitted)
                        stream.flush()
                        retained += len(admitted)
                        need(len(admitted) == len(chunk), 'command log limit: ' + log.name)
            process.wait(timeout=max(0.01, seconds - (time.monotonic() - started)))
            need(process.returncode in allowed_exit, 'command failed: ' + log.name)
        finally:
            cleanup_group(process, output_eof)
    need(log.stat().st_size <= MAX_LOG, 'command log limit')
    return log.read_text(errors='strict')


def cancel(signum, frame):
    # Give the owned child/container cleanup one non-reentrant opportunity;
    # the workflow's independent 35-second KILL grace remains the hard bound.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    raise JobCancelled('generated-control job cancelled')


def cleanup_container(name, log):
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
    try:
        text = command(['docker', 'rm', '--force', name], log, 20, allowed_exit=(0, 1))
        need(text.strip() == name or ('No such container: ' + name) in text,
             'owned container removal was not confirmed')
    finally:
        # A first cancellation during ordinary cleanup is delivered only after
        # the bounded cleanup finishes. Do not abandon the owned container.
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def owned_container(argv, name, log):
    try:
        return command(argv, log)
    finally:
        cleanup_container(name, log.with_name(log.name + '.cleanup'))


def strict_result(parsed, controls):
    need(parsed.strip() == '4 R source files parsed; no expressions evaluated.', 'parse success marker mismatch')
    expected = 'Generated R collector/parse checks: 219 passed; no estimator called.'
    need(re.findall(r'^Generated R collector/parse checks: .*$', controls, re.MULTILINE) == [expected], 'generated control count/outcome mismatch')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def read_dependency_response(response, extent, raw, receipt):
    while len(raw) <= extent:
        chunk = response.read1(min(16384, extent + 1 - len(raw)))
        if not chunk:
            break
        raw.extend(chunk)
        receipt['body_bytes_read'] = len(raw)


def acquire_jsonlite(spec, output):
    need(spec['url'] == 'https://cran.r-project.org/src/contrib/Archive/jsonlite/jsonlite_1.8.8.tar.gz'
         and spec['bytes'] == 1053028, 'only exact jsonlite source acquisition is permitted')
    receipt = {'url': spec['url'], 'body_bytes_read': 0, 'scope': 'one dependency source archive', 'retries': 0, 'redirects_followed': 0}
    raw = bytearray()
    def expired(signum, frame):
        raise TimeoutError('dependency acquisition deadline')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 60)
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        response = None
        try:
            response = opener.open(spec['url'], timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            receipt['status'] = response.code
            receipt['final_url'] = response.geturl()
            need(response.geturl() == spec['url'], 'dependency redirect refused')
            read_dependency_response(response, spec['bytes'], raw, receipt)
            body = bytes(raw)
        receipt['body_sha256'] = hashlib.sha256(body).hexdigest()
        need(receipt['status'] == 200 and len(body) == spec['bytes'] and receipt['body_sha256'] == spec['sha256'], 'dependency bytes/digest/status mismatch')
        target = output / 'jsonlite_1.8.8.tar.gz'
        target.write_bytes(body)
        receipt['status_result'] = 'authenticated_before_install'
        return target
    except BaseException as error:
        receipt['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        (output / 'dependency-response.bin').write_bytes(raw)
        receipt['retained_response_sha256'] = hashlib.sha256(raw).hexdigest()
        (output / 'dependency-acquisition.json').write_text(json.dumps(receipt, indent=2) + '\n')


def main():
    need(len(sys.argv) == 6, 'descriptor bytes digest checkout output required')
    descriptor = Path(sys.argv[1])
    document = json.loads(pinned(descriptor, int(sys.argv[2]), sys.argv[3]))
    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)
    root = Path(sys.argv[4]).resolve()
    output = Path(sys.argv[5]).absolute()
    need(document['schema'] == 'exp003-generated-r-environment/v1', 'descriptor schema mismatch')
    need(not output.exists() and not output.is_symlink() and not output.resolve().is_relative_to(root), 'fresh external output required')
    for parent in output.parents:
        need(not parent.is_symlink(), 'output symlink refused')
    output.mkdir(mode=0o700)
    prefix = document['namespace'] + '/'
    expected_members = {name[len(prefix):] for name in document['source_files'] if name.startswith(prefix)}
    need(len(expected_members) == 9, 'exact nine reviewed source files required')
    exact_namespace(local(root, document['namespace']), expected_members)
    for name, pin in document['source_files'].items():
        pinned(local(root, name), pin['bytes'], pin['sha256'])
    for name in THREADS:
        os.environ[name] = '1'
    image = document['image']['identity']
    need(re.fullmatch(r'rocker/r-ver@sha256:[0-9a-f]{64}', image), 'exact image identity required')
    command(['docker', 'pull', '--platform', 'linux/arm64', image], output/'image-pull.log')
    observation = json.loads(command(['docker', 'image', 'inspect', image], output/'image-inspect.log', 20))
    need(len(observation) == 1 and observation[0]['Id'] == document['image']['config_digest'] and observation[0]['Os'] == 'linux' and observation[0]['Architecture'] == 'arm64', 'pulled image identity/platform mismatch')
    archive = acquire_jsonlite(document['jsonlite'], output)
    library = output/'library';library.mkdir(mode=0o700)
    namespace = local(root, document['namespace'])
    field_schema = local(root, document['field_schema'])
    inside = '/inputs/nider-primary-producer-v2'
    name = 'exp003-generated-' + str(os.getpid())
    common = ['docker','run','--rm','--name',name,'--platform','linux/arm64','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','64','--cpus','1','--memory','256m','--memory-swap','256m','--user',str(os.getuid())+':'+str(os.getgid()),'--tmpfs','/tmp:rw,nosuid,nodev,size=134217728','--env','HOME=/tmp','--env','R_LIBS_USER=/library']
    for variable in THREADS:
        common += ['--env', variable+'=1']
    def container(args, logfile, install=False):
        mounts = ['--mount','type=bind,src='+str(library)+',dst=/library'+('' if install else ',readonly')]
        if install:
            mounts += ['--mount','type=bind,src='+str(archive)+',dst=/package/jsonlite.tar.gz,readonly']
        else:
            mounts += ['--mount','type=bind,src='+str(namespace)+',dst='+inside+',readonly','--mount','type=bind,src='+str(field_schema)+',dst=/inputs/nider-full120-reconstruction-profile-v1/participant/FIELD_SCHEMA.json,readonly','--workdir',inside]
        return owned_container(common+mounts+[image]+args, name, output/logfile)
    container(['R','CMD','INSTALL','--no-docs','--no-html','--no-demo','--no-help','--no-multiarch','--library=/library','/package/jsonlite.tar.gz'],'jsonlite-install.log',install=True)
    container(['Rscript','--vanilla','-e','stopifnot(as.character(getRversion()) == "4.3.2", as.character(utils::packageVersion("jsonlite")) == "1.8.8"); print(sessionInfo())'],'runtime-version.log')
    parsed = container(['Rscript','--vanilla','-e',document['parse_expression']],'parse.log')
    controls = container(['Rscript','--vanilla','tests/collector_controls.R',inside],'generated-controls.log')
    strict_result(parsed, controls)
    (output/'result.json').write_text(json.dumps({'scope':'generated_R_source_controls_only','source_commit':document['source_commit'],'parsed_files':4,'checks':219,'skips':0,'scientific_qualification':False,'authentic_data_reads':0,'author_expression_evaluation':False}, indent=2)+'\n')


if __name__ == '__main__':
    main()
