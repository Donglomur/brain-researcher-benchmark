"""Exact inherited live-profile verifier and inert request capture with durable create hook."""
from types import SimpleNamespace
from files import HERE, json_read, captured_module
_guard = captured_module(json_read(HERE/'IMPORTS.json')['recovery_guard'], '_hierarchy_inherited_recovery_guard')
verify_live = _guard.verify_live


class RequestCaptured(Exception):
    pass


def capture_request(engine_class, method, args, profile=None):
    class Capture(engine_class):
        def own(self,kind,name,argv): self.captured=(kind,name,argv)
        def run(self,*unused,**kwargs): return SimpleNamespace(returncode=0,stdout=b'a'*64+b'\n',stderr=b'')
        def record_create_result(self,*unused): return 'a'*64
        def inspect(self,*unused): raise RequestCaptured()
    instance=object.__new__(Capture)
    if profile is not None: instance.profile=profile
    try:getattr(instance,method)(*args)
    except RequestCaptured:return instance.captured
    raise ValueError('Frozen constructor did not reach captured inspect')
