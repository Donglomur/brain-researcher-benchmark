"""FIND032 fresh Debian host construction SOURCE; never run during authoring.

This is an explicit root installer for a disposable, otherwise unused host.
It neither invokes the reference producer nor constructs a cgroup delegation.
The upstream CPython configure/build sequence is adapted from docker-library/
python; preserve UPSTREAM_DOCKER_PYTHON_LICENSE.txt with this file.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
import urllib.request


PREFIX = Path('/opt/find032-host/python-3.11.11')
ROOT = PREFIX.parent
SHA = re.compile('[0-9a-f]{64}')


def need(value, message):
    if not value:
        raise RuntimeError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def ordinary(path, maximum):
    path = Path(path)
    need(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)),
         'absolute unlinked operand required: ' + str(path))
    s = path.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size <= maximum,
         'bounded ordinary operand: ' + str(path))
    identity = lambda v: (v.st_dev,v.st_ino,v.st_mode,v.st_nlink,v.st_size,v.st_mtime_ns,v.st_ctime_ns)
    fd = None; parts = []; first = None; secondary = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        need(identity(os.fstat(fd)) == identity(s), 'opened ordinary identity')
        left = s.st_size
        while left:
            raw = os.read(fd, min(65536,left))
            need(bool(raw), 'short ordinary read')
            parts.append(raw); left -= len(raw)
        need(not os.read(fd,1), 'ordinary extent grew')
        need(identity(s)==identity(os.fstat(fd))==identity(path.lstat()),'stable ordinary identity')
    except BaseException as error:
        first = error
    finally:
        if fd is not None:
            try: os.close(fd)
            except BaseException as error: secondary = error
    if first is not None:
        if secondary is not None: first.add_note('Secondary ordinary close: '+repr(secondary))
        ORIGINAL_ERRORS.append((first,secondary,tuple(parts)))
        raise first
    if secondary is not None:
        ORIGINAL_ERRORS.append((secondary,None,tuple(parts)))
        raise secondary
    return b''.join(parts)


ORIGINAL_ERRORS = []


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def publish(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(body)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


class Build:
    def __init__(self, args, lock, recipe):
        self.args, self.lock, self.recipe = args, lock, recipe
        self.end = time.monotonic() + args.total_seconds
        self.events = []
        self.downloaded = 0
        self.env = {
            'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': str(ROOT / 'home'),
            'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC',
            'DEBIAN_FRONTEND': 'noninteractive', 'PYTHONDONTWRITEBYTECODE': '1',
            'PIP_DISABLE_PIP_VERSION_CHECK': '1', 'PIP_NO_CACHE_DIR': '1',
            'PIP_CONFIG_FILE': '/dev/null', 'RPY2_CFFI_MODE': 'API',
            'R_HOME': '/usr/lib/R', 'LD_LIBRARY_PATH': '/usr/lib/R/lib',
            'MPLBACKEND': 'Agg', 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1',
            'MKL_NUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1',
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
            'GIT_TERMINAL_PROMPT': '0', 'TMPDIR': str(ROOT / 'tmp'),
        }

    def run(self, name, argv, *, cwd=None, allowed_status=(0,)):
        need(re.fullmatch('[a-z0-9-]+', name), 'fixed command name')
        remaining = self.end - time.monotonic()
        need(remaining > 6, 'original total build interval exhausted')
        seconds = min(self.args.command_seconds, remaining - 5)
        logfile = ROOT / 'logs' / (name + '.log')
        row = {'name': name, 'argv': argv, 'cwd': str(cwd or ROOT),
               'timeout_seconds': seconds, 'log': str(logfile), 'allowed_status': list(allowed_status)}
        self.events.append(row)
        publish(ROOT / 'logs' / (name + '.command.json'), encoded(row))
        # GNU timeout owns its command group. Capture one combined bounded pipe;
        # do not cap compiler-created files with a process-wide RLIMIT_FSIZE.
        process = None
        selector = None
        first = None
        secondaries = []
        count = 0
        command_end = min(self.end-5, time.monotonic() + seconds)
        try:
            process = subprocess.Popen(
                ['/usr/bin/timeout', '--signal=TERM', '--kill-after=5', str(seconds), *argv],
                cwd=cwd or ROOT, env=self.env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            with logfile.open('xb') as output:
                while selector.get_map():
                    need(time.monotonic() < command_end, 'original command capture cutoff')
                    for key, _ in selector.select(min(.05, max(0,command_end-time.monotonic()))):
                        raw = os.read(key.fileobj.fileno(), min(65536, self.args.log_bytes+1-count))
                        if not raw:
                            selector.unregister(key.fileobj)
                            continue
                        output.write(raw); output.flush(); count += len(raw)
                        need(count <= self.args.log_bytes, 'original combined build log exceeded selection')
                # Observe without reaping. The retained leader PID prevents
                # reuse of its group number before a failure retirement attempt.
                terminal = None
                while terminal is None:
                    need(time.monotonic() < command_end, 'original terminal status cutoff')
                    terminal = os.waitid(os.P_PID, process.pid,
                                         os.WEXITED | os.WNOHANG | os.WNOWAIT)
                    if terminal is None:
                        time.sleep(min(.005,max(0,command_end-time.monotonic())))
                row['observed_terminal'] = {'code':terminal.si_code,'status':terminal.si_status}
                need(terminal.si_code == os.CLD_EXITED and terminal.si_status in allowed_status,
                     'build command failed: '+name)
        except BaseException as error:
            first = error
        finally:
            if process is not None:
                try:
                    if process.stdout is not None:
                        process.stdout.close()
                except BaseException as error:
                    secondaries.append(error)
            if selector is not None:
                try:
                    selector.close()
                except BaseException as error:
                    secondaries.append(error)
            if (first is not None or secondaries) and process is not None:
                # Only the just-created session/group; no PID rediscovery or
                # host-wide process matching. The leader is still unreaped even
                # after an observed nonzero status. No re-execution on failure.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except BaseException as error:
                    secondaries.append(error)
            if process is not None:
                try:
                    process.wait(timeout=max(0, min(self.end,command_end+5)-time.monotonic()))
                except BaseException as error:
                    secondaries.append(error)
        row['exit_code'] = None if process is None else process.returncode
        row['first_error'] = None if first is None else {'type':type(first).__name__,'message':str(first)}
        row['secondary_errors'] = [{'type':type(e).__name__,'message':str(e)} for e in secondaries]
        try:
            row['log_pin'] = pin(ordinary(logfile, self.args.log_bytes+1)) if logfile.exists() else None
        except BaseException as error:
            secondaries.append(error); row['log_pin'] = None
        row['secondary_errors'] = [{'type':type(e).__name__,'message':str(e)} for e in secondaries]
        try:
            publish(ROOT / 'logs' / (name + '.result.json'), encoded(row))
        except BaseException as error:
            secondaries.append(error)
            row['secondary_errors'].append({'type':type(error).__name__,'message':str(error)})
        if first is not None or secondaries:
            ORIGINAL_ERRORS.append((first,tuple(secondaries),process))
        if first is not None:
            raise first
        if secondaries:
            raise secondaries[0]
        need(time.monotonic() < self.end, 'original total build interval exhausted')
        captured_log=ordinary(logfile,self.args.log_bytes)
        need(time.monotonic() < self.end, 'original total build interval exhausted after log capture')
        return captured_log

    def fetch(self, name, row):
        need(type(row['bytes']) is int and row['bytes'] > 0 and SHA.fullmatch(row['sha256']),
             'fixed download descriptor')
        need(row['url'].startswith(('https://www.python.org/ftp/python/',
                                   'https://files.pythonhosted.org/')),
             'fixed software download authority')
        self.downloaded += row['bytes']
        need(self.downloaded <= self.args.download_bytes, 'selected software download ceiling')
        need(time.monotonic() < self.end, 'original download interval')
        output = ROOT / 'downloads' / name
        digest = hashlib.sha256()
        count = 0
        request = urllib.request.Request(row['url'], headers={'User-Agent': 'find032-host-build/1'})
        with urllib.request.urlopen(request, timeout=min(30, self.end-time.monotonic())) as response:
            need(response.url.startswith(('https://www.python.org/', 'https://files.pythonhosted.org/')),
                 'download redirect authority')
            with output.open('xb') as stream:
                while True:
                    need(time.monotonic() < self.end, 'original download cutoff')
                    part = response.read(min(65536, row['bytes'] + 1 - count))
                    if not part:
                        break
                    stream.write(part); digest.update(part); count += len(part)
                    need(count <= row['bytes'], 'download extent overrun')
                stream.flush(); os.fsync(stream.fileno())
        need(count == row['bytes'] and digest.hexdigest() == row['sha256'],
             'download identity mismatch: ' + name)
        return output


def installed(raw):
    result = {}
    for line in raw.decode().splitlines():
        name, version, architecture, status = line.split('\t')
        need(status == 'ii ' and architecture in ('all', 'amd64'),
             'only completely installed amd64/all packages supported')
        need(name not in result and re.fullmatch('[a-z0-9][a-z0-9+.-]*', name),
             'unique installed package names')
        result[name] = version
    need(bool(result), 'nonempty dedicated Debian host')
    return result


def versions(raw):
    result = {}
    for line in raw.decode().splitlines():
        name, version, origin = [v.strip() for v in line.split('|', 2)]
        need(origin.startswith('https://snapshot.debian.org/archive/'), 'snapshot index only')
        result.setdefault(name, set()).add(version)
    return result


def planned(raw, before):
    result = dict(before)
    for line in raw.decode().splitlines():
        need(not line.startswith('Remv '), 'host package removals unsupported')
        if line.startswith('Inst '):
            match = re.match(r'Inst ([a-z0-9][a-z0-9+.-]*)(?: \[[^]]+\])? \(([^ ]+) ', line)
            need(match is not None, 'unrecognized exact APT installation plan')
            result[match[1]] = match[2]
    return result


def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--fresh-dedicated-host', action='store_true', required=True)
    parser.add_argument('--jobs', type=int, required=True)
    parser.add_argument('--command-seconds', type=int, required=True)
    parser.add_argument('--total-seconds', type=int, required=True)
    parser.add_argument('--log-bytes', type=int, required=True)
    parser.add_argument('--download-bytes', type=int, required=True)
    parser.add_argument('--minimum-free-bytes', type=int, required=True)
    args = parser.parse_args()
    need(all(getattr(args, k) > 0 for k in ('jobs','command_seconds','total_seconds',
         'log_bytes','download_bytes','minimum_free_bytes')), 'all resource selections explicit and positive')
    need(os.geteuid() == 0 and platform.system() == 'Linux' and platform.machine() == 'x86_64',
         'fresh Linux x86-64 root host only')
    need(sys.version_info[:2] == (3, 11), 'Debian bookworm bootstrap Python 3.11 required')
    recipe = Path(__file__).absolute().parent
    lockraw = ordinary(recipe / 'host-build.lock.json', 262144)
    lock = json.loads(lockraw)
    need(lock['schema'] == 'find032_fresh_host_build_v1', 'fixed host lock schema')
    need(lock['prefix'] == str(PREFIX), 'fixed nonrelocatable host prefix')
    for row in lock['accepted_recipe_files']:
        raw = ordinary(recipe / row['path'], row['bytes'])
        need(pin(raw) == {k:row[k] for k in ('bytes','sha256')}, 'original recipe identity: '+row['path'])
    os_release = ordinary(Path('/etc/os-release').resolve(), 65536).decode()
    need('\nID=debian\n' in '\n'+os_release and '\nVERSION_CODENAME=bookworm\n' in '\n'+os_release,
         'dedicated Debian bookworm host only')
    need(not ROOT.exists() and not ROOT.is_symlink(), 'fresh /opt/find032-host required; no automatic recovery')
    need(not any(p.is_symlink() for p in (ROOT.parent, *ROOT.parent.parents)), 'unlinked /opt ancestry')
    need(not any(Path(p).exists() for p in ('/etc/pip.conf','/etc/xdg/pip/pip.conf')),
         'ambient global pip configuration unsupported on the fresh host')
    site = Path('/usr/local/lib/R/site-library')
    need(not site.exists() or (site.is_dir() and not site.is_symlink() and not any(site.iterdir())),
         'no preexisting local R packages on the dedicated host')
    fs = os.statvfs('/opt')
    need(fs.f_bavail * fs.f_frsize >= args.minimum_free_bytes, 'selected initial build storage')
    ROOT.mkdir(mode=0o700)
    for name in ('logs','downloads','tmp','home','apt','source'):
        (ROOT / name).mkdir(mode=0o700)
    build = Build(args, lock, recipe)
    publish(ROOT / 'SELECTED_BUILD.json', encoded({'args':vars(args),'lock':pin(lockraw),
        'environment':build.env,'started_monotonic':time.monotonic(),
        'end_monotonic':build.end,'native_qualification':False,'scientific_qualification':False}))
    try:
        need(not build.run('foreign-architecture', ['/usr/bin/dpkg','--print-foreign-architectures']).strip(),
             'foreign package architectures unsupported')
        # Modified packaged files or configuration make this host unsupported;
        # this installer never tries to restore an arbitrary existing host.
        need(not build.run('verify-initial-dpkg', ['/usr/bin/dpkg','--verify']).strip(),
             'modified packaged host files unsupported')
        dpkg = ['/usr/bin/dpkg-query','-W','-f=${Package}\t${Version}\t${Architecture}\t${db:Status-Abbrev}\n']
        before = installed(build.run('initial-packages', dpkg))
        for name in ('lists','archives','empty-parts'):
            (ROOT/'apt'/name).mkdir(mode=0o700)
        (ROOT/'apt'/'lists'/'partial').mkdir(mode=0o700)
        (ROOT/'apt'/'archives'/'partial').mkdir(mode=0o700)
        publish(ROOT/'apt'/'preferences', b'Package: *\nPin: origin "snapshot.debian.org"\nPin-Priority: 1001\n')
        config = '\n'.join([
            'Dir::Etc::parts "'+str(ROOT/'apt'/'empty-parts')+'";',
            'Dir::Etc::main "/dev/null";',
            'Dir::Etc::sourcelist "'+str(recipe/'sources.list')+'";',
            'Dir::Etc::sourceparts "'+str(ROOT/'apt'/'empty-parts')+'";',
            'Dir::Etc::preferences "'+str(ROOT/'apt'/'preferences')+'";',
            'Dir::Etc::preferencesparts "'+str(ROOT/'apt'/'empty-parts')+'";',
            'Dir::Etc::trusted "/usr/share/keyrings/debian-archive-keyring.gpg";',
            'Dir::Etc::trustedparts "'+str(ROOT/'apt'/'empty-parts')+'";',
            'Dir::State::lists "'+str(ROOT/'apt'/'lists')+'";',
            'Dir::Cache::archives "'+str(ROOT/'apt'/'archives')+'";',
            'APT::Sandbox::User "root";', 'Acquire::AllowInsecureRepositories "false";',
            'Acquire::AllowDowngradeToInsecureRepositories "false";', 'APT::Get::AllowUnauthenticated "false";',
            'Acquire::Retries "0";', 'Acquire::http::Timeout "30";', 'Acquire::https::Timeout "30";',
        ])+'\n'
        publish(ROOT/'apt'/'apt.conf', config.encode()); build.env['APT_CONFIG']=str(ROOT/'apt'/'apt.conf')
        build.run('apt-update', ['/usr/bin/apt-get','update'])
        # Reuse the accepted check's exact cleartext transformation against our
        # isolated lists directory. APT has independently checked signatures.
        indexes = []
        for row in lock['release_files']:
            suite=row['url'].rsplit('/',2)[1]
            matches=list((ROOT/'apt'/'lists').glob('snapshot.debian.org_archive_*_20250409T000000Z_dists_'+suite+'_InRelease'))
            need(len(matches)==1,'one actual signed index per selected suite')
            raw=ordinary(matches[0],2097152)
            need(raw.startswith(b'-----BEGIN PGP SIGNED MESSAGE-----\n'),'signed index cleartext')
            start=raw.find(b'\n\n');end=raw.find(b'\n-----BEGIN PGP SIGNATURE-----',start+2)
            need(start>=0 and end>start,'signed index framing')
            clear=b'\n'.join(x[2:] if x.startswith(b'- ') else x for x in raw[start+2:end].split(b'\n'))+b'\n'
            need(pin(clear)=={k:row[k] for k in ('bytes','sha256')},'exact snapshot Release identity')
            indexes.append({'name':row['name'],'cleartext':pin(clear),'signed_body':pin(raw)})
        publish(ROOT/'APT_INDEXES.json',encoded(indexes))
        packages=lock['apt_direct_packages']
        names=sorted(set(before)|{v.split('=',1)[0] for v in packages})
        available=versions(build.run('apt-available-before',['/usr/bin/apt-cache','madison',*names]))
        need(all(v in available.get(k,set()) for k,v in before.items()),
             'initial package version outside the authenticated snapshots; unsupported host')
        # Highest authenticated snapshot version, using dpkg's actual version
        # comparator, except the already-exact R=4.2.2 Debian version operands.
        selected=[]
        for item in packages:
            name,sep,exact=item.partition('=')
            choices=sorted(available.get(name,set()))
            need(bool(choices),'direct package absent from selected indexes: '+name)
            if not sep:
                exact=choices[0]
                for index,version in enumerate(choices[1:]):
                    build.run('compare-'+name+'-'+str(index),
                              ['/usr/bin/dpkg','--compare-versions',version,'gt',exact],allowed_status=(0,1))
                    if build.events[-1]['exit_code']==0:exact=version
            need(exact in choices,'pinned direct package absent from snapshots')
            selected.append(name+'='+exact)
        common=['/usr/bin/apt-get','--no-install-recommends','--no-remove','--allow-downgrades']
        desired=planned(build.run('apt-initial-plan',[*common,'--simulate','install',*selected]),before)
        all_available=versions(build.run('apt-available-plan',['/usr/bin/apt-cache','madison',*sorted(desired)]))
        need(all(v in all_available.get(k,set()) for k,v in desired.items()),'complete plan snapshot membership')
        exact=[k+'='+v for k,v in sorted(desired.items())]
        second=planned(build.run('apt-exact-plan',[*common,'--simulate','install',*exact]),before)
        need(second==desired,'explicit full version vector changed solver plan')
        publish(ROOT/'APT_INSTALL_SELECTION.json',encoded({'before':before,'direct':selected,
                'complete_after':desired,'exact_install_argv':[*common,'-y','install',*exact],
                'snapshot_membership_verified':True,'host_binary_reproducibility_claimed':False}))
        need(installed(build.run('unchanged-packages-before-install',dpkg))==before,'concurrent package mutation')
        build.run('apt-install', [*common,'-y','install',*exact])
        need(installed(build.run('installed-packages',dpkg))==desired,'actual package vector differs from selected plan')
        need(not build.run('verify-installed-dpkg',['/usr/bin/dpkg','--verify']).strip(),'modified installed package bodies')
        archive=build.fetch('Python-3.11.11.tar.xz',lock['cpython_source'])
        source=ROOT/'source'/'Python-3.11.11';source.mkdir(mode=0o700)
        build.run('python-extract',['/usr/bin/tar','--extract','--directory',str(source),
                                  '--strip-components=1','--file',str(archive)])
        architecture=build.run('gnu-architecture',['/usr/bin/dpkg-architecture','--query','DEB_BUILD_GNU_TYPE']).decode().strip()
        need(architecture=='x86_64-linux-gnu','selected GNU architecture')
        cflags=build.run('compiler-flags',['/usr/bin/dpkg-buildflags','--get','CFLAGS']).decode().strip()
        ldflags=build.run('linker-flags',['/usr/bin/dpkg-buildflags','--get','LDFLAGS']).decode().strip()
        build.run('python-configure',[str(source/'configure'),'--prefix='+str(PREFIX),
                  '--build='+architecture,*lock['configure_flags']],cwd=source)
        linker=(ldflags or '-Wl')+',--strip-all'
        build.run('python-build',['/usr/bin/make','-j',str(args.jobs),'EXTRA_CFLAGS='+cflags,
                                  'LDFLAGS='+linker],cwd=source)
        # Exact source-directory executable only; never remove a host Python.
        (source/'python').unlink()
        build.run('python-link-prefix',['/usr/bin/make','-j',str(args.jobs),'EXTRA_CFLAGS='+cflags,
                  'LDFLAGS='+linker+",-rpath='$$ORIGIN/../lib'",'python'],cwd=source)
        build.run('python-install',['/usr/bin/make','install'],cwd=source)
        python=str(PREFIX/'bin'/'python3.11')
        build.run('python-linkage',['/usr/bin/readelf','-d',python])
        environment=json.loads(ordinary(recipe/'environment.lock.json',1048576))
        for row in environment['python_artifacts']:
            build.fetch(row['filename'],row)
        groups={'bootstrap':{'pip','setuptools','wheel'},'rpy2':{'rpy2'}}
        groups['wheels']={row['name'] for row in environment['python_artifacts']}-groups['bootstrap']-groups['rpy2']
        for group in ('bootstrap','wheels','rpy2'):
            rows=[r for r in environment['python_artifacts'] if r['name'] in groups[group]]
            text=''.join(str(ROOT/'downloads'/r['filename'])+' --hash=sha256:'+r['sha256']+'\n' for r in rows)
            requirements=ROOT/('requirements-'+group+'.txt');publish(requirements,text.encode())
            argv=[python,'-I','-B','-m','pip','--isolated','install','--no-index','--require-hashes',
                  '--no-deps','--no-compile','--no-cache-dir','-r',str(requirements)]
            argv+=['--no-build-isolation'] if group=='rpy2' else ['--only-binary=:all:']
            build.run('pip-'+group,argv)
        bayes=ROOT/'source'/'BayesFactor';bayes.mkdir(mode=0o700)
        git=['/usr/bin/git','-c','credential.helper=','-c','core.askPass=','-C',str(bayes)]
        build.run('bayesfactor-init',[*git,'init'])
        build.run('bayesfactor-fetch',[*git,'fetch','--depth=1',environment['r']['bayesfactor']['repository'],
                                      environment['r']['bayesfactor']['commit']])
        fetched=build.run('bayesfactor-commit',[*git,'rev-parse','FETCH_HEAD']).decode().strip()
        need(fetched==environment['r']['bayesfactor']['commit'],'exact CRAN mirror commit')
        build.run('bayesfactor-checkout',[*git,'checkout','--detach',fetched])
        site.mkdir(mode=0o755,parents=True,exist_ok=True)
        build.run('bayesfactor-install',['/usr/bin/R','CMD','INSTALL','--library='+str(site),str(bayes)])
        build.run('pip-check',[python,'-I','-B','-m','pip','--isolated','check'])
        build.run('environment-verification',[python,'-I','-B',str(recipe/'verify_environment.py'),
                                             '--lock',str(recipe/'environment.lock.json')])
        build.run('host-verification',[python,'-I','-S','-B',str(recipe/'verify_host.py'),
                                      '--environment-lock',str(recipe/'environment.lock.json')])
        need(time.monotonic() < build.end, 'original total build cutoff before final publication')
        publish(ROOT/'BUILD_COMPLETE.json',encoded({'schema':'find032_host_build_result_v1',
            'status':'constructed_and_dependency_checked_not_natively_or_scientifically_qualified',
            'python':python,'numerical_search_roots':[str(PREFIX/'lib/python3.11/site-packages')],
            'runtime_environment':{'R_HOME':'/usr/lib/R','LD_LIBRARY_PATH':'/usr/lib/R/lib','TZ':'UTC'},
            'events':build.events,'native_qualification':False,'scientific_qualification':False}))
        need(time.monotonic() < build.end, 'original total build cutoff after final publication')
    except BaseException as error:
        try:
            publish(ROOT/'BUILD_FAILURE.json',encoded({'type':type(error).__name__,'message':str(error),
                'events':build.events,'no_retry_or_cleanup_performed':True,'native_qualification':False}))
        except BaseException as secondary:
            print('Secondary failure report publication error: '+repr(secondary),file=sys.stderr)
        raise


if __name__=='__main__':
    main()
