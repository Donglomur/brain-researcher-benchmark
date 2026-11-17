"""Original two-program host caller. Never constructs a qualification issuer.

This owner only joins externally selected operands to the existing signed-root
Authority and complete Campaign. It does not turn command-line metadata into
scientific, native, source or target authority.
"""
import argparse
from pathlib import Path
from .domain import need, fields, pin, digest, parse, encoded, sha
from .runtime.common import FailureCarrier
from .runtime.budget import Budget
from .runtime.journal import Journal
from .admission import Authority
from .campaign import Campaign
from .cli import original_file, selected_limits, enforce_host
from .storage import read

REQUIRED_SOURCE = ('capture_entry.py', 'neural057/__init__.py', 'neural057/admission.py', 'neural057/campaign.py', 'neural057/cli.py', 'neural057/domain.py', 'neural057/execution.py', 'neural057/features.py', 'neural057/learning.py', 'neural057/operator.py', 'neural057/preparation.py', 'neural057/reference_cli.py', 'neural057/runtime/__init__.py', 'neural057/runtime/budget.py', 'neural057/runtime/cgroup.py', 'neural057/runtime/common.py', 'neural057/runtime/journal.py', 'neural057/runtime/native.py', 'neural057/runtime/native_providers.py', 'neural057/runtime/process.py', 'neural057/runtime/resource_policy.py', 'neural057/scoring.py', 'neural057/splits.py', 'neural057/storage.py', 'neural057/taxonomy.py', 'operator_entry.py', 'phase_entry.py', 'reference_entry.py', 'run.py')
BOOTSTRAP = dict(wall_seconds=120,cpu_seconds=120,read_bytes=33554432,
                 write_bytes=1048576,live_bytes=1048576,files=16,
                 model_calls=1,stream_bytes=1048576)

class ClosedParser(argparse.ArgumentParser):
    def error(self, message):
        # Raw argument text is retained on the owner, not formatted as a failure.
        raise ValueError('invalid closed N057 two-program operator arguments')

def arguments(argv):
    need(type(argv) is tuple and all(type(x) is str for x in argv),'original argument tokens')
    ap=ClosedParser(add_help=False,allow_abbrev=False)
    names=('root','root-sha256','qualification','qualification-sha256',
           'issuer-public-key','issuer-public-key-sha256','fixed-program',
           'fixed-program-sha256','investigation-program',
           'investigation-program-sha256','output')
    need(len(argv)==2*len(names),'one value for every required operand')
    need(set(argv[::2])=={'--'+n for n in names},'no duplicate, omitted or unknown operand')
    for n in names:ap.add_argument('--'+n,required=True)
    a=ap.parse_args(argv)
    for n in ('root','qualification','issuer_public_key','fixed_program','investigation_program','output'):
        s=getattr(a,n);p=Path(s)
        need(p.is_absolute() and str(p)==s and '..' not in p.parts and '\x00' not in s,
             'literal absolute operator path, no rewriting')
    for n in ('root_sha256','qualification_sha256','issuer_public_key_sha256',
              'fixed_program_sha256','investigation_program_sha256'):digest(getattr(a,n))
    return a

def programme_selection(a,root):
    fields(root['programmes'],('F','I'))
    actual=Path(__file__).absolute().parents[1]
    need(root['source_root']==str(actual),'signed source root is this actual fixed entry tree')
    rows=root['source_members'];need(type(rows) is list,'original complete source member list')
    for row in rows:pin(row)
    need(len(rows)==len(REQUIRED_SOURCE) and sorted(r['path'] for r in rows)==list(REQUIRED_SOURCE),
         'whole 27 inherited plus two operator source roles; no reduced or extra source tree')
    asset=Path(root['asset_root'])
    need(asset.is_absolute() and str(asset)==root['asset_root'] and '..' not in asset.parts,
         'literal selected asset root')
    out={}
    for mode,path,digest_ in [('F',a.fixed_program,a.fixed_program_sha256),
                              ('I',a.investigation_program,a.investigation_program_sha256)]:
        d=root['programmes'][mode];fields(d,('source','policy'));pin(d['source'])
        need(path==str(asset/d['source']['path']) and digest_==d['source']['sha256'],
             'each explicit programme operand is its exact signed-root source')
        out[mode]=dict(d['source'])
    return out

