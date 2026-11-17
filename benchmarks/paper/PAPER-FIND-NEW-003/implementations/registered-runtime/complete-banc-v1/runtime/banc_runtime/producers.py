"""Closed source-bound producers; missing original methods remain missing.

The complete family graph is constructed here. No callable supplied by a user
can stand in for a native producer. Original figure scripts are concrete
producers retained in full, but their entire source/data/runtime context and
raw-to-derived lineage must be qualified before they may be run.
"""
import importlib
import importlib.abc
import importlib.util
import sys
from .codec import need
from .construct import FAMILY_SCRIPTS


FAMILY_KERNELS={
 'D00':('codec.capture',),
 'D01':('native_R.banc_original_figure',),
 'D02':('native_R.banc_original_figure',),
 'D03':('native_R.banc_original_figure',),
 'D04':('execution.prepare_native_request','execution.native_r_job','r_bridge.serialize_native_r_job','native_R_bridge.banc_run_influence_wire','native_python.run_python_literal','native_R.banc_native_influence','native_R.banc_native_statistics'),
 'D05':('native_R.banc_original_figure',),
 'D06':('influence.sensory_sweeps','native_python.run_python_literal','native_R.banc_native_sensory','native_R_bridge.banc_run_sensory_wires','native_R.banc_native_statistics','influence.full_panel','influence.collect_three_panels'),
 'D07':('legacy.an_dn.effector_upstream','native_R.banc_original_figure'),
 'D08':('banc_graph_core.banc_graph.run_centrality','native_R.banc_original_figure'),
 'D09':('native_R.banc_original_figure',),
 'D10':('legacy.program.an_dn_influence_program','native_R.banc_original_figure'),
 'D11':('legacy.an_dn.an_dn_direct','legacy.program.reciprocity_program','native_R.banc_original_figure'),
 'D12':('native_R.banc_original_figure','native_R.banc_native_statistics'),
 'D13':('legacy.community.run_python_reference','legacy.community_R.banc_community_R','native_R.banc_original_figure'),
 'D14':('legacy.cns_panels.run_all_panels','legacy.consumers.partner_distribution','legacy.consumers.out_of_network','legacy.nulls.source_binomial_summary','native_R.banc_original_figure'),
 'D15':('native_R.banc_original_figure',),
 'D16':('native_R.banc_native_statistics','native_R.banc_original_figure','render.heatmap_svg'),
 'D17':('collect.capture_bundle','collect.compare_sealed','metrics.fixed_quantity_comparison'),
}


def complete_pipeline(program, contracts, source_members):
    """Construct every full source job and unresolved gate without opening data."""
    families=[]
    for f in contracts['WORKFLOW']['families']:
        scripts=tuple('source/primary-source/R/figures/'+x for x in FAMILY_SCRIPTS[f['id']])
        need(all(x in source_members for x in scripts), 'complete captured family source')
        families.append({'id':f['id'],'dependencies':f['dependencies'],
          'concrete_kernel_bindings':FAMILY_KERNELS[f['id']],
          'original_script_members':[source_members[x] for x in scripts],
          'panel_ids':[r['id'] for r in contracts['OBLIGATIONS']['rows'] if r['workflow_family']==f['id']],
          'state':'source_defined_authentic_native_reference_unqualified',
          'source_context_qualification':False,'original_remaining_gate':f['remaining_gate']})
    return {'program_identity':program.selection_identity,'families':families,
            'legacy_entries':contracts['WORKFLOW']['legacy_entries'],
            'graph_null':{'state':'required_unscorable','reason':'exact original randomized graph producer unlocated'},
            'sensory_scope':{'shape':[3,17,19],'primary_threshold':5,'extension_thresholds':[3,10],
                            'matched_shape':[14,14],'GCS_to_enriched_graph_profile_equivalence':False},
            'native_branches':contracts['NATIVE_BRANCH_MAP']['rows'],
            'gates':contracts['GATES']['gates'],
            'no_successful_original_script_invocation_claimed':True,
            'counts_are_obligations_not_new_benchmarks':True}


class _CapturedLegacy(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Load only captured bytes under one private namespace, not ambient code."""
    prefix='_banc_full_captured_legacy'
    def __init__(self,captured,root):
        self.captured=captured;self.root=root
    def _member(self,fullname):
        if fullname!=self.prefix and not fullname.startswith(self.prefix+'.'): return None
        tail=fullname[len(self.prefix):].lstrip('.').replace('.','/')
        return 'legacy/banc_composition/'+(tail+'.py' if tail else '__init__.py')
    def find_spec(self,fullname,path=None,target=None):
        member=self._member(fullname)
        if member not in self.captured:return None
        return importlib.util.spec_from_loader(fullname,self,is_package=fullname==self.prefix)
    def create_module(self,spec):return None
    def exec_module(self,module):
        member=self._member(module.__name__)
        module.__file__=str(self.root/member)
        if module.__name__==self.prefix:module.__path__=[str(self.root/'legacy/banc_composition')]
        exec(compile(self.captured[member],module.__file__,'exec'),module.__dict__)


def load_legacy(captured,root):
    """One authenticated snapshot per process; no native component imported."""
    prefix=_CapturedLegacy.prefix
    need(prefix not in sys.modules,'legacy snapshot already owned; reuse returned package')
    loader=_CapturedLegacy(captured,root)
    sys.meta_path.insert(0,loader)
    try:
        package=importlib.import_module(prefix)
        # Import remaining pure wrappers while the captured-only finder owns
        # this namespace. Native affinity/community import is not selected.
        for name in ('an_dn','cns_panels','nulls'):
            importlib.import_module(prefix+'.'+name)
    except BaseException:
        for name in tuple(sys.modules):
            if name==prefix or name.startswith(prefix+'.'):sys.modules.pop(name,None)
        raise
    finally:sys.meta_path.remove(loader)
    return package


def run_pure_legacy(package, endpoint, arguments, meter):
    """Only concrete pre-existing full-population consumers, never callbacks."""
    need(type(arguments) is dict and not any(callable(x) for x in arguments.values()), 'no producer callbacks')
    program=sys.modules[package.__name__+'.program']
    an=sys.modules[package.__name__+'.an_dn']
    cns=sys.modules[package.__name__+'.cns_panels']
    nulls=sys.modules[package.__name__+'.nulls']
    consumers=sys.modules[package.__name__+'.consumers']
    methods={'an_dn_direct':an.an_dn_direct,'an_dn_supercluster':an.an_dn_supercluster_direct,
             'an_dn_effector_upstream':an.effector_upstream,
             'an_dn_reciprocity':program.reciprocity_program,
             'an_dn_influence':program.an_dn_influence_program,
             'influence_normalization':program.normalized_influence_program,
             'cns_partner_distribution':consumers.partner_distribution,
             'cns_out_of_network':consumers.out_of_network,
             'cns_influence_panel_sweeps':cns.run_all_panels,
             'source_binomial_null':nulls.source_binomial_summary}
    need(endpoint in methods,'endpoint requires a different concrete native/graph producer or remains unlocated')
    meter.start_job()
    value=methods[endpoint](**arguments)
    meter.check_deadline('after_pure_legacy')
    return {'endpoint':endpoint,'value':value,'state':'computed_unqualified',
            'native_parity_qualified':False,'scientific_qualification':False}


def randomized_graph_null():
    raise RuntimeError('required_unscorable: original randomized graph ensemble producer not located; no alternative null substituted')
