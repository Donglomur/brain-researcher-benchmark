"""Full paper constructor over complete source/data descriptors, never samples."""
from dataclasses import dataclass
from .codec import descriptor, encode, pin, need


ARMS = ('paper_and_data','paper_data_official_code')
OBJECTIVES = ('reconstruction','fixed_quantity_improvement')
DATA_ROLES = (
 'banc_edges','banc_metadata','manuscript_annotations','seed_and_neck_maps',
 'fixed_an_dn_annotations','fixed_cns_annotations','fixed_effector_annotations',
 'source_function_evidence','fafb783_graph_metadata','manc121_graph_metadata',
 'external_match_and_nblast_support','anatomical_assets','synapse_evaluation_support',
 'regional_synapses','transmitter_neuron_split','transmitter_sampling',
 'transmitter_checkpoint_selection_history','transmitter_selected_model_identity',
 'transmitter_original_predictions','supplementary_data_1_to_10')


@dataclass(frozen=True)
class Job:
    id: str
    kind: str
    family: str
    dependencies: tuple
    output_ids: tuple
    source_members: tuple
    state: str
    reasons: tuple


@dataclass(frozen=True)
class Program:
    task_id: str
    arm: str
    objective: str
    annotation_profile: str
    operator_branch: str | None
    graph_variant: str
    source_catalogue_identity: tuple
    data: tuple
    missing_roles: tuple
    jobs: tuple
    gates: tuple
    selection_identity: str


FAMILY_SCRIPTS = {
 'D01':('panels_inventory.R','panels_neuroanatomy.R','panels_proofread_matching.R','panels_synapse_review.R','panels_annotation_hierarchy.R'),
 'D02':('panels_transmitter_predictions.R',),
 'D03':('panels_connectivity_comparison.R','panels_proofread_matching.R'),
 'D04':(), 'D05':('panels_influence_validation.R',),
 'D06':('panels_sensory_motor.R',), 'D07':('panels_pre_effector_influence.R',),
 'D08':('panels_betweenness_layers.R',),
 'D09':('panels_an_dn_umap.R','panels_neuroanatomy.R'),
 'D10':('panels_an_dn_influence.R','panels_efferent_umap.R','panels_body_parts.R','panels_cell_type_blowouts.R','panels_cluster_sensory_correlations.R','panels_bias.R'),
 'D11':('panels_an_dn_connectivity.R','panels_an_dn_polarity.R','panels_vignette_networks.R'),
 'D12':('panels_an_dn_influence.R',),
 'D13':('panels_cns_networks.R',),
 'D14':('panels_cns_network_analyses.R','panels_cns_network_diagram.R','panels_all_to_all_influence.R'),
 'D15':('panels_mbx_cx_control.R','panels_example_neuroanatomies.R'),
 'D16':(), 'D17':(), 'D00':()}


def construct(contracts, source_members, *, arm, objective, annotation_profile,
              data_descriptors, source_catalogue_identity, operator_branch=None,
              graph_variant='full_CNS_source/sequential_supplied_calculator'):
    need(arm in ARMS and objective in OBJECTIVES, 'closed information/objective condition')
    need(annotation_profile in ('frozen_GCS_generation1787336614757441',
                                'deposited_manuscript_snapshot'), 'explicit annotation namespace')
    branches = {x['id'] for x in contracts['NATIVE_BRANCH_MAP']['rows']}
    need(operator_branch is None or operator_branch in branches, 'explicit known native/specification branch')
    need(graph_variant in ('full_CNS_source/sequential_supplied_calculator',
                           'no_neck_CNS_source/sequential_supplied_calculator',
                           'full_CNS_source/parallel_rebuild_default_global',
                           'no_neck_CNS_source/parallel_rebuild_default_global'),
         'explicit full/no-neck and sequential/parallel execution mode')
    need(type(data_descriptors) is dict and set(data_descriptors) <= set(DATA_ROLES),
         'closed source-specific complete data roles')
    admitted=[]
    for role in DATA_ROLES:
        if role not in data_descriptors:
            continue
        rows=data_descriptors[role]
        need(type(rows) is list and rows, 'nonempty whole-role descriptor list')
        values=tuple((d['path'],d['bytes'],d['sha256']) for d in map(descriptor, rows))
        need(len({v[0] for v in values})==len(values), 'unique role file paths')
        admitted.append((role,values))
    missing=tuple(x for x in DATA_ROLES if x not in data_descriptors)
    jobs=[]
    families=contracts['WORKFLOW']['families']
    for family in families:
        fid=family['id']
        outputs=tuple(x['id'] for x in contracts['OBLIGATIONS']['rows'] if x['workflow_family']==fid)
        scripts=tuple('source/primary-source/R/figures/'+name for name in FAMILY_SCRIPTS[fid])
        need(all(s in source_members for s in scripts), 'required exact original producer source present')
        reasons=['Native/source/data/environment and panel-to-output parity remain unqualified']
        if fid=='D04' and operator_branch is None:
            reasons.append('No historical operator selected; seven branches remain explicit')
        if fid=='D02':
            reasons.append('Original model-selection-used testing result; no untouched final evaluation')
        jobs.append(Job(fid,'scientific_family',fid,tuple(family['dependencies']),outputs,
                        scripts,'requires_qualification',tuple(reasons)))
    for row in contracts['OBLIGATIONS']['rows']:
        jobs.append(Job('panel:'+row['id'],'panel_obligation',row['workflow_family'],
                        (row['workflow_family'],),(row['id'],),(),
                        'requires_complete_producer_product',('A header or cached plot is not a producer receipt',)))
    for row in contracts['WORKFLOW']['legacy_entries']:
        dep=row['mapped_family']
        jobs.append(Job('legacy:'+row['entry'],'legacy_obligation',dep,
                        () if dep=='NULL_PROVENANCE' else (dep,),(),(),
                        'required_unscorable' if dep=='NULL_PROVENANCE' else 'requires_source_bound_inputs',
                        ('Original randomized-graph method not located',) if dep=='NULL_PROVENANCE' else ()))
    jobs.append(Job('NULL_PROVENANCE','required_original_method','G09',(),(),(),
                    'required_unscorable',('No randomized-graph producer located; no replacement null',)))
    need(len(jobs)==139 and len({j.id for j in jobs})==139, 'full139-job accounting,not139 benchmarks')
    selection={'task_id':'PAPER-FIND-NEW-003','arm':arm,'objective':objective,
               'annotation_profile':annotation_profile,'operator_branch':operator_branch,
               'graph_variant':graph_variant,'data':admitted,'missing_roles':missing,
               'jobs':[j.__dict__ for j in jobs],'source_catalogue_identity':source_catalogue_identity}
    return Program(selection['task_id'],arm,objective,annotation_profile,operator_branch,graph_variant,
                   tuple(sorted(source_catalogue_identity.items())),tuple(admitted),missing,tuple(jobs),
                   tuple((g['id'],g['status']) for g in contracts['GATES']['gates']),pin(encode(selection))['sha256'])


def manifest(program):
    return {**program.__dict__,'jobs':[j.__dict__ for j in program.jobs],
            'counts':{'canonical_tasks':1,'panels':96,'families':18,'legacy_entries':24,
                      'source_accounting_jobs':139,'open_scientific_gates':16},
            'scientific_qualification':False,'data_bodies_read_by_constructor':False,
            'counterfactual_or_predictive_branch_selected':False}
