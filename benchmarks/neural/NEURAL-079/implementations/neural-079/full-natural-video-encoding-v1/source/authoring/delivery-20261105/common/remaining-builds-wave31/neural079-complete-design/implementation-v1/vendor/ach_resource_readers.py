"""Concrete named Linux readers. Enabled constructors require explicit admission.

Nothing probes the host at import. Kernel/file readers are never run by the
source-only construction controls except through explicit invented RAM seams.
"""
import os
import stat
from pathlib import PurePosixPath
from ach_resource_common import (require, integer, fields, check_pin, read_fd,
                                 read_body, close_all, bounded_encode, body_pin)
from ach_resource_model import profile, device, storage_delta, CLASSES


def key_values(raw):
    result = {}
    for line in raw.decode('ascii', 'strict').splitlines():
        pair = line.split()
        require(len(pair) == 2 and pair[0] not in result and pair[1].isdecimal(),
                'unique named integer kernel fields')
        result[pair[0]] = int(pair[1])
    return result


def io_values(raw):
    result = {}
    for line in raw.decode('ascii', 'strict').splitlines():
        parts = line.split()
        require(parts and device(parts[0]) not in result, 'unique device row')
        counts = {}
        for part in parts[1:]:
            pair = part.split('=')
            require(len(pair) == 2 and pair[0] not in counts and pair[1].isdecimal(), 'typed io.stat field')
            counts[pair[0]] = int(pair[1])
        require({'rbytes', 'wbytes'} <= set(counts), 'required storage byte fields present')
        result[parts[0]] = {'read_bytes': counts['rbytes'], 'write_bytes': counts['wbytes']}
    return result


def scalar(raw):
    text = raw.decode('ascii', 'strict').strip()
    require(text.isdecimal(), 'one nonnegative scalar kernel counter')
    return int(text)


def identity(fd):
    status = os.fstat(fd)
    return {'device': status.st_dev, 'inode': status.st_ino}


def absolute(path):
    require(type(path) is str and path.startswith('/') and '\x00' not in path and
            str(PurePosixPath(path)) == path and '..' not in PurePosixPath(path).parts,
            'canonical independently selected absolute path')
    return path


def mount_path(text):
    # mountinfo escapes only these characters in pathname columns.
    for old, new in (('\\040', ' '), ('\\011', '\t'), ('\\012', '\n'), ('\\134', '\\')):
        text = text.replace(old, new)
    return text


def cgroup_mount(raw, path, expected_device):
    selected = []
    for line in raw.decode('utf-8', 'strict').splitlines():
        left, separator, right = line.partition(' - ')
        require(separator, 'complete mountinfo row')
        before, after = left.split(), right.split()
        require(len(before) >= 6 and len(after) >= 3, 'mountinfo fields')
        point = mount_path(before[4])
        if path == point or path.startswith(point.rstrip('/') + '/'):
            selected.append((len(point), before, after))
    require(selected, 'selected scope has a visible mount')
    _, before, after = max(selected, key=lambda x: x[0])
    require(after[0] == 'cgroup2' and before[2] == expected_device,
            'actual unified cgroup2 filesystem identity')
    return {'mount_id': int(before[0]), 'device': before[2], 'mountpoint': mount_path(before[4]),
            'filesystem': after[0]}


