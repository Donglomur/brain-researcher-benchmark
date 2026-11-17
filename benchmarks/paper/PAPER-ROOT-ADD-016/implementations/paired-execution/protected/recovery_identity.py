"""Exact reused Cardiac recovery functions; no other task routes."""
import copy
import re
from types import SimpleNamespace

def need(ok, message):
    if not ok:
        raise ValueError(message)


class RequestCaptured(Exception):
    pass


def capture_request(engine_class, method, args, profile=None):
    """Execute only the frozen request constructor; every I/O method is replaced."""
    class Capture(engine_class):
        def own(self, kind, name, argv):
            self.captured = (kind, name, argv)
        def run(self, *unused, **kwargs):
            return SimpleNamespace(returncode=0)
        def inspect(self, *unused):
            raise RequestCaptured()
    instance = object.__new__(Capture)
    if profile is not None:
        instance.profile = profile
    try:
        getattr(instance, method)(*args)
    except RequestCaptured:
        return instance.captured
    raise ValueError('Frozen constructor did not reach captured inspect')


def verify_live(info, expected, captured):
    kind, name = expected['kind'], expected['name']
    if kind == 'volume':
        module = expected['module']
        need(info.get('Name') == name and info.get('Driver') == 'local' and info.get('Scope') == 'local' and
             info.get('Options') == {'type': 'tmpfs', 'device': 'tmpfs', 'o': module.VOLUME_OPTIONS} and
             type(info.get('CreatedAt')) is str and bool(info['CreatedAt']) and
             type(info.get('Mountpoint')) is str and bool(info['Mountpoint']), 'Exact live local tmpfs volume')
        for before in captured:
            need(all(before.get(key) == info.get(key) for key in ('Name', 'Driver', 'Scope', 'Options', 'CreatedAt', 'Mountpoint')),
                 'Volume matches all captured creation identities')
        return name
    identity = info.get('Id')
    need(type(identity) is str and re.fullmatch('[a-f0-9]{64}', identity) and info.get('Name') == '/' + name,
         'Exact live immutable container ID and name')
    for before in captured:
        need(all(before.get(key) == info.get(key) for key in ('Id', 'Name', 'Image', 'Config', 'HostConfig')),
             'Live identity/configuration matches all captured inspections')
    state = info.get('State')
    need(type(state) is dict and state.get('Status') in ('created', 'running', 'paused', 'restarting', 'exited', 'dead', 'removing') and
         type(state.get('Running')) is bool, 'Recognized current lifecycle')
    checked = copy.deepcopy(info)
    checked['State'].update(Status='created', Running=False, Pid=0)
    if 'role' in expected:
        expected['module'].verify(checked, name, expected['role'], expected['mounts'], expected['profile'])
    else:
        expected['module'].verify(checked, name, expected['mounts'])
    return identity
