"""Full C4 producer graph, paired-source obligations and actual science calls.

Public execution remains disabled until genuine source/native/target issuers
exist. Internal methods are concrete scientific functions, not callbacks passed
off as executed reference or evaluator authority.
"""
from c4_distribution.import_guard import require_bound_source as _c4_require_source
from dataclasses import dataclass
from .cohort import Population, SupportError
from .profiles import MethodGap
from .preparation import load_raw_unit,prepare_unit
from .pretraining import train_vae
from .classification import fit_loo,predict_transfer
from .evaluation import Prediction,loo_prediction,probability_products

@dataclass(frozen=True)
class Obligation:
    name: str
    panels: tuple
    populations: tuple
    producer: str
    prerequisite: tuple

OBLIGATIONS=(
 Obligation('acquisition_and_support',('F1',),('all_recordings','all_source_files'),
            'census.build_census',('complete_annotations','independent_label_and_layer_provenance','full_published_cohort_binding')),
 Obligation('quality_and_layer',tuple('F2'+x for x in 'ABCDEFGHIJ'),('all_recordings',),
            'source_qc_layer_products',('continuous_voltage','amplitudes','histology_tracks','phyllum_coordinates')),
 Obligation('optogenetic_blockade',tuple('F3'+x for x in 'ABCDEFG'),('ground_truth_candidates',),
            'source_optotag_products',('photostim_events','blockade_windows','unit_waveform_identity','original_spatial_selection')),
 Obligation('ground_truth_library',tuple('F4'+x for x in 'ABCDEFGH'),('mouse_ground_truth','granule_descriptive'),
            'prepared_features_and_curation',('complete_curation_dispositions','original_label_provenance')),
 Obligation('vae_pretraining',('F5A','S5'),('mouse_unlabelled_pretrain',),
            'pretraining.train_vae',('unlabelled_3090_bindings','complete_explicit_recipe','historical_notebook_identity')),
 Obligation('unit_loo',tuple('F5'+x for x in 'BCDE'),('mouse_ground_truth',),
            'classification.fit_loo/evaluation.loo_prediction',('202_ground_truth_bindings','pretrained_encoder_capture','seed_schedule')),
 Obligation('no_layer_ablation',('S6',),('mouse_ground_truth',),
            'classification.fit_loo(use_layer=False)',('matched_seed_schedule','same_full_cohort')),
 Obligation('all_photoactivated_ablation',('F5F',),('mouse_all_photoactivated',),
            'classification.fit_loo',('complete_alternative_cohort','unconfirmed_blockade_label_semantics')),
 Obligation('external_transfer',tuple('F6'+x for x in 'ABCDEF'),('mouse_expert_medina','monkey_expert_lisberger'),
            'classification.predict_transfer',('complete_2020_models','complete_external_unit_identity','expert_target_provenance','paired_Purkinje_truth')),
 Obligation('latent_congruence',('F6G','S7'),('mouse_ground_truth','mouse_expert_medina','monkey_expert_lisberger'),
            'evaluation.feature_cosine',('same_encoder_identity','latent_row_order')),
 Obligation('behaviour',tuple('F7'+x for x in 'ABCDEF'),('behaviour_hull','behaviour_medina','behaviour_hausser','behaviour_lisberger'),
            'behaviour.trial_rates/normalized_responses/dynamics_comparisons',('trial_clock','all_four_task_rosters','source_soft_normalization','components_and_fraction_grid')),
 Obligation('supplementary_support',('S1','S2','S3','S4','S5','S6','S7'),('full_paper_support',),
            'explicit_supplementary_dispositions',('supplementary_panel_definitions','in_vitro_source','full_source_table_definitions')),
)

