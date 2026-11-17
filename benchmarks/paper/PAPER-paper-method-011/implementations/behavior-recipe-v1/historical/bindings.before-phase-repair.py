"""Scientific meaning joins, beyond content hashes and output-name coverage."""
from . import catalog
from .validation import exact, need, ident, sha, integer, digest

PREDICTIVE = {'network_ground_truth','primary_behavior','hyperparameter_sensitivity',
              'factorial_ablations','threshold_crossings','averaged_training_control',
              'cycle_direction_generalization','small_training_sets','maze_simulations'}
NLB = {'bits_per_spike':('neural_state',['bits_per_spike']),
       'PSTH_R2':('psth',['mean_r2']), 'velocity_R2':('behavior',['groups','velocity'])}


def experiment(case):
    return {k:case[k] for k in ('module','dataset','method','repeat','factors','output_dimensions')}


def dimensions(dataset):
    data = next((d for d in catalog.scope()['datasets'] if d['id']==dataset), None)
    if data is None or not data['behavior']:
        return None
    return [f'{name}:{j}' for group in data['behavior']['groups'] for name,count in [group.rsplit(':',1)] for j in range(int(count))]


def validate_identity(case, item):
    exact(item, ('key','estimand','kind','selector','dimensions','source_support_sha256'), 'typed scientific output')
    need(item['key'] in case['outputs'], 'identity belongs to producer')
    sha(item['source_support_sha256'])
    need(type(item['selector']) is list and type(item['dimensions']) is list, 'exact metric/column joins')
    for dimension in item['dimensions']:
        need(dimension in case['output_dimensions'], 'output references actual declared dimension')
    key, module = item['key'], case['module']
    auxiliary=(module=='network_ground_truth' and item['estimand']=='network_geometry' and item['kind']=='geometry' and case['mode']=='analysis') or (module=='maze_simulations' and item['estimand']=='documentary_provenance' and item['kind']=='documentary' and case['mode']=='analysis')
    if module in PREDICTIVE and not auxiliary:
        need(item['estimand']=='behavior_R2' and item['kind']=='behavior', 'required prediction cannot become analysis answer')
        need(case['mode'] in ('behavior_causal','behavior_acausal'), 'actual held-out predictions required')
    if module=='primary_behavior':
        original=dimensions(case['dataset'])
        if case['method']=='Kalman_filter':original=[d for d in original if d.startswith(('position:','velocity:'))]
        need(case['output_dimensions']==original,'all original primary method-eligible behavior dimensions')
        need(item['selector']==[] and item['dimensions']==case['output_dimensions'], 'primary bundle retains all groups/dimensions')
    if module=='factorial_ablations':
        dataset,readout,interpolation,direction,column=key.split(':')
        need(case['dataset']==dataset and case['method']=='MINT' and case['repeat']==0, 'factorial dataset/method/repeat')
        need(case['factors']=={'readout':readout,'interpolation':interpolation,'direction':direction}, 'one genuine factorial configuration')
        original=dimensions(dataset)
        expected_dimensions=[d for d in original if not(dataset=='MC_Cycle' and readout=='linear' and d=='phase:0')]
        need(case['output_dimensions']==expected_dimensions,'all eligible factorial original variables')
        expected = original[int(column)]
        need(item['dimensions']==[expected] and item['selector']==['per_dimension_r2',case['output_dimensions'].index(expected)], 'factorial original variable to actual output column')
        need(case['mode']=='behavior_'+direction, 'factorial information mode')
    if module=='neuron_loss' and key in _loss_keys():
        count,repeat,regime,method,group=key.split(':')
        need(case['dataset']=='MC_Maze-L' and case['method']==method and case['repeat']==int(repeat), 'loss dataset/method/mask repetition')
        exact(case['factors'], ('neuron_count','regime','mask_sha256'), 'loss scientific factors')
        need(case['factors']['neuron_count']==int(count) and case['factors']['regime']==regime, 'one loss count/regime per prediction')
        sha(case['factors']['mask_sha256'])
        need(case['output_dimensions']==dimensions('MC_Maze-L'),'full position/velocity loss prediction bundle')
        expected=[group+':0',group+':1']
        need(case['mode']=='behavior_causal' and item['estimand']=='behavior_R2' and item['kind']=='behavior', 'loss requires causal predictions')
        need(item['dimensions']==expected and item['selector']==['groups',group], 'loss original behavior group')
    if module=='nlb_neural_state':
        dataset,endpoint=key.split(':')
        need(dataset==case['dataset'] and endpoint in NLB and case['mode']=='neural_acausal', 'authentic NLB rate endpoint')
        kind,selector=NLB[endpoint]
        need(item['kind']==kind and item['selector']==selector and item['estimand']=='nlb_'+endpoint, 'NLB endpoint cannot be relabeled')
    if module=='cycle_geometry':
        need(case['dataset']=='MC_Cycle' and case['mode']=='analysis', 'Cycle geometry source')
        need(item['estimand'] in ('cycle_joint_distribution','cycle_ordering','cycle_projection'), 'original Cycle geometry obligations')
        need(item['kind']==('documentary' if item['estimand']=='cycle_projection' else 'cycle_geometry'), 'original geometry is not optional Euclidean Pearson')
        if key=='cycle:projection':need(item['estimand']=='cycle_projection' and item['selector']==[],'projection evidence remains required independent review')
        else:
            _,quantity,axis=key.split(':');need(axis in ('muscle','kinematic','partition'),'Cycle comparison identity')
            need(item['estimand']==('cycle_joint_distribution' if quantity=='joint' else 'cycle_ordering') and item['selector']==(['histograms',axis] if quantity=='joint' else ['ordering',axis,'concordance']),'original joint distribution and ordering estimands')
    if item['estimand']=='behavior_R2' and module not in PREDICTIVE and module!='nlb_neural_state':
        need(item['kind']=='behavior' and case['mode']=='behavior_causal', 'behavioral held-out prediction obligation')
    if module=='threshold_crossings':
        need(case['dataset']=='MC_Cycle' and case['method']=='MINT' and case['output_dimensions']==dimensions('MC_Cycle'),'original13variable threshold comparison')
        exact(case['factors'],('spike_type','channel_membership_sha256'),'source spike representation')
        need(case['factors']['spike_type'] in ('sorted','threshold'),'original two spike representations');sha(case['factors']['channel_membership_sha256'])
    if item['kind']=='behavior' and module!='nlb_neural_state':
        need(item['estimand']=='behavior_R2', 'no analysis scalar substitutes behavior')


