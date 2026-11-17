"""Fixed original Docker-control entry identity, retained process observer underneath."""
from pathlib import Path
from .domain import need
from .runtime.common import capture
from .runtime.process import ProcessRunner

class QualifiedRunner:
    def __init__(self,authority,journal,carrier):
        self.authority=authority;self.actual=ProcessRunner(authority.budget,journal,carrier);self.originals=self.actual.originals
    def run(self,ident,argv,deadline,cap,**kwargs):
        self.authority.validate_live();p=self.authority.root['native_profile'];path=Path(p['docker_binary'])
        need(argv[0]==str(path),'only selected original control executable')
        # The qualified host must enforce immutable executable/dependency mounts;
        # current full read verifies exact bytes before every original dispatch.
        capture(path.parent,dict(p['docker_binary_pin'],mode='0o755',role='qualified_original_docker_control_executable'),self.authority.budget,67108864)
        return self.actual.run(ident,argv,deadline,cap,**kwargs)