class LocalReaders:
    def __init__(self, admitted, selected, clock, *, held_peak_fd=None):
        # Disabled selection refuses before uname, /proc, directories or FDs.
        require(type(admitted) is dict and admitted.get('execution_enabled') is True,
                'typed Linux deployment disabled before host access')
        fields(admitted, ('schema', 'execution_enabled', 'kernel_release', 'kernel_admission_pin',
                          'scope_path', 'scope_identity', 'creation_receipt_pin',
                          'peak_interval_receipt_pin', 'peak_file_identity', 'memory_mode'),
               'complete independent local-reader admission')
        require(admitted['schema'] == 'ach_local_reader_admission_v1', 'selected reader schema')
        self.selected = profile(selected); self.clock = clock; self.admitted = admitted
        for name in ('kernel_admission_pin', 'creation_receipt_pin', 'peak_interval_receipt_pin'):
            check_pin(admitted[name])
        fields(admitted['scope_identity'], ('device', 'inode'), 'admitted scope inode')
        fields(admitted['peak_file_identity'], ('device', 'inode'), 'admitted held peak inode')
        require(admitted['memory_mode'] == selected['memory_mode'], 'same peak interval semantics')
        require(type(admitted['kernel_release']) is str and admitted['kernel_release'], 'exact admitted kernel release')
        self.scope = None; self.peak = None; self.closed = False; self.baseline = None; self.raw_baseline = None
        primary = None
        try:
            clock.tick('scientific')
            require(os.uname().sysname == 'Linux' and os.uname().release == admitted['kernel_release'],
                    'actual selected Linux release')
            self.scope = os.open(absolute(admitted['scope_path']), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            require(identity(self.scope) == admitted['scope_identity'], 'same admitted common ancestor')
            st = os.fstat(self.scope)
            proc = os.open('/proc/self/mountinfo', os.O_RDONLY | os.O_NOFOLLOW)
            error = None
            try:
                raw = read_fd(proc, selected['reader_limits']['file_bytes'], clock, 'scientific')
            except BaseException as exc:
                error = exc; raise
            finally:
                close_all([('mountinfo descriptor', lambda: os.close(proc))], error)
            self.mount = cgroup_mount(raw, admitted['scope_path'], f'{os.major(st.st_dev)}:{os.minor(st.st_dev)}')
            controllers = self.read_named('cgroup.controllers', 'scientific').decode('ascii').split()
            require('memory' in controllers and 'io' in controllers, 'required cgroup controllers available')
            self.events = key_values(self.read_named('cgroup.events', 'scientific'))
            require(self.events.get('populated') in (0, 1), 'population capability')
            if selected['memory_mode'] == 'verified_same_fd_reset':
                require(type(held_peak_fd) is int and held_peak_fd >= 3, 'original reset/read descriptor required')
                self.peak = os.dup(held_peak_fd)
            else:
                require(held_peak_fd is None, 'fresh lifetime has no foreign reset descriptor')
                self.peak = os.open('memory.peak', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=self.scope)
            require(identity(self.peak) == admitted['peak_file_identity'], 'same selected peak file identity')
            # Caller must supply independently authenticated creation/reset
            # chronology. This reader never resets a counter after work began.
            self.read_peak('scientific')
            self.read_named('io.stat', 'scientific')
            for name in selected['supplemental_memory_limits']:
                scalar(self.read_named(name, 'scientific'))
        except BaseException as error:
            primary = error
            self.close(error)
            raise

    def read_named(self, name, phase):
        allowed = {'cgroup.controllers', 'cgroup.events', 'io.stat', 'pids.current',
                   'memory.current'} | set(self.selected['supplemental_memory_limits'])
        require(name in allowed and '/' not in name and not self.closed, 'fixed named kernel reader')
        require(identity(self.scope) == self.admitted['scope_identity'], 'same open scope descriptor')
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=self.scope)
        primary = None
        try:
            require(stat.S_ISREG(os.fstat(fd).st_mode), 'ordinary cgroup virtual control file')
            return read_fd(fd, self.selected['reader_limits']['file_bytes'], self.clock, phase)
        except BaseException as error:
            primary = error; raise
        finally:
            close_all([('named kernel descriptor', lambda: os.close(fd))], primary)

    def read_peak_raw(self, phase):
        require(self.peak is not None and identity(self.peak) == self.admitted['peak_file_identity'],
                'same held peak descriptor')
        os.lseek(self.peak, 0, os.SEEK_SET)
        return read_fd(self.peak, self.selected['reader_limits']['file_bytes'], self.clock, phase)

    def read_peak(self, phase):
        return scalar(self.read_peak_raw(phase))

    def establish_baseline(self):
        require(self.baseline is None, 'one initial baseline')
        require(key_values(self.read_named('cgroup.events', 'scientific')).get('populated') == 0,
                'scope baseline before application/collector processes')
        raw = self.read_named('io.stat', 'scientific')
        values = io_values(raw)
        require(set(values) <= set(self.selected['storage_limits']), 'baseline devices admitted')
        self.baseline, self.raw_baseline = values, body_pin(raw)
        return {'storage_baseline': values, 'raw_pin': self.raw_baseline,
                'scope_identity': self.admitted['scope_identity'], 'observed_ns': self.clock.tick('scientific'),
                'raw_ascii':raw.decode('ascii','strict')}

    def bind_baseline(self, receipt):
        fields(receipt, ('storage_baseline', 'raw_pin', 'scope_identity', 'observed_ns','raw_ascii'), 'same launcher baseline')
        require(self.baseline is None and receipt['scope_identity'] == self.admitted['scope_identity'],
                'one inherited independently authenticated baseline')
        check_pin(receipt['raw_pin']); integer(receipt['observed_ns'])
        require(self.clock.origin <= receipt['observed_ns'] < self.clock.scientific, 'original baseline time')
        raw=receipt['raw_ascii'].encode('ascii','strict')
        require(body_pin(raw)==receipt['raw_pin'] and io_values(raw)==receipt['storage_baseline'], 'exact retained original native baseline')
        self.baseline, self.raw_baseline = receipt['storage_baseline'], receipt['raw_pin']

    def snapshot(self, phase, *, closed=False):
        require(self.baseline is not None and not self.closed, 'scope baseline before observations')
        started=self.clock.tick(phase)
        event_raw=self.read_named('cgroup.events',phase);events=key_values(event_raw)
        require(not closed or events.get('populated') == 0, 'all scope descendants quiescent')
        raw = self.read_named('io.stat', phase)
        devices = storage_delta(self.baseline, io_values(raw), self.selected)
        supplemental_raw={name:self.read_named(name,phase) for name in self.selected['supplemental_memory_limits']}
        supplemental = {name:scalar(value) for name,value in supplemental_raw.items()}
        peak_raw=self.read_peak_raw(phase);peak=scalar(peak_raw);after_raw=None
        if closed:
            after_raw=self.read_named('cgroup.events',phase)
            require(key_values(after_raw).get('populated') == 0,
                    'scope repopulated during final observation')
        return {'storage': {'devices': devices, 'baseline_pin': self.raw_baseline,
                            'current_pin': body_pin(raw), 'attribution': 'kernel_cgroup_charge_not_unique_causal_media'},
                'memory': {'charged_peak_bytes': peak, 'mode': self.selected['memory_mode'],
                           'supplemental': supplemental,
                           'device_memory': {'status': 'unmeasured_not_in_selected_charge_estimand'}},
                'sample_started_ns':started,'observed_ns': self.clock.tick(phase), 'population_observed': events,
                'native_raw':{'events_before':event_raw.decode('ascii'),'events_after':None if after_raw is None else after_raw.decode('ascii'),
                    'io_stat':raw.decode('ascii'),'memory_peak':peak_raw.decode('ascii'),
                    'supplemental':{name:value.decode('ascii') for name,value in supplemental_raw.items()}},
                'scope_identity': {**self.admitted['scope_identity'],
                                   'creation_receipt_pin': self.admitted['creation_receipt_pin']}}

    def close(self, primary=None):
        if self.closed:
            return
        self.closed = True
        operations = []
        for name in ('peak', 'scope'):
            fd = getattr(self, name)
            if fd is not None:
                setattr(self, name, None)
                operations.append((name + ' descriptor', lambda fd=fd: os.close(fd)))
        close_all(operations, primary)