_loss_cache=None

def _loss_keys():
    global _loss_cache
    if _loss_cache is None:
        _loss_cache=set(catalog.loss_cells())
    return _loss_cache


def validate_case(case):
    need(type(case['factors']) is dict and type(case['output_dimensions']) is list and
         len(set(case['output_dimensions']))==len(case['output_dimensions']), 'typed factors and unique dimensions')
    for value in case['output_dimensions']:ident(value)
    need(type(case['output_identities']) is list and [x['key'] for x in case['output_identities']]==case['outputs'], 'all output identities in exact producer order')
    for item in case['output_identities']:validate_identity(case,item)
    need(type(case['uncertainty_requirements']) is list, 'required uncertainty identities')
    for requirement in case['uncertainty_requirements']:
        exact(requirement, ('id','target','kind','policy_sha256'), 'uncertainty requirement')
        ident(requirement['id']);sha(requirement['policy_sha256'])
        need(requirement['kind'] in ('historical_absolute_trial_bootstrap','prospective_paired_gain'), 'supported uncertainty estimand, no implicit gain fallback')
        need(requirement['target'] in case['outputs'], 'uncertainty tied to output')
    if case['module']=='hyperparameter_sensitivity':
        need(all(any(r['target']==key and r['kind']=='historical_absolute_trial_bootstrap' for r in case['uncertainty_requirements']) for key in case['outputs']), 'published absolute-R2 intervals required')
    if case['purpose']=='improve':
        need(all(any(r['target']==key and r['kind']=='prospective_paired_gain' for r in case['uncertainty_requirements']) for key in case['outputs'] if next(i for i in case['output_identities'] if i['key']==key)['kind']=='behavior'), 'confirmatory prediction gains require uncertainty')


def validate_recipe(case, recipe):
    need(recipe['experiment_sha256']==digest(experiment(case)), 'metric tied to actual experiment')
    need([r['key'] for r in recipe['outputs']]==case['outputs'], 'exact recipe support')
    for rule,item in zip(recipe['outputs'],case['output_identities']):
        validate_identity(case,item)
        need(rule['kind']==item['kind'] and rule['value_selector']==item['selector'], 'metric kind and selector are scientific identity')
        if rule['kind']=='behavior' and case['mode']!='neural_acausal':
            groups=rule['parameters']['groups']
            for name,columns in groups.items():
                need([case['output_dimensions'][j] for j in columns]==[d for d in case['output_dimensions'] if d.startswith(name+':')], 'source behavioral group maps exactly to produced columns')
            if item['selector'][:1]==['per_dimension_r2']:
                need(len(item['selector'])==2 and item['dimensions']==[case['output_dimensions'][item['selector'][1]]],'exact per-variable metric selector')
            if item['selector'][:1]==['groups']:
                group=item['selector'][1]
                need([case['output_dimensions'][j] for j in groups[group]]==item['dimensions'], 'group metric original dimensions')
    need(recipe['uncertainty_requirements']==case['uncertainty_requirements'], 'no omitted required uncertainty in recipe')


