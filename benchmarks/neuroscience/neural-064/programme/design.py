"""Frozen source design; declarations are not admitted cohort membership."""
CATALOGUE={'declared_experiments':1936,'declared_mice':107,'declared_sessions':703,'status':'unverified_source_declaration'}
SECONDARY={'declared_experiments':475,'declared_containers':204,'declared_mice':80,'roles':{'fit':55,'validation':11,'query':14},'status':'unverified_source_declaration'}
CONDITIONS=('Familiar','Novel 1','Novel >1')
CELL_TYPES=('Slc17a7-IRES2-Cre','Sst-IRES-Cre','Vip-IRES-Cre')
POLICIES=('prestate_history','outcome_conditioned_sensitivity')
ROLE_NAMES=('fit','validation','query')
NUISANCE_CATEGORICAL=('cre_line','image_set','image','area','change','pupil_bin','running_bin','history_bin')
NUISANCE_CONTINUOUS=('depth','running','prior_image_count')
OUTCOME_FIELDS=('aborted','auto_rewarded','hit','miss','false_alarm','correct_reject','go','catch')
REFERENCE_GRID=tuple({'max_leaf_nodes':leaf,'l2_regularization':penalty,'max_iter':200,'learning_rate':0.1,'min_samples_leaf':20,'early_stopping':False,'random_state':127} for leaf in (15,31) for penalty in (0.0,1.0))
ANALYSIS_OBLIGATIONS=('catalogue_identifiability_support','secondary_prestate_prediction_contrast','secondary_outcome_conditioned_sensitivity')