def inventory(roots, selected, clock, *, custody_receipt_pin):
    """Read actual quiesced roots; logical file identities, never allocated media.

    Quiescence and exclusion of foreign writers are independently admitted and
    verified by the finalizer. Directory traversal cannot establish them alone.
    """
    profile(selected); check_pin(custody_receipt_pin)
    clock.tick('outer')
    require(type(roots) is list and roots, 'complete classed root roster')
    seen = {}; aliases = 0; directory_ids = set(); underlying_links = {}; rank = {name: i for i, name in enumerate(selected['retention_class_precedence'])}
    limits = selected['reader_limits']

    def walk(fd, prefix, root, depth):
        nonlocal aliases
        require(depth <= selected['encoding_limits']['depth'], 'directory depth ceiling')
        current = os.fstat(fd); ident = (current.st_dev, current.st_ino)
        require(ident not in directory_ids, 'directory cycle')
        directory_ids.add(ident)
        before = (current.st_dev, current.st_ino, current.st_mtime_ns, current.st_ctime_ns)
        entries = os.scandir(fd); scan_error = None
        try:
            for entry in entries:
                clock.tick('outer'); aliases += 1
                require(aliases <= limits['directory_entries'], 'complete traversal entry ceiling')
                name = entry.name
                require(name not in ('.', '..') and '/' not in name and '\x00' not in name, 'ordinary directory name')
                relative = prefix + name
                require(len(relative) <= limits['path_chars'], 'complete path ceiling')
                status = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(status.st_mode):
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    error = None
                    try:
                        require(identity(child) == {'device': status.st_dev, 'inode': status.st_ino}, 'directory replaced')
                        walk(child, relative + '/', root, depth + 1)
                    except BaseException as exc:
                        error = exc; raise
                    finally:
                        close_all([('inventory directory', lambda: os.close(child))], error)
                    continue
                require(stat.S_ISREG(status.st_mode), 'retention inventory admits ordinary files only')
                child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
                error = None
                try:
                    actual = os.fstat(child)
                    require((actual.st_dev, actual.st_ino, actual.st_size, actual.st_mtime_ns, actual.st_ctime_ns) ==
                            (status.st_dev, status.st_ino, status.st_size, status.st_mtime_ns, status.st_ctime_ns),
                            'file identity changed during inventory')
                    key = (actual.st_dev, actual.st_ino)
                    alias = {'root_id': root['id'], 'path': relative, 'declared_class': root['class']}
                    if key not in seen:
                        require(len(seen) < selected['retention_limits']['files'], 'unique-file ceiling')
                        seen[key] = {'device': key[0], 'inode': key[1], 'bytes': actual.st_size,
                                     'class': root['class'], 'aliases': [], 'links': actual.st_nlink}
                    item = seen[key]
                    require(item['bytes'] == actual.st_size and item['links'] == actual.st_nlink, 'shared backing changed')
                    if rank[root['class']] < rank[item['class']]:
                        item['class'] = root['class']
                    item['aliases'].append(alias)
                    underlying_links.setdefault(key, set()).add((ident[0], ident[1], name))
                except BaseException as exc:
                    error = exc; raise
                finally:
                    close_all([('inventory file', lambda: os.close(child))], error)
        except BaseException as exc:
            scan_error = exc; raise
        finally:
            directory_ids.remove(ident)
            close_all([('inventory iterator', entries.close)], scan_error)
        after = os.fstat(fd)
        require(before == (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns), 'directory changed during inventory')

    ids = set()
    for root in roots:
        fields(root, ('id', 'path', 'class', 'identity', 'custody_pin', 'external_links'), 'full classed root')
        from ach_resource_common import token
        token(root['id']); require(root['id'] not in ids, 'unique root identifier'); ids.add(root['id'])
        require(root['class'] in CLASSES and root['external_links'] in ('forbid', 'declared_shared'), 'explicit inclusion/link policy')
        require(root['external_links'] != 'declared_shared' or root['class'] in ('preexisting', 'imported', 'shared'),
                'new/failed/evidence artifacts require complete link custody')
        check_pin(root['custody_pin']); fields(root['identity'], ('device', 'inode'), 'selected root identity')
        fd = os.open(absolute(root['path']), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        error = None
        try:
            require(identity(fd) == root['identity'], 'same admitted retained root')
            walk(fd, '', root, 0)
        except BaseException as exc:
            error = exc; raise
        finally:
            close_all([('inventory root', lambda: os.close(fd))], error)
    rows = sorted(seen.values(), key=lambda x: (x['device'], x['inode']))
    declared_shared = {root['id'] for root in roots if root['external_links'] == 'declared_shared'}
    for item in rows:
        require(item['links'] <= len(underlying_links[(item['device'], item['inode'])]) or
                any(alias['root_id'] in declared_shared for alias in item['aliases']), 'unaccounted external hard link')
    totals = {name: 0 for name in CLASSES}
    for item in rows:
        totals[item['class']] += item['bytes']
    for name, amount in totals.items():
        require(amount <= selected['retention_limits'][name], 'complete retention class ceiling')
    require(sum(totals.values()) <= selected['retention_limits']['total_unique_bytes'], 'complete logical retention ceiling')
    result = {'schema': 'ach_quiescent_logical_inventory_v1', 'files': rows, 'class_bytes': totals,
              'total_unique_bytes': sum(totals.values()), 'custody_receipt_pin': custody_receipt_pin,
              'physical_allocation_claim': False, 'observed_ns': clock.tick('outer')}
    raw = bounded_encode(result, selected['encoding_limits'])
    return result, raw, {'state': 'closed_logical_inventory', 'class_bytes': totals,
                         'total_unique_bytes': sum(totals.values()), 'files': len(rows), 'inventory_pin': body_pin(raw)}