def validate_bundle(case,index,config,recipe=None):
    validate_case(case)
    identity=experiment(case)
    exact(config, ('experiment','program','factor_bindings'), 'scientifically bound program configuration')
    need(config['experiment']==identity and index['experiment']==identity, 'dataset/method/repeat/factors/dimensions joined to actual inputs/config')
    need(set(config['factor_bindings'])==set(case['factors']), 'all declared factors have trusted bindings')
    if case['module']=='neuron_loss':
        # These factors describe trusted input construction, not candidate knobs.
        need(config['factor_bindings']=={
            'neuron_count':['construction','selected_channels','length'],
            'mask_sha256':['construction','selected_channels','digest'],
            'regime':['experiment','factors','regime']},
            'loss factors bind private source construction, never public program fields')
    else:
        for key,path in config['factor_bindings'].items():
            need(type(path) is list and path, 'nonempty actual configuration field path')
            value=config['program']
            for component in path:value=value[component]
            need(value==case['factors'][key], 'factor value agrees with actual configuration')
    program=config['program'];route=program.get('reference_route')
    if route=='accepted_legacy_comparators':
        need(case['module']=='primary_behavior' and case['method']!='MINT','legacy source route only implements its stated primary comparator family')
        actual=program['legacy_case']
        need(actual['dataset']==case['dataset'] and actual['method']==case['method'] and actual['run_slot']==case['repeat'],'actual reference constructor dataset/method/repetition agrees with scientific identity')
    elif route=='native_mint_three_task_prefix':
        need(case['module']=='primary_behavior' and case['method']=='MINT' and case['repeat']==0 and case['dataset'] in ('Area2_Bump','MC_Maze','MC_RTT'),'native bridge cannot masquerade as an unimplemented variant')
        need(program['native_config']['dataset']==case['dataset'],'actual native loader dataset identity')
    else:
        need(route=='independently_bound_original_extension','no unbound implementation label')
        if case['module']!='neuron_loss':
            need(program['extension_config']['experiment']==identity,'unprovided original extension receives explicit scientific identity')
        binding=program['extension_source'];need(binding['path']=='original_extension.py','independently captured original extension');sha(binding['sha256'])
        need(binding['sha256']==case['source_recipe_sha256'],'source recipe is the actual selected extension implementation')
    construction=index['construction']
    exact(construction, ('source_recipe_sha256','experiment_sha256','selected_channels','raw_channel_count'), 'input construction witness')
    need(construction['source_recipe_sha256']==case['source_recipe_sha256'] and construction['experiment_sha256']==digest(identity), 'same selected source construction')
    if case['module']=='neuron_loss':
        channels=construction['selected_channels'];factors=case['factors']
        need(type(channels) is list and len(channels)==factors['neuron_count'] and len(set(channels))==len(channels), 'exact selected neuron mask support')
        need(construction['raw_channel_count']==162 and digest(channels)==factors['mask_sha256'], 'authentic original mask identity')
        for channel in channels:integer(channel,0,161)
        need(factors['regime'] in ('known','undetected'),'declared original information regime')
        exact(program,('reference_route','extension_source','extension_config'),'loss public executable allowlist')
        exact(program['extension_source'],('path','bytes','sha256'),'fixed complete original extension descriptor')
        integer(program['extension_source']['bytes'],1,262144)
        allowed={'method':case['method']}
        if factors['regime']=='known':
            allowed['adaptation']={'selected_channels':channels,'raw_channel_count':162}
        need(program['extension_config']==allowed,
             'public loss configuration contains only method and authorized known-loss adaptation')
        # Fixed public method settings live in the independently captured source.
        # Until that original extension is recovered, its native gate stays open.
        for stream in index['streams']:
            if stream['role'] in ('train','history','query'):
                expected=len(channels) if factors['regime']=='known' else 162
                need(stream['width']==expected, 'loss construction changes actual neural width as specified')
    if case['mode'].startswith('behavior'):
        need(index['output_schema']['width']==len(case['output_dimensions']) and index['output_schema']['target_columns']==list(range(len(case['output_dimensions']))), 'behavior truth/prediction original-column identity')
    if recipe is not None:validate_recipe(case,recipe)
