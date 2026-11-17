"""Root-selected investigation semantics; no original data instantiated."""
from .core import need, exact, digest
PARTICIPANTS=tuple("sub-%02d"%i for i in range(1,11))
VIDEOS=tuple("vid%04d"%i for i in range(1,1103))
ROI_FAMILIES=("V1v","V1d","V2v","V2d","V3v","V3d","hV4","EBA","FFA","OFA","STS","LOC","PPA","RSC","TOS","V3ab","IPS0","IPS1-2-3","7AL","BA2","PFt","PFop","MT")
ROIS=tuple(hemi+roi for roi in ROI_FAMILIES for hemi in ("l","r"))
CONDITIONS=("frozen_program","case_adaptive_equal_inputs_tools_compute")
ARMS=("generic","supplied_reference","agent_with_reference")
MODELS=("static_center","static_mean","static_orderless","motion_only","static_motion_category","dynamic_motion_category","shuffled_motion_category","reverse_motion_category")
PRIMARY="dynamic_motion_category"
REFERENCE_MODELS=("static_motion_category","dynamic_motion_category")
REFERENCE_PRODUCER="n070_fixed_reference_v2"
MEASUREMENT_LABEL="conditional_on_released_joint_GLMsingle_VersionB_estimator"
ALPHAS=(0.1,1.0,10.0,100.0)
def specification():
    return {"id":"NEURAL-070","measurement":MEASUREMENT_LABEL,"participants":list(PARTICIPANTS),
            "videos":list(VIDEOS),"rois":list(ROIS),"conditions":list(CONDITIONS),"arms":list(ARMS),
            "models":list(MODELS),"outer_folds":5,"inner_folds":5,"alphas":list(ALPHAS),
            "pca_rank":100,"repeat_aggregation":"equal_video_after_fold_training_only_session_normalization",
            "metric":"raw_unclipped_candidate_dynamic_motion_category_R2",
            "protected_comparators":list(REFERENCE_MODELS),
            "comparator_custody":"original_Engine_reference_attempt_and_immutable_capture_once_per_view",
            "candidate_self_contrast":"secondary_descriptive_only_never_reward_or_pass_gate",
            "aggregate":"equal_46_ROI_then_equal_10_participant_only_if_every_cell_defined",
            "split_claim":"public_development; protected_grouped_partition_not_independent_raw_measurement",
            "published_test_102":"exposed_development_only",
            "BMDgeneral":"task_response_derived_descriptive_hold",
            "inference":"shared_resamples_for_primary_and_fixed_comparisons; each_separate46_ROI_family_Bonferroni; descriptive_until_calibrated",
            "revision":"prospective_V2_metric_amendment_not_historical_score_parity"}
def protocol_identity():return digest(specification())
def reference_procedure_identity():
    return digest({"producer":REFERENCE_PRODUCER,"protocol":protocol_identity(),"models":list(MODELS),
                   "caller":"reference.run->models.choose_and_predict","selection":"fixed_training_only_inner_loss_layer_alpha",
                   "source_binding":"actual_original_Engine_before_source_tree_identity"})
def repetitions(video):return 3 if int(video[3:])<=1000 else 10
def validate_roi_policy(policy):
    exact(policy,("rois","space","source_identity","independent_of_task_responses","coordinate_policy","clinical_availability"))
    need(tuple(policy["rois"])==ROIS and policy["independent_of_task_responses"]is True,
         "All 46 independently fixed anatomical/localizer ROIs; no task-response ROI selection")
    need(policy["space"]=="fsLR32k" and policy["coordinate_policy"]=="fixed_before_task_targets",
         "One exact coordinate system and independent fixed coordinate roster")
    need(policy["source_identity"] and policy["clinical_availability"]=="independently_ascertained","Real mask/availability producer required")
    return policy