class OperatorOwner:
    """Retain the original lifetime, partial owners and raw first failure."""
    def __init__(self,origin,cpu_origin,argv):
        self.origin=origin;self.cpu_origin=cpu_origin;self.argv=tuple(argv)
        self.carrier=FailureCarrier();self.carrier.retain(self)
        self.started=False;self.finished=False;self.stage='created';self.args=None
        self.budget=None;self.journal=None;self.journal_ready=False
        self.root_bytes=None;self.root=None;self.qualification=None;self.key=None
        self.selection=None;self.programmes={};self.authority=None;self.campaign=None
        self.report=None;self.terminal_return=None;self.exit_status=2

    def run(self):
        need(not self.started,'one original operator attempt; no retry/reset')
        self.started=True
        try:
            self.stage='budget'
            self.budget=Budget.__new__(Budget);self.carrier.retain(self.budget)
            Budget.__init__(self.budget,self.origin,BOOTSTRAP,cpu_origin=self.cpu_origin)
            self.stage='arguments';self.args=arguments(self.argv);a=self.args;b=self.budget
            self.stage='root'
            self.root_bytes=original_file(a.root,a.root_sha256,b,16777216)
            self.root=parse(self.root_bytes);root=self.root
            limits=selected_limits(root['limits']);selected_limits(root['cell_limits'])
            b.limits=limits;b.global_limits=dict(limits);b.deadline=self.origin+limits['wall_seconds']
            b.check('two-program root includes original bootstrap and imports')
            self.stage='journal'
            self.journal=Journal.__new__(Journal);self.carrier.retain(self.journal)
            Journal.__init__(self.journal,Path(a.output),b,self.carrier);self.journal_ready=True
            self.stage='programme-selection';self.selection=programme_selection(a,root)
            self.stage='qualification-and-key'
            self.qualification=original_file(a.qualification,a.qualification_sha256,b,1048576)
            self.key=original_file(a.issuer_public_key,a.issuer_public_key_sha256,b,32)
            # Both original committed bodies are captured before any preparation,
            # native participant phase or target access. Same actual Budget.
            for mode in ('F','I'):
                self.stage='capture-'+mode
                self.programmes[mode]=read(root['asset_root'],self.selection[mode],b,131072)
            self.stage='authority'
            self.authority=Authority.__new__(Authority);self.carrier.retain(self.authority)
            Authority.__init__(self.authority,self.root_bytes,a.root_sha256,self.qualification,self.key,b)
            need(self.authority.budget is b,'same original signed-root owner budget')
            for mode in ('F','I'):
                need(self.authority.programmes[mode]==self.programmes[mode],
                     'actual Authority recapture equals original committed programme bytes')
            self.authority.retain(self)
            self.stage='host-containment';enforce_host(root,b)
            self.stage='campaign-construction'
            self.campaign=Campaign.__new__(Campaign);self.carrier.retain(self.campaign)
            Campaign.__init__(self.campaign,self.authority,self.journal)
            self.stage='complete-campaign'
            # No requested cell/mode/panel subset and no direct scorer entry.
            self.report=self.campaign.run()
        except BaseException as exc:
            self.carrier.fail(exc,'operator:'+self.stage)
        finally:
            if self.journal_ready:
                try:
                    self.stage='terminal'
                    self.terminal_return=self.journal.complete_terminal(self.report)
                except BaseException as exc:
                    self.carrier.fail(exc,'operator:terminal-return')
                    self.carrier.durable=False
            self.finished=True
        self.exit_status=0 if (self.report is not None and self.carrier.first is None
                               and self.carrier.durable and self.terminal_return is True) else 2
        return self

def launch(origin,cpu_origin,argv):
    owner=OperatorOwner(origin,cpu_origin,argv)
    owner.run()
    return owner