class ScientificDriver:
    """Internal full support producer. No run admission is implied by constructing it."""
    def __init__(self,cohort,source_paths,outputs,source_identity):
        _c4_require_source()
        cohort.validate()
        if set(source_paths)!=set(cohort.source_roles):raise SupportError('exact five-source mapping required')
        if not source_identity:raise SupportError('frozen scientific source identity required')
        self.cohort=cohort;self.paths=dict(source_paths);self.outputs=outputs;self.source_identity=source_identity
        self.raw_units={};self.prepared={};self.vaes={};self.ensembles={};self.predictions={};self.captures={};self.events=[];self.raw_failures=[]
        self.target_blind_tables={};self.grouped_results={};self.group_plans={}

    def prepare_population(self,population,*,external_quality_policy,single_channel_policy):
        if population in self.prepared:raise SupportError('population already prepared')
        members=self.cohort.eligible(population);out=[];raw_rows=[]
        for member in members:
            try:
                raw=load_raw_unit(self.paths[member.source_role],member,external_quality_policy=external_quality_policy)
                out.append(prepare_unit(raw,spike_clock_policy='literal_source_clock',single_channel_policy=single_channel_policy))
                raw_rows.append(raw)
            except BaseException as error:
                self.raw_failures.append(error);self.events.append({'stage':'prepare','unit':member.key,'status':'failed','error_type':type(error).__name__})
                raise
        self.prepared[population]=tuple(out)
        self.raw_units[population]=tuple(raw_rows)
        self.events.append({'stage':'prepare','population':population.value,'units':len(out),'status':'returned'})
        return self.prepared[population]

    def pretrain(self,recipe,*,device):
        p=Population.MOUSE_UNLABELLED_PRETRAIN
        if p not in self.prepared:raise SupportError('pretraining source producer has not returned')
        model=train_vae(self.cohort,self.prepared[p],recipe,device=device)
        captures={'encoder':self.outputs.state_dict('vae-'+recipe.modality+'-encoder',model.encoder.state_dict()),
                  'decoder':self.outputs.state_dict('vae-'+recipe.modality+'-decoder',model.decoder.state_dict())}
        self.outputs.json('vae-'+recipe.modality+'-history.json',model.history)
        self.vaes[recipe.modality]=model;self.captures['vae-'+recipe.modality]=captures
        return captures

    def classify(self,variant,targets,*,profile,use_layer,augment_waveform,augment_spikes,freeze_heads,device,source_seed,
                 population=Population.MOUSE_GROUND_TRUTH):
        _c4_require_source()
        if variant in self.ensembles:raise SupportError('variant already trained')
        p=population
        if p not in self.prepared or set(self.vaes)!= {'waveform','acg'}:raise SupportError('complete raw/pretraining producer chain missing')
        ensemble=fit_loo(self.cohort,self.prepared[p],targets,self.vaes['waveform'],self.vaes['acg'],
            profile=profile,use_layer=use_layer,augment_waveform=augment_waveform,
            augment_spikes=augment_spikes,freeze_heads=freeze_heads,device=device,
            source_seed=source_seed,dataloader_workers=4,population=population)
        prediction,raw=loo_prediction(ensemble,self.source_identity)
        from .captured_prediction import capture_probabilities
        capture=capture_probabilities(self.outputs,variant+'-loo',raw,ensemble.unit_order,
                                     prediction.classes,self.source_identity,prediction.model_identity,
                                     member_support=prediction.member_support)
        # Complete actual model/Hessian/precision capture precedes transfer.
        # Unsupported provider state refuses; no cached or opaque pickle stand-in.
        _c4_require_source()
        from npyx.c4.run_deep_classifier import get_kronecker_hessian_attributes
        import torch
        model_captures=[]
        for ordinal,model in enumerate(ensemble.fitted):
            prefix=f'{variant}-model-{ordinal:04d}'
            parameters=self.outputs.state_dict(prefix,model.model.state_dict())
            hessian=model.calibrated.H
            if not isinstance(hessian,torch.Tensor):hessian=get_kronecker_hessian_attributes(hessian)[0]
            calibration=self.outputs.tensor_tree(prefix+'-calibration',{
                'H':hessian,'prior_precision':model.calibrated.prior_precision,
                'mean':model.calibrated.mean,'n_data':model.calibrated.n_data,
                'loss':model.calibrated.loss})
            self.outputs.json(prefix+'-training.json',{'repeat':model.repeat,'held':model.held,
                'training':model.training,'history':model.history})
            self.outputs.array(prefix+'-oversample-rows.npy',model.oversample_rows)
            self.outputs.tensor_tree(prefix+'-rng',{'before':model.rng_before,'after':model.rng_after})
            model_captures.append({'repeat':model.repeat,'held':model.held,'parameters':parameters,'calibration':calibration})
        ensemble_capture=self.outputs.json(variant+'-complete-ensemble.json',model_captures)
        self.ensembles[variant]=ensemble;self.predictions[(variant,p)]=prediction
        self.captures[(variant,p)]=capture
        self.captures[(variant,'ensemble')]=ensemble_capture
        return capture

    def transfer(self,variant,population,*,use_layer):
        if variant not in self.ensembles or population not in self.prepared or (variant,'ensemble') not in self.captures:
            raise SupportError('transfer parent producer/capture missing')
        result=predict_transfer(self.ensembles[variant],self.cohort,self.prepared[population],population,use_layer=use_layer)
        from .captured_prediction import capture_probabilities
        capture=capture_probabilities(self.outputs,variant+'-'+population.value,result['raw_probabilities'],
            result['units'],result['classes'],self.source_identity,result['models'])
        self.predictions[(variant,population)]=Prediction(result['units'],result['classes'],result['mean_probabilities'],self.source_identity,result['models'])
        self.captures[(variant,population)]=capture
        return capture

    def score_captured(self,variant,population,protected_targets,thresholds,*,threshold_rule):
        from .evaluation import capture_score_products
        key=(variant,population)
        if key not in self.captures:raise SupportError('target access before immutable prediction capture prohibited')
        from .captured_prediction import read_prediction
        expected=tuple(m.key for m in self.cohort.eligible(population))
        prediction=read_prediction(self.outputs,self.captures[key],expected,self.source_identity)
        products=probability_products(prediction,expected,
                                      protected_targets,thresholds,threshold_rule=threshold_rule)
        return capture_score_products(self.outputs,variant+'-'+population.value+'-'+threshold_rule,products)

    def target_blind_features(self,population,qc_bindings,recipe,*,external_quality_policy):
        from .target_blind_features import extract_target_blind,admit_feature_bindings
        if population in self.target_blind_tables:raise SupportError('target-blind feature population already produced')
        members=self.cohort.eligible(population)
        admit_feature_bindings(tuple(m.key for m in members),qc_bindings,recipe)
        raw=[]
        try:
            for member in members:
                raw.append(load_raw_unit(self.paths[member.source_role],member,external_quality_policy=external_quality_policy))
            table,failures=extract_target_blind(tuple(raw),qc_bindings,recipe)
        except BaseException as error:
            self.raw_failures.append(error)
            self.events.append({'stage':'target_blind_features','status':'failed','returned_raw_units':tuple(r.key for r in raw)})
            raise
        self.raw_failures.extend(error for _,error in failures)
        self.target_blind_tables[population]=table
        # Dispositions are published before require_complete can refuse a fit.
        self.outputs.json('target-blind-'+population.value+'-feature-dispositions.json',{
            'recipe':recipe,'names':table.names,'rows':tuple({'unit':r.unit,'disposition':r.disposition,
                'reason':r.reason,'qc_binding':r.qc_binding} for r in table.rows)})
        self.events.append({'stage':'target_blind_features','status':'returned_with_full_dispositions','population':population.value})
        return table

    def grouped_target_blind_reference(self,population,plan,recipe,training_targets_by_outer):
        from .grouped_reference import fit_grouped
        from .captured_prediction import capture_probabilities
        from .evaluation import capture_score_products
        from .cohort import CLASSES
        expected=tuple(m.key for m in self.cohort.eligible(population))
        if plan.unit_order!=expected or population not in self.target_blind_tables:
            raise SupportError('complete target-blind population producer/group support required')
        if population in self.grouped_results:raise SupportError('grouped population already fitted')
        table=self.target_blind_tables[population];table.require_complete(expected)
        result=fit_grouped(table,plan,recipe,training_targets_by_outer)
        self.grouped_results[population]=result;self.group_plans[population]=plan
        import numpy as np
        prefix='target-blind-'+population.value
        self.outputs.array(prefix+'-features.npy',np.stack([r.values for r in table.rows]))
        self.outputs.json(prefix+'-groups.json',{'units':expected,
            'group_by_unit':tuple((k,plan.group_by_unit[k]) for k in expected),
            'outer_by_group':plan.outer_by_group,'inner_by_outer':plan.inner_by_outer,'provenance':plan.provenance})
        self.outputs.json(prefix+'-recipe.json',recipe)
        capture_score_products(self.outputs,prefix+'-tuning',{'tuning':result.tuning,'selections':result.selections})
        # All fitted objects remain owned by result. Actual scaler, sampling,
        # training/evaluation identities and probabilities are captured for
        # every grid fit; full native estimator-state deployment is still gated.
        for ordinal,fit in enumerate(result.fitted):
            p=prefix+f'-fit-{ordinal:06d}'
            self.outputs.json(p+'-identity.json',{'job':fit.job,'resampled_units':fit.resampled_units})
            self.outputs.array(p+'-scaler-mean.npy',fit.scaler.mean_)
            self.outputs.array(p+'-scaler-scale.npy',fit.scaler.scale_)
            self.outputs.array(p+'-sample-indices.npy',fit.oversampler.sample_indices_)
            self.outputs.array(p+'-predictions.npy',fit.probabilities)
        manifest=self.outputs.json(prefix+'-model-support.json',{'jobs':tuple(f.job for f in result.fitted),
            'units':expected,'status':'actual fitted objects retained; native estimator-state serialization unqualified'})
        for family,probabilities in result.probabilities.items():
            variant='target-blind-'+family
            capture=capture_probabilities(self.outputs,variant+'-'+population.value,probabilities[:,:,None],
                expected,CLASSES,self.source_identity,(('cross_fitted_group_reference',manifest.sha256),))
            self.captures[(variant,population)]=capture
        self.events.append({'stage':'grouped_target_blind_reference','population':population.value,'status':'captured_unqualified'})
        return result

    def score_grouped_target_blind(self,family,population,protected_targets):
        from .captured_prediction import read_prediction
        from .grouped_reference import captured_group_scores
        from .evaluation import capture_score_products
        variant='target-blind-'+family;key=(variant,population)
        if key not in self.captures or population not in self.group_plans:
            raise SupportError('complete captured grouped prediction missing before targets')
        expected=tuple(m.key for m in self.cohort.eligible(population))
        prediction=read_prediction(self.outputs,self.captures[key],expected,self.source_identity)
        products=captured_group_scores(prediction,expected,protected_targets,self.group_plans[population])
        return capture_score_products(self.outputs,variant+'-'+population.value+'-grouped',products)

    def literal_engineered_baselines(self,protected_labels,*,recipes,model_names,source_seed):
        from .baselines import literal_features,fit_baselines
        import numpy as np
        populations=(Population.MOUSE_GROUND_TRUTH,Population.MOUSE_EXPERT,Population.MONKEY_EXPERT)
        if any(p not in protected_labels or p not in recipes for p in populations):
            raise SupportError('complete baseline source/target populations missing')
        features={}
        for population in populations:
            members=self.cohort.eligible(population);parts=[]
            for role in dict.fromkeys(m.source_role for m in members):
                selected=tuple(m for m in members if m.source_role==role)
                recipe=recipes[population][role]
                part=literal_features(self.paths[role],selected,**recipe)
                if any(part['labels'][k]!=protected_labels[population][k] for k in part['units']):
                    raise SupportError('literal preprocessing label differs from protected reproduction label')
                parts.append(part)
            units=tuple(k for p in parts for k in p['units'])
            if units!=tuple(m.key for m in members):raise SupportError('source grouping changed original unit order')
            if any(p['names']!=parts[0]['names'] for p in parts):raise SupportError('feature schema mismatch')
            features[population]={'units':units,'names':parts[0]['names'],'matrix':np.concatenate([p['matrix'] for p in parts])}
        train=features[Population.MOUSE_GROUND_TRUTH]
        external={p:(features[p]['units'],features[p]['matrix'],protected_labels[p]) for p in populations[1:]}
        result=fit_baselines(self.cohort,train['matrix'],train['names'],train['units'],
            protected_labels[Population.MOUSE_GROUND_TRUTH],external,model_names=model_names,source_seed=source_seed)
        for name,row in result.items():
            self.outputs.array(name+'-baseline-loo-probabilities.npy',row['loo']['predicted_probability'])
            for pop,transfer in row['transfers'].items():
                self.outputs.array(name+'-baseline-'+pop+'-probabilities.npy',transfer['predicted_probability'])
        self.events.append({'stage':'engineered_baselines','status':'returned',
                            'scope':'label_conditioned_literal_reproduction_only'})
        return result

    def behavioural_products(self,variant,population,behaviour_inputs,recipe,denominators):
        from .behaviour import trial_rates,normalized_responses,dynamics_comparisons
        import numpy as np
        if (variant,population) not in self.captures:raise SupportError('classifier capture must precede behavior selection')
        from .captured_prediction import read_prediction
        prediction=read_prediction(self.outputs,self.captures[(variant,population)],
            tuple(m.key for m in self.cohort.eligible(population)),self.source_identity)
        if tuple(behaviour_inputs)!=prediction.units:raise SupportError('complete behavior/unit identity/order mismatch')
        p=prediction.probabilities;order=np.sort(p,axis=1)
        ratio=np.divide(order[:,-1],order[:,-2],out=np.full(len(p),np.inf),where=order[:,-2]!=0)
        keep=ratio>2;classes=np.asarray(prediction.classes)[p.argmax(axis=1)]
        selected=[k for k,ok,c in zip(prediction.units,keep,classes) if ok and c!='PkC_cs']
        records=[trial_rates(behaviour_inputs[k]['spike_seconds'],behaviour_inputs[k]['trials'],recipe) for k in selected]
        responses,normalization=normalized_responses(records,recipe)
        if denominators is None:raise MethodGap('original Fig7 soft-normalization producer is unresolved')
        if set(denominators)!=set(selected):raise SupportError('normalization/unit join mismatch')
        labels=[c for c,ok in zip(classes,keep) if ok and c!='PkC_cs']
        result=dynamics_comparisons(responses,labels,selected,recipe,np.asarray([denominators[k] for k in selected]))
        self.outputs.array(recipe.task+'-responses.npy',responses)
        self.outputs.array(recipe.task+'-full-trajectory.npy',result['full'])
        for name,value in result['trajectories'].items():self.outputs.array(recipe.task+'-'+name+'-trajectory.npy',value)
        for pair,value in result['permutation_pairs'].items():self.outputs.array(recipe.task+'-'+pair[0]+'-'+pair[1]+'-null.npy',value['null_distances'])
        for fraction_index,(fraction,draws) in enumerate(result['mislabel_draws'].items()):
            prefix=recipe.task+f'-relabel-{fraction_index:03d}'
            self.outputs.array(prefix+'-labels.npy',np.stack([row['labels'] for row in draws]))
            values=np.full((len(draws),4),np.nan)
            for i,row in enumerate(draws):
                if row['disposition']=='computed':values[i]=[row['distances'][c] for c in ('PkC_ss','GoC','MFB','MLI')]
            self.outputs.array(prefix+'-distances.npy',values)
            self.outputs.json(prefix+'-dispositions.json',{'fraction':fraction,'draws':[r['disposition'] for r in draws],
                'inferential_status':'original finite-sample tail and confidence-interval producer unresolved'})
        self.outputs.json(recipe.task+'-dispositions.json',{'all_units':prediction.units,'selected':tuple(selected),
            'confidence_rule':'strictly >2','complex_spikes':'excluded from four-class trajectories',
            'normalization':normalization,'method_recipe':recipe})
        self.events.append({'stage':'behaviour','task':recipe.task,'status':'returned'})
        return result

    def full_dispositions(self):
        # Never accept caller-supplied completion flags. These partial producer
        # returns do not establish full panel-family or historical equivalence.
        returned=set()
        if 'waveform' in self.vaes and 'acg' in self.vaes:returned.add('vae_pretraining')
        if any(k[1]==Population.MOUSE_GROUND_TRUTH for k in self.predictions):returned.add('unit_loo')
        if all(any(k[1]==p for k in self.predictions) for p in (Population.MOUSE_EXPERT,Population.MONKEY_EXPERT)):
            returned.add('external_transfer')
        return tuple({'name':o.name,'panels':o.panels,'populations':o.populations,'producer':o.producer,
            'status':'partial_producer_returned_unqualified' if o.name in returned else 'missing_producer_or_input',
            'prerequisites':o.prerequisite} for o in OBLIGATIONS)

def run(*args,**kwargs):
    raise MethodGap('No genuine qualified source/native/target issuer is supplied; public execution remains inactive')

def score(*args,**kwargs):
    raise MethodGap('Standalone untrusted target/reference dictionaries cannot issue a protected evaluation')
